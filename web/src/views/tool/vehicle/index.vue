<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import {
  NButton,
  NCard,
  NDatePicker,
  NGi,
  NGrid,
  NSelect,
  NSpin,
  NTag,
  useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

const { t } = useI18n()

defineOptions({ name: i18n.global.t('views.tool.vehicle.title') })
const message = useMessage()

// ── 车辆选择 ──
const accountOptions = ref([])
const selectedAccount = ref(null)
const carTypeOptions = ref([])
const selectedCarType = ref(null)
const carTypesLoading = ref(false)
const carOptions = ref([])
const selectedCar = ref(null)
const carsLoading = ref(false)

// ── 检测状态 ──
const checking = ref(false)
const checkResult = ref(null) // { status, device }

// ── 刷新状态 ──
const refreshing = ref(false)

// ── 流量查询 ──
const flowDate = ref(null)        // timestamp (ms) from NDatePicker
const flowLoading = ref(false)
const flowResult = ref(null)      // { flow, device }

const hasResult = computed(() => !!checkResult.value)

// ── 统计卡片映射 ──
const statCategoryKeys = ['ALG_PIC', 'ALG_RESULT', 'DISTANCE_PIC', 'POSITION_COUNT']
const statI18nMap = {
  ALG_PIC: 'stat_alg_pic',
  ALG_RESULT: 'stat_alg_result',
  DISTANCE_PIC: 'stat_distance_pic',
  POSITION_COUNT: 'stat_position',
}
const statColors = {
  ALG_PIC: '#2080f0',
  ALG_RESULT: '#18a058',
  DISTANCE_PIC: '#f0a020',
  POSITION_COUNT: '#d03050',
}

// ── 账户列表 ──
async function loadAccounts() {
  try {
    const res = await api.getVehicleAccounts()
    const accounts = res.data || []
    accountOptions.value = accounts.map((a) => ({
      label: `${a.username} (${a.tenant_address})`,
      value: a.id,
    }))
  } catch (e) {
    message.error(t('views.errors.text_back_to_home'))
  }
}

// ── 账户切换 → 加载车型 ──
async function onAccountChange(value) {
  selectedCarType.value = null
  selectedCar.value = null
  carOptions.value = []
  carTypeOptions.value = []
  checkResult.value = null

  if (!value) return

  carTypesLoading.value = true
  try {
    const res = await api.getVehicleCarTypes({ account_id: value })
    const types = res.data || []
    carTypeOptions.value = types.map((t) => ({
      label: `${t.name} (type=${t.type})`,
      value: t.type,
    }))
  } catch (e) {
    message.error(t('views.pixel.message_cn_98c45a41'))
  } finally {
    carTypesLoading.value = false
  }
}

// ── 车型切换 → 加载车辆 ──
async function onCarTypeChange(value) {
  selectedCar.value = null
  carOptions.value = []
  checkResult.value = null

  if (!value || !selectedAccount.value) return

  carsLoading.value = true
  try {
    const res = await api.getVehicleCars({
      account_id: selectedAccount.value,
      car_type: value,
    })
    const cars = res.data || []
    carOptions.value = cars.map((c) => ({
      label: `${c.car_no || c.car_id} — ${c.name || c.device_id || ''}`,
      value: c.car_id,
    }))
  } catch (e) {
    message.error(t('views.pixel.message_cn_97e1c686'))
  } finally {
    carsLoading.value = false
  }
}

// ── 一站式检测 ──
async function handleCheck() {
  if (!selectedAccount.value) {
    message.warning(t('views.tool.vehicle.select_account_first'))
    return
  }
  if (!selectedCar.value) {
    message.warning(t('views.tool.vehicle.select_car_first'))
    return
  }

  checking.value = true
  checkResult.value = null
  try {
    const res = await api.getVehicleFullCheck({ car_id: selectedCar.value })
    checkResult.value = res.data
  } catch (e) {
    message.error(t('views.tool.message_cn_a0d51a5f') + (e.response?.data?.msg || e.message))
  } finally {
    checking.value = false
  }
}

// ── 刷新设备状态 ──
async function handleRefresh() {
  if (!selectedCar.value) return

  refreshing.value = true
  try {
    const res = await api.getVehicleFullCheck({ car_id: selectedCar.value })
    checkResult.value = res.data
    message.success(
      checkResult.value.status.online
        ? t('views.tool.vehicle.device_online')
        : t('views.tool.vehicle.device_offline')
    )
  } catch (e) {
    message.error(t('views.tool.message_cn_df570e03') + (e.response?.data?.msg || e.message))
  } finally {
    refreshing.value = false
  }
}

// ── 查询流量 ──
async function handleQueryFlow() {
  if (!selectedCar.value) return
  if (!flowDate.value) {
    message.warning(t('views.tool.vehicle.label_flow_date'))
    return
  }

  const d = new Date(flowDate.value)
  const dateStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

  flowLoading.value = true
  flowResult.value = null
  try {
    const res = await api.getVehicleFlow({
      car_id: selectedCar.value,
      date: dateStr,
    })
    flowResult.value = res.data
    // 流量查询会自动刷新设备信息，同步更新 checkResult
    if (flowResult.value.device) {
      const currentStatus = checkResult.value?.status
      checkResult.value = {
        status: currentStatus,
        device: flowResult.value.device,
      }
    }
    message.success(t('views.tool.vehicle.flow_ok'))
  } catch (e) {
    message.error(t('views.tool.message_cn_d6f56b29') + (e.response?.data?.msg || e.message))
  } finally {
    flowLoading.value = false
  }
}

// ── 格式化设备信息描述项 ──
const deviceInfoItems = computed(() => {
  const data = checkResult.value?.device
  if (!data) return []

  const info = data.info || {}
  const wrapper = data.wrapper || {}

  return [
    { key: 'device_id', value: wrapper.device_id || '-' },
    { key: 'imei', value: wrapper.imei || '-' },
    { key: 'iccid', value: wrapper.iccid || '-' },
    { key: 'software', value: wrapper.software || '-' },
    { key: 'hardware', value: wrapper.hardware || '-' },
    { key: 'protocol', value: wrapper.protocol_version ?? '-' },
    { key: 'ip', value: wrapper.ip_addr || '-' },
    { key: 'city', value: wrapper.city || '-' },
    { key: 'location', value: info.longitude != null && info.latitude != null
      ? `${info.longitude.toFixed(4)}°E, ${info.latitude.toFixed(4)}°N`
      : '-' },
    { key: 'speed', value: info.speed != null ? `${info.speed} km/h` : '-' },
    { key: 'angle', value: info.angle != null ? `${info.angle}°` : '-' },
    { key: 'car_state', value: info.car_state ?? '-' },
    { key: 'last_report', value: info.last_report_time
      ? new Date(info.last_report_time).toLocaleString()
      : '-' },
  ]
})

// ── 获取统计值 ──
function getStatValue(category, metric) {
  return checkResult.value?.device?.statistics?.[category]?.[metric] ?? 0
}

// ── 字节格式化 ──
function formatBytes(bytes) {
  if (bytes == null || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const v = bytes / Math.pow(1024, i)
  return `${v.toFixed(i > 0 ? 2 : 0)} ${units[i]}`
}

// ── 流量汇总 ──
const flowSummary = computed(() => {
  const wrapper = flowResult.value?.flow         // {ok, status_code, date, flow: {...}}
  if (!wrapper) return null
  const flow = wrapper.flow || wrapper           // 内层 FlowData（兼容扁平结构）
  if (!flow) return null
  const detail = flow.detail || []
  return {
    send: flow.send || 0,
    receive: flow.receive || 0,
    total: (flow.send || 0) + (flow.receive || 0),
    detail,
  }
})

onMounted(() => {
  loadAccounts()
})
</script>

<template>
  <CommonPage :title="t('views.tool.vehicle.title')">
    <!-- 选择器栏：响应式换行 -->
    <div class="selector-bar">
      <NSelect
        v-model:value="selectedAccount"
        :options="accountOptions"
        :placeholder="t('views.tool.vehicle.select_account')"
        clearable
        class="selector-item"
        @update:value="onAccountChange"
      />
      <NSelect
        v-model:value="selectedCarType"
        :options="carTypeOptions"
        :loading="carTypesLoading"
        :disabled="!selectedAccount"
        :placeholder="t('views.tool.vehicle.select_car_type')"
        clearable
        class="selector-item"
        @update:value="onCarTypeChange"
      />
      <NSelect
        v-model:value="selectedCar"
        :options="carOptions"
        :loading="carsLoading"
        :disabled="!selectedCarType"
        :placeholder="t('views.tool.vehicle.select_car')"
        clearable
        filterable
        class="selector-item selector-item--wide"
      />
      <NButton
        type="primary"
        :loading="checking"
        :disabled="!selectedCar"
        class="check-btn"
        @click="handleCheck"
      >
        {{ checking ? t('views.tool.vehicle.checking') : t('views.tool.vehicle.btn_check') }}
      </NButton>
      <NButton
        :loading="refreshing"
        :disabled="!selectedCar || !hasResult"
        class="check-btn"
        @click="handleRefresh"
      >
        {{ refreshing ? t('views.tool.vehicle.refreshing') : t('views.tool.vehicle.btn_refresh') }}
      </NButton>
    </div>

    <!-- 流量查询栏 -->
    <div class="flow-bar">
      <NDatePicker
        v-model:value="flowDate"
        type="date"
        clearable
        :placeholder="t('views.tool.vehicle.label_flow_date')"
        class="flow-date"
      />
      <NButton
        type="info"
        :loading="flowLoading"
        :disabled="!selectedCar || !flowDate"
        size="small"
        @click="handleQueryFlow"
      >
        {{ t('views.tool.vehicle.btn_query_flow') }}
      </NButton>
    </div>

    <!-- 结果区域 -->
    <NSpin :show="checking">
      <template v-if="hasResult">
        <!-- 在线状态横幅 -->
        <div class="status-banner" :class="checkResult.status.online ? 'online' : 'offline'">
          <div class="status-dot" />
          <span class="status-text">
            {{ checkResult.status.online ? t('views.tool.vehicle.device_online') : t('views.tool.vehicle.device_offline') }}
          </span>
          <span v-if="!checkResult.status.online && checkResult.status.data" class="status-msg">
            — {{ checkResult.status.data }}
          </span>
        </div>

        <!-- 设备运行统计 -->
        <NCard :title="t('views.tool.vehicle.label_statistics')" size="small" class="section-card">
          <NGrid cols="1 s:2" :x-gap="12" :y-gap="12" responsive="screen">
            <NGi v-for="cat in statCategoryKeys" :key="cat">
              <div class="stat-card" :style="{ borderLeftColor: statColors[cat] }">
                <div class="stat-card-title" :style="{ color: statColors[cat] }">
                  {{ t(`views.tool.vehicle.${statI18nMap[cat]}`) }}
                </div>
                <div class="stat-card-metrics">
                  <div class="stat-metric">
                    <span class="metric-label">{{ t('views.tool.vehicle.metric_processing') }}</span>
                    <span class="metric-value">{{ getStatValue(cat, 'CURRENT_RUN_COUNT').toLocaleString() }}</span>
                  </div>
                  <div class="stat-metric">
                    <span class="metric-label">{{ t('views.tool.vehicle.metric_uploaded') }}</span>
                    <span class="metric-value">{{ getStatValue(cat, 'CURRENT_RUN_UPLOADED_TOTAL').toLocaleString() }}</span>
                  </div>
                  <div class="stat-metric">
                    <span class="metric-label">{{ t('views.tool.vehicle.metric_pending') }}</span>
                    <span class="metric-value metric-value--pending">
                      {{ getStatValue(cat, 'PENDING_UPLOAD_COUNT').toLocaleString() }}
                    </span>
                  </div>
                </div>
              </div>
            </NGi>
          </NGrid>
        </NCard>

        <!-- 设备信息 -->
        <NCard :title="t('views.tool.vehicle.label_device_info')" size="small" class="section-card">
          <NGrid cols="1 s:2 m:3" :x-gap="8" :y-gap="4" responsive="screen">
            <NGi v-for="item in deviceInfoItems" :key="item.key">
              <div class="info-item">
                <span class="info-label">{{ t(`views.tool.vehicle.label_${item.key}`) }}</span>
                <span class="info-value">{{ item.value }}</span>
              </div>
            </NGi>
          </NGrid>
        </NCard>

        <!-- 数据流量 -->
        <NCard v-if="flowResult" :title="t('views.tool.vehicle.label_flow')" size="small" class="section-card">
          <div class="flow-result">
            <NTag :type="flowResult.flow.ok ? 'success' : 'error'" size="medium" round>
              {{ flowResult.flow.ok ? t('views.tool.vehicle.flow_ok') : t('views.tool.vehicle.flow_fail') }}
            </NTag>
            <!-- 流量汇总 -->
            <div v-if="flowSummary" class="flow-summary">
              <NGrid cols="1 s:3" :x-gap="12" :y-gap="8" responsive="screen">
                <NGi>
                  <div class="flow-stat-card upload">
                    <span class="flow-stat-label">{{ t('views.tool.vehicle.label_send') }}</span>
                    <span class="flow-stat-value">{{ formatBytes(flowSummary.send) }}</span>
                  </div>
                </NGi>
                <NGi>
                  <div class="flow-stat-card download">
                    <span class="flow-stat-label">{{ t('views.tool.vehicle.label_receive') }}</span>
                    <span class="flow-stat-value">{{ formatBytes(flowSummary.receive) }}</span>
                  </div>
                </NGi>
                <NGi>
                  <div class="flow-stat-card total">
                    <span class="flow-stat-label">{{ t('views.tool.vehicle.label_total') }}</span>
                    <span class="flow-stat-value">{{ formatBytes(flowSummary.total) }}</span>
                  </div>
                </NGi>
              </NGrid>
            </div>
            <!-- IP 明细 -->
            <div v-if="flowSummary && flowSummary.detail.length" class="flow-detail">
              <div class="flow-detail-title">{{ t('views.tool.vehicle.label_flow_detail') }}</div>
              <div v-for="(item, idx) in flowSummary.detail" :key="idx" class="flow-detail-row">
                <span class="flow-detail-ip">{{ item.ip || '-' }}</span>
                <span class="flow-detail-send">{{ formatBytes(item.send || item.snd || 0) }}</span>
                <span class="flow-detail-rcv">{{ formatBytes(item.rcv || item.receive || 0) }}</span>
              </div>
            </div>
            <div class="flow-meta">
              <span class="flow-meta-item">
                <span class="flow-meta-label">{{ t('views.tool.vehicle.flow_status_code') }}:</span>
                <strong>{{ flowResult.flow.status_code }}</strong>
              </span>
              <span class="flow-meta-item">
                <span class="flow-meta-label">Date:</span>
                <strong>{{ flowResult.flow.date }}</strong>
              </span>
            </div>
          </div>
        </NCard>
      </template>

      <!-- 空状态 -->
      <div v-if="!hasResult && !checking" class="empty-hint">
        {{ t('views.tool.vehicle.select_car_first') }}
      </div>
    </NSpin>
  </CommonPage>
</template>

<style scoped>
/* ── 选择器栏 ── */
.selector-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 16px;
}

.selector-item {
  width: 200px;
  flex-shrink: 0;
}

.selector-item--wide {
  width: 240px;
}

.check-btn {
  flex-shrink: 0;
}

/* ── 流量查询栏 ── */
.flow-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 16px;
}

.flow-date {
  width: 200px;
  flex-shrink: 0;
}

/* ── 流量结果 ── */
.flow-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.flow-summary {
  margin-top: 4px;
}

.flow-stat-card {
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid var(--n-border-color, #e8e8e8);
  background: var(--n-color, #fff);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.flow-stat-card.upload {
  border-left: 4px solid #2080f0;
}

.flow-stat-card.download {
  border-left: 4px solid #18a058;
}

.flow-stat-card.total {
  border-left: 4px solid #f0a020;
}

.flow-stat-label {
  font-size: 12px;
  color: #999;
  text-transform: uppercase;
}

.flow-stat-value {
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--n-text-color, #333);
}

/* ── IP 明细 ── */
.flow-detail {
  background: var(--n-color-embedded, #fafafa);
  border-radius: 8px;
  padding: 10px 14px;
}

.flow-detail-title {
  font-size: 13px;
  font-weight: 600;
  color: #666;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--n-border-color, #e8e8e8);
}

.flow-detail-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
  font-size: 13px;
}

.flow-detail-row + .flow-detail-row {
  border-top: 1px dashed rgba(128, 128, 128, 0.1);
}

.flow-detail-ip {
  font-family: monospace;
  color: var(--n-text-color, #333);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.flow-detail-send {
  color: #2080f0;
  font-weight: 500;
  white-space: nowrap;
}

.flow-detail-rcv {
  color: #18a058;
  font-weight: 500;
  white-space: nowrap;
}

.flow-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 14px;
}

.flow-meta-label {
  color: #999;
  margin-right: 4px;
}

/* ── 在线状态横幅 ── */
.status-banner {
  display: flex;
  align-items: center;
  padding: 14px 20px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 600;
}

.status-banner.online {
  background: #f0f9eb;
  color: #18a058;
  border: 1px solid #b7eb8f;
}

.status-banner.offline {
  background: #fef0f0;
  color: #d03050;
  border: 1px solid #fbc4c4;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 10px;
  flex-shrink: 0;
}

.status-banner.online .status-dot {
  background: #18a058;
  box-shadow: 0 0 6px rgba(24, 160, 88, 0.4);
}

.status-banner.offline .status-dot {
  background: #d03050;
  box-shadow: 0 0 6px rgba(208, 48, 80, 0.4);
}

.status-text {
  white-space: nowrap;
}

.status-msg {
  font-weight: 400;
  font-size: 14px;
  opacity: 0.8;
}

/* ── 区块卡片 ── */
.section-card {
  margin-bottom: 16px;
}

/* ── 统计卡片 ── */
.stat-card {
  padding: 14px 16px;
  border-radius: 8px;
  border: 1px solid var(--n-border-color, #e8e8e8);
  border-left: 4px solid;
  background: var(--n-color, #fff);
  transition: box-shadow 0.2s;
}

.stat-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.stat-card-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 10px;
}

.stat-card-metrics {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-metric {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px dashed rgba(128, 128, 128, 0.15);
}

.stat-metric:last-child {
  border-bottom: none;
}

.metric-label {
  font-size: 13px;
  color: #666;
}

.metric-value {
  font-size: 15px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.metric-value--pending {
  color: #f0a020;
}

/* ── 设备信息项 ── */
.info-item {
  display: flex;
  flex-direction: column;
  padding: 6px 0;
  min-width: 0;
}

.info-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 2px;
}

.info-value {
  font-size: 14px;
  font-weight: 500;
  word-break: break-all;
  color: var(--n-text-color, #333);
}

/* ── 空状态提示 ── */
.empty-hint {
  text-align: center;
  color: #999;
  padding: 60px 0;
  font-size: 15px;
}

/* ── 手机适配 ── */
@media (max-width: 600px) {
  .selector-item,
  .selector-item--wide {
    width: 100%;
  }

  .check-btn {
    width: 100%;
  }

  .flow-date {
    width: 100%;
  }

  .status-banner {
    font-size: 14px;
    padding: 10px 14px;
  }

  .stat-card {
    padding: 10px 12px;
  }
}
</style>
