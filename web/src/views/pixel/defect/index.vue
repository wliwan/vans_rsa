<script setup>
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
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
import { getToken } from '@/utils'
import { useTaskProgressStore } from '@/store/modules/taskProgress'

const { t } = useI18n()

defineOptions({ name: i18n.global.t('views.pixel.title_cn_32c6db68') })

const message = useMessage()
const $table = ref(null)
const taskStore = useTaskProgressStore()

// 账户列表
const accountOptions = ref([])
const selectedAccount = ref(null)

// 日期范围
const dateRange = ref(null)

// 同步状态（按钮 loading）
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

// ── SSE 流式同步（进度通过全局 TaskProgressPanel 展示） ──

function parseSSELine(line, handlers) {
  if (line.startsWith('event: ')) {
    handlers._currentEvent = line.slice(7).trim()
  } else if (line.startsWith('data: ')) {
    const dataStr = line.slice(6)
    try {
      const data = JSON.parse(dataStr)
      const eventType = handlers._currentEvent || 'message'
      if (handlers[eventType]) {
        handlers[eventType](data)
      }
    } catch (_) {
      // 跳过无法解析的 data 行
    }
  }
}

async function handleSync() {
  if (!selectedAccount.value) {
    message.warning(t('views.pixel.message_cn_9ba8511a'))
    return
  }
  if (!dateRange.value || dateRange.value.length !== 2) {
    message.warning(t('views.pixel.placeholder_cn_0e49c6f7'))
    return
  }

  const [startTime, endTime] = dateRange.value
  const formatDate = (d) => {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  }

  // 启动全局任务进度
  const taskId = taskStore.startTask('同步病害数据')
  let taskRunning = true
  syncing.value = true

  const baseURL = import.meta.env.VITE_BASE_API || ''
  const url = `${baseURL}/defect/sync-stream`
  const token = getToken()

  let reader = null
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        token: token || '',
      },
      body: JSON.stringify({
        account_id: selectedAccount.value,
        start_time: formatDate(new Date(startTime)),
        end_time: formatDate(new Date(endTime)),
      }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`HTTP ${response.status}: ${errorText}`)
    }

    reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    const handlers = { _currentEvent: '' }

    handlers.start = (data) => {
      const totalPages = data.total_pages || 0
      const totalApi = data.total_api || 0
      taskStore.updateProgress(taskId, {
        progress: 0,
        message: `共 ${totalApi.toLocaleString()} 条记录，分 ${totalPages} 页`,
        phase: '连接成功',
      })
    }

    handlers.progress = (data) => {
      const page = data.page || 0
      const totalPages = data.total_pages || 0
      const created = data.created || 0
      const updated = data.updated || 0
      const pct = totalPages > 0 ? Math.round((page / totalPages) * 100) : 0
      taskStore.updateProgress(taskId, {
        progress: pct,
        message: data.message || `第 ${page}/${totalPages} 页`,
        phase: `新增 ${created} / 更新 ${updated}`,
      })
    }

    handlers.done = (data) => {
      taskRunning = false
      taskStore.finishTask(taskId, data.message || '同步完成')
      message.success(data.message || '同步完成')
      $table.value?.handleSearch()
    }

    handlers.error = (data) => {
      taskRunning = false
      taskStore.failTask(taskId, {
        message: data.message || '同步失败',
        detail: data.message || '',
      })
      message.error(t('views.pixel.message_cn_a0f67c55') + (data.message || ''))
    }

    // 读取 SSE 流
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.trim() === '') {
          handlers._currentEvent = ''
        } else {
          parseSSELine(line, handlers)
        }
      }
    }

    // 处理缓冲区剩余内容
    if (buffer.trim()) {
      parseSSELine(buffer, handlers)
    }

    // 流正常结束但未收到 done 事件
    if (taskRunning) {
      taskRunning = false
      taskStore.finishTask(taskId, '同步完成')
      message.success('同步完成')
      $table.value?.handleSearch()
    }
  } catch (e) {
    if (taskRunning) {
      taskRunning = false
      taskStore.failTask(taskId, {
        message: '同步请求失败',
        detail: e.message || '',
      })
    }
    message.error(t('views.pixel.message_cn_a0f67c55') + (e.message || ''))
  } finally {
    syncing.value = false
    if (reader) {
      try { reader.cancel() } catch (_) { /* ignore */ }
    }
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
