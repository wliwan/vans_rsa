<script setup>
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import { h, onMounted, ref, reactive } from 'vue'
import {



  NButton,
  NDatePicker,
  NSelect,
  NSpace,
  NTag,
  NPopconfirm,
  NInput,
  useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

const { t } = useI18n()

defineOptions({ name: i18n.global.t('views.pixel.title_cn_32c6db68') })

const message = useMessage()
const $table = ref(null)

// 账户列表
const accountOptions = ref([])
const selectedAccount = ref(null)

// 日期范围
const dateRange = ref(null)

// 同步状态
const syncing = ref(false)

// 筛选参数
const queryItems = ref({
  road_name: '',
  risk_level_name: '',
  status_name: '',
})

// 表格列
const columns = [
  { title: t('views.pixel.title_cn_311a9e48'), key: 'risk_time', width: 160, ellipsis: { tooltip: true } },
  { title: t('views.pixel.title_cn_3f25ec9e'), key: 'road_name', width: 140, ellipsis: { tooltip: true } },
  {
    title: t('views.pixel.title_cn_25eb6ba3'),
    key: 'risk_level_name',
    width: 90,
    render(row) {
      const colorMap = { 低: 'info', 中等: 'warning', 高: 'error' }
      const color = colorMap[row.risk_level_name] || 'default'
      return h(NTag, { type: color, size: 'small' }, { default: () => row.risk_level_name || '-' })
    },
  },
  { title: t('views.pixel.title_cn_13514198'), key: 'risk_name3', width: 120, ellipsis: { tooltip: true } },
  {
    title: t('views.network.roadNetwork.fileColumns.status'),
    key: 'status_name',
    width: 100,
    render(row) {
      return h(NTag, { type: 'info', size: 'small' }, { default: () => row.status_name || '-' })
    },
  },
  { title: t('views.pixel.title_cn_a094e5b7'), key: 'data_from_name', width: 100, ellipsis: { tooltip: true } },
  { title: t('views.tool.vehicle.label_city'), key: 'city_name', width: 80 },
  { title: t('views.pixel.title_cn_188c235b'), key: 'car_no', width: 100 },
  { title: t('views.network.region.formLabels.longitude'), key: 'longitude', width: 90 },
  { title: t('views.network.region.formLabels.latitude'), key: 'latitude', width: 90 },
]

// 加载账户列表
async function loadAccounts() {
  try {
    const res = await api.getDefectAccounts()
    const accounts = res.data || []
    accountOptions.value = accounts.map((a) => ({
      label: `${a.username} (${a.tenant_address})`,
      value: a.id,
    }))
  } catch (e) {
    message.error(t('views.pixel.message_cn_819b786c'))
  }
}

// getData（CrudTable 需要的格式，闭包捕获 selectedAccount）
function getData(params) {
  return api.getDefectList({
    ...params,
    account_id: selectedAccount.value || undefined,
  })
}

// 同步数据
async function handleSync() {
  if (!selectedAccount.value) {
    message.warning(t('views.pixel.message_cn_9ba8511a'))
    return
  }
  if (!dateRange.value || dateRange.value.length !== 2) {
    message.warning(t('views.pixel.placeholder_cn_0e49c6f7'))
    return
  }

  syncing.value = true
  try {
    const [startTime, endTime] = dateRange.value
    const formatDate = (d) => {
      const y = d.getFullYear()
      const m = String(d.getMonth() + 1).padStart(2, '0')
      const day = String(d.getDate()).padStart(2, '0')
      return `${y}-${m}-${day}`
    }
    const res = await api.syncDefects({
      account_id: selectedAccount.value,
      start_time: formatDate(new Date(startTime)),
      end_time: formatDate(new Date(endTime)),
    })
    const result = res.data
    message.success(
      `同步完成：新增 ${result.data?.created || 0} 条，更新 ${result.data?.updated || 0} 条，API 共 ${result.data?.total_api || 0} 条`
    )
    $table.value?.handleSearch()
  } catch (e) {
    message.error(t('views.pixel.message_cn_a0f67c55') + (e.response?.data?.msg || e.message))
  } finally {
    syncing.value = false
  }
}

// 清除数据
async function handleClear() {
  if (!selectedAccount.value) {
    message.warning(t('views.pixel.message_cn_9ba8511a'))
    return
  }
  try {
    const res = await api.clearDefects({
      account_id: selectedAccount.value,
    })
    message.success(`已清除 ${res.data.data?.deleted || 0} 条数据`)
    $table.value?.handleSearch()
  } catch (e) {
    message.error(t('views.network.roadNetworkWorkbench.messages.clearCacheFail'))
  }
}

// 账户切换
function onAccountChange() {
  $table.value?.handleSearch()
}

onMounted(async () => {
  await loadAccounts()
  $table.value?.handleSearch()
})
</script>

<template>
  <CommonPage :title="t('views.pixel.title_cn_32c6db68')">
    <!-- 操作区：账户选择 + 日期选择 + 同步/清除 -->
    <NSpace align="center" style="margin-bottom: 12px">
      <span style="font-weight: 500">像素账户：</span>
      <NSelect
        v-model:value="selectedAccount"
        :options="accountOptions"
        :placeholder="t('views.pixel.placeholder_cn_7f19cdb7')"
        clearable
        style="width: 260px"
        @update:value="onAccountChange"
      />
      <span style="font-weight: 500; margin-left: 8px">时间段：</span>
      <NDatePicker
        v-model:value="dateRange"
        type="daterange"
        clearable
        style="width: 260px"
        :placeholder="t('views.pixel.placeholder_cn_542fdf02')"
      />
      <NButton type="primary" :loading="syncing" @click="handleSync">
        <TheIcon icon="material-symbols:sync" :size="18" class="mr-5" />同步数据
      </NButton>
      <NPopconfirm @positive-click="handleClear">
        <template #trigger>
          <NButton type="error" :disabled="!selectedAccount">
            <TheIcon icon="material-symbols:delete-outline" :size="18" class="mr-5" />清除数据
          </NButton>
        </template>
        确认清除该账户的所有病害数据？
      </NPopconfirm>
    </NSpace>

    <!-- 表格：使用 CrudTable -->
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="getData"
    >
      <template #queryBar>
        <QueryBarItem :label="t('views.pixel.title_cn_3f25ec9e')" :content="queryItems.road_name">
          <NInput
            v-model:value="queryItems.road_name"
            clearable
            :placeholder="t('views.pixel.placeholder_cn_33c3deb4')"
            @keydown.enter="$table.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem :label="t('views.pixel.title_cn_25eb6ba3')" :content="queryItems.risk_level_name">
          <NInput
            v-model:value="queryItems.risk_level_name"
            clearable
            :placeholder="t('views.pixel.placeholder_cn_77b366c3')"
            @keydown.enter="$table.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem :label="t('views.network.roadNetwork.fileColumns.status')" :content="queryItems.status_name">
          <NInput
            v-model:value="queryItems.status_name"
            clearable
            :placeholder="t('views.pixel.placeholder_cn_bcc12ba0')"
            @keydown.enter="$table.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>
  </CommonPage>
</template>
