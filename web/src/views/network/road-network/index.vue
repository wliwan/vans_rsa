<script setup>
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton, NCard, NDataTable, NInput, NModal, NPopconfirm,
  NSelect, NSpace, NSpin, NTag, NTree, NUpload,
  useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import { getToken } from '@/utils'
import api from '@/api'

defineOptions({ name: '路网文件管理' })

const message = useMessage()

const treeData = ref([])
const selectedKeys = ref([])
const selectedNode = ref(null)
const treeLoading = ref(false)
const treePattern = ref('')

const networkStatus = ref({ has_network: false, count: 0, files: [] })
const networkLoading = ref(false)
const downloadLoading = ref(false)
const showUploadModal = ref(false)
const downloadMode = ref('name')  // boundary | name

const uploadUrl = computed(() =>
  `${import.meta.env.VITE_BASE_API}/region/road-network/upload?region_id=${selectedNode.value?.id || ''}`
)
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${getToken() || ''}`,
}))

onMounted(() => loadTree())

async function loadTree() {
  treeLoading.value = true
  try {
    const res = await api.getRegionTree()
    treeData.value = res.data || []
  } catch (e) {
    message.error('加载树失败')
  } finally {
    treeLoading.value = false
  }
}

function onNodeSelect(keys, option) {
  if (keys.length === 0) {
    selectedNode.value = null
    networkStatus.value = { has_network: false, count: 0, files: [] }
    return
  }
  const node = Array.isArray(option) ? option[0] : option
  selectedKeys.value = keys
  selectedNode.value = node
  loadNetworkStatus(node.id)
}

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
  try {
    await api.downloadRoadNetwork({
      region_id: selectedNode.value.id,
      mode: downloadMode.value,
      file_type: 'GRAPHML',
    })
    message.success('路网下载成功')
    loadNetworkStatus(selectedNode.value.id)
  } catch (e) {
    message.error('下载失败: ' + (e?.response?.data?.msg || e?.message || '未知错误'))
  } finally {
    downloadLoading.value = false
  }
}

function onUploadFinish({ file }) {
  if (file.status === 'finished') {
    message.success('上传成功')
    showUploadModal.value = false
    loadNetworkStatus(selectedNode.value?.id)
  }
}

async function onDeleteFile(row) {
  try {
    await api.deleteRoadNetwork({ network_id: row.id })
    message.success('删除成功')
    loadNetworkStatus(selectedNode.value?.id)
  } catch (e) {
    message.error('删除失败')
  }
}

async function onClearAll() {
  if (!selectedNode.value) return
  try {
    const res = await api.clearRoadNetworks({ region_id: selectedNode.value.id })
    message.success(`已清除 ${res.data?.deleted || 0} 个文件`)
    loadNetworkStatus(selectedNode.value.id)
  } catch (e) {
    message.error('清除失败')
  }
}

function onExportFile(row) {
  api.downloadRoadNetworkFile({ network_id: row.id }).then((res) => {
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = row.file_name || 'network.graphml'
    a.click()
    URL.revokeObjectURL(url)
  }).catch(() => message.error('导出失败'))
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatCount(n) {
  return n != null ? n.toLocaleString() : '-'
}

const downloadModeOptions = [
  { label: '按地名下载', value: 'name' },
  { label: '按边界文件下载', value: 'boundary' },
]

const statusMap = {
  SUCCESS: { type: 'success', label: '已下载' },
  DOWNLOADING: { type: 'warning', label: '下载中' },
  FAILED: { type: 'error', label: '失败' },
  PENDING: { type: 'default', label: '待下载' },
}

const fileColumns = [
  { title: '文件名', key: 'file_name', ellipsis: { tooltip: true }, width: 160 },
  { title: '格式', key: 'file_type', width: 70 },
  { title: '大小', key: 'file_size', width: 70, render: (row) => formatSize(row.file_size) },
  { title: '节点数', key: 'node_count', width: 70, render: (row) => formatCount(row.node_count) },
  { title: '边数', key: 'edge_count', width: 70, render: (row) => formatCount(row.edge_count) },
  {
    title: '模式', key: 'download_mode', width: 60,
    render(row) { return h(NTag, { size: 'tiny', type: 'info' }, { default: () => row.download_mode || '-' }) },
  },
  {
    title: '状态', key: 'download_status', width: 70,
    render(row) {
      const s = statusMap[row.download_status] || { type: 'default', label: row.download_status }
      return h(NTag, { type: s.type, size: 'small' }, { default: () => s.label })
    },
  },
  { title: '时间', key: 'created_at', width: 140, render: (row) => (row.created_at || '').replace('T', ' ') },
  {
    title: '操作', key: 'actions', width: 100,
    render(row) {
      return h(NSpace, { size: 2 }, {
        default: () => [
          row.download_status === 'SUCCESS' && h(NButton, {
            size: 'tiny', quaternary: true, type: 'primary',
            onClick: () => onExportFile(row),
          }, { default: () => '导出' }),
          h(NPopconfirm, { onPositiveClick: () => onDeleteFile(row) }, {
            trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' }, { default: () => '删除' }),
          }),
        ],
      })
    },
  },
]
</script>

<template>
  <CommonPage title="路网文件管理">
    <div class="region-layout">
      <NCard size="small" class="left-panel" :bordered="true">
        <template #header>
          <span style="font-weight: 600">区域树</span>
        </template>
        <div style="padding: 0 0 8px 0">
          <NInput v-model:value="treePattern" placeholder="搜索区域名称..." clearable size="small" />
        </div>
        <NSpin :show="treeLoading">
          <NTree
            v-if="treeData.length"
            :data="treeData"
            :selected-keys="selectedKeys"
            :pattern="treePattern"
            :filter="(pattern, node) => !pattern || String(node.label||'').toLowerCase().includes(String(pattern).toLowerCase())"
            virtual-scroll
            key-field="id"
            label-field="label"
            children-field="children"
            block-line
            selectable
            @update:selected-keys="(keys, opt) => onNodeSelect(keys, opt)"
          />
          <div v-else style="text-align: center; color: #999; padding: 40px 0">
            暂无数据，请先导入
          </div>
        </NSpin>
      </NCard>

      <NCard size="small" class="right-panel" :bordered="true">
        <template #header>
          <span style="font-weight: 600">
            {{ selectedNode ? `路网文件 — ${selectedNode.label}` : '请从左侧选择区域' }}
          </span>
          <span v-if="selectedNode" style="float: right">
            <NSelect
              v-model:value="downloadMode"
              :options="downloadModeOptions"
              size="small"
              style="width: 130px; margin-right: 4px"
              filterable
            />
            <NButton
              size="small" type="primary" :loading="downloadLoading"
              @click="onDownload" style="margin-right: 4px"
            >
              下载路网
            </NButton>
            <NButton size="small" type="primary" @click="showUploadModal = true" style="margin-right: 4px">
              上传
            </NButton>
            <NPopconfirm @positive-click="onClearAll" v-if="networkStatus.count > 0">
              <template #trigger>
                <NButton size="small" type="error" secondary>清除</NButton>
              </template>
              确认清除「{{ selectedNode.label }}」的所有路网文件？
            </NPopconfirm>
          </span>
        </template>

        <div v-if="!selectedNode" style="text-align: center; color: #999; padding: 60px 0">
          选择左侧区域查看和下载路网文件
        </div>

        <NSpin v-else :show="networkLoading">
          <div style="margin-bottom: 16px">
            <NSpace align="center">
              <span>下载状态：</span>
              <NTag :type="networkStatus.has_network ? 'success' : 'warning'" size="small">
                {{ networkStatus.has_network ? '已下载' : '未下载' }}
              </NTag>
              <span v-if="networkStatus.count > 0" style="color: #999">
                共 {{ networkStatus.count }} 个文件
              </span>
            </NSpace>
          </div>

          <NDataTable
            v-if="networkStatus.files.length"
            :columns="fileColumns"
            :data="networkStatus.files"
            :row-key="(row) => row.id"
            size="small"
            :bordered="true"
            stripe
            max-height="400"
          />

          <div v-else style="text-align: center; color: #999; padding: 40px 0">
            暂无路网文件，请下载或上传
          </div>
        </NSpin>
      </NCard>
    </div>

    <NModal v-model:show="showUploadModal" title="上传路网文件" preset="card" style="width: 480px">
      <NUpload
        :action="uploadUrl"
        :headers="uploadHeaders"
        accept=".graphml,.osm,.gpkg,.xml"
        :max="1"
        @finish="onUploadFinish"
      >
        <NButton>选择文件</NButton>
      </NUpload>
      <div style="margin-top: 8px; color: #999; font-size: 13px">
        支持 GraphML、OSM、GeoPackage 格式
      </div>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.region-layout {
  display: flex;
  height: calc(100vh - 180px);
  overflow: hidden;
  gap: 8px;
}
.left-panel {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.right-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.left-panel :deep(.n-card__content),
.right-panel :deep(.n-card__content) {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.left-panel :deep(.n-tree-node-content__text) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
