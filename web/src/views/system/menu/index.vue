<script setup>
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import MenuI18nModal from './MenuI18nModal.vue'
import { h, onMounted, ref, resolveDirective, withDirectives, computed, nextTick } from 'vue'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NSpace,
  NSpin,
  NSwitch,
  NTree,
  NTreeSelect,
  NRadio,
  NRadioGroup,
  NTag,
  NSelect,
  NDivider,
  useMessage,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import IconPicker from '@/components/icon/IconPicker.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

import { formatDate, renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
const { t } = useI18n()

import api from '@/api'

defineOptions({ name: i18n.global.t('views.system.title_cn_310c10c1') })

const $table = ref(null)
const queryItems = ref({})
const vPermission = resolveDirective('permission')

// 表单初始化内容
const initForm = {
  order: 1,
  keepalive: true,
}

const {
  modalVisible,
  modalTitle,
  modalLoading,
  handleAdd,
  handleDelete,
  handleEdit,
  handleSave,
  modalForm,
  modalFormRef,
} = useCRUD({
  name: t('views.system.label_cn_4ccbdc53'),
  initForm,
  doCreate: api.createMenu,
  doDelete: api.deleteMenu,
  doUpdate: api.updateMenu,
  refresh: () => $table.value?.handleSearch(),
})

onMounted(() => {
  $table.value?.handleSearch()
  getTreeSelect()
})

// 是否展示 "菜单类型"
const showMenuType = ref(false)
const menuOptions = ref([])

const columns = [
  { title: 'ID', key: 'id', width: 50, ellipsis: { tooltip: true }, align: 'center' },
  { title: t('views.system.title_cn_8ee9f276'), key: 'name', width: 80, ellipsis: { tooltip: true }, align: 'center' },
  {
    title: t('views.system.title_cn_52fe00c3'),
    key: 'menu_type',
    width: 80,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      let round = false
      let bordered = false
      if (row.menu_type === 'catalog') {
        bordered = true
        round = false
      } else if (row.menu_type === 'menu') {
        bordered = false
        round = true
      }
      return h(
        NTag,
        { type: 'primary', round: round, bordered: bordered },
        { default: () => (row.menu_type === 'catalog' ? '目录' : t('views.system.label_cn_4ccbdc53')) }
      )
    },
  },
  {
    title: t('views.system.title_cn_5ef69f62'),
    key: 'icon',
    width: 40,
    align: 'center',
    render(row) {
      return h(TheIcon, { icon: row.icon, size: 20 })
    },
  },
  { title: t('views.system.label_cn_c360e994'), key: 'order', width: 40, ellipsis: { tooltip: true }, align: 'center' },
  { title: t('views.system.title_cn_d14fcd8f'), key: 'path', width: 80, ellipsis: { tooltip: true }, align: 'center' },
  { title: t('views.system.title_cn_0fec1892'), key: 'redirect', width: 80, ellipsis: { tooltip: true }, align: 'center' },
  { title: t('views.system.title_cn_f39bf763'), key: 'component', width: 80, ellipsis: { tooltip: true }, align: 'center' },
  {
    title: t('views.system.title_cn_bc28072c'),
    key: 'keepalive',
    width: 40,
    align: 'center',
    render(row) {
      return h(NSwitch, {
        size: 'small',
        rubberBand: false,
        value: row.keepalive,
        onUpdateValue: () => handleUpdateKeepalive(row),
      })
    },
  },
  {
    title: t('views.system.title_cn_dce5379c'),
    key: 'is_hidden',
    width: 40,
    align: 'center',
    render(row) {
      return h(NSwitch, {
        size: 'small',
        rubberBand: false,
        value: row.is_hidden,
        onUpdateValue: () => handleUpdateHidden(row),
      })
    },
  },
  {
    title: t('views.system.title_cn_696f5a97'),
    key: 'created_at',
    width: 80,
    align: 'center',
    render(row) {
      return h('span', formatDate(row.created_at))
    },
  },
  {
    title: t('views.network.roadNetworkWorkbench.tabs.fields.colActions'),
    key: 'actions',
    width: 120,
    align: 'center',
    fixed: 'right',
    render(row) {
      return [
        withDirectives(
          h(
            NButton,
            {
              size: 'tiny',
              quaternary: true,
              type: 'primary',
              style: `display: ${row.children && row.menu_type !== 'menu' ? '' : 'none'};`,
              onClick: () => {
                initForm.parent_id = row.id
                initForm.menu_type = 'menu'
                showMenuType.value = false
                handleAdd()
              },
            },
            { default: () => t('views.system.label_cn_26f9bff7'), icon: renderIcon('material-symbols:add', { size: 16 }) }
          ),
          [[vPermission, 'post/api/v1/menu/create']]
        ),
        withDirectives(
          h(
            NButton,
            {
              size: 'tiny',
              quaternary: true,
              type: 'info',
              onClick: () => {
                showMenuType.value = false
                handleEdit(row)
              },
            },
            {
              default: () => t('views.workbench.label_edit'),
              icon: renderIcon('material-symbols:edit-outline', { size: 16 }),
            }
          ),
          [[vPermission, 'post/api/v1/menu/update']]
        ),
        h(
          NPopconfirm,
          {
            onPositiveClick: () => handleDelete({ id: row.id }, false),
          },
          {
            trigger: () =>
              withDirectives(
                h(
                  NButton,
                  {
                    size: 'tiny',
                    quaternary: true,
                    type: 'error',
                    style: `display: ${row.children && row.children.length > 0 ? 'none' : ''};`,
                  },
                  {
                    default: () => t('views.network.roadNetworkWorkbench.tabs.filter.delete'),
                    icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                  }
                ),
                [[vPermission, 'delete/api/v1/menu/delete']]
              ),
            default: () => h('div', {}, t('views.system.label_cn_ee097e23')),
          }
        ),
      ]
    },
  },
]
// 修改是否keepalive
async function handleUpdateKeepalive(row) {
  if (!row.id) return
  row.publishing = true
  row.keepalive = row.keepalive === false ? true : false
  await api.updateMenu(row)
  row.publishing = false
  $message?.success(row.keepalive ? '已开启' : t('views.system.label_cn_9c58505d'))
}

// 修改是否隐藏
async function handleUpdateHidden(row) {
  if (!row.id) return
  row.publishing = true
  row.is_hidden = row.is_hidden === false ? true : false
  await api.updateMenu(row)
  row.publishing = false
  $message?.success(row.is_hidden ? '已隐藏' : t('views.system.label_cn_47f038fd'))
}

// 新增菜单(可选目录)
function handleClickAdd() {
  initForm.parent_id = 0
  initForm.menu_type = 'catalog'
  initForm.is_hidden = false
  initForm.order = 1
  initForm.keepalive = true
  showMenuType.value = true
  handleAdd()
}

async function getTreeSelect() {
  const { data } = await api.getMenus()
  const menu = { id: 0, name: t('views.system.label_cn_c2b9f4b9'), children: [] }
  menu.children = data
  menuOptions.value = [menu]
}

// ============================================================
// AI 智能视图
// ============================================================
const message = useMessage()
const showAIModal = ref(false)
const aiLoading = ref(false)
const aiSaving = ref(false)
const aiStep = ref('config') // 'config' | 'result'

// AI 配置
const selectedProxy = ref(null)
const proxyOptions = ref([])
const extraPrompt = ref('')

// 扫描视图树（原始数据）
const scanTreeData = ref([])

// AI 生成的菜单树（可编辑）
const menuTreeData = ref([])

// 选中的节点路径（NTree key）
const selectedMenuKey = ref(null)

// 当前编辑的节点（找到对应节点引用）
const editingNode = ref(null)

// 节点选中后自动回填编辑表单
function onMenuNodeSelect(keys) {
  if (keys.length > 0) {
    selectedMenuKey.value = keys[0]
    editingNode.value = findNodeByKey(menuTreeData.value, keys[0])
  } else {
    selectedMenuKey.value = null
    editingNode.value = null
  }
}

// 在菜单树中根据 key 查找节点
function findNodeByKey(nodes, key) {
  for (const node of nodes) {
    if (node._key === key) return node
    if (node.children && node.children.length > 0) {
      const found = findNodeByKey(node.children, key)
      if (found) return found
    }
  }
  return null
}

// 给菜单树节点分配唯一 key，并设置默认勾选
let _keyCounter = 0
function assignKeys(nodes, parentPath = '') {
  for (const node of nodes) {
    node._key = `node_${++_keyCounter}`
    node._parent = parentPath
    node._checked = true
    if (node.children && node.children.length > 0) {
      assignKeys(node.children, node._key)
    }
  }
}

// 收集树中所有节点的 key
function collectAllKeys(nodes) {
  const keys = []
  for (const node of nodes) {
    keys.push(node._key)
    if (node.children && node.children.length > 0) {
      keys.push(...collectAllKeys(node.children))
    }
  }
  return keys
}

// 根据 checkedKeys 过滤菜单树，只保留勾选的节点
function filterTreeByKeys(nodes, checkedSet) {
  const result = []
  for (const node of nodes) {
    if (!checkedSet.has(node._key)) continue
    const filtered = { ...node }
    if (node.children && node.children.length > 0) {
      const filteredChildren = filterTreeByKeys(node.children, checkedSet)
      if (filteredChildren.length > 0) {
        filtered.children = filteredChildren
      } else {
        delete filtered.children
      }
    }
    result.push(filtered)
  }
  return result
}

// 勾选状态
const checkedKeys = ref([])
const allKeysCount = computed(() => menuTreeData.value.length ? collectAllKeys(menuTreeData.value).length : 0)
const checkedCount = computed(() => checkedKeys.value.length)

function handleCheckAll() {
  if (checkedKeys.value.length === allKeysCount.value) {
    checkedKeys.value = []
  } else {
    checkedKeys.value = collectAllKeys(menuTreeData.value)
  }
}

// 将菜单树转为 NTree 可用的格式
function toTreeData(nodes) {
  return nodes.map(node => ({
    label: `${node.icon ? '🔹 ' : ''}${node.name}  [${node.menu_type === 'catalog' ? '目录' : '菜单'}] ${node.path}`,
    key: node._key,
    children: node.children && node.children.length > 0 ? toTreeData(node.children) : undefined,
  }))
}

const treeDataComputed = computed(() => toTreeData(menuTreeData.value))

// 加载 AI 代理列表
async function loadProxyList() {
  try {
    const res = await api.getAIProxyList({ page: 1, page_size: 100 })
    proxyOptions.value = (res.data || []).map(p => ({
      label: `${p.name} (${p.model || 'unknown'})`,
      value: p.name,
    }))
  } catch (e) {
    message.error('加载AI代理列表失败')
  }
}

// 打开 AI 智能视图弹窗
async function handleAIScanViews() {
  showAIModal.value = true
  aiStep.value = 'config'
  aiLoading.value = true
  selectedMenuKey.value = null
  editingNode.value = null
  menuTreeData.value = []
  selectedProxy.value = null
  extraPrompt.value = ''

  try {
    // 加载代理列表 + 扫描视图
    await Promise.all([
      loadProxyList(),
      (async () => {
        const res = await api.scanViews()
        scanTreeData.value = res.data || []
      })(),
    ])
  } catch (e) {
    message.error('加载数据失败')
  } finally {
    aiLoading.value = false
  }
}

// 开始 AI 分析
async function handleAIAnalyze() {
  if (!selectedProxy.value) {
    message.warning('请先选择AI代理')
    return
  }

  aiLoading.value = true
  aiStep.value = 'config'
  menuTreeData.value = []
  selectedMenuKey.value = null
  editingNode.value = null

  try {
    const res = await api.aiAnalyzeViews({
      proxy_name: selectedProxy.value,
      extra_prompt: extraPrompt.value || '',
    })
    const menuTree = res.data?.menu_tree || []

    // 分配唯一 key，默认全选
    _keyCounter = 0
    assignKeys(menuTree)
    menuTreeData.value = menuTree
    checkedKeys.value = collectAllKeys(menuTree)

    aiStep.value = 'result'
    message.success('AI分析完成，勾选需要导入的菜单后点提交')
  } catch (e) {
    message.error('AI分析失败: ' + (e.message || '未知错误'))
  } finally {
    aiLoading.value = false
  }
}

// 重新分析
function handleReAnalyze() {
  aiStep.value = 'config'
  menuTreeData.value = []
  checkedKeys.value = []
  selectedMenuKey.value = null
  editingNode.value = null
}

// 提交保存
async function handleAISubmit() {
  if (menuTreeData.value.length === 0) {
    message.warning('没有可保存的菜单数据')
    return
  }

  // 先按勾选过滤，再清理前端字段
  const checkedSet = new Set(checkedKeys.value)
  const filteredTree = filterTreeByKeys(menuTreeData.value, checkedSet)
  if (filteredTree.length === 0) {
    message.warning('请至少勾选一个菜单项')
    return
  }

  function cleanNode(node) {
    const { _key, _parent, _checked, children, ...rest } = node
    const cleaned = { ...rest }
    if (children && children.length > 0) {
      cleaned.children = children.map(cleanNode)
    }
    return cleaned
  }

  const cleanedTree = filteredTree.map(cleanNode)

  aiSaving.value = true
  try {
    await api.batchSaveMenus({ menu_tree: cleanedTree })
    message.success('菜单已全部保存')
    showAIModal.value = false
    // 刷新主列表
    $table.value?.handleSearch()
    await getTreeSelect()
  } catch (e) {
    message.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    aiSaving.value = false
  }
}

// 复制视图路径
async function copyViewPath(path) {
  try {
    await navigator.clipboard.writeText(path)
    message.success(`已复制: ${path}`)
  } catch {
    // 降级方案
    const textarea = document.createElement('textarea')
    textarea.value = path
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    message.success(`已复制: ${path}`)
  }
}

function getViewNodeProps({ option }) {
  return {
    onClick: (e) => {
      e.stopPropagation()
      copyViewPath(option.path)
    },
    style: { cursor: 'pointer' },
    title: '点击复制路径',
  }
}

// 关闭弹窗
function handleCloseAIModal() {
  showAIModal.value = false
}

// ============================================================
// 导出 / 导入
// ============================================================
const importFileRef = ref(null)

// 导出菜单为 JSON 文件
async function handleExport() {
  try {
    const res = await api.exportMenus()
    const blob = res.data instanceof Blob ? res.data : new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'menu-export.json'
    a.click()
    URL.revokeObjectURL(url)
    message.success('菜单已导出')
  } catch (e) {
    message.error('导出失败')
  }
}

// 触发文件选择
function handleImportClick() {
  importFileRef.value?.click()
}

const showI18nModal = ref(false)

// 导入菜单 JSON 文件
async function handleImportFile(e) {
  const file = e.target?.files?.[0]
  if (!file) return
  try {
    await api.importMenus(file)
    message.success('菜单已导入')
    $table.value?.handleSearch()
    await getTreeSelect()
  } catch (err) {
    message.error('导入失败: ' + (err.message || '未知错误'))
  } finally {
    // 重置 input 以允许重复选择同一文件
    e.target.value = ''
  }
}
</script>

<template>
  <!-- 业务页面 -->
  <CommonPage show-footer :title="t('views.system.title_cn_a6522480')">
    <template #action>
      <NSpace>
        <NButton v-permission="'post/api/v1/menu/create'" type="primary" @click="handleClickAdd">
          <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新建根菜单
        </NButton>
        <NButton secondary @click="handleAIScanViews">
          <TheIcon icon="material-symbols:auto-awesome" :size="18" class="mr-5" />AI智能视图
        </NButton>
        <NButton secondary @click="showI18nModal = true">
          <TheIcon icon="material-symbols:translate" :size="18" class="mr-5" />国际化管理
        </NButton>
        <NButton secondary @click="handleExport">
          <TheIcon icon="material-symbols:download" :size="18" class="mr-5" />导出
        </NButton>
        <NButton secondary @click="handleImportClick">
          <TheIcon icon="material-symbols:upload" :size="18" class="mr-5" />导入
        </NButton>
        <input
          ref="importFileRef"
          type="file"
          accept=".json"
          style="display: none"
          @change="handleImportFile"
        />
      </NSpace>
    </template>

    <!-- 表格 -->
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :is-pagination="false"
      :columns="columns"
      :get-data="api.getMenus"
      :single-line="true"
    >
    </CrudTable>

    <!-- 新增/编辑/查看 弹窗 -->
    <CrudModal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :loading="modalLoading"
      @save="handleSave(getTreeSelect)"
    >
      <NForm
        ref="modalFormRef"
        label-placement="left"
        label-align="left"
        :label-width="80"
        :model="modalForm"
      >
        <NFormItem :label="t('views.system.title_cn_52fe00c3')" path="menu_type">
          <NRadioGroup v-model:value="modalForm.menu_type">
            <NRadio :label="t('views.system.label_cn_767fa455')" value="catalog" />
            <NRadio :label="t('views.system.label_cn_4ccbdc53')" value="menu" />
          </NRadioGroup>
        </NFormItem>
        <NFormItem :label="t('views.system.label_cn_8427054c')" path="parent_id">
          <NTreeSelect
            v-model:value="modalForm.parent_id"
            key-field="id"
            label-field="name"
            :options="menuOptions"
            default-expand-all="true"
          />
        </NFormItem>
        <NFormItem
          :label="t('views.system.title_cn_8ee9f276')"
          path="name"
          :rule="{
            required: true,
            message: t('views.system.placeholder_cn_fb389b09'),
            trigger: ['input', 'blur'],
          }"
        >
          <NInput v-model:value="modalForm.name" :placeholder="t('views.system.placeholder_cn_fb389b09')" />
        </NFormItem>
        <NFormItem
          :label="t('views.system.title_cn_d14fcd8f')"
          path="path"
          :rule="{
            required: true,
            message: t('views.system.placeholder_cn_26942298'),
            trigger: ['blur'],
          }"
        >
          <NInput v-model:value="modalForm.path" :placeholder="t('views.system.placeholder_cn_26942298')" />
        </NFormItem>
        <NFormItem v-if="modalForm.menu_type === 'menu'" :label="t('views.system.title_cn_f39bf763')" path="component">
          <NInput
            v-model:value="modalForm.component"
            :placeholder="t('views.system.placeholder_cn_1d8242f1')"
          />
        </NFormItem>
        <NFormItem :label="t('views.system.title_cn_0fec1892')" path="redirect">
          <NInput
            v-model:value="modalForm.redirect"
            :disabled="modalForm.parent_id !== 0"
            :placeholder="
              modalForm.parent_id !== 0 ? '只有一级菜单可以设置跳转路径' : t('views.system.placeholder_cn_266e7f8a')
            "
          />
        </NFormItem>
        <NFormItem :label="t('views.system.label_cn_9483042d')" path="icon">
          <IconPicker v-model:value="modalForm.icon" />
        </NFormItem>
        <NFormItem :label="t('views.system.label_cn_53295d54')" path="order">
          <NInputNumber v-model:value="modalForm.order" :min="1" />
        </NFormItem>
        <NFormItem :label="t('views.system.label_cn_1a493fc3')" path="is_hidden">
          <NSwitch v-model:value="modalForm.is_hidden" />
        </NFormItem>
        <NFormItem label="KeepAlive" path="keepalive">
          <NSwitch v-model:value="modalForm.keepalive" />
        </NFormItem>
      </NForm>
    </CrudModal>

    <!-- ============================================================ -->
    <!-- AI 智能视图弹窗 -->
    <!-- ============================================================ -->
    <NModal
      v-model:show="showAIModal"
      title="AI智能视图"
      preset="card"
      style="width: 960px; max-height: 85vh"
      @mask-click="null"
    >
      <template #header>
        <span style="display: flex; align-items: center; gap: 8px">
          <TheIcon icon="material-symbols:auto-awesome" :size="20" /> AI智能视图
        </span>
      </template>

      <div style="min-height: 400px; display: flex; flex-direction: column; gap: 12px">
        <NSpin :show="aiLoading">
          <!-- ========= 配置阶段 ========= -->
          <template v-if="aiStep === 'config'">
            <!-- AI 配置区域 -->
            <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap">
              <span style="font-weight: 600; white-space: nowrap; min-width: 56px">AI代理：</span>
              <NSelect
                v-model:value="selectedProxy"
                :options="proxyOptions"
                placeholder="选择AI代理"
                style="flex: 1; min-width: 200px"
                clearable
              />
              <span style="font-weight: 600; white-space: nowrap; min-width: 56px">提示词：</span>
              <NInput
                v-model:value="extraPrompt"
                placeholder="额外提示词（可选）"
                style="flex: 1; min-width: 200px"
                clearable
              />
              <NButton type="primary" :loading="aiLoading" @click="handleAIAnalyze">
                <TheIcon icon="material-symbols:play-arrow" :size="16" class="mr-4" />开始分析
              </NButton>
            </div>

            <NDivider style="margin: 8px 0" />

            <!-- 视图结构预览 -->
            <p style="color: var(--n-text-color-3); font-size: 13px; margin-bottom: 8px">
              以下为 <code>web/src/views/</code> 下的视图文件夹，AI 将据此分析生成菜单：
            </p>
            <div
              v-if="scanTreeData.length === 0"
              style="color: var(--n-text-color-3); text-align: center; padding: 20px 0"
            >
              未扫描到视图文件夹
            </div>
            <NTree
              v-if="scanTreeData.length > 0"
              :data="scanTreeData"
              label-field="path"
              key-field="path"
              :default-expand-all="true"
              :node-props="getViewNodeProps"
              block-line
              style="max-height: 320px; overflow: auto; border: 1px solid var(--n-border-color); border-radius: 4px; padding: 8px"
            />
          </template>

          <!-- ========= 结果阶段 ========= -->
          <template v-if="aiStep === 'result' && menuTreeData.length > 0">
            <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 4px; flex-wrap: wrap">
              <NButton size="small" secondary @click="handleReAnalyze">
                <TheIcon icon="material-symbols:arrow-back" :size="14" class="mr-4" />返回重配
              </NButton>
              <NButton size="small" secondary @click="handleCheckAll">
                {{ checkedCount === allKeysCount ? '取消全选' : '全选' }}
                ({{ checkedCount }}/{{ allKeysCount }})
              </NButton>
              <span style="color: var(--n-text-color-3); font-size: 13px">
                AI 已生成菜单，勾选需要导入的项，然后点「提交保存」
              </span>
            </div>

            <NDivider style="margin: 4px 0" />

            <!-- 双面板：树 + 编辑表单 -->
            <div style="display: flex; gap: 12px; flex: 1; min-height: 420px; max-height: 55vh; overflow: hidden">
              <!-- 左侧：菜单树（可勾选） -->
              <div style="width: 380px; flex-shrink: 0; overflow: auto; border: 1px solid var(--n-border-color); border-radius: 4px; padding: 8px">
                <NTree
                  :data="treeDataComputed"
                  :selected-keys="selectedMenuKey ? [selectedMenuKey] : []"
                  :checked-keys="checkedKeys"
                  :default-expand-all="true"
                  block-line
                  selectable
                  checkable
                  cascade
                  style="height: 100%"
                  @update:selected-keys="onMenuNodeSelect"
                  @update:checked-keys="(keys) => checkedKeys = keys"
                />
              </div>

              <!-- 右侧：编辑面板 -->
              <div style="flex: 1; min-width: 0; overflow: auto; border: 1px solid var(--n-border-color); border-radius: 4px; padding: 16px">
                <template v-if="editingNode">
                  <h4 style="margin: 0 0 12px; color: var(--n-text-color)">
                    <TheIcon :icon="editingNode.icon || 'ph:folder-duotone'" :size="18" style="vertical-align: middle" />
                    {{ editingNode.name }}
                  </h4>
                  <NForm label-placement="left" label-align="left" :label-width="80" size="small">
                    <NFormItem label="菜单名称" path="_name">
                      <NInput v-model:value="editingNode.name" />
                    </NFormItem>
                    <NFormItem label="菜单类型">
                      <NRadioGroup v-model:value="editingNode.menu_type">
                        <NRadio value="catalog">目录</NRadio>
                        <NRadio value="menu">菜单</NRadio>
                      </NRadioGroup>
                    </NFormItem>
                    <NFormItem label="图标">
                      <IconPicker v-model:value="editingNode.icon" />
                    </NFormItem>
                    <NFormItem label="排序">
                      <NInputNumber v-model:value="editingNode.order" :min="1" style="width: 100px" />
                    </NFormItem>
                    <NFormItem label="访问路径">
                      <NInput v-model:value="editingNode.path" />
                    </NFormItem>
                    <NFormItem label="跳转路径">
                      <NInput v-model:value="editingNode.redirect" placeholder="仅一级目录菜单可设置" />
                    </NFormItem>
                    <NFormItem label="组件路径">
                      <NInput v-model:value="editingNode.component" />
                    </NFormItem>
                    <NFormItem label="保活">
                      <NSwitch v-model:value="editingNode.keepalive" />
                    </NFormItem>
                    <NFormItem label="隐藏">
                      <NSwitch v-model:value="editingNode.is_hidden" />
                    </NFormItem>
                  </NForm>
                </template>
                <template v-else>
                  <div style="color: var(--n-text-color-3); text-align: center; padding: 60px 0; font-size: 14px">
                    <TheIcon icon="material-symbols:touch-app-outline" :size="40" style="opacity: 0.3" />
                    <p>点击左侧菜单节点查看和编辑详情</p>
                  </div>
                </template>
              </div>
            </div>
          </template>
        </NSpin>
      </div>

      <template #footer>
        <NSpace justify="space-between" style="width: 100%">
          <span style="color: var(--n-text-color-3); font-size: 12px">
            {{ aiStep === 'result' ? `共 ${menuTreeData.length} 个一级菜单` : '选择AI代理后点击「开始分析」' }}
          </span>
          <NSpace>
            <NButton @click="handleCloseAIModal" :disabled="aiSaving">关闭</NButton>
            <NButton v-if="aiStep === 'result'" type="primary" :loading="aiSaving" @click="handleAISubmit">
              <TheIcon icon="material-symbols:save" :size="16" class="mr-4" />提交保存
            </NButton>
          </NSpace>
        </NSpace>
      </template>
    </NModal>

    <!-- 菜单国际化管理弹窗 -->
    <MenuI18nModal v-model:visible="showI18nModal" />
  </CommonPage>
</template>