"""
心情打卡 API 测试——test_mood.py
覆盖：打卡创建、今日查询、历史查询、统计
"""
import pytest
from fastapi.testclient import TestClient

from main import app
from api.routes_auth import get_current_user


@pytest.fixture(autouse=True)
def override_auth():
    """跳过 JWT 认证，返回固定 user_id"""
    app.dependency_overrides[get_current_user] = lambda: "test-user-mood"
    yield
    app.dependency_overrides.clear()


class TestMoodCheckin:

    def test_checkin_success(self):
        with TestClient(app) as client:
            resp = client.post("/api/mood/checkin", json={"score": 7, "note": "good day"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["score"] == 7
            assert data["note"] == "good day"
            assert "id" in data
            assert "created_at" in data

    def test_checkin_score_min(self):
        with TestClient(app) as client:
            resp = client.post("/api/mood/checkin", json={"score": 1})
            assert resp.status_code == 200
            assert resp.json()["score"] == 1

    def test_checkin_score_max(self):
        with TestClient(app) as client:
            resp = client.post("/api/mood/checkin", json={"score": 10})
            assert resp.status_code == 200
            assert resp.json()["score"] == 10

    def test_checkin_score_too_low(self):
        with TestClient(app) as client:
            resp = client.post("/api/mood/checkin", json={"score": 0})
            assert resp.status_code == 422

    def test_checkin_score_too_high(self):
        with TestClient(app) as client:
            resp = client.post("/api/mood/checkin", json={"score": 11})
            assert resp.status_code == 422

    def test_checkin_no_score(self):
        with TestClient(app) as client:
            resp = client.post("/api/mood/checkin", json={})
            assert resp.status_code == 422

    def test_checkin_without_note(self):
        with TestClient(app) as client:
            resp = client.post("/api/mood/checkin", json={"score": 5})
            assert resp.status_code == 200
            assert resp.json()["note"] == ""


class TestMoodToday:

    def test_today_no_checkin(self):
        """使用独立用户确保无打卡记录"""
        app.dependency_overrides[get_current_user] = lambda: "user-no-checkin"
        with TestClient(app) as client:
            resp = client.get("/api/mood/today")
            assert resp.status_code == 200
            assert resp.json()["checkin"] is None

    def test_today_after_checkin(self):
        with TestClient(app) as client:
            client.post("/api/mood/checkin", json={"score": 8, "note": "happy"})
            resp = client.get("/api/mood/today")
            assert resp.status_code == 200
            checkin = resp.json()["checkin"]
            assert checkin is not None
            assert checkin["score"] == 8


class TestMoodHistory:

    def test_history_returns_records(self):
        with TestClient(app) as client:
            client.post("/api/mood/checkin", json={"score": 3})
            client.post("/api/mood/checkin", json={"score": 9})
            resp = client.get("/api/mood/history?days=30")
            assert resp.status_code == 200
            records = resp.json()["records"]
            assert len(records) >= 2

    def test_history_invalid_days(self):
        with TestClient(app) as client:
            resp = client.get("/api/mood/history?days=0")
            assert resp.status_code == 422


class TestMoodStats:

    def test_stats_empty_user(self):
        """使用独立用户确保无记录"""
        app.dependency_overrides[get_current_user] = lambda: "user-stats-empty"
        with TestClient(app) as client:
            resp = client.get("/api/mood/stats?days=30")
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] == 0

    def test_stats_with_data(self):
        app.dependency_overrides[get_current_user] = lambda: "user-stats-data"
        with TestClient(app) as client:
            for s in [3, 5, 7, 9]:
                client.post("/api/mood/checkin", json={"score": s})
            resp = client.get("/api/mood/stats?days=30")
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] == 4
            assert data["avg_score"] == 6.0
            assert data["max_score"] == 9
            assert data["min_score"] == 3
            assert data["trend"] in ("up", "down", "stable")
