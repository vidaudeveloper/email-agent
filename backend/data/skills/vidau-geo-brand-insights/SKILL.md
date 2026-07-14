---
name: vidau-geo-brand-insights
description: AI visibility, citations, SOV, sentiment, and content opportunities for brands tracked in VidAU GEO.
version: 1.3.2
metadata:
  hermes:
    tags: [geo, vidau, monitoring, brand, overview]
    category: marketing
---

# VidAU Brand Monitoring Insights

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

- User asks about **their brand's** performance: visibility, citation rate, SOV, sentiment, or "overview" style metrics.
- Brand must exist in **`list_brands`** (tracked in GEO console).

## Procedure

1. **`list_brands`** → `brand_id` (auto-pick silently when exactly one brand).
2. **`brand_overview(brand_id, days=7)`** — primary call. Report these KPIs in plain language:
   - **Visibility** (`kpis.visibility.value`, rank, badge)
   - **Citation rate** (`kpis.citation.value`, rank)
   - **Share of voice** (`kpis.shareOfVoice.value`, rank)
   - **Sentiment** (`kpis.sentiment.label`, `kpis.sentiment.score`)
3. If user wants drill-down → **`citations`**, **`leaderboard`**, **`opportunities`**, **`list_responses`** as needed.
4. If `hasProbeData` is false, explain probe may still be running (`probeRun`) or prompts need setup in GEO console.

## Do NOT Use

- Arbitrary URL audits — use `vidau-geo-quick-audit` or `vidau-geo-full-audit`.
- **`run_quick_audit`** here — no HTML site audit; this is probe/monitoring KPIs.

## Pitfalls

- Brand not in `list_brands` → user must add brand in GEO console first.
- Empty/zero KPIs with `probeRun.status=running` → tell user to check back when probes finish.
- MCP not connected → show Step 0 YAML (see Step 0).

## Verification

- Response includes `kpis.visibility`, `kpis.citation`, `kpis.shareOfVoice`, `kpis.sentiment`.
- Numbers come from the tool, not invented.
