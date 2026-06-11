<script setup>
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton, NCard, NDataTable, NModal, NPopconfirm,
  NSelect, NSpace, NSpin, NTag, NTree, NUpload,
  useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import { getToken } from '@/utils'
import api from '@/api'

defineOptions({ name: '行政区边界文件管理' })

const message = useMessage()

// 树相关
const treeData = ref([])
const selectedKeys = ref([])
const selectedNode = ref(null)
const treeLoading = ref(false)
const treePattern = ref('')

// 边界文件
const boundaryStatus = ref({ has_boundary: false, count: 0, files: [] })
const boundaryLoading = ref(false)
const downloadLoading = ref(false)
const showUploadModal = ref(false)

// 上传 URL 和 headers（模板中不能直接使用 import.meta）
const uploadUrl = computed(() =>
  `${import.meta.env.VITE_BASE_API}/region/region-boundary/upload?region_id=${selectedNode.value?.id || ''}`
)
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${getToken() || ''}`,
}))

const fileTypeOptions = [
  { label: 'GeoJSON', value: 'GEOJSON' },
]

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

// NTree 的 @update:selected-keys 第二个参数是选中节点数组
function onNodeSelect(keys, option) {
  if (keys.length === 0) {
    selectedNode.value = null
    boundaryStatus.value = { has_boundary: false, count: 0, files: [] }
    return
  }
  const node = Array.isArray(option) ? option[0] : option
  selectedKeys.value = keys
  selectedNode.value = node
  loadBoundaryStatus(node.id)
}

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

// 从 OSM 下载边界
async function onDownload() {
  if (!selectedNode.value) return
  downloadLoading.value = true
  try {
    const res = await api.downloadBoundary({
      region_id: selectedNode.value.id,
      file_type: 'GEOJSON',
    })
    message.success('边界文件下载成功')
    loadBoundaryStatus(selectedNode.value.id)
  } catch (e) {
    message.error('下载失败，请检查网络或区域名称是否正确')
  } finally {
    downloadLoading.value = false
  }
}

// 上传文件
function onUploadFinish({ file }) {
  if (file.status === 'finished') {
    message.success('上传成功')
    showUploadModal.value = false
    loadBoundaryStatus(selectedNode.value?.id)
  }
}

// 删除单个文件
async function onDeleteFile(row) {
  try {
    await api.deleteBoundary({ boundary_id: row.id })
    message.success('删除成功')
    loadBoundaryStatus(selectedNode.value?.id)
  } catch (e) {
    message.error('删除失败')
  }
}

// 清除全部
async function onClearAll() {
  if (!selectedNode.value) return
  try {
    const res = await api.clearBoundaries({ region_id: selectedNode.value.id })
    message.success(`已清除 ${res.data?.deleted || 0} 个文件`)
    loadBoundaryStatus(selectedNode.value.id)
  } catch (e) {
    message.error('清除失败')
  }
}

// 导出文件
function onExportFile(row) {
  api.downloadBoundaryFile({ boundary_id: row.id }).then((res) => {
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = row.file_name || 'boundary.geojson'
    a.click()
    URL.revokeObjectURL(url)
  }).catch(() => message.error('导出失败'))
}

const statusMap = {
  SUCCESS: { type: 'success', label: '已下载' },
  DOWNLOADING: { type: 'warning', label: '下载中' },
  FAILED: { type: 'error', label: '失败' },
  PENDING: { type: 'default', label: '待下载' },
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const fileColumns = [
  { title: '文件名', key: 'file_name', ellipsis: { tooltip: true }, width: 180 },
  { title: '类型', key: 'file_type', width: 80 },
  { title: '大小', key: 'file_size', width: 80, render: (row) => formatSize(row.file_size) },
  {
    title: '状态', key: 'download_status', width: 80,
    render(row) {
      const s = statusMap[row.download_status] || { type: 'default', label: row.download_status }
      return h(NTag, { type: s.type, size: 'small' }, { default: () => s.label })
    },
  },
  { title: '时间', key: 'created_at', width: 150, render: (row) => (row.created_at || '').replace('T', ' ') },
  {
    title: '操作', key: 'actions', width: 120,
    render(row) {
      return h(NSpace, { size: 4 }, {
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
  <CommonPage title="行政区边界文件管理">
    <div class="region-layout">
      <!-- 左侧树 -->
      <NCard size="small" class="left-panel" :bordered="true">
        <template #header>
          <span style="font-weight: 600">区域树</span>
        </template>
        <div style="padding: 0 0 8px 0">
          <NInput
            v-model:value="treePattern"
            placeholder="搜索区域名称..."
            clearable
            size="small"
          />
        </div>
        <NSpin :show="treeLoading">
          <NTree
            v-if="treeData.length"
            :data="treeData"
            :selected-keys="selectedKeys"
            :pattern="treePattern"
            :filter="(pattern, node) => !pattern || String(node.label || '').toLowerCase().includes(String(pattern).toLowerCase())"
            virtual-scroll
            key-field="id"
            label-field="label"
            children-field="children"
            block-line
            selectable
            @update:selected-keys="(keys, opt) => onNodeSelect(keys, opt)"
          />
          <div v-else style="text-align: center; color: #999; padding: 40px 0">
            暂无数据，请先在「全球国家及行政区管理」中导入
          </div>
        </NSpin>
      </NCard>

      <!-- 右侧边界文件面板 -->
      <NCard size="small" class="right-panel" :bordered="true">
        <template #header>
          <span style="font-weight: 600">
            {{ selectedNode ? `边界文件 — ${selectedNode.label}` : '请从左侧选择区域' }}
          </span>
          <span v-if="selectedNode" style="float: right">
            <NButton
              size="small" type="primary" :loading="downloadLoading"
              @click="onDownload" style="margin-right: 4px"
            >
              从 GADM 下载
            </NButton>
            <NButton size="small" type="primary" @click="showUploadModal = true" style="margin-right: 4px">
              上传文件
            </NButton>
            <NPopconfirm @positive-click="onClearAll" v-if="boundaryStatus.count > 0">
              <template #trigger>
                <NButton size="small" type="error" secondary>清除</NButton>
              </template>
              确认清除「{{ selectedNode.label }}」的所有边界文件？
            </NPopconfirm>
          </span>
        </template>

        <div v-if="!selectedNode" style="text-align: center; color: #999; padding: 60px 0">
          选择左侧区域查看和下载边界文件
        </div>

        <NSpin v-else :show="boundaryLoading">
          <!-- 状态概览 -->
          <div style="margin-bottom: 16px">
            <NSpace align="center">
              <span>下载状态：</span>
              <NTag :type="boundaryStatus.has_boundary ? 'success' : 'warning'" size="small">
                {{ boundaryStatus.has_boundary ? '已下载' : '未下载' }}
              </NTag>
              <span v-if="boundaryStatus.count > 0" style="color: #999">
                共 {{ boundaryStatus.count }} 个文件
              </span>
            </NSpace>
          </div>

          <!-- 文件列表 -->
          <NDataTable
            v-if="boundaryStatus.files.length"
            :columns="fileColumns"
            :data="boundaryStatus.files"
            :row-key="(row) => row.id"
            size="small"
            :bordered="true"
            stripe
            max-height="400"
          />

          <div v-else style="text-align: center; color: #999; padding: 40px 0">
            暂无边界文件，请从 GADM 下载或上传
          </div>
        </NSpin>
      </NCard>
    </div>

    <!-- 上传弹窗 -->
    <NModal v-model:show="showUploadModal" title="上传边界文件" preset="card" style="width: 480px">
      <NUpload
        :action="uploadUrl"
        :headers="uploadHeaders"
        accept=".geojson,.json,.kml,.shp"
        :max="1"
        @finish="onUploadFinish"
      >
        <NButton>选择文件</NButton>
      </NUpload>
      <div style="margin-top: 8px; color: #999; font-size: 13px">
        支持 GeoJSON、KML、SHP 格式
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
