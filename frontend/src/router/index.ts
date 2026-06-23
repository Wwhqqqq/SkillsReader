import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('@/views/Dashboard.vue') },
    { path: '/live', name: 'live', component: () => import('@/views/LiveScan.vue') },
    { path: '/sources', name: 'sources', component: () => import('@/views/Sources.vue') },
    { path: '/rankings', name: 'rankings', component: () => import('@/views/Rankings.vue') },
    { path: '/push', name: 'push', component: () => import('@/views/PushConsole.vue') },
    { path: '/testbench', name: 'testbench', component: () => import('@/views/TestBench.vue') },
    { path: '/debug', name: 'debug', component: () => import('@/views/DebugLab.vue') },
  ],
})

export default router
