<script setup>
import { h, onMounted, ref } from 'vue'
import {
  NButton,
  NDatePicker,
  NInput,
  NSelect,
  NSpace,
  NTag,
  NPopconfirm,
  useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

defineOptions({ name: '轨迹点数据管理' })

const message = useMessage()
const $table = ref(null)

// 账户下拉
const accountOptions = ref([])
const selectedAccount = ref(null)

// 车型下拉
const carTypeOptions = ref([])
const selectedCarType = ref(null)
const carTypesLoading = ref(false)

// 车辆下拉
const carOptions = ref([])
const selectedCar = ref(null)
const carsLoading = ref(false)

// 日期范围
const dateRange = ref(null)

// 同步状态
const syncing = ref(false)

// 筛选参数
const queryItems = ref({
  car_id: '',
  road_name: '',
})

// 表格列
const columns = [
  { title: '轨迹时间', key: 'track_time', width: 160, ellipsis: { tooltip: true } },
  { title: '车辆ID', key: 'car_id', width: 160, ellipsis: { tooltip: true } },
  { title: '道路名称', key: 'road_name', width: 180, ellipsis: { tooltip: true } },
  {
    title: '车辆类型',
    key: 'car_type',
    width: 90,
    render(row) {
      const typeMap = { 1: '小客车', 2: '巡检车', 3: '其他' }
      return h('span', typeMap[row.car_type] || `类型${row.car_type}`)
    },
  },
  { title: '经度', key: 'longitude', width: 100, ellipsis: { tooltip: true } },
  { title: '纬度', key: 'latitude', width: 100, ellipsis: { tooltip: true } },
  {
    title: '标志',
    key: 'flag',
    width: 70,
    render(row) {
      return h(NTag, { type: row.flag === 1 ? 'success' : 'default', size: 'small' }, { default: () => row.flag ?? '-' })
    },
  },
]

// 加载账户列表
async function loadAccounts() {
  try {
    const res = await api.getTrackAccounts()
    const accounts = res.data || []
    accountOptions.value = accounts.map((a) => ({
      label: `${a.username} (${a.tenant_address})`,
      value: a.id,
    }))
  } catch (e) {
    message.error('获取账户列表失败')
  }
}

// 账户切换 → 加载车型
async function onAccountChange(value) {
  selectedCarType.value = null
  selectedCar.value = null
  carOptions.value = []
  carTypeOptions.value = []

  if (!value) {
    $table.value?.handleSearch()
    return
  }

  carTypesLoading.value = true
  try {
    const res = await api.getTrackCarTypes({ account_id: value })
    const types = res.data || []
    carTypeOptions.value = types.map((t) => ({
      label: `${t.name} (type=${t.type})`,
      value: t.type,
    }))
  } catch (e) {
    message.error('获取车型列表失败')
  } finally {
    carTypesLoading.value = false
  }

  $table.value?.handleSearch()
}

// 车型切换 → 加载车辆
async function onCarTypeChange(value) {
  selectedCar.value = null
  carOptions.value = []

  if (!value || !selectedAccount.value) return

  carsLoading.value = true
  try {
    const res = await api.getTrackCars({
      account_id: selectedAccount.value,
      car_type: value,
    })
    const cars = res.data || []
    carOptions.value = cars.map((c) => ({
      label: `${c.car_no || c.car_id} — ${c.name || c.device_id || ''}`,
      value: c.car_id,
    }))
  } catch (e) {
    message.error('获取车辆列表失败')
  } finally {
    carsLoading.value = false
  }
}

// getData（CrudTable 格式）
function getData(params) {
  return api.getTrackList({
    ...params,
    account_id: selectedAccount.value || undefined,
  })
}

// 同步数据
async function handleSync() {
  if (!selectedAccount.value) {
    message.warning('请先选择像素账户')
    return
  }
  if (!selectedCar.value) {
    message.warning('请选择车型和车辆')
    return
  }
  if (!dateRange.value || dateRange.value.length !== 2) {
    message.warning('请选择同步时间段')
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
    const res = await api.syncTracks({
      account_id: selectedAccount.value,
      car_id: selectedCar.value,
      start_time: formatDate(new Date(startTime)),
      end_time: formatDate(new Date(endTime)),
    })
    const result = res.data
    message.success(
      `同步完成：新增 ${result.data?.created || 0} 条，更新 ${result.data?.updated || 0} 条，API 共 ${result.data?.total_api || 0} 条`
    )
    $table.value?.handleSearch()
  } catch (e) {
    message.error('同步失败：' + (e.response?.data?.msg || e.message))
  } finally {
    syncing.value = false
  }
}

// 清除数据
async function handleClear() {
  if (!selectedAccount.value) {
    message.warning('请先选择像素账户')
    return
  }
  try {
    const res = await api.clearTracks({
      account_id: selectedAccount.value,
      car_id: selectedCar.value || '',
    })
    message.success(`已清除 ${res.data.data?.deleted || 0} 条数据`)
    $table.value?.handleSearch()
  } catch (e) {
    message.error('清除失败')
  }
}

onMounted(async () => {
  await loadAccounts()
  $table.value?.handleSearch()
})
</script>

<template>
  <CommonPage title="轨迹点数据管理">
    <!-- 操作区：四级联动 -->
    <NSpace align="center" style="margin-bottom: 12px">
      <span style="font-weight: 500">像素账户：</span>
      <NSelect
        v-model:value="selectedAccount"
        :options="accountOptions"
        placeholder="选择像素平台账户"
        clearable
        style="width: 220px"
        @update:value="onAccountChange"
      />
      <span style="font-weight: 500; margin-left: 4px">车型：</span>
      <NSelect
        v-model:value="selectedCarType"
        :options="carTypeOptions"
        :loading="carTypesLoading"
        :disabled="!selectedAccount"
        placeholder="选择车型"
        clearable
        style="width: 180px"
        @update:value="onCarTypeChange"
      />
      <span style="font-weight: 500; margin-left: 4px">车辆：</span>
      <NSelect
        v-model:value="selectedCar"
        :options="carOptions"
        :loading="carsLoading"
        :disabled="!selectedCarType"
        placeholder="选择车辆"
        clearable
        filterable
        style="width: 220px"
      />
      <span style="font-weight: 500; margin-left: 4px">时间段：</span>
      <NDatePicker
        v-model:value="dateRange"
        type="daterange"
        clearable
        style="width: 220px"
        placeholder="选择同步时间段"
      />
      <NButton type="primary" :loading="syncing" :disabled="!selectedCar" @click="handleSync">
        <TheIcon icon="material-symbols:sync" :size="18" class="mr-5" />同步数据
      </NButton>
      <NPopconfirm @positive-click="handleClear">
        <template #trigger>
          <NButton type="error" :disabled="!selectedAccount">
            <TheIcon icon="material-symbols:delete-outline" :size="18" class="mr-5" />清除数据
          </NButton>
        </template>
        确认清除该账户{{ selectedCar ? '该车辆' : '所有' }}的轨迹数据？
      </NPopconfirm>
    </NSpace>

    <!-- 表格 -->
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="getData"
    >
      <template #queryBar>
        <QueryBarItem label="车辆ID" :content="queryItems.car_id">
          <NInput
            v-model:value="queryItems.car_id"
            clearable
            placeholder="请输入车辆ID"
            @keydown.enter="$table.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="道路名称" :content="queryItems.road_name">
          <NInput
            v-model:value="queryItems.road_name"
            clearable
            placeholder="请输入道路名称"
            @keydown.enter="$table.handleSearch()"
          />
        </QueryBarItem>
      </template>
    </CrudTable>
  </CommonPage>
</template>
