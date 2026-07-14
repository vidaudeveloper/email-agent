---
name: creative-direct
description: Direct image/video generation (sync, single clip ≤15s; audio on by default)
metadata:
  layer: L1-capability
  requires: [creative-platform, creative-job-runner, creative-seedance2-prompt, creative-gpt-image2-prompt]
  tags: [image, video, sync, one-click]
---

# Creative Direct — Sync generation

For a single ad image or **single clip ≤15s** product short — no storyboard.

> **Prompt gate (required)**: Before any MCP call below, load **creative-gpt-image2-prompt** (images) or **creative-seedance2-prompt** (video), output a paste-ready prompt, then pass it as MCP `prompt`. Never use raw user text.

> **Duration routing**: User wants **>15s** / 30s / 60s / multi-shot / storyboard → use **creative-script2film** (start with `creative_generate_script`); **do not** force long-form through this skill.

> **Job tracking**: Load **creative-job-runner** before any generation call; give real-time status even for sync tasks.

## Video skill selection

| Need | Skill | MCP |
|------|-------|-----|
| Reference images, product consistency | **creative-script2film** | `creative_submit_script2film` |
| First/last-frame transitions, controlled camera | **creative-script2film-keyframes** | `creative_submit_script2film_keyframes` |
| Single short clip | **This skill** | `creative_generate_video` / `creative_image_to_video` / `creative_first_frame_to_video` |

## Image generation

1. Tell user: "Generating image, ~1–2 minutes…"
2. **Load creative-gpt-image2-prompt** — craft production-grade `prompt` from user intent + references
3. **When user has local/attached reference images** (`@image`, etc.):
   - **Prefer** `creative_get_upload_instructions` → local curl/terminal PUT to S3 → use `upload.file_url`
   - Fallback (no local terminal): `creative_upload_reference` (`content_base64`)
4. `creative_generate_image`:
   - `prompt`: **output from creative-gpt-image2-prompt** (not raw user text)
   - `aspect_ratio`: `9:16` | `1:1` | `16:9`
   - `reference_urls`: optional — `file_url` from upload step (or existing HTTPS URLs)
5. Read `tracking.user_message`; return `artifacts[0].urls.download` + local save hint

## Video generation

1. Tell user: "Generating video, ~2–5 minutes…"
2. **Load creative-seedance2-prompt** — craft production-grade `prompt` (reference roles, camera, audio rules)
3. With user reference images → **`creative_image_to_video`** (Seedance **reference-to-video**, `reference_image` role — **not** first/last frame):
   - `prompt`: **output from creative-seedance2-prompt**
   - `reference_image_urls`: product / talent / scene / style, etc. (max 9)
   - or single `reference_image_url`
4. Without reference images → `creative_generate_video` (text-to-video) with **Seedance prompt from step 2**
5. Deliver artifacts + `tracking.user_message`

## Optional: BGM

For a single short clip with background music:

1. `creative_generate_bgm` (may pass `script` / `brief` / `bgm_hint` for auto prompt)
2. `creative_mux_bgm_into_video` — mux `video_url` + `bgm_url`

> script2film one-click deliverables **auto-mix BGM** in workflow; direct video requires the two steps above.

## Defaults

- Vertical short: `aspect_ratio=9:16`, `duration_sec=5`
- **Audio on**: `generate_audio=true` (default); in-shot SFX from Seedance
