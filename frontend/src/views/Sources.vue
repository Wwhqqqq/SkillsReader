<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NButton, NSwitch, NInputNumber, useMessage } from 'naive-ui'
import { api } from '../api/client'

const message = useMessage()
const sources = ref<any[]>([])
const globalEnabled = ref(true)
const selectedVendors = ref<string[]>([])

async function load() {
  sources.value = await api.sources()
  const g = await api.getGlobalScan()
  globalEnabled.value = g.enabled
}

onMounted(load)

async function toggleGlobal(v: boolean) {
  await api.setGlobalScan(v)
  globalEnabled.value = v
  message.success(v ? '扫描已开启' : '扫描已暂停')
}

async function toggleSource(s: any, enabled: boolean) {
  await api.updateSource(s.id, { enabled })
  s.enabled = enabled
}

async function updateInterval(s: any, val: number | null) {
  if (!val) return
  await api.updateSource(s.id, { interval_sec: val })
  s.interval_sec = val
}

async function scanOne(s: any) {
  await api.triggerScan({ source_ids: [s.id] })
  message.info(`已触发 ${s.vendor} 扫描`)
}

async function scanSelected() {
  const vendors = selectedVendors.value.length ? selectedVendors.value : undefined
  await api.triggerScan({ vendors: vendors || [] })
  message.info('定向扫描已触发')
}

function toggleVendor(v: string) {
  const i = selectedVendors.value.indexOf(v)
  if (i >= 0) selectedVendors.value.splice(i, 1)
  else selectedVendors.value.push(v)
}

const vendors = () => [...new Set(sources.value.map((s) => s.vendor))]
</script>

<template>
  <div class="page">
    <div class="page-title">采集源管理</div>

    <div class="panel">
      <div class="panel-header">
        <span>全局扫描开关</span>
        <NSwitch :value="globalEnabled" @update:value="toggleGlobal" />
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <span>定向扫描公司</span>
        <NButton size="small" type="primary" @click="scanSelected">立即扫描</NButton>
      </div>
      <div>
        <span
          v-for="v in vendors()"
          :key="v"
          class="vendor-chip"
          :class="{ active: selectedVendors.includes(v) }"
          @click="toggleVendor(v)"
        >{{ v }}</span>
      </div>
    </div>

    <div class="panel" v-for="s in sources" :key="s.id">
      <div class="panel-header">
        <span>{{ s.vendor }} · {{ s.name }}</span>
        <div style="display: flex; gap: 8px; align-items: center">
          <NButton size="tiny" @click="scanOne(s)">立即扫描</NButton>
          <NSwitch :value="s.enabled" @update:value="(v: boolean) => toggleSource(s, v)" />
        </div>
      </div>
      <div class="text-muted" style="display: grid; gap: 4px">
        <div>ID: {{ s.id }} · Adapter: {{ s.adapter }}</div>
        <div>间隔: <NInputNumber size="small" :value="s.interval_sec" :min="60" :step="60" style="width: 100px" @update:value="(v) => updateInterval(s, v)" /> 秒</div>
        <div>上次: {{ s.last_run_at || '从未' }} · 状态: {{ s.last_status }}</div>
        <div v-if="s.last_error" style="color: var(--color-error)">{{ s.last_error }}</div>
      </div>
    </div>
  </div>
</template>
