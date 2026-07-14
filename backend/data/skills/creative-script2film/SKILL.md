---
name: creative-script2film
description: Long-form multi-shot video (16s–120s) — one-liner → script → reference-image-to-video + FFmpeg concat + BGM
metadata:
  layer: L1-capability
  requires: [creative-job-runner, creative-platform, creative-narrative-router, creative-seedance2-prompt]
  tags: [storyboard, async, script2film, reference, bgm, one-click, long-video, script]
---

# Creative Script2Film — Reference-image-to-video

Turn a script (or a one-line brief) into a deliverable short video. **Default `video_mode=reference`**: each shot uses Seedance reference-image-to-video (user reference images + per-shot keyframe).

For **first/last-frame transitions** between shots, use **creative-script2film-keyframes** instead.

> **Prompt gate**: Load **creative-seedance2-prompt** when writing or refining Final Video Spec shot visuals (camera, motion, diegetic audio). Server generates per-shot video prompts from script — rich cinematic scene lines improve output quality. For any direct video MCP outside this workflow, Seedance prompt skill is **mandatory** before the MCP call.

## When to use (routing priority)

| User intent | Use |
|-------------|-----|
| **Long video >15s** (16s–120s): 30s/60s product ads, brand spots | **This skill** |
| One-liner / bullet selling points, no script yet | **This skill** (start with `creative_generate_script`) |
| Multi-shot + product/character reference constraints | **This skill** → `creative_submit_script2film` |
| Multi-shot + smooth inter-shot transitions (first/last frame) | **creative-script2film-keyframes** |
| **Single clip ≤15s**, one-shot direct output | **creative-direct** (do **not** use this skill) |

**Routing rule**: User says “30 second video”, “one-minute short”, “multi-shot”, “storyboard deliverable”, or `duration > 15s` → this skill. Single segment ≤15s → **creative-direct**.

## Agent flow (user-facing)

### 0. Collect inputs (can be minimal)

The user may only provide one sentence, e.g.:

> "Make a 30s vertical TikTok ad for these wireless earbuds — highlight ANC and 30h battery."

Script language matches the user's conversation (`brief.locale` or inferred from user text; EN user → EN script, ZH user → ZH script, etc.).

Ask only if missing (skip when already provided):
- Product/topic, core selling points
- Target duration (**>15s default 30s**), aspect ratio (default 9:16)
- Reference images (product / talent / scene) and what each is for
- **Voiceover** and **subtitles** (default off; see [Client voiceover & subtitles](references/client-voiceover-post.md))

### 1. Narrative routing (required before script generation)

Follow **creative-narrative-router**:

1. Parse intent → pick `narrative_structure` (`product_ad` / `story_narrative` / `problem_solution` / …)
2. **Read** the matching `references/*.md`; write beats and forbidden rules into `brief.narrative`
3. If confidence is low, show **2–3 options** with **different** structures; wait for user choice

### 2. Generate script (required when user has no full script)

Call **`creative_generate_script`** (no credits charged):

```json
{
  "creative_request": "30s vertical TikTok ad for wireless earbuds — highlight ANC and 30h battery",
  "brief": {
    "product": "Wireless earbuds",
    "audience": "US commuters",
    "platform": "TikTok",
    "locale": "en",
    "narrative_structure": "product_ad",
    "secondary_structure": "problem_solution",
    "narrative": {
      "beats": ["pain_hook", "hero_product", "feature_demo", "cta"],
      "constraints": ["No invented SKUs", "No fake stats"]
    }
  },
  "target_duration_sec": 30,
  "aspect_ratio": "9:16",
  "voiceover": true
}
```

Set `"voiceover": true` when the user wants narration; set `false` when they want BGM + ambient SFX only.

**Deliver to user**: Show the returned **`spec_markdown`** in full as Markdown (including `# Final Video Spec`, numbered scene overview, **`## Voiceover Copy`** when voiceover is on, etc.).

**Before confirmation**: Load **creative-seedance2-prompt** and enrich each scene line with clear camera, motion, and diegetic-audio wording (no BGM in shot descriptions when voiceover is on).

**Wait for user confirmation** (or re-run `creative_generate_script` after edits) before submitting the final render.

On confirm, check that **`narrative_structure`** matches intent; if not, adjust brief and regenerate.

> If the user pasted a complete Final Video Spec / storyboard script, skip this step and pass `script.full_text` or the user's text directly to `creative_submit_script2film.script`.

### 2b. Client voiceover plan (when voiceover enabled)

**Do not submit** until this step completes. Full playbook: **[references/client-voiceover-post.md](references/client-voiceover-post.md)**

1. Verify Hermes local **TTS** is configured (`~/.hermes/config.yaml` → `tts:`). If missing → tell user to configure a provider; do not submit with `voiceover_enabled`.
2. Parse `## Voiceover Copy` from confirmed `spec_markdown`.
3. For each line: local TTS → `ffprobe` duration → `duration_sec = clamp(ceil(sec + 0.4), 4, 12)`.
4. Build `voiceover_shot_plan` + save local `vo-NN.mp3` + manifest for post-process.

### 3. Estimate credits + submit

1. `creative_estimate` with `workflow_type=script2film`
2. `creative_submit_script2film`:
   ```json
   {
     "script": "<spec_markdown or user-confirmed script text>",
     "target_duration_sec": 30,
     "aspect_ratio": "9:16",
     "reference_image_urls": ["<user upload URL 1>", "<URL 2>"],
     "voiceover_enabled": true,
     "subtitles_enabled": true,
     "voiceover_shot_plan": [
       { "index": 1, "text": "Shot 1 VO line", "duration_sec": 6 },
       { "index": 2, "text": "Shot 2 VO line", "duration_sec": 8 }
     ],
     "brief": {
       "product": "...",
       "audience": "...",
       "reference_image_urls": ["<same URLs, may also live in brief>"]
     },
     "delivery": { "mode": "both" },
     "client_request_id": "<uuid>"
   }
   ```
   Omit `voiceover_*` / `subtitles_enabled` when user does not want narration.
3. Hand the returned `job_id` to **creative-job-runner** — send `tracking.user_message` **immediately** and **end the turn**; **do not** sleep or poll `creative_get_job`
4. When the user asks for progress in this thread, query then; on completion **artifacts[0]** is the server master (**BGM mixed in**). If `voiceover_enabled`, run **client post-process** (VO mux + optional subtitles) — see [client-voiceover-post.md](references/client-voiceover-post.md).

### 4. Client post-process (voiceover / subtitles only)

After job `completed` and user still wants delivery in-thread:

1. Download `artifacts[0].urls.download` to local workspace.
2. Mux saved TTS files using `progress.shots[].duration_sec` offsets (`adelay` + `amix`).
3. If `subtitles_enabled`, generate SRT from the same lines + burn with ffmpeg `subtitles=`.
4. Deliver final local MP4 to user.

**Before post-process**: run ffmpeg preflight in [client-voiceover-post.md](references/client-voiceover-post.md) §1b (macOS → `ffmpeg-full`). **On any user status ping** (`怎么样了`, etc.) reply current step immediately — see same doc §5 progress rules; never silent-hang on brew/ffmpeg.

Server **does not** run TTS or subtitle ffmpeg — Hermes terminal only.

## Server pipeline (after submit)

Aligned with vidau-agent storyboard, executed in order:

1. **Parse script** — normalize to structured **Final Video Spec** Markdown (title / duration / aspect / scene overview, etc.)
2. **Extract key elements** — detect `character` / `scene` / `prop|brand` / `style`; bind user reference images by semantics (product → prop, person → character, environment → scene)
3. **Plan shots** — each shot gets `key_element_ids` and `duration_sec`; if `voiceover_shot_plan` is submitted, **client TTS durations win** (no server re-normalization). Progress includes `voiceover_text` per shot when enabled.
4. **Generate element reference images** — Identity Board per element; filenames like `element-01-character-*.jpg`, `element-02-prop-*.jpg`, …
5. **Parallel keyframe gen** — per-shot keyframes **must** use bound elements' Identity Boards as reference; `shot-01-keyframe.jpg`
6. **Parallel video gen** — reference mode uses element refs + keyframe; **`generate_audio=false` when `voiceover_enabled`** (silent shots; VO added on client); otherwise `generate_audio=true` with prompt rules (**diegetic ambient SFX / foley OK; strictly NO BGM / soundtrack / vocals**); `shot-01-video.mp4`
7. **Concat pre-BGM timeline** (strict **shot index order**) → **BGM** → **mux final** (**amix: keep shot SFX when present + overlay BGM**)

Job progress includes `script_spec_preview`, `key_elements`, `shots[]` (`duration_sec`, `voiceover_text`), `voiceover_enabled`, `subtitles_enabled`.

Tune concurrency via `SCRIPT2FILM_SHOT_CONCURRENCY` (e.g. `3`); default `all` runs all shots in parallel.

Progress steps include: parse script / extract key elements / plan shots / generate element refs / parallel keyframes / parallel video / concat timeline (no BGM) / generate BGM / mux final.

## BGM (automatic)

script2film generates BGM **after** pre-BGM timeline concat completes (same as vidau-agent — not a silent master; shot diegetic SFX may already be present), so:

- BGM length = **actual final duration** (ffprobe, not planning estimate)
- BGM prompt includes **full per-shot visual/motion descriptions** aligned with on-screen narrative

| Param | Meaning |
|-------|---------|
| `skip_bgm` | `true` to skip auto BGM |
| `bgm_hint` | Style hint, e.g. "upbeat electronic, product-ad friendly" |
| `bgm_url` | Use existing BGM URL; skip generation |

Manual steps (optional):

- `creative_generate_bgm` — generate BGM alone for preview
- `creative_mux_bgm_into_video` — mux BGM into a given video URL

Requires `RUNWARE_API_KEY`; if unset, BGM is skipped and the pre-BGM timeline (with diegetic SFX if present) is still delivered.

## Key elements & user reference images

| Stage | Behavior |
|-------|----------|
| **Generate script** | `creative_generate_script` → `spec_markdown` (Final Video Spec) |
| **Parse script** | Final Video Spec Markdown; progress includes `script_spec_preview` |
| **Extract key elements** | LLM detects character/scene/product/style; user refs bound by semantics |
| **Plan shots** | Every shot binds elements; progress shows `shots[].key_element_ids`, `duration_sec`, `voiceover_text` when enabled |
| **Element refs** | Identity Board; `element-01-character-*.jpg`, etc. (ordered character → prop → scene) |
| **Per-shot keyframes** | refs = bound elements' Identity Boards; `shot-NN-keyframe.jpg` |
| **Per-shot video** | reference mode; `generate_audio=false` if `voiceover_enabled`, else diegetic SFX (no BGM in prompt) |
| **Concat order** | Strict `shots[].index` ascending — unaffected by parallel completion order |
| **Pre-BGM timeline** | FFmpeg concat; silent per shot when voiceover enabled |
| **Final audio (server)** | BGM mixed on timeline; **VO + subtitles on Hermes client** after job completes |

Collect reference image URLs from (merged & deduped):

- Top-level `reference_image_urls`
- `brief.reference_image_urls`

**Agent duty**: Before submit, note each image's role in brief (product / talent / scene / style). Image-only input → use `creative_generate_script` to expand script from images + brief.

## Duration planning

| Param | Meaning |
|-------|---------|
| `target_duration_sec` | Target total length (**16–120s**; >15s uses this skill). Planner assigns per-shot durations; **sum must equal target** (±3s) unless `voiceover_shot_plan` overrides |
| `voiceover_shot_plan` | Client TTS-measured `[{ index, text, duration_sec }]` — **authoritative** per-shot durations (4–12s) |
| `voiceover_enabled` | Silent Seedance shots; TTS on Hermes client |
| `subtitles_enabled` | Client ffmpeg burn-in after VO mux |
| `shot_duration_sec` | **Optional** fallback average (default 5s) for shot-count estimate only; actual per-shot durations come from planner (4–12s) |
| `SCRIPT2FILM_MAX_SHOTS` | Env cap on shot count (default 4; for 30s set **6**) |

**30s example**: `target_duration_sec=30`, omit `shot_duration_sec`; planner sums near 30s (e.g. 4+6+5+7+4+4) — **not fixed 5s per shot**.

If planned total `< target`, job still completes but progress notes under-target duration.

## Dependencies

- Server needs **ffmpeg** and **ffprobe** (or `FFMPEG_BIN`) for concat + BGM only
- Client (Hermes) needs **TTS** + **ffmpeg** for voiceover mux and subtitles
- Script expansion needs `LLM_BASE_URL` + `LLM_API_KEY` (heuristic template fallback if unset)

## When input is thin

Ask user for: product, selling points, platform, aspect ratio, **target duration (>15s)**; if images exist, confirm image↔product mapping.

A one-liner alone is OK: run `creative_generate_script`, show script, get confirmation.

## Notes

- Same `client_request_id` is idempotent — avoids duplicate charges
- Do not block the chat on long jobs; after submit, tell user they can ask for progress anytime in this thread
- Max **8** reference images (keyframe gen); max **9** refs for video gen (including shot keyframe)

## Shot failure & retry (content safety / copyright)

Seedance may block at **per-shot video gen**. Unlike privacy/face blocks, common cases:

| Type | Typical error | Meaning |
|------|---------------|---------|
| **Copyright / IP** | `output video may be related to copyright restrictions` | Output-side review — suspected protected IP, brand look, etc. |
| **Privacy / real face** | `PrivacyInformation` / `InputImageSensitiveContentDetected` | Input reference contains identifiable real person; server may retry via `asset://` |

**Agent playbook** (when shot `progress` or `error` mentions the above):

1. Explain **that shot** was blocked; other shots may have succeeded (job may still have partial artifacts)
2. Ask user to **revise that shot's script** (more abstract/cinematic; avoid IP names/brands/celebrities) and/or **swap reference images** (original/AI art; no copyrighted characters)
3. Re-submit full script2film with a **new `client_request_id`** (or after user edits script)
4. Same prompt sometimes **passes on retry** (stochastic); if repeated failures, change copy/images

> First/last-frame mode: see **creative-script2film-keyframes** — same failure principles.

## Concat & rehost

- Before FFmpeg concat, server **retries rehosting** non-platform URLs (e.g. TOS) to VidAU CDN, then downloads for concat (avoids direct `volces.com` timeouts)
- BGM mux uses the same reliable download (with retries); output is verified to contain an audio track
- Tunables: `FETCH_CONNECT_TIMEOUT_MS` (default 30s), `REMOTE_FETCH_MAX_ATTEMPTS` (default 3), `PLATFORM_REHOST_MAX_ATTEMPTS` (default 4)
