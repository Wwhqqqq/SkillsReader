# SkillRadar 待办清单

> 更新日期：2026-06-16  
> 基线：本机已跑通采集 + MySQL + 调试台；库内约 **863** 条 Skill  
> 相关文档：[NEXT_PHASE_DEVELOPMENT.md](./NEXT_PHASE_DEVELOPMENT.md) | [DEBUG_CONSOLE.md](./DEBUG_CONSOLE.md) | [如流机器人操作文档](./如流机器人操作文档/)

---

## 目录

1. [当前完成度总览](#1-当前完成度总览)
2. [P0 — 如流开放 API（最高优先级）](#2-p0--如流开放-api最高优先级)
3. [P1 — Phase 1 收尾与上线](#3-p1--phase-1-收尾与上线)
4. [P2 — Phase 2：质量 + 国内 + 告警](#4-p2--phase-2质量--国内--告警)
5. [P3 — Phase 3：运营增强](#5-p3--phase-3运营增强)
6. [P4 — Phase 4：产品化](#6-p4--phase-4产品化)
7. [技术债与横切任务](#7-技术债与横切任务)
8. [需你提供的资源 / 权限](#8-需你提供的资源--权限)
9. [推荐实施顺序](#9-推荐实施顺序)
10. [各阶段 Done 定义](#10-各阶段-done-定义)

---

## 1. 当前完成度总览

### 1.1 产品能力矩阵

| 能力 | 状态 | 备注 |
|------|------|------|
| 海外 Skill 采集（skills.sh + GitHub） | ✅ 已完成 | 本机实测有数据 |
| 数据入库 / 去重 / 打分 | ✅ 已完成 | |
| 规则分类（关键词 + 地域） | ✅ 已实现 | 准确率待调优，大量 `uncategorized` |
| 本地调试台 | ✅ 已完成 | `python -m skill_radar debug` |
| 一键启动脚本 | ✅ 已完成 | `./scripts/start_all.sh` |
| MySQL 本机部署 | ✅ 已完成 | `./scripts/setup_mysql.sh` |
| **如流群推送（真实 API）** | ❌ **未做** | 当前为占位 Webhook，与官方 Open API 不一致 |
| 生产 Cron / 服务器部署 | ❌ 未验证 | Docker 脚本已有，未上生产 |
| LLM 分类兜底 | ❌ 未做 | `llm.py` 空文件 |
| 国内源（Gitee / Awesome） | ❌ 未做 | 采集器 stub |
| 官方新发即时告警 | ❌ 未做 | |
| 远程 SKILL.md 校验 | ❌ 未做 | |
| MCP Market 采集 | ❌ 未做 | 默认 disabled |
| 人工反馈闭环 | ❌ 未做 | 表已建，无业务逻辑 |
| 多群 / 订阅 / 周报 | ❌ 未做 | Phase 4 |

### 1.2 代码模块状态

| 模块 | 文件 | 状态 |
|------|------|------|
| skills.sh 采集 | `collectors/skills_sh.py` | ✅ |
| GitHub Search | `collectors/github_search.py` | ✅ |
| GitHub Watch | `collectors/github_watch.py` | ✅ |
| Gitee 采集 | `collectors/gitee.py` | 🔶 stub |
| Awesome 列表 | `collectors/awesome_lists.py` | 🔶 stub |
| MCP Market | `collectors/mcp_market.py` | 🔶 stub |
| 规则分类 | `processors/classifier/rules.py` | ✅ |
| LLM 分类 | `processors/classifier/llm.py` | ❌ 空 |
| 混合分类 | `processors/classifier/hybrid.py` | 🔶 仅规则层 |
| 如流通知 | `notifiers/ruliu.py` | 🔶 占位 payload |
| 本地调试台 | `debug/app.py` | ✅ |

---

## 2. P0 — 如流开放 API（最高优先级）

**为什么先做：** 没有真实推送，产品无法交付价值；你已有完整 API 文档，与当前实现差距明确。

**参考文档：**

- [调用开放API_获取app_access_token.md](./如流机器人操作文档/调用开放api/调用开放API_获取app_access_token.md)
- [以机器人身份发消息给群聊.md](./如流机器人操作文档/调用开放api/群聊api/以机器人身份发消息给群聊.md)

### 2.1 待办任务

| ID | 任务 | 文件 | 说明 |
|----|------|------|------|
| R1 | 实现 `app_access_token` 获取与缓存 | 新建 `notifiers/ruliu_auth.py` 或扩展 `ruliu.py` | `POST /api/v1/auth/app_access_token`；body 中 `app_secret` = `strlower(md5hex(原始secret))`；token 缓存至 expire |
| R2 | 实现群消息发送 | `notifiers/ruliu.py` | `POST /robot/msg/groupmsgsend`；Header: `Authorization: Bearer-{app_access_token}`（注意文档要求的 `Bearer-` 前缀） |
| R3 | 构造正式请求体 | `notifiers/ruliu.py` | `message.header.toid` = 群 ID；`msgtype: TEXT`；`body[].content` = 日报正文 |
| R4 | 新增环境配置项 | `.env.example`, `settings.py` | `RULIU_APP_KEY`, `RULIU_APP_SECRET`, `RULIU_GROUP_ID`, `RULIU_API_BASE`（preonline / 线上地址） |
| R5 | 调试台预览对齐 | `debug/app.py`, `debug/services.py` | 预览页展示 Open API 真实 JSON，而非占位 `{"message":...}` |
| R6 | 错误处理与限流 | `notifiers/ruliu.py` | 文档默认 10 QPS；token 过期自动刷新；失败写 `daily_digests.push_error` |
| R7 | 联调验收 | CLI | `notify-test` → 群收到测试消息 → `run --once` → 群收到日报 |

### 2.2 权限前置（需人工）

- [ ] 在如流机器人后台开通 **「以机器人身份发送消息到群聊」** 权限
- [ ] 获取 `app_key` / `app_secret`（原始 secret，代码内做 md5）
- [ ] 确认目标群 `toid`（群 ID）
- [ ] 确认环境：preonline 或线上 `apiin.im.baidu.com`

### 2.3 验收标准

- [ ] 调试台「如流预览」与真实 POST body 一致
- [ ] `python -m skill_radar notify-test` 群内可见
- [ ] `python -m skill_radar run --once` 推送日报成功，`daily_digests.push_status = sent`

---

## 3. P1 — Phase 1 收尾与上线

| ID | 任务 | 状态 | 说明 |
|----|------|------|------|
| P1-1 | 分类调优 | ⏳ | 编辑 `config/taxonomy.yaml`，降低 `uncategorized` / `needs_review` 比例 |
| P1-2 | 分类准确率抽样 | ⏳ | 人工抽 20 条，目标 > 70%（规则层） |
| P1-3 | 生产部署验证 | ❌ | Docker Compose + `docker/crontab` 在服务器实测 |
| P1-4 | 连续 3 天 Cron | ❌ | 自动采集 + 推送无人工干预 |
| P1-5 | 更新 `FOUNDATION_IMPLEMENTED.md` | ⏳ | 同步 Phase 1 实际完成项 |
| P1-6 | GitHub Token 轮换 | ⚠️ 建议 | Token 曾在对话中暴露，建议 revoke 后换新 |

### Phase 1 Done 定义（尚未全部达成）

- [x] 单次采集 `skills` 表有真实记录
- [x] 本地调试台可用
- [ ] 如流群收到格式化日报
- [ ] 连续 3 天 Cron 自动推送成功

---

## 4. P2 — Phase 2：质量 + 国内 + 告警

| ID | 任务 | 文件 | 验收 |
|----|------|------|------|
| P2-1 | LLM 分类兜底 | `processors/classifier/llm.py`, `hybrid.py` | confidence < 0.8 时调用；抽样准确率 ≥ 85% |
| P2-2 | LLM 客户端 | `utils/llm_client.py`（新建） | OpenAI 兼容 API；记录 `latency_ms` |
| P2-3 | Gitee 采集器 | `collectors/gitee.py` | 需 `GITEE_TOKEN`；国内 Skill 进日报 |
| P2-4 | Awesome 列表采集 | `collectors/awesome_lists.py` | 监控 awesome-*-skills commit |
| P2-5 | 官方新发即时告警 | `pipeline.py` | `official_owners` 新 Skill 立即 `send_alert` |
| P2-6 | GitHub health 完善 | 已有 | 生产环境持续监控 |

**依赖：** `LLM_API_KEY`、`GITEE_TOKEN`

---

## 5. P3 — Phase 3：运营增强

| ID | 任务 | 说明 |
|----|------|------|
| P3-1 | 远程 SKILL.md 校验 | `validator.py` 从 GitHub 拉取 frontmatter |
| P3-2 | 日报增强 | 含 1–2 句摘要；按场景分组；MCP 独立段 |
| P3-3 | MCP Market 采集 | `collectors/mcp_market.py`；启用 config |
| P3-4 | 人工反馈闭环 | 解析纠错 → `classification_feedback` → 更新 taxonomy |
| P3-5 | 正式管理看板（可选） | Streamlit/FastAPI；历史日报、采集统计 |

---

## 6. P4 — Phase 4：产品化

| ID | 任务 | 说明 |
|----|------|------|
| P4-1 | 多群推送 | 不同群不同过滤规则 |
| P4-2 | 订阅偏好 | 用户配置只看某类 Skill |
| P4-3 | 周报 / 月报 | 趋势、Top 10 |
| P4-4 | 规则自学习 | 从 feedback 生成 taxonomy 补丁 |
| P4-5 | `run --since Nd` | CLI 补采参数 |
| P4-6 | 数据归档 | > 90 天 logs 压缩归档 |

---

## 7. 技术债与横切任务

| ID | 项 | 优先级 | 说明 |
|----|-----|--------|------|
| TD-1 | 如流 Open API 替换 Webhook 占位 | P0 | 见 §2 |
| TD-2 | `items_new` 统计 | ✅ 已做 | pipeline 已填充 |
| TD-3 | 测试覆盖扩充 | P1 | collector / notifier Open API mock 测试 |
| TD-4 | 日志写文件 | P2 | `/var/log/skill-radar/app.log` |
| TD-5 | `classification_feedback` API | P3 | 表已建，无读写 |
| TD-6 | skills.sh API 变更监控 | P2 | 当前 HTML 解析，站点改版需适配 |
| TD-7 | 首次全量采集 vs 增量 | P2 | 当前 24h 窗口 + 指纹去重；可优化「仅推 truly new」 |

---

## 8. 需你提供的资源 / 权限

| 资源 | 阶段 | 状态 | 用途 |
|------|------|------|------|
| MySQL | P1 | ✅ 已配置 | 存储 |
| `GITHUB_TOKEN` | P1 | ✅ 已写入 `.env` | GitHub 采集（建议轮换） |
| 如流 `app_key` / `app_secret` | P0 | ⏳ 待提供 | Open API 鉴权 |
| 如流群 ID (`toid`) | P0 | ⏳ 待提供 | 群消息目标 |
| 如流 API 权限开通 | P0 | ⏳ 待申请 | 发群消息权限 |
| `GITEE_TOKEN` | P2 | ❌ | 国内源 |
| `LLM_API_KEY` | P2 | ❌ | 分类兜底 |
| 生产服务器 + Docker | P1 | ❌ | Cron 部署 |

---

## 9. 推荐实施顺序

```
Week 1（当前）
├── [P0] 如流 Open API 对接（R1–R7）
├── [P0] 调试台预览 + notify-test 联调
├── [P1] taxonomy 调优 + 分类抽样
└── [P1] 生产 Cron 部署（如流通后再上）

Week 2
├── [P2] LLM 分类 + hybrid 改造
├── [P2] Gitee + Awesome 采集器
└── [P2] 官方新发即时告警

Week 3–4
├── [P3] 远程校验 + 日报增强 + MCP
└── [P3] 反馈闭环 / 看板（可选）

按需
└── [P4] 多群、订阅、周报、自学习
```

---

## 10. 各阶段 Done 定义

| 阶段 | Done 的标准 | 当前 |
|------|-------------|------|
| **Phase 1 MVP** | 连续 3 天 Cron 自动推送；单日有真实新增；如流收到日报 | 🟡 约 70% |
| **Phase 2 V1** | 国内单独分组；分类 ≥ 85%；官方新发 5 分钟内告警 | 🔴 未开始 |
| **Phase 3 V2** | 日报含摘要；MCP 独立展示；可选看板 | 🔴 未开始 |
| **Phase 4 V3** | 多群/订阅可用；周报自动生成 | 🔴 未开始 |

---

## 附录：文档索引

| 文档 | 用途 |
|------|------|
| [TODO_BACKLOG.md](./TODO_BACKLOG.md) | **本文档** — 待办总览 |
| [NEXT_PHASE_DEVELOPMENT.md](./NEXT_PHASE_DEVELOPMENT.md) | 各 Task 详细实现规格 |
| [NEXT_PHASE_ROADMAP.md](./NEXT_PHASE_ROADMAP.md) | 路线图简版 |
| [DEBUG_CONSOLE.md](./DEBUG_CONSOLE.md) | 本地调试台使用 |
| [FOUNDATION_IMPLEMENTED.md](./FOUNDATION_IMPLEMENTED.md) | 已实现基线对照 |
| [如流机器人操作文档/](./如流机器人操作文档/) | 如流 Open API 官方说明 |

---

> **下一步建议：** 从 §2 如流 Open API（R1–R7）开始；拿到 `app_key` / `app_secret` / 群 ID 后即可开发联调。
