<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { NButton, NSwitch, NTag, useMessage } from 'naive-ui'
import { api, downloadSkillsBundle, downloadSkillsExport } from '../api/client'

const message = useMessage()
const stats = ref<any>(null)
const vendorStats = ref<any>(null)
const sources = ref<any[]>([])
const recentEvents = ref<any[]>([])
const exportVendor = ref<string>('')
const officialScan = ref<any>(null)
const officialScanLoading = ref(false)
const officialPortals = ref<any[]>([])
let timer: number

async function loadOfficialScanStatus() {
  try {
    officialScan.value = await api.officialScanStatus()
  } catch {
    /* ignore */
  }
}

async function loadOfficialPortals() {
  try {
    officialPortals.value = await api.officialScanPortals()
  } catch {
    /* ignore */
  }
}

async function load() {
  try {
    ;[stats.value, vendorStats.value, sources.value, recentEvents.value] = await Promise.all([
      api.overview(),
      api.vendorStats(),
      api.sources(),
      api.scanEvents(10),
    ])
    await loadOfficialScanStatus()
  } catch (e: any) {
    message.error(e.message)
  }
}

onMounted(() => {
  load()
  loadOfficialPortals()
  timer = window.setInterval(load, 15000)
})
onUnmounted(() => clearInterval(timer))

function statusColor(s: string) {
  if (s === 'ok') return 'success'
  if (s === 'error') return 'error'
  if (s === 'scanning') return 'warning'
  return 'default'
}

function exportSkills(format: 'csv' | 'xlsx', todayOnly: boolean) {
  downloadSkillsExport({
    format,
    vendor: exportVendor.value || undefined,
    today_only: todayOnly,
  })
  const scope = exportVendor.value || '全部公司'
  message.success(`正在下载${scope}${todayOnly ? '今日新增' : '全量'} ${format.toUpperCase()}`)
}

function exportRecentDiscoveries(format: 'csv' | 'xlsx') {
  downloadSkillsExport({
    format,
    vendor: exportVendor.value || undefined,
    recent_only: true,
  })
  const scope = exportVendor.value || '全部公司'
  message.success(`正在下载${scope}近24小时新发现 ${format.toUpperCase()}`)
}

async function runOfficialScan() {
  if (officialScanLoading.value || officialScan.value?.status === 'running') return
  officialScanLoading.value = true
  try {
    const res = await api.triggerOfficialScan()
    if (res.status === 'running') {
      message.warning('官方扫描进行中，请稍候')
      officialScanLoading.value = false
      return
    }
    message.info('已开始官方一键扫描，完成后可导出新增')
    officialScan.value = { ...officialScan.value, status: 'running' }
    const poll = window.setInterval(async () => {
      await loadOfficialScanStatus()
      if (officialScan.value?.status !== 'running') {
        window.clearInterval(poll)
        officialScanLoading.value = false
        await load()
        if (officialScan.value?.status === 'done') {
          const pushHint =
            officialScan.value.push_status === 'sent'
              ? '，已推送官方新增'
              : ''
          message.success(
            `官方门户扫描完成：新增官方 ${officialScan.value.new_official_count ?? 0} 条${pushHint}`
          )
        }
      }
    }, 5000)
  } catch (e: any) {
    officialScanLoading.value = false
    message.error(e.message)
  }
}

function exportLastOfficialScan(format: 'csv' | 'xlsx') {
  downloadSkillsExport({
    format,
    vendor: exportVendor.value || undefined,
    last_official_scan: true,
  })
  const scope = exportVendor.value || '全部公司'
  message.success(`正在下载${scope}最近官方扫描新增 ${format.toUpperCase()}`)
}

function officialScanStatusText() {
  const s = officialScan.value
  if (!s || s.status === 'idle') return '尚未执行官方门户扫描'
  if (s.status === 'running') return '官方门户扫描进行中…'
  if (s.status === 'error') return `上次扫描失败：${s.error_message || '未知错误'}`
  const t = s.finished_at?.slice(0, 19)?.replace('T', ' ') || '--'
  const push =
    s.push_status === 'sent' ? ' · 已推送' : s.push_status === 'failed' ? ' · 推送失败' : ''
  return `上次官方门户扫描 ${t} · 新增官方 ${s.new_official_count ?? 0} 条${push}`
}

function exportBundle(todayOnly: boolean) {
  downloadSkillsBundle({ today_only: todayOnly, scope: 'domestic' })
  message.success(
    todayOnly
      ? '正在最新下载：国内各公司今日新增 CSV（每公司一个文件）'
      : '正在全部下载：国内各公司全量 CSV（每公司一个文件）'
  )
}

function exportRecentDiscoveriesBundle() {
  downloadSkillsBundle({ recent_only: true, scope: 'domestic' })
  message.success('正在下载：国内各公司近24小时新发现 CSV 打包')
}

const exportableVendors = () => vendorStats.value?.vendors || []
</script>

<template>
  <div class="page">
    <div class="page-title">总览</div>

    <div class="stat-grid" v-if="stats">
      <div class="stat-card">
        <div class="stat-label">Skill 总量</div>
        <div class="stat-value">{{ stats.total_skills }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">今日新增</div>
        <div class="stat-value">{{ stats.today_new }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">活跃源</div>
        <div class="stat-value">{{ stats.active_sources }}/{{ stats.total_sources }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">扫描状态</div>
        <div class="stat-value">{{ stats.scan_enabled ? '运行中' : '已暂停' }}</div>
      </div>
    </div>

    <div class="panel" v-if="vendorStats">
      <div class="panel-header">公司 Skill 统计（含分类）</div>
      <div v-for="v in vendorStats.vendors" :key="v.vendor" style="margin-bottom: 12px">
        <div style="font-weight: 600; margin-bottom: 4px">
          {{ v.vendor }} · {{ v.total }} 条
          <span class="text-muted" v-if="v.vendor === '美团'">（API 共 43）</span>
          <span class="text-muted" v-if="v.today_new"> · 今日 +{{ v.today_new }}</span>
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 6px">
          <NTag v-for="(cnt, cat) in v.categories" :key="String(cat)" size="small">
            {{ cat }} {{ cnt }}
          </NTag>
        </div>
      </div>
    </div>

    <div class="panel" v-if="vendorStats">
      <div class="panel-header">官方门户扫描</div>
      <div style="margin-bottom: 12px" class="text-muted">
        仅扫描各公司官方网站/API（不含 GitHub、SkillsMP、ClawHub），比对入库后自动推送官方新增。
        {{ officialScanStatusText() }}
      </div>
      <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px">
        <NButton
          type="primary"
          :loading="officialScanLoading || officialScan?.status === 'running'"
          :disabled="officialScan?.status === 'running'"
          @click="runOfficialScan"
        >
          官方门户扫描
        </NButton>
        <NButton
          type="primary"
          :disabled="!officialScan || officialScan.status !== 'done' || !(officialScan.new_official_count > 0)"
          @click="exportLastOfficialScan('xlsx')"
        >
          导出最近官方扫描新增 Excel
        </NButton>
        <NButton
          size="small"
          :disabled="!officialScan || officialScan.status !== 'done' || !(officialScan.new_official_count > 0)"
          @click="exportLastOfficialScan('csv')"
        >
          CSV
        </NButton>
      </div>
      <div v-if="officialPortals.length" style="overflow-x: auto">
        <table style="width: 100%; border-collapse: collapse; font-size: 13px">
          <thead>
            <tr style="text-align: left; border-bottom: 1px solid var(--border-color, #eee)">
              <th style="padding: 8px 12px">公司</th>
              <th style="padding: 8px 12px">官方 Skill 门户</th>
              <th style="padding: 8px 12px">链接</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in officialPortals" :key="p.source_id" style="border-bottom: 1px solid var(--border-color, #f5f5f5)">
              <td style="padding: 8px 12px; white-space: nowrap">{{ p.vendor }}</td>
              <td style="padding: 8px 12px">{{ p.name }}</td>
              <td style="padding: 8px 12px">
                <a :href="p.url" target="_blank" rel="noopener noreferrer">{{ p.url }}</a>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="panel" v-if="vendorStats">
      <div class="panel-header">数据导出</div>
      <div style="margin-bottom: 12px">
        <span class="text-muted" style="margin-right: 8px">公司筛选:</span>
        <span
          class="vendor-chip"
          :class="{ active: !exportVendor }"
          @click="exportVendor = ''"
        >全部</span>
        <span
          v-for="v in exportableVendors()"
          :key="v.vendor"
          class="vendor-chip"
          :class="{ active: exportVendor === v.vendor }"
          @click="exportVendor = v.vendor"
        >{{ v.vendor }}</span>
      </div>
      <div style="margin-bottom: 12px" class="text-muted">
        单公司：先选公司再点下载；一键打包：ZIP 内按公司各一个 CSV。
        「近24小时新发现」= 与榜单 🆕 一致（24h 内首次入库），含官方与个人创作者；发现时间为北京时间。
      </div>
      <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px">
        <NButton type="primary" @click="exportBundle(false)">全部下载</NButton>
        <NButton type="primary" @click="exportBundle(true)">今日新增打包</NButton>
        <NButton type="primary" @click="exportRecentDiscoveriesBundle()">近24小时新发现打包</NButton>
      </div>
      <div style="display: flex; flex-wrap: wrap; gap: 8px">
        <NButton size="small" @click="exportSkills('csv', false)">全量 CSV</NButton>
        <NButton size="small" @click="exportSkills('xlsx', false)">全量 Excel</NButton>
        <NButton size="small" type="primary" @click="exportSkills('csv', true)">今日新增 CSV</NButton>
        <NButton size="small" type="primary" @click="exportSkills('xlsx', true)">今日新增 Excel</NButton>
        <NButton size="small" type="primary" @click="exportRecentDiscoveries('xlsx')">近24小时新发现 Excel</NButton>
        <NButton size="small" @click="exportRecentDiscoveries('csv')">近24小时新发现 CSV</NButton>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">源健康</div>
      <div style="display: flex; flex-wrap: wrap; gap: 8px">
        <NTag v-for="s in sources" :key="s.id" :type="statusColor(s.last_status)" size="small">
          {{ s.vendor }} · {{ s.last_status }}
        </NTag>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <span>最近扫描</span>
        <NButton size="small" @click="load">刷新</NButton>
      </div>
      <div class="log-stream" style="height: 200px">
        <div
          v-for="ev in recentEvents"
          :key="ev.id"
          class="log-line"
          :class="ev.level === 'error' ? 'error' : ev.level === 'success' ? 'success' : 'info'"
        >
          [{{ ev.created_at?.slice(11, 19) || '--' }}] {{ ev.message }}
        </div>
      </div>
    </div>
  </div>
</template>
