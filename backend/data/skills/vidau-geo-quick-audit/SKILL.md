---
name: vidau-geo-quick-audit
description: Run a 60-second GEO snapshot for any URL via VidAU MCP; returns HTML report download link.
version: 1.2.2
metadata:
  hermes:
    tags: [geo, vidau, audit, snapshot]
    category: marketing
---

# VidAU GEO Quick Audit (60s Snapshot)

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

- User asks for a GEO snapshot, quick audit, "60 second" assessment, or 快照 for **any website URL**.
- The URL may **not** be a tracked brand in VidAU — still use this skill.

## Procedure

1. Call **`run_quick_audit(url)`** with the full URL or domain (e.g. `https://example.com`).
2. Optional: pass `locale` as `"zh"` or `"en"` if the user specified report language.
3. Wait for completion (several minutes). Do not guess scores while waiting.
4. Reply with the **`summary`** and **`downloadUrl`** from the tool response (styled HTML report, same as GEO web Agent).
5. If `downloadUrl` is missing, report `reportError` — do not fabricate a report.

## Do NOT Use

- `list_brands`, `citations`, `opportunities`, `keyword_volume`, `leaderboard`, or browser navigation to **build** an audit.
- Those tools read **tracked brand probe data** and cannot replace the quick-audit pipeline.

## Pitfalls

- Empty citation/SEO data for unknown domains is normal — the audit skill fetches and analyzes the site directly.
- Never infer Schema markup or dimension scores from empty MCP data fields.
- MCP not connected → show Step 0 YAML (see Step 0).

## Verification

- Tool response includes `downloadUrl` pointing to `/api/reports/download/.../*.html`.
- Summary mentions GEO score or dimension analysis from the tool, not invented numbers.
