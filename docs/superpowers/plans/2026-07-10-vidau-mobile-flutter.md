# Vidau Mobile Link 移动端优先实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `mobile_agent` 落地 Flutter App：登录壳、设备列表、聊天同步 UI、本地存储；默认 Mock Link，协议与真 Gateway 对齐，服务端就绪后只换实现。

**Architecture:** 表现层（页面）→ 状态（Riverpod/ChangeNotifier）→ `LinkClient` 抽象（Mock / 真 WSS）→ 本地 SQLite。一期不依赖真实服务端即可跑通主路径；切 `LinkMode.remote` 后连真 Gateway。

**Tech Stack:** Flutter 3.35+、Dart 3.9+、`web_socket_channel`、`sqflite`、`flutter_secure_storage`、`go_router`、`provider` 或 `riverpod`

**服务端门槛（何时叫用户建仓）：** 当 Mock 主路径已通，需要与桌面 `vidau gateway` 真联调 `register_device` / `chat.*` 时，再创建 `link-gateway` 项目。此前移动端可独立开发。

---

## 文件结构（将创建）

```text
mobile_agent/
  pubspec.yaml
  lib/
    main.dart
    app.dart
    core/
      config.dart              # LinkMode, gatewayBaseUrl
      theme.dart
    models/
      device.dart
      chat_message.dart
      link_events.dart         # WS 消息类型与编解码
    link/
      link_client.dart         # 抽象接口
      mock_link_client.dart    # 本地模拟桌面回包
      ws_link_client.dart      # 真 WSS（先骨架，联调时补全）
    data/
      local_db.dart
      auth_store.dart
    features/
      auth/login_page.dart
      devices/devices_page.dart
      chat/chat_page.dart
    state/
      auth_controller.dart
      devices_controller.dart
      chat_controller.dart
  test/
    link_events_test.dart
    mock_link_client_test.dart
```

---

### Task 1: 创建 Flutter 工程与依赖

**Files:**
- Create: 标准 Flutter 工程于仓库根（或 `app/` 子目录；本计划用仓库根）
- Create: `pubspec.yaml` 依赖

- [ ] **Step 1: 生成工程**

```bash
cd /Users/kean/Desktop/DemoFile/mobile_agent
flutter create --org ai.vidau --project-name vidau_mobile .
```

若根目录已有 `docs/` / `.git`，`flutter create .` 可合并；冲突时保留 docs。

- [ ] **Step 2: 加入依赖到 `pubspec.yaml`**

```yaml
dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.8
  go_router: ^15.1.2
  provider: ^6.1.5
  web_socket_channel: ^3.0.3
  http: ^1.4.0
  sqflite: ^2.4.2
  path: ^1.9.1
  path_provider: ^2.1.5
  flutter_secure_storage: ^9.2.4
  uuid: ^4.5.1
  intl: ^0.20.2

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^5.0.0
```

- [ ] **Step 3: 安装并分析**

```bash
flutter pub get
flutter analyze
```

Expected: 无 error（warning 可后续清）

- [ ] **Step 4: Commit**

```bash
git add pubspec.yaml pubspec.lock lib/ test/ analysis_options.yaml README.md
git commit -m "chore: scaffold Flutter vidau_mobile app"
```

---

### Task 2: 协议模型与编解码

**Files:**
- Create: `lib/models/device.dart`
- Create: `lib/models/chat_message.dart`
- Create: `lib/models/link_events.dart`
- Test: `test/link_events_test.dart`

- [ ] **Step 1: 写失败测试**

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:vidau_mobile/models/link_events.dart';

void main() {
  test('chat.send roundtrip', () {
    final event = LinkEvent.chatSend(
      msgId: 'm1',
      deviceId: 'mac-1',
      text: '打开 Finder',
    );
    final decoded = LinkEvent.fromJson(event.toJson());
    expect(decoded.type, LinkEventType.chatSend);
    expect(decoded.text, '打开 Finder');
    expect(decoded.deviceId, 'mac-1');
  });
}
```

- [ ] **Step 2: 运行确认失败**

```bash
flutter test test/link_events_test.dart
```

Expected: FAIL（库/类型不存在）

- [ ] **Step 3: 实现模型**

`link_events.dart` 需覆盖：`registerDevice`（桌面侧）、`deviceStatus`、`chatSend`、`chatUser`、`chatAssistant`、`chatProgress`、`chatDone`、`chatError`、`ping`/`pong`、`historyPull`/`historySnapshot`。字段：`msgId`、`sessionId`、`deviceId`、`userId`、`ts`、`text`、`status`。

- [ ] **Step 4: 测试通过**

```bash
flutter test test/link_events_test.dart
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lib/models test/link_events_test.dart
git commit -m "feat: add link protocol models and codec"
```

---

### Task 3: LinkClient 抽象 + Mock 实现

**Files:**
- Create: `lib/link/link_client.dart`
- Create: `lib/link/mock_link_client.dart`
- Create: `lib/core/config.dart`
- Test: `test/mock_link_client_test.dart`

- [ ] **Step 1: 定义接口**

```dart
abstract class LinkClient {
  Stream<LinkEvent> get events;
  Future<void> connect({required String accessToken});
  Future<void> disconnect();
  Future<List<Device>> listDevices();
  Future<void> sendChat({required String deviceId, required String text});
  Future<void> pullHistory({required String deviceId, int limit = 50});
}
```

- [ ] **Step 2: Mock 行为**

`MockLinkClient`：

1. `listDevices` 返回 1 台 online 电脑（如 `Kean-MacBook-Pro`）
2. `sendChat` 先 emit `chat.user`，再隔 200–500ms emit 若干 `chat.progress`，再 `chat.assistant` + `chat.done`
3. 不连网络

- [ ] **Step 3: 测试 Mock 闭环**

```dart
test('sendChat emits user then done', () async {
  final client = MockLinkClient();
  await client.connect(accessToken: 'test');
  final done = client.events.firstWhere((e) => e.type == LinkEventType.chatDone);
  await client.sendChat(deviceId: 'mac-1', text: 'hello');
  await done;
});
```

- [ ] **Step 4: Commit**

```bash
git add lib/link lib/core/config.dart test/mock_link_client_test.dart
git commit -m "feat: add LinkClient interface and mock desktop replies"
```

---

### Task 4: 本地 SQLite 缓存

**Files:**
- Create: `lib/data/local_db.dart`
- Create: `lib/data/auth_store.dart`

- [ ] **Step 1: `LocalDb` 表**

- `devices(device_id PK, name, status, updated_at)`
- `messages(msg_id PK, device_id, session_id, role, text, created_at)`

提供：`upsertDevice`、`listDevices`、`insertMessage`、`messagesForDevice`。

- [ ] **Step 2: `AuthStore`**

用 `flutter_secure_storage` 存 `accessToken` / `refreshToken` / `userId`；Mock 模式可写死 `demo-user`。

- [ ] **Step 3: Commit**

```bash
git add lib/data
git commit -m "feat: add local sqlite cache and secure auth store"
```

---

### Task 5: 页面与导航（登录 → 设备 → 聊天）

**Files:**
- Create: `lib/app.dart`
- Create: `lib/features/auth/login_page.dart`
- Create: `lib/features/devices/devices_page.dart`
- Create: `lib/features/chat/chat_page.dart`
- Create: `lib/state/*.dart`
- Modify: `lib/main.dart`

- [ ] **Step 1: 路由**

`/login` → `/devices` → `/chat/:deviceId`

- [ ] **Step 2: 登录页（Mock）**

按钮「使用演示账号继续」→ 写入 AuthStore → 进设备页。真 SSO 留接口注释，服务端就绪后接 Portal。

- [ ] **Step 3: 设备页**

展示 `LinkClient.listDevices()`；online 可点进聊天；offline 灰色不可进或提示。

- [ ] **Step 4: 聊天页**

输入框发送 → `sendChat`；监听 `events` 追加气泡（user / progress / assistant）；写入 `LocalDb`。

- [ ] **Step 5: 真机/模拟器跑通**

```bash
flutter run
```

Expected: Mock 下可完成 登录→选电脑→发指令→看到模拟执行流

- [ ] **Step 6: Commit**

```bash
git add lib/
git commit -m "feat: add login, devices, and chat screens with mock link"
```

---

### Task 6: WsLinkClient 骨架（不阻塞 UI）

**Files:**
- Create: `lib/link/ws_link_client.dart`
- Modify: `lib/core/config.dart`（`LinkMode.mock | remote`，`gatewayWsUrl`）

- [ ] **Step 1: 实现骨架**

连接 `wss://.../ws?token=`，按 `LinkEvent` 收发；`listDevices` 调 `GET /devices`。无服务端时默认不启用。

- [ ] **Step 2: 用 config 切换**

```dart
enum LinkMode { mock, remote }
```

`main.dart` 根据 `LinkMode` 注入 `MockLinkClient` 或 `WsLinkClient`。

- [ ] **Step 3: Commit**

```bash
git add lib/link/ws_link_client.dart lib/core/config.dart lib/main.dart
git commit -m "feat: add WsLinkClient skeleton behind LinkMode.remote"
```

---

### Task 7: README 与服务端门槛说明

**Files:**
- Create/Modify: `README.md`

- [ ] **Step 1: 写清如何跑 Mock、如何切 remote、何时需要建 `link-gateway`**

门槛原文写入 README：

> 当需要与桌面 `vidau gateway` 真机联调（设备注册、真实 chat 转发）时，再创建服务端项目并实现 Link Gateway；此前请保持 `LinkMode.mock`。

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: explain mock mode and when to create link-gateway"
```

---

## 规格覆盖自检

| Spec 项 | 对应 Task |
|---|---|
| Flutter 移动端 | Task 1–5 |
| 设备列表 / 聊天 / 流式展示 | Task 3, 5 |
| 本地存储 | Task 4 |
| 协议与 Gateway 对齐 | Task 2, 6 |
| 账号 SSO | Task 5 Mock 壳；真 SSO 等服务端 |
| 桌面 channel / 真执行 | 不在本计划（桌面仓 + 服务端） |

---

## 执行说明

本计划 **只覆盖移动端**。桌面端由你本地运行；服务端在 Task 5–6 Mock 闭环完成后、准备真联调时再建。
