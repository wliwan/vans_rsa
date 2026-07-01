<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import {


  NButton, NCard, NDataTable, NModal, NPopconfirm,
  NSpace, NSpin, NTag, NUpload,
  NBreadcrumb, NBreadcrumbItem, NInput,
  useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import { useTaskProgressStore } from '@/store/modules/taskProgress'
import { getToken } from '@/utils'
const { t } = useI18n()

import api from '@/api'

defineOptions({ name: i18n.global.t('views.network.regionBoundary.title') })

const message = useMessage()

// ── 级联列表 ──
const breadcrumb = ref([])
const currentList = ref([])
const currentLoading = ref(false)
const currentSearch = ref('')

const selectedNode = computed(() =>
  breadcrumb.value.length > 0 ? breadcrumb.value[breadcrumb.value.length - 1] : null
)

const currentLevelLabel = computed(() => {
  if (breadcrumb.value.length === 0) return t('views.network.regionBoundary.levelLabel.country')
  if (breadcrumb.value.length === 1) return t('views.network.regionBoundary.levelLabel.state')
  return t('views.network.regionBoundary.levelLabel.city')
})

// ── 边界文件 ──
const boundaryStatus = ref({ has_boundary: false, count: 0, files: [] })
const boundaryLoading = ref(false)
const downloadLoading = ref(false)
const showUploadModal = ref(false)
const showLeftPanel = ref(true)  // 移动端左面板展开控制

const uploadUrl = computed(() =>
  `${import.meta.env.VITE_BASE_API}/region/region-boundary/upload?region_id=${selectedNode.value?.id || ''}`
)
const uploadHeaders = computed(() => ({
  token: getToken() || '',
}))

const typeColorMap = { COUNTRY: '#2080f0', STATE: '#18a058', CITY: '#f0a020' }

onMounted(resetToRoot)

function resetToRoot() {
  breadcrumb.value = []
  boundaryStatus.value = { has_boundary: false, count: 0, files: [] }
  loadCurrentLevel()
}

// ── 加载当前层级 ──
async function loadCurrentLevel() {
  currentLoading.value = true
  currentSearch.value = ''
  try {
    if (breadcrumb.value.length === 0) {
      const res = await api.getRegionList({ region_type: 'COUNTRY', page_size: 500, is_active: true })
      currentList.value = (res.data || []).map(item => ({ ...item, has_children: true }))
    } else {
      const parentId = breadcrumb.value[breadcrumb.value.length - 1].id
      const res = await api.getRegionChildren(parentId)
      currentList.value = res.data || []
    }
  } catch (e) {
    currentList.value = []
  } finally {
    currentLoading.value = false
  }
}

const filteredList = computed(() => {
  if (!currentSearch.value) return currentList.value
  const s = currentSearch.value.toLowerCase()
  return currentList.value.filter(item =>
    (item.name || '').toLowerCase().includes(s) ||
    (item.local_name || '').toLowerCase().includes(s) ||
    (item.code || '').toLowerCase().includes(s)
  )
})

// ── 点击行 → 进入子层级并加载边界文件状态 ──
function onClickRow(row) {
  breadcrumb.value.push({ id: row.id, name: row.name, localName: row.local_name || '', type: row.region_type || '' })
  loadCurrentLevel()
  loadBoundaryStatus(row.id)
}

function backToLevel(index) {
  breadcrumb.value = breadcrumb.value.slice(0, index)
  if (breadcrumb.value.length > 0) {
    loadBoundaryStatus(breadcrumb.value[breadcrumb.value.length - 1].id)
  } else {
    boundaryStatus.value = { has_boundary: false, count: 0, files: [] }
  }
  loadCurrentLevel()
}

// ── 边界文件操作 ──
async function loadBoundaryStatus(regionId) {
  boundaryLoading.value = true
  try {
    const res = await api.getBoundaryStatus(regionId)
    boundaryStatus.value = res.data || { has_boundary: false, count: 0, files: [] }
  } catch (e) {
    boundaryStatus.value = { has_boundary: false, count: 0, files: [] }
  } finally {
    boundaryLoading.value = false
  }
}

async function onDownload() {
  if (!selectedNode.value) return
  downloadLoading.value = true

  const taskStore = useTaskProgressStore()
  const nodeName = selectedNode.value.localName
    ? `${selectedNode.value.name}（${selectedNode.value.localName}）`
    : selectedNode.value.name
  const taskId = taskStore.startTask(t('views.network.regionBoundary.task.downloadName', { name: nodeName }))

  let simProgress = 10
  const simTimer = setInterval(() => {
    if (simProgress < 85) {
      simProgress += 5
      taskStore.updateProgress(taskId, { progress: simProgress, message: t('views.network.regionBoundary.task.downloading') })
    }
  }, 600)

  try {
    await api.downloadBoundary({ region_id: selectedNode.value.id, file_type: 'GEOJSON' })
    clearInterval(simTimer)
    taskStore.finishTask(taskId, t('views.network.regionBoundary.task.complete'))
    message.success(t('views.network.regionBoundary.messages.downloadSuccess'))
    loadBoundaryStatus(selectedNode.value.id)
  } catch (e) {
    clearInterval(simTimer)
    const errMsg = e?.response?.data?.msg || e?.message || t('views.network.label_cn_65e200d3')
    taskStore.failTask(taskId, { message: t('views.network.regionBoundary.task.fail'), detail: errMsg })
    message.error(t('views.network.regionBoundary.messages.downloadFailTip'))
  } finally {
    downloadLoading.value = false
  }
}

function onUploadFinish({ file }) {
  if (file.status === 'finished') {
    message.success(t('views.network.regionBoundary.messages.uploadSuccess'))
    showUploadModal.value = false
    loadBoundaryStatus(selectedNode.value?.id)
  }
}

async function onDeleteFile(row) {
  try {
    await api.deleteBoundary({ boundary_id: row.id })
    message.success(t('views.network.regionBoundary.messages.deleteSuccess'))
    loadBoundaryStatus(selectedNode.value?.id)
  } catch (e) { message.error(t('views.network.regionBoundary.messages.deleteFail')) }
}

async function onClearAll() {
  if (!selectedNode.value) return
  try {
    const res = await api.clearBoundaries({ region_id: selectedNode.value.id })
    message.success(t('views.network.regionBoundary.messages.clearSuccess', { count: res.data?.deleted || 0 }))
    loadBoundaryStatus(selectedNode.value.id)
  } catch (e) { message.error(t('views.network.regionBoundary.messages.clearFail')) }
}

function onExportFile(row) {
  api.downloadBoundaryFile({ boundary_id: row.id }).then((res) => {
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = row.file_name || 'boundary.geojson'
    a.click()
    URL.revokeObjectURL(url)
  }).catch(() => message.error(t('views.network.regionBoundary.messages.exportFail')))
}

const statusMap = {
  SUCCESS: { type: 'success' },
  DOWNLOADING: { type: 'warning' },
  FAILED: { type: 'error' },
  PENDING: { type: 'default' },
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const fileColumns = [
  { title: t('views.network.regionBoundary.fileColumns.fileName'), key: 'file_name', ellipsis: { tooltip: true }, width: 180 },
  { title: t('views.network.regionBoundary.fileColumns.fileType'), key: 'file_type', width: 80 },
  { title: t('views.network.regionBoundary.fileColumns.fileSize'), key: 'file_size', width: 80, render: (row) => formatSize(row.file_size) },
  {
    title: t('views.network.regionBoundary.fileColumns.status'), key: 'download_status', width: 80,
    render(row) {
      const labels = {
        SUCCESS: t('views.network.regionBoundary.statusMap.SUCCESS'),
        DOWNLOADING: t('views.network.regionBoundary.statusMap.DOWNLOADING'),
        FAILED: t('views.network.regionBoundary.statusMap.FAILED'),
        PENDING: t('views.network.regionBoundary.statusMap.PENDING'),
      }
      const s = { type: statusMap[row.download_status]?.type || 'default', label: labels[row.download_status] || row.download_status }
      return h(NTag, { type: s.type, size: 'small' }, { default: () => s.label })
    },
  },
  { title: t('views.network.regionBoundary.fileColumns.time'), key: 'created_at', width: 150, render: (row) => (row.created_at || '').replace('T', ' ') },
  {
    title: t('views.network.regionBoundary.fileColumns.actions'), key: 'actions', width: 120,
    render(row) {
      return h(NSpace, { size: 4 }, {
        default: () => [
          row.download_status === 'SUCCESS' && h(NButton, {
            size: 'tiny', quaternary: true, type: 'primary',
            onClick: () => onExportFile(row),
          }, { default: () => t('views.network.regionBoundary.buttons.export') }),
          h(NPopconfirm, { onPositiveClick: () => onDeleteFile(row) }, {
            trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' }, { default: () => t('views.network.regionBoundary.buttons.delete') }),
          }),
        ],
      })
    },
  },
]
</script>

<template>
  <CommonPage :title="t('views.network.regionBoundary.title')">
    <!-- 面包屑 -->
    <div class="toolbar-row">
      <NBreadcrumb>
        <NBreadcrumbItem>
          <span class="breadcrumb-link" @click="backToLevel(0)">{{ t('views.network.regionBoundary.breadcrumb.root') }}</span>
        </NBreadcrumbItem>
        <NBreadcrumbItem v-for="(item, idx) in breadcrumb" :key="item.id">
          <span v-if="idx < breadcrumb.length - 1" class="breadcrumb-link" @click="backToLevel(idx + 1)">{{ item.localName ? item.name + '（' + item.localName + '）' : item.name }}</span>
          <span v-else style="font-weight: 600">{{ item.localName ? item.name + '（' + item.localName + '）' : item.name }}</span>
        </NBreadcrumbItem>
      </NBreadcrumb>
    </div>

    <div class="main-layout">
      <!-- 左侧级联列表 -->
      <NCard size="small" :bordered="true" class="left-panel" :class="{ 'left-panel--collapsed': !showLeftPanel }">
        <template #header>
          <div class="left-panel-header">
            <span class="panel-title">{{ t('views.network.regionBoundary.panel.currentLevel', { level: currentLevelLabel }) }}</span>
            <NButton size="tiny" quaternary class="panel-toggle-btn" @click="showLeftPanel = !showLeftPanel">
              <TheIcon :icon="showLeftPanel ? 'material-symbols:chevron-left' : 'material-symbols:chevron-right'" :size="16" />
            </NButton>
          </div>
        </template>
        <NInput v-model:value="currentSearch" :placeholder="t('views.network.regionBoundary.searchPlaceholder', { level: currentLevelLabel })" clearable size="small" style="margin-bottom: 8px" />
        <NSpin :show="currentLoading" style="flex: 1; min-height: 0">
          <div v-if="filteredList.length" class="region-list">
            <div v-for="row in filteredList" :key="row.id" class="region-row" @click="onClickRow(row)">
              <span class="row-code">{{ row.code || '-' }}</span>
              <div class="row-names">
                <span class="row-name">{{ row.name }}</span>
                <span v-if="row.local_name" class="row-local-name">{{ row.local_name }}</span>
              </div>
              <NTag :style="{ background: typeColorMap[row.region_type] + '20', color: typeColorMap[row.region_type], border: 'none' }" size="small">{{ row.region_type }}</NTag>
            </div>
          </div>
          <div v-else class="empty-state">{{ currentLoading ? t('views.network.regionBoundary.list.loading') : t('views.network.regionBoundary.list.noData') }}</div>
        </NSpin>
      </NCard>

      <!-- 右侧边界文件 -->
      <NCard size="small" :bordered="true" class="right-panel">
        <template #header>
          <span class="panel-title">{{ selectedNode ? t('views.network.regionBoundary.panel.boundaryFiles', { name: selectedNode.localName ? selectedNode.name + '（' + selectedNode.localName + '）' : selectedNode.name }) : t('views.network.regionBoundary.panel.selectRegion') }}</span>
          <span v-if="selectedNode" style="float: right">
            <NButton size="small" type="primary" :loading="downloadLoading" @click="onDownload" style="margin-right: 4px">{{ t('views.network.regionBoundary.buttons.gadmDownload') }}</NButton>
            <NButton size="small" type="primary" @click="showUploadModal = true" style="margin-right: 4px">{{ t('views.network.regionBoundary.buttons.upload') }}</NButton>
            <NPopconfirm @positive-click="onClearAll" v-if="boundaryStatus.count > 0">
              <template #trigger><NButton size="small" type="error" secondary>{{ t('views.network.regionBoundary.buttons.clear') }}</NButton></template>
              {{ t('views.network.regionBoundary.confirmClear', { name: selectedNode.localName ? selectedNode.name + '（' + selectedNode.localName + '）' : selectedNode.name }) }}
            </NPopconfirm>
          </span>
        </template>

        <div v-if="!selectedNode" class="empty-state">{{ t('views.network.regionBoundary.panel.selectHint') }}</div>

        <NSpin v-else :show="boundaryLoading">
          <div style="margin-bottom: 16px">
            <NSpace align="center">
              <span>{{ t('views.network.regionBoundary.panel.downloadStatus') }}</span>
              <NTag :type="boundaryStatus.has_boundary ? 'success' : 'warning'" size="small">{{ boundaryStatus.has_boundary ? t('views.network.regionBoundary.panel.downloaded') : t('views.network.regionBoundary.panel.notDownloaded') }}</NTag>
              <span v-if="boundaryStatus.count > 0" style="color: #999">{{ t('views.network.regionBoundary.panel.fileCount', { count: boundaryStatus.count }) }}</span>
            </NSpace>
          </div>
          <NDataTable v-if="boundaryStatus.files.length" :columns="fileColumns" :data="boundaryStatus.files" :row-key="(row) => row.id" size="small" :bordered="true" stripe max-height="400" />
          <div v-else class="empty-state">{{ t('views.network.regionBoundary.panel.noFiles') }}</div>
        </NSpin>
      </NCard>
    </div>

    <NModal v-model:show="showUploadModal" :title="t('views.network.regionBoundary.uploadModal.title')" preset="card" style="width: 480px">
      <NUpload :action="uploadUrl" :headers="uploadHeaders" accept=".geojson,.json,.kml,.shp" :max="1" @finish="onUploadFinish">
        <NButton>{{ t('views.network.regionBoundary.buttons.selectFile') }}</NButton>
      </NUpload>
      <div style="margin-top: 8px; color: #999; font-size: 13px">{{ t('views.network.regionBoundary.uploadModal.supportedFormats') }}</div>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.toolbar-row { display: flex; align-items: center; margin-bottom: 8px; gap: 8px; flex-wrap: wrap; }
.breadcrumb-link { cursor: pointer; color: #2080f0; }
.breadcrumb-link:hover { text-decoration: underline; }
.panel-title { font-weight: 600; }

.main-layout { display: flex; height: calc(100vh - 210px); height: calc(100dvh - 210px); overflow: hidden; gap: 8px; }

.left-panel { width: 280px; flex-shrink: 0; display: flex; flex-direction: column; overflow: hidden; }
.right-panel { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; }
.left-panel :deep(.n-card__content), .right-panel :deep(.n-card__content) { flex: 1; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; }

/* 左面板 header 工具栏 */
.left-panel-header { display: flex; justify-content: space-between; align-items: center; }
.panel-toggle-btn { display: none; }

/* 列表行 */
.region-list { flex: 1; min-height: 0; }
.region-row { display: flex; align-items: flex-start; padding: 5px 8px; cursor: pointer; border-bottom: 1px solid #f0f0f0; transition: background 0.15s; gap: 6px; }
.region-row:hover { background: #f5f7fa; }
.row-code { font-size: 11px; color: #999; flex-shrink: 0; font-family: monospace; margin-top: 1px; }
.row-names { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.row-name { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-local-name { font-size: 11px; color: #999; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.empty-state { text-align: center; color: #999; padding: 40px 0; font-size: 14px; }

.left-panel :deep(.n-card__content)::-webkit-scrollbar,
.right-panel :deep(.n-card__content)::-webkit-scrollbar { width: 5px; }
.left-panel :deep(.n-card__content)::-webkit-scrollbar-thumb,
.right-panel :deep(.n-card__content)::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }

/* ── 移动端适配（≤767px）── */
@media (max-width: 767px) {
  /* 垂直堆叠 */
  .main-layout {
    flex-direction: column;
    height: calc(100dvh - 180px);
  }

  /* 左面板：宽度自适应，可折叠 */
  .left-panel {
    width: 100%;
    flex-shrink: 0;
    max-height: 40vh;
    transition: max-height 0.2s ease;
  }
  .left-panel--collapsed {
    max-height: 44px;
  }
  /* 折叠时隐藏内容 */
  .left-panel--collapsed :deep(.n-card__content) {
    display: none;
  }

  /* 折叠按钮：移动端显示 */
  .panel-toggle-btn {
    display: inline-flex;
  }

  /* 右面板 */
  .right-panel {
    flex: 1;
    min-height: 0;
  }

  /* 右面板 header 按钮：紧凑 */
  .right-panel :deep(.n-card-header) :deep(.n-button) {
    font-size: 12px;
    padding: 0 8px;
  }

  /* 列表行：触控友好 */
  .region-row {
    padding: 8px 12px;
  }
  .row-name {
    font-size: 14px;
  }
}
</style>
