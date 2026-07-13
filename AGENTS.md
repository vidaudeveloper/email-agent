# AGENTS.md — email_demo

## Project

- **Root**: `/Users/kean/Desktop/DemoFile/email_demo`
- **Runtime**: Hermes Agent via `HERMES_HOME=email_demo/.hermes`
- **LLM**: Vidau OPEN (`https://open.vidau.ai/v1`)
- **Framework**: Aaron SEND 16 + cross-discipline deps

## Start

```bash
python3 scripts/sync-send-skills.py
bash hermes/install.sh
bash hermes/run.sh chat
```

## Skills (25 + router = 26 SKILL.md)

- **Router**: `email-router`
- **SEND 16**: under `skills/setup|engage|nurture|deliver/`
- **Protocol**: `consent-registry`, `offer-claims-registry`, `memory-management`
- **Cross-discipline**: `audience-mapper`, `landing-optimizer`, `roi-calculator`, `performance-analyzer`, `report-generator` under `skills/cross-discipline/influencer/`

## Natural-language routing

Hermes NL does **not** hard-inject skills (only `/slash` does). This project compensates via:

- `hermes/run.sh chat` preloads `--skills email-router`
- hooks: inject **generate-only vs explicit-send** context; block SMTP + placeholder recipients + unverified `@vidau.ai` from-domain
- Prefer slash commands when possible
- **生成 ≠ 发送**: “生成广告推广” → draft only; “发送给 xubin@…” → consent → EQS → `resend.py`
- Do **not** use `himalaya`, `smtplib`, or invent `recipient@example.com`

## Send workflow (template → inbox)

SEND skills plan and audit; they do not improvise SMTP. Delivery path:

1. `consent-registry` — recipient must be opted-in (`memory/consent/`)
2. `email-quality-auditor` — need **SHIP** (not FIX/BLOCK)
3. `scripts/connectors/resend.py send|seed` — dry-run first; `--live` only after SHIP

```bash
set -a && source .hermes/.env && set +a
python3 scripts/connectors/resend.py send \
  --from "you@verified-domain.com" \
  --to "recipient@example.com" \
  --subject "…" \
  --html path/to/build.html
# add --live only after SHIP
```

Enable Resend MCP (optional): `bash hermes/enable-resend.sh` then `/reload-mcp` in chat.

## Memory

`memory/consent/`, `memory/claims/`, `memory/audits/email/`, `memory/archive/`, `memory/hot-cache.md`, `memory/open-loops.md`

## Connectors

`scripts/connectors/doh.py`, `resend.py`, `ledger.py`, `experiment.py`
