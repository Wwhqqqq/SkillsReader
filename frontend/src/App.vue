<script setup lang="ts">
import {
  NConfigProvider,
  NLayout,
  NLayoutSider,
  NLayoutContent,
  NMenu,
  NIcon,
  NMessageProvider,
  lightTheme,
} from 'naive-ui'
import { computed, h } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import {
  PulseOutline,
  RadioOutline,
  GridOutline,
  TrophyOutline,
  SendOutline,
  BugOutline,
  FlaskOutline,
} from '@vicons/ionicons5'

const route = useRoute()
const router = useRouter()

function icon(comp: object) {
  return () => h(NIcon, null, { default: () => h(comp) })
}

const menuOptions = [
  { label: '总览', key: '/', icon: icon(PulseOutline) },
  { label: '实时扫描', key: '/live', icon: icon(RadioOutline) },
  { label: '采集源', key: '/sources', icon: icon(GridOutline) },
  { label: '精选', key: '/rankings', icon: icon(TrophyOutline) },
  { label: '推送', key: '/push', icon: icon(SendOutline) },
  { label: '测试平台', key: '/testbench', icon: icon(FlaskOutline) },
  { label: '调试', key: '/debug', icon: icon(BugOutline) },
]

const activeKey = computed(() => route.path)

const contentStyle = {
  minHeight: '100vh',
  background: 'var(--color-bg)',
  overflow: 'auto',
}
</script>

<template>
  <NConfigProvider :theme="lightTheme">
    <NMessageProvider>
      <NLayout has-sider style="height: 100vh">
        <NLayoutSider
          bordered
          collapse-mode="width"
          :collapsed-width="0"
          :width="200"
          :native-scrollbar="false"
          style="background: #ffffff"
        >
          <div class="sidebar-title">SkillGetter</div>
          <NMenu
            :value="activeKey"
            :options="menuOptions"
            @update:value="(k: string) => router.push(k)"
          />
        </NLayoutSider>
        <NLayoutContent :content-style="contentStyle">
          <RouterView />
        </NLayoutContent>
      </NLayout>
    </NMessageProvider>
  </NConfigProvider>
</template>

<style scoped>
.sidebar-title {
  padding: 16px;
  font-size: 14px;
  font-weight: 600;
  border-bottom: 1px solid #d9dde4;
  color: #1f2329;
}
</style>
