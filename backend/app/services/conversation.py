"""Dịch vụ Live Conversation & Realtime (docs/01 §4.9, docs/06, docs/07 §9-10).

Hỗ trợ:
- Quản lý phòng hội thoại (Shared Device / Two Devices Room với mã tham gia).
- Cấp vé tham gia (Join Token) ngắn hạn an toàn.
- Điều phối WebSocket realtime: VAD events, Turn events, phụ đề song ngữ.
- Tích hợp pipeline dịch máy (MT) và từ điển.
- Tuân thủ quyền riêng tư: mặc định KHÔNG lưu âm thanh và nội dung hội thoại trừ khi phòng bật lưu.
"""
from __future__ import annotations

import hashlib
import secrets
import string
import time
import uuid
from datetime import timedelta
from typing import Any

import jwt
from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import utcnow
from ..core.deps import audit
from ..core.errors import AppError, not_found
from ..core.text import nfc
from ..models import ConversationParticipant, ConversationRoom, ConversationTurn, User
from . import translation


def _generate_room_code() -> str:
    chars = string.ascii_uppercase + string.digits
    # Loại trừ ký tự dễ nhầm lẫn (0, O, 1, I)
    clean_chars = [c for c in chars if c not in "0O1I"]
    return "".join(secrets.choice(clean_chars) for _ in range(6))


def create_room(db: Session, user: User | None, data: dict) -> ConversationRoom:
    code = _generate_room_code()
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    expires_at = utcnow() + timedelta(hours=24)

    room = ConversationRoom(
        room_code=code,
        room_code_hash=code_hash,
        mode=data.get("mode", "shared_device"),
        language_a=data.get("language_a", "ede"),
        language_b=data.get("language_b", "vi"),
        endpointing_mode=data.get("endpointing_mode", "push_to_talk"),
        silence_threshold_ms=min(5000, max(500, int(data.get("silence_threshold_ms", 1500)))),
        status="active",
        created_by=user.id if user else None,
        expires_at=expires_at,
        save_audio_enabled=bool(data.get("save_audio", False)),
        save_transcript_enabled=bool(data.get("save_transcript", False)),
    )
    db.add(room)
    db.flush()
    if user:
        audit(db, user, "conversation.create_room", "conversation_room", room.id, mode=room.mode)
    db.commit()
    return room


def get_room_by_code(db: Session, code: str) -> ConversationRoom | None:
    clean_code = code.strip().upper()
    room = db.scalar(
        select(ConversationRoom).where(
            ConversationRoom.room_code == clean_code,
            ConversationRoom.status == "active",
        )
    )
    if room:
        now = utcnow()
        expires = room.expires_at if room.expires_at.tzinfo else room.expires_at.replace(tzinfo=now.tzinfo)
        if expires < now:
            room.status = "expired"
            db.commit()
            return None
    return room


def issue_join_ticket(room: ConversationRoom, alias: str, language_pref: str, user_id: uuid.UUID | None = None) -> str:
    """Cấp vé JWT ngắn hạn (5 phút) cho kết nối WebSocket."""
    now = utcnow()
    payload = {
        "sub": str(user_id) if user_id else f"guest-{secrets.token_hex(4)}",
        "room_id": str(room.id),
        "room_code": room.room_code,
        "alias": alias,
        "language": language_pref,
        "type": "room_ticket",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def verify_room_ticket(token: str, room_id: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        if payload.get("type") != "room_ticket" or payload.get("room_id") != room_id:
            return None
        return payload
    except jwt.PyJWTError:
        return None


def execute_turn(
    db: Session, room: ConversationRoom, speaker: str, text: str,
    sequence_no: int = 1, participant_id: uuid.UUID | None = None, audio_ref: str | None = None
) -> dict:
    """Xử lý một lượt nói: Dịch sang ngôn ngữ đối ứng và lưu nếu bật lưu transcript."""
    text_clean = nfc(text).strip()
    if not text_clean:
        raise AppError(422, "EMPTY_TEXT", "Nội dung lượt nói không được để trống.")

    target_lang = "vi" if speaker == "ede" else "ede"
    start_time = utcnow()
    t_result = translation.translate(db, text_clean, speaker, target_lang)
    end_time = utcnow()

    turn_data = {
        "turn_id": str(uuid.uuid4()),
        "sequence_no": sequence_no,
        "speaker": speaker,
        "target_language": target_lang,
        "original_text": text_clean,
        "translated_text": t_result.translated_text,
        "translation_status": t_result.translation_status,
        "model_version": t_result.model_version,
        "uncertainty_notes": t_result.uncertainty_notes,
        "seconds": t_result.seconds,
        "started_at": start_time.isoformat(),
        "ended_at": end_time.isoformat(),
    }

    if room.save_transcript_enabled:
        turn = ConversationTurn(
            id=uuid.UUID(turn_data["turn_id"]),
            room_id=room.id,
            participant_id=participant_id,
            sequence_no=sequence_no,
            input_language=speaker,
            audio_ref=audio_ref if room.save_audio_enabled else None,
            transcript_final=text_clean,
            translated_text=t_result.translated_text,
            translation_model_version=t_result.model_version,
            status="completed",
            started_at=start_time,
            ended_at=end_time,
        )
        db.add(turn)
        db.commit()

    return turn_data


def room_view(room: ConversationRoom) -> dict:
    return {
        "id": str(room.id),
        "room_code": room.room_code,
        "mode": room.mode,
        "language_a": room.language_a,
        "language_b": room.language_b,
        "endpointing_mode": room.endpointing_mode,
        "silence_threshold_ms": room.silence_threshold_ms,
        "status": room.status,
        "expires_at": room.expires_at,
        "save_audio": room.save_audio_enabled,
        "save_transcript": room.save_transcript_enabled,
        "participant_count": len(room.participants),
        "created_at": room.created_at,
    }


# ---------- WebSocket Hub ----------

class RoomConnectionManager:
    """Quản lý các kết nối WebSocket đang hoạt động theo room_id."""

    def __init__(self):
        self.active_rooms: dict[str, set[WebSocket]] = {}
        self.turn_counters: dict[str, int] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.active_rooms:
            self.active_rooms[room_id] = set()
            self.turn_counters[room_id] = 1
        self.active_rooms[room_id].add(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        if room_id in self.active_rooms:
            self.active_rooms[room_id].discard(websocket)
            if not self.active_rooms[room_id]:
                del self.active_rooms[room_id]
                self.turn_counters.pop(room_id, None)

    async def broadcast(self, room_id: str, message: dict):
        if room_id in self.active_rooms:
            for connection in list(self.active_rooms[room_id]):
                try:
                    await connection.send_json(message)
                except Exception:
                    self.active_rooms[room_id].discard(connection)


room_manager = RoomConnectionManager()
