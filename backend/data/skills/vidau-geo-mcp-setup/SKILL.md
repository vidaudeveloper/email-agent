---
name: vidau-geo-mcp-setup
description: Detect missing VidAU GEO MCP and prompt the user to connect — only when MCP is not already working.
version: 1.0.3
metadata:
  hermes:
    tags: [geo, vidau, setup, mcp]
    category: marketing
---

# VidAU GEO — Connect MCP First

## When to Use

- **Only when MCP is missing:** User tries audit, brand metrics, write article, publish, or automation but VidAU MCP tools are not available or return 401.
- User only installed Skills (`hermes skills install …`) without connecting vidau-geo MCP.

## Do NOT Use

- **MCP already connected and working** — skip this skill entirely. Do not mention setup. Run the user's requested VidAU skill instead.

## Step 0 — MCP gate

**Check first:** Can you call VidAU tools from MCP server `vidau-geo` / `geo.vidau.ai`?  
Examples: `list_brands`, `brand_overview`, `run_quick_audit`, `compose_article`.

| Result | Action |
|--------|--------|
| **YES** — tools work | **Do nothing.** No MCP prompt. Proceed with the user's actual request using the right VidAU skill. |
| **NO** — no tools or 401 | Reply with **only** the user message below (match 中文/English). Do **not** guess or fabricate data. |

### User message — 中文

您已经安装了 VidAU Skill，但还**没有连接 vidau-geo MCP**，所以我暂时无法帮您查询数据、写稿或做审计。

**请把下面配置写入 MCP（VidAU Agent / Hermes），保存后 `/reload-mcp`：**

```yaml
mcp_servers:
  vidau-geo:
    url: https://geo.vidau.ai/mcp
    enabled: true
    connect_timeout: 60
    timeout: 300
```

完成后请**再说一次**您的需求。

### User message — English

You installed the VidAU Skill, but **vidau-geo MCP is not connected yet**, so I cannot fetch metrics, write articles, or run audits.

**Add this MCP config in VidAU Agent / Hermes, save, then `/reload-mcp`:**

```yaml
mcp_servers:
  vidau-geo:
    url: https://geo.vidau.ai/mcp
    enabled: true
    connect_timeout: 60
    timeout: 300
```

Then **ask again**.

## Verification

- MCP missing → user got the YAML block and reload steps, not a fabricated answer.
- MCP already working → this skill was not shown.
