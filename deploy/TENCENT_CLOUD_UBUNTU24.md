# 腾讯云 Ubuntu 24.04 部署指南（IKnow / SkillGetter）

适用：已有 Ubuntu 24.04 云服务器（腾讯云 CVM），公网 IP，域名可选。

## 1. 架构概览

```
Internet → Nginx(:80) → Frontend 静态页
                      → /api、/ws → FastAPI(:8000)
MySQL 8 (:3306)  Redis 7 (:6379)
Worker: scan_loop（10min 官方扫描+推送 / 8h 全量扫描）
```

## 2. 服务器准备

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl nginx ufw

# Docker（推荐）
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# 重新登录 shell 后生效
sudo apt install -y docker-compose-plugin
```

防火墙（按需）：

```bash
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

## 3. 拉取代码

```bash
sudo mkdir -p /opt/iknow
sudo chown $USER:$USER /opt/iknow
cd /opt/iknow
git clone <你的仓库地址> .
```

## 4. 配置环境变量

```bash
cp .env.example .env
vim .env
```

**生产必改项：**

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | Docker 内用 `mysql+aiomysql://root:强密码@mysql:3306/iknow` |
| `REDIS_URL` | `redis://redis:6379/0` |
| `MYSQL_ROOT_PASSWORD` | 与 compose 一致 |
| `DEEPSEEK_API_KEY` | LLM  enrichment |
| `RULIU_APP_KEY` / `RULIU_APP_SECRET` / `RULIU_AGENT_ID` | 如流推送 |
| `RULIU_DM_USER` | 你的如流账号（单聊接收人） |
| `GITHUB_TOKEN` | 可选，提高 GitHub 限流 |
| `SCAN_GLOBAL_ENABLED` | `true` |

调度配置（已内置，一般无需改）：

- `config/worker_schedule.yaml` — 10 分钟官方门户 / 8 小时全量
- `config/digest_pick.yaml` — 8 小时窗口评分、白名单+install 权重
- `config/official_portals.yaml` — 12 家官方门户

## 5. Docker Compose 一键部署（推荐）

```bash
cd /opt/iknow
bash deploy/scripts/deploy_tencent.sh
```

或手动：

```bash
cd /opt/iknow/backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m app.init_db

cd /opt/iknow/frontend
npm ci && npm run build

cd /opt/iknow/deploy
docker compose -f docker-compose.prod.yml up -d --build
```

验证：

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1/api/health   # 经 nginx
docker compose -f docker-compose.prod.yml logs -f worker
```

## 6. Nginx 反向代理（非 Docker 前端时）

```bash
sudo cp /opt/iknow/deploy/nginx.conf /etc/nginx/sites-available/iknow
sudo ln -sf /etc/nginx/sites-available/iknow /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 7. Systemd 部署（不用 Docker 时）

```bash
# 后端 + Worker
sudo cp /opt/iknow/deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable iknow-api iknow-worker
sudo systemctl start iknow-api iknow-worker

# 前端静态
cd /opt/iknow/frontend && npm ci && npm run build
sudo cp -r dist/* /var/www/iknow/
```

## 8. 运行行为说明

| 任务 | 间隔 | 行为 |
|------|------|------|
| 官方门户扫描 | **10 分钟** | 仅 12 家官网/API；有新增 → **如流单聊推送**（详细 Markdown） |
| 全量扫描 | **8 小时** | 所有 enabled 源完整 fetch + 指标快照 |
| 逐源轮询 | 默认关闭 | `config/worker_schedule.yaml` 中 `per_source_scan: false` |

全局开关：Dashboard → 源管理 → 全局扫描；或 Redis 键 `iknow:scan_global_enabled`。

## 9. 运维命令

```bash
# 查看 Worker 日志
docker compose -f /opt/iknow/deploy/docker-compose.prod.yml logs -f worker

# 重启
docker compose -f /opt/iknow/deploy/docker-compose.prod.yml restart api worker

# 手动触发官方扫描
curl -X POST http://127.0.0.1:8000/api/scan/official

# 数据库迁移（发版后）
cd /opt/iknow/backend && .venv/bin/python -m app.init_db
```

## 10. 腾讯云建议

1. **安全组**：仅开放 22/80/443；MySQL/Redis 不对公网。
2. **数据盘**：Docker volume `mysql_data` 可挂载到 CBS 数据盘。
3. **监控**：云监控 + `docker compose ps`；Worker 日志关键字 `official_new_push`、`full_scan_done`。
4. **HTTPS**：腾讯云 SSL 证书 + Nginx `listen 443 ssl`。
5. **备份**：定时 `mysqldump iknow` 到 COS。

## 11. 常见问题

- **推送没收到**：检查 `.env` 如流配置、`RULIU_DM_USER`、Worker 是否在跑。
- **扫描太慢**：确认 Worker 日志无 GitHub 全量请求；官方扫描应走 `fetch_official_portal`。
- **评分异常**：确认 `config/digest_pick.yaml` version 3 已加载；重启 worker。
