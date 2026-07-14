# Cloud Agent 桌面 Expert 对齐设计

**日期：** 2026-07-13  
**状态：** 已批准  
**工作树：** `.worktrees/cloud-agent-p0`

**关联：** [Cloud Agent 产品设计](./2026-07-11-vidau-cloud-agent-design.md)、桌面 catalog `~/.vidau/cache/experts-catalog.json`

---

## 1. 目标

手机云端 Experts 列表对齐桌面线上 4 个 Expert；**执行全部在云端**（Skill / MCP / sandbox），手机无本机 runtime。

| Expert | 本期 |
|---|---|
| Creative | 可安装、可会话；Skill 按 manifest **全量** |
| TikTok Ads | 可安装、可会话（保持并微调文案） |
| GEO | **新增**可安装、可会话；MCP `https://geo.vidau.ai/mcp` |
| Social | 卡片上架，`availability=coming_soon`，不可 Install / 开聊 |

### 明确不做

- Social 云端 browser / 平台登录发布
- 桌面离线兜底 4 个 bundled Expert
- 手机本机安装 Skill / 跑 MCP

---

## 2. 云端运行边界

| 能力 | 位置 |
|---|---|
| Skill 文件 | 服务器 `backend/data/skills/` |
| MCP | 云端进程 → 远程 MCP |
| Sandbox | 云端本机磁盘 |
| 手机 | 仅 UI + WS |

---

## 3. Catalog

- 字段对齐桌面 remote catalog（id / name_i18n / description / tags / toolsets / mcp_servers / remote_skill_sources / activation_prompt）
- 新增 `availability`: `ready` | `coming_soon`
- Creative：`manifest_url` 驱动全量 paths（不硬编码子集）
- GEO：`requires_mcp: ["vidau-geo"]`
- Social：`availability: coming_soon`，`mcp_servers: []`

---

## 4. Install + Gateway + Session

- Install 写服务器 skills；优先 manifest；失败可拷贝 `~/.vidau/skills/{vidau-creative|vidau-geo}`
- Social install → 4xx
- Gateway 增加 `vidau-geo`（Streamable HTTP + vidau_user_id）
- `POST /v1/sessions` 拒绝 `coming_soon`

---

## 5. Flutter

- 列表 4 卡；coming_soon 禁用 Install/对话并提示
- 其余沿用现有门禁

---

## 6. 验收

1. `/v1/experts` 含 4 个；Social 为 coming_soon  
2. Social 无法 install/session  
3. GEO install 后云端有 skills，可会话调 geo MCP  
4. Creative skills 数量对齐 manifest  
5. 手机无本地 runtime 依赖  
