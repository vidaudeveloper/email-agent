---
name: trend-viral-short
description: Trend short-form — batch hook image variants for TikTok/Reels product ads
metadata:
  layer: L2-vertical
  requires: [creative-job-runner, creative-platform, creative-gpt-image2-prompt, creative-seedance2-prompt, creative-script2film, creative-script2film-keyframes, creative-direct]
  tags: [trend, batch, ecommerce, image]
---

# Trend Viral Short

Ride trends; quickly produce multiple vertical **image** variants for A/B testing.

> **Prompt gate**: Load **creative-gpt-image2-prompt** before `creative_submit_batch_variants` — craft base prompt + variant hooks. For video paths, load **creative-seedance2-prompt** before video MCP.

## When to use

- MCN daily drops, trend chasing
- Same product, multiple opening-hook tests (**image** variants)

## When user wants "video deliverable"

This skill defaults to **batch images**. For video, switch L1 skill by intent:

| Need | Skill | MCP |
|------|-------|-----|
| Multi-shot product short + reference | creative-script2film | `creative_submit_script2film` |
| Multi-shot + keyframe transitions | creative-script2film-keyframes | `creative_submit_script2film_keyframes` |
| Single trend short clip | creative-direct | `creative_generate_video` / `creative_first_frame_to_video` |

Confirm intent before submit — do not default to batch_variants for video requests.

## Flow (image variants)

1. Organize brief: `product`, `trend_tags` (trend keywords), `hook_idea` (optional)
2. **Load creative-gpt-image2-prompt** — craft production-grade base `prompt` (+ variant hook clauses if needed)
3. `creative_estimate` workflow_type=`batch_variants`, params=`{ count: 5 }`
4. `creative_submit_batch_variants`:
   - `prompt`: **output from creative-gpt-image2-prompt** (not raw user text)
   - `count`: default **5**
   - `aspect_ratio`: **9:16**
   - `preset`: **trend_viral_v1**
5. **creative-job-runner** — push `tracking.user_message` immediately; **no** sleep/polling
6. List artifacts by variant number; suggest launch priority

## Preset constraints (trend_viral_v1)

- Strong hook in first 3 seconds (visual)
- Product close-up ≤ 40% of frame
- No infringing trends, sensitive content

## Technique injection

When orchestrating, read preset file: `presets/trend_viral_v1.json`
