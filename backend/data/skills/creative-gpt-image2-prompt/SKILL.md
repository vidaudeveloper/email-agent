---
name: creative-gpt-image2-prompt
description: GPT Image 2 / gpt-image-2 prompt engineering — mandatory before any image MCP call. Use when generating or editing images via creative_generate_image, batch_variants, direct_image workflows, keyframe briefs, or identity-board descriptions.
metadata:
  layer: L0-foundation
  requires: []
  tags: [foundation, prompt, gpt-image-2, image, openai]
---

# Creative GPT Image 2 Prompt

Production-grade **GPT Image 2 (`gpt-image-2`)** prompt engineering for VidAU Creative Agent.

> **Mandatory gate**: Load this skill **before** any MCP that generates images (`creative_generate_image`, `creative_submit_batch_variants`, `creative_submit_workflow` with `direct_image`, or any `prompt` for still/keyframe generation). **Never** pass raw user text directly as `prompt` — run this skill's workflow first.

Adapted from [wuyoscar/GPT-Image2-Skill](https://github.com/wuyoscar/GPT-Image2-Skill) (MIT) and [freestylefly/awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2) (MIT).

## When to load

| Trigger | Action |
|---------|--------|
| `creative_generate_image` | Craft prompt → MCP `prompt` |
| `creative_submit_batch_variants` | Craft base prompt + variant hooks |
| `direct_image` workflow | Craft prompt → `input.prompt` |
| Keyframe / product still brief | Output English or Chinese prompt per user locale |
| User says GPT Image / 生图 / 海报 / mockup | Draft or refine |

## Agent workflow (required)

1. **Classify artifact** — product hero / poster / UI mockup / infographic / photo / character sheet / edit
2. **Read references** when needed:
   - [craft.md](references/craft.md) — 6-block protocol + checklist
   - [templates.md](references/templates.md) — category starters
   - [categories.md](references/categories.md) — routing table
3. **Build prompt** with **6-block protocol** (below)
4. **Text pass** — all display copy in `"quotes"`; Chinese: specify 简体/繁体
5. **Deliver** copy-ready prompt → then call downstream MCP

## 6-block protocol

Order matters — layout before subject detail:

```
1. Canvas & layout   — aspect ratio, grid, zones, device frame
2. Subject & task    — what to depict, role of reference images
3. Composition       — foreground/background, hierarchy, camera
4. Style & materials — medium, palette, lighting (split controls)
5. Text & labels     — exact quoted strings, legibility constraints
6. Constraints       — avoid lines, edit invariants, no fake logos
```

### Block 1 examples

- `Vertical 9:16 product hero poster…`
- `Square 1:1 e-commerce white-background packshot…`
- `Landscape 16:9 UI mockup, 1290×2796 phone frame…`

### Block 5 (typography)

Weak: `poster with brand name and price`

Strong: `Exact readable text: "无线耳机 Pro" / "主动降噪" / "¥399"`

## Reference images (VidAU MCP)

When `reference_urls` / `reference_image_urls` are set:

```
Image 1: product photo — preserve packaging shape and label colors.
Image 2: style reference — apply lighting and palette only.
Change only background to soft gradient; keep product identical.
```

## VidAU-specific rules

| Context | Rule |
|---------|------|
| Product ads | Clear hierarchy: product largest; no fake competitor logos |
| batch_variants | One strong base prompt + hook variations in `count` submissions |
| script2film keyframes | Photoreal or brand-locked style; match `brief.narrative` tone |
| Edit / inpaint | State transform + explicit preserve list |
| Safety | No real-person likeness unless user owns reference; tasteful fashion only |

## Output format

```markdown
### GPT Image 2 Prompt
<paste-ready prompt>

### Strategy
- Category: product_hero | poster | ui_mockup | …
- Aspect: 9:16 | 1:1 | 16:9
- References: [role summary]
- Text blocks: [quoted strings]
```

Then invoke MCP with `prompt` = paste-ready text.

## Quick checklist

- [ ] Aspect ratio / layout stated first
- [ ] Literal text in `"quotes"`
- [ ] Materials, lighting, palette separated
- [ ] 5–12 concrete scene nouns (not empty adjectives)
- [ ] Targeted `Avoid:` line (1–3 items)
- [ ] Reference roles indexed if multiple URLs

## References

- [craft.md](references/craft.md)
- [templates.md](references/templates.md)
- [categories.md](references/categories.md)
