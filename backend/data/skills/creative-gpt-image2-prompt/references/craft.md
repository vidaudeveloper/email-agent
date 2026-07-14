# GPT Image 2 Prompt Craft

Condensed from wuyoscar/GPT-Image2-Skill `references/craft.md`.

## Core principles

### 1. Exact text in quotes

Every displayed string must appear in `"…"`. Do not paraphrase user-supplied copy.

### 2. Layout before subject

State canvas, aspect ratio, and grid/zones **before** describing surface detail.

### 3. JSON / config prompts (complex product shots)

For premium product or food renders with many interacting systems, use a structured block:

```text
/* PRODUCT_RENDER_CONFIG */
{
  "GLOBAL_SETTINGS": { "aspect_ratio": "2:3 vertical", "style": "hyper-realistic commercial" },
  "ENVIRONMENT": { "background": "warm gradient studio", "lighting": "softbox + rim" },
  "CORE_ASSETS": { "primary_subject": "hero earbuds case", "materials": ["matte plastic", "metal hinge"] },
  "OUTPUT": { "mood": "premium minimal", "avoid": ["fake logos", "plastic CGI look"] }
}
```

### 4. Split material / lighting / palette

Weak: `premium look`

Strong: `brushed aluminum body, soft morning side light, palette muted teal and warm stone`

### 5. Scene density over adjectives

Include 5–12 concrete nouns (surfaces, props, reflections) instead of `stunning, beautiful, 8K`.

### 6. Multi-panel consistency

For grids and character sheets: exact panel count (`3×3`, `16-panel`), shared palette, per-panel role.

### 7. Edit invariants

For reference-based edits:

> Change background to soft grey gradient; **keep product shape, label text, and camera angle identical**.

Index references: `Image 1: product`, `Image 2: style only`.

### 8. Targeted negation

Short avoid-lines for likely failures:

`Avoid: fake brand logos, garbled characters, anime style, unreadable microtext.`

## Chinese / multilingual

- Specify `Simplified Chinese` or `Traditional Chinese`
- Provide all modules and hierarchy
- Require `crisp legible text, no garbled characters`

## Safety

- No operational harmful content
- Brand aesthetics OK with **original** characters/products
- Real-person likeness edits may fail moderation — abstract or owned refs only
