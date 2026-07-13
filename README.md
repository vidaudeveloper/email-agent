# Email Demo — SEND 邮件营销（Hermes 独立运行）

Full [Aaron SEND 16](https://github.com/aaron-he-zhu/aaron-marketing-skills/blob/main/docs/README.zh.md#邮件营销--send16) plus cross-discipline dependencies for **Hermes Agent**, isolated in `email_demo/.hermes/`.

## Quick start

```bash
cd /Users/kean/Desktop/DemoFile/email_demo

# 1. Sync skills from upstream
python3 scripts/sync-send-skills.py

# 2. Init isolated Hermes env
bash hermes/install.sh

# 3. Edit API key in email_demo/.hermes/.env  (VIDAU_API_KEY=...)

# 4. Run
bash hermes/run.sh chat
```

## Skills

### SEND 16 + router

| Phase | Skill | Slash |
|-------|-------|-------|
| router | `email-router` | `/email-router` |
| setup | `deliverability-qa`, `list-segment-builder`, `list-growth-designer`, `list-hygiene-monitor` | same name |
| engage | `email-creative-builder`, `subject-line-lab`, `email-render-builder`, `dynamic-content-personalizer` | same name |
| nurture | `email-sequence-designer`, `newsletter-monetization-planner`, `preference-frequency-manager`, `reactivation-specialist` | same name |
| deliver | `email-quality-auditor`, `send-experiment-designer`, `inbox-placement-monitor`, `cold-outbound-sequencer` | same name |

### Protocol

| Skill | Slash | Purpose |
|-------|-------|---------|
| `consent-registry` | `/consent-registry` | Consent SSOT (S2/N1) |
| `offer-claims-registry` | `/offer-claims-registry` | Claims SSOT (D1) |
| `memory-management` | `/memory-management` | HOT/WARM/COLD memory |

### Cross-discipline (influencer)

| Skill | Slash | Purpose |
|-------|-------|---------|
| `audience-mapper` | `/audience-mapper` | Persona / lifecycle map |
| `landing-optimizer` | `/landing-optimizer` | Post-click page QA |
| `roi-calculator` | `/roi-calculator` | ROI / revenue-per-send |
| `performance-analyzer` | `/performance-analyzer` | Post-send measurement |
| `report-generator` | `/report-generator` | Report packaging |

## Sync from upstream

```bash
python3 scripts/sync-send-skills.py
```

## Config

| What | Where |
|------|-------|
| API Key | `email_demo/.hermes/.env` |
| Hermes config | `email_demo/.hermes/config.yaml` |

## Docs

- [Setup](docs/SETUP.md)
- [Deliver verification](docs/DELIVER-VERIFICATION.md)
- [Vidau LLM](docs/VIDAU-LLM-INTEGRATION.md)
- [Plan](docs/HERMES-EMAIL-MARKETING-PLAN.md)

## Verify Deliver phase

```bash
bash scripts/verify-deliver-flow.sh --domain yourdomain.com
```
