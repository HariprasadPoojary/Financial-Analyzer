"""Security checks for transaction values rendered and submitted by review routes."""

import pickle

import pandas as pd
from fastapi.testclient import TestClient

import app.fast_api as fast_api


def _session_df(description: str = '<img src=x onerror="alert(1)"> &') -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-01")],
            "description": [description],
            "amount": [-25.0],
            "type": ["debit"],
            "category": ["Other"],
        }
    )


def _setup_session(tmp_path, monkeypatch) -> str:
    session_id = "0123456789"
    sessions = tmp_path / "sessions"
    reports = tmp_path / "reports"
    sessions.mkdir()
    reports.mkdir()
    monkeypatch.setattr(fast_api, "SESSION_DIR", sessions)
    monkeypatch.setattr(fast_api, "REPORT_DIR", reports)
    with (sessions / f"{session_id}.pkl").open("wb") as session_file:
        pickle.dump({"df": _session_df(), "warnings": []}, session_file)
    return session_id


def test_review_escapes_description_and_categories(tmp_path, monkeypatch):
    session_id = _setup_session(tmp_path, monkeypatch)
    hostile_category = 'Food"><script>alert(1)</script>&'
    monkeypatch.setattr(fast_api, "get_category_names", lambda: [hostile_category])

    response = TestClient(fast_api.app).get(f"/review/{session_id}")

    assert response.status_code == 200
    rendered = response.text
    assert '<img src=x onerror="alert(1)">' not in rendered
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp;" in rendered
    assert '<option value="Food&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;&amp;">' in rendered
    assert "const sessionId = \"0123456789\";" in rendered


def test_review_rejects_unknown_categories_and_indexes_without_saving(tmp_path, monkeypatch):
    session_id = _setup_session(tmp_path, monkeypatch)
    monkeypatch.setattr(fast_api, "get_category_names", lambda: ["Dining"])
    with TestClient(fast_api.app) as client:
        bad_category = client.post(
            f"/review/{session_id}", json={"overrides": {"0": "<script>"}}
        )
        bad_index = client.post(
            f"/review/{session_id}", json={"overrides": {"999": "Dining"}}
        )

    assert bad_category.status_code == 400
    assert bad_index.status_code == 400
    saved = fast_api._load_session(session_id)
    assert saved["df"].at[0, "category"] == "Other"
    assert not (tmp_path / "reports" / f"report_{session_id}.html").exists()


def test_review_accepts_valid_override_and_regenerates_report(tmp_path, monkeypatch):
    session_id = _setup_session(tmp_path, monkeypatch)
    monkeypatch.setattr(fast_api, "get_category_names", lambda: ["Dining"])

    with TestClient(fast_api.app) as client:
        response = client.post(
            f"/review/{session_id}", json={"overrides": {"0": "Dining"}}
        )

    assert response.status_code == 200
    assert response.json() == {"report_url": f"/report/{session_id}"}
    saved = fast_api._load_session(session_id)
    assert saved["df"].at[0, "category"] == "Dining"
    assert (tmp_path / "reports" / f"report_{session_id}.html").is_file()
