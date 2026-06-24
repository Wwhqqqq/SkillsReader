<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { NSelect, NButton } from 'naive-ui'
import { api, wsScanEvents } from '../api/client'
import { formatBeijingTimeOnly } from '../utils/time'

const logs = ref<any[]>([])
const filterLevel = ref<string | null>(null)
const filterSource = ref<string | null>(null)
const sources = ref<any[]>([])
let ws: WebSocket | null = null

const levelOptions = [
  { label: '全部', value: '' },
  { label: 'info', value: 'info' },
  { label: 'success', value: 'success' },
  { label: 'error', value: 'error' },
]

function addLog(ev: any) {
  logs.value.push(ev)
  if (logs.value.length > 500) logs.value.shift()
}

const filtered = () => {
  return logs.value.filter((l) => {
    if (filterLevel.value && l.level !== filterLevel.value) return false
    if (filterSource.value && l.source_id !== filterSource.value) return false
    return true
  })
}

onMounted(async () => {
  sources.value = await api.sources()
  const history = await api.scanEvents(100)
  logs.value = [...history].reverse()
  ws = wsScanEvents(addLog)
})

onUnmounted(() => ws?.close())

async function clearLogs() {
  logs.value = []
}
</script>

<template>
  <div class="page">
    <div class="page-title">实时扫描日志</div>

    <div style="display: flex; gap: 12px; margin-bottom: 16px; align-items: center">
      <NSelect
        v-model:value="filterLevel"
        :options="levelOptions"
        placeholder="级别"
        clearable
        style="width: 120px"
      />
      <NSelect
        v-model:value="filterSource"
        :options="sources.map((s) => ({ label: s.vendor, value: s.id }))"
        placeholder="来源"
        clearable
        style="width: 160px"
      />
      <NButton size="small" @click="clearLogs">清空</NButton>
      <span class="text-muted">{{ filtered().length }} 条</span>
    </div>

    <div class="log-stream">
      <div
        v-for="(ev, i) in filtered()"
        :key="ev.id || i"
        class="log-line"
        :class="ev.level === 'error' ? 'error' : ev.level === 'success' ? 'success' : 'info'"
      >
        [{{ formatBeijingTimeOnly(ev.created_at) || '--:--:--' }}]
        {{ ev.source_id ? `[${ev.source_id}] ` : '' }}{{ ev.message }}
      </div>
      <div v-if="!filtered().length" class="log-line info">等待扫描事件...</div>
    </div>
  </div>
</template>
