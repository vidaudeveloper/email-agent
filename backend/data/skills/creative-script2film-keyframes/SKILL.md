---
name: creative-script2film-keyframes
description: Script-to-video (first/last frame) — per-shot keyframes drive Seedance transition animation
metadata:
  layer: L1-capability
  requires: [creative-job-runner, creative-platform, creative-narrative-router, creative-seedance2-prompt, creative-script2film]
  tags: [storyboard, async, script2film, keyframes, first-frame, one-click]
---

# Creative Script2Film — First/last-frame video

Shares the same script2film workflow as **creative-script2film** (reference-image-to-video), but per-shot video uses **first-frame / first-last-frame** mode instead of reference mode.

> **Prompt gate**: Same as **creative-script2film** — load **creative-seedance2-prompt** to enrich Final Video Spec shot visuals and motion-between-frames language before submit.

## When to use

| Scenario | Recommended skill |
|----------|-------------------|
| Product/person must match reference images closely; multi-reference constraints | **creative-script2film** (reference) |
| Smooth inter-shot transitions; controllable motion | **This skill** (first_last_frame) |
| Single shot expands action from a static keyframe; no end frame needed | This skill + `video_mode: first_frame` |
| Single short clip (not multi-shot deliverable) | **creative-direct** + `creative_first_frame_to_video` |

## Flow (shared script2film workflow with reference version)

Same server pipeline as **creative-script2film** — **only `video_mode` differs** (this skill defaults to `first_last_frame`).

1. `creative_estimate` with `workflow_type=script2film`
2. **`creative_submit_script2film_keyframes`** (default `video_mode=first_last_frame`):

```json
{
  "script": "<user script>",
  "target_duration_sec": 30,
  "aspect_ratio": "9:16",
  "reference_image_urls": ["<product hero image>"],
  "brief": { "product": "..." },
  "client_request_id": "<uuid>"
}
```

3. **creative-job-runner** — send `tracking.user_message` immediately after submit; **do not** sleep/poll; **artifacts[0]** is final video (with BGM unless `skip_bgm: true`)

### Server execution order (same as reference version)

1. **Extract key elements** — character / scene / prop / style / brand; bind user reference images
2. **Plan shots** — shot count, per-shot `duration_sec` (sum = target duration), `key_element_ids`
3. **Generate element reference images** — Identity Board (global visual anchors)
4. **Parallel keyframe gen** — per-shot keyframes; prompt weaves element descriptions + image refs
5. **Parallel video gen** — Seedance **first_last_frame** (see below)
6. FFmpeg concat + BGM

## First/last-frame principle (only difference from reference version)

| Stage | Reference version | First/last-frame (this skill) |
|-------|-------------------|-------------------------------|
| Key elements + element refs | ✅ Same | ✅ Same |
| Per-shot keyframes | Element anchors + woven prompt | ✅ Same |
| Per-shot video | Seedance **reference** (element imgs + keyframe) | Seedance **first_last_frame** (first/last keyframes only) |
| Motion prompt | Woven element descriptions | ✅ Same (keeps subject consistent) |

Per-shot video:

- **First frame** = this shot's keyframe (already constrained by element anchors)
- **Last frame** = next shot's keyframe (last shot: last frame = this shot's keyframe)

> Element reference images are **not** passed into Seedance video gen (first/last-frame mode uses keyframe images only). Consistency relies on **steps 3–4** locked keyframe appearance; inter-shot transitions are smoother.

## Key elements & user reference images

Same as **creative-script2film**: user refs bind semantically during **extract key elements**, then Identity Boards are generated; per-shot keyframe gen passes element refs via `key_element_ids`.

| Stage | First/last-frame behavior |
|-------|---------------------------|
| Extract / plan / element refs | Same as reference version |
| Per-shot keyframes | Element anchors + woven prompt |
| Per-shot video | Uses this/next shot **keyframes only** — no reference element images |

## Duration planning

Same as reference version: `target_duration_sec` assigns per-shot durations at planning time; **sum must equal target** (±3s).

## video_mode parameter

| Value | Meaning |
|-------|---------|
| `first_last_frame` | **Default** — first + last frame; smoother shot transitions |
| `first_frame` | First frame only; good for in-shot action expansion |

You may also use `creative_submit_script2film` with explicit `video_mode`.

## Sync single segment (not full deliverable)

When you already have first/last frame images and only need one clip:

```
creative_first_frame_to_video:
  prompt: "..."
  first_frame_url: "<first frame URL>"
  last_frame_url: "<last frame URL>"   # optional; omit for first_frame mode
  duration_sec: 5
  aspect_ratio: "9:16"
```

## Dependencies

- Server ffmpeg (or `FFMPEG_BIN`)
- `RUNWARE_API_KEY` (BGM, optional)

## Shot failure & retry

Same as **creative-script2film**: if a shot fails due to Seedance **copyright/IP** or **real-face privacy** blocks, guide the user to **revise that shot's prompt / swap reference images**, then re-submit with a **new `client_request_id`**. See the reference skill's "Shot failure & retry" section.
