---
name: vidau-geo-automation
description: Run or schedule VidAU content automation — topic, compose, quality gate, WordPress/Shopify publish.
version: 1.2.3
metadata:
  hermes:
    tags: [geo, vidau, automation]
    category: marketing
---

# VidAU Content Automation

## Step 0 — MCP check (only prompt when NOT connected)

**Check first:** Is **vidau-geo MCP** already connected and working?

| Result | What to do |
|--------|------------|
| **YES** — VidAU MCP tools are available and calls succeed (e.g. `list_brands`, `run_quick_audit`, `compose_article`) | **Skip this entire Step 0.** Do **not** mention MCP setup. Go straight to **When to Use / Procedure** below and run the skill normally. |
| **NO** — no VidAU tools in your tool list, or calls fail with **401** | **Stop.** Your **entire reply** = **only** the user message below (pick 中文 or English). Do **not** answer the original request. Do **not** invent audits, metrics, or articles. See `references/mcp-user-not-connected.md`. |

### 中文（仅 MCP 未连接时发给用户）

您已经安装了 VidAU Skill，但还**没有连接 vidau-geo MCP**，所以我暂时无法帮您完成这个请求。

请在 MCP 配置中添加：

```yaml
mcp_servers:
  vidau-geo:
    url: https://geo.vidau.ai/mcp
    enabled: true
    connect_timeout: 60
    timeout: 300
```

保存后执行 `/reload-mcp`（或重启），再**说一次**您的需求。

### English (only when MCP is NOT connected)

You installed the VidAU Skill, but **vidau-geo MCP is not connected yet**, so I can't complete this request yet.

Add this to MCP config:

```yaml
mcp_servers:
  vidau-geo:
    url: https://geo.vidau.ai/mcp
    enabled: true
    connect_timeout: 60
    timeout: 300
```

Save, run `/reload-mcp` (or restart), then **ask again**.
## When to Use

- One-off pipeline: topic → write → quality gate → publish.
- Daily scheduled auto-writing.
- Cancel queued/running automation jobs.

## Procedure

### One-off run

1. **`list_brands`** → `brand_id`; **`list_connectors`** if needed.
2. **`run_content_automation(brand_id, topic=...)`** → `runId`.
3. **`wait_for_content_automation_run(run_id)`** until terminal status (`success`, `draft`, `failed`, `skipped`).

### Daily schedule

**`update_content_automation_settings(brand_id, enabled=True, schedule_hour=9, schedule_minute=0, schedule_timezone="Asia/Shanghai", publish_mode="draft", image_source="auto")`**

Disable: `enabled=False`. Cancel in-flight: **`cancel_content_automation_run(run_id)`**.

## Parameters (automation settings)

- `publish_mode`: `draft` (default) or `auto`
- `article_template_id`: `simple`, `vidau-blue`, `vidau-pink`
- `image_source`: `auto` (default — Pexels when configured), `pexels`, `none`, `both`
- `daily_article_count`, `quality_threshold`, `default_connector_id`

## Pitfalls

- MCP not connected → show Step 0 YAML (see Step 0).
- `image_source=auto` with no WordPress connector → article composes without hero images.

## Verification

- Terminal run shows `postLink` or draft saved; daily settings reflect in `get_content_automation_settings`.
