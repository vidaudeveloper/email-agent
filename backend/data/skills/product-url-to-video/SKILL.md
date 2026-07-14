---
name: product-url-to-video
description: Product URL → scrape product info → product ad video/image (DTC and major marketplaces)
metadata:
  layer: L2-vertical
  requires: [creative-job-runner, creative-platform, creative-seedance2-prompt, creative-gpt-image2-prompt, creative-script2film, creative-script2film-keyframes]
  tags: [ecommerce, product, url, scrape, script2film, bgm, one-click]
---

# Product URL → Video

Enable when the user pastes a **product page URL**. Scrape product info with Agent web tools, then call **vidau-creative** MCP to generate ad assets.

> **Prompt gate**: Before any image MCP → **creative-gpt-image2-prompt**. Before any video MCP or script visual enrichment → **creative-seedance2-prompt**.

> **Applies to**: Shopify DTC, Amazon, TikTok Shop, Temu, any reachable product page.  
> **Not for**: social profile pages, cloud drives, YouTube/Bilibili video links — treat as normal chat.

## Video skill selection (L2 required reading)

Before submitting final render, pick **L1 video skill** from user intent:

| User intent / scenario | Load skill | MCP entry |
|------------------------|------------|-----------|
| Product short; hero must match main image (**default**) | **creative-script2film** | `creative_submit_script2film` |
| Emphasis on shot transitions, camera motion, cinematic feel | **creative-script2film-keyframes** | `creative_submit_script2film_keyframes` |
| Single 5–15s demo clip only, no multi-shot | **creative-direct** | `creative_image_to_video` or `creative_first_frame_to_video` |
| A/B test multiple hook **images** | **trend-viral-short** | `creative_submit_batch_variants` |

**Decision shorthand**:
- Has product hero, must "look like this SKU" → **reference** (creative-script2film)
- Wants "smooth transitions / story camera" → **keyframes** (creative-script2film-keyframes)
- If unspecified, e-commerce default → **creative-script2film**

## When to trigger

Message contains `https://` and looks like a product page (`product`, `/p/`, `/dp/`, `shop`, `store`, etc.) or user says "this link's product".

## Flow overview

```
1. Scrape product info (Agent local tools)
2. Show summary to user and confirm
3. Estimate credits + submit generation (MCP)
4. creative-job-runner — send tracking.user_message immediately; no sleep/polling
```

---

## 1. Scrape product info

Try in order; **stop at first success**:

### A. `web_extract` (preferred)

```
web_extract(urls=["<product URL>"], format="markdown")
```

Extract from response: `product_name`, `brand`, `price`, `description`, hero image URLs (`og:image` / largest product image).

### B. `execute_code` (structured parse)

When `web_extract` is thin or fails. Prefer **JSON-LD** (`@type: Product`), **Open Graph**, `application/ld+json`:

```python
import urllib.request, json, re

url = "<product URL>"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

# JSON-LD Product
for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
    try:
        data = json.loads(block)
        # recurse for @type == Product
        ...
    except: pass

# Open Graph fallback
og = lambda prop: re.search(rf'property="og:{prop}" content="([^"]+)"', html)
name = og("title") or og("product:title")
image = og("image")
desc = og("description")
print(json.dumps({"name": name, "image": image, "description": desc}, ensure_ascii=False))
```

**Required fields**:

| Field | Meaning |
|-------|---------|
| `product_name` | Product title |
| `product_description` | Selling points / description (truncate ~500 chars OK) |
| `product_images` | Hero image URLs (max 8, prefer high-res) |
| `price` | Optional, for display |
| `brand` | Optional |

### C. `terminal` + curl (light fallback)

Only if A/B fail:

```
curl -sL -A "Mozilla/5.0" "<URL>" | head -c 200000
```

Then `execute_code` or regex for og/meta.

### D. `browser` (JS-rendered pages)

When login required or A–C return shell HTML — open URL in browser, repeat B.

### Scrape failure

Tell user clearly: "Could not parse product info from this URL" — ask for manual product images + name/selling points. Do not force MCP submit.

---

## 2. Confirm with user

After successful scrape, **show summary before generation**:

- Product name, brand, price (if any)
- Hero image preview (Markdown image or URL)
- Selling points summary (2–3 sentences)

Ask user:

1. **Output type**: short video deliverable (default) / batch hook variants / single ad image
2. **Aspect ratio**: default `9:16` (TikTok/Reels)
3. **Duration**: default 30s (script2film)
4. **Reference images**: default scraped hero (up to 3)

If user only pasted URL, default → **script2film 30s vertical product short**.

---

## 3. Generate script

From scrape results, write **30–60s vertical product script** (storyboard feel, optional VO tone):

1. First 3s hook (pain/scene)
2. Product reveal + 2–3 core selling points
3. CTA (limited offer / shop now — only if user provided)

Script language matches user conversation (`brief.locale` or user text; EN → EN, ZH → ZH, etc.).

Before script generation, run **creative-narrative-router** (usually `product_ad` + optional `problem_solution`).

---

## 4. MCP submit

### Preflight (required)

1. `creative_estimate` for overview
2. `creative_estimate` per selected workflow

### Default: script2film deliverable (reference)

```
creative_submit_script2film:
  script: "<script from step 3>"
  reference_image_urls: ["<hero URL>", ...]
  brief:
    product: "<product_name>"
    product_description: "<selling points>"
    product_url: "<original URL>"
    reference_image_urls: ["<hero URL>", ...]
    audience: "<inferred audience>"
    locale: "en"
    narrative_structure: "product_ad"
  aspect_ratio: "9:16"
  target_duration_sec: 30
  client_request_id: "<uuid>"
```

**Reference usage**: keyframe + video both use **reference** mode.

### Alt: keyframes script2film

User wants cinematic transitions, less strict product lock:

```
creative_submit_script2film_keyframes:
  script: "<script from step 3>"
  reference_image_urls: ["<hero URL>"]   # constrains product at keyframe stage only
  video_mode: "first_last_frame"         # optional; tool default
  aspect_ratio: "9:16"
  target_duration_sec: 30
  client_request_id: "<uuid>"
```

### Alt: batch hook variants

User wants A/B hook tests → **trend-viral-short** or:

```
creative_submit_batch_variants:
  prompt: "<product name + selling points + trend hook; English often works well>"
  count: 5
  aspect_ratio: "9:16"
```

### Alt: single image / single video

Use **creative-direct**:

- Image: `creative_generate_image` + `reference_urls: [<hero>]`
- Reference video: `creative_image_to_video` + `reference_image_urls: [<hero>]`
- First/last frame: `creative_first_frame_to_video` + `first_frame_url` / `last_frame_url`

---

## 5. Job tracking

Load **creative-job-runner** immediately after submit:

- Send `tracking.user_message`; user can ask for progress in this thread
- **No** sleep / `creative_get_job` loops; single query when user asks
- On user follow-up, one `creative_get_job` → deliver URL + local hint (**script2film includes BGM by default**)

---

## Notes

- **Image URLs**: scraped external URLs may go directly into `reference_urls`; if MCP download fails, ask user to upload manually and retry.
- **Compliance**: respect target site robots.txt; don't brute-force repeated scrapes on failure.
- **Major platforms**: Amazon/TikTok Shop etc. — prefer `web_extract` or `browser` for complex pages.
- **Multiple URLs**: max **3** product links per turn; scrape and confirm separately.
- **Do not** call vidau-creative MCP during scrape; scrape = Agent local tools only, generation = MCP.
