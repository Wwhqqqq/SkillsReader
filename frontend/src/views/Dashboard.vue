<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { NButton, NInput, NInputNumber, NSelect, NTag, useMessage } from 'naive-ui'
import { api, downloadSkillsBundle, downloadSkillsExport } from '../api/client'
import { formatBeijingTime, formatBeijingTimeOnly } from '../utils/time'

const message = useMessage()
const stats = ref<any>(null)
const vendorStats = ref<any>(null)
const sources = ref<any[]>([])
const recentEvents = ref<any[]>([])
const officialScan = ref<any>(null)
const officialScanLoading = ref(false)
const officialPortals = ref<any[]>([])
const officialSettings = ref<any>(null)
const scanIntervalMin = ref(10)
const savingInterval = ref(false)
const newOfficialDmInput = ref('')
const recentExportVendors = ref<string[]>([])
let timer: number

const domesticVendors = computed(() =>
  (vendorStats.value?.vendors || []).map((v: any) => v.vendor as string)
)

const vendorSelectOptions = computed(() =>
  domesticVendors.value.map((v) => ({ label: v, value: v }))
)

const allRecentSelected = computed(
  () =>
    domesticVendors.value.length > 0 &&
    recentExportVendors.value.length === domesticVendors.value.length
)

async function loadOfficialScanStatus() {
  try {
    officialScan.value = await api.officialScanStatus()
    if (officialScan.value?.interval_sec) {
      scanIntervalMin.value = Math.round(officialScan.value.interval_sec / 60)
    }
  } catch {
    /* ignore */
  }
}

async function loadOfficialSettings() {
  try {
    officialSettings.value = await api.officialScanSettings()
    if (officialSettings.value?.interval_sec) {
      scanIntervalMin.value = Math.round(officialSettings.value.interval_sec / 60)
    }
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
    await loadOfficialSettings()
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

function formatTime(iso: string | null | undefined) {
  return formatBeijingTime(iso)
}

function officialScanStatusText() {
  const s = officialScan.value
  if (!s || s.status === 'idle') return '尚未执行官方门户扫描'
  if (s.status === 'running') return '官方门户扫描进行中…'
  if (s.status === 'error') return `上次扫描失败：${s.error_message || '未知错误'}`
  const t = formatTime(s.finished_at)
  const push =
    s.push_status === 'sent' ? ' · 已推送' : s.push_status === 'failed' ? ' · 推送失败' : ''
  return `上次官方门户扫描 ${t} · 新增官方 ${s.new_official_count ?? 0} 条${push}`
}

function lastNewOfficialText() {
  const t =
    officialSettings.value?.last_new_official_at ||
    officialScan.value?.last_new_official_at
  if (!t) return '尚未发现新的官方内容'
  return `最近一次发现新官方内容：${formatTime(t)}`
}

async function saveScanInterval() {
  savingInterval.value = true
  try {
    const sec = Math.max(1, scanIntervalMin.value) * 60
    officialSettings.value = await api.updateOfficialScanSettings({ interval_sec: sec })
    message.success(`扫描间隔已设为 ${scanIntervalMin.value} 分钟`)
    await loadOfficialScanStatus()
  } catch (e: any) {
    message.error(e.message)
  } finally {
    savingInterval.value = false
  }
}

async function addOfficialDmUser() {
  const val = newOfficialDmInput.value.trim()
  if (!val) return
  const current = officialSettings.value?.official_new_dm_users || []
  if (current.includes(val)) {
    message.warning('已在名单中')
    return
  }
  try {
    officialSettings.value = await api.updateOfficialScanSettings({
      official_new_dm_users: [...current, val],
    })
    newOfficialDmInput.value = ''
    message.success(`已添加 ${val}`)
  } catch (e: any) {
    message.error(e.message)
  }
}

async function removeOfficialDmUser(user: string) {
  const current = (officialSettings.value?.official_new_dm_users || []).filter(
    (u: string) => u !== user
  )
  try {
    officialSettings.value = await api.updateOfficialScanSettings({
      official_new_dm_users: current,
    })
    message.success(`已移除 ${user}`)
  } catch (e: any) {
    message.error(e.message)
  }
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
      await loadOfficialSettings()
      if (officialScan.value?.status !== 'running') {
        window.clearInterval(poll)
        officialScanLoading.value = false
        await load()
        if (officialScan.value?.status === 'done') {
          const pushHint =
            officialScan.value.push_status === 'sent' ? '，已推送官方新增' : ''
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

function exportFullLibrary() {
  downloadSkillsBundle({ scope: 'domestic', fmt: 'xlsx' })
  message.success('正在下载全库（国内各公司 Excel 打包 ZIP）')
}

function toggleAllRecentVendors() {
  if (allRecentSelected.value) recentExportVendors.value = []
  else recentExportVendors.value = [...domesticVendors.value]
}

function exportRecentDiscoveries() {
  const selected = recentExportVendors.value
  if (!selected.length) {
    message.warning('请至少选择一个公司')
    return
  }
  if (selected.length === 1) {
    downloadSkillsExport({
      format: 'xlsx',
      vendor: selected[0],
      recent_only: true,
    })
    message.success(`正在下载 ${selected[0]} 近24小时新发现 Excel`)
    return
  }
  downloadSkillsBundle({
    recent_only: true,
    scope: 'domestic',
    vendors: selected.join(','),
    fmt: 'xlsx',
  })
  message.success(`正在下载 ${selected.length} 家公司近24小时新发现 Excel 打包`)
}
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
      <div style="margin-bottom: 8px" class="text-muted">{{ lastNewOfficialText() }}</div>

      <div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 12px">
        <span class="text-muted">扫描间隔（分钟）</span>
        <NInputNumber v-model:value="scanIntervalMin" :min="1" :max="1440" style="width: 120px" />
        <NButton size="small" :loading="savingInterval" @click="saveScanInterval">保存间隔</NButton>
        <span class="text-muted">
          默认 {{ Math.round((officialSettings?.default_interval_sec || 600) / 60) }} 分钟
        </span>
      </div>

      <div style="margin-bottom: 12px">
        <span class="text-muted" style="margin-right: 8px">官方新增推送单聊 ID:</span>
        <NTag
          v-for="u in officialSettings?.official_new_dm_users || []"
          :key="u"
          closable
          size="small"
          style="margin-right: 6px"
          @close="removeOfficialDmUser(u)"
        >
          {{ u }}
        </NTag>
        <div style="display: flex; gap: 8px; margin-top: 8px; max-width: 360px">
          <NInput v-model:value="newOfficialDmInput" placeholder="输入如流用户名" size="small" />
          <NButton size="small" @click="addOfficialDmUser">添加</NButton>
        </div>
      </div>

      <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px">
        <NButton
          type="primary"
          :loading="officialScanLoading || officialScan?.status === 'running'"
          :disabled="officialScan?.status === 'running'"
          @click="runOfficialScan"
        >
          立即扫描
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
      <div style="margin-bottom: 16px" class="text-muted">
        「近24小时新发现」= 与榜单 🆕 一致（24h 内首次入库），发现时间为北京时间。
        勾选一家公司下载 Excel；勾选多家或全选下载 ZIP。
      </div>

      <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px">
        <NButton type="primary" @click="exportFullLibrary">全库下载</NButton>
      </div>

      <div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 12px">
        <NButton type="primary" @click="exportRecentDiscoveries">24h内新发现</NButton>
        <NSelect
          v-model:value="recentExportVendors"
          multiple
          filterable
          clearable
          placeholder="选择公司（可多选）"
          :options="vendorSelectOptions"
          max-tag-count="responsive"
          style="min-width: 280px; max-width: 420px"
          :consistent-menu-width="false"
          :menu-props="{ style: 'max-height: 240px; overflow-y: auto' }"
        />
        <NButton size="small" quaternary @click="toggleAllRecentVendors">
          {{ allRecentSelected ? '清空' : '全选' }}
        </NButton>
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
          [{{ formatBeijingTimeOnly(ev.created_at) }}] {{ ev.message }}
        </div>
      </div>
    </div>
  </div>
</template>
