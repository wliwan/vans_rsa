<script setup>
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NSpace,
  NTag,
  NPopconfirm,
  NSelect,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

const { t } = useI18n()

defineOptions({ name: i18n.global.t('views.pixel.title_cn_2375de65') })

const $table = ref(null)
const queryItems = ref({})
const vPermission = resolveDirective('permission')

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
  name: t('views.pixel.label_cn_e034af06'),
  initForm: { user_ids: [] },
  doCreate: api.createPixelAccount,
  doUpdate: api.updatePixelAccount,
  doDelete: api.deletePixelAccount,
  refresh: () => $table.value?.handleSearch(),
})

const userOptions = ref([])

onMounted(() => {
  $table.value?.handleSearch()
  api.getUserList({ page: 1, page_size: 9999 }).then((res) => {
    userOptions.value = (res.data || []).map((u) => ({
      label: `${u.username} (${u.email})`,
      value: u.id,
    }))
  })
})

const columns = [
  {
    title: t('views.pixel.title_cn_819767ad'),
    key: 'username',
    width: 80,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: t('views.pixel.title_cn_3f173571'),
    key: 'tenant_address',
    width: 80,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: t('views.network.roadNetwork.levelLabel.country'),
    key: 'country',
    width: 80,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return row.country || '-'
    },
  },
  {
    title: t('views.pixel.title_cn_d3ce40d8'),
    key: 'state',
    width: 80,
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return row.state || '-'
    },
  },
  {
    title: t('views.pixel.title_cn_44e1fa6f'),
    key: 'users',
    width: 150,
    align: 'center',
    render(row) {
      const userList = row.users ?? []
      const group = []
      for (let i = 0; i < userList.length; i++)
        group.push(
          h(NTag, { type: 'info', style: { margin: '2px 3px' } }, { default: () => userList[i].username })
        )
      return group.length ? h('span', group) : h('span', '-')
    },
  },
  {
    title: t('views.network.roadNetworkWorkbench.tabs.fields.colActions'),
    key: 'actions',
    width: 80,
    align: 'center',
    fixed: 'right',
    render(row) {
      return [
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              type: 'primary',
              style: 'margin-right: 8px;',
              onClick: () => {
                handleEdit(row)
                modalForm.value.user_ids = (row.users || []).map((u) => u.id)
              },
            },
            {
              default: () => t('views.workbench.label_edit'),
              icon: renderIcon('material-symbols:edit', { size: 16 }),
            }
          ),
          [[vPermission, 'post/api/v1/pixel-account/update']]
        ),
        h(
          NPopconfirm,
          {
            onPositiveClick: () => handleDelete({ account_id: row.id }),
          },
          {
            trigger: () =>
              withDirectives(
                h(
                  NButton,
                  {
                    size: 'small',
                    type: 'error',
                  },
                  {
                    default: () => t('views.network.roadNetworkWorkbench.tabs.filter.delete'),
                    icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
                  }
                ),
                [[vPermission, 'delete/api/v1/pixel-account/delete']]
              ),
          }
        ),
      ]
    },
  },
]

function onClose() {
  modalForm.value = { user_ids: [] }
}
</script>

<template>
  <CommonPage :title="t('views.pixel.title_cn_2375de65')">
    <template #action>
      <NButton
        v-permission="'post/api/v1/pixel-account/create'"
        type="primary"
        @click="handleAdd"
      >
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新建账户
      </NButton>
    </template>

    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getPixelAccountList"
    >
      <template #queryBar>
        <QueryBarItem :label="t('views.pixel.title_cn_819767ad')" :content="queryItems.username">
          <NInput
            v-model:value="queryItems.username"
            clearable
            :placeholder="t('views.pixel.placeholder_cn_08b1fa13')"
            @keydown.enter="$table.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem :label="t('views.pixel.title_cn_3f173571')" :content="queryItems.tenant_address">
          <NInput
            v-model:value="queryItems.tenant_address"
            clearable
            :placeholder="t('views.pixel.placeholder_cn_e8e90126')"
            @keydown.enter="$table.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :loading="modalLoading"
      :width="'700px'"
      @save="handleSave"
      @update:visible="onClose"
    >
      <NForm
        ref="modalFormRef"
        label-placement="left"
        label-width="auto"
        :model="modalForm"
      >
        <NFormItem label="用户名" path="username" :rule="{ required: true, message: t('views.pixel.placeholder_cn_50a8a4cf') }">
          <NInput v-model:value="modalForm.username" :placeholder="t('views.pixel.placeholder_cn_50a8a4cf')" />
        </NFormItem>
        <NFormItem label="密码" path="password" :rule="{ required: true, message: t('views.pixel.placeholder_cn_9afe700f') }">
          <NInput v-model:value="modalForm.password" type="password" :placeholder="t('views.pixel.placeholder_cn_9afe700f')" />
        </NFormItem>
        <NFormItem label="租户地址" path="tenant_address" :rule="{ required: true, message: t('views.pixel.placeholder_cn_955d007f') }">
          <NInput v-model:value="modalForm.tenant_address" :placeholder="t('views.pixel.placeholder_cn_46af0b32')" />
        </NFormItem>
        <NFormItem :label="t('views.pixel.title_cn_44e1fa6f')" path="user_ids">
          <NSelect
            v-model:value="modalForm.user_ids"
            multiple
            filterable
            :placeholder="t('views.pixel.placeholder_cn_592e44a3')"
            :options="userOptions"
          />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
