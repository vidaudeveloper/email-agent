---
name: creative-platform
description: VidAU Creative reference upload and pre-generation setup
metadata:
  layer: L0-foundation
  requires: [creative-seedance2-prompt, creative-gpt-image2-prompt]
  tags: [foundation, platform, upload]
---

# Creative Platform Gateway

## Billing

- Generation (sync + async) requires **VIP** and **deducts coins**.
- Non-VIP → share the purchase URL from the MCP error.
- Insufficient coins → ask user to top up.
- **Free**: `creative_estimate`, `creative_get_upload_instructions`, `creative_upload_reference`, `creative_generate_script`, `creative_list_models`, `creative_mux_bgm_into_video`.

## Prompt gate (required before any generation MCP)

**All image and video MCP calls must go through prompt skills first** — never pass raw user text as `prompt`.

| MCP / output | Load skill first |
|--------------|------------------|
| `creative_generate_image`, `direct_image`, `batch_variants` | **creative-gpt-image2-prompt** |
| `creative_generate_video`, `creative_image_to_video`, `creative_first_frame_to_video`, `direct_video` | **creative-seedance2-prompt** |
| script2film Final Video Spec (per-shot visuals) | **creative-seedance2-prompt** before submit |

Workflow: load prompt skill → craft paste-ready prompt → call downstream skill / MCP with that `prompt`.

## Flow

1. Call `creative_estimate` for time/credit estimate (optional)
2. Call `creative_generate_*` / `creative_submit_*`

## Local reference upload (recommended)

Image/video MCP tools accept **HTTPS URLs** only (`reference_urls`) — not raw file bytes.

**When the user has a local terminal:**

1. `creative_get_upload_instructions` — get S3 presigned PUT URL + curl example
2. On the **user's machine**, PUT the file via `terminal` / curl (`Content-Type` per response)
3. After upload, use returned `upload.file_url`
4. Pass into `creative_generate_image.reference_urls` or `creative_image_to_video.reference_image_urls`

**Do not** use `local_path` on remote MCP (ENOENT). **Do not** default to sending large base64 via MCP; use `creative_upload_reference` only when no local terminal is available.

## Notes

- Single reference image ~25 MB max; jpg/png/webp/gif/bmp supported
