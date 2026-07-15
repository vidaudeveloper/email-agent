---
name: email-router
slug: email-demo-router
displayName: "Email Router · 邮件营销路由"
summary: "SEND 循环路由/邮件营销入口"
description: 'Routes email marketing requests through the SEND loop (setup/engage/nurture/deliver). Use when the user mentions email marketing, ESP campaigns, newsletter, cold outbound, deliverability, DMARC, list hygiene, pre-send go/no-go, EQS audit, writing promotional copy/templates (生成推广/写邮件), sending a template to an address, seed/test send, 发送模版, or 发给收件人. Delegates to phase skills; prefers VidAU Messaging Email SMTP via send_mail.py when configured, else Resend; never improvises raw SMTP; does not auto-send on generate-only requests.'
version: "1.4.0"
license: Apache-2.0
compatibility: "Hermes Agent (use repo .hermes via hermes/run.sh; exports EMAIL_AGENT_ROOT)"
when_to_use: "User asks about email campaigns, deliverability, list building, lifecycle flows, pre-send audit, writing promo/ad email copy (生成广告推广/营销模版), or wants to send/seed a template to a recipient — without naming a specific phase skill."
argument-hint: "[phase: setup|engage|nurture|deliver] [goal: promotional|retention|cold-outbound]"
metadata: {"author": "vidau-email-agent", "version": "1.4.0", "discipline": "email", "phase": "router", "hermes": {"tags": ["marketing", "email", "send", "router"], "category": "email"}}
---

# Email Router

Entry skill for the **SEND** email marketing loop in this repo (`vidaudeveloper/email-agent`). Infer the user's phase and delegate to the matching skill. Default to Tier 1 (paste exports) unless MCP is configured.

Equivalent to upstream `/aaron-marketing:email`.

## Project paths

- **Project root**: clone of this repo; start with `bash hermes/run.sh chat` (`HERMES_HOME=$EMAIL_AGENT_ROOT/.hermes`, `EMAIL_AGENT_ROOT` exported automatically)
- **References**: `references/send-benchmark.md`, `references/auditor-runbook.md`
- **Connectors**: `python3 "$EMAIL_AGENT_ROOT/scripts/connectors/doh.py" auth <domain>` (keyless S1)
- **Send executor**: `python3 "$EMAIL_AGENT_ROOT/scripts/connectors/send_mail.py" send|seed …` (auto: VidAU Messaging Email SMTP if configured, else Resend)
- **Memory**: `memory/consent/`, `memory/claims/`, `memory/audits/email/`

## Routing table (SEND 16)

| User intent | Phase | Target skill |
|-------------|-------|--------------|
| DMARC / SPF / DKIM / spam / inbox pre-flight | setup | `deliverability-qa` |
| List segment / suppression / CRM export | setup | `list-segment-builder` |
| List growth / lead magnet / double opt-in | setup | `list-growth-designer` |
| Bounce / complaint / sunset hygiene trend | setup | `list-hygiene-monitor` |
| Write email / subject / preview / CTA / 生成推广 / 广告推广 / 营销模版（不发送） | engage | `email-creative-builder` only — **do not send** |
| Subject line A/B / spam trigger check | engage | `subject-line-lab` |
| HTML render / dark mode / plain-text QA | engage | `email-render-builder` |
| Dynamic blocks / merge tags | engage | `dynamic-content-personalizer` |
| Welcome / cart / lifecycle automation | nurture | `email-sequence-designer` |
| Paid newsletter / sponsorship economics | nurture | `newsletter-monetization-planner` |
| Preference center / frequency caps | nurture | `preference-frequency-manager` |
| Win-back / reactivation / sunset save | nurture | `reactivation-specialist` |
| Pre-send EQS / go-no-go | deliver | `email-quality-auditor` |
| Explicit send / 发送给 / seed test / 发给邮箱（用户给出真实收件人） | deliver | `email-quality-auditor` → then `scripts/connectors/send_mail.py send\|seed` (SMTP first if Messaging Email configured; dry-run; `--live` only after **SHIP**) |
| A/B / send-time / hold-out experiment | deliver | `send-experiment-designer` |
| Inbox placement monitoring | deliver | `inbox-placement-monitor` |
| B2B cold outbound sequence | deliver | `cold-outbound-sequencer` |
| Log opt-in / unsubscribe / consent | protocol | `consent-registry` |
| Register offer / claim / D1 evidence | protocol | `offer-claims-registry` |
| Archive memory / HOT-WARM-COLD lifecycle | protocol | `memory-management` |
| Persona / lifecycle audience map | cross | `audience-mapper` |
| Post-click / signup page QA | cross | `landing-optimizer` |
| ROI / revenue-per-send math | cross | `roi-calculator` |
| Post-send performance read | cross | `performance-analyzer` |
| Stakeholder report packaging | cross | `report-generator` |

If phase is ambiguous, ask once for **goal** (promotional / retention / cold-outbound), then start at the earliest incomplete phase.

## Quick Start

```
/email-router promotional — 夏季清仓 8 折，写主题行、预览、正文和 CTA
```

```
/email-router deliver — audit tomorrow's broadcast before send
```

```
/email-creative-builder B2C promo: 20% off summer sale, subject + preview + body + CTA
```

## Skill Contract

- **Reads**: user goal, domain, ESP name, pasted exports
- **Writes**: handoff summary only (routes; does not score EQS)
- **Done when**: correct downstream skill is invoked with goal + missing-input list
- **Primary next skill**: per routing table above

## Data tiers

1. **Tier 1** (default): pasted ESP/DMARC/GA4 exports + `doh.py auth`
2. **Tier 2a**: VidAU Messaging Email SMTP via `send_mail.py` / `user_smtp.py` when `EMAIL_ADDRESS` + `EMAIL_PASSWORD` + `EMAIL_SMTP_HOST` are set (desktop Messaging → Email, or `.hermes/.env`)
3. **Tier 2b**: Resend MCP / `resend.py` when `RESEND_API_KEY` is set (fallback if no personal SMTP)
4. **Tier 3**: multi-MCP orchestration

## Generate vs send (hard rules)

| User says | Do | Do not |
|-----------|----|--------|
| 生成 / 写 / 做一封 / 广告推广 / 营销模版（无收件人） | `email-creative-builder` → show subject + preview + body + CTA; save draft | Call send_mail / Resend / MCP send / invent recipients |
| 发送给 / 发给 `user@domain` | Confirm consent → EQS → `send_mail.py` with **that** address | Use `recipient@example.com`, `@example.com`, or prior-session promo copy |

- **Never** improvise raw `smtplib` / SMTP / `himalaya` / `execute_code` mail hacks — only `send_mail.py`, `user_smtp.py`, or `resend.py`.
- **Never** send to placeholder addresses (`*@example.com`, `recipient@…` fakes).
- Prefer personal SMTP when Messaging Email is configured; Resend from-domain must be **verified** (`mail.vidau.ai`, not bare `vidau.ai`).
- Delivery executor: `python3 "$EMAIL_AGENT_ROOT/scripts/connectors/send_mail.py" send|seed` (`hermes/run.sh` exports `EMAIL_AGENT_ROOT`). Check `send_mail.py status` first.
- Mutating calls are dry-run by default; add `--live` only after `email-quality-auditor` returns **SHIP**.
- Confirm consent in `memory/consent/` before `--live`.
- Do **not** reuse unrelated session examples (e.g. 夏季清仓 8 折) when the user asked for a different product (e.g. Mete 智能投放).

## Recommended workflows

**Generate promo copy only**

`email-creative-builder` → present draft → stop (ask if user wants send)

**Promotional broadcast**

`deliverability-qa` → `email-creative-builder` → `email-quality-auditor`

**Send template to one address (seed / test)**

`consent-registry` (if missing) → `email-quality-auditor` → `send_mail.py send|seed` (dry-run → `--live` after SHIP)

**Lifecycle program**

`list-segment-builder` → `email-sequence-designer` → `email-quality-auditor`

**Experiment**

`send-experiment-designer` → `email-quality-auditor`

## Next Best Skill

After routing, follow the target skill's **Next Best Skill** section. Max chain depth: 3.
