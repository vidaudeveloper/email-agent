---
name: creative-seedance2-prompt
description: Seedance 2.0 / 即梦 video prompt engineering — mandatory before any video MCP call. Use when generating, editing, or refining video prompts for creative_generate_video, creative_image_to_video, creative_first_frame_to_video, script2film shot descriptions, or direct_video workflows.
metadata:
  layer: L0-foundation
  requires: []
  tags: [foundation, prompt, seedance, video, jimeng]
---

# Creative Seedance 2.0 Prompt

Production-grade **Seedance 2.0 / 即梦** video prompt engineering for VidAU Creative Agent.

> **Mandatory gate**: Load this skill **before** any MCP that generates video (`creative_generate_video`, `creative_image_to_video`, `creative_first_frame_to_video`, `creative_submit_workflow` with `direct_video`, or enriching script shot visuals). **Never** pass raw user text directly as `prompt` — run this skill's workflow first and use the output prompt string.

Adapted from [dexhunter/seedance2-skill](https://github.com/dexhunter/seedance2-skill) (MIT) and [MapleShaw/seedance2.0-prompt-skill](https://github.com/MapleShaw/seedance2.0-prompt-skill).

## When to load

| Trigger | Action |
|---------|--------|
| Any video MCP call | Generate Seedance prompt first → pass to MCP `prompt` |
| script2film / keyframes script writing | Enrich per-shot **visual + motion + audio** lines in Final Video Spec |
| User says 即梦 / Seedance / 视频提示词 / AI video | Load and draft or refine prompts |
| Reference-image-to-video | Include reference role semantics in prompt (see platform notes) |

## Agent workflow (required)

1. **Parse intent** — ad / short drama / product demo / transition / extend / edit / MV /科普
2. **Collect constraints** — duration (4–15s per clip), aspect ratio, reference assets (URLs already uploaded), locale (ZH default for 即梦-native copy; EN when user speaks English)
3. **Read references** when needed:
   - [platform-specs.md](references/platform-specs.md) — limits, compliance, VidAU MCP mapping
   - [templates.md](references/templates.md) — scene templates
   - [camera-vocabulary.md](references/camera-vocabulary.md) — shot language
4. **Draft prompt** using the structure below
5. **Compliance pass** — no real-person faces in refs; no IP/brand/celebrity names; no conflicting camera instructions
6. **Deliver** — output a single copy-ready prompt block; then call the downstream skill / MCP

## Prompt structure (SCELA + time segments)

For clips **>8s**, use segmented timing:

```
[主体/人物] + [场景] + [动作/运动] + [运镜] +
[0–Ns 分时段描述] + [转场/特效] + [音效/对白] + [风格/氛围]
```

| Block | Content |
|-------|---------|
| **S** Subject | Who/what is on screen; tie to reference roles |
| **C** Camera | Push/pull/pan/orbit/POV/establishing — one dominant move per beat |
| **E** Effect | Particles, speed ramp, match cut, product spin, etc. |
| **L** Light | Time of day, key/rim, color grade |
| **A** Audio | Diegetic SFX / ambient / dialogue tone — **no BGM in shot prompt** when VidAU adds BGM later (script2film) |

### @ reference syntax (即梦 native)

When user assets map to references, label each role explicitly:

```
@图片1 作为首帧，产品细节参考 @图片2，运镜参考 @视频1 的慢推
```

VidAU MCP uses HTTPS URLs — in Agent text, describe roles as `reference_image_urls[0] as product hero` and weave the same semantics into the prompt prose.

## VidAU-specific rules

| Context | Rule |
|---------|------|
| **script2film + voiceover** | Per-shot video prompt: diegetic SFX/foley OK; **strictly NO BGM / soundtrack / vocals** in prompt (server appends same rule) |
| **script2film default audio** | Ambient SFX only; BGM mixed server-side after concat |
| **direct / single clip** | `generate_audio=true` default; still avoid asking for full soundtrack in prompt — let model produce in-shot SFX |
| **reference mode** | Up to 9 refs; state each image's role (product / character / scene / style) |
| **first/last frame** | Prompt describes motion **between** keyframes; do not contradict frame composition |
| **Copyright safety** | Abstract cinematic language; no Disney/Marvel/celebrity/brand slogans; product = user's actual SKU only |

## Output format

Always return to user (and to downstream MCP) in this order:

```markdown
### Seedance Prompt
<paste-ready prompt text>

### Strategy
- Duration: Ns | Aspect: 9:16 | Mode: reference | first_last_frame | text_to_video
- References: [role → asset summary]
- Compliance: [what was avoided]
```

Then invoke the calling skill's MCP with `prompt` = the paste-ready text.

## Common failures (pre-empt)

| Mistake | Fix |
|---------|-----|
| Vague "参考视频1" | Specify: 运镜 / 动作 / 节奏 / 特效 |
| Too much in 4s | Reduce beats or extend duration |
| Conflicting cameras | One dominant move per segment |
| Real face in refs | Swap to product-only or stylized character |
| BGM in VO script2film shot | Strip music words; keep foley only |

## References

- [platform-specs.md](references/platform-specs.md)
- [templates.md](references/templates.md)
- [camera-vocabulary.md](references/camera-vocabulary.md)
