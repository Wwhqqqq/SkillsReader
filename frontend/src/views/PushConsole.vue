<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  NButton,
  NInput,
  NInputNumber,
  NRadioGroup,
  NRadio,
  NSwitch,
  NTag,
  useMessage,
} from 'naive-ui'
import { api } from '../api/client'
import { formatBeijingTime } from '../utils/time'

const message = useMessage()
const pushTarget = ref('dm')
const pushChannel = ref('digest')
const dryRun = ref(false)
const topN = ref(10)
const preview = ref('')
const charCount = ref(0)
const skillCount = ref(0)
const previewItems = ref<any[]>([])
const history = ref<any[]>([])
const selectedVendors = ref<string[]>([])
const allVendors = ref<string[]>([])
const sending = ref(false)
const pushTargets = ref({
  dm_users: ['wangheqiao'],
  group_ids: ['13038971'],
  official_new_dm_users: ['wangheqiao'],
  dm: { label: '单聊', default_user: 'wangheqiao' },
  group: { label: '群聊', default_group_id: '13038971' },
})
const newDmInput = ref('')
const newGroupInput = ref('')

const scheduleEnabled = ref(true)
const scheduleTimes = ref('09:00,18:00')
const scheduleTopN = ref(10)
const scheduleTarget = ref('dm')
const scheduleOfficialNewEnabled = ref(false)
const scheduleOfficialNewTime = ref('08:30')
const scheduleOfficialNewTopN = ref(10)
const savingSchedule = ref(false)

const channelLabels: Record<string, string> = {
  digest: '综合精选',
  official_new: '官方发布新增日报',
}

const slotLabels: Record<string, string> = {
  official: '官方精选',
  trend: '趋势爆发',
  discovery: '新发现',
  fill: '综合推荐',
  official_new: '官方新增',
}

const targetLabels = computed(() => ({
  dm: `单聊（${(pushTargets.value.dm_users || []).join('、') || pushTargets.value.dm.default_user}）`,
  group: `群聊（toid：${(pushTargets.value.group_ids || []).join('、') || pushTargets.value.group.default_group_id}）`,
}))

const previewHint = computed(() => {
  const vendor = selectedVendors.value.length
    ? ` · 公司：${selectedVendors.value.join('、')}`
    : ''
  const target =
    pushTarget.value === 'group' ? targetLabels.value.group : targetLabels.value.dm
  return `${channelLabels[pushChannel.value] || pushChannel.value} Top${topN.value}${vendor} · ${target}`
})

async function loadHistory() {
  history.value = await api.pushHistory()
}

async function loadSchedule() {
  try {
    const s = await api.digestSchedule()
    scheduleEnabled.value = s.enabled
    scheduleTimes.value = (s.times || []).join(',')
    scheduleTopN.value = s.top_n ?? 10
    scheduleTarget.value = s.target || 'dm'
    scheduleOfficialNewEnabled.value = s.official_new_enabled ?? false
    scheduleOfficialNewTime.value = s.official_new_time || '08:30'
    scheduleOfficialNewTopN.value = s.official_new_top_n ?? 10
  } catch {
    /* defaults */
  }
}

async function loadPushTargets() {
  try {
    pushTargets.value = await api.pushTargets()
  } catch {
    /* use defaults */
  }
}

async function addRecipient(kind: 'dm' | 'group') {
  const val = (kind === 'dm' ? newDmInput.value : newGroupInput.value).trim()
  if (!val) return
  const listKey = kind === 'dm' ? 'dm_users' : 'group_ids'
  const current = pushTargets.value[listKey as 'dm_users' | 'group_ids'] || []
  if (current.includes(val)) {
    message.warning('已在名单中')
    return
  }
  try {
    pushTargets.value = await api.addPushTarget({ kind, value: val })
    if (kind === 'dm') newDmInput.value = ''
    else newGroupInput.value = ''
    message.success(`已添加 ${val}`)
  } catch (e: any) {
    message.error(e.message)
  }
}

async function removeRecipient(kind: 'dm' | 'group', value: string) {
  try {
    pushTargets.value = await api.removePushTarget({ kind, value })
    message.success(`已移除 ${value}`)
  } catch (e: any) {
    message.error(e.message)
  }
}

onMounted(async () => {
  await loadPushTargets()
  const src = await api.sources()
  allVendors.value = [...new Set(src.map((s: any) => s.vendor))].filter(
    (v) => !['海外社区', 'GitHub'].includes(v)
  )
  await loadHistory()
  await loadSchedule()
})

async function saveSchedule() {
  savingSchedule.value = true
  try {
    const times = scheduleTimes.value
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)
    await api.setDigestSchedule({
      enabled: scheduleEnabled.value,
      times,
      top_n: scheduleTopN.value,
      target: scheduleTarget.value,
      timezone: 'Asia/Shanghai',
      official_new_enabled: scheduleOfficialNewEnabled.value,
      official_new_time: scheduleOfficialNewTime.value,
      official_new_top_n: scheduleOfficialNewTopN.value,
    })
    message.success('定时精选推送配置已保存')
  } catch (e: any) {
    message.error(e.message)
  } finally {
    savingSchedule.value = false
  }
}

function toggleVendor(v: string) {
  const i = selectedVendors.value.indexOf(v)
  if (i >= 0) selectedVendors.value.splice(i, 1)
  else selectedVendors.value.push(v)
}

async function doPreview() {
  try {
    const res = await api.pushPreview({
      vendors: selectedVendors.value,
      top_n: topN.value,
      channel: pushChannel.value,
    })
    preview.value = res.content_md
    charCount.value = res.char_count
    skillCount.value = res.skill_count
    previewItems.value = res.items || []
  } catch (e: any) {
    message.error(e.message)
  }
}

async function doSend() {
  sending.value = true
  try {
    const res = await api.pushSend({
      vendors: selectedVendors.value,
      top_n: topN.value,
      target: pushTarget.value,
      channel: pushChannel.value,
      dry_run: dryRun.value,
    })
    if (res.success) {
      message.success(res.message)
      preview.value = res.content_md || preview.value
    } else {
      message.error(res.message)
    }
    await loadHistory()
  } catch (e: any) {
    message.error(e.message)
  } finally {
    sending.value = false
  }
}

function historyTargetLabel(target: string) {
  if (target === 'ruliu_group') return '群聊'
  if (target === 'ruliu_dm') return '单聊'
  return target || '单聊'
}

function historyTypeLabel(pushType: string) {
  if (pushType === 'digest_top10') return '综合精选'
  if (pushType === 'official_new_daily') return '官方新增日报'
  return pushType
}

function growthLabel(g: any) {
  const parts: string[] = []
  if (g?.growth_1d_pct > 0) parts.push(`1d +${Math.round(g.growth_1d_pct)}%`)
  if (g?.growth_3d_pct > 0) parts.push(`3d +${Math.round(g.growth_3d_pct)}%`)
  if (g?.growth_7d_pct > 0) parts.push(`7d +${Math.round(g.growth_7d_pct)}%`)
  return parts.join(' / ') || '-'
}
</script>

<template>
  <div class="page">
    <div class="page-title">如流推送 · 每日精选</div>

    <div class="panel">
      <div class="panel-header">每日精选定时推送</div>
      <div style="margin-bottom: 12px" class="text-muted">
        Worker（digest_loop）按以下时刻自动生成 Top N 并推送；默认单聊
      </div>
      <div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin-bottom: 12px">
        <span class="text-muted">启用</span>
        <NSwitch v-model:value="scheduleEnabled" />
        <span class="text-muted">Top N</span>
        <NInputNumber v-model:value="scheduleTopN" :min="1" :max="30" style="width: 100px" />
        <span class="text-muted">时刻（逗号分隔）</span>
        <input v-model="scheduleTimes" class="schedule-input" placeholder="09:00,18:00" />
        <NRadioGroup v-model:value="scheduleTarget">
          <NRadio value="dm">定时 · 单聊</NRadio>
          <NRadio value="group">定时 · 群聊</NRadio>
        </NRadioGroup>
        <NButton :loading="savingSchedule" @click="saveSchedule">保存定时配置</NButton>
      </div>
      <div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: center">
        <span class="text-muted">官方新增日报</span>
        <NSwitch v-model:value="scheduleOfficialNewEnabled" />
        <span class="text-muted">时刻</span>
        <input v-model="scheduleOfficialNewTime" class="schedule-input" placeholder="08:30" />
        <span class="text-muted">Top N</span>
        <NInputNumber v-model:value="scheduleOfficialNewTopN" :min="1" :max="30" style="width: 100px" />
        <span class="text-muted">（建议早于综合精选，如 08:30 → 09:00）</span>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">推送收件人名单</div>
      <div style="margin-bottom: 16px" class="text-muted">
        手动推送与定时精选会按名单发送；单聊推送给所有单聊 ID，群聊推送给所有群 ID。
      </div>

      <div style="margin-bottom: 16px">
        <div style="font-weight: 600; margin-bottom: 8px">单聊 ID</div>
        <NTag
          v-for="u in pushTargets.dm_users || []"
          :key="'dm-' + u"
          closable
          size="small"
          style="margin-right: 6px; margin-bottom: 6px"
          @close="removeRecipient('dm', u)"
        >
          {{ u }}
        </NTag>
        <div style="display: flex; gap: 8px; margin-top: 8px; max-width: 360px">
          <NInput v-model:value="newDmInput" placeholder="输入如流用户名" size="small" />
          <NButton size="small" @click="addRecipient('dm')">添加</NButton>
        </div>
      </div>

      <div style="margin-bottom: 16px">
        <div style="font-weight: 600; margin-bottom: 8px">群聊 ID（toid）</div>
        <NTag
          v-for="g in pushTargets.group_ids || []"
          :key="'group-' + g"
          closable
          size="small"
          style="margin-right: 6px; margin-bottom: 6px"
          @close="removeRecipient('group', g)"
        >
          {{ g }}
        </NTag>
        <div style="display: flex; gap: 8px; margin-top: 8px; max-width: 360px">
          <NInput v-model:value="newGroupInput" placeholder="输入群 toid" size="small" />
          <NButton size="small" @click="addRecipient('group')">添加</NButton>
        </div>
      </div>
    </div>

    <div class="panel">
      <div style="margin-bottom: 16px">
        <span class="text-muted" style="margin-right: 12px">推送渠道:</span>
        <NRadioGroup v-model:value="pushChannel">
          <NRadio value="digest">综合精选 Top N</NRadio>
          <NRadio value="official_new">官方发布新增日报</NRadio>
        </NRadioGroup>
      </div>

      <div style="margin-bottom: 16px">
        <span class="text-muted" style="margin-right: 12px">手动推送目标:</span>
        <NRadioGroup v-model:value="pushTarget">
          <NRadio value="dm">{{ targetLabels.dm }}</NRadio>
          <NRadio value="group">{{ targetLabels.group }}</NRadio>
        </NRadioGroup>
      </div>

      <div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin-bottom: 16px">
        <span class="text-muted">精选数量</span>
        <NInputNumber v-model:value="topN" :min="1" :max="30" style="width: 100px" />
        <span class="text-muted">Dry Run</span>
        <NSwitch v-model:value="dryRun" />
      </div>

      <div style="margin-bottom: 12px">
        <span class="text-muted" style="margin-right: 8px">定向公司:</span>
        <span
          v-for="v in allVendors"
          :key="v"
          class="vendor-chip"
          :class="{ active: selectedVendors.includes(v) }"
          @click="toggleVendor(v)"
        >{{ v }}</span>
      </div>

      <div style="display: flex; gap: 8px">
        <NButton @click="doPreview">预览精选 Markdown</NButton>
        <NButton type="primary" :loading="sending" @click="doSend">
          {{ dryRun ? '模拟推送' : '发送精选到如流' }}
        </NButton>
      </div>
      <div v-if="charCount" class="text-muted" style="margin-top: 8px">
        {{ previewHint }} · {{ skillCount }} 条 · {{ charCount }} 字符
        <span v-if="charCount > 2048" style="color: var(--color-warn)"> (超限将拆成多条发送)</span>
      </div>
    </div>

    <div class="panel" v-if="previewItems.length">
      <div class="panel-header">精选列表</div>
      <div v-for="item in previewItems" :key="item.rank" class="pick-row">
        <strong>{{ item.rank }}.</strong>
        <NTag size="small" :bordered="false">{{ slotLabels[item.slot] || item.slot }}</NTag>
        <span>{{ item.skill.name }}</span>
        <span class="text-muted">· {{ item.skill.vendor }}</span>
        <span v-if="item.is_official" class="text-muted">· 官方</span>
        <span v-if="item.is_new"> 🆕</span>
        <div class="text-muted pick-reason">{{ item.recommend_reason }} · 增长 {{ growthLabel(item.growth) }} · 分 {{ item.score.toFixed(1) }}</div>
      </div>
    </div>

    <div class="panel" v-if="preview">
      <div class="panel-header">Markdown 预览</div>
      <div class="md-preview">{{ preview }}</div>
    </div>

    <div class="panel">
      <div class="panel-header">推送历史</div>
      <div class="log-stream" style="height: 160px">
        <div v-for="h in history" :key="h.id" class="log-line info">
          [{{ formatBeijingTime(h.created_at) }}] {{ historyTargetLabel(h.target) }} · {{ historyTypeLabel(h.push_type) }} · {{ h.status }} · {{ h.skill_count }} 条
          <span v-if="h.error" style="color: #f45b5b"> · {{ h.error }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.schedule-input {
  padding: 4px 8px;
  border: 1px solid #d9dde4;
  border-radius: 4px;
  min-width: 160px;
}
.pick-row {
  padding: 8px 0;
  border-bottom: 1px solid #eef0f3;
}
.pick-reason {
  font-size: 12px;
  margin-top: 4px;
  margin-left: 24px;
}
</style>
