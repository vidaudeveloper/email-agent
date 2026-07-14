---
name: vidau-geo-compose
description: Compose publish-ready GEO articles via VidAU MCP with smart defaults for language, tone, template, SEO keywords, and hero images.
version: 1.2.3
metadata:
  hermes:
    tags: [geo, vidau, content, compose]
    category: marketing
---

# VidAU GEO Article Compose

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

- User wants a **GEO article** for their brand/site (default path — prefer over `write_article`).
- User says "write an article", "写一篇", competitor comparison, thought leadership, etc.

## Procedure (smart defaults)

1. **`list_brands`** → `brand_id` (silent if one brand; ask by site name if multiple and unclear).
2. **Topic**
   - User gave topic → use it.
   - No topic → **`suggest_topic(brand_id)`** (content opportunity).
   - Still none → **`generate_topic(brand_id)`**.
3. **SEO keywords** (when topic is known)
   - Call **`suggest_seo_keywords(brand_id, topic)`** → pass returned `keywords` to compose.
   - User named keywords explicitly → use those instead.
   - Else → `seo_keywords=[]` (server auto-matches from brand library).
4. **`compose_article`** with defaults unless user specified otherwise:
   - `language=auto`, `tone=professional`, `template_id=simple`
   - `seo_keywords` from step 3
   - `image_source=auto` for Pexels hero images when a WordPress connector exists; `none` if user says no images
5. Tell user to preview/edit in **GEO console → Content Creation → My Articles** (`draftId` in response).
6. Publish only if user asked — use **`vidau-geo-publish`** skill / `publish_compose`.

## Parameters

For full parameter matrix load: `skill_view("vidau-geo-compose", "references/compose-params.md")`.

For SEO keyword recommendation prompt signals load: `skill_view("vidau-geo-compose", "references/seo-keyword-recommend.md")`.

Optional: **`list_article_templates`** when user asks which HTML templates exist.

## Pitfalls

| Error | Action |
|-------|--------|
| `missing_brand_words` | User must configure brand words in GEO keyword library |
| `missing_seo_keywords` | User must configure SEO keywords in GEO keyword library |
| `insufficient_credits` | User needs credits at geo.vidau.ai |
| `imagesSkippedReason=no_connector` | Pexels images need a WordPress connector; article still saved |
| MCP not connected / no API key / 401 | User must connect MCP with Step 0 YAML (see Step 0) |

Do **not** use `write_article` unless user explicitly wants markdown-only without meta/schema.

## Verification

- Response includes `draftId`, `content`, `score`, and quality gate info.
- Article saved to user's GEO account under the resolved brand.
