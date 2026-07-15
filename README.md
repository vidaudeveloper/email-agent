# Email Agent · SEND 邮件营销（Hermes Skills）

Aaron SEND 16 + 跨学科依赖，面向 **Hermes Agent**。真发走 `scripts/connectors/send_mail.py`（默认 dry-run）：需已配置 **Messaging Email**；未配置时会提示用户去桌面配置。

仓库：https://github.com/vidaudeveloper/email-agent

## Quick start

```bash
git clone --depth 1 https://github.com/vidaudeveloper/email-agent.git
cd email-agent

# 可选：安装到 ~/.hermes/skills/vidau-email/
node scripts/install-skills.mjs --force

# 独立 Hermes 环境（推荐发信）
bash hermes/install.sh
# 编辑 .hermes/.env → VIDAU_API_KEY
# 个人邮箱：桌面 Messaging → Email 已配置即可（自动读 vidau/.env）
# 或设 RESEND_API_KEY 作为兜底

bash hermes/run.sh chat
```

完整步骤与发信规则见 **[SETUP.md](./SETUP.md)**。

## Skills

清单以 [`_manifest.yaml`](./_manifest.yaml) 为准（安装脚本只读该文件）。

| Phase | Skills |
|-------|--------|
| router | `email-router` |
| setup | `deliverability-qa`, `list-segment-builder`, `list-growth-designer`, `list-hygiene-monitor` |
| engage | `email-creative-builder`, `subject-line-lab`, `email-render-builder`, `dynamic-content-personalizer` |
| nurture | `email-sequence-designer`, `newsletter-monetization-planner`, `preference-frequency-manager`, `reactivation-specialist` |
| deliver | `email-quality-auditor`, `send-experiment-designer`, `inbox-placement-monitor`, `cold-outbound-sequencer` |
| protocol | `consent-registry`, `offer-claims-registry`, `memory-management` |
| cross | `audience-mapper`, `landing-optimizer`, `roi-calculator`, `performance-analyzer`, `report-generator` |

## Send (safe path)

```bash
export EMAIL_AGENT_ROOT="$(pwd)"
set -a && source .hermes/.env && set +a

python3 "$EMAIL_AGENT_ROOT/scripts/connectors/send_mail.py" status
python3 "$EMAIL_AGENT_ROOT/scripts/connectors/send_mail.py" send \
  --to "real@recipient.com" \
  --subject "…" \
  --html build.html
# add --live only after EQS SHIP + consent
```

Do **not** improvise raw SMTP / `smtplib` / placeholder `@example.com` recipients — only `send_mail.py` / `user_smtp.py` / `resend.py`.

## Docs

- [SETUP.md](./SETUP.md) — one-click install & send
- [docs/SETUP.md](./docs/SETUP.md) — Hermes 细节
- [docs/DELIVER-VERIFICATION.md](./docs/DELIVER-VERIFICATION.md)
- [docs/VIDAU-LLM-INTEGRATION.md](./docs/VIDAU-LLM-INTEGRATION.md)

## Verify

```bash
python3 scripts/connectors/send_mail.py status
bash scripts/verify-deliver-flow.sh --domain mail.vidau.ai
```
