---
name: vidau-geo-publish
description: Publish compose_article output to WordPress or Shopify via VidAU MCP publish_compose.
version: 1.2.2
metadata:
  hermes:
    tags: [geo, vidau, publish, wordpress]
    category: marketing
---

# VidAU Publish GEO Article

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

- User asks to **publish** or **post** an article after compose, or "发到 WordPress/Shopify".
- Requires a prior **`compose_article`** JSON response (full object).

## Procedure

1. **`list_connectors(brand_id)`** when multiple WordPress/Shopify sites exist.
2. **`publish_compose(compose=<full compose JSON>, connector_id=..., status=...)`**
   - Default **`status=draft`** unless user said "publish live" / "上线".
3. Success only when response has **`ok=true`** and **`postId`** / **`link`**.

## Pitfalls

- Saving to My Articles is **not** publishing — confirm with tool result.
- Do not claim success without `publish_compose` returning ok.
- MCP not connected → show Step 0 YAML (see Step 0).

## Verification

- User receives WordPress/Shopify post link from tool response.
