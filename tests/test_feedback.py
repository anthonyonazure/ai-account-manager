from fastapi.testclient import TestClient


def test_feedback_endpoint_records_verdict(seeded_db):
    from aam.feedback import app

    c = TestClient(app)
    r = c.post("/v1/feedback", json={
        "briefing_id": "fake-id",
        "account_id": "acct-001",
        "am_email": "alice@cyberco.com",
        "verdict": "done",
        "note": "called CISO, all good",
    })
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}


def test_feedback_rejects_invalid_verdict(seeded_db):
    from aam.feedback import app

    c = TestClient(app)
    r = c.post("/v1/feedback", json={
        "briefing_id": "x", "account_id": "acct-001",
        "am_email": "a@b", "verdict": "lol",
    })
    assert r.status_code == 400
