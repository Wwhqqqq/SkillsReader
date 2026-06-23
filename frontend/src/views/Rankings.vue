<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NButton, NDataTable, useMessage } from 'naive-ui'
import { api, downloadSkillsExport } from '../api/client'

const message = useMessage()
const items = ref<any[]>([])
const selectedVendors = ref<string[]>([])
const allVendors = ref<string[]>([])
const topN = ref(10)
const loading = ref(false)
const meta = ref<any>({})

const slotLabels: Record<string, string> = {
  official: '官方精选',
  trend: '趋势爆发',
  discovery: '新发现',
  fill: '综合推荐',
}

const columns = [
  { title: '#', key: 'rank', width: 50 },
  {
    title: '槽位',
    key: 'slot',
    width: 100,
    render: (row: any) => slotLabels[row.slot] || row.slot,
  },
  { title: 'Skill', key: 'name', ellipsis: { tooltip: true } },
  { title: '公司', key: 'vendor', width: 80 },
  { title: '推荐理由', key: 'reason', ellipsis: { tooltip: true } },
  { title: '增长', key: 'growth', width: 120 },
  { title: '分数', key: 'score', width: 70 },
  { title: '安装量', key: 'install', width: 80 },
]

function growthLabel(g: any) {
  const parts: string[] = []
  if (g?.growth_1d_pct > 0) parts.push(`1d +${Math.round(g.growth_1d_pct)}%`)
  if (g?.growth_3d_pct > 0) parts.push(`3d +${Math.round(g.growth_3d_pct)}%`)
  if (g?.growth_7d_pct > 0) parts.push(`7d +${Math.round(g.growth_7d_pct)}%`)
  return parts.join(' / ') || '-'
}

function mapRows(list: any[]) {
  return list.map((r) => ({
    rank: r.rank,
    slot: r.slot,
    name: r.skill.name + (r.is_new ? ' 🆕' : '') + (r.is_official ? ' [官方]' : ''),
    vendor: r.skill.vendor,
    reason: r.recommend_reason || '-',
    growth: growthLabel(r.growth),
    score: r.score?.toFixed?.(1) ?? r.score,
    install: r.skill.install_count || '-',
    key: r.skill.id,
  }))
}

async function load() {
  loading.value = true
  try {
    const vendors = selectedVendors.value.length ? selectedVendors.value : undefined
    const res = await api.digestPicks({
      top_n: topN.value,
      vendors,
      regenerate: true,
    })
    items.value = mapRows(res.items || [])
    meta.value = res.meta || {}
  } catch (e: any) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const src = await api.sources()
  allVendors.value = [...new Set(src.map((s: any) => s.vendor))].filter(
    (v) => !['海外社区', 'GitHub'].includes(v)
  )
  await load()
})

function toggleVendor(v: string) {
  const i = selectedVendors.value.indexOf(v)
  if (i >= 0) selectedVendors.value.splice(i, 1)
  else selectedVendors.value.push(v)
  load()
}

function exportCurrent(format: 'csv' | 'xlsx') {
  const vendor = selectedVendors.value.length === 1 ? selectedVendors.value[0] : undefined
  downloadSkillsExport({ format, vendor, today_only: false })
  message.success(`正在下载${vendor || '全部公司'} ${format.toUpperCase()}`)
}
</script>

<template>
  <div class="page">
    <div class="page-title">每日精选 Top {{ topN }}</div>
    <div class="text-muted" style="margin-bottom: 12px">
      官方 1–3 · 趋势 4–7 · 发现 8–10（结构化推荐，非简单排序）
      <span v-if="meta.candidate_count"> · 候选 {{ meta.candidate_count }} 条</span>
    </div>

    <div style="margin-bottom: 16px">
      <span
        v-for="v in allVendors"
        :key="v"
        class="vendor-chip"
        :class="{ active: selectedVendors.includes(v) }"
        @click="toggleVendor(v)"
      >{{ v }}</span>
      <NButton size="small" style="margin-left: 8px" :loading="loading" @click="load">刷新</NButton>
      <NButton size="small" style="margin-left: 8px" @click="exportCurrent('csv')">导出 CSV</NButton>
      <NButton size="small" style="margin-left: 8px" @click="exportCurrent('xlsx')">导出 Excel</NButton>
    </div>

    <NDataTable :columns="columns" :data="items" size="small" :bordered="false" :loading="loading" />
  </div>
</template>
