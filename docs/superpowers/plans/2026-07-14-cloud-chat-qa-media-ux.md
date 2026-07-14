# Cloud Chat Q&A + Media UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flutter Cloud Chat shows pure Q&A transcript, Manus-style media Shimmer cards, and dual-position Phase UI (in-stream + floating bar) using existing `media.*` WS events with no backend changes.

**Architecture:** Extend `CloudEvent` for `media.*`; `CloudChatController` maintains `PhaseUiState` + media messages by `job_id`, filters progress/tool/sandbox out of the transcript; `CloudChatPage` renders Phase/Media widgets and a floating bar that shares the same state.

**Tech Stack:** Flutter, existing Cloud WS client, Creative `media.*` from `cloud_agent` MediaJobTracker

**Worktree:** `.worktrees/cloud-agent-p0` on branch `feature/cloud-agent-p0`

**Spec:** `docs/superpowers/specs/2026-07-14-cloud-chat-qa-media-ux-design.md`

**Status:** Implemented in worktree commit `d0bd089` (2026-07-14). Tests: `flutter test test/cloud_media_events_test.dart test/cloud_chat_controller_media_test.dart` PASS.

---

## File map

| File | Responsibility |
|------|----------------|
| `lib/cloud/models/cloud_models.dart` | `media.*` event types + payload fields |
| `lib/state/cloud_chat_controller.dart` | Media upsert, PhaseUiState, transcript filter |
| `lib/features/chat/widgets/phase_status_card.dart` | In-stream Phase card (active / collapsed) |
| `lib/features/chat/widgets/media_job_card.dart` | Shimmer → image/video / error |
| `lib/features/chat/widgets/phase_floating_bar.dart` | Bottom floating bar |
| `lib/features/chat/cloud_chat_page.dart` | Wire widgets; hide progress/tool bubbles |
| `test/cloud_media_events_test.dart` | Parse media events |
| `test/cloud_chat_controller_media_test.dart` | Controller media + filter behavior |

---

### Task 1: CloudEvent media.* + tests

**Files:**
- Modify: `.worktrees/cloud-agent-p0/lib/cloud/models/cloud_models.dart`
- Create: `.worktrees/cloud-agent-p0/test/cloud_media_events_test.dart`

- [x] **Step 1: Write failing test**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:vidau_mobile/cloud/models/cloud_models.dart';

void main() {
  test('parses media.placeholder', () {
    final e = CloudEvent.fromJson({
      'type': 'media.placeholder',
      'session_id': 's1',
      'job_id': 'job-1',
      'kind': 'image',
      'tool': 'creative_generate_image',
      'ratio': '1:1',
      'label': '生成图片',
    });
    expect(e.type, CloudEventType.mediaPlaceholder);
    expect(e.jobId, 'job-1');
    expect(e.kind, 'image');
    expect(e.ratio, '1:1');
  });

  test('parses media.progress / ready / failed', () {
    final p = CloudEvent.fromJson({
      'type': 'media.progress',
      'job_id': 'job-1',
      'progress': 42,
      'status': 'processing',
      'message': '生成中',
    });
    expect(p.progress, 42);
    expect(p.message, '生成中');

    final r = CloudEvent.fromJson({
      'type': 'media.ready',
      'job_id': 'job-1',
      'kind': 'image',
      'urls': ['https://example.com/a.png'],
      'thumbnail_url': 'https://example.com/t.png',
    });
    expect(r.urls, ['https://example.com/a.png']);
    expect(r.thumbnailUrl, 'https://example.com/t.png');

    final f = CloudEvent.fromJson({
      'type': 'media.failed',
      'job_id': 'job-1',
      'error': 'timeout',
    });
    expect(f.error, 'timeout');
  });
}
```

- [ ] **Step 2: Run test — expect FAIL** (unknown types / missing fields)

Run from worktree: `flutter test test/cloud_media_events_test.dart`

- [ ] **Step 3: Extend `CloudEventType` + `CloudEvent`**

Add enum values: `mediaPlaceholder`, `mediaProgress`, `mediaReady`, `mediaFailed`.

Add fields on `CloudEvent`: `jobId`, `kind`, `progress` (int?), `message`, `urls` (List\<String\>?), `thumbnailUrl`, `error`, `ratio`, `label`, `status` (already exists — reuse for progress status string).

Wire `typeFromWire` / `wireType` / `fromJson` / `toJson` for:

| wire | fields |
|------|--------|
| `media.placeholder` | job_id, kind, tool, ratio?, label? |
| `media.progress` | job_id, progress, status, message? |
| `media.ready` | job_id, kind, urls[], thumbnail_url?, message? |
| `media.failed` | job_id, error |

Parse `progress` via existing `_asInt`. Parse `urls` as string list.

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit in worktree**

```bash
cd .worktrees/cloud-agent-p0
git add lib/cloud/models/cloud_models.dart test/cloud_media_events_test.dart
git commit -m "feat(cloud): parse media.* WebSocket events"
```

---

### Task 2: Controller — PhaseUiState, media upsert, Q&A filter

**Files:**
- Modify: `.worktrees/cloud-agent-p0/lib/state/cloud_chat_controller.dart`
- Create: `.worktrees/cloud-agent-p0/test/cloud_chat_controller_media_test.dart`

- [ ] **Step 1: Add models to controller file (or small companion)**

```dart
enum MediaJobState { pending, generating, ready, failed }
enum PhaseStatus { active, ready, failed }

class PhaseUiState {
  const PhaseUiState({
    required this.jobId,
    required this.kind,
    required this.label,
    required this.progress,
    required this.elapsed,
    required this.status,
    this.thumbnailUrl,
  });
  final String jobId;
  final String kind;
  final String label;
  final int progress;
  final Duration elapsed;
  final PhaseStatus status;
  final String? thumbnailUrl;
}

// Extend CloudMessageKind with: media, phase
// Extend CloudDisplayMessage with optional media fields:
// jobId, mediaKind, mediaState, progress, statusMessage, urls, thumbnailUrl, error, ratio, phaseCollapsed
```

- [ ] **Step 2: Controller state**

```dart
PhaseUiState? activePhase; // for floating bar (latest active)
final Map<String, DateTime> _jobStartedAt = {};
bool phaseBarVisible = false;
int otherActiveJobCount = 0;

void dismissPhaseBar() { phaseBarVisible = false; notifyListeners(); }
String? scrollToJobId; // set when bar tapped; UI clears after scroll
void clearScrollTarget() { scrollToJobId = null; }
```

- [ ] **Step 3: `_onEvent` changes**

- `chatProgress` / `toolMcp`: **do not** append to `messages`. If no active media job (`_hasActiveMedia`), update `activePhase` with kind `thinking`, label from content/tool, `phaseBarVisible = true`.
- `sandboxStatus`: **ignore** (no transcript, no bar).
- `mediaPlaceholder` / `mediaProgress` / `mediaReady` / `mediaFailed`: call `_upsertMedia(event)`.
- `chatDone`: do **not** clear media cards or phase state for active jobs.

`_upsertMedia` logic:

1. Find message by `jobId` or create two messages: phase (`kind=phase`, id=`phase-$jobId`) + media (`kind=media`, id=`media-$jobId`).
2. Update media fields from event; on placeholder set `pending`/`generating`, start `_jobStartedAt`.
3. Rebuild `PhaseUiState` from latest media job; set `phaseBarVisible` when status active.
4. On ready/failed: set `phaseCollapsed=true` on phase message; schedule hide bar after 1.2s on ready; keep bar until dismiss/next send on failed.
5. Multi-job: `activePhase` = most recently updated active job; `otherActiveJobCount` = other actives.

Friendly label helper: prefer `event.message` / `event.label`, else map tool suffix (e.g. `creative_generate_image` → `生成图片`).

- [ ] **Step 4: Unit test with fake stream**

Use a test-only controller setup: inject a `StreamController<CloudEvent>` via a thin fake `CloudClient` **or** test pure helpers if faking client is heavy. Minimal path: extract `_applyMediaEvent` / filter logic testable without full CloudClient — prefer testing by constructing controller with a mock.

If mock is heavy, test:

```dart
test('media.placeholder creates phase+media; progress updates; ready collapses', () {
  // Use CloudChatController with FakeCloudClient that exposes event sink
});
```

FakeCloudClient must implement `CloudClient` methods used by `start`/`send` — for media-only tests, skip `start()` and call a `@visibleForTesting void handleEvent(CloudEvent e)` that wraps `_onEvent`.

Add:

```dart
@visibleForTesting
void debugHandleEvent(CloudEvent event) => _onEvent(event);
```

Then test without network.

- [ ] **Step 5: Run tests PASS + commit**

```bash
flutter test test/cloud_media_events_test.dart test/cloud_chat_controller_media_test.dart
git add lib/state/cloud_chat_controller.dart test/cloud_chat_controller_media_test.dart
git commit -m "feat(cloud): media job state and Q&A transcript filter"
```

---

### Task 3: UI widgets — Phase card, Media card, Floating bar

**Files:**
- Create: `.worktrees/cloud-agent-p0/lib/features/chat/widgets/phase_status_card.dart`
- Create: `.worktrees/cloud-agent-p0/lib/features/chat/widgets/media_job_card.dart`
- Create: `.worktrees/cloud-agent-p0/lib/features/chat/widgets/phase_floating_bar.dart`

- [ ] **Step 1: `PhaseStatusCard`**

- Active: white card, 44px thumb (thumbnail or grey box), title `生成中 · {kind}`, label, `elapsed` + `progress%`
- Collapsed ready: one line `已完成 · {kind}`
- Collapsed failed: one line `生成失败`

- [ ] **Step 2: `MediaJobCard`**

- pending/generating: AspectRatio from `ratio` (default image 1:1, video 9:16), shimmer via `LinearGradient` + `AnimationController` (or simple pulsing `Container`), text `Generating… {progress}%`
- ready: `Image.network` for image; video show cover + open URL (`url_launcher` if already a dep, else `launchUrl` pattern from page)
- failed: error text

Reuse patterns from `_UserBubbleImage` / existing `url_launcher` usage in `cloud_chat_page.dart`.

- [ ] **Step 3: `PhaseFloatingBar`**

Pill above composer: thumb + truncated label + elapsed/%; optional `+N`; onTap callback; hide when `!visible`.

- [ ] **Step 4: Commit**

```bash
git add lib/features/chat/widgets/
git commit -m "feat(cloud): phase and media loading widgets"
```

---

### Task 4: Wire `cloud_chat_page` + scroll-to-job

**Files:**
- Modify: `.worktrees/cloud-agent-p0/lib/features/chat/cloud_chat_page.dart`

- [ ] **Step 1: ListView itemBuilder**

```dart
switch (msg.kind) {
  case CloudMessageKind.user:
  case CloudMessageKind.assistant:
    return _Bubble(message: msg);
  case CloudMessageKind.phase:
    return PhaseStatusCard(message: msg);
  case CloudMessageKind.media:
    return KeyedSubtree(
      key: ValueKey('media-${msg.jobId}'),
      child: MediaJobCard(message: msg),
    );
  case CloudMessageKind.progress:
  case CloudMessageKind.tool:
    return const SizedBox.shrink(); // belt-and-suspenders
}
```

- [ ] **Step 2: Stack floating bar above SafeArea composer**

When `chat.phaseBarVisible && chat.activePhase != null`, show `PhaseFloatingBar`. On tap: `chat.requestScrollToJob(jobId)` then scroll to key.

- [ ] **Step 3: Elapsed ticker**

In `_CloudChatViewState`, if any active media, `Timer.periodic(1s)` → `setState` (or controller `tickElapsed()`) so elapsed labels update.

- [ ] **Step 4: `flutter analyze` on touched files + commit**

```bash
flutter analyze lib/cloud/models/cloud_models.dart lib/state/cloud_chat_controller.dart lib/features/chat/
git add lib/features/chat/cloud_chat_page.dart
git commit -m "feat(cloud): wire Q&A media UX in cloud chat page"
```

---

### Task 5: Verification

- [ ] **Step 1:** `flutter test test/cloud_media_events_test.dart test/cloud_chat_controller_media_test.dart`
- [ ] **Step 2:** `flutter analyze` (touched paths clean)
- [ ] **Step 3:** Manual smoke note: Creative Expert → generate image → Phase + Shimmer + bar → ready collapses

---

## Spec coverage

| Spec requirement | Task |
|------------------|------|
| Pure Q&A (hide progress/tool/sandbox) | 2, 4 |
| Media Shimmer → ready/failed | 2, 3, 4 |
| Dual Phase (stream + float) | 2, 3, 4 |
| Shared PhaseUiState + collapse rules | 2 |
| No backend change | ✓ |
| chat.done keeps media updating | 2 |
| Multi-job floating bar +N | 2, 3 |
| Local elapsed | 2, 4 |

## Out of scope (do not implement)

Task steps, hard confirm gate, streaming tokens, history media replay, Link mode, `phase_label` WS field.
