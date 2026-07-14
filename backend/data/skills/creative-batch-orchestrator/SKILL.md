---
name: creative-batch-orchestrator
description: Batch orchestration — up to 10 items per batch, mixed skills/MCP, parallel submit and track
metadata:
  layer: L1-capability
  requires: [creative-job-runner, creative-platform, creative-seedance2-prompt, creative-gpt-image2-prompt, creative-direct, creative-script2film, creative-script2film-keyframes]
  tags: [batch, orchestrator, multi-skill, video, async]
---

# Creative Batch Orchestrator

Group **multiple independent generation jobs** into one batch. **Mixed skills allowed** (script2film, keyframes, direct video, batch image variants, etc.) — parallel submit, unified tracking and delivery.

> **Requires**: load **creative-job-runner** (multi-job UI tracking) and **creative-platform** (upload + preflight) first.  
> **Prompt gate**: For every item that hits image/video MCP, load **creative-gpt-image2-prompt** or **creative-seedance2-prompt** and craft `prompt` **before** submit — never raw user text.
> **Typical size**: **10 items/batch** (hard cap 10; split larger requests).  
> **Visibility**: all batch items are **async jobs** (including direct image/video) — appear in `creative_list_jobs` / Dashboard; **do not** use sync MCP inside a batch (`creative_generate_*` / `creative_image_to_video`, etc.).

## When to use

- A/B same product across render modes (reference vs keyframes vs direct)
- Multiple products / scripts in one run
- Mixed batch: 3× script2film + 5× direct_video + 2× batch_variants images
- Ops daily drops: submit batch, track in background — no need to wait per item

## When not to use

- Single task → use the matching L1/L2 skill directly, no batch wrapper
- Same prompt, N image variants only → **trend-viral-short** + `creative_submit_batch_variants` (one job)
- User wants instant result, no job list → **creative-direct** sync MCP (not in batch)

---

## Batch manifest format

Confirm with user or organize as **items array** (1–10):

```yaml
batch_label: "Summer sale batch-A"          # optional, for reporting
items:
  - label: "SKU-A reference render"
    skill: creative-script2film
    input:
      script: "..."
      target_duration_sec: 30
      aspect_ratio: "9:16"
      reference_image_urls: ["https://..."]
      brief: { product: "...", audience: "..." }
      delivery: { mode: "both" }

  - label: "SKU-B keyframes"
    skill: creative-script2film-keyframes
    input:
      script: "..."
      target_duration_sec: 30
      shot_duration_sec: 5

  - label: "Trend hook — direct"
    skill: creative-direct-video
    mode: image_to_video                    # text_to_video | image_to_video | first_frame | first_last_frame
    input:
      prompt: "..."
      duration_sec: 5
      aspect_ratio: "9:16"
      reference_image_urls: ["https://..."]

  - label: "Hero image — direct"
    skill: creative-direct-image
    input:
      prompt: "..."
      aspect_ratio: "9:16"
      reference_urls: ["https://..."]

  - label: "Hook image variants x5"
    skill: trend-viral-short
    input:
      prompt: "..."
      count: 5
      aspect_ratio: "9:16"
      preset: trend_viral_v1

  - label: "Store URL — full video"
    skill: product-url-to-video
    workflow: script2film                   # script2film | keyframes | direct
    input:
      product_url: "https://..."
      # Agent scrapes per product-url-to-video skill first, then fills script / reference_image_urls
```

Each item **must** have a unique `label` (for delivery table). Generate a **`client_request_id` (UUID)** per item before submit — idempotent, avoids duplicate charges.

---

## Skill → MCP mapping (strict on submit)

| `skill` field | Skill doc | MCP tool | workflow_type |
|---------------|-----------|----------|---------------|
| `creative-script2film` | creative-script2film | `creative_submit_script2film` | `script2film` |
| `creative-script2film-keyframes` | creative-script2film-keyframes | `creative_submit_script2film_keyframes` | `script2film` |
| `creative-direct-video` | creative-direct | `creative_submit_workflow` | `direct_video` |
| `creative-direct-image` | creative-direct | `creative_submit_workflow` | `direct_image` |
| `trend-viral-short` | trend-viral-short | `creative_submit_batch_variants` | `batch_variants` |
| `product-url-to-video` | product-url-to-video | after scrape → any L1 MCP above | per `workflow` |

**All batch items are async jobs** with `job_id`; track via `creative_get_job` / `creative_list_jobs` / `creative_cancel_job`.

### Direct video `mode` → `creative_submit_workflow` input

Unified call:

```json
{
  "workflow_type": "direct_video",
  "input": { "...see table..." },
  "delivery": { "mode": "both" },
  "client_request_id": "<uuid>"
}
```

| mode | Required `input` fields |
|------|-------------------------|
| `text_to_video` (no refs) | `prompt`, `duration_sec`, `aspect_ratio` |
| `image_to_video` (reference) | above + `reference_image_urls` or `reference_image_url` |
| `first_frame` | above + `video_mode: "first_frame"`, `first_frame_url` |
| `first_last_frame` | above + `video_mode: "first_last_frame"`, `first_frame_url`, `last_frame_url` |

Example (reference image to video):

```json
{
  "workflow_type": "direct_video",
  "input": {
    "prompt": "Product hero, slow rotation, UGC ad style",
    "duration_sec": 5,
    "aspect_ratio": "9:16",
    "reference_image_urls": ["https://example.com/product.jpg"]
  },
  "delivery": { "mode": "both" },
  "client_request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Direct image → `creative_submit_workflow`

```json
{
  "workflow_type": "direct_image",
  "input": {
    "prompt": "...",
    "aspect_ratio": "9:16",
    "reference_urls": ["https://..."]
  },
  "delivery": { "mode": "both" },
  "client_request_id": "<uuid>"
}
```

### L2 vertical (product-url-to-video)

When batch item is `product-url-to-video`:

1. **First** complete URL scrape + user confirm per **product-url-to-video** (may scrape in bulk, confirm whole batch once)
2. Map item's `workflow` to L1 MCP (default `script2film`)
3. When `workflow: direct` → `creative-direct-video` + `creative_submit_workflow` (`direct_video`); hero image in `reference_image_urls`
4. Write scraped `product_name`, `description`, hero URLs into `script` / `brief` / `reference_image_urls` before submit

---

## Standard flow (required)

### 1. Validate batch

- `items.length` **1–10**; if >10 → split batches and tell user
- Each `label` non-empty; `skill` in mapping table
- Missing script / prompt / URL → ask user; **do not** submit partial items
- Confirm no sync MCP (`creative_generate_*`, etc.)

### 2. Estimate credits

1. `creative_estimate` for batch overview (optional)
2. **Per item** `creative_estimate` (`workflow_type` aligned with input):

| skill | estimate workflow_type | params example |
|-------|------------------------|----------------|
| creative-script2film / keyframes | `script2film` | `{ target_duration_sec: 30 }` |
| trend-viral-short | `batch_variants` | `{ count: 5 }` |
| creative-direct-video | `direct_video` | `{ duration_sec: 5 }` |
| creative-direct-image | `direct_image` | `{}` |

3. **Summary table** for user confirmation (label, skill, est. credits, est. time):

```
| # | label | skill | est. credits | notes |
|---|-------|-------|--------------|-------|
| 1 | SKU-A | script2film | 120 | ~15min |
| 2 | Trend direct | direct_video | 8 | ~3min job |
| … | … | … | … | … |
| Total | | | 528 | ~20–40min parallel |
```

Submit only after user confirms.

### 3. Parallel submit

- **All items async**: fire all `creative_submit_*` / `creative_submit_workflow` in parallel (unique `client_request_id` each)
- Maintain in-memory **batch_tracker** (complements `creative_list_jobs`):

```json
{
  "batch_label": "Summer sale batch-A",
  "items": [
    {
      "index": 1,
      "label": "SKU-A",
      "skill": "creative-script2film",
      "workflow_type": "script2film",
      "client_request_id": "uuid-1",
      "job_id": "uuid-job-1",
      "status": "running"
    },
    {
      "index": 2,
      "label": "Trend direct",
      "skill": "creative-direct-video",
      "workflow_type": "direct_video",
      "client_request_id": "uuid-2",
      "job_id": "uuid-job-2",
      "status": "queued"
    }
  ]
}
```

After submit, send summary: `Submitted N async jobs` + each `job_id`; tell user they can ask for progress in this thread.

### 4. Tracking (creative-job-runner extension)

1. **No** sleep / `creative_get_job` loops; send `tracking.user_message` per submit
2. Tell user they can ask for whole-batch or single-job progress anytime
3. When user asks, **once** `creative_list_jobs` or `creative_get_job` for specific `job_id`
4. When all terminal → deliver batch result table (§5)

**Do not wait in chat**; keep all `job_id`s — user can query anytime.

### 5. Delivery

When all terminal, output **batch result table**:

```
| # | label | skill | job_id | status | artifact |
|---|-------|-------|--------|--------|----------|
| 1 | SKU-A | script2film | uuid-1 | ✅ | https://... |
| 2 | Trend direct | direct_video | uuid-2 | ✅ | https://... |
| 3 | Store B | script2film | uuid-3 | ❌ | error: ... |
```

- Success: `artifacts[0].urls.download` + local save hint
- Failure: `error` + whether to retry single item (new `client_request_id`)
- Stats: M succeeded / N total, total credits consumed

---

## Cancel & retry

| Action | Behavior |
|--------|----------|
| User: "cancel whole batch" | `creative_cancel_job` for each `queued`/`running` in batch_tracker |
| User: "cancel item 3" | cancel that `job_id` only |
| Single item retry | **new UUID** as `client_request_id` — never reuse failed id |
| Retry all failed | re-submit failed items only; keep successes |

---

## Concurrency notes

| Type | Guidance |
|------|----------|
| script2film / keyframes | Parallel submit OK (server parallelizes shots); 10 full jobs at once → credit spike |
| direct_video / direct_image | Parallel with other jobs; ~2–5 min per job |
| batch_variants | One job, internal batch — uses 1 batch slot |
| Mixed batch | All 10 may submit at once; track in one thread |

---

## Example: 10-item mixed batch

User: "Three product URLs as reference renders, plus two keyframe scripts, five trend direct videos."

1. Split 10 items (3× product-url-to-video + 2× keyframes + 5× direct-video)
2. Scrape 3 URLs → 3 scripts + references
3. Estimate summary → user confirm
4. **Parallel submit 10 async jobs** (5× `direct_video` via `creative_submit_workflow`)
5. Tell user to query progress in chat; on follow-up or all terminal → 10-row result table with job_ids

---

## Notes

- Batch is an **Agent-side orchestration concept** — no unified parent job on server; use `batch_tracker` + `creative_list_jobs`
- **Direct jobs still appear in job list**: batch must use `creative_submit_workflow`, not sync `creative_generate_video`
- Single chat, no dashboard → still OK to use **creative-direct** sync MCP outside batch
- Same `client_request_id` is idempotent — retries need new UUID
- L2 presets/constraints (e.g. trend_viral_v1) follow original skills; this skill only schedules
- For video, confirm user wants **full deliverable**, not image variants only
