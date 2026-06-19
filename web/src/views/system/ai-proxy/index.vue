<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {
  NButton,
  NInput,
  NSelect,
  NTag,
  NPopconfirm,
  NForm,
  NFormItem,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: 'AI代理管理' })

const $table = ref(null)
const queryItems = ref({})
const vPermission = resolveDirective('permission')

const userOptions = ref([])

const {
  modalVisible,
  modalTitle,
  modalAction,
  modalLoading,
  handleSave,
  modalForm,
  modalFormRef,
  handleEdit,
  handleDelete,
  handleAdd,
} = useCRUD({
  name: 'AI代理',
  initForm: { name: '', url: '', token: '', model: '', user_ids: [] },
  doCreate: api.createAIProxy,
  doUpdate: api.updateAIProxy,
  doDelete: api.deleteAIProxy,
  refresh: () => $table.value?.handleSearch(),
})

onMounted(() => {
  $table.value?.handleSearch()
})

async function loadUserOptions() {
  try {
    const res = await api.getAIProxyUsers()
    userOptions.value = (res.data || []).map((u) => ({
      label: u.alias ? `${u.username} (${u.alias})` : u.username,
      value: u.id,
    }))
  } catch (e) { /* ignore */ }
}

function handleAddOverride() {
  loadUserOptions()
  handleAdd()
}

function handleEditOverride(row) {
  loadUserOptions()
  handleEdit(row)
}

function handleClone(row) {
  loadUserOptions()
  modalAction.value = 'add'
  modalTitle.value = '克隆AI代理'
  modalForm.value = {
    name: row.name + '_副本',
    url: row.url || '',
    token: row.token || '',
    model: row.model || '',
    user_ids: (row.users || []).map(u => u.id),
  }
  modalVisible.value = true
}

const columns = [
  {
    title: '名称', key: 'name', width: 60, align: 'center', ellipsis: { tooltip: true },
  },
  {
    title: '接口地址', key: 'url', width: 120, align: 'center', ellipsis: { tooltip: true },
  },
  {
    title: '模型', key: 'model', width: 60, align: 'center', ellipsis: { tooltip: true },
  },
  {
    title: '令牌', key: 'token', width: 70, align: 'center',
    render(row) {
      if (!row.token) return '-'
      return h(NTag, { type: 'info' }, { default: () => '****' + row.token.slice(-4) })
    },
  },
  {
    title: '授权用户', key: 'users', width: 80, align: 'center',
    render(row) {
      const names = (row.users || []).map((u) => u.username).join(', ')
      return names || '-'
    },
  },
  {
    title: '更新时间', key: 'updated_at', width: 80, align: 'center',
  },
  {
    title: '操作', key: 'actions', width: 120, align: 'center', fixed: 'right',
    render(row) {
      return [
        withDirectives(
          h(NButton, {
            size: 'small', type: 'primary', style: 'margin-right: 8px;',
            onClick: () => handleEditOverride(row),
          }, { default: () => '编辑', icon: renderIcon('material-symbols:edit', { size: 16 }) }),
          [[vPermission, 'post/api/v1/ai-proxy/update']],
        ),
        withDirectives(
          h(NButton, {
            size: 'small', style: 'margin-right: 8px;',
            onClick: () => handleClone(row),
          }, { default: () => '克隆', icon: renderIcon('material-symbols:content-copy', { size: 16 }) }),
          [[vPermission, 'post/api/v1/ai-proxy/create']],
        ),
        h(NPopconfirm, {
          onPositiveClick: () => handleDelete({ name: row.name }),
        }, {
          trigger: () =>
            withDirectives(
              h(NButton, { size: 'small', type: 'error' }, {
                default: () => '删除',
                icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
              }),
              [[vPermission, 'delete/api/v1/ai-proxy/delete']],
            ),
        }),
      ]
    },
  },
]
</script>

<template>
  <CommonPage title="AI代理管理">
    <template #action>
      <NButton
        v-permission="'post/api/v1/ai-proxy/create'"
        type="primary"
        @click="handleAddOverride"
      >
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新建
      </NButton>
    </template>

    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getAIProxyList"
    />

    <CrudModal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :loading="modalLoading"
      @save="handleSave"
    >
      <NForm ref="modalFormRef" :model="modalForm">
        <NFormItem label="代理名称" required>
          <NInput v-model:value="modalForm.name" placeholder="代理名称" :disabled="modalAction === 'update'" />
        </NFormItem>
        <NFormItem label="接口地址">
          <NInput v-model:value="modalForm.url" placeholder="接口地址（可选）" />
        </NFormItem>
        <NFormItem label="认证令牌">
          <NInput v-model:value="modalForm.token" placeholder="认证令牌（可选）" />
        </NFormItem>
        <NFormItem label="模型名称">
          <NInput v-model:value="modalForm.model" placeholder="如 gpt-4（可选）" />
        </NFormItem>
        <NFormItem label="授权用户">
          <NSelect
            v-model:value="modalForm.user_ids"
            :options="userOptions"
            multiple
            placeholder="选择可访问的用户"
            filterable
          />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
