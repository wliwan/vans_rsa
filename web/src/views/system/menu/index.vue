<script setup>
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
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
                    style: `display: ${row.children && row.children.length > 0 ? 'none' : ''};`, //有子菜单不允许删除
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

// 扫描视图
const message = useMessage()
const showScanModal = ref(false)
const scanLoading = ref(false)
const scanTreeData = ref([])
const selectedScanPath = ref('')

async function handleScanViews() {
  showScanModal.value = true
  scanLoading.value = true
  selectedScanPath.value = ''
  try {
    const res = await api.scanViews()
    scanTreeData.value = res.data || []
  } catch (e) {
    message.error(t('views.system.message_cn_646928c1'))
  } finally {
    scanLoading.value = false
  }
}

function onScanNodeSelect(keys) {
  if (keys.length > 0) {
    selectedScanPath.value = keys[0]
  }
}

async function copyScanPath() {
  if (!selectedScanPath.value) return
  try {
    await navigator.clipboard.writeText(selectedScanPath.value)
    message.success(t('views.system.message_cn_4fb42e6e'))
  } catch {
    message.warning(t('views.system.message_cn_41da1ca4'))
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
        <NButton secondary @click="handleScanViews">
          <TheIcon icon="material-symbols:folder-open-outline" :size="18" class="mr-5" />扫描视图
        </NButton>
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
      <!-- 表单 -->
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

    <!-- 扫描视图弹窗 -->
    <NModal
      v-model:show="showScanModal"
      :title="t('views.system.title_cn_8397ac5b')"
      preset="card"
      style="width: 600px; max-height: 80vh"
    >
      <template #header>
        <span>视图文件夹扫描结果</span>
      </template>
      <div style="min-height: 200px">
        <NSpin :show="scanLoading">
          <p style="color: var(--n-text-color-3); margin-bottom: 12px; font-size: 13px">
            以下是 <code>web/src/views/</code> 下的所有视图文件夹，可用于菜单配置中的「组件路径」字段。
          </p>
          <div
            v-if="!scanLoading && scanTreeData.length === 0"
            style="color: var(--n-text-color-3); text-align: center; padding: 40px 0"
          >
            未扫描到视图文件夹
          </div>
          <div
            v-if="!scanLoading && scanTreeData.length > 0"
            style="display: flex; flex-direction: column; gap: 12px"
          >
            <NTree
              :data="scanTreeData"
              label-field="path"
              key-field="path"
              :default-expand-all="true"
              block-line
              selectable
              style="max-height: 50vh; overflow: auto; border: 1px solid var(--n-border-color); border-radius: 4px; padding: 8px"
              @update:selected-keys="onScanNodeSelect"
            />
            <div
              v-if="selectedScanPath"
              style="
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 8px 12px;
                background: var(--n-color-embedded);
                border-radius: 4px;
              "
            >
              <span style="color: var(--n-text-color-2); font-size: 13px">已选路径：</span>
              <code style="font-size: 13px; flex: 1">{{ selectedScanPath }}</code>
              <NButton size="tiny" secondary @click="copyScanPath">复制</NButton>
            </div>
          </div>
        </NSpin>
      </div>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showScanModal = false">关闭</NButton>
        </NSpace>
      </template>
    </NModal>
  </CommonPage>
</template>
