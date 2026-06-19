<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NButton, NCard, NDataTable, NInput, NModal, NPopconfirm,
  NSelect, NSpace, NSpin, NTag, NUpload,
  NBreadcrumb, NBreadcrumbItem,
  useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import { useTaskProgressStore } from '@/store/modules/taskProgress'
import { getToken } from '@/utils'
import api from '@/api'

defineOptions({ name: '路网文件管理' })

const { t } = useI18n()
const _t = (key) => t(`views.network.roadNetwork.${key}`)

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
  if (breadcrumb.value.length === 0) return _t('levelLabel.country')
  if (breadcrumb.value.length === 1) return _t('levelLabel.state')
  return _t('levelLabel.city')
})

// ── 路网文件 ──
const networkStatus = ref({ has_network: false, count: 0, files: [] })
const networkLoading = ref(false)
const downloadLoading = ref(false)
const showUploadModal = ref(false)
const downloadMode = ref('name')

const uploadUrl = computed(() =>
  `${import.meta.env.VITE_BASE_API}/region/road-network/upload?region_id=${selectedNode.value?.id || ''}`
)
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${getToken() || ''}`,
}))

const typeColorMap = { COUNTRY: '#2080f0', STATE: '#18a058', CITY: '#f0a020' }

onMounted(resetToRoot)

function resetToRoot() {
  breadcrumb.value = []
  networkStatus.value = { has_network: false, count: 0, files: [] }
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

// ── 点击行 → 进入子层级并加载路网状态 ──
function onClickRow(row) {
  breadcrumb.value.push({ id: row.id, name: row.name, localName: row.local_name || '', type: row.region_type || '' })
  loadCurrentLevel()
  loadNetworkStatus(row.id)
}

function backToLevel(index) {
  breadcrumb.value = breadcrumb.value.slice(0, index)
  if (breadcrumb.value.length > 0) {
    loadNetworkStatus(breadcrumb.value[breadcrumb.value.length - 1].id)
  } else {
    networkStatus.value = { has_network: false, count: 0, files: [] }
  }
  loadCurrentLevel()
}

// ── 路网操作 ──
async function loadNetworkStatus(regionId) {
  networkLoading.value = true
  try {
    const res = await api.getRoadNetworkStatus(regionId)
    networkStatus.value = res.data || { has_network: false, count: 0, files: [] }
  } catch (e) {
    networkStatus.value = { has_network: false, count: 0, files: [] }
  } finally {
    networkLoading.value = false
  }
}

async function onDownload() {
  if (!selectedNode.value) return
  downloadLoading.value = true

  const taskStore = useTaskProgressStore()
  const nodeName = selectedNode.value.localName
    ? `${selectedNode.value.name}（${selectedNode.value.localName}）`
    : selectedNode.value.name
  const taskId = taskStore.startTask(_t('task.downloadName', { name: nodeName }))

  // 模拟进度（后端同步返回，无法获取真实百分比）
  let simProgress = 10
  const simTimer = setInterval(() => {
    if (simProgress < 85) {
      simProgress += 5
      taskStore.updateProgress(taskId, { progress: simProgress, message: _t('task.downloading') })
    }
  }, 800)

  try {
    await api.downloadRoadNetwork({
      region_id: selectedNode.value.id,
      mode: downloadMode.value,
      file_type: 'GPKG',
    })
    clearInterval(simTimer)
    taskStore.finishTask(taskId, _t('task.complete'))
    message.success(_t('messages.downloadSuccess'))
    loadNetworkStatus(selectedNode.value.id)
  } catch (e) {
    clearInterval(simTimer)
    const errMsg = e?.response?.data?.msg || e?.message || _t('task.unknownError')
    taskStore.failTask(taskId, { message: _t('task.fail'), detail: errMsg })
    message.error(_t('messages.downloadFail', { error: errMsg }))
  } finally {
    downloadLoading.value = false
  }
}

function onUploadFinish({ file }) {
  if (file.status === 'finished') {
    message.success(_t('messages.uploadSuccess'))
    showUploadModal.value = false
    loadNetworkStatus(selectedNode.value?.id)
  }
}

async function onDeleteFile(row) {
  try {
    await api.deleteRoadNetwork({ network_id: row.id })
    message.success(_t('messages.deleteSuccess'))
    loadNetworkStatus(selectedNode.value?.id)
  } catch (e) { message.error(_t('messages.deleteFail')) }
}

async function onClearAll() {
  if (!selectedNode.value) return
  try {
    const res = await api.clearRoadNetworks({ region_id: selectedNode.value.id })
    message.success(_t('messages.clearSuccess', { count: res.data?.deleted || 0 }))
    loadNetworkStatus(selectedNode.value.id)
  } catch (e) { message.error(_t('messages.clearFail')) }
}

function onExportFile(row) {
  api.downloadRoadNetworkFile({ network_id: row.id }).then((res) => {
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = row.file_name || 'network.gpkg'
    a.click()
    URL.revokeObjectURL(url)
  }).catch(() => message.error(_t('messages.exportFail')))
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatCount(n) { return n != null ? n.toLocaleString() : '-' }

const downloadModeOptions = computed(() => [
  { label: _t('downloadModes.byName'), value: 'name' },
  { label: _t('downloadModes.byBoundary'), value: 'boundary' },
])

const fileColumns = computed(() => {
  const statusLabels = {
    SUCCESS: _t('statusMap.SUCCESS'),
    DOWNLOADING: _t('statusMap.DOWNLOADING'),
    FAILED: _t('statusMap.FAILED'),
    PENDING: _t('statusMap.PENDING'),
  }
  const statusTypeMap = { SUCCESS: 'success', DOWNLOADING: 'warning', FAILED: 'error', PENDING: 'default' }
  return [
    { title: _t('fileColumns.fileName'), key: 'file_name', ellipsis: { tooltip: true }, width: 160 },
    { title: _t('fileColumns.fileType'), key: 'file_type', width: 70 },
    { title: _t('fileColumns.fileSize'), key: 'file_size', width: 70, render: (row) => formatSize(row.file_size) },
    { title: _t('fileColumns.nodeCount'), key: 'node_count', width: 70, render: (row) => formatCount(row.node_count) },
    { title: _t('fileColumns.edgeCount'), key: 'edge_count', width: 70, render: (row) => formatCount(row.edge_count) },
    { title: _t('fileColumns.mode'), key: 'download_mode', width: 60,
      render(row) { return h(NTag, { size: 'tiny', type: 'info' }, { default: () => row.download_mode || '-' }) },
    },
    { title: _t('fileColumns.status'), key: 'download_status', width: 70,
      render(row) {
        const label = statusLabels[row.download_status] || row.download_status
        const type = statusTypeMap[row.download_status] || 'default'
        return h(NTag, { type, size: 'small' }, { default: () => label })
      },
    },
    { title: _t('fileColumns.time'), key: 'created_at', width: 140, render: (row) => (row.created_at || '').replace('T', ' ') },
    {
      title: _t('fileColumns.actions'), key: 'actions', width: 100,
      render(row) {
        return h(NSpace, { size: 2 }, {
          default: () => [
            row.download_status === 'SUCCESS' && h(NButton, {
              size: 'tiny', quaternary: true, type: 'primary',
              onClick: () => onExportFile(row),
            }, { default: () => _t('buttons.export') }),
            h(NPopconfirm, { onPositiveClick: () => onDeleteFile(row) }, {
              trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' }, { default: () => _t('buttons.delete') }),
            }),
          ],
        })
      },
    },
  ]
})
</script>

<template>
  <CommonPage :title="_t('title')">
    <div class="toolbar-row">
      <NBreadcrumb>
        <NBreadcrumbItem><span class="breadcrumb-link" @click="backToLevel(0)">{{ _t('breadcrumb.root') }}</span></NBreadcrumbItem>
        <NBreadcrumbItem v-for="(item, idx) in breadcrumb" :key="item.id">
          <span v-if="idx < breadcrumb.length - 1" class="breadcrumb-link" @click="backToLevel(idx + 1)">{{ item.localName ? item.name + '（' + item.localName + '）' : item.name }}</span>
          <span v-else style="font-weight: 600">{{ item.localName ? item.name + '（' + item.localName + '）' : item.name }}</span>
        </NBreadcrumbItem>
      </NBreadcrumb>
    </div>

    <div class="main-layout">
      <NCard size="small" :bordered="true" class="left-panel">
        <template #header><span class="panel-title">{{ _t('panel.currentLevel', { level: currentLevelLabel }) }}</span></template>
        <NInput v-model:value="currentSearch" :placeholder="_t('searchPlaceholder', { level: currentLevelLabel })" clearable size="small" style="margin-bottom: 8px" />
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
          <div v-else class="empty-state">{{ currentLoading ? _t('list.loading') : _t('list.noData') }}</div>
        </NSpin>
      </NCard>

      <NCard size="small" :bordered="true" class="right-panel">
        <template #header>
          <div class="panel-header-row">
            <span class="panel-title">{{ selectedNode ? _t('panel.networkFiles', { name: selectedNode.localName ? selectedNode.name + '（' + selectedNode.localName + '）' : selectedNode.name }) : _t('panel.selectRegion') }}</span>
            <div v-if="selectedNode" class="panel-actions">
              <NSelect v-model:value="downloadMode" :options="downloadModeOptions" size="small" class="action-dl-select" />
              <NButton size="small" type="primary" :loading="downloadLoading" @click="onDownload">{{ _t('buttons.osmDownload') }}</NButton>
              <NButton size="small" type="primary" @click="showUploadModal = true">{{ _t('buttons.upload') }}</NButton>
              <NPopconfirm @positive-click="onClearAll" v-if="networkStatus.count > 0">
                <template #trigger><NButton size="small" type="error" secondary>{{ _t('buttons.clear') }}</NButton></template>
                {{ _t('confirmClear', { name: selectedNode.localName ? selectedNode.name + '（' + selectedNode.localName + '）' : selectedNode.name }) }}
              </NPopconfirm>
            </div>
          </div>
        </template>

        <div v-if="!selectedNode" class="empty-state">{{ _t('panel.selectHint') }}</div>

        <NSpin v-else :show="networkLoading">
          <div style="margin-bottom: 16px">
            <NSpace align="center">
              <span>{{ _t('panel.downloadStatus') }}</span>
              <NTag :type="networkStatus.has_network ? 'success' : 'warning'" size="small">{{ networkStatus.has_network ? _t('panel.downloaded') : _t('panel.notDownloaded') }}</NTag>
              <span v-if="networkStatus.count > 0" style="color: #999">{{ _t('panel.fileCount', { count: networkStatus.count }) }}</span>
            </NSpace>
          </div>
          <NDataTable v-if="networkStatus.files.length" :columns="fileColumns" :data="networkStatus.files" :row-key="(row) => row.id" size="small" :bordered="true" stripe max-height="400" />
          <div v-else class="empty-state">{{ _t('panel.noFiles') }}</div>
        </NSpin>
      </NCard>
    </div>

    <NModal v-model:show="showUploadModal" :title="_t('uploadModal.title')" preset="card" style="width: 480px">
      <NUpload :action="uploadUrl" :headers="uploadHeaders" accept=".graphml,.osm,.gpkg,.shp" :max="1" @finish="onUploadFinish">
        <NButton>{{ _t('buttons.selectFile') }}</NButton>
      </NUpload>
      <div style="margin-top: 8px; color: #999; font-size: 13px">{{ _t('uploadModal.supportedFormats') }}</div>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.toolbar-row { display: flex; align-items: center; margin-bottom: 8px; gap: 8px; flex-wrap: wrap; }
.breadcrumb-link { cursor: pointer; color: #2080f0; }
.breadcrumb-link:hover { text-decoration: underline; }
.main-layout { display: flex; height: calc(100vh - 210px); overflow: hidden; gap: 8px; }

.left-panel { width: 280px; flex-shrink: 0; display: flex; flex-direction: column; overflow: hidden; }
.right-panel { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; }
.left-panel :deep(.n-card__content), .right-panel :deep(.n-card__content) { flex: 1; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; }

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

/* 右面板 header 行 */
.panel-header-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.panel-title { font-weight: 600; flex-shrink: 0; }
.panel-actions { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; margin-left: auto; }
.action-dl-select { width: 120px; }

/* ── 移动端适配（≤768px）── */
@media (max-width: 768px) {
  .toolbar-row { margin-bottom: 4px; }

  /* 双面板 → 垂直堆叠 */
  .main-layout {
    flex-direction: column;
    height: auto;
    height: calc(100dvh - 160px);
    min-height: 400px;
    gap: 6px;
  }

  .left-panel {
    width: 100%;
    flex-shrink: 1;
    max-height: 35vh;
    min-height: 140px;
  }

  .right-panel {
    flex: 1;
    min-height: 150px;
  }

  /* header 按钮全宽换行 */
  .panel-header-row {
    gap: 4px;
  }
  .panel-actions {
    width: 100%;
    margin-left: 0;
    gap: 4px;
  }
  .panel-actions > * {
    flex: 1 1 auto;
    min-width: 0;
  }
  .action-dl-select {
    width: 100% !important;
    min-width: 100px;
  }

  /* 紧凑行间距 */
  .region-row { padding: 6px 8px; }
  .row-code { font-size: 10px; }
  .row-name { font-size: 12px; }
}
</style>