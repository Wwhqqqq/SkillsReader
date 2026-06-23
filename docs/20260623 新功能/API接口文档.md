# 每日精选 Top N — API 接口文档

> 模块路径：`backend/app/services/digest/`  
> 配置文件：`config/digest_pick.yaml`  
> 路由前缀：`/api/digest`

## 1. 业务概述

每日从 GitHub / SkillsMP / ClawHub / skills.sh 等源批量采集 Skill，经标准化、去重、四池筛选、多维评分后，生成结构化 **Top 10 精选**并推送。

| 核心能力 | 说明 |
|---------|------|
| 超级公司官方发现 | 优先推荐大厂 **官方发布** Skill（权重高于个人开发者） |
| 短期爆发发现 | 基于 1d / 3d / 7d 指标增长率识别趋势 Skill |
| 结构化推荐 | 槽位 1–3 官方 / 4–7 趋势 / 8–10 发现（可配置） |
| 可扩展配置 | 池子阈值、评分权重、推送时间均在 YAML 中可调 |

---

## 2. 数据流

```mermaid
flowchart LR
  A[多源采集] --> B[标准化入库]
  B --> C[指纹去重]
  C --> D[指标日快照]
  D --> E[四池候选]
  E --> F[多维评分]
  F --> G[结构化 Top N]
  G --> H[Markdown 推送]
```

---

## 3. 配置字段（`config/digest_pick.yaml`）

### 3.1 顶层

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `version` | string | 是 | 配置版本号，写入 `DigestPickRun.config_version` |
| `schedule` | object | 否 | 默认定时推送 schedule |
| `selection` | object | 是 | 选取数量、槽位、多样性 |
| `pools` | object | 是 | 四池入池条件 |
| `scoring` | object | 是 | 评分权重与增长窗口 |
| `push` | object | 否 | Markdown 标题与展示开关 |

### 3.2 `schedule`

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `times` | string[] | `["09:00","18:00"]` | 上海时区推送时刻（可被 Redis/API 覆盖） |
| `timezone` | string | `Asia/Shanghai` | 时区 |

### 3.3 `selection`

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `default_top_n` | int | 10 | 默认精选数量 |
| `candidate_pool_limit` | int | 800 | 候选池 DB 查询上限 |
| `quality_threshold` | int | 40 | 最低质量分 |
| `slots.official.count` | int | 3 | 官方槽位数 |
| `slots.trend.count` | int | 4 | 趋势槽位数 |
| `slots.discovery.count` | int | 3 | 发现槽位数 |
| `diversity.max_per_vendor` | int | 2 | 同一厂商最多入选数 |
| `diversity.max_per_platform` | int | 4 | 同一 source_id 最多入选数 |

### 3.4 `pools`

| 池子 | 关键字段 | 说明 |
|------|----------|------|
| `official` | `min_quality` | 官方发布 + 超级公司相关 |
| `popularity` | `min_install`, `min_quality` | 高安装/Star |
| `trend` | `min_trend_velocity` | Z-Score 趋势速度阈值 |
| `discovery` | `max_age_days`, `min_quality`, `min_description_len` | 新近高质量 |
| `domestic_vendors` | string[] | 超级公司名单 |
| `entry` | `min_install`, `github_stars_baseline` | §4.4 入池硬条件 |

### 3.5 `scoring`（v2 — 对齐功能开发文档 §5.2 / §7.1）

**最终排序 `scoring.final_weights`（§7.1 FinalScore）**

| 维度 | 字段 | 默认 | 说明 |
|------|------|------|------|
| 趋势 | `trend` | 0.35 | Log+Z-Score 跨平台增速 + log(install) |
| 官方 | `official` | 0.30 | 官方发布 / metadata.official / 超级公司 |
| 质量 | `quality` | 0.20 | 描述/标签/SKILL.md 结构/filter 强度 |
| 多样性 | `diversity` | 0.15 | `1 - platform_count_ratio` 防刷屏 |

**趋势速度子权重 `scoring.velocity_weights`（§5.2）**

| 字段 | 默认 | 说明 |
|------|------|------|
| `z_1d` | 0.40 | 1 日 Z-Score |
| `z_3d` | 0.30 | 3 日 Z-Score |
| `z_7d` | 0.30 | 7 日 Z-Score |

**源权重 `scoring.source_weights`**

| source_id | 默认 | 说明 |
|-----------|------|------|
| `skills_sh` | 1.0 | 趋势雷达源 |
| `github_watch` | 0.9 | GitHub 补充 |
| `default` | 0.8 | 其他源 |

---

## 4. REST API

### 4.1 GET `/api/digest/config`

返回完整 YAML 配置 + 当前 schedule（含 Redis 覆盖）。

**响应 `DigestConfigResponse`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `version` | string | 配置版本 |
| `config` | object | 完整 digest_pick.yaml 解析结果 |
| `schedule` | DigestScheduleSettings | 当前生效 schedule |

**`schedule` 子字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled` | bool | 是否启用定时推送 Worker |
| `times` | string[] | `HH:MM` 列表 |
| `timezone` | string | 时区 |
| `target` | string | `dm` \| `group` |
| `top_n` | int | 定时推送数量 |

---

### 4.2 GET/PUT `/api/digest/schedule`

读写 Redis 中的 schedule 覆盖（不改 YAML 文件）。

---

### 4.3 POST `/api/digest/preview`

实时计算精选，**不持久化**。

**请求 `DigestPreviewRequest`**

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `date` | string? | 今日 | ISO 日期 `YYYY-MM-DD` |
| `top_n` | int | 10 | 精选数量 |
| `vendors` | string[] | [] | 限定厂商；空=全量 |

**响应 `DigestPreviewResponse`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `digest_date` | date | 精选日期 |
| `top_n` | int | 数量 |
| `items` | DigestPickItemOut[] | 精选列表 |
| `content_md` | string | 如流 Markdown 全文 |
| `char_count` | int | 字符数 |
| `config_version` | string | 配置版本 |
| `meta` | object | 候选数、池分布等 |
| `needs_split` | bool | 是否超过 2048 字需拆分 |

**`DigestPickItemOut` 字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `rank` | int | 排名 1..N |
| `slot` | string | `official` \| `trend` \| `discovery` \| `fill` |
| `pool` | string | 主池：`official` / `trend` / `discovery` / `popularity` |
| `skill` | SkillOut | Skill 详情（见下） |
| `score` | float | 综合分 |
| `score_breakdown` | ScoreBreakdownOut | 四维得分 |
| `growth` | GrowthMetricsOut | 增长指标 |
| `recommend_reason` | string | 人类可读推荐理由 |
| `is_official` | bool | 是否官方发布 |
| `is_new` | bool | 是否 1 日内新发现 |

**`ScoreBreakdownOut`（v2）**

| 字段 | 类型 | 说明 |
|------|------|------|
| `trend` | float | 趋势维度 0–100 |
| `official` | float | 官方维度 0–100 |
| `quality` | float | 质量维度 0–100 |
| `diversity` | float | 源多样性维度 0–100 |
| `total` | float | 加权综合分 |

**`GrowthMetricsOut`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `metric_value` | int | 当前统一指标值（多为 install_count） |
| `metric_kind` | string | `install` \| `stars` \| `views` |
| `value_1d_ago` | int? | 1 日前快照 |
| `value_3d_ago` | int? | 3 日前 |
| `value_7d_ago` | int? | 7 日前 |
| `growth_1d_pct` | float | 1 日增长率 % |
| `growth_3d_pct` | float | 3 日增长率 % |
| `growth_7d_pct` | float | 7 日增长率 % |
| `log_growth_1d/3d/7d` | float | log(1+growth_rate) 压缩值 |
| `z_1d/3d/7d` | float | 平台内 Z-Score |
| `trend_velocity_score` | float | 加权 Z-Score 趋势分 0–100 |
| `growth_score` | float | 兼容字段，同 trend_velocity_score |

**`SkillOut`（节选）**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 主键 |
| `vendor` | string | 厂商/公司 |
| `source_id` | string | 采集源 ID |
| `name` | string | Skill 名称 |
| `install_count` | int | 安装/Star 代理值 |
| `quality_score` | int | 0–100 |
| `detail_url` | string? | 详情链接 |
| `first_seen_at` | datetime | 首次入库 |

---

### 4.4 POST `/api/digest/generate`

同 preview，并写入 `digest_pick_runs` 表。

**响应**

| 字段 | 类型 | 说明 |
|------|------|------|
| `run_id` | int | 生成记录 ID |
| `digest_date` | date | 日期 |
| `top_n` | int | 数量 |
| `skill_count` | int | 实际入选数 |
| `config_version` | string | 配置版本 |

---

### 4.5 GET `/api/digest/picks`

| Query | 类型 | 说明 |
|-------|------|------|
| `date` | string? | ISO 日期 |
| `top_n` | int | 默认 10 |
| `regenerate` | bool | true 时强制重算 |

优先返回该日最新 `DigestPickRun` 缓存；无缓存或 `regenerate=true` 时实时计算。

---

### 4.6 POST `/api/digest/push`

生成精选并推送到如流。

**请求 `DigestSendRequest`**

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `date` | string? | 今日 | 精选日期 |
| `top_n` | int | 10 | 数量 |
| `vendors` | string[] | [] | 厂商过滤 |
| `dry_run` | bool | false | 仅预览不发送 |
| `target` | string | `dm` | `dm` \| `group` |

**响应 `DigestSendResponse`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 是否成功 |
| `message` | string | 结果说明 |
| `push_log_id` | int? | push_logs 记录 |
| `digest_run_id` | int? | digest_pick_runs 记录 |
| `content_md` | string? | 推送正文 |

---

### 4.7 GET `/api/digest/history`

| Query | 类型 | 默认 | 说明 |
|-------|------|------|------|
| `limit` | int | 30 | 条数 |

返回最近生成/推送记录摘要。

---

## 5. 数据库表

### 5.1 `skill_metric_snapshots`

| 列 | 类型 | 说明 |
|----|------|------|
| `skill_id` | bigint | FK → skills.id |
| `snapshot_date` | date | 快照日 |
| `metric_value` | int | 当日最大指标 |
| `metric_kind` | varchar | install/stars/views |
| `source_id` | varchar | 来源 |

唯一索引：`(skill_id, snapshot_date)`。每次 scan 入库后 upsert。

### 5.2 `digest_pick_runs`

| 列 | 类型 | 说明 |
|----|------|------|
| `digest_date` | date | 精选日 |
| `top_n` | int | N |
| `picks` | json | `DigestPickItem.to_dict()` 数组 |
| `content_md` | text | Markdown |
| `config_version` | varchar | 配置版本 |
| `selection_meta` | json | 候选数、池分布 |
| `push_status` | varchar | pending/sent/failed/dry_run |
| `pushed_at` | datetime? | 推送时间 |

---

## 6. Worker

```bash
cd backend && python -m app.worker.digest_loop
```

每 30 秒检查 schedule；命中时刻且当日未推送则自动 `select_daily_picks` + `send_digest`。

---

## 7. 扩展指南

| 需求 | 修改位置 |
|------|----------|
| 新增超级公司 | `pools.domestic_vendors` |
| 调整 Top N 槽位 | `selection.slots.*.count` |
| 修改评分权重 | `scoring.weights` |
| 调整趋势阈值 | `pools.trend.min_growth_*` |
| 新平台 metric 映射 | `scoring.metric_sources.{source_id}` |
| 自定义推荐理由 | `services/digest/reasons.py` |
| 新候选池 | `pools.py` + `selector.py` + yaml |

修改 YAML 后 API `/api/digest/config` 即时生效（`load_digest_config(reload=True)` 可用于热加载）。

---

## 8. 与现有模块关系

| 模块 | 关系 |
|------|------|
| `services/scan/pipeline.py` | 入库后写入 metric snapshot |
| `services/push/ruliu_notifier.py` | digest 复用 Markdown 表格样式；scan 自动推送仍用 today 模式 |
| `adapters/*` | 多源采集；去重沿用 `record_dedup` |
