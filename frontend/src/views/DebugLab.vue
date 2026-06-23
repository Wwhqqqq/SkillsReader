<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NButton, NSelect, NInput, useMessage } from 'naive-ui'
import { api } from '../api/client'

const message = useMessage()
const sources = ref<any[]>([])
const probeSource = ref<string | null>(null)
const probeResult = ref<any>(null)
const diagnosis = ref<any>(null)
const fpVendor = ref('美团')
const fpSource = ref('meituan_ai_hub')
const fpExternal = ref('test-1')
const fpName = ref('测试Skill')
const fpResult = ref('')
const enrichSkillId = ref('')

onMounted(async () => {
  sources.value = await api.sources()
  if (sources.value.length) probeSource.value = sources.value[0].id
})

async function runProbe() {
  if (!probeSource.value) return
  probeResult.value = await api.adapterProbe(probeSource.value)
}

async function runDiagnosis() {
  diagnosis.value = await api.digestDiagnosis()
}

async function calcFp() {
  const base = `/api/debug/fingerprint?vendor=${encodeURIComponent(fpVendor.value)}&source_id=${encodeURIComponent(fpSource.value)}&external_id=${encodeURIComponent(fpExternal.value)}&name=${encodeURIComponent(fpName.value)}`
  fpResult.value = JSON.stringify(await fetch(base).then((r) => r.json()), null, 2)
}

async function runEnrich() {
  const id = parseInt(enrichSkillId.value, 10)
  if (!id) return
  const res = await api.llmEnrich(id)
  message.success(res.summary || '完成')
}
</script>

<template>
  <div class="page">
    <div class="page-title">研究调试台</div>

    <div class="panel">
      <div class="panel-header">Adapter 探针</div>
      <div style="display: flex; gap: 8px; margin-bottom: 12px">
        <NSelect
          v-model:value="probeSource"
          :options="sources.map((s) => ({ label: `${s.vendor} · ${s.name}`, value: s.id }))"
          style="width: 320px"
        />
        <NButton @click="runProbe">执行 fetch</NButton>
      </div>
      <pre v-if="probeResult" class="md-preview">{{ JSON.stringify(probeResult, null, 2) }}</pre>
    </div>

    <div class="panel">
      <div class="panel-header">
        <span>精选诊断</span>
        <NButton size="small" @click="runDiagnosis">运行</NButton>
      </div>
      <pre v-if="diagnosis" class="md-preview">{{ JSON.stringify(diagnosis, null, 2) }}</pre>
    </div>

    <div class="panel">
      <div class="panel-header">指纹计算器</div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px">
        <NInput v-model:value="fpVendor" placeholder="vendor" />
        <NInput v-model:value="fpSource" placeholder="source_id" />
        <NInput v-model:value="fpExternal" placeholder="external_id" />
        <NInput v-model:value="fpName" placeholder="name" />
      </div>
      <NButton size="small" @click="calcFp">计算</NButton>
      <pre v-if="fpResult" class="md-preview" style="margin-top: 8px">{{ fpResult }}</pre>
    </div>

    <div class="panel">
      <div class="panel-header">LLM 描述试跑</div>
      <div style="display: flex; gap: 8px">
        <NInput v-model:value="enrichSkillId" placeholder="Skill ID" style="width: 120px" />
        <NButton @click="runEnrich">生成描述</NButton>
      </div>
    </div>
  </div>
</template>
