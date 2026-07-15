# AGENTS.md — vidaudeveloper/email-agent

## Project

- **Root**: this repository (clone path = `$EMAIL_AGENT_ROOT`)
- **Runtime**: Hermes Agent via `HERMES_HOME=$EMAIL_AGENT_ROOT/.hermes`
- **LLM**: Vidau OPEN (`https://open.vidau.ai/v1`)
- **ESP**: Resend via `scripts/connectors/resend.py` (dry-run default)

## Start

```bash
python3 scripts/sync-send-skills.py   # optional upstream refresh
bash hermes/install.sh
# edit .hermes/.env → VIDAU_API_KEY + RESEND_API_KEY
bash hermes/run.sh chat
```

`hermes/run.sh` exports `EMAIL_AGENT_ROOT` and `HERMES_HOME`. Skills must call connectors as:

```bash
python3 "$EMAIL_AGENT_ROOT/scripts/connectors/resend.py" …
```

## Skills

See `_manifest.yaml` (25 + router). Install: `node scripts/install-skills.mjs --force`.

## Send workflow

1. `consent-registry` → recipient opted-in (`memory/consent/`)
2. `email-quality-auditor` → **SHIP**
3. `resend.py send|seed` → dry-run first; `--live` only after SHIP

```bash
set -a && source .hermes/.env && set +a
export EMAIL_AGENT_ROOT="$(pwd)"
python3 "$EMAIL_AGENT_ROOT/scripts/connectors/resend.py" send \
  --from "you@mail.vidau.ai" \
  --to "recipient@real-domain.com" \
  --subject "…" \
  --html path/to/build.html
# add --live only after SHIP
```

Do **not** use `himalaya`, `smtplib`, or invent `recipient@example.com`.

## Memory / Connectors

- Memory: `memory/consent/`, `memory/claims/`, `memory/audits/email/`
- Connectors: `scripts/connectors/{doh,resend,ledger,experiment}.py`
