#!/usr/bin/env bash
# ================================================================
# IKnow 腾讯云 Lighthouse 部署脚本
# 服务器: lhins-236pfmiq / 上海 / Ubuntu 24.04 / IP: 111.229.87.157
# 使用方式: bash deploy_server.sh
# ================================================================
set -euo pipefail

# ---------- 可配置项 ----------
MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-Whq050207!}"
DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
RULIU_AGENT_ID="${RULIU_AGENT_ID:-}"
RULIU_APP_KEY="${RULIU_APP_KEY:-}"
RULIU_APP_SECRET="${RULIU_APP_SECRET:-}"
RULIU_DM_USER="${RULIU_DM_USER:-wangheqiao}"

# 项目目录
ROOT="/opt/iknow"
# 数据库备份文件路径（压缩包）
BACKUP_GZ=$(ls /tmp/iknow_backup_*.sql.gz 2>/dev/null | sort | tail -1)
# 补全参数后置 flag
NEED_ENV_CONFIG="${NEED_ENV_CONFIG:-0}"

# ---------- 颜色输出 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

echo ""
echo "================================================"
echo "  IKnow 腾讯云 Lighthouse 部署"
echo "================================================"
echo "  服务器 IP : 111.229.87.157"
echo "  项目目录  : ${ROOT}"
echo "  数据库备份: ${BACKUP_GZ:-未找到}"
echo ""

# ============================================
# Step 1 — 拉取代码
# ============================================
log_info "Step 1/6: 拉取代码..."

if [ -d "${ROOT}/.git" ]; then
  log_info "项目已存在，执行 git pull..."
  cd "${ROOT}"
  git fetch origin
  git reset --hard origin/main
  log_info "代码更新完成"
else
  log_info "首次部署，克隆仓库..."
  sudo mkdir -p "${ROOT}"
  sudo chown $USER:$USER "${ROOT}"
  git clone https://github.com/Wwhqqqq/SkillsReader.git "${ROOT}"
  log_info "代码克隆完成"
fi

cd "${ROOT}"

# ============================================
# Step 2 — 环境变量
# ============================================
log_info "Step 2/6: 配置环境变量..."

if [ ! -f .env ]; then
  cp .env.example .env
  log_info "已从 .env.example 创建 .env"
fi

# 写入生产环境配置
cat > .env << ENVEOF
# ==================== 数据库 (Docker 内部服务名) ====================
DATABASE_URL=mysql+aiomysql://root:${MYSQL_ROOT_PASSWORD}@mysql:3306/iknow

# ==================== Redis ====================
REDIS_URL=redis://redis:6379/0

# ==================== MySQL 密码 ====================
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}

# ==================== DeepSeek LLM ====================
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# ==================== GitHub Token ====================
GITHUB_TOKEN=${GITHUB_TOKEN}

# ==================== 自动推送 ====================
AUTO_PUSH_MODE=dm
AUTO_PUSH_MAX_ITEMS=15

# ==================== 如流推送 ====================
RULIU_AGENT_ID=${RULIU_AGENT_ID}
RULIU_APP_KEY=${RULIU_APP_KEY}
RULIU_APP_SECRET=${RULIU_APP_SECRET}
RULIU_API_BASE=https://apiin.im.baidu.com/api/v1
RULIU_GROUP_ID=13038971
RULIU_ALLOW_GROUP=true
RULIU_NOTIFY_TARGET=dm
RULIU_DM_USER=${RULIU_DM_USER}
RULIU_CALLBACK_TOKEN=
RULIU_CALLBACK_AES_KEY=

# ==================== Worker ====================
SCAN_GLOBAL_ENABLED=true
TZ=Asia/Shanghai
LOG_LEVEL=INFO

# ==================== API ====================
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://111.229.87.157,http://localhost:5173
ENVEOF

log_info ".env 配置完成"

# 检查密钥是否已填
MISSING=()
[ -z "${DEEPSEEK_API_KEY}" ] && MISSING+=("DEEPSEEK_API_KEY")
[ -z "${RULIU_APP_KEY}" ]   && MISSING+=("RULIU_APP_KEY")
[ -z "${RULIU_APP_SECRET}"  ] && MISSING+=("RULIU_APP_SECRET")

if [ ${#MISSING[@]} -gt 0 ]; then
  log_warn "以下密钥未填写，对应功能不可用:"
  for k in "${MISSING[@]}"; do
    echo "        - ${k}"
  done
  echo ""
  echo "   如需填写，请编辑 ${ROOT}/.env 后重新运行本脚本"
  echo ""
else
  log_info "所有密钥已配置"
fi

# ============================================
# Step 3 — 停止旧容器
# ============================================
log_info "Step 3/6: 停止旧容器..."
cd "${ROOT}/deploy"
docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true

# ============================================
# Step 4 — 构建并启动
# ============================================
log_info "Step 4/6: 构建镜像并启动服务..."
docker compose -f docker-compose.prod.yml up -d --build

# ============================================
# Step 5 — 等待 MySQL 就绪 → 导入数据
# ============================================
log_info "Step 5/6: 等待 MySQL 就绪..."
for i in $(seq 1 30); do
  if docker exec iknow-mysql-1 mysqladmin ping -h localhost --silent 2>/dev/null; then
    log_info "MySQL 已就绪"
    break
  fi
  if [ "$i" -eq 30 ]; then
    log_error "MySQL 启动超时"
    echo "请检查日志: docker compose -f ${ROOT}/deploy/docker-compose.prod.yml logs mysql"
    exit 1
  fi
  sleep 2
done

# 导入数据库备份
if [ -n "${BACKUP_GZ}" ] && [ -f "${BACKUP_GZ}" ]; then
  log_info "发现数据库备份: ${BACKUP_GZ}"
  log_info "正在解压并导入..."
  gunzip -c "${BACKUP_GZ}" | docker exec -i iknow-mysql-1 mysql -uroot -p${MYSQL_ROOT_PASSWORD}
  log_info "数据库导入完成"
else
  log_warn "未找到数据库备份文件，将初始化空数据库"
  log_warn "如需导入数据，请手动执行:"
  echo "  gunzip -c /tmp/iknow_backup_*.sql.gz | docker exec -i iknow-mysql-1 mysql -uroot -p${MYSQL_ROOT_PASSWORD}"
fi

# ============================================
# Step 6 — 数据库迁移
# ============================================
log_info "Step 6/6: 执行数据库迁移..."
sleep 5  # 等 API 容器完全就绪
docker exec iknow-api-1 python -m app.init_db 2>/dev/null || {
  log_warn "首次迁移可能因数据库尚未初始化，等待 10 秒后重试..."
  sleep 10
  docker exec iknow-api-1 python -m app.init_db
}
log_info "数据库迁移完成"

# ============================================
# 验证
# ============================================
echo ""
echo "================================================"
echo "  部署完成！"
echo "================================================"
echo ""
echo "  ✅ 前端 : http://111.229.87.157"
echo "  ✅ API  : http://111.229.87.157:8000/api/health"
echo ""
echo "  健康检查:"
curl -s http://127.0.0.1:8000/api/health 2>/dev/null && echo "" || echo "  (等待 API 就绪...)"
curl -s -o /dev/null -w "  前端 HTTP %{http_code}\n" http://127.0.0.1/ 2>/dev/null || echo "  (等待前端就绪...)"
echo ""
echo "  查看日志:"
echo "    docker compose -f ${ROOT}/deploy/docker-compose.prod.yml logs -f worker"
echo "    docker compose -f ${ROOT}/deploy/docker-compose.prod.yml logs -f api"
echo ""
echo "  容器状态:"
docker compose -f "${ROOT}/deploy/docker-compose.prod.yml" ps
echo ""
