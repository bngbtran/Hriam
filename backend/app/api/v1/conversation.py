"""API Hội thoại trực tiếp và WebSocket Realtime (docs/01 §4.9, docs/06, docs/07 §9–10)."""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ...core import ratelimit
from ...core.db import get_db
from ...core.deps import client_key, current_user, optional_user
from ...core.errors import AppError, not_found, ok
from ...models import ConversationRoom, User
from ...schemas.requests import JoinTokenIn, RoomCreateIn, TurnIn
from ...services import conversation
from ...services.conversation import room_manager

router = APIRouter(tags=["conversation"])


@router.post("/conversations/rooms")
def create_room(body: RoomCreateIn, request: Request, user: User | None = Depends(optional_user),
                db: Session = Depends(get_db)):
    ratelimit.check("room_create", client_key(request, user))
    room = conversation.create_room(db, user, body.model_dump())
    return ok(conversation.room_view(room), 201)


@router.get("/conversations/rooms/{room_id}")
def get_room(room_id: uuid.UUID, db: Session = Depends(get_db)):
    room = db.get(ConversationRoom, room_id)
    if not room or room.status == "closed":
        raise not_found()
    return ok(conversation.room_view(room))


@router.get("/conversations/rooms/code/{room_code}")
def get_room_by_code(room_code: str, db: Session = Depends(get_db)):
    room = conversation.get_room_by_code(db, room_code)
    if not room:
        raise not_found()
    return ok(conversation.room_view(room))


@router.post("/conversations/rooms/{room_id}/join-token")
def issue_token(room_id: uuid.UUID, body: JoinTokenIn, user: User | None = Depends(optional_user),
                db: Session = Depends(get_db)):
    room = db.get(ConversationRoom, room_id)
    if not room or room.status != "active":
        raise not_found()
    token = conversation.issue_join_ticket(
        room, body.participant_alias, body.language_preference, user.id if user else None
    )
    return ok({"token": token, "room": conversation.room_view(room)})


@router.post("/conversations/rooms/{room_id}/turns")
def post_turn(room_id: uuid.UUID, body: TurnIn, db: Session = Depends(get_db)):
    """API gửi lượt nói REST (dành cho chế độ Shared Device hoặc client không dùng WebSocket)."""
    room = db.get(ConversationRoom, room_id)
    if not room or room.status != "active":
        raise not_found()
    turn_res = conversation.execute_turn(
        db, room, body.speaker, body.text, sequence_no=body.sequence_no, audio_ref=body.audio_ref
    )
    return ok(turn_res)


@router.post("/conversations/rooms/{room_id}/end")
def end_room(room_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    room = db.get(ConversationRoom, room_id)
    if not room:
        raise not_found()
    if room.created_by and room.created_by != user.id and "admin" not in user.role_names:
        raise AppError(403, "FORBIDDEN", "Bạn không có quyền kết thúc phòng này.")
    room.status = "closed"
    db.commit()
    return ok({"status": "closed"})


# ---------- WebSocket Realtime Gateway ----------

@router.websocket("/realtime/rooms/{room_id}")  # prefix /api/v1 thêm ở main.py
async def websocket_room_endpoint(websocket: WebSocket, room_id: str, token: str = Query(...),
                                  db: Session = Depends(get_db)):
    """Kênh WebSocket điều phối sự kiện hội thoại thời gian thực (docs/06 §7, docs/07 §10)."""
    ticket = conversation.verify_room_ticket(token, room_id)
    if not ticket:
        await websocket.close(code=4403, reason="Invalid or expired ticket")
        return

    try:
        rid = uuid.UUID(room_id)
        room = db.get(ConversationRoom, rid)
        if not room or room.status != "active":
            await websocket.close(code=4404, reason="Room not found or inactive")
            return
    except ValueError:
        await websocket.close(code=4400, reason="Invalid room id")
        return

    await room_manager.connect(room_id, websocket)
    alias = ticket.get("alias", "Khách")
    participant_lang = ticket.get("language", "vi")

    # Thông báo cho client đã tham gia thành công
    await websocket.send_json({
        "type": "room.joined",
        "room_id": room_id,
        "payload": {"alias": alias, "language": participant_lang, "mode": room.mode}
    })

    # Broadcast cho cả phòng biết có người mới tham gia
    await room_manager.broadcast(room_id, {
        "type": "participant.joined",
        "room_id": room_id,
        "payload": {"alias": alias, "language": participant_lang}
    })

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                event = json.loads(raw_data)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type")
            payload = event.get("payload", {})

            if event_type == "turn.start":
                # Lượt nói bắt đầu (VAD speech detected hoặc push-to-talk press)
                await room_manager.broadcast(room_id, {
                    "type": "turn.started",
                    "room_id": room_id,
                    "turn_id": event.get("turn_id", str(uuid.uuid4())),
                    "payload": {"speaker": payload.get("language", participant_lang), "alias": alias}
                })

            elif event_type in ("turn.end", "audio.chunk", "turn.text"):
                # Khi kết thúc lượt nói hoặc gửi văn bản lượt nói
                text = payload.get("text", "")
                speaker = payload.get("language", participant_lang)
                if text:
                    # Dịch máy chạy CPU nặng: đưa sang luồng phụ để không chặn các kết nối khác
                    turn_result = await run_in_threadpool(conversation.execute_turn, db, room, speaker, text)
                    await room_manager.broadcast(room_id, {
                        "type": "transcript.final",
                        "room_id": room_id,
                        "turn_id": turn_result["turn_id"],
                        "payload": {"text": text, "language": speaker, "alias": alias}
                    })
                    await room_manager.broadcast(room_id, {
                        "type": "translation.final",
                        "room_id": room_id,
                        "turn_id": turn_result["turn_id"],
                        "payload": {
                            "text": turn_result["translated_text"],
                            "target_language": turn_result["target_language"],
                            "status": turn_result["translation_status"],
                            "model_version": turn_result["model_version"],
                            "seconds": turn_result["seconds"]
                        }
                    })
                    await room_manager.broadcast(room_id, {
                        "type": "turn.completed",
                        "room_id": room_id,
                        "turn_id": turn_result["turn_id"]
                    })

            elif event_type == "room.leave":
                break

    except WebSocketDisconnect:
        pass
    finally:
        room_manager.disconnect(room_id, websocket)
        await room_manager.broadcast(room_id, {
            "type": "participant.left",
            "room_id": room_id,
            "payload": {"alias": alias}
        })
