<script setup>
import { h, onMounted, ref } from 'vue'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NPopconfirm,
  NSelect,
  NSpace,
  NTag,
  NTree,
  NModal,
  NCard,
  NSpin,
  useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

defineOptions({ name: '全球国家及行政区管理' })

const message = useMessage()

// 树相关
const treeData = ref([])
const selectedKeys = ref([])
const selectedNode = ref(null)
const treeLoading = ref(false)
const treePattern = ref('')

// 子节点列表
const childrenList = ref([])
const childrenLoading = ref(false)

// 表单
const formMode = ref('view') // view | create | edit
const formLoading = ref(false)
const formRef = ref(null)
const formData = ref({
  name: '', local_name: '', code: '', iso_alpha2: '', iso_alpha3: '',
  iso_numeric: '', region_type: 'COUNTRY', parent_id: null,
  capital: '', population: null, area: null, latitude: null, longitude: null,
  timezone: '',
})
const formRules = { name: { required: true, message: '请输入名称' } }

// 弹窗
const showCreateModal = ref(false)
const importLoading = ref(false)

const typeOptions = [
  { label: '国家', value: 'COUNTRY' },
  { label: '行政区', value: 'STATE' },
  { label: '城市', value: 'CITY' },
]

const exportLevelOptions = [
  { label: '全部（含国家）', value: 'ALL' },
  { label: '仅行政区', value: 'STATE' },
  { label: '行政区 + 城市', value: 'CITY' },
]

onMounted(() => {
  loadTree()
})

// 加载树
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

// 树节点选中
// NTree 的 @update:selected-keys 第二个参数是选中节点数组，取第一个
function onNodeSelect(keys, option) {
  if (keys.length === 0) {
    selectedNode.value = null
    childrenList.value = []
    return
  }
  const node = Array.isArray(option) ? option[0] : option
  selectedKeys.value = keys
  selectedNode.value = node
  formMode.value = 'view'
  loadNodeDetail(node.id)
  loadChildren(node.id)
}

// 加载节点详情
async function loadNodeDetail(nodeId) {
  try {
    const res = await api.getRegionById(nodeId)
    formData.value = { ...res.data }
  } catch (e) {
    // ignore
  }
}

// 加载子节点
async function loadChildren(parentId) {
  childrenLoading.value = true
  try {
    const res = await api.getRegionChildren(parentId)
    childrenList.value = res.data || []
  } catch (e) {
    childrenList.value = []
  } finally {
    childrenLoading.value = false
  }
}

// 新增
function onAdd(childParentId) {
  formMode.value = 'create'
  formData.value = {
    name: '', local_name: '', code: '', iso_alpha2: '', iso_alpha3: '',
    iso_numeric: '', region_type: selectedNode.value ? 'STATE' : 'COUNTRY',
    parent_id: childParentId || selectedNode.value?.id || null,
    capital: '', population: null, area: null, latitude: null, longitude: null,
    timezone: '',
  }
  showCreateModal.value = true
}

// 编辑
function onEdit() {
  if (!selectedNode.value) return
  formMode.value = 'edit'
  showCreateModal.value = true
}

// 保存表单
async function onSave() {
  formLoading.value = true
  try {
    if (formMode.value === 'create') {
      await api.createRegion(formData.value)
      message.success('新增成功')
    } else {
      await api.updateRegion({ id: selectedNode.value.id, ...formData.value })
      message.success('更新成功')
    }
    showCreateModal.value = false
    await loadTree()
    if (selectedNode.value) {
      loadNodeDetail(selectedNode.value.id)
      loadChildren(selectedNode.value.id)
    }
  } catch (e) {
    message.error('保存失败')
  } finally {
    formLoading.value = false
  }
}

// 删除
async function onDelete() {
  if (!selectedNode.value) return
  try {
    await api.deleteRegion({ region_id: selectedNode.value.id })
    message.success('删除成功')
    selectedNode.value = null
    selectedKeys.value = []
    childrenList.value = []
    await loadTree()
  } catch (e) {
    message.error('删除失败')
  }
}

// 批量导入
async function onImport() {
  importLoading.value = true
  try {
    const res = await api.importRegions()
    const d = res.data || {}
    const parts = []
    if (d.created_country) parts.push(`国家 +${d.created_country}`)
    if (d.updated_country) parts.push(`国家更新 ${d.updated_country}`)
    if (d.created_state) parts.push(`行政区 +${d.created_state}`)
    if (d.created_city) parts.push(`城市 +${d.created_city}`)
    message.success(`导入完成：${parts.join('，') || '无新数据'}`)
    await loadTree()
  } catch (e) {
    message.error('导入失败')
  } finally {
    importLoading.value = false
  }
}

// 全部清空
async function onClearAll() {
  try {
    const res = await api.clearRegions()
    message.success(`已清空 ${res.data?.deleted || 0} 条`)
    selectedNode.value = null
    selectedKeys.value = []
    childrenList.value = []
    await loadTree()
  } catch (e) {
    message.error('清空失败')
  }
}

// 导出
async function onExport(level) {
  if (!selectedNode.value || selectedNode.value.region_type !== 'COUNTRY') {
    message.warning('请先选中一个国家')
    return
  }
  try {
    const res = await api.exportRegions({
      country_id: selectedNode.value.id,
      level: level,
    })
    const data = res.data
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedNode.value.label}_export_${level}.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success('导出完成')
  } catch (e) {
    message.error('导出失败')
  }
}

// 子节点操作列
const childColumns = [
  { title: '名称', key: 'name', width: 140, ellipsis: { tooltip: true } },
  { title: '代码', key: 'code', width: 60 },
  {
    title: '类型', key: 'region_type', width: 60,
    render(row) { return h(NTag, { type: 'info', size: 'small' }, { default: () => row.region_type }) },
  },
  { title: '首府', key: 'capital', width: 80, ellipsis: { tooltip: true } },
  {
    title: '操作', key: 'actions', width: 60, align: 'center',
    render(row) {
      return h(NPopconfirm, {
        onPositiveClick: async () => {
          try {
            await api.deleteRegion({ region_id: row.id })
            message.success('删除成功')
            loadTree()
            loadChildren(selectedNode.value?.id)
          } catch (e) { message.error('删除失败') }
        },
      }, {
        trigger: () => h(NButton, { size: 'tiny', type: 'error', quaternary: true }, {
          default: () => '删除', icon: renderIcon('material-symbols:delete-outline', { size: 14 }),
        }),
      })
    },
  },
]

function renderIcon(name, opts) {
  return h('span', { class: 'inline-flex', style: { marginRight: '4px' } })
}
</script>

<template>
  <CommonPage title="全球国家及行政区管理">
    <template #action>
      <NButton type="warning" :loading="importLoading" @click="onImport" style="margin-right: 8px">
        <TheIcon icon="material-symbols:cloud-download" :size="18" class="mr-5" />导入 ISO 3166 国家
      </NButton>
      <NPopconfirm @positive-click="onClearAll">
        <template #trigger>
          <NButton type="error" secondary>
            <TheIcon icon="material-symbols:delete-forever" :size="18" class="mr-5" />全部清空
          </NButton>
        </template>
        确认清空所有国家及行政区数据？此操作不可恢复！
      </NPopconfirm>
    </template>

    <div class="region-layout">
      <!-- 左侧树 -->
      <NCard size="small" class="left-panel" :bordered="true">
        <template #header>
          <span style="font-weight: 600">区域树</span>
          <NButton size="tiny" type="primary" quaternary @click="onAdd(null)" style="float: right; margin-top: -2px">
            <TheIcon icon="material-symbols:add" :size="16" />新增国家
          </NButton>
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
          <div v-else style="text-align: center; color: #999; padding: 40px 0">暂无数据，请先导入</div>
        </NSpin>
      </NCard>

      <!-- 右侧详情 -->
      <NCard size="small" class="right-panel" :bordered="true">
        <template #header>
          <span style="font-weight: 600">
            {{ selectedNode ? `详情 — ${selectedNode.label}` : '请从左侧选择区域' }}
          </span>
          <span v-if="selectedNode" style="float: right">
            <NButton size="small" type="primary" @click="onEdit" style="margin-right: 4px">编辑</NButton>
            <NButton size="small" type="primary" @click="onAdd(selectedNode.id)" style="margin-right: 4px">新增子级</NButton>
            <NSelect
              v-if="selectedNode.region_type === 'COUNTRY'"
              :options="exportLevelOptions"
              value="STATE"
              size="small"
              style="width: 130px; margin-right: 4px"
              @update:value="onExport"
              placeholder="导出"
              filterable
            />
            <NPopconfirm @positive-click="onDelete">
              <template #trigger>
                <NButton size="small" type="error">删除</NButton>
              </template>
              确认删除「{{ selectedNode.label }}」及其所有子区域？
            </NPopconfirm>
          </span>
        </template>

        <div v-if="!selectedNode" style="text-align: center; color: #999; padding: 60px 0">选择左侧区域查看详情</div>

        <div v-else>
          <!-- 详情表单（只读） -->
          <NForm label-placement="left" label-width="100">
            <NSpace vertical :size="0">
              <NFormItem label="名称"><span>{{ formData.name }}</span></NFormItem>
              <NFormItem label="本地名称"><span>{{ formData.local_name || '-' }}</span></NFormItem>
              <NFormItem label="代码"><span>{{ formData.code || '-' }}</span></NFormItem>
              <NFormItem label="ISO Alpha-2"><span>{{ formData.iso_alpha2 || '-' }}</span></NFormItem>
              <NFormItem label="ISO Alpha-3"><span>{{ formData.iso_alpha3 || '-' }}</span></NFormItem>
              <NFormItem label="ISO Numeric"><span>{{ formData.iso_numeric || '-' }}</span></NFormItem>
              <NFormItem label="类型">
                <NTag type="info" size="small">{{ formData.region_type }}</NTag>
              </NFormItem>
              <NFormItem label="首都/首府"><span>{{ formData.capital || '-' }}</span></NFormItem>
              <NFormItem label="人口"><span>{{ formData.population?.toLocaleString() || '-' }}</span></NFormItem>
              <NFormItem label="面积"><span>{{ formData.area ? formData.area + ' km²' : '-' }}</span></NFormItem>
              <NFormItem label="经纬度"><span>{{ formData.latitude }}, {{ formData.longitude || '-' }}</span></NFormItem>
              <NFormItem label="时区"><span>{{ formData.timezone || '-' }}</span></NFormItem>
            </NSpace>
          </NForm>

          <!-- 子节点列表 -->
          <div style="margin-top: 16px">
            <h4 style="margin-bottom: 8px">子区域列表（{{ childrenList.length }}）</h4>
            <n-data-table
              :columns="childColumns"
              :data="childrenList"
              :loading="childrenLoading"
              :row-key="(row) => row.id"
              size="small"
              :bordered="true"
              stripe
              max-height="300"
            />
          </div>
        </div>
      </NCard>
    </div>

    <!-- 新增/编辑 弹窗 -->
    <NModal v-model:show="showCreateModal" title="区域信息" preset="card" style="width: 600px" :mask-closable="false">
      <NForm ref="formRef" :model="formData" :rules="formRules" label-placement="left" label-width="100">
        <NFormItem label="名称" path="name"><NInput v-model:value="formData.name" placeholder="如：中国" /></NFormItem>
        <NFormItem label="本地名称" path="local_name"><NInput v-model:value="formData.local_name" placeholder="如：China" /></NFormItem>
        <NFormItem label="代码" path="code"><NInput v-model:value="formData.code" placeholder="如：CN" /></NFormItem>
        <NFormItem label="ISO Alpha-2"><NInput v-model:value="formData.iso_alpha2" maxlength="2" placeholder="CN" /></NFormItem>
        <NFormItem label="ISO Alpha-3"><NInput v-model:value="formData.iso_alpha3" maxlength="3" placeholder="CHN" /></NFormItem>
        <NFormItem label="ISO Numeric"><NInput v-model:value="formData.iso_numeric" maxlength="3" placeholder="156" /></NFormItem>
        <NFormItem label="类型" path="region_type"><NSelect v-model:value="formData.region_type" :options="typeOptions" filterable /></NFormItem>
        <NFormItem label="父级ID"><NInputNumber v-model:value="formData.parent_id" :disabled="true" style="width: 100%" /></NFormItem>
        <NFormItem label="首都/首府"><NInput v-model:value="formData.capital" placeholder="如：北京" /></NFormItem>
        <NFormItem label="人口"><NInputNumber v-model:value="formData.population" :min="0" style="width: 100%" /></NFormItem>
        <NFormItem label="面积(km²)"><NInputNumber v-model:value="formData.area" :min="0" style="width: 100%" /></NFormItem>
        <NFormItem label="纬度"><NInputNumber v-model:value="formData.latitude" style="width: 100%" /></NFormItem>
        <NFormItem label="经度"><NInputNumber v-model:value="formData.longitude" style="width: 100%" /></NFormItem>
        <NFormItem label="时区"><NInput v-model:value="formData.timezone" placeholder="Asia/Shanghai" /></NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showCreateModal = false">取消</NButton>
          <NButton type="primary" :loading="formLoading" @click="onSave">保存</NButton>
        </NSpace>
      </template>
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

/* NCard 内容区撑满并滚动 */
.left-panel :deep(.n-card__content),
.right-panel :deep(.n-card__content) {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

/* 树节点文本截断 */
.left-panel :deep(.n-tree-node-content__text) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 滚动条美化 */
.left-panel :deep(.n-card__content)::-webkit-scrollbar,
.right-panel :deep(.n-card__content)::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.left-panel :deep(.n-card__content)::-webkit-scrollbar-thumb,
.right-panel :deep(.n-card__content)::-webkit-scrollbar-thumb {
  background-color: #c1c1c1;
  border-radius: 3px;
}
</style>