# 自媒体场景 Skills 清单

> 文档日期：2026-06-25  
> 负责人：王鹤桥  
> 数据来源：IKnow 技能库（2796 条 active）+ ClawHub / SkillsMP / GitHub 社区检索  
> 筛选方式：关键词召回 1819 条 → DeepSeek 对 Top 120 条精评 → 人工复核商用与场景匹配

---

## 一、调研结论摘要

### 1.1 与竞品对比的差异化机会

| 维度 | WorkBuddy / 扣子现状 | IKnow 库内现状 | 产品机会 |
|------|---------------------|----------------|----------|
| 覆盖环节 | 选题、排期、生成为主 | **发布/数据采集类 Skill 丰富**，创作类中等 | 串联「找题→写→发→复盘」Skill 组合包 |
| 发布能力 | 竞品几乎不涉及 | 小红书/公众号/B站/快手/视频号均有 upload/publish Skill | **生产-发布全链路**是核心差异化 |
| 平台侧重 | 公众号、小红书 | 同上 + B站/知乎/快手，抖音/微博偏弱 | 补齐抖音、微博、数据复盘类 Skill |
| 商用合规 | 部分加密不可见 | 约 61/120 精评样本可明确商用 | 优先接入 MIT/Apache/官方开放 Skill |

### 1.2 库内召回统计

| 指标 | 数量 |
|------|------|
| 库内 active Skill 总量 | 2,796 |
| 自媒体关键词召回（去重） | 1,819 |
| DeepSeek 精评样本 | 120（按 quality_score + install_count 排序） |
| 精评推荐纳入 | 75 |
| 精评明确可商用 | 61 |
| 推荐 Skill 平均适用分 | 7.6 / 10 |

### 1.3 各旅程阶段覆盖度

| 阶段 | 库内相关 Skill 数 | 商用推荐 Top Skill 数 | 覆盖评级 |
|------|------------------|----------------------|----------|
| ① 目标策略 | 少 | 1 | ⚠️ 弱 |
| ② 观察竞品 | 510 | 8 | ✅ 强 |
| ③ 捕捉素材 | 104 | 5 | ✅ 中强 |
| ④ 选题策划 | 127 | 6 | ✅ 中 |
| ⑤ 内容排期 | 少 | 2 | ⚠️ 弱 |
| ⑥ 内容制作 | 625 | 12 | ✅ 强 |
| ⑦ 拍摄设计 | 576 | 6 | ✅ 中 |
| ⑧ 内容优化 | 248 | 5 | ✅ 中 |
| ⑨ 多平台适配 | 167 | 3 | ⚠️ 弱 |
| ⑩ 发布分发 | 415 | 8 | ✅ 强 |
| ⑪ 互动承接 | 165 | 2 | ⚠️ 弱 |
| ⑫ 数据查看 | 268 | 4 | ✅ 中 |
| ⑬ 复盘分析 | 291 | 3 | ⚠️ 弱 |
| ⑭ 资产复用 | 22 | 2 | ❌ 很弱 |
| ⑮ 商业化 | 339 | 2 | ⚠️ 弱 |

**结论：** 现有 Skill 生态在「观察竞品、内容制作、发布分发」三段最成熟；「目标策略、排期、多平台适配、互动、复盘、资产复用」是明显缺口，需组合多个 Skill 或自研补齐。

---

## 二、筛选标准

### 2.1 商用许可判定

| 标记 | 含义 |
|------|------|
| ✅ 可商用 | MIT / Apache-2.0 / 官方开放 Skill / 无明确限制的开源仓库 |
| ⚠️ 待确认 | 仓库无 LICENSE 文件，或依赖付费 API 但 Skill 本身无限制 |
| ❌ 不建议商用 | Proprietary、加密不可审计、明确个人非商用、强依赖违规自动化 |

### 2.2 适用性评分（DeepSeek 1-10）

- **9-10**：自媒体核心能力，可直接作为场景默认 Skill
- **7-8**：场景可用，需配合其他 Skill 或注意平台风险
- **5-6**：边缘相关，仅作补充
- **<5**：不推荐

### 2.3 风险标签

- **R1 非官方 API / Cookie 自动化**：可能触发平台风控，建议测试号 + 低频
- **R2 付费 API 依赖**：火山/阿里/JustOneAPI 等，需预算
- **R3 版权/洗稿风险**：AI 改写类 Skill 需人工审核
- **R4 平台 ToS 违规**：批量下载/爬取类

---

## 三、推荐 Skill 组合包（可直接落地）

以下组合按「个人 IP 打造者 + 自媒体运营」画像设计，优先 **✅ 可商用** Skill。

### 3.1 公众号深度文链路

```
观察竞品 → 内容制作 → 优化 → 发布
```

| 顺序 | Skill | 阶段 | 评分 | 商用 | 安装/链接 |
|------|-------|------|------|------|-----------|
| 1 | wechat-official-account-strategist | ①④⑥⑧ | 8 | ✅ | [SkillsMP](https://skillsmp.com/creators/sickn33/antigravity-awesome-skills/skills-wechat-official-account-strategist) |
| 2 | wechat-mp-writer-skill-mxx | ④⑥⑦⑩ | 9 | ✅ | [ClawHub](https://clawhub.ai/wechat-mp-writer-skill-mxx) |
| 3 | wechat-title-generator | ⑧ | 7 | ✅ | [SkillsMP](https://skillsmp.com/creators/gainubi/wechat-skills/wechat-title-generator) |
| 4 | wechat-mp-publisher | ⑩ | 9 | ✅ | [ClawHub](https://clawhub.ai/wechat-mp-publisher) |
| 5 | WeChat MP CN | ②⑫⑬ | 8 | ✅ | [ClawHub](https://clawhub.ai/wechat-mp-cn) |

**能力说明：** 从账号策略、热点选题、AI 写作润色、标题优化到草稿箱发布，覆盖公众号主链路。监控类 Skill 辅助复盘阅读量。

### 3.2 小红书笔记链路

```
竞品研究 → 选题 → 写作 → 配图 → 发布 → 互动
```

| 顺序 | Skill | 阶段 | 评分 | 商用 | 安装/链接 |
|------|-------|------|------|------|-----------|
| 1 | xhs-content-ops | ②④⑥⑩ | 9 | ✅ | [WiseFlow/WiseFlow](https://skillsmp.com/creators/teamwiseflow/wiseflow/addons-officials-crew-selfmedia-operator-skills-xhs-content-ops) |
| 2 | xiaohongshu-ops | ④⑥⑧⑩ | 9 | ⚠️ | [ClawHub](https://clawhub.ai/xiaohongshu-ops) |
| 3 | xiaohongshu-writing | ⑥⑧ | 9 | ✅ | [ClawHub](https://clawhub.ai/xiaohongshu-writing) |
| 4 | xiaohongshu-viral-content | ⑥⑧ | 8 | ✅ | [ClawHub](https://clawhub.ai/xiaohongshu-viral-content) |
| 5 | rednote-viral-writer | ⑥ | 8 | ✅ | [ClawHub](https://clawhub.ai/rednote-viral-writer) |
| 6 | volcengine-ai-image-generation | ⑦ | 8 | ✅ | [ClawHub](https://clawhub.ai/volcengine-ai-image-generation) |
| 7 | xiaohongshu-upload | ⑩ | 7 | ✅ | [social-auto-upload](https://github.com/dreammis/social-auto-upload/tree/main/skills/xiaohongshu-upload) |
| 8 | xhs-interact | ⑪ | 7 | ✅ | [WiseFlow](https://skillsmp.com/creators/teamwiseflow/wiseflow/addons-officials-skills-xhs-interact) |

**能力说明：** WiseFlow 的 `xhs-content-ops` 是库内最接近「自媒体专家团」的全链路 Skill；配合 `xiaohongshu-writing` 做去 AI 味文案，`social-auto-upload` 做发布。

### 3.3 短视频 / 多平台分发链路

```
脚本 → 视频生成 → 字幕 → 多平台上传
```

| 顺序 | Skill | 阶段 | 评分 | 商用 | 安装/链接 |
|------|-------|------|------|------|-----------|
| 1 | video-creation-suite | ⑥⑦ | 8 | ✅ | [anbeime/skill](https://skillsmp.com/creators/anbeime/skill/skills-video-creation-suite-video-creation-suite) |
| 2 | video-creation-pro | ⑥⑦ | 8 | ✅ | [anbeime/skill](https://skillsmp.com/creators/anbeime/skill/skills-video-creation-pro-video-creation-pro) |
| 3 | volcengine-ata-subtitle | ⑦ | 7 | ✅ | [ClawHub](https://clawhub.ai/doubao-ata-subtitle) |
| 4 | Aliyun TTS | ⑥⑦ | 8 | ✅ | [ClawHub](https://clawhub.ai/aliyun-tts) |
| 5 | xiaohongshu-upload | ⑩ | 7 | ✅ | [GitHub](https://github.com/dreammis/social-auto-upload) |
| 6 | bilibili-upload | ⑩ | 7 | ✅ | [GitHub](https://github.com/dreammis/social-auto-upload/tree/main/skills/bilibili-upload) |
| 7 | kuaishou-upload | ⑩ | 7 | ✅ | [GitHub](https://github.com/dreammis/social-auto-upload/tree/main/skills/kuaishou-upload) |
| 8 | Weixin Video Publish | ⑩ | 7 | ✅ | [ClawHub](https://clawhub.ai/weixin-video-publish) |

**能力说明：** `dreammis/social-auto-upload`（12.8k⭐）是目前最成熟的多平台发布基建，覆盖抖音、小红书、视频号、B站、TikTok、YouTube。字节 `video-creation-*` 系列负责脚本到成片。

### 3.4 竞品洞察 / 找题链路

| Skill | 平台 | 阶段 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|------|
| xiaohongshu-search | 小红书 | ②④ | 7 | ⚠️ | [ClawHub](https://clawhub.ai/xiaohongshu-search) |
| xhs-explore | 小红书 | ②③ | 8 | ✅ | [SkillsMP](https://skillsmp.com/creators/autoclaw-cc/xiaohongshu-mcp-skills/skills-xhs-explore) |
| xiaohongshu-user-profile | 小红书 | ② | 7 | ⚠️ | [BrowserAct](https://skillsmp.com/creators/browser-act/skills/solutions-social-listening-xiaohongshu-user-profile) |
| zhihu-search | 知乎 | ②③ | 7 | ✅ | [GitHub](https://github.com/excalibursssooo/zhihu-search) |
| Zhihu Hot CN | 知乎 | ② | 9 | ⚠️ | [ClawHub](https://clawhub.ai/zhihu-hot-cn) |
| Bilibili Analytics | B站 | ②⑫ | 9 | ✅ | [ClawHub](https://clawhub.ai/bilibili-analytics) |
| Bilibili All In One | B站 | ②③ | 7 | ✅ | [ClawHub](https://clawhub.ai/bilibili-all-in-one) |
| wechat-article-downloader | 公众号 | ③ | 8 | ✅ | [SkillsMP](https://skillsmp.com/creators/qiye45/wechatdownload/skills-wechat-article-downloader) |
| Weixin Reader | 公众号 | ③ | 9 | ⚠️ | [ClawHub](https://clawhub.ai/weixin-reader-oc) |
| 小红书每日爆款笔记 | 小红书 | ②⑭ | 7 | ⚠️ | [ClawHub](https://clawhub.ai/xhs-daily-ranking) |

### 3.5 内容日历 / 协作 / 提醒

| Skill | 阶段 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| 腾讯文档 TENCENT DOCS | ④⑤⑥ | 8 | ✅ | [ClawHub](https://clawhub.ai/tencent-docs) |
| 腾讯文档Markdown | ⑥⑨ | 8 | ✅ | [ClawHub](https://clawhub.ai/tencent-docs-markdown) |
| xhs-content-plan | ④⑤ | 7 | ✅ | [SkillsMP](https://skillsmp.com/creators/autoclaw-cc/xiaohongshu-mcp-skills/skills-xhs-content-plan) |
| 企业微信通知提醒 | ⑤ | 7 | ✅ | [ClawHub](https://clawhub.ai/weixin-webhook) |

---

## 四、按旅程阶段的详细 Skill 清单

> 以下列出 **DeepSeek 推荐 + 商用优先** 的 Skill。完整 1819 条召回列表可通过 IKnow API `GET /api/skills?q=小红书` 等检索。

### ① 目标策略（业务目标 → 内容策略）

| Skill | 能力 | 评分 | 商用 | 来源 | 链接 | 备注 |
|-------|------|------|------|------|------|------|
| wechat-official-account-strategist | 公众号高转化内容策略：标题公式、文章架构、小程序集成 | 8 | ✅ | 腾讯/SkillsMP | [链接](https://skillsmp.com/creators/sickn33/antigravity-awesome-skills/skills-wechat-official-account-strategist) | 目前库内唯一明确的策略型 Skill |

**缺口：** 缺少跨平台的「账号定位 / 内容比例（涨粉/信任/转化）」专用 Skill，建议自研或基于 prompt 模板封装。

---

### ② 观察竞品（热点、同行、趋势）

| Skill | 能力 | 评分 | 商用 | 平台 | 链接 |
|-------|------|------|------|------|------|
| xhs-content-ops | 小红书复合运营：浏览+分析+热点追踪 | 9 | ✅ | 小红书 | [WiseFlow](https://skillsmp.com/creators/teamwiseflow/wiseflow/addons-officials-crew-selfmedia-operator-skills-xhs-content-ops) |
| Bilibili Analytics | B站视频搜索、数据统计、趋势报告 | 9 | ✅ | B站 | [ClawHub](https://clawhub.ai/bilibili-analytics) |
| WeChat MP CN | 公众号文章监控、阅读量追踪 | 8 | ✅ | 微信 | [ClawHub](https://clawhub.ai/wechat-mp-cn) |
| xhs-explore | 小红书搜索、首页浏览、笔记详情 | 8 | ✅ | 小红书 | [SkillsMP](https://skillsmp.com/creators/autoclaw-cc/xiaohongshu-mcp-skills/skills-xhs-explore) |
| B站热门视频监控 | B站热门日报 + 邮件推送 | 8 | ✅ | B站 | [ClawHub](https://clawhub.ai/bilibili-hot-monitor) |
| zhihu-search | 知乎话题/问答/用户搜索 | 7 | ✅ | 知乎 | [GitHub](https://github.com/excalibursssooo/zhihu-search) |
| Wechat Search Release | 合规搜索公众号文章 | 7 | ✅ | 微信 | [ClawHub](https://clawhub.ai/wechat-search-release) |
| Bilibili All In One | 热门监控 + 下载 + 字幕 | 7 | ✅ | B站 | [ClawHub](https://clawhub.ai/bilibili-all-in-one) |
| Xiaohongshu Search Summarizer | 小红书搜索 + AI 摘要 | 8 | ⚠️ | 小红书 | [ClawHub](https://clawhub.ai/xiaohongshu-search-summarizer) |
| maxhub-xiaohongshu | MaxHub API 小红书搜索/分析 | 7 | ⚠️ | 小红书 | [ClawHub](https://clawhub.ai/maxhub-xiaohongshu) |

**BrowserAct Social Listening 系列**（同一厂商，适合批量监控，⚠️ 依赖付费 API）：
- [xiaohongshu-search](https://clawhub.ai/justoneapi-xiaohongshu-search-note)
- [xiaohongshu-note-detail](https://clawhub.ai/justoneapi-xiaohongshu-get-note-detail)
- [xiaohongshu-user-profile](https://clawhub.ai/justoneapi-xiaohongshu-get-user)
- [weixin-search](https://clawhub.ai/justoneapi-weixin-search)

---

### ③ 捕捉素材（灵感、链接、文章归档）

| Skill | 能力 | 评分 | 商用 | 链接 | 风险 |
|-------|------|------|------|------|------|
| wechat-article-downloader | 公众号文章下载 HTML/PDF/Word/Markdown | 8 | ✅ | [SkillsMP](https://skillsmp.com/creators/qiye45/wechatdownload/skills-wechat-article-downloader) | R4 |
| Bilibili Downloader | B站视频/音频/字幕/封面下载 | 8 | ✅ | [ClawHub](https://clawhub.ai/bilibili-downloader) | R4 |
| bilibili-video-download | yutto 端到端 B站下载 | 8 | ✅ | [SkillsMP](https://skillsmp.com/creators/yutto-dev/yutto/skills-bilibili-video-download) | R4 |
| Bilibili Subtitle Downloader | BV 号字幕下载 → LLM 总结 | 7 | ✅ | [ClawHub](https://clawhub.ai/bilibili-subtitle-download-skill) | — |
| xiaohongshu-extract | 小红书分享链接元数据提取 | 7 | ⚠️ | [ClawHub](https://clawhub.ai/xiaohongshu-extract) | R1 |
| xiaohongshu-research-kit | yt-dlp + gallery-dl 小红书内容提取 | 7 | ✅ | [ClawHub](https://clawhub.ai/xiaohongshu-research-kit) | R4 |
| xiaohongshu-ingest | 笔记入库归档 | 6 | ✅ | [SkillsMP](https://skillsmp.com/creators/chubbyguan/chubbyskills/xiaohongshu-ingest) | — |

**缺口：** 缺少移动端「随手收藏/语音灵感」专用 Skill（Notion/Flomo 类接入可补）。

---

### ④ 选题策划

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| wechat-mp-writer-skill-mxx | 热点选题 + 写作 + 发布一体化 | 9 | ✅ | [ClawHub](https://clawhub.ai/wechat-mp-writer-skill-mxx) |
| xhs-content-ops | 竞品分析驱动的选题 | 9 | ✅ | [WiseFlow](https://skillsmp.com/creators/teamwiseflow/wiseflow/addons-officials-crew-selfmedia-operator-skills-xhs-content-ops) |
| xiaohongshu-ops | 定位→选题→创作→发布全流程 | 9 | ⚠️ | [ClawHub](https://clawhub.ai/xiaohongshu-ops) |
| 小红书内容创作 | CES 算法适配内容策划 | 8 | ✅ | [ClawHub](https://clawhub.ai/xhs-content-creator) |
| xhs-content-plan | 小红书内容日历/计划 | 7 | ✅ | [SkillsMP](https://skillsmp.com/creators/autoclaw-cc/xiaohongshu-mcp-skills/skills-xhs-content-plan) |
| wechat-viral-topic | 公众号爆款选题 | 7 | ✅ | [SkillsMP](https://skillsmp.com/creators/kangarooking/kangarooking-skills/viral-topic-wechat-viral-topic) |
| xiaohongshu-makeup | 美妆垂类选题+笔记 | 7 | ✅ | [SkillsMP](https://skillsmp.com/creators/anbeime/skill/skills-xiaohongshu-makeup-xiaohongshu-makeup) |

---

### ⑤ 内容排期

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| 腾讯文档 TENCENT DOCS | 内容日历/协作文档 | 8 | ✅ | [ClawHub](https://clawhub.ai/tencent-docs) |
| xhs-content-plan | 小红书排期计划 | 7 | ✅ | [SkillsMP](https://skillsmp.com/creators/autoclaw-cc/xiaohongshu-mcp-skills/skills-xhs-content-plan) |
| 企业微信通知提醒 | 定时创作/发布提醒 | 7 | ✅ | [ClawHub](https://clawhub.ai/weixin-webhook) |

**缺口：** 无原生「内容日历 + 定时发布队列」Skill，需组合腾讯文档 + 企业微信 Webhook + Cron。

---

### ⑥ 内容制作（文章/笔记/脚本/口播）

#### 6.1 小红书写作

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| xiaohongshu-writing | 爆款笔记：去 AI 味、标题公式、SEO | 9 | ✅ | [ClawHub](https://clawhub.ai/xiaohongshu-writing) |
| xiaohongshu-writer | 标题优化、emoji 策略、话题标签 | 9 | ✅ | [SkillsMP](https://skillsmp.com/creators/dongsheng123132/u-claw/portable-skills-cn-xiaohongshu-writer) |
| rednote-viral-writer | 基于 9000+ 爆款结构的快写 | 8 | ✅ | [ClawHub](https://clawhub.ai/rednote-viral-writer) |
| xiaohongshu-viral-content | 数据驱动爆款文案模板 | 8 | ✅ | [ClawHub](https://clawhub.ai/xiaohongshu-viral-content) |
| xiaohongshu-viral-writing | 五段式爆款结构模板 | 7 | ✅ | [ClawHub](https://clawhub.ai/xiaohongshu-viral-writing) |
| Auto Redbook Content | AI 自动生成小红书内容 | 7 | ⚠️ | [ClawHub](https://clawhub.ai/auto-redbook-content) |
| redbook-creator | 小红书帖子创作触发器 | 7 | ✅ | [SkillsMP](https://skillsmp.com/creators/diegosouzapw/awesome-omni-skill/skills-content-media-redbook-creator) |

#### 6.2 公众号写作

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| wechat-mp-writer-skill-mxx | 全流程写作 + 配图 + 草稿 | 9 | ✅ | [ClawHub](https://clawhub.ai/wechat-mp-writer-skill-mxx) |
| wechat-article-writer | 市场调研→大纲→AI 写作→审校 | 8 | ⚠️ | [SkillsMP](https://skillsmp.com/creators/leoyeai/openclaw-master-skills/skills-wechat-article-writer-cc) |
| wechat-content-creator | 高 eCPM 公众号文章 | 7 | ⚠️ | [SkillsMP](https://skillsmp.com/creators/dvcrn/openclaw-skills-marketplace/plugins-bbintom123321-lab-wechat-content-creator-skills-wechat-content-creator) |
| wewrite | 热点→选题→写作→排版→推送 | 9 | ⚠️ | [SkillsMP](https://skillsmp.com/creators/oaker-io/wewrite/dist-openclaw) |

#### 6.3 知乎 / 其他平台

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| zhihu-writer | 知乎回答/文章/盐选风格 | 9 | ✅ | [SkillsMP](https://skillsmp.com/creators/dongsheng123132/u-claw/portable-skills-cn-zhihu-writer) |
| Weixin WeChat Channel | 视频号文案 + 口播稿 | 8 | ✅ | [ClawHub](https://clawhub.ai/weixin-wechat-channel) |

#### 6.4 视频脚本 / 口播

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| video-creation-pro | 10 智能体协同商品视频 | 8 | ✅ | [SkillsMP](https://skillsmp.com/creators/anbeime/skill/skills-video-creation-pro-video-creation-pro) |
| video-creation-suite | 原创/二创/分析三模式 | 8 | ✅ | [SkillsMP](https://skillsmp.com/creators/anbeime/skill/skills-video-creation-suite-video-creation-suite) |
| video-recreation | 视频反推→素材→合成 | 8 | ✅ | [SkillsMP](https://skillsmp.com/creators/anbeime/skill/skills-video-recreation-video-recreation) |
| byted-kickart-viral-replicator | 爆款视频结构复刻 | 7 | ✅ | [SkillsMP](https://skillsmp.com/creators/bytedance/agentkit-samples/skills-byted-kickart-viral-replicator) |

---

### ⑦ 拍摄设计（封面/配图/字幕/视频）

| Skill | 能力 | 评分 | 商用 | 链接 | 依赖 |
|-------|------|------|------|------|------|
| volcengine-ai-image-generation | 火山引擎文生图/风格变体 | 8 | ✅ | [ClawHub](https://clawhub.ai/volcengine-ai-image-generation) | 火山 API |
| aliyun-image | 百炼图像生成/编辑/翻译 | 8 | ⚠️ | [ClawHub](https://clawhub.ai/aliyun-image) | 阿里 API |
| Aliyun TTS | 文本转语音/口播 | 8 | ✅ | [ClawHub](https://clawhub.ai/aliyun-tts) | 阿里 API |
| volcengine-ai-video-generation | 文生视频/图生视频 | 7 | ✅ | [ClawHub](https://clawhub.ai/volcengine-ai-video-generation) | 火山 API |
| volcengine-ata-subtitle | 字幕生成 + 时间轴对齐 | 7 | ✅ | [ClawHub](https://clawhub.ai/doubao-ata-subtitle) | 火山 API |
| Bilibili Auto Transcript | B站 CC/AI/Whisper 字幕 | 7 | ✅ | [ClawHub](https://clawhub.ai/bilibili-auto-transcript) | — |
| Xhs Note Creator | 笔记标题+正文+图片卡片 | 8 | ⚠️ | [ClawHub](https://clawhub.ai/auto-redbook-skills) | — |
| pw-redbook-image | 小红书配图生成 | 6 | ⚠️ | [SkillsMP](https://skillsmp.com/creators/plugins-world/pw-skills/pw-redbook-image) | — |

---

### ⑧ 内容优化（标题/平台感/风险检查）

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| xiaohongshu-title-score | 小红书标题 10 维评分 | 7 | ✅ | [SkillsMP](https://skillsmp.com/creators/redfox-data/redfox-community/skills-xiaohongshu-title-score) |
| wechat-title-generator | 公众号标题 8 种风格 | 7 | ✅ | [SkillsMP](https://skillsmp.com/creators/gainubi/wechat-skills/wechat-title-generator) |
| wechat-title | 公众号标题优化 | 7 | ✅ | [SkillsMP](https://skillsmp.com/creators/redfox-data/redfox-community/skills-wechat-title) |
| Bilibili Helper | B站标题/标签/描述优化 | 8 | ✅ | [ClawHub](https://clawhub.ai/bilibili-helper) |
| xiaohongshu-ops | 含违禁词/垂类词库审核 | 9 | ⚠️ | [GitHub](https://github.com/timandjerry/xiaohongshu-ops) |

**xiaohongshu-ops 词库亮点：** 含违禁词、AI 工具、美妆/服饰/美食/家居/母婴垂类词库，适合发布前风险检查。

---

### ⑨ 多平台适配（一稿多发）

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| 腾讯文档Markdown | Markdown 协作 → 多平台改写基础 | 8 | ✅ | [ClawHub](https://clawhub.ai/tencent-docs-markdown) |
| wechat-md-publisher | Markdown → 公众号 | 8 | ⚠️ | [SkillsMP](https://skillsmp.com/creators/leoyeai/openclaw-master-skills/skills-wechat-md-publisher-skill) |
| social-auto-upload 套件 | 同一视频 → 抖音/小红书/视频号/B站等 | 7 | ✅ | [GitHub](https://github.com/dreammis/social-auto-upload) |

**缺口：** 缺少「同一主题 → 小红书种草版 / 抖音口播版 / 公众号深度版」专用改写 Skill，目前需 LLM prompt 或自研。

---

### ⑩ 发布分发

#### 10.1 小红书

| Skill | 能力 | 评分 | 商用 | 链接 | 风险 |
|-------|------|------|------|------|------|
| xiaohongshu-upload | CLI Cookie 登录 + 图文/视频发布 | 7 | ✅ | [GitHub](https://github.com/dreammis/social-auto-upload/tree/main/skills/xiaohongshu-upload) | R1 |
| Post To Xhs | 图文/视频自动发布 | 7 | ✅ | [ClawHub](https://clawhub.ai/post-to-xhs) | R1 |
| xiaohongshu-publish | Markdown 文档渲染发布 | 7 | ✅ | [ClawHub](https://clawhub.ai/xiaohongshu-publish) | R1 |
| Fox Xiaohongshu Publish | 确认后发布 | 7 | ⚠️ | [ClawHub](https://clawhub.ai/fox-xiaohongshu-publish) | R1 |
| redbook | 浏览器自动化发布 | 8 | ⚠️ | [ClawHub](https://clawhub.ai/redbook) | R1 |

#### 10.2 微信公众号

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| wechat-mp-publisher | 官方 API 草稿发布全流程 | 9 | ✅ | [ClawHub](https://clawhub.ai/wechat-mp-publisher) |
| wechat article publisher | Markdown/URL → 排版发布 | 8 | ⚠️ | [ClawHub](https://clawhub.ai/wechat-article-publisher) |
| wechat-draft-publisher | Markdown → 草稿箱 | 7 | ✅ | [SkillsMP](https://skillsmp.com/creators/bnd-1/wechat_article_skills/wechat-draft-publisher) |
| wechat-mp-suite | 发文+用户+评论+数据+多号 | 9 | ⚠️ | [SkillsMP](https://skillsmp.com/creators/leoyeai/openclaw-master-skills/skills-wechat-mp) |

#### 10.3 其他平台

| Skill | 平台 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| bilibili-upload | B站 | 7 | ✅ | [GitHub](https://github.com/dreammis/social-auto-upload/tree/main/skills/bilibili-upload) |
| kuaishou-upload | 快手 | 7 | ✅ | [GitHub](https://github.com/dreammis/social-auto-upload/tree/main/skills/kuaishou-upload) |
| Weixin Video Publish | 视频号 | 7 | ✅ | [ClawHub](https://clawhub.ai/weixin-video-publish) |
| Zhihu Publisher | 知乎 | 7 | ⚠️ | [ClawHub](https://clawhub.ai/zhihu-publisher) |

---

### ⑪ 互动承接

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| xhs-interact | 小红书评论/回复/点赞/收藏 | 7 | ✅ | [WiseFlow](https://skillsmp.com/creators/teamwiseflow/wiseflow/addons-officials-skills-xhs-interact) |
| wechat-auto-reply | 公众号自动回复 | 6 | ⚠️ | [ClawHub](https://clawhub.ai/wechat-auto-reply) |
| redbook-feedback-analyzer | 小红书评论反馈分析 → 选题 | 7 | ⚠️ | [ClawHub](https://clawhub.ai/xhs-feedback-analyzer) |

**缺口：** 无私信线索识别、跨平台评论聚合 Skill。

---

### ⑫ 数据查看

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| Bilibili Analytics | B站视频数据报告 | 9 | ✅ | [ClawHub](https://clawhub.ai/bilibili-analytics) |
| WeChat MP CN | 公众号阅读量监控 | 8 | ✅ | [ClawHub](https://clawhub.ai/wechat-mp-cn) |
| justoneapi-weixin-get-article-feedback | 公众号互动指标 API | 7 | ⚠️ | [ClawHub](https://clawhub.ai/justoneapi-weixin-get-article-feedback) |
| Socialdatax Kuaishou 系列 | 快手创作者数据 | 7 | ⚠️ | [ClawHub](https://clawhub.ai/socialdatax-kuaishou) |
| maxhub-wechat | MaxHub 公众号数据 | 7 | ⚠️ | [ClawHub](https://clawhub.ai/maxhub-wechat) |

**缺口：** 无跨平台统一看板 Skill，需自研聚合层或手动录入。

---

### ⑬ 复盘分析

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| Xiaohongshu Search Summarizer | 搜索 + AI 摘要复盘 | 8 | ⚠️ | [ClawHub](https://clawhub.ai/xiaohongshu-search-summarizer) |
| bilibili-subtitle-analysis | B站字幕 → 内容分析 | 7 | ✅ | [ClawHub](https://clawhub.ai/bilibili-subtitle-analysis) |
| xiaohongshu-viral-analyzer | 爆款笔记结构分析 | 7 | ⚠️ | [SkillsMP](https://skillsmp.com/creators/cyhzzz/finance_aigc_skills/xiaohongshu-creation-workflow-skills-xiaohongshu-viral-analyzer) |
| redbook-feedback-analyzer | 评论反馈 → 优化建议 | 7 | ⚠️ | [ClawHub](https://clawhub.ai/xhs-feedback-analyzer) |

**缺口：** 无「发布后 24h/72h 自动复盘提醒 + 优化建议」专用 Skill。

---

### ⑭ 资产复用

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| 小红书每日爆款笔记 | 爆款笔记库 | 7 | ⚠️ | [ClawHub](https://clawhub.ai/xhs-daily-ranking) |
| xiaohongshu-ingest | 笔记入库 | 6 | ✅ | [SkillsMP](https://skillsmp.com/creators/chubbyguan/chubbyskills/xiaohongshu-ingest) |
| video-recreation | 旧视频二创翻新 | 8 | ✅ | [SkillsMP](https://skillsmp.com/creators/anbeime/skill/skills-video-recreation-video-recreation) |
| bilibili-cc-to-notion | B站字幕 → Notion 笔记 | 7 | ⚠️ | [ClawHub](https://clawhub.ai/bilibili-cc-to-notion) |

**缺口：** 库内仅 22 条相关 Skill，是整个旅程最大短板。

---

### ⑮ 商业化

| Skill | 能力 | 评分 | 商用 | 链接 |
|-------|------|------|------|------|
| xiaohongshu-ad-ops | 小红书广告投放工作流 | 7 | ⚠️ | [ClawHub](https://clawhub.ai/xiaohongshu-ad-ops) |
| redbook-daihuo | 小红书带货笔记 | 7 | ⚠️ | [ClawHub](https://clawhub.ai/redbook-daihuo) |
| wechat-official-account-strategist | 转化路径/小程序 | 8 | ✅ | [SkillsMP](https://skillsmp.com/creators/sickn33/antigravity-awesome-skills/skills-wechat-official-account-strategist) |

---

## 五、网外补充 Skill（建议纳入采集）

以下来自 GitHub / 社区推荐，**部分尚未入库或入库不完整**，建议加入 IKnow 监控源。

| 仓库 / Skill | 平台 | 许可 | 阶段 | 链接 |
|-------------|------|------|------|------|
| dreammis/social-auto-upload | 抖音/小红书/视频号/B站/YouTube | ⚠️ 无 LICENSE 文件 | ⑩ | [GitHub](https://github.com/dreammis/social-auto-upload) |
| teamwiseflow/wiseflow (selfmedia-operator) | 小红书全链路 | 待确认 | ②④⑥⑩ | [GitHub](https://github.com/TeamWiseFlow/WiseFlow) |
| timandjerry/xiaohongshu-ops | 小红书运营+词库 | 待确认 | ④⑥⑧ | [GitHub](https://github.com/timandjerry/xiaohongshu-ops) |
| leoyeai/openclaw-master-skills | 微信/小红书套件 | 待确认 | ⑥⑩ | [GitHub](https://github.com/leoyeai/openclaw-master-skills) |
| WebJeffery/media-creator-skills | 微信/小红书分阶段 | 待确认 | ④⑥ | 社区推荐 |
| anthonyhann/xhs-workflow-skill | 小红书全流程 | 待确认 | ②④⑥⑩ | 社区推荐 |
| mythkiven/rednote-director-skill | 小红书视觉/轮播 | 待确认 | ⑦ | 社区推荐 |
| dongsheng123132/u-claw portable-skills-cn | 小红书/知乎 writer | 待确认 | ⑥ | [SkillsMP](https://skillsmp.com/creators/dongsheng123132/u-claw) |
| anbeime/skill (video-creation-*) | 视频创作/二创 | 待确认 | ⑥⑦ | [SkillsMP](https://skillsmp.com/creators/anbeime/skill) |
| excalibursssooo/zhihu-search | 知乎搜索 | 待确认 | ② | [GitHub](https://github.com/excalibursssooo/zhihu-search) |

---

## 六、与 Dumate / 扣子技能包对照

| 扣子/WorkBuddy 能力 | 库内对应 Skill | 差距 |
|--------------------|---------------|------|
| 爆款选题 | xhs-content-ops + zhihu-search + wechat-viral-topic | ✅ 可覆盖 |
| 公众号 10w+ 文章 | wechat-mp-writer-skill-mxx + wechat-official-account-strategist | ✅ 可覆盖 |
| 小红书种草笔记 | xiaohongshu-writing + xiaohongshu-viral-content | ✅ 可覆盖 |
| 全域内容分发 | social-auto-upload 套件 | ✅ 可覆盖，但缺抖音独立 Skill 入库 |
| 内容日历/排期 | xhs-content-plan + 腾讯文档 | ⚠️ 需组合，无一体化 |
| 发布后复盘 | redbook-feedback-analyzer 等 | ⚠️ 弱 |
| 多平台改写 | 无专用 Skill | ❌ 需自研 |
| 图片/音视频生成 | volcengine-ai-* + aliyun-* + video-creation-* | ✅ Dumate 可复用 |

---

## 七、落地建议

### 7.1 MVP Skill 包（10 个，优先接入）

1. **xhs-content-ops** — 小红书全链路运营  
2. **wechat-mp-writer-skill-mxx** — 公众号写作发布  
3. **xiaohongshu-writing** — 小红书爆款文案  
4. **social-auto-upload**（xiaohongshu/bilibili/kuaishou upload）— 多平台发布  
5. **wechat-mp-publisher** — 公众号官方 API 发布  
6. **volcengine-ai-image-generation** — 配图  
7. **video-creation-suite** — 短视频脚本/成片  
8. **Bilibili Analytics** — B站竞品分析  
9. **zhihu-writer** — 知乎内容  
10. **腾讯文档 TENCENT DOCS** — 内容日历协作  

### 7.2 需自研/补采的 Skill（6 项）

| 优先级 | 缺失能力 | 建议方案 |
|--------|---------|---------|
| P0 | 多平台一稿多发改写 | 封装 LLM prompt Skill：`content-platform-adapter` |
| P0 | 内容日历 + 定时提醒 | 组合腾讯文档 + 企业微信 Webhook + Cron |
| P1 | 跨平台数据看板 | 聚合 JustOneAPI / MaxHub + 手动录入 |
| P1 | 发布后 24h/72h 复盘 | 定时任务 + LLM 分析 Skill |
| P2 | 移动端灵感采集 | Flomo/Notion Webhook Skill |
| P2 | 内容资产库/爆款翻新 | 基于 xiaohongshu-ingest 扩展 |

### 7.3 MCP 发布能力调研（待办交叉）

| 平台 | MCP/Skill 发布现状 | 结论 |
|------|-------------------|------|
| 小红书 | xiaohongshu-upload / MCP login 多个 Skill | ✅ Skill 可用，非官方 MCP |
| 微信公众号 | wechat-mp-publisher 官方 API | ✅ 推荐官方 API 路径 |
| 企业微信 | wecomcli-* / 企业微信 Webhook | ✅ 通知/文档，非内容发布 |
| 微博 | 库内无专用 publish Skill | ❌ 缺口 |
| 抖音 | social-auto-upload 含抖音 | ⚠️ Cookie 自动化，无官方 MCP |

---

## 八、附录

### A. 检索关键词

```
小红书, 公众号, 微信, 自媒体, 选题, 内容, 短视频, 视频号,
抖音, 微博, 知乎, B站, xiaohongshu, rednote, wechat, douyin,
content, social, copywrit, publish, viral, script, title, kol,
creator, media, article, writer, comment, analytics, calendar
```

### B. DeepSeek 精评 Prompt 模板

```
对用户旅程 15 阶段，评估 Skill 的 stages / primary_stage / commercial_ok /
apply_score / risk / recommend，输出 JSON 数组。
```

### C. IKnow API 查询示例

```bash
# 小红书相关
curl "http://localhost:8000/api/skills?q=小红书&page_size=50"

# 导出 CSV
curl "http://localhost:8000/api/skills/export?format=csv&q=wechat" -o wechat_skills.csv
```

### D. 相关文档

- [SKILL_SOURCES.md](./SKILL_SOURCES.md) — 各厂商 Skill 采集来源
- [TODO_BACKLOG.md](./TODO_BACKLOG.md) — 产品待办

---

*本文档由 IKnow 技能库自动召回 + DeepSeek API 精评生成，商用许可以各 Skill 原始 LICENSE 为准，接入前请人工复核。*
