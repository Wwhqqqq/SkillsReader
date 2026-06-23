# SkillGetter

7×24 扫描国内超级 App（美团、阿里等）及补充源的 Agent Skill 生态，LLM 补全描述，Vue 控制台实时观测，一键推送如流双榜。

## 快速启动（本地）

```bash
# 1. 初始化
chmod +x scripts/setup_local.sh
./scripts/setup_local.sh

# 2. 启动 API（终端 1）
cd backend && .venv/bin/python -m app.main

# 3. 启动扫描 Worker（终端 2）
cd backend && .venv/bin/python -m app.worker.scan_loop

# 4. 启动前端（终端 3）
cd frontend && npm run dev
```

访问 http://localhost:5173

## 腾讯云部署

```bash
chmod +x deploy/scripts/deploy_tencent.sh
./deploy/scripts/deploy_tencent.sh
```

或使用 Docker Compose：

```bash
cd deploy && docker compose -f docker-compose.prod.yml up -d --build
```

## 环境变量

复制 `.env.example` 为 `.env`，配置：

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | MySQL 连接 |
| `REDIS_URL` | Redis（可选，无则内存降级） |
| `DEEPSEEK_API_KEY` | LLM 描述生成 |
| `GITHUB_TOKEN` | GitHub 补充源 |
| `RULIU_APP_KEY/SECRET` | 如流 Open API |
| `RULIU_GROUP_ID` | 群 ID |
| `RULIU_ALLOW_GROUP` | 是否允许群推送 |

## 架构

- **backend/** — FastAPI + 常驻 Worker + Source Adapters
- **frontend/** — Vue 3 + Naive UI 控制台
- **config/** — 采集源与双榜配置
- **deploy/** — Docker / Nginx / systemd

## 页面

| 路径 | 功能 |
|------|------|
| `/` | 总览 Dashboard |
| `/live` | 实时扫描日志 (WebSocket) |
| `/sources` | 源开关 / 定向扫描 |
| `/rankings` | 每日精选 Top N |
| `/push` | 精选预览与如流推送（单聊/群聊） |
| `/push` | 如流推送预览与发送 |
| `/debug` | Adapter 探针 / 双榜诊断 |

## 测试

```bash
./scripts/run_tests.sh
```
