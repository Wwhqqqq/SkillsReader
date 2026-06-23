<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton,
  NCard,
  NCollapse,
  NCollapseItem,
  NDataTable,
  NDatePicker,
  NInput,
  NInputNumber,
  NSelect,
  NSpace,
  NTabPane,
  NTabs,
  NTag,
  useMessage,
} from 'naive-ui'
import { testbenchApi } from '../api/client'

const message = useMessage()
const platforms = ref<any[]>([])
const skills = ref<any[]>([])
const snapshotDates = ref<string[]>([])
const refDate = ref<number>(Date.now())
const simDate = ref<number>(Date.now())
const topN = ref(10)
const simResult = ref<any>(null)
const loading = ref(false)

const form = ref({
  source_id: '',
  name: '',
  external_id: '',
  raw_description: '',
  install_count: 100,
  quality_score: 65,
  official: false,
  first_seen_date: null as number | null,
})

const snapshotEdits = ref<Record<number, number>>({})
const timelineSkillId = ref<number | null>(null)
const timelineStart = ref<number>(Date.now())
const timelineValues = ref('10,20,35,50,80,120,200,320')

const platformOptions = computed(() =>
  platforms.value.map((p) => ({ label: `${p.vendor} (${p.id})`, value: p.id }))
)

function isoFromTs(ts: number | null) {
  if (!ts) return new Date().toISOString().slice(0, 10)
  return new Date(ts).toISOString().slice(0, 10)
}

async function initTestDb() {
  loading.value = true
  try {
    await testbenchApi.init()
    message.success('测试库已初始化')
    await refreshAll()
  } catch (e: any) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function resetTestDb() {
  if (!confirm('确认清空测试库所有 Skill 与快照？')) return
  loading.value = true
  try {
    await testbenchApi.reset()
    message.success('测试库已重置')
    simResult.value = null
    await refreshAll()
  } catch (e: any) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  platforms.value = await testbenchApi.platforms()
  const res = await testbenchApi.skills()
  skills.value = res.items || []
  snapshotDates.value = await testbenchApi.snapshotDates()
  if (!form.value.source_id && platforms.value.length) {
    form.value.source_id = platforms.value[0].id
  }
  await loadSnapshotsForDate()
}

async function createSkill() {
  if (!form.value.name || !form.value.source_id) {
    message.warning('请填写平台与名称')
    return
  }
  loading.value = true
  try {
    await testbenchApi.createSkill({
      ...form.value,
      first_seen_date: isoFromTs(form.value.first_seen_date),
    })
    message.success('Skill 已创建')
    form.value.name = ''
    await refreshAll()
  } catch (e: any) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function loadSnapshotsForDate() {
  const d = isoFromTs(refDate.value)
  const rows = await testbenchApi.snapshots(d)
  const edits: Record<number, number> = {}
  for (const s of skills.value) {
    const hit = rows.find((r: any) => r.skill_id === s.id)
    edits[s.id] = hit ? hit.metric_value : s.install_count || 0
  }
  snapshotEdits.value = edits
}

async function saveSnapshots() {
  loading.value = true
  try {
    const items = Object.entries(snapshotEdits.value).map(([id, val]) => ({
      skill_id: Number(id),
      metric_value: Number(val),
    }))
    await testbenchApi.upsertSnapshots(isoFromTs(refDate.value), items)
    message.success(`已保存 ${items.length} 条快照`)
    snapshotDates.value = await testbenchApi.snapshotDates()
    await refreshAll()
  } catch (e: any) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function generateTimeline() {
  if (!timelineSkillId.value) {
    message.warning('请选择 Skill')
    return
  }
  const values = timelineValues.value.split(',').map((s) => parseInt(s.trim(), 10)).filter((n) => !Number.isNaN(n))
  loading.value = true
  try {
    const res = await testbenchApi.generateTimeline({
      skill_id: timelineSkillId.value,
      start_date: isoFromTs(timelineStart.value),
      values,
    })
    message.success(`已写入 ${res.days_written} 天快照`)
    await refreshAll()
  } catch (e: any) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

async function runSimulate() {
  loading.value = true
  try {
    simResult.value = await testbenchApi.simulate({
      digest_date: isoFromTs(simDate.value),
      top_n: topN.value,
    })
    message.success('模拟完成')
  } catch (e: any) {
    message.error(e.message)
  } finally {
    loading.value = false
  }
}

const skillColumns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '名称', key: 'name', ellipsis: { tooltip: true } },
  { title: '公司', key: 'vendor', width: 80 },
  { title: '平台', key: 'source_id', width: 120 },
  { title: '安装量', key: 'install_count', width: 80 },
  { title: '质量分', key: 'quality_score', width: 70 },
]

const snapshotColumns = computed(() => [
  { title: 'ID', key: 'id', width: 60 },
  { title: 'Skill', key: 'name', ellipsis: { tooltip: true } },
  { title: '平台', key: 'source_id', width: 120 },
  {
    title: '指标值',
    key: 'metric',
    width: 140,
    render: (row: any) =>
      h(NInputNumber, {
        value: snapshotEdits.value[row.id],
        min: 0,
        size: 'small',
        onUpdateValue: (v: number | null) => {
          snapshotEdits.value[row.id] = v ?? 0
        },
      }),
  },
])

onMounted(refreshAll)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1>测试平台</h1>
      <p>独立测试库 · 模拟各平台 Skill 与每日指标 · 带完整评分追踪的推送模拟</p>
      <NSpace>
        <NButton type="primary" :loading="loading" @click="initTestDb">初始化测试库</NButton>
        <NButton :loading="loading" @click="resetTestDb">清空测试数据</NButton>
        <NButton :loading="loading" @click="refreshAll">刷新</NButton>
      </NSpace>
    </header>

    <NTabs type="line" animated>
      <NTabPane name="skills" tab="Skill 管理">
        <NCard title="新增 Skill" size="small">
          <NSpace vertical>
            <NSelect v-model:value="form.source_id" :options="platformOptions" placeholder="模拟平台" />
            <NInput v-model:value="form.name" placeholder="Skill 名称" />
            <NInput v-model:value="form.external_id" placeholder="external_id（可选）" />
            <NInput v-model:value="form.raw_description" type="textarea" placeholder="描述" />
            <NSpace>
              <NInputNumber v-model:value="form.install_count" :min="0" placeholder="初始安装量" />
              <NInputNumber v-model:value="form.quality_score" :min="0" :max="100" placeholder="质量分" />
            </NSpace>
            <NDatePicker v-model:value="form.first_seen_date" type="date" clearable placeholder="首次发现日" />
            <NButton type="primary" :loading="loading" @click="createSkill">上传 Skill</NButton>
          </NSpace>
        </NCard>
        <NCard title="Skill 列表" size="small" style="margin-top: 12px">
          <NDataTable :columns="skillColumns" :data="skills" :row-key="(r: any) => r.id" size="small" />
        </NCard>
      </NTabPane>

      <NTabPane name="snapshots" tab="指标快照">
        <NCard size="small">
          <NSpace align="center" style="margin-bottom: 12px">
            <span>参考日期</span>
            <NDatePicker v-model:value="refDate" type="date" @update:value="loadSnapshotsForDate" />
            <NButton type="primary" :loading="loading" @click="saveSnapshots">保存当日全部指标</NButton>
          </NSpace>
          <p class="hint">修改各 Skill 在选定日期的 install/star 代理值。保存后会写入 skill_metric_snapshots 并同步 install_count。</p>
          <NDataTable
            :columns="snapshotColumns"
            :data="skills"
            :row-key="(r: any) => r.id"
            size="small"
          />
        </NCard>

        <NCard title="批量生成时间线（验证 7 日增速）" size="small" style="margin-top: 12px">
          <NSpace vertical>
            <NSelect
              v-model:value="timelineSkillId"
              :options="skills.map((s) => ({ label: `${s.name} (#${s.id})`, value: s.id }))"
              placeholder="选择 Skill"
              filterable
            />
            <NDatePicker v-model:value="timelineStart" type="date" />
            <NInput v-model:value="timelineValues" placeholder="逗号分隔每日指标，如 10,20,35,50,80,120,200,320" />
            <NButton :loading="loading" @click="generateTimeline">生成连续日快照</NButton>
          </NSpace>
        </NCard>

        <NCard v-if="snapshotDates.length" title="已有快照日期" size="small" style="margin-top: 12px">
          <NSpace>
            <NTag v-for="d in snapshotDates" :key="d">{{ d }}</NTag>
          </NSpace>
        </NCard>
      </NTabPane>

      <NTabPane name="simulate" tab="模拟推送">
        <NCard size="small">
          <NSpace align="center">
            <span>模拟日期</span>
            <NDatePicker v-model:value="simDate" type="date" />
            <span>Top N</span>
            <NInputNumber v-model:value="topN" :min="1" :max="30" />
            <NButton type="primary" :loading="loading" @click="runSimulate">运行模拟推送</NButton>
          </NSpace>
        </NCard>

        <template v-if="simResult">
          <NCard title="指标就绪状态" size="small" style="margin-top: 12px">
            <p>{{ simResult.metrics_readiness?.message }}</p>
            <NSpace>
              <NTag :type="simResult.metrics_readiness?.full_7d_ready ? 'success' : 'warning'">
                7日历史: {{ simResult.metrics_readiness?.candidates_with_7d_history }}/{{ simResult.metrics_readiness?.total_candidates }}
              </NTag>
              <NTag>1日: {{ simResult.metrics_readiness?.candidates_with_1d_history }}</NTag>
              <NTag>3日: {{ simResult.metrics_readiness?.candidates_with_3d_history }}</NTag>
            </NSpace>
          </NCard>

          <NCard title="推送 Markdown 预览" size="small" style="margin-top: 12px">
            <pre class="md-preview">{{ simResult.content_md }}</pre>
          </NCard>

          <NCard title="选榜过程" size="small" style="margin-top: 12px">
            <NCollapse>
              <NCollapseItem
                v-for="(step, i) in simResult.selection_steps"
                :key="i"
                :title="`${step.slot} · 池 ${step.pool} · 目标 ${step.target_count} · 选中 ${step.picked_skill_ids?.length}`"
              >
                <pre>{{ JSON.stringify(step, null, 2) }}</pre>
              </NCollapseItem>
            </NCollapse>
          </NCard>

          <NCard title="Top10 详细评分追踪" size="small" style="margin-top: 12px">
            <NCollapse accordion>
              <NCollapseItem
                v-for="pick in simResult.picks"
                :key="pick.rank"
                :title="`#${pick.rank} ${pick.name} · 总分 ${pick.score?.total} · 槽位 ${pick.slot}`"
              >
                <h4>增长指标</h4>
                <pre>{{ JSON.stringify(pick.growth, null, 2) }}</pre>
                <h4>评分明细</h4>
                <pre>{{ JSON.stringify(pick.score, null, 2) }}</pre>
              </NCollapseItem>
            </NCollapse>
          </NCard>

          <NCard title="全部候选池评分明细" size="small" style="margin-top: 12px">
            <NCollapse>
              <NCollapseItem
                v-for="c in simResult.candidates"
                :key="c.skill_id"
                :title="`${c.name} · 池 ${c.pools?.join(',')} · 总分 ${c.score?.total}`"
              >
                <pre>{{ JSON.stringify(c, null, 2) }}</pre>
              </NCollapseItem>
            </NCollapse>
          </NCard>
        </template>
      </NTabPane>

      <NTabPane name="platforms" tab="模拟平台">
        <NDataTable
          :columns="[
            { title: 'ID', key: 'id' },
            { title: '厂商', key: 'vendor' },
            { title: '名称', key: 'name' },
            { title: 'Adapter', key: 'adapter' },
          ]"
          :data="platforms"
          size="small"
        />
      </NTabPane>
    </NTabs>
  </div>
</template>

<style scoped>
.page {
  padding: 20px 24px;
  max-width: 1200px;
}
.page-header h1 {
  margin: 0 0 4px;
  font-size: 20px;
}
.page-header p {
  color: #646a73;
  margin: 0 0 12px;
}
.hint {
  color: #8f959e;
  font-size: 13px;
  margin-bottom: 12px;
}
.md-preview {
  white-space: pre-wrap;
  font-size: 12px;
  max-height: 400px;
  overflow: auto;
  background: #f5f6f7;
  padding: 12px;
  border-radius: 6px;
}
pre {
  font-size: 11px;
  overflow: auto;
  max-height: 360px;
}
h4 {
  margin: 8px 0 4px;
  font-size: 13px;
}
</style>
