# Cloud Chat Timeline History Implementation Plan

> **For agentic workers:** Use executing-plans or implement task-by-task. Steps use checkbox syntax.

**Goal:** Persist MCP steps + media for replay; Manus-style Markdown chat; full-cycle Creative placeholders; media detail page with download.

**Architecture:** SQLite `session_steps` / `session_media` + `GET /timeline`; Flutter loads timeline on start, renders steps/Markdown/media; detail route for download.

**Tech Stack:** FastAPI, SQLite, Flutter, flutter_markdown, gal (or path_provider), url_launcher

**Worktree:** `.worktrees/cloud-agent-p0`

**Spec:** `docs/superpowers/specs/2026-07-14-cloud-chat-timeline-history-design.md`

---

### Task 1: Backend tables + timeline API
### Task 2: Persist on tool.mcp / media.* in agent_loop + media_tracker
### Task 3: Flutter models + fetch timeline + controller hydrate
### Task 4: MCP steps UI + Markdown assistant
### Task 5: Media placeholder hardening + MediaDetailPage + download
### Task 6: Tests + analyze

---
