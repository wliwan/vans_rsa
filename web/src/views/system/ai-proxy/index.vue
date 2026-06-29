<script setup>
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {



  NButton,
  NInput,
  NInputNumber,
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
const { t } = useI18n()

import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: i18n.global.t('views.system.title_cn_ca9a28fd') })

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
  name: t('views.skill.label_cn_c1dfc5cf'),
  initForm: { name: '', url: '', token: '', model: '', max_tokens: 16384, user_ids: [] },
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
  modalTitle.value = t('views.system.title_cn_07d17e16')
  modalForm.value = {
    name: row.name + t('views.system.label_cn_33d1acb7'),
    url: row.url || '',
    token: row.token || '',
    model: row.model || '',
    max_tokens: row.max_tokens || 16384,
    user_ids: (row.users || []).map(u => u.id),
  }
  modalVisible.value = true
}

const columns = [
  {
    title: t('views.network.region.formLabels.name'), key: 'name', width: 60, align: 'center', ellipsis: { tooltip: true },
  },
  {
    title: t('views.system.title_cn_85624c8e'), key: 'url', width: 120, align: 'center', ellipsis: { tooltip: true },
  },
  {
    title: t('views.system.title_cn_8000f187'), key: 'model', width: 60, align: 'center', ellipsis: { tooltip: true },
  },
  {
    title: 'Max Tokens', key: 'max_tokens', width: 50, align: 'center',
  },
  {
    title: t('views.system.title_cn_9f66731b'), key: 'token', width: 70, align: 'center',
    render(row) {
      if (!row.token) return '-'
      return h(NTag, { type: 'info' }, { default: () => '****' + row.token.slice(-4) })
    },
  },
  {
    title: t('views.skill.label_cn_5f07f1ad'), key: 'users', width: 80, align: 'center',
    render(row) {
      const names = (row.users || []).map((u) => u.username).join(', ')
      return names || '-'
    },
  },
  {
    title: t('views.system.title_cn_a001a226'), key: 'updated_at', width: 80, align: 'center',
  },
  {
    title: t('views.network.roadNetworkWorkbench.tabs.fields.colActions'), key: 'actions', width: 120, align: 'center', fixed: 'right',
    render(row) {
      return [
        withDirectives(
          h(NButton, {
            size: 'small', type: 'primary', style: 'margin-right: 8px;',
            onClick: () => handleEditOverride(row),
          }, { default: () => t('views.workbench.label_edit'), icon: renderIcon('material-symbols:edit', { size: 16 }) }),
          [[vPermission, 'post/api/v1/ai-proxy/update']],
        ),
        withDirectives(
          h(NButton, {
            size: 'small', style: 'margin-right: 8px;',
            onClick: () => handleClone(row),
          }, { default: () => t('views.system.label_cn_25fe25ae'), icon: renderIcon('material-symbols:content-copy', { size: 16 }) }),
          [[vPermission, 'post/api/v1/ai-proxy/create']],
        ),
        h(NPopconfirm, {
          onPositiveClick: () => handleDelete({ name: row.name }),
        }, {
          trigger: () =>
            withDirectives(
              h(NButton, { size: 'small', type: 'error' }, {
                default: () => t('views.network.roadNetworkWorkbench.tabs.filter.delete'),
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
  <CommonPage :title="t('views.system.title_cn_ca9a28fd')">
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
        <NFormItem :label="t('views.system.label_cn_00d24bdf')" required>
          <NInput v-model:value="modalForm.name" :placeholder="t('views.system.label_cn_00d24bdf')" :disabled="modalAction === 'update'" />
        </NFormItem>
        <NFormItem :label="t('views.system.title_cn_85624c8e')">
          <NInput v-model:value="modalForm.url" :placeholder="t('views.system.placeholder_cn_f35edb23')" />
        </NFormItem>
        <NFormItem :label="t('views.system.label_cn_9add30c8')">
          <NInput v-model:value="modalForm.token" :placeholder="t('views.system.placeholder_cn_402a74ed')" />
        </NFormItem>
        <NFormItem :label="t('views.system.label_cn_920fe38e')">
          <NInput v-model:value="modalForm.model" :placeholder="t('views.system.placeholder_cn_5b6e06ac')" />
        </NFormItem>
        <NFormItem label="Max Tokens">
          <NInputNumber v-model:value="modalForm.max_tokens" :min="512" :max="131072" placeholder="单次最大输出 token 数" />
        </NFormItem>
        <NFormItem :label="t('views.skill.label_cn_5f07f1ad')">
          <NSelect
            v-model:value="modalForm.user_ids"
            :options="userOptions"
            multiple
            :placeholder="t('views.system.placeholder_cn_ddc1aac1')"
            filterable
          />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
