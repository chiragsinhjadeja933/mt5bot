"""Unit tests — FastAPI HTTP Control API & Auth (Section 25, 34)"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app, settings
from app.trading.state_machine import BotState


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = settings.api_token.get_secret_value()
    return {"Authorization": f"Bearer {token}"}


class TestApiAuthentication:
    def test_unauthorized_without_token(self, client):
        resp = client.get("/api/mt5/status")
        assert resp.status_code == 401
        assert "Invalid or missing API token" in resp.json()["detail"]

    def test_unauthorized_with_invalid_token(self, client):
        resp = client.get("/api/mt5/status", headers={"Authorization": "Bearer bad-token-xyz"})
        assert resp.status_code == 401

    def test_health_check_public(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestTradingStateControls:
    def test_get_trading_state(self, client, auth_headers):
        resp = client.get("/api/mt5/status", headers={**auth_headers})
        assert resp.status_code == 200
        data = resp.json()
        assert "state" in data
        assert "connected" in data

    def test_start_request_nonce(self, client, auth_headers):
        resp = client.post("/api/trading/start-request", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "nonce" in data
        assert "START DEMO" in data["instructions"]

    def test_start_requires_exact_typed_token(self, client, auth_headers):
        # Passing wrong token
        resp = client.post(
            "/api/trading/start",
            headers=auth_headers,
            json={"confirmation_token": "start"},
        )
        assert resp.status_code == 400
        assert "START DEMO" in resp.json()["detail"]

    def test_emergency_stop_works(self, client, auth_headers):
        resp = client.post("/api/trading/emergency-stop", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "EMERGENCY_STOP"
        assert data["state"]["bot_state"] == BotState.EMERGENCY_STOP

    def test_cannot_start_from_emergency_stop_without_reset(self, client, auth_headers):
        resp = client.post(
            "/api/trading/start",
            headers=auth_headers,
            json={"confirmation_token": "START DEMO"},
        )
        assert resp.status_code == 400
        assert "reset first" in resp.json()["detail"]

    def test_reset_emergency_stop(self, client, auth_headers):
        # Reset requires typing 'RESET'
        resp = client.post(
            "/api/trading/reset-emergency",
            headers=auth_headers,
            json={"confirmation_token": "RESET"},
        )
        assert resp.status_code == 200
        assert resp.json()["state"]["bot_state"] == BotState.READY
