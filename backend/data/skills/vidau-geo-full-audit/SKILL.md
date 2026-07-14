---
name: vidau-geo-full-audit
description: Run a full multi-agent GEO audit for any URL via VidAU MCP; returns HTML report and action plan.
version: 1.2.2
metadata:
  hermes:
    tags: [geo, vidau, audit]
    category: marketing
---

# VidAU Full GEO Audit

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

- User asks for a **full**, **deep**, or **complete** GEO audit with prioritized recommendations.
- Any public URL — not limited to tracked brands.

## Procedure

1. Warn the user this may take **15–30+ minutes**.
2. Call **`run_geo_audit(url)`** with the target URL.
3. Optional: `locale` = `"zh"` or `"en"` when user specifies language.
4. Share **`summary`** and **`downloadUrl`** when the tool completes.

## Do NOT Use

- Data tools (`citations`, `opportunities`, etc.) or browser DIY audits — same rule as quick audit.

## Pitfalls

- MCP not connected → show Step 0 YAML (see Step 0).

## Verification

- `downloadUrl` present in response.
- Action plan and scores come from tool output, not inference.
