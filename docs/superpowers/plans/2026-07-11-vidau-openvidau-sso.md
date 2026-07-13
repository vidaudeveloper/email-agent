# OpenVidAU SSO Cloud Login Implementation Plan

> **For agentic workers:** Implement task-by-task. Checkboxes track progress.

**Goal:** Replace Cloud demo login with browser SSO via Cloud Agent proxy; bootstrap plan-scoped OpenVidAU key for LLM + Expert MCP.

**Architecture:** Cloud Agent proxies open.vidau.ai ticket/poll/bootstrap; stores key in `data/openvidau.env`; issues session tokens. Flutter opens login URL and polls until signed_in.

**Tech Stack:** FastAPI, httpx, Flutter url_launcher, existing AuthStore

**Spec:** `docs/superpowers/specs/2026-07-11-vidau-openvidau-sso-design.md`

---

## Files

| File | Role |
|------|------|
| `cloud_agent/app/openvidau_sso.py` | Upstream SSO HTTP client |
| `cloud_agent/app/account_store.py` | Persist auth, env, session tokens |
| `cloud_agent/app/auth.py` | Accept session tokens (+ optional dev token) |
| `cloud_agent/app/llm_config.py` | Prefer `data/openvidau.env` |
| `cloud_agent/app/main.py` | Auth routes |
| `cloud_agent/app/config.py` | openvidau base URL, allow_dev_token |
| Flutter auth + cloud clients | SSO login UX + dynamic token |

## Tasks

- [x] Backend: account_store + openvidau_sso + auth routes + llm_config
- [x] Backend tests with mocked SSO
- [x] Flutter: url_launcher, SSO login, token wiring
- [x] README + verify pytest / analyze
