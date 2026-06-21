<script setup>
import { useI18n } from 'vue-i18n'
import { ref, computed } from 'vue'
import {
  NButton, NInput, NDivider, useMessage,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

const { t } = useI18n()
const message = useMessage()

// ── Props ──
const props = defineProps({
  visible: { type: Boolean, default: true },
  isMobile: { type: Boolean, default: false },
  workspaces: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:visible', 'select-ws', 'select-report', 'hide', 'generate'])

const accentColors = ['#6366f1', '#8b5cf6', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899']
function cardAccent(idx) {
  return accentColors[idx % accentColors.length]
}

// ── 状态 ──
const reports = ref([])
const selectedWs = ref(null)
const searchQuery = ref('')

// ── 过滤 ──
const filteredWorkspaces = computed(() => {
  if (!searchQuery.value) return props.workspaces
  const q = searchQuery.value.toLowerCase()
  return props.workspaces.filter((w) => w.name.toLowerCase().includes(q))
})

const filteredReports = computed(() => {
  if (!searchQuery.value) return reports.value
  const q = searchQuery.value.toLowerCase()
  return reports.value.filter((r) => r.name.toLowerCase().includes(q))
})

// ── 加载 ──
async function loadReports() {
  if (!selectedWs.value) return
  try {
    const res = await api.getReportList({ workspace_id: selectedWs.value.id })
    reports.value = res.data || []
  } catch (e) { message.error(t('views.statistic-center.message_cn_8fc82eb8')) }
}

// ── 选择 ──
function selectWorkspace(ws) {
  selectedWs.value = ws
  searchQuery.value = ''
  reports.value = []
  emit('select-ws', ws)
  loadReports()
}

function selectReport(r) {
  emit('select-report', r)
  // 选中报告后自动隐藏侧边栏
  emit('update:visible', false)
  emit('hide')
}

function backToWorkspaces() {
  selectedWs.value = null
  reports.value = []
  searchQuery.value = ''
}

function handleClose() {
  emit('update:visible', false)
  emit('hide')
}

function handleGenerate() {
  emit('generate')
}

// ── 暴露 ──
defineExpose({ loadReports })
</script>

<template>
  <div
    v-show="visible"
    class="doc-sidebar"
  >
    <!-- 移动端关闭按钮 -->
    <div v-if="isMobile" class="flex justify-end mb-2">
      <NButton size="tiny" quaternary @click="handleClose">
        <TheIcon icon="material-symbols:close" :size="18" />
      </NButton>
    </div>

    <!-- 面板头部 -->
    <div class="sidebar-header">
      <div class="flex items-center justify-between mb-3">
        <span class="header-label">{{ $t('views.statistic-center.title_cn_c56cb26a') }}</span>
        <span class="header-count">{{ selectedWs ? reports.length : props.workspaces.length }}</span>
      </div>
      <NInput
        v-model:value="searchQuery"
        :placeholder="selectedWs ? t('views.statistic-center.placeholder_cn_d37f5b56') : t('views.statistic-center.placeholder_cn_a466ba6b')"
        clearable
        size="small"
        class="search-box"
      >
        <template #prefix>
          <TheIcon icon="material-symbols:search" :size="16" class="text-gray-400" />
        </template>
      </NInput>
      <NButton type="primary" block @click="handleGenerate" class="generate-btn" size="large">
        <TheIcon icon="material-symbols:smart-toy" :size="20" class="mr-1" />{{ t('views.statistic-center.title_cn_ca40d85d') }}
      </NButton>
    </div>

    <!-- 工作区列表（未选中时） -->
    <div v-if="!selectedWs" class="card-list">
      <div
        v-for="(ws, idx) in filteredWorkspaces"
        :key="ws.id"
        class="sidebar-card"
        @click="selectWorkspace(ws)"
      >
        <div class="card-avatar" :style="{ background: cardAccent(idx) }">
          {{ ws.name.charAt(0) }}
        </div>
        <div class="card-body">
          <div class="card-title">{{ ws.name }}</div>
          <div class="card-meta">
            <span>{{ ws.updated_at?.slice(0, 10) }}</span>
            <span v-if="ws.users?.length" class="card-stat">
              <TheIcon icon="material-symbols:group" :size="13" class="mr-0.5" />{{ ws.users.length }}
            </span>
          </div>
        </div>
        <TheIcon icon="material-symbols:chevron-right" :size="18" class="text-gray-400 flex-shrink-0" />
      </div>
      <div v-if="!filteredWorkspaces.length" class="empty-state">
        <TheIcon icon="material-symbols:inbox-outline" :size="40" class="text-gray-300 dark:text-gray-600 mb-3" />
        <p class="text-sm text-gray-400">
          {{ searchQuery ? t('views.statistic-center.label_cn_f63f56b1') : t('views.statistic-center.label_cn_c3e99070') }}
        </p>
      </div>
    </div>

    <!-- 报告列表（选中工作区后，带面包屑） -->
    <div v-else class="card-list">
      <!-- 面包屑 -->
      <div class="breadcrumb-row">
        <NButton size="tiny" quaternary @click="backToWorkspaces">
          <TheIcon icon="material-symbols:folder" :size="15" class="mr-1" />{{ t('views.statistic-center.label_cn_4fa8c1a3') }}
        </NButton>
        <span class="breadcrumb-sep">›</span>
        <span class="breadcrumb-current">{{ selectedWs.name }}</span>
      </div>
      <NDivider style="margin: 8px 0" />
      <div class="section-label">{{ t('views.statistic-center.message_cn_a6a1c93e', { count: reports.length }) }}</div>
      <div
        v-for="(r, idx) in filteredReports"
        :key="r.id"
        class="sidebar-card"
        @click="selectReport(r)"
      >
        <div class="card-avatar" :style="{ background: cardAccent(idx) }">
          {{ r.name.charAt(0) }}
        </div>
        <div class="card-body">
          <div class="card-title">{{ r.name }}</div>
          <div class="card-meta">
            <span>{{ r.updated_at?.slice(0, 10) }}</span>
          </div>
        </div>
        <TheIcon icon="material-symbols:chevron-right" :size="18" class="text-gray-400 flex-shrink-0" />
      </div>
      <div v-if="!filteredReports.length && !searchQuery" class="empty-state">
        <TheIcon icon="material-symbols:description-outline" :size="40" class="text-gray-300 dark:text-gray-600 mb-3" />
        <p class="text-sm text-gray-400">{{ t('views.statistic-center.label_cn_48ea44d0') }}</p>
      </div>
      <div v-if="!filteredReports.length && searchQuery" class="empty-state">
        <TheIcon icon="material-symbols:search-off" :size="40" class="text-gray-300 dark:text-gray-600 mb-3" />
        <p class="text-sm text-gray-400">{{ t('views.statistic-center.label_cn_d85571de') }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.doc-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-right: 1px solid var(--n-border-color);
  background: var(--n-color);
  overflow: hidden;
}

.sidebar-header {
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--n-border-color);
  flex-shrink: 0;
}

.header-label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--n-text-color-3);
}

.header-count {
  font-size: 11px;
  font-weight: 600;
  color: var(--n-text-color-3);
  background: var(--n-color-embedded);
  padding: 1px 8px;
  border-radius: 999px;
}

.search-box {
  margin-bottom: 12px;
}

.generate-btn {
  border-radius: 10px !important;
  font-weight: 600 !important;
  transition: all 0.2s;
}
.generate-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
}

.card-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

.sidebar-card {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 4px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 1px solid transparent;
}
.sidebar-card:hover {
  background: var(--n-color-hover);
  border-color: var(--n-border-color);
}

.card-avatar {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 700;
  font-size: 15px;
  flex-shrink: 0;
  margin-right: 10px;
  transition: transform 0.2s;
}

.card-body {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--n-text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 3px;
  font-size: 12px;
  color: var(--n-text-color-3);
}

.card-stat {
  display: flex;
  align-items: center;
}

/* 面包屑 */
.breadcrumb-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
  font-size: 13px;
}

.breadcrumb-sep {
  color: var(--n-text-color-3);
  font-size: 16px;
  margin: 0 2px;
}

.breadcrumb-current {
  font-weight: 600;
  color: var(--n-text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--n-text-color-3);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  padding: 4px 4px 6px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

/* 字体覆盖 */
.text-xs { font-size: 12px !important; line-height: 16px !important; }
.text-sm { font-size: 14px !important; line-height: 20px !important; }
.text-base { font-size: 16px !important; line-height: 24px !important; }
.text-lg { font-size: 18px !important; line-height: 26px !important; }
.text-xl { font-size: 20px !important; line-height: 28px !important; }
</style>
