<script setup>
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import { watch, onMounted, ref } from 'vue'
import {
  NButton, NInput,
  NModal, NSpace, NSelect, NPopconfirm,
  NForm, NFormItem,
  NSpin, NTabs, NTabPane,
  useMessage,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import { createDataWorkbenchState } from '@/composables/useDataWorkbench'

import ExcelTab from './ExcelTab.vue'
import DocumentsTab from './DocumentsTab.vue'
import DatabaseTab from './DatabaseTab.vue'
import StaticFilesTab from './StaticFilesTab.vue'

const { t } = useI18n()
defineOptions({ name: i18n.global.t('views.statistic-center.title_cn_aad781ad') })

const message = useMessage()

const db = createDataWorkbenchState()
const {
  isMobileCollapsed, sidebarVisible,
  workspaces, selectedWs, userOptions, loading,
  searchQuery, filteredWorkspaces,
  showWsModal, wsModalForm, wsEditing,
  formatFileSize, wsAccent,
  loadWorkspaces, loadUserOptions,
  openCreateWs, openEditWs, handleWsSubmit, deleteWorkspace,
} = db

watch(isMobileCollapsed, (mobile) => {
  if (mobile) sidebarVisible.value = false
})

const activeDataSource = ref('excel')
const dataSourceTabs = [
  { name: 'excel', label: t('views.statistic-center.label_cn_a7d53e8d'), icon: 'material-symbols:table' },
  { name: 'documents', label: t('views.statistic-center.label_cn_c35ee691'), icon: 'material-symbols:description' },
  { name: 'database', label: t('views.statistic-center.label_cn_5bac3fe5'), icon: 'material-symbols:database' },
  { name: 'static-files', label: t('views.statistic-center.label_cn_6856e820'), icon: 'material-symbols:folder' },
]

const excelTabRef = ref(null)
const documentsTabRef = ref(null)
const databaseTabRef = ref(null)
const staticFilesTabRef = ref(null)

async function selectWorkspace(ws) {
  selectedWs.value = ws
  sidebarVisible.value = false
}

onMounted(() => loadWorkspaces())
</script>

<template>
  <div class="flex" :class="{ 'mobile-root': isMobileCollapsed }" style="height: calc(100vh - 120px)">
    <!-- ── 左侧工作区列表 ── -->
    <div
      v-show="sidebarVisible"
      class="data-sidebar"
      :class="{ 'mobile-overlay': isMobileCollapsed }"
      :style="isMobileCollapsed ? '' : 'width: 300px; flex-shrink: 0'"
    >
      <div class="sidebar-header">
        <div class="flex items-center justify-between mb-3">
          <span class="header-label">{{ $t('views.statistic-center.title_cn_aad781ad') }}</span>
          <div class="flex items-center gap-2">
            <span class="header-count">{{ workspaces.length }}</span>
            <NButton v-if="!isMobileCollapsed" size="tiny" quaternary @click="sidebarVisible = false" class="sidebar-toggle-btn">
              <TheIcon icon="material-symbols:chevron-left" :size="16" />
            </NButton>
            <div v-if="isMobileCollapsed" class="mobile-close-btn" @click="sidebarVisible = false">
              <TheIcon icon="material-symbols:close" :size="20" />
            </div>
          </div>
        </div>
        <NInput
          v-model:value="searchQuery"
          :placeholder="t('views.statistic-center.placeholder_cn_a466ba6b')"
          clearable
          size="small"
          class="search-box"
        >
          <template #prefix>
            <TheIcon icon="material-symbols:search" :size="16" class="text-gray-400" />
          </template>
        </NInput>
        <NButton type="primary" block @click="openCreateWs" class="create-btn" size="large">
          <TheIcon icon="material-symbols:add" :size="20" class="mr-1" />{{ t('views.statistic-center.label_cn_9cb11943') }}
        </NButton>
      </div>

      <div class="card-list">
        <div
          v-for="(ws, idx) in filteredWorkspaces"
          :key="ws.id"
          class="sidebar-card"
          :class="{ 'sidebar-card--active': selectedWs?.id === ws.id }"
          @click="selectWorkspace(ws)"
        >
          <div class="card-avatar" :style="{ background: wsAccent(idx) }">
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
    </div>

    <!-- ── 右侧数据源区域 ── -->
    <div class="flex-1 min-w-0 overflow-hidden flex flex-col" :class="{ 'mobile-content': isMobileCollapsed }" :style="isMobileCollapsed ? '' : 'padding: 16px'">
      <!-- 桌面端：侧边栏收起时的边栏拉手 -->
      <div
        v-if="!sidebarVisible && !isMobileCollapsed"
        class="sidebar-pull-handle"
        @click="sidebarVisible = true"
        :title="$t('views.statistic-center.label_cn_9cb11943')"
      >
        <TheIcon icon="material-symbols:chevron-right" :size="18" />
      </div>

      <!-- 侧边栏收起时浮动展开按钮（右下角） -->
      <div
        v-if="!sidebarVisible"
        class="mobile-menu-btn"
        @click="sidebarVisible = true"
      >
        <TheIcon icon="material-symbols:menu" :size="26" />
      </div>

      <NSpin :show="loading">
        <div v-if="!selectedWs" class="flex items-center justify-center h-full text-gray-400 text-lg">
          {{ t('views.statistic-center.label_cn_aba2706f') }}
        </div>

        <div v-else class="h-full flex flex-col">
          <!-- 工作区标题栏 -->
          <div class="flex items-center justify-between mb-4" :class="{ 'mobile-ws-header': isMobileCollapsed }">
            <div class="flex items-center gap-3">
              <div>
                <h2 class="text-xl font-bold m-0">{{ selectedWs.name }}</h2>
                <p v-if="selectedWs.description" class="text-gray-500 text-sm m-0 mt-1">{{ selectedWs.description }}</p>
              </div>
            </div>
            <NSpace>
              <NButton size="small" @click="openEditWs">
                <TheIcon icon="material-symbols:edit" :size="18" class="mr-1" />{{ t('views.statistic-center.label_cn_24d67862') }}
              </NButton>
              <NPopconfirm @positive-click="deleteWorkspace">
                <template #trigger>
                  <NButton size="small" type="error">
                    <TheIcon icon="material-symbols:delete-outline" :size="18" class="mr-1" />{{ t('views.statistic-center.label_cn_2f4aaddd') }}
                  </NButton>
                </template>
                {{ t('views.statistic-center.label_cn_9f1f93b6') }}
              </NPopconfirm>
            </NSpace>
          </div>

          <!-- 数据源 Tab 切换 -->
          <NTabs v-model:value="activeDataSource" type="card" class="flex-1 flex flex-col" style="min-height: 0; overflow: hidden">
            <NTabPane v-for="tab in dataSourceTabs" :key="tab.name" :name="tab.name">
              <template #tab>
                <TheIcon :icon="tab.icon" :size="18" class="mr-2" />{{ tab.label }}
              </template>

              <ExcelTab v-if="tab.name === 'excel'" ref="excelTabRef" />
              <DocumentsTab v-else-if="tab.name === 'documents'" ref="documentsTabRef" />
              <DatabaseTab v-else-if="tab.name === 'database'" ref="databaseTabRef" />
              <StaticFilesTab v-else-if="tab.name === 'static-files'" ref="staticFilesTabRef" />
            </NTabPane>
          </NTabs>
        </div>
      </NSpin>
    </div>
  </div>

  <!-- ── 工作区弹窗（共享） ── -->
  <NModal v-model:show="showWsModal" :title="wsEditing ? '编辑工作区' : t('views.statistic-center.title_cn_9cb11943')" preset="card" style="width: 500px">
    <NForm :model="wsModalForm" label-placement="top">
      <NFormItem :label="t('views.network.region.formLabels.name')" required>
        <NInput v-model:value="wsModalForm.name" :placeholder="t('views.statistic-center.placeholder_cn_042874e1')" />
      </NFormItem>
      <NFormItem :label="t('views.statistic-center.label_cn_3bdd08ad')">
        <NInput v-model:value="wsModalForm.description" :placeholder="t('views.statistic-center.label_cn_3bdd08ad')" type="textarea" />
      </NFormItem>
      <NFormItem :label="t('views.skill.label_cn_5f07f1ad')">
        <NSelect v-model:value="wsModalForm.user_ids" :options="userOptions" multiple :placeholder="t('views.statistic-center.placeholder_cn_6674b18c')" filterable />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showWsModal = false">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton>
        <NButton type="primary" @click="handleWsSubmit">{{ t('views.statistic-center.label_cn_e83a256e') }}</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
/*
  全局 html { font-size: 4px } 导致 UnoCSS 的 text-* 类（基于 rem）
  实际渲染只有预期的 1/4。此处用 px 覆盖 font-size 和 line-height。
*/
.text-xs { font-size: 12px !important; line-height: 16px !important; }
.text-sm { font-size: 14px !important; line-height: 20px !important; }
.text-base { font-size: 16px !important; line-height: 24px !important; }
.text-lg { font-size: 18px !important; line-height: 26px !important; }
.text-xl { font-size: 20px !important; line-height: 28px !important; }

/* ======== 侧边栏样式（与 DocWorkbenchSidebar 一致） ======== */

.data-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  border-right: 1px solid var(--n-border-color);
  background: var(--n-color);
}

.sidebar-header {
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--n-border-color);
  flex-shrink: 0;
}

.sidebar-toggle-btn {
  margin-right: -4px;
  opacity: 0.5;
}
.sidebar-toggle-btn:hover {
  opacity: 1;
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

.create-btn {
  border-radius: 10px !important;
  font-weight: 600 !important;
  transition: all 0.2s;
}
.create-btn:hover {
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
.sidebar-card--active {
  background: var(--n-color-embedded);
  border-color: var(--primary-color-hover);
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

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

/* 侧边栏收起时的边栏拉手 */
.sidebar-pull-handle {
  position: absolute;
  top: 50%;
  left: 0;
  transform: translateY(-50%);
  width: 24px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
  background: var(--n-color-embedded);
  border: 1px solid var(--n-border-color);
  border-left: none;
  border-radius: 0 8px 8px 0;
  color: var(--n-text-color-3);
  transition: width 0.15s, color 0.15s;
}
.sidebar-pull-handle:hover {
  width: 28px;
  color: var(--primary-color);
}

/* ======== 移动端响应式 ======== */

.mobile-root {
  position: relative;
}

/* 汉堡菜单按钮 */
.mobile-menu-btn {
  position: fixed;
  bottom: 24px;
  right: 20px;
  z-index: 100;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--primary-color);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(0,0,0,0.25);
  transition: transform 0.2s, box-shadow 0.2s;
}
.mobile-menu-btn:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 20px rgba(0,0,0,0.3);
}

/* 侧边栏：移动端全屏浮层 */
.mobile-overlay {
  position: absolute !important;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100% !important;
  z-index: 200;
  border-right: none !important;
  box-shadow: 4px 0 24px rgba(0,0,0,0.15);
}
.mobile-overlay .sidebar-header {
  padding-top: env(safe-area-inset-top, 16px);
}

.mobile-close-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--n-color-embedded);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--n-text-color-3);
  transition: background 0.15s;
  flex-shrink: 0;
}
.mobile-close-btn:hover {
  background: var(--n-color-hover);
  color: var(--n-text-color);
}

/* 工作区标题栏：移动端换行 */
.mobile-ws-header {
  flex-wrap: wrap !important;
  gap: 10px !important;
}
.mobile-ws-header > div:last-child {
  width: 100%;
  display: flex;
  justify-content: flex-end;
}

/* Excel 双栏堆叠 */
.mobile-stack {
  flex-direction: column !important;
}

/* Tab 标签在移动端缩小间距 */
@media (max-width: 990px) {
  :deep(.n-tabs .n-tabs-tab) {
    padding: 6px 10px !important;
    font-size: 13px !important;
  }
}

/* 修复 NSpin 容器阻断 flex 链条 */
:deep(.n-spin-container) {
  display: flex;
  flex-direction: column;
}
:deep(.n-spin-content) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* 修复 NTabs 根元素 flex 列布局 + pane-wrapper 高度约束 */
:deep(.n-tabs) {
  flex: 1 !important;
  min-height: 0 !important;
}
:deep(.n-tabs-pane-wrapper) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
:deep(.n-tab-pane) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* 移动端右侧内容区 */
.mobile-content {
  padding: 10px !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  -webkit-overflow-scrolling: touch;
}

/* 移动端双栏堆叠 */
.mobile-stack > * {
  flex: none !important;
  width: 100% !important;
  max-height: 45vh;
}

/* 移动端：弹窗全宽 */
@media (max-width: 990px) {
  :deep(.n-modal) {
    width: 95vw !important;
    max-width: 95vw !important;
  }
}

/* 移动端：上传区缩小 */
@media (max-width: 990px) {
  .upload-dragger-mobile :deep(.n-upload-dragger) {
    padding: 12px 8px !important;
  }
}
</style>
