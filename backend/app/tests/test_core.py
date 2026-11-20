"""Test theo docs/09 §5: Unicode, quyền, đóng góp, kiểm duyệt, strike, khiếu nại, số điện thoại, dịch."""
from __future__ import annotations

import unicodedata

from app.core.text import guess_language, nfc, search_key
from app.tests.conftest import PASSWORD, idem, make_user

EDE = "Kâo čiăng ƀơ̆ng êsei ê̆ ô̆ ư̆"


# ---------- Unicode ----------

def test_unicode_preserves_combining_marks():
    decomposed = unicodedata.normalize("NFD", EDE)
    assert nfc(decomposed) == unicodedata.normalize("NFC", EDE)
    assert "̆" in nfc("ê̆")  # dấu trăng rời không bị xoá
    assert search_key("Ƀŏng") == "ƀŏng" != search_key("Bong")


def test_language_guess_does_not_confuse_vietnamese_breve():
    assert guess_language("Tôi muốn ăn cơm") == "vi"
    assert guess_language("Kâo čiăng ƀơ̆ng") == "ede"


def test_unicode_round_trip_through_contribution(client):
    u = make_user(client, "lan")
    r = client.post("/api/v1/contributions", headers=u["headers"], json={
        "submission_type": "phrase", "ede_form": unicodedata.normalize("NFD", EDE), "proposed_vi_meaning": "Câu thử",
        "consents": {"publish_as_lexicon": True}})
    assert r.status_code == 201
    got = client.get(f"/api/v1/contributions/{r.json()['data']['id']}", headers=u["headers"]).json()["data"]
    assert got["ede_form"] == unicodedata.normalize("NFC", EDE)


# ---------- Quyền ----------

def test_permissions_enforced_on_backend(client):
    u = make_user(client, "binh")
    for path in ("/api/v1/admin/contributions", "/api/v1/admin/moderation/cases", "/api/v1/admin/users",
                 "/api/v1/admin/audit", "/api/v1/admin/dataset-releases"):
        assert client.get(path, headers=u["headers"]).status_code == 403, path
    assert client.get("/api/v1/admin/users").status_code == 401


def test_admin_is_not_language_expert(client):
    admin = make_user(client, "quantri", ("admin",))
    me = client.get("/api/v1/me", headers=admin["headers"]).json()["data"]
    assert "lexicon.approve" in me["permissions"] and "lexicon.verify" not in me["permissions"]


def test_error_envelope(client):
    r = client.post("/api/v1/translations", json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.get("/api/v1/health").json()["meta"]["request_id"]


# ---------- Đóng góp ----------

def _submit(client, user, **extra):
    body = {"submission_type": "word", "ede_form": "Hriăm", "proposed_vi_meaning": "Học",
            "consents": {"publish_as_lexicon": True}} | extra
    r = client.post("/api/v1/contributions", headers=user["headers"], json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def test_contribution_not_in_master_until_approved(client):
    u = make_user(client, "lan")
    _submit(client, u)
    assert client.get("/api/v1/lexicon/search", params={"q": "hriăm"}).json()["data"] == []


def test_approve_promotes_exactly_once(client):
    u, expert = make_user(client, "lan"), make_user(client, "chuyengia", ("language_expert",))
    sid = _submit(client, u)
    headers = expert["headers"] | idem()
    body = {"reason_code": "OK", "review_note": "Đúng"}
    r1 = client.post(f"/api/v1/admin/contributions/{sid}/approve", headers=headers, json=body)
    r2 = client.post(f"/api/v1/admin/contributions/{sid}/approve", headers=headers, json=body)  # retry cùng key
    assert r1.status_code == r2.status_code == 200 and r1.json()["data"] == r2.json()["data"]
    found = client.get("/api/v1/lexicon/search", params={"q": "hriăm"}).json()["data"]
    assert len(found) == 1 and found[0]["senses"][0]["status"] == "verified"
    r3 = client.post(f"/api/v1/admin/contributions/{sid}/approve", headers=expert["headers"] | idem(), json=body)
    assert r3.status_code == 409


def test_admin_approval_is_not_expert_verification(client):
    u, admin = make_user(client, "lan"), make_user(client, "quantri", ("admin",))
    sid = _submit(client, u)
    client.post(f"/api/v1/admin/contributions/{sid}/approve", headers=admin["headers"] | idem(),
                json={"reason_code": "OK"})
    sense = client.get("/api/v1/lexicon/search", params={"q": "hriăm"}).json()["data"][0]["senses"][0]
    assert sense["status"] == "draft"


def test_reject_purges_content_keeps_minimal_audit(client):
    u, expert = make_user(client, "lan"), make_user(client, "chuyengia", ("language_expert",))
    admin = make_user(client, "quantri", ("admin",))
    sid = _submit(client, u, context_text="Ngữ cảnh riêng tư")
    client.post(f"/api/v1/admin/contributions/{sid}/reject", headers=expert["headers"] | idem(),
                json={"reason_code": "DUPLICATE"})
    got = client.get(f"/api/v1/contributions/{sid}", headers=u["headers"]).json()["data"]
    assert got["status"] == "rejected" and got["purged"] and got["ede_form"] is None and got["context_text"] is None
    logs = client.get("/api/v1/admin/audit", headers=admin["headers"]).json()["data"]
    entry = next(a for a in logs if a["action"] == "contribution.reject")
    assert entry["reason_code"] == "DUPLICATE" and "Hriăm" not in str(entry) and "riêng tư" not in str(entry)


def test_approval_requires_publication_consent(client):
    u, expert = make_user(client, "lan"), make_user(client, "chuyengia", ("language_expert",))
    sid = _submit(client, u, consents={"publish_as_lexicon": False})
    r = client.post(f"/api/v1/admin/contributions/{sid}/approve", headers=expert["headers"] | idem(),
                    json={"reason_code": "OK"})
    assert r.status_code == 409


def test_approve_requires_idempotency_key(client):
    u, expert = make_user(client, "lan"), make_user(client, "chuyengia", ("language_expert",))
    sid = _submit(client, u)
    r = client.post(f"/api/v1/admin/contributions/{sid}/approve", headers=expert["headers"], json={"reason_code": "OK"})
    assert r.status_code == 400


# ---------- Diễn đàn & kiểm duyệt ----------

def _post(client, user, body="Xin hỏi cách đọc chữ này?"):
    r = client.post("/api/v1/forum/posts", headers=user["headers"],
                    json={"category": "hoi-dap", "title": "Câu hỏi", "body_text": body})
    assert r.status_code == 202
    return r.json()["data"]


def test_ede_post_held_for_human_review_and_hidden(client):
    u = make_user(client, "lan")
    post = _post(client, u, "Kâo čiăng ƀơ̆ng êsei")
    assert post["status"] == "pending_human_review"
    assert client.get("/api/v1/forum/posts").json()["data"] == []
    assert client.get(f"/api/v1/forum/posts/{post['id']}").status_code == 404
    assert client.get(f"/api/v1/forum/posts/{post['id']}", headers=u["headers"]).status_code == 200


def test_clear_vietnamese_post_published(client):
    u = make_user(client, "lan")
    assert _post(client, u)["status"] == "published"
    assert len(client.get("/api/v1/forum/posts").json()["data"]) == 1


def test_automatic_spam_reject_gives_no_strike(client):
    u = make_user(client, "lan")
    post = _post(client, u, "Xem ngay " + " ".join(f"http://spam{i}.example" for i in range(5)))
    assert post["status"] == "rejected"
    assert client.get("/api/v1/me/strikes", headers=u["headers"]).json()["data"]["effective_strikes"] == 0


def _held_case(client, user, mod):
    _post(client, user, "Kâo čiăng ƀơ̆ng êsei")
    cases = client.get("/api/v1/admin/moderation/cases", headers=mod["headers"]).json()["data"]
    return cases[0]["id"]


def _reject_with_strike(client, user, mod):
    cid = _held_case(client, user, mod)
    r = client.post(f"/api/v1/admin/moderation/cases/{cid}/reject", headers=mod["headers"] | idem(),
                    json={"reason_code": "HARASSMENT", "apply_strike": True})
    assert r.status_code == 200, r.text
    return cid


def test_fourth_strike_bans_account_and_restricts_phone(client):
    u = make_user(client, "lan", phone="0901234567")
    mod = make_user(client, "kiemduyet", ("moderator",))
    for _ in range(3):
        _reject_with_strike(client, u, mod)
    me = client.get("/api/v1/me", headers=u["headers"]).json()["data"]
    assert me["effective_strikes"] == 3 and me["status"] == "active"
    _reject_with_strike(client, u, mod)
    assert client.get("/api/v1/me", headers=u["headers"]).json()["data"]["status"] == "permanently_banned"
    r = client.post("/api/v1/auth/register", json={"username": "lanmoi", "display_name": "Lan", "password": PASSWORD,
                                                   "accept_terms": True, "phone": "+84901234567"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "REGISTRATION_BLOCKED"


def test_strike_once_per_case(client):
    u, mod = make_user(client, "lan"), make_user(client, "kiemduyet", ("moderator",))
    cid = _reject_with_strike(client, u, mod)
    r = client.post(f"/api/v1/admin/moderation/cases/{cid}/apply-strike", headers=mod["headers"] | idem())
    assert r.json()["data"]["applied"] is False
    assert client.get("/api/v1/me/strikes", headers=u["headers"]).json()["data"]["effective_strikes"] == 1


def test_appeal_accepted_reduces_strike_once(client):
    u, mod = make_user(client, "lan"), make_user(client, "kiemduyet", ("moderator",))
    mod2 = make_user(client, "kiemduyet2", ("moderator",))
    cid = _reject_with_strike(client, u, mod)
    r = client.post("/api/v1/appeals", headers=u["headers"],
                    json={"moderation_case_id": cid, "appeal_text": "Đây là câu tiếng Ê Đê bình thường."})
    assert r.status_code == 201
    aid = r.json()["data"]["id"]
    key = idem()
    for _ in range(2):  # gọi lại cùng key không đảo strike hai lần
        r = client.post(f"/api/v1/admin/appeals/{aid}/accept", headers=mod2["headers"] | key,
                        json={"decision_note": "Nội dung hợp lệ."})
        assert r.status_code == 200, r.text
    assert client.get("/api/v1/me/strikes", headers=u["headers"]).json()["data"]["effective_strikes"] == 0
    r = client.post(f"/api/v1/admin/appeals/{aid}/accept", headers=mod2["headers"] | idem(),
                    json={"decision_note": "Lần nữa"})
    assert r.status_code == 409


def test_banned_user_can_appeal_but_not_post(client):
    u, mod = make_user(client, "lan"), make_user(client, "kiemduyet", ("moderator",))
    cids = [_reject_with_strike(client, u, mod) for _ in range(4)]
    r = client.post("/api/v1/forum/posts", headers=u["headers"], json={"category": "hoi-dap", "title": "abc",
                                                                       "body_text": "xin chào"})
    assert r.status_code == 403
    r = client.post("/api/v1/appeals", headers=u["headers"],
                    json={"moderation_case_id": cids[0], "appeal_text": "Xin xem lại quyết định này."})
    assert r.status_code == 201


def test_admin_unban_and_phone_release_are_audited(client):
    u = make_user(client, "lan", phone="0901234567")
    admin = make_user(client, "quantri", ("admin",))
    client.post(f"/api/v1/admin/users/{u['id']}/ban", headers=admin["headers"] | idem(),
                json={"reason_code": "MANUAL", "note": "Thử nghiệm"})
    restrictions = client.get("/api/v1/admin/phone-restrictions", headers=admin["headers"]).json()["data"]
    assert len(restrictions) == 1 and "phone_hmac" not in restrictions[0]
    r = client.post(f"/api/v1/admin/users/{u['id']}/unban", headers=admin["headers"] | idem(),
                    json={"reason_code": "APPEAL", "note": "Đã xác minh nhầm lẫn"})
    assert r.json()["data"]["status"] == "active"
    actions = [a["action"] for a in client.get(f"/api/v1/admin/users/{u['id']}/audit",
                                               headers=admin["headers"]).json()["data"]]
    assert "user.ban" in actions and "user.unban" in actions
    r = client.post("/api/v1/auth/register", json={"username": "lanmoi", "display_name": "Lan", "password": PASSWORD,
                                                   "accept_terms": True, "phone": "0901234567"})
    assert r.status_code == 201  # hạn chế đã được gỡ khi mở khoá


def test_report_creates_review_case(client):
    u, other = make_user(client, "lan"), make_user(client, "binh")
    mod = make_user(client, "kiemduyet", ("moderator",))
    post = _post(client, u)
    r = client.post(f"/api/v1/forum/posts/{post['id']}/report", headers=other["headers"],
                    json={"reason_code": "SPAM"})
    assert r.status_code == 202
    cases = client.get("/api/v1/admin/moderation/cases", params={"queue": "reports"},
                       headers=mod["headers"]).json()["data"]
    assert len(cases) == 1


# ---------- Dịch ----------

def test_translation_without_model_marks_needs_review(client):
    d = client.post("/api/v1/translations", json={"text": "Adŭ", "source_language": "ede"}).json()["data"]
    assert d["translation_status"] == "needs_review" and d["verified_matches"] == []
    assert any(n["code"] == "UNVERIFIED_TERMS" for n in d["uncertainty_notes"])


def test_verified_memory_takes_precedence(client):
    u, expert = make_user(client, "lan"), make_user(client, "chuyengia", ("language_expert",))
    sid = _submit(client, u, submission_type="sentence_pair", ede_form="Kâo čiăng ƀơ̆ng êsei",
                  proposed_vi_meaning="Tôi muốn ăn cơm")
    client.post(f"/api/v1/admin/contributions/{sid}/approve", headers=expert["headers"] | idem(),
                json={"reason_code": "OK"})
    d = client.post("/api/v1/translations", json={"text": "Tôi muốn ăn cơm", "source_language": "vi"}).json()["data"]
    assert d["translation_status"] == "verified_memory" and d["translated_text"] == "Kâo čiăng ƀơ̆ng êsei"


def test_dictionary_example_used_for_exact_sentence(client):
    from app.core.db import SessionLocal
    from app.models import CorpusExample
    from app.services.lexicon import term_index
    with SessionLocal() as db:
        db.add(CorpusExample(text_ede="Jŭ msĕ si ak", text_vi="Đen như quạ"))
        db.commit()
    term_index.invalidate()
    d = client.post("/api/v1/translations", json={"text": "Jŭ msĕ si ak", "source_language": "ede"}).json()["data"]
    assert d["translation_status"] == "dictionary_example" and d["translated_text"] == "Đen như quạ"
    d = client.post("/api/v1/translations", json={"text": "Đen như quạ", "source_language": "vi"}).json()["data"]
    assert d["translation_status"] == "dictionary_example" and d["translated_text"] == "Jŭ msĕ si ak"
    d = client.post("/api/v1/translations", json={"text": "Jŭ msĕ si ak", "source_language": "ede",
                                                  "use_verified_memory": False}).json()["data"]
    assert d["translation_status"] == "needs_review"  # tắt tra bộ nhớ thì không dùng câu ví dụ


import pytest


@pytest.fixture
def set_setting():
    """Settings là dataclass đóng băng: đổi bằng object.__setattr__ và trả lại giá trị cũ sau test."""
    from app.core.config import settings
    old: dict = {}

    def apply(name: str, value) -> None:
        old.setdefault(name, getattr(settings, name))
        object.__setattr__(settings, name, value)
    yield apply
    for name, value in old.items():
        object.__setattr__(settings, name, value)


def test_gemini_used_when_no_local_model_and_marked_external(client, monkeypatch, set_setting):
    from app.integrations.gemini import gemini
    seen = {}

    def fake(lines, source, target, glossary=None, examples=None):
        seen.update(lines=lines, glossary=glossary)
        return ["Tôi muốn ăn cơm"]
    set_setting("gemini_api_key", "test-key")
    monkeypatch.setattr(gemini, "translate", fake)
    d = client.post("/api/v1/translations", json={"text": "Êsei Ƀŏng", "source_language": "ede"}).json()["data"]
    assert d["translation_status"] == "machine_draft" and d["translated_text"] == "Tôi muốn ăn cơm"
    assert d["provenance"] == {"type": "machine_translation", "adapter": "gemini", "sends_data_externally": True}
    assert any(n["code"] == "EXTERNAL_MT" for n in d["uncertainty_notes"])
    assert "Êsei = Cơm" in seen["glossary"]  # nghĩa từ điển được đưa vào prompt làm ngữ cảnh


def test_provider_local_never_calls_gemini(client, monkeypatch, set_setting):
    from app.integrations.gemini import gemini
    set_setting("gemini_api_key", "test-key")
    set_setting("mt_provider", "local")
    monkeypatch.setattr(gemini, "translate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("không được gọi")))
    d = client.post("/api/v1/translations", json={"text": "Êsei", "source_language": "ede"}).json()["data"]
    assert d["translation_status"] == "needs_review"


def test_gemini_failure_returns_502(client, monkeypatch, set_setting):
    from app.integrations.gemini import gemini
    set_setting("gemini_api_key", "test-key")
    monkeypatch.setattr(gemini, "translate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("mạng lỗi")))
    r = client.post("/api/v1/translations", json={"text": "Êsei", "source_language": "ede"})
    assert r.status_code == 502


def test_gemini_mode_falls_back_to_local_model(client, monkeypatch, set_setting):
    from app.integrations.gemini import gemini
    from app.integrations.mt import mt
    set_setting("gemini_api_key", "test-key")
    set_setting("mt_provider", "gemini")
    monkeypatch.setattr(gemini, "translate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("mất mạng")))
    monkeypatch.setattr(mt, "available", lambda s, t: True)
    monkeypatch.setattr(mt, "translate", lambda lines, s, t: ["Phòng ăn cơm"])
    d = client.post("/api/v1/translations", json={"text": "Adŭ Ƀŏng Êsei", "source_language": "ede"}).json()["data"]
    assert d["translated_text"] == "Phòng ăn cơm" and d["provenance"]["adapter"] == "nllb"
    assert d["provenance"]["sends_data_externally"] is False


def test_engine_switch_per_request(client, monkeypatch, set_setting):
    from app.integrations.gemini import gemini
    from app.integrations.mt import mt
    set_setting("gemini_api_key", "test-key")
    set_setting("mt_provider", "gemini")  # mặc định máy chủ: Gemini trước
    calls = []
    monkeypatch.setattr(gemini, "translate", lambda *a, **k: calls.append("gemini") or ["Bản Gemini"])
    monkeypatch.setattr(mt, "available", lambda s, t: True)
    monkeypatch.setattr(mt, "translate", lambda lines, s, t: calls.append("local") or ["Bản mô hình"])
    post = lambda **extra: client.post("/api/v1/translations", json={"text": "Êsei Ƀŏng", "source_language": "ede", **extra}).json()["data"]
    d = post(engine="local")
    assert d["translated_text"] == "Bản mô hình" and calls == ["local"]  # chọn local thì không gọi Gemini
    d = post(engine="gemini")
    assert d["translated_text"] == "Bản Gemini" and d["provenance"]["sends_data_externally"] is True
    d = post()  # không chọn: theo cấu hình máy chủ (gemini)
    assert d["translated_text"] == "Bản Gemini"
    assert client.post("/api/v1/translations", json={"text": "x", "source_language": "ede", "engine": "abc"}).status_code == 422


def test_engines_endpoint(client, set_setting):
    d = client.get("/api/v1/translations/engines").json()["data"]
    assert d["gemini"]["available"] is False and d["gemini"]["sends_data_externally"] is True
    set_setting("gemini_api_key", "test-key")
    d = client.get("/api/v1/translations/engines").json()["data"]
    assert d["gemini"]["available"] is True and d["local"]["sends_data_externally"] is False
    assert "test-key" not in str(d)  # không lộ key


def test_gemini_adapter_caches_and_sends_thinking_level(set_setting, monkeypatch):
    from app.integrations.gemini import GeminiAdapter
    set_setting("gemini_api_key", "test-key")
    set_setting("gemini_thinking_level", "minimal")
    calls = []

    class Fake:
        class interactions:
            @staticmethod
            def create(**kw):
                calls.append(kw)
                return type("R", (), {"output_text": "Đen như quạ"})()
    adapter = GeminiAdapter()
    adapter._client = Fake
    assert adapter.translate(["Jŭ msĕ si ak"], "ede", "vi") == ["Đen như quạ"]
    assert adapter.translate(["Jŭ msĕ si ak"], "ede", "vi") == ["Đen như quạ"]
    assert len(calls) == 1 and calls[0]["generation_config"] == {"thinking_level": "minimal"}  # lần 2 lấy từ cache


def test_gemini_billing_error_is_not_retried(set_setting):
    import pytest
    from app.integrations.gemini import GeminiAdapter
    set_setting("gemini_api_key", "test-key")
    calls = []

    class Billing(Exception):
        status_code = 402

    class Fake:
        class interactions:
            @staticmethod
            def create(**kw):
                calls.append(1)
                raise Billing("credits depleted")
    adapter = GeminiAdapter()
    adapter._client = Fake
    with pytest.raises(Billing):
        adapter.translate(["Jŭ msĕ si ak"], "ede", "vi")
    assert len(calls) == 1


def test_history_saved_only_when_enabled(client):
    u = make_user(client, "lan")
    client.post("/api/v1/translations", headers=u["headers"], json={"text": "Adŭ", "source_language": "ede"})
    assert client.get("/api/v1/translations/history", headers=u["headers"]).json()["data"] == []
    client.patch("/api/v1/me", headers=u["headers"], json={"save_translation_history": True})
    client.post("/api/v1/translations", headers=u["headers"], json={"text": "Adŭ", "source_language": "ede"})
    assert len(client.get("/api/v1/translations/history", headers=u["headers"]).json()["data"]) == 1


def test_feedback_with_suggestion_goes_to_contribution_queue(client):
    u = make_user(client, "lan")
    r = client.post("/api/v1/translations/feedback", headers=u["headers"], json={
        "source_text": "Tôi muốn ăn cơm", "translated_text": "Kâo čiăng ŏng êsei", "source_language": "vi",
        "target_language": "ede", "error_type": "spelling", "suggested_translation": "Kâo čiăng ƀơ̆ng êsei"})
    assert r.status_code == 201 and r.json()["data"]["contribution_id"]
    assert client.get("/api/v1/lexicon/search", params={"q": "kâo čiăng"}).json()["data"] == []


def test_refresh_rotation_and_reuse_detection(client):
    make_user(client, "lan")
    old = client.cookies.get("hriam_refresh")
    assert client.post("/api/v1/auth/refresh").status_code == 200
    newest = client.cookies.get("hriam_refresh")
    assert newest != old
    client.cookies.clear()
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old}).status_code == 401
    # dùng lại token cũ -> mọi phiên của người dùng bị thu hồi
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": newest}).status_code == 401


def test_dataset_release_has_manifest_and_checksum(client):
    admin = make_user(client, "quantri", ("admin",))
    r = client.post("/api/v1/admin/dataset-releases", headers=admin["headers"] | idem(),
                    json={"version": "2026.11", "change_summary": "Bản đầu"})
    assert r.status_code == 201
    data = r.json()["data"]
    assert len(data["checksum_sha256"]) == 64 and data["record_counts"]["lexical_entry"] == 3
    assert data["status"] == "research_only"  # giấy phép từ điển nguồn chưa được duyệt
    again = client.post("/api/v1/admin/dataset-releases", headers=admin["headers"] | idem(),
                        json={"version": "2026.11", "change_summary": "Trùng"})
    assert again.status_code == 409


# ---------- Lexical Discovery ----------

def test_lexical_discovery_pipeline_and_approval(client):
    u = make_user(client, "lan")
    expert = make_user(client, "chuyengia", ("language_expert",))
    mod = make_user(client, "kiemduyet", ("moderator",))
    # Đăng bài có bật consent phân tích ngôn ngữ
    post_res = client.post("/api/v1/forum/posts", headers=u["headers"], json={
        "category": "tu-vung", "title": "Tìm hiểu từ mới",
        "body_text": "Klei mghao čiăng bla bla kdrêč",
        "consent_research_analysis": True,
    })
    assert post_res.status_code == 202
    pid = post_res.json()["data"]["id"]

    # Duyệt bài qua moderation để chuyển sang published
    cases = client.get("/api/v1/admin/moderation/cases", headers=mod["headers"]).json()["data"]
    pcase = next(c for c in cases if c["content_id"] == pid)
    client.post(f"/api/v1/admin/moderation/cases/{pcase['id']}/approve", headers=mod["headers"] | idem(),
                json={})

    # Chạy pipeline discovery
    run_res = client.post("/api/v1/admin/lexical-candidates/run-discovery", headers=expert["headers"])
    assert run_res.status_code == 200

    # Liệt kê candidates
    cands_res = client.get("/api/v1/admin/lexical-candidates", headers=expert["headers"])
    assert cands_res.status_code == 200
    cands = cands_res.json()["data"]
    assert len(cands) > 0
    cid = cands[0]["id"]

    # Xem chi tiết candidate
    detail_res = client.get(f"/api/v1/admin/lexical-candidates/{cid}", headers=expert["headers"])
    assert detail_res.status_code == 200
    assert "occurrences" in detail_res.json()["data"]

    # Duyệt candidate vào Master Lexicon
    appr_res = client.post(f"/api/v1/admin/lexical-candidates/{cid}/approve",
                           headers=expert["headers"] | idem(),
                           json={"definition_vi": "Nghĩa thử nghiệm", "reason_code": "VERIFIED_VALID"})
    assert appr_res.status_code == 200
    assert appr_res.json()["data"]["status"] == "approved"



# ---------- Live Conversation ----------

def test_conversation_room_and_turns(client):
    u = make_user(client, "lan")
    # Tạo room
    room_res = client.post("/api/v1/conversations/rooms", headers=u["headers"], json={
        "mode": "two_devices", "language_a": "ede", "language_b": "vi",
        "endpointing_mode": "push_to_talk", "silence_threshold_ms": 1500,
        "save_transcript": True
    })
    assert room_res.status_code == 201
    room = room_res.json()["data"]
    assert len(room["room_code"]) == 6
    rid = room["id"]

    # Tra cứu room qua code
    code_res = client.get(f"/api/v1/conversations/rooms/code/{room['room_code']}")
    assert code_res.status_code == 200

    # Cấp join token
    token_res = client.post(f"/api/v1/conversations/rooms/{rid}/join-token", json={
        "participant_alias": "Bạn A", "language_preference": "ede"
    })
    assert token_res.status_code == 200
    assert "token" in token_res.json()["data"]

    # Gửi một lượt nói
    turn_res = client.post(f"/api/v1/conversations/rooms/{rid}/turns", json={
        "speaker": "vi", "text": "Tôi muốn ăn cơm", "sequence_no": 1
    })
    assert turn_res.status_code == 200
    turn = turn_res.json()["data"]
    assert turn["target_language"] == "ede"
    assert turn["translated_text"]


# ---------- Cultural Archive ----------

def test_cultural_archive_access_tiers(client):
    u = make_user(client, "lan")
    expert = make_user(client, "chuyengia", ("language_expert",))

    # Đăng một mục văn hoá cấp community
    item_res = client.post("/api/v1/culture/items", headers=u["headers"], json={
        "title": "Sử thi Đăm Săn", "category": "story",
        "content_ede": "Klei khan Dam San...", "content_vi": "Sử thi Đăm Săn kể về...",
        "access_tier": "community"
    })
    assert item_res.status_code == 201
    item_id = item_res.json()["data"]["id"]

    # Khách chưa đăng nhập không đọc được nội dung community
    guest_view = client.get(f"/api/v1/culture/items/{item_id}")
    assert "hạn chế" in guest_view.json()["data"]["content_ede"]

    # Thành viên đã đăng nhập đọc được nội dung community
    member_view = client.get(f"/api/v1/culture/items/{item_id}", headers=u["headers"])
    assert member_view.json()["data"]["content_ede"] == "Klei khan Dam San..."


# ---------- Phone Verification ----------

def test_phone_verification_flow(client):
    u = make_user(client, "lan")
    # Yêu cầu mã xác thực
    req_res = client.post("/api/v1/auth/request-phone-code", headers=u["headers"], json={
        "phone": "+84912345678"
    })
    assert req_res.status_code == 200
    code = req_res.json()["data"]["dev_code_hint"]

    # Nhập mã xác thực
    verify_res = client.post("/api/v1/auth/verify-phone", headers=u["headers"], json={
        "code": code
    })
    assert verify_res.status_code == 200
    assert verify_res.json()["data"]["verified"] is True



# ---------- Phòng hội thoại hai thiết bị ----------

def test_room_flow_by_code_join_and_websocket(client):
    room = client.post("/api/v1/conversations/rooms", json={"mode": "two_devices", "save_transcript": True}).json()["data"]
    assert room["save_transcript"] is True
    found = client.get(f"/api/v1/conversations/rooms/code/{room['room_code'].lower()}")
    assert found.status_code == 200 and found.json()["data"]["id"] == room["id"]
    assert client.get("/api/v1/conversations/rooms/code/ZZZZZZ").status_code == 404
    ticket = client.post(f"/api/v1/conversations/rooms/{room['id']}/join-token",
                         json={"participant_alias": "Lan", "language_preference": "ede"}).json()["data"]["token"]
    with client.websocket_connect(f"/api/v1/realtime/rooms/{room['id']}?token={ticket}") as ws:
        assert ws.receive_json()["type"] == "room.joined"
        assert ws.receive_json()["type"] == "participant.joined"
        ws.send_json({"type": "turn.text", "payload": {"text": "Adŭ", "language": "ede"}})
        types = [ws.receive_json()["type"] for _ in range(3)]
        assert types == ["transcript.final", "translation.final", "turn.completed"]


def test_room_websocket_rejects_bad_ticket(client):
    room = client.post("/api/v1/conversations/rooms", json={"mode": "two_devices"}).json()["data"]
    from starlette.websockets import WebSocketDisconnect
    import pytest
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/v1/realtime/rooms/{room['id']}?token=sai") as ws:
            ws.receive_json()
