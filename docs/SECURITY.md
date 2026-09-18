# Security Policy & Hardening Controls

This document details the security controls implemented to protect the terminal, broker credentials, and trading environment.

---

## 1. Network Boundary & Localhost Binding

- **Default Interface:** FastAPI binds exclusively to `127.0.0.1` (localhost).
- **No Public Exposure:** The terminal is strictly intended for local workstation or private VPS operation. Under no circumstances should port `8000` or `3000` be forwarded to the public internet without an authenticated reverse proxy (e.g. Caddy/Nginx with TLS and IP whitelisting).
- **CORS Policy:** Strict origin whitelisting (`settings.frontend_origin`, defaulting to `http://localhost:3000`).

---

## 2. Authentication & Authorization

- **Bearer Token Auth:** Every state-modifying REST endpoint (`/api/trading/*`, `/api/risk/*`, `/api/mt5/*`) requires an `Authorization: Bearer <TOKEN>` header.
- **WebSocket Auth:** WebSocket connections require authentication via header or query parameter (`?token=<TOKEN>`).
- **Timing Safe Comparisons:** Token validation uses `secrets.compare_digest` to prevent timing attacks.

---

## 3. Secret Management & Sanitization

- **No Hardcoded Secrets:** All MT5 passwords, server names, and API keys are stored strictly in local `.env` files.
- **Sanitized Logging:** `structlog` and log endpoints filter out any fields named `password`, `api_token`, or `token`.
- **Frontend Masking:** API endpoints return masked account summaries without exposing raw passwords or sensitive credentials to the browser.

---

## 4. Single-Instance Protection

- To prevent concurrent bot executions on a single MT5 account, the backend maintains a process lock (`mt5terminal.lock`).
- If an existing process is detected, the second instance terminates immediately.
