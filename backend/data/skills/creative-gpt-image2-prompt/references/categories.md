# GPT Image 2 Category Router

Map user intent → template + craft emphasis.

| User intent | Category | Read | Emphasis |
|-------------|----------|------|----------|
| Product on white / Amazon hero | `product_hero` | templates.md § Product hero | Materials, lighting, no fake logos |
| Sale poster / campaign KV | `poster` | templates.md § Vertical ad | Quoted text hierarchy, 3-glance test |
| App / dashboard screenshot | `ui_mockup` | templates.md § UI | Device frame, real copy, spacing |
| TikTok hook still / A/B | `ugc_photo` | templates.md § UGC + batch hooks | Capture context, imperfection |
| Explainer / feature board | `infographic` | templates.md § Infographic | Fixed zones, exact labels |
| Character consistency | `character_sheet` | templates.md § Character board | Grid count, shared wardrobe |
| Reference edit | `edit` | craft.md § Edit invariants | Preserve list first |
| Research / diagram | `technical_figure` | craft.md § JSON config | Nodes, arrows, exact module names |
| Food / beverage splash | `product_render_json` | craft.md § JSON config | Suspended ingredients, motion |

## 3-glance test (posters & hero ads)

1. **First glance** — silhouette / theme instantly readable
2. **Second glance** — promise / product story clear
3. **Third glance** — texture, micro-labels, background reward

## VidAU MCP routing

| Skill | MCP | Prompt source |
|-------|-----|---------------|
| creative-direct | `creative_generate_image` | This skill → `prompt` |
| trend-viral-short | `creative_submit_batch_variants` | This skill → `prompt` (+ variant hooks) |
| product-url-to-video | hero still if needed | This skill before image MCP |
| creative-batch-orchestrator | `direct_image` | This skill per item |

## Language

| User locale | Prompt language |
|-------------|-----------------|
| ZH conversation | Simplified Chinese unless EN copy requested |
| EN conversation | English |
| Mixed marketing copy | Match on-screen text language exactly |
