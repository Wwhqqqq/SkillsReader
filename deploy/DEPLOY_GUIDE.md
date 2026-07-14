# IKnow (SkillGetter) — 腾讯云 Ubuntu 24 完整部署指南

> 适用: 已有腾讯云 CVM Ubuntu 24.04 实例，公网 IP，域名可选。

---

## 目录

- [1. 架构概览](#1-架构概览)
- [2. 服务器初始化](#2-服务器初始化)
- [3. 数据库迁移（本地 → 服务器）](#3-数据库迁移本地--服务器)
- [4. 代码部署](#4-代码部署)
- [5. 一键部署脚本](#5-一键部署脚本)
- [6. 验证部署](#6-验证部署)
- [7. 配置域名 + HTTPS（可选）](#7-配置域名--https可选)
- [8. 运维常用命令](#8-运维常用命令)
- [9. 附录](#9-附录)

---

## 1. 架构概览

```
Internet → Nginx(:80) → Vue 前端静态页
                      → /api、/ws → FastAPI(:8000)
MySQL 8.0 (Docker)     Redis 7 (Docker)
Worker (scan_loop): 官方扫描 10 分钟/次，全量扫描 8 小时/次
```

Docker Compose 启动 5 个容器：

| 容器 | 端口 | 说明 |
|---|---|---|
| `mysql` | 3306 | MySQL 8.0，数据卷持久化 |
| `redis` | 6379 | Redis 7，pub/sub + 缓存 |
| `api` | 8000 | FastAPI 后端服务 |
| `worker` | — | 常驻扫描 Worker，定时拉取 + 如流推送 |
| `frontend` | 80 | Nginx 提供前端静态页 + API 反向代理 |

---

## 2. 服务器初始化

### 2.1 登录服务器

```bash
ssh ubuntu@<服务器公网IP>
```

### 2.2 执行初始化脚本

复制以下全部内容，在服务器终端粘贴执行：

```bash
#!/bin/bash
set -e

echo "========================================="
echo "  IKnow 服务器初始化"
echo "========================================="

# ---------- 系统更新 ----------
echo ">>> [1/5] 系统更新..."
sudo apt update && sudo apt upgrade -y

# ---------- 基础工具 ----------
echo ">>> [2/5] 安装基础工具..."
sudo apt install -y git curl nginx ufw

# ---------- Docker ----------
echo ">>> [3/5] 安装 Docker..."
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# ---------- Docker Compose 插件 ----------
echo ">>> [4/5] 安装 Docker Compose..."
sudo apt install -y docker-compose-plugin

# ---------- 防火墙 ----------
echo ">>> [5/5] 配置防火墙..."
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable

echo ""
echo "========================================="
echo "  初始化完成！"
echo "========================================="
echo ""
echo "请退出并重新登录使 docker 组生效："
echo "  exit"
echo "  ssh ubuntu@<服务器IP>"
echo ""
```

### 2.3 腾讯云控制台安全组

登录腾讯云控制台 → 云服务器 → 安全组 → 添加入站规则：

| 端口 | 协议 | 来源 | 说明 |
|---|---|---|---|
| 22 | TCP | 0.0.0.0/0 | SSH |
| 80 | TCP | 0.0.0.0/0 | HTTP |
| 443 | TCP | 0.0.0.0/0 | HTTPS |

> MySQL (3306) 和 Redis (6379) 不要对公网开放。

### 2.4 重新登录

```bash
exit
ssh ubuntu@<服务器公网IP>
```

验证 Docker：

```bash
docker --version          # 应显示 >= 27.x
docker compose version    # 应显示 >= 2.x
```

---

## 3. 数据库迁移（本地 → 服务器）

### 3.1 在本地 Mac 导出数据库

> **用 Docker 导出（推荐，无需安装 mysqldump）**

```bash
#!/bin/bash
# 保存为 backup_db.sh，在本地项目根目录执行
set -e

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="iknow_backup_${DATE}.sql"

echo "==> 导出本地 MySQL 数据库 (via Docker)"

docker run --rm --network host mysql:8.0 mysqldump \
  -h 127.0.0.1 -u root -pwhq050207 \
  --single-transaction \
  --routines \
  --triggers \
  --databases iknow \
  > "${BACKUP_FILE}"

echo "==> 备份完成: ${BACKUP_FILE}"
echo "文件大小: $(du -h "${BACKUP_FILE}" | awk '{print $1}')"
```

> 如果本地已安装 `mysqldump`，可以直接：
>
> ```bash
> mysqldump -u root -pwhq050207 --single-transaction --routines --triggers \
>   --databases iknow > iknow_backup_$(date +%Y%m%d).sql
> ```

### 3.2 传输到服务器

```bash
# 替换 <SERVER_IP> 为你的服务器公网 IP
scp iknow_backup_*.sql ubuntu@<SERVER_IP>:/tmp/

```

验证传输：

```bash
ssh ubuntu@<SERVER_IP> "ls -lh /tmp/iknow_backup_*.sql"
```

---

## 4. 代码部署

### 4.1 拉取代码

在服务器上执行：

```bash
# 创建项目目录
sudo mkdir -p /opt/iknow
sudo chown $USER:$USER /opt/iknow
cd /opt/iknow

# 克隆仓库
git clone https://github.com/Wwhqqqq/SkillsReader.git .

# 验证
ls -la
```

### 4.2 配置环境变量

```bash
cd /opt/iknow
cp .env.example .env
vim .env
```

**生产环境必改项**（注释掉旧值，填入新值）：

```ini
# ==================== 数据库 ====================
# Docker 内部用服务名 "mysql"，不是 IP 地址
DATABASE_URL=mysql+aiomysql://root:你的强密码@mysql:3306/iknow

# ==================== Redis ====================
REDIS_URL=redis://redis:6379/0

# ==================== MySQL root 密码（与 docker-compose 中一致）====================
MYSQL_ROOT_PASSWORD=你的强密码

# ==================== DeepSeek LLM ====================
DEEPSEEK_API_KEY=sk-你的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# ==================== GitHub Token（可选，提高 API 限流）====================
GITHUB_TOKEN=ghp_你的GitHubToken

# ==================== 如流推送 ====================
RULIU_AGENT_ID=你的AgentID
RULIU_APP_KEY=你的AppKey
RULIU_APP_SECRET=你的AppSecret
RULIU_DM_USER=你的如流账号

# ==================== Worker ====================
SCAN_GLOBAL_ENABLED=true
TZ=Asia/Shanghai
LOG_LEVEL=INFO

# ==================== API ====================
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://你的服务器IP,http://你的域名
```

### 4.3 启动 Docker Compose

```bash
cd /opt/iknow/deploy
docker compose -f docker-compose.prod.yml up -d --build
```

等待容器启动（约 30-60 秒），数据库需要初始化。

### 4.4 导入数据库备份

```bash
# 等待 MySQL 就绪
echo "等待 MySQL 就绪..."
for i in $(seq 1 30); do
  if docker exec iknow-mysql-1 mysqladmin ping -h localhost --silent 2>/dev/null; then
    echo "MySQL 已就绪"
    break
  fi
  sleep 2
done

# 导入数据
MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-whq050207}"
docker exec -i iknow-mysql-1 mysql -uroot -p${MYSQL_ROOT_PASSWORD} < /tmp/iknow_backup_*.sql

echo "数据导入完成"
```

### 4.5 执行数据库迁移

```bash
# 确保表结构与当前代码一致
docker exec iknow-api-1 python -m app.init_db
```

---

## 5. 一键部署脚本

将以下内容保存为 `/opt/iknow/deploy_full.sh`：

```bash
#!/usr/bin/env bash
# ============================================================
# IKnow 一键部署脚本 — 腾讯云 Ubuntu 24.04
# 使用方式: bash deploy_full.sh
# ============================================================
set -euo pipefail

ROOT="/opt/iknow"
MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-whq050207}"
BACKUP_FILE=$(ls /tmp/iknow_backup_*.sql 2>/dev/null | sort | tail -1)

echo ""
echo "========================================"
echo "  IKnow 一键部署"
echo "========================================"
echo "  项目目录 : ${ROOT}"
echo "  数据库备份: ${BACKUP_FILE:-未找到（将初始化空库）}"
echo ""

# ---------- 1. 检查 Docker ----------
echo ">>> [1/6] 检查 Docker..."
if ! command -v docker &>/dev/null; then
  echo "Docker 未安装，正在安装..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker $USER
  sudo apt install -y docker-compose-plugin
  echo ""
  echo "Docker 安装完成。请重新登录后再次运行本脚本："
  echo "  exit"
  echo "  ssh ubuntu@<服务器IP>"
  echo "  bash /opt/iknow/deploy_full.sh"
  exit 0
fi

# ---------- 2. 环境变量 ----------
echo ">>> [2/6] 检查环境变量..."
cd "${ROOT}"
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "已从 .env.example 创建 .env 文件。"
  echo "请编辑 .env 填入生产环境配置后再次运行："
  echo "  vim /opt/iknow/.env"
  exit 1
fi

# ---------- 3. 停止旧容器 ----------
echo ">>> [3/6] 停止旧容器..."
cd "${ROOT}/deploy"
docker compose -f docker-compose.prod.yml down 2>/dev/null || true

# ---------- 4. 构建并启动 ----------
echo ">>> [4/6] 构建并启动 Docker Compose..."
docker compose -f docker-compose.prod.yml up -d --build

# ---------- 5. 等待 MySQL 就绪 ----------
echo ">>> [5/6] 等待 MySQL 就绪..."
for i in $(seq 1 30); do
  if docker exec iknow-mysql-1 mysqladmin ping -h localhost --silent 2>/dev/null; then
    echo "MySQL 已就绪"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "错误: MySQL 启动超时，请检查日志"
    echo "  docker compose -f ${ROOT}/deploy/docker-compose.prod.yml logs mysql"
    exit 1
  fi
  sleep 2
done

# ---------- 6. 导入数据库 + 迁移 ----------
if [ -n "${BACKUP_FILE}" ] && [ -f "${BACKUP_FILE}" ]; then
  echo ">>> [6/6] 导入数据库: ${BACKUP_FILE}"
  docker exec -i iknow-mysql-1 mysql -uroot -p${MYSQL_ROOT_PASSWORD} < "${BACKUP_FILE}"
  echo "数据导入完成"
else
  echo ">>> [6/6] 未找到备份文件，将初始化空数据库"
fi

# 执行迁移确保表结构
echo "执行数据库迁移..."
docker exec iknow-api-1 python -m app.init_db || true

# ---------- 完成 ----------
echo ""
echo "========================================"
echo "  部署完成！"
echo "========================================"
echo ""
echo "访问地址:"
echo "  前端 : http://$(curl -s ifconfig.me 2>/dev/null || echo '<服务器IP>')"
echo "  API  : http://<服务器IP>:8000/api/health"
echo ""
echo "查看日志:"
echo "  cd ${ROOT}/deploy"
echo "  docker compose -f docker-compose.prod.yml logs -f worker"
echo "  docker compose -f docker-compose.prod.yml logs -f api"
echo ""
echo "容器状态:"
echo "  docker compose -f ${ROOT}/deploy/docker-compose.prod.yml ps"
echo ""
```

### 一键部署执行流程

```bash
# 步骤 1：从本地传输数据库备份
scp iknow_backup_*.sql ubuntu@<服务器IP>:/tmp/

# 步骤 2：首次运行（安装 Docker 后会退出）
bash /opt/iknow/deploy_full.sh

# 步骤 3：重新登录使 docker 组生效
exit
ssh ubuntu@<服务器IP>

# 步骤 4：编辑 .env 填入生产密码和 API Key
vim /opt/iknow/.env

# 步骤 5：再次运行完成部署
bash /opt/iknow/deploy_full.sh

# 步骤 6：浏览器访问 http://<服务器IP>
```

---

## 6. 验证部署

### 6.1 容器状态检查

```bash
cd /opt/iknow/deploy
docker compose -f docker-compose.prod.yml ps
```

5 个容器显示 `Up` 状态即为正常。

### 6.2 健康检查

```bash
# API 直连
curl http://127.0.0.1:8000/api/health

# 通过 Nginx
curl http://127.0.0.1/api/health

# 前端页面
curl -I http://127.0.0.1/
# 应返回 200 OK，Content-Type: text/html
```

### 6.3 Worker 日志

```bash
# 实时查看 Worker 日志
docker compose -f /opt/iknow/deploy/docker-compose.prod.yml logs -f --tail=50 worker
```

关键日志标记：
- `official_new_push` — 官方扫描发现新 Skill，已推送到如流
- `full_scan_done` — 全量扫描完成
- `digest_pick_run` — 每日精选榜单生成完成

### 6.4 手动触发扫描（验证 Worker 是否正常）

```bash
curl -X POST http://127.0.0.1:8000/api/scan/official
```

然后查看 Worker 日志，应看到 `official_new_push` 或类似的扫描记录。

---

## 7. 配置域名 + HTTPS（可选）

### 7.1 申请 SSL 证书

1. 登录腾讯云控制台 → SSL 证书 → 免费证书
2. 申请并下载 Nginx 格式证书

### 7.2 修改 Nginx 配置

需要修改 Docker 内的 Nginx 配置以支持 HTTPS。

首先创建自定义 Nginx 配置 `deploy/nginx-ssl.conf`：

```nginx
server {
    listen 80;
    server_name 你的域名;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name 你的域名;

    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://api:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://api:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

然后在 `docker-compose.prod.yml` 中修改 `frontend` 服务，挂载证书和自定义配置：

```yaml
  frontend:
    build:
      context: ..
      dockerfile: frontend/Dockerfile
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx-ssl.conf:/etc/nginx/conf.d/default.conf
      - /etc/ssl/certs:/etc/nginx/certs:ro
    depends_on:
      - api
    restart: unless-stopped
```

重建容器：

```bash
cd /opt/iknow/deploy
docker compose -f docker-compose.prod.yml up -d --build frontend
```

---

## 8. 运维常用命令

### 容器管理

```bash
cd /opt/iknow/deploy

# 查看状态
docker compose -f docker-compose.prod.yml ps

# 重启服务
docker compose -f docker-compose.prod.yml restart api
docker compose -f docker-compose.prod.yml restart worker

# 停止全部
docker compose -f docker-compose.prod.yml down

# 启动全部
docker compose -f docker-compose.prod.yml up -d

# 更新代码后重新部署
cd /opt/iknow && git pull
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

### 日志查看

```bash
# Worker 实时日志
docker compose -f /opt/iknow/deploy/docker-compose.prod.yml logs -f --tail=100 worker

# API 实时日志
docker compose -f /opt/iknow/deploy/docker-compose.prod.yml logs -f --tail=100 api

# 数据库日志
docker compose -f /opt/iknow/deploy/docker-compose.prod.yml logs mysql
```

### 手动操作

```bash
# 触发官方扫描
curl -X POST http://127.0.0.1:8000/api/scan/official

# 数据库迁移（发版后）
docker exec iknow-api-1 python -m app.init_db

# 进入容器调试
docker exec -it iknow-api-1 bash
docker exec -it iknow-mysql-1 mysql -uroot -p
```

### 数据库备份

```bash
# 手动备份
docker exec iknow-mysql-1 mysqldump -uroot -p${MYSQL_ROOT_PASSWORD} \
  --single-transaction --routines --triggers \
  --databases iknow | gzip > /tmp/iknow_$(date +%Y%m%d_%H%M).sql.gz

# 定期备份（crontab）
# 每天凌晨 3 点备份，保留最近 7 天
crontab -l > /tmp/crontab.bak 2>/dev/null
cat >> /tmp/crontab.bak << 'CRON'
0 3 * * * docker exec iknow-mysql-1 mysqldump -uroot -p密码 --single-transaction --databases iknow | gzip > /tmp/iknow_$(date +\%Y\%m\%d).sql.gz && find /tmp -name 'iknow_*.sql.gz' -mtime +7 -delete
CRON
crontab /tmp/crontab.bak
```

---

## 9. 附录

### A. 运行行为说明

| 任务 | 间隔 | 行为 |
|---|---|---|
| 官方门户扫描 | 10 分钟 | 12 家官网/API 增量拉取；有新增 → 如流单聊推送 |
| 全量扫描 | 8 小时 | 所有 enabled 源完整 fetch + 指标快照 |
| 每日精选 | 09:00 / 18:00 | 8 小时窗口评分 + 白名单加权 |

### B. 项目文件结构

```
/opt/iknow/
├── .env                   # 环境变量（生产配置）
├── .env.example           # 环境变量模板
├── config/                # YAML 配置（采集源、调度、榜单）
├── backend/               # Python FastAPI 后端
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py        # API 入口
│   │   ├── init_db.py     # 数据库初始化
│   │   ├── worker/        # 后台 Worker
│   │   ├── services/      # 业务逻辑
│   │   └── models/        # ORM 模型
│   └── tests/
├── frontend/              # Vue 3 + Naive UI 前端
│   └── Dockerfile
├── deploy/                # 部署配置
│   ├── docker-compose.prod.yml
│   ├── nginx.conf
│   ├── systemd/           # systemd 备选方案
│   └── scripts/
└── deploy_full.sh         # 一键部署脚本
```

### C. 环境变量完整清单

| 变量 | 默认值 | 必填 | 说明 |
|---|---|---|---|
| `DATABASE_URL` | — | 是 | MySQL 连接字符串 |
| `REDIS_URL` | — | 否 | Redis 连接（无则内存降级） |
| `MYSQL_ROOT_PASSWORD` | — | 是 | MySQL root 密码 |
| `DEEPSEEK_API_KEY` | — | 否 | LLM 描述补全 |
| `GITHUB_TOKEN` | — | 否 | GitHub API 限流提升 |
| `RULIU_APP_KEY` | — | 否 | 如流推送 |
| `RULIU_APP_SECRET` | — | 否 | 如流推送密钥 |
| `RULIU_AGENT_ID` | — | 否 | 如流 Bot Agent ID |
| `RULIU_DM_USER` | — | 否 | 如流单聊接收人 |
| `SCAN_GLOBAL_ENABLED` | `true` | 否 | 全局扫描开关 |
| `TZ` | `Asia/Shanghai` | 否 | 时区 |
| `CORS_ORIGINS` | `localhost` | 否 | 允许跨域来源 |

### D. 常见问题

**Q: 推送没收到？**
A: 检查 `.env` 中如流配置（`RULIU_APP_KEY`、`RULIU_APP_SECRET`、`RULIU_AGENT_ID`、`RULIU_DM_USER`），确认 Worker 日志有 `official_new_push` 输出。

**Q: 扫描没有数据？**
A: 检查 `SCAN_GLOBAL_ENABLED=true`，确认 Worker 日志无错误。可以手动触发 `curl -X POST http://127.0.0.1:8000/api/scan/official` 测试。

**Q: 更新代码后如何部署？**
A:
```bash
cd /opt/iknow
git pull
docker compose -f deploy/docker-compose.prod.yml up -d --build
docker exec iknow-api-1 python -m app.init_db   # 如有新表或迁移
```

**Q: 如何不用 Docker 部署？**
A: 参考 `deploy/systemd/` 目录下的 systemd 服务文件。需要手动安装 MySQL 8.0 + Redis，然后用 `pip install -e ".[dev]"` 安装依赖，用 systemd 管理 API 和 Worker 进程。

### E. 监控建议

1. **腾讯云云监控** — 配置 CPU / 内存 / 磁盘告警
2. **容器健康** — `docker compose -f deploy/docker-compose.prod.yml ps`，关注 `healthy` 状态
3. **Worker 日志关键词** — 监控 `official_new_push` 和 `full_scan_done` 确保扫描正常运行
4. **定时备份** — crontab + mysqldump，备份文件可上传到腾讯云 COS
