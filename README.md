# Vidau Mobile

对标 WorkBuddy「链接电脑」的 Flutter 客户端；另含可独立部署的 **Cloud Agent** 后端。

## 文档

- Mobile Link 设计：`docs/superpowers/specs/2026-07-10-vidau-mobile-link-phase1-design.md`
- Cloud Agent 设计：`docs/superpowers/specs/2026-07-11-vidau-cloud-agent-design.md`
- Backend 拆分：`docs/superpowers/specs/2026-07-14-backend-folder-split-design.md`
- 计划：`docs/superpowers/plans/2026-07-10-vidau-mobile-flutter.md`

## Cloud Agent（backend/）

后端同事可只拿 `backend/` 目录部署。详见 `backend/README.md`。

```bash
cd backend
cp .env.example .env
docker compose up -d --build
# 或：python3.11 -m venv .venv && source .venv/bin/activate
#     pip install -r requirements.txt && ./scripts/run_dev.sh
curl http://localhost:8787/health
```

Flutter 云端联调示例：

```bash
flutter run --dart-define=EXECUTION_MODE=cloud --dart-define=CLOUD_HOST=<LAN_IP>
```

## 本地联调（Mobile Link 三端）

### 1. Link Gateway

```bash
cd /Users/kean/Desktop/DemoFile/mobile_agent_service
./scripts/run.sh
```

### 2. 桌面端

确保 `~/.vidau/.env` 含：

```
MOBILE_LINK_ENABLED=true
MOBILE_LINK_URL=ws://127.0.0.1:8787/ws
MOBILE_LINK_TOKEN=demo-token
MOBILE_LINK_ALLOW_ALL_USERS=true
GATEWAY_ALLOW_ALL_USERS=true
```

启用插件并启动 gateway：

```bash
vidau plugins enable platforms/mobile
vidau gateway install && vidau gateway start
vidau gateway status
curl -s http://127.0.0.1:8787/devices -H 'Authorization: Bearer demo-token'
```

### 3. 移动端

默认 `LinkMode.remote`（`lib/core/config.dart`）。

```bash
cd /Users/kean/Desktop/DemoFile/mobile_agent
flutter run
```

登录用「使用演示账号继续」→ 选在线电脑 → 发指令。

## Mock 模式

将 `AppConfig.current` 的 `linkMode` 改为 `LinkMode.mock` 即可离线开发 UI。
