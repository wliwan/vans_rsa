<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
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
  NModal,
  NCard,
  NSpin,
  NBreadcrumb,
  NBreadcrumbItem,
  useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import { useTaskProgressStore } from '@/store/modules/taskProgress'
import api from '@/api'

defineOptions({ name: '全球国家及行政区管理' })

const { t } = useI18n()

const message = useMessage()
const route = useRoute()

// ── 面包屑级联状态 ──
const breadcrumb = ref([])
const currentList = ref([])
const currentLoading = ref(false)
const currentSearch = ref('')
const detailData = ref(null)
const detailLoading = ref(false)

const selectedNode = computed(() => {
  return breadcrumb.value.length > 0 ? breadcrumb.value[breadcrumb.value.length - 1] : null
})

const currentLevelLabel = computed(() => {
  if (breadcrumb.value.length === 0) return t('views.network.region.levelLabel.country')
  if (breadcrumb.value.length === 1) return t('views.network.region.levelLabel.state')
  return t('views.network.region.levelLabel.city')
})

// ── 表单 ──
const formMode = ref('view')
const formLoading = ref(false)
const formRef = ref(null)
const formData = ref({
  name: '', local_name: '', code: '', iso_alpha2: '', iso_alpha3: '',
  iso_numeric: '', region_type: 'COUNTRY', parent_id: null,
  capital: '', population: null, area: null, latitude: null, longitude: null,
  timezone: '',
})
const formRules = computed(() => ({ name: { required: true, message: t('views.network.region.formRules.nameRequired') } }))
const showCreateModal = ref(false)
const showDetailMobile = ref(false)  // 移动端详情面板展开控制
const importLoading = ref(false)
const geonamesLoading = ref(false)
const proxyUrl = ref('')
const showProxyInput = ref(false)

const typeOptions = computed(() => [
  { label: t('views.network.region.levelLabel.country'), value: 'COUNTRY' },
  { label: t('views.network.region.levelLabel.state'), value: 'STATE' },
  { label: t('views.network.region.levelLabel.city'), value: 'CITY' },
])

const exportLevelOptions = computed(() => [
  { label: t('views.network.region.exportLevelOptions.all'), value: 'ALL' },
  { label: t('views.network.region.exportLevelOptions.stateOnly'), value: 'STATE' },
  { label: t('views.network.region.exportLevelOptions.stateAndCity'), value: 'CITY' },
])

const typeColorMap = { COUNTRY: '#2080f0', STATE: '#18a058', CITY: '#f0a020' }

// ── 初始化 + 路由切换时重置 ──
function resetToRoot() {
  breadcrumb.value = []
  detailData.value = null
  loadCurrentLevel()
}

onMounted(resetToRoot)

// ── 加载当前层级 ──
async function loadCurrentLevel() {
  currentLoading.value = true
  currentSearch.value = ''
  try {
    if (breadcrumb.value.length === 0) {
      const res = await api.getRegionList({ region_type: 'COUNTRY', page_size: 500, is_active: true })
      currentList.value = (res.data || []).map(item => ({
        ...item,
        has_children: true,
      }))
    } else {
      const parentId = breadcrumb.value[breadcrumb.value.length - 1].id
      const res = await api.getRegionChildren(parentId)
      currentList.value = res.data || []
    }
  } catch (e) {
    currentList.value = []
  } finally {
    currentLoading.value = false
  }
}

// ── 过滤 ──
const filteredList = computed(() => {
  if (!currentSearch.value) return currentList.value
  const s = currentSearch.value.toLowerCase()
  return currentList.value.filter(item =>
    (item.name || '').toLowerCase().includes(s) ||
    (item.local_name || '').toLowerCase().includes(s) ||
    (item.code || '').toLowerCase().includes(s)
  )
})

// ── 点击行进入子层级 ──
function onClickRow(row) {
  breadcrumb.value.push({
    id: row.id,
    name: row.name,
    localName: row.local_name || '',
    type: row.region_type || '',
  })
  showDetailMobile.value = true
  loadDetail(row.id)
  loadCurrentLevel()
}

// ── 面包屑回退 ──
function backToLevel(index) {
  breadcrumb.value = breadcrumb.value.slice(0, index)
  if (breadcrumb.value.length > 0) {
    loadDetail(breadcrumb.value[breadcrumb.value.length - 1].id)
  } else {
    detailData.value = null
  }
  loadCurrentLevel()
}

// ── 详情 ──
async function loadDetail(nodeId) {
  detailLoading.value = true
  try {
    const res = await api.getRegionById(nodeId)
    detailData.value = res.data
  } catch (e) {
    detailData.value = null
  } finally {
    detailLoading.value = false
  }
}

// ── CRUD ──
function onAdd() {
  let parentId = null
  let defaultType = 'COUNTRY'
  if (breadcrumb.value.length >= 1) {
    parentId = breadcrumb.value[breadcrumb.value.length - 1].id
    defaultType = breadcrumb.value.length === 1 ? 'STATE' : 'CITY'
  }
  formMode.value = 'create'
  formData.value = {
    name: '', local_name: '', code: '', iso_alpha2: '', iso_alpha3: '',
    iso_numeric: '', region_type: defaultType, parent_id: parentId,
    capital: '', population: null, area: null, latitude: null, longitude: null,
    timezone: '',
  }
  showCreateModal.value = true
}

function onEdit() {
  if (!selectedNode.value) return
  formMode.value = 'edit'
  formData.value = { ...detailData.value }
  showCreateModal.value = true
}

async function onSave() {
  formLoading.value = true
  try {
    if (formMode.value === 'create') {
      await api.createRegion(formData.value)
      message.success(t('views.network.region.messages.createSuccess'))
    } else {
      await api.updateRegion({ id: selectedNode.value.id, ...formData.value })
      message.success(t('views.network.region.messages.updateSuccess'))
    }
    showCreateModal.value = false
    loadCurrentLevel()
    if (breadcrumb.value.length > 0) {
      loadDetail(breadcrumb.value[breadcrumb.value.length - 1].id)
    }
  } catch (e) {
    message.error(t('views.network.region.messages.saveFail'))
  } finally {
    formLoading.value = false
  }
}

async function onDelete() {
  if (!selectedNode.value) return
  try {
    await api.deleteRegion({ region_id: selectedNode.value.id })
    message.success(t('views.network.region.messages.deleteSuccess'))
    breadcrumb.value = breadcrumb.value.slice(0, -1)
    if (breadcrumb.value.length > 0) {
      loadDetail(breadcrumb.value[breadcrumb.value.length - 1].id)
    } else {
      detailData.value = null
    }
    loadCurrentLevel()
  } catch (e) {
    message.error(t('views.network.region.messages.deleteFail'))
  }
}

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
    message.success(t('views.network.region.messages.importSuccess', { detail: parts.join('，') || t('views.network.region.messages.importNoData') }))
    resetToRoot()
  } catch (e) {
    message.error(t('views.network.region.messages.importFail'))
  } finally {
    importLoading.value = false
  }
}

async function onClearAll() {
  try {
    const res = await api.clearRegions()
    message.success(t('views.network.region.messages.clearSuccess', { count: res.data?.deleted || 0 }))
    breadcrumb.value = []
    currentList.value = []
    detailData.value = null
  } catch (e) {
    message.error(t('views.network.region.messages.clearFail'))
  }
}

async function onFillGeonames() {
  const taskProgressStore = useTaskProgressStore()
  const proxy = proxyUrl.value.trim() || null

  geonamesLoading.value = true

  // 先尝试同步请求（有缓存则秒级返回）
  try {
    const res = await api.fillGeonames(false, proxy)
    const d = res.data || {}
    if (d.source === 'cache') {
      message.success(t('views.network.region.messages.geonamesCacheSuccess', { count: d.updated || 0 }))
      geonamesLoading.value = false
      resetToRoot()
      return
    }
    if (d.source === 'empty') {
      message.info(t('views.network.region.messages.geonamesNoData'))
      geonamesLoading.value = false
      return
    }
    if (d.source === 'error') {
      // 首次请求直接返回错误（无缓存 + 下载快速失败）
      message.error(d.error || t('views.network.region.messages.geonamesDownloadFail'))
      geonamesLoading.value = false
      return
    }
  } catch (_) {
    // 请求超时 → 后台可能已在下载，进入轮询模式
  }

  // 启动后台任务（可重试）
  geonamesLoading.value = false
  doStartGeonamesTask(proxy)
}

// 抽取为独立函数，供重试回调使用
function doStartGeonamesTask(proxy) {
  const taskProgressStore = useTaskProgressStore()
  const taskId = taskProgressStore.startTask(t('views.network.region.messages.geonamesTaskName'), () => {
    doStartGeonamesTask(proxy)
  })

  // 触发后台下载（不等待返回）
  api.fillGeonames(true, proxy).catch(() => {})

  let elapsed = 0
  const maxElapsed = 30 * 60 * 1000 // 30 分钟超时
  const timer = setInterval(async () => {
    elapsed += 2000
    try {
      const res = await api.getGeonamesProgress()
      const d = res.data || {}
      taskProgressStore.updateProgress(taskId, {
        progress: d.progress || 0,
        message: d.message || '',
        phase: d.phase || '',
      })
      if (d.status === 'done') {
        clearInterval(timer)
        taskProgressStore.finishTask(taskId, d.message)
        message.success(t('views.network.region.messages.geonamesFillComplete'))
        resetToRoot()
      } else if (d.status === 'error') {
        clearInterval(timer)
        taskProgressStore.failTask(taskId, {
          message: d.message || t('views.network.region.messages.geonamesDownloadFail'),
          detail: d.detail || d.message || '',
        })
        message.error(d.message || t('views.network.region.messages.geonamesRetryHint'))
      } else if (elapsed >= maxElapsed) {
        clearInterval(timer)
        taskProgressStore.failTask(taskId, {
          message: t('views.network.region.messages.geonamesTimeout'),
          detail: t('views.network.region.messages.geonamesTimeoutDetail'),
        })
      }
    } catch (_) {}
  }, 2000)
}

function doExport(level) {
  const countryId = breadcrumb.value[0]?.id
  if (!countryId) return
  api.exportRegions({ country_id: countryId, level }).then((res) => {
    const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${breadcrumb.value[0].name}_${level}.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success(t('views.network.region.messages.exportSuccess'))
  }).catch(() => message.error(t('views.network.region.messages.exportFail')))
}

async function deleteRow(row) {
  try {
    await api.deleteRegion({ region_id: row.id })
    message.success(t('views.network.region.messages.deleteSuccess'))
    loadCurrentLevel()
  } catch (e) { message.error(t('views.network.region.messages.deleteFail')) }
}
</script>

<template>
  <CommonPage :title="t('views.network.region.title')">
    <template #action>
      <NSpace wrap :size="[8, 6]">
        <NButton type="warning" :loading="importLoading" @click="onImport">
          <TheIcon icon="material-symbols:cloud-download" :size="18" class="mr-5" />{{ t('views.network.region.buttons.importIso3166') }}
        </NButton>
        <div style="display: flex; align-items: center; gap: 4px">
          <NButton type="info" :loading="geonamesLoading" @click="onFillGeonames">
            <TheIcon icon="material-symbols:translate" :size="18" class="mr-5" />{{ t('views.network.region.buttons.fillGeonames') }}
          </NButton>
          <NButton size="small" quaternary @click="showProxyInput = !showProxyInput" :type="showProxyInput ? 'primary' : 'default'">
            <TheIcon icon="material-symbols:settings-ethernet" :size="16" />
          </NButton>
        </div>
        <NInput
          v-if="showProxyInput"
          v-model:value="proxyUrl"
          :placeholder="t('views.network.region.proxyPlaceholder')"
          clearable
          size="small"
          style="width: 220px"
        />
      </NSpace>
    </template>

    <!-- 面包屑 -->
    <div class="toolbar-row">
      <NBreadcrumb>
        <NBreadcrumbItem>
          <span class="breadcrumb-link" @click="backToLevel(0)">{{ t('views.network.region.breadcrumb.root') }}</span>
        </NBreadcrumbItem>
        <NBreadcrumbItem v-for="(item, idx) in breadcrumb" :key="item.id">
          <span
            v-if="idx < breadcrumb.length - 1"
            class="breadcrumb-link"
            @click="backToLevel(idx + 1)"
          >{{ item.localName ? item.name + '（' + item.localName + '）' : item.name }}</span>
          <span v-else style="font-weight: 600">{{ item.localName ? item.name + '（' + item.localName + '）' : item.name }}</span>
        </NBreadcrumbItem>
      </NBreadcrumb>

      <NSpace style="margin-left: auto" wrap :size="[6, 4]">
        <NButton v-if="selectedNode" size="small" type="primary" @click="onEdit">{{ t('views.network.region.buttons.edit') }}</NButton>
        <NButton v-if="selectedNode" size="small" type="primary" secondary @click="onAdd()">{{ t('views.network.region.buttons.addChild') }}</NButton>
        <NPopconfirm v-if="selectedNode" @positive-click="onDelete">
          <template #trigger>
            <NButton size="small" type="error" secondary>{{ t('views.network.region.list.delete') }}</NButton>
          </template>
          {{ t('views.network.region.list.confirmDeleteWithChildren', { name: selectedNode.localName ? selectedNode.name + '（' + selectedNode.localName + '）' : selectedNode.name }) }}
        </NPopconfirm>
        <NPopconfirm v-if="breadcrumb.length === 0" @positive-click="onClearAll">
          <template #trigger>
            <NButton size="small" type="error" secondary>
              <TheIcon icon="material-symbols:delete-forever" :size="14" class="mr-4" />{{ t('views.network.region.buttons.clearAll') }}
            </NButton>
          </template>
          {{ t('views.network.region.list.confirmClear') }}
        </NPopconfirm>
      </NSpace>
    </div>

    <div class="main-content">
      <!-- 列表 -->
      <NCard size="small" :bordered="true" class="list-panel" :class="{ 'list-panel--collapsed': selectedNode && showDetailMobile }">
        <template #header>
          <div class="panel-header">
            <span class="panel-title">{{ t('views.network.region.list.currentLevel', { level: currentLevelLabel }) }}</span>
            <span class="panel-count">{{ t('views.network.region.list.count', { count: filteredList.length }) }}</span>
            <NButton
              v-if="selectedNode"
              size="tiny"
              quaternary
              class="detail-toggle-btn"
              @click="showDetailMobile = !showDetailMobile"
            >
              <TheIcon :icon="showDetailMobile ? 'material-symbols:expand-more' : 'material-symbols:info'" :size="16" />
              {{ showDetailMobile ? t('views.network.region.buttons.hideDetail') : t('views.network.region.buttons.showDetail') }}
            </NButton>
          </div>
        </template>

        <NInput
          v-model:value="currentSearch"
            :placeholder="t('views.network.region.searchPlaceholder', { level: currentLevelLabel })"
          clearable
          size="small"
          style="margin-bottom: 8px"
        />

        <NSpin :show="currentLoading" style="flex: 1; min-height: 0">
          <div v-if="filteredList.length" class="region-list">
            <div
              v-for="row in filteredList"
              :key="row.id"
              class="region-row"
              @click="onClickRow(row)"
            >
              <div class="row-main">
                <div class="row-names">
                  <span class="row-name">
                    <span class="row-code">{{ row.code || '-' }}</span>
                    {{ row.name }}
                  </span>
                  <span v-if="row.local_name" class="row-local-name">{{ row.local_name }}</span>
                </div>
              </div>
              <div class="row-meta row-meta--mobile">
                <NTag
                  :style="{ background: typeColorMap[row.region_type] + '20', color: typeColorMap[row.region_type], border: 'none' }"
                  size="small"
                >{{ row.region_type }}</NTag>
                <span v-if="row.has_children" class="row-has-children">{{ t('views.network.region.list.hasChildren') }}</span>
              </div>
              <div class="row-actions row-actions--desktop" @click.stop>
                <NPopconfirm @positive-click="deleteRow(row)">
                  <template #trigger>
                    <NButton size="tiny" type="error" quaternary>{{ t('views.network.region.list.delete') }}</NButton>
                  </template>
                  {{ t('views.network.region.list.confirmDelete', { name: row.local_name ? row.name + '（' + row.local_name + '）' : row.name }) }}
                </NPopconfirm>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            {{ currentLoading ? t('views.network.region.list.loading') : t('views.network.region.list.noData') }}
          </div>
        </NSpin>
      </NCard>

      <!-- 详情 -->
      <NCard size="small" :bordered="true" class="detail-panel" :class="{ 'detail-panel--visible': showDetailMobile }" v-if="selectedNode">
        <template #header>
          <div class="panel-header">
            <span class="panel-title">{{ t('views.network.region.detail.title', { name: selectedNode.localName ? selectedNode.name + '（' + selectedNode.localName + '）' : selectedNode.name }) }}</span>
            <NSelect
              v-if="breadcrumb.length >= 1"
              :options="exportLevelOptions"
              value="STATE"
              size="tiny"
              style="width: 130px"
              @update:value="doExport"
              :placeholder="t('views.network.region.detail.exportPlaceholder')"
            />
          </div>
        </template>

        <NSpin :show="detailLoading">
          <div v-if="detailData" class="detail-grid">
            <div class="detail-item"><label>{{ t('views.network.region.detailLabels.name') }}</label><span>{{ detailData.name }}</span></div>
            <div class="detail-item"><label>{{ t('views.network.region.detailLabels.localName') }}</label><span>{{ detailData.local_name || '-' }}</span></div>
            <div class="detail-item"><label>{{ t('views.network.region.detailLabels.code') }}</label><span>{{ detailData.code || '-' }}</span></div>
            <div class="detail-item"><label>{{ t('views.network.region.detailLabels.isoAlpha2') }}</label><span>{{ detailData.iso_alpha2 || '-' }}</span></div>
            <div class="detail-item"><label>{{ t('views.network.region.detailLabels.isoAlpha3') }}</label><span>{{ detailData.iso_alpha3 || '-' }}</span></div>
            <div class="detail-item"><label>{{ t('views.network.region.detailLabels.isoNumeric') }}</label><span>{{ detailData.iso_numeric || '-' }}</span></div>
            <div class="detail-item"><label>{{ t('views.network.region.detailLabels.type') }}</label><NTag type="info" size="small">{{ detailData.region_type }}</NTag></div>
            <div class="detail-item"><label>{{ t('views.network.region.detailLabels.capital') }}</label><span>{{ detailData.capital || '-' }}</span></div>
            <div class="detail-item"><label>{{ t('views.network.region.detailLabels.population') }}</label><span>{{ detailData.population?.toLocaleString() || '-' }}</span></div>
            <div class="detail-item"><label>{{ t('views.network.region.detailLabels.area') }}</label><span>{{ detailData.area ? detailData.area + ' km²' : '-' }}</span></div>
            <div class="detail-item"><label>{{ t('views.network.region.detailLabels.latitude') }}</label><span>{{ detailData.latitude || '-' }}</span></div>
            <div class="detail-item"><label>{{ t('views.network.region.detailLabels.longitude') }}</label><span>{{ detailData.longitude || '-' }}</span></div>
            <div class="detail-item"><label>{{ t('views.network.region.detailLabels.timezone') }}</label><span>{{ detailData.timezone || '-' }}</span></div>
          </div>
        </NSpin>
      </NCard>
    </div>

    <!-- 弹窗 -->
    <NModal v-model:show="showCreateModal" :title="t('views.network.region.modalTitle')" preset="card" style="width: 600px" :mask-closable="false">
      <NForm ref="formRef" :model="formData" :rules="formRules" label-placement="left" label-width="100">
        <NFormItem :label="t('views.network.region.formLabels.name')" path="name"><NInput v-model:value="formData.name" :placeholder="t('views.network.region.formPlaceholders.name')" /></NFormItem>
        <NFormItem :label="t('views.network.region.formLabels.localName')" path="local_name"><NInput v-model:value="formData.local_name" :placeholder="t('views.network.region.formPlaceholders.localName')" /></NFormItem>
        <NFormItem :label="t('views.network.region.formLabels.code')" path="code"><NInput v-model:value="formData.code" :placeholder="t('views.network.region.formPlaceholders.code')" /></NFormItem>
        <NFormItem :label="t('views.network.region.formLabels.isoAlpha2')"><NInput v-model:value="formData.iso_alpha2" maxlength="2" :placeholder="t('views.network.region.formPlaceholders.isoAlpha2')" /></NFormItem>
        <NFormItem :label="t('views.network.region.formLabels.isoAlpha3')"><NInput v-model:value="formData.iso_alpha3" maxlength="3" :placeholder="t('views.network.region.formPlaceholders.isoAlpha3')" /></NFormItem>
        <NFormItem :label="t('views.network.region.formLabels.isoNumeric')"><NInput v-model:value="formData.iso_numeric" maxlength="3" :placeholder="t('views.network.region.formPlaceholders.isoNumeric')" /></NFormItem>
        <NFormItem :label="t('views.network.region.formLabels.type')" path="region_type"><NSelect v-model:value="formData.region_type" :options="typeOptions" filterable /></NFormItem>
        <NFormItem :label="t('views.network.region.formLabels.parentId')"><NInputNumber v-model:value="formData.parent_id" :disabled="true" style="width: 100%" /></NFormItem>
        <NFormItem :label="t('views.network.region.formLabels.capital')"><NInput v-model:value="formData.capital" :placeholder="t('views.network.region.formPlaceholders.capital')" /></NFormItem>
        <NFormItem :label="t('views.network.region.formLabels.population')"><NInputNumber v-model:value="formData.population" :min="0" style="width: 100%" /></NFormItem>
        <NFormItem :label="t('views.network.region.formLabels.area')"><NInputNumber v-model:value="formData.area" :min="0" style="width: 100%" /></NFormItem>
        <NFormItem :label="t('views.network.region.formLabels.latitude')"><NInputNumber v-model:value="formData.latitude" style="width: 100%" /></NFormItem>
        <NFormItem :label="t('views.network.region.formLabels.longitude')"><NInputNumber v-model:value="formData.longitude" style="width: 100%" /></NFormItem>
        <NFormItem :label="t('views.network.region.formLabels.timezone')"><NInput v-model:value="formData.timezone" placeholder="Asia/Shanghai" /></NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showCreateModal = false">{{ t('views.network.region.buttons.cancel') }}</NButton>
          <NButton type="primary" :loading="formLoading" @click="onSave">{{ t('views.network.region.buttons.save') }}</NButton>
        </NSpace>
      </template>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.toolbar-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  gap: 8px;
  flex-wrap: wrap;
}

.breadcrumb-link {
  cursor: pointer;
  color: #2080f0;
}
.breadcrumb-link:hover {
  text-decoration: underline;
}

.main-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: calc(100vh - 200px);
  height: calc(100dvh - 200px);
  overflow: hidden;
}

.list-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.list-panel :deep(.n-card__content) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.detail-panel {
  flex-shrink: 0;
  max-height: 45%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.detail-panel :deep(.n-card__content) {
  overflow: auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-title { font-weight: 600; }
.panel-count { font-size: 12px; color: #999; }
.detail-toggle-btn { display: none; margin-left: auto; }

/* 列表行 */
.region-list { flex: 1; min-height: 0; }
.region-row {
  display: flex;
  align-items: center;
  padding: 6px 10px;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.15s;
  gap: 8px;
}
.region-row:hover { background: #f5f7fa; }

.row-main { flex: 1; min-width: 0; display: flex; align-items: center; gap: 6px; }
.row-code { font-size: 12px; color: #999; flex-shrink: 0; font-family: monospace; }
.row-names { display: flex; flex-direction: column; min-width: 0; }
.row-name { font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-local-name { font-size: 12px; color: #999; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-meta { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.row-has-children { font-size: 11px; color: #18a058; }
.row-actions { flex-shrink: 0; }

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 2px 16px;
}
.detail-item { display: flex; gap: 4px; font-size: 13px; line-height: 2; }
.detail-item label { color: #999; min-width: 72px; flex-shrink: 0; }

.empty-state { text-align: center; color: #999; padding: 40px 0; font-size: 14px; }

.list-panel :deep(.n-card__content)::-webkit-scrollbar,
.detail-panel :deep(.n-card__content)::-webkit-scrollbar { width: 5px; }
.list-panel :deep(.n-card__content)::-webkit-scrollbar-thumb,
.detail-panel :deep(.n-card__content)::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }

/* ── 移动端适配（≤767px）── */
@media (max-width: 767px) {
  /* 主内容区高度调整 */
  .main-content {
    height: calc(100dvh - 160px);
  }

  /* 默认隐藏详情面板，通过按钮切换 */
  .detail-panel {
    display: none;
    max-height: 50vh;
  }
  .detail-panel--visible {
    display: flex;
  }
  /* 展开详情时缩小列表 */
  .list-panel--collapsed {
    flex: 0 0 auto;
    max-height: calc(50dvh - 56px);
  }

  /* 详情切换按钮：移动端显示 */
  .detail-toggle-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }

  /* 面包屑行：换行 */
  .toolbar-row {
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
    flex-wrap: wrap;
  }
  .toolbar-row > :deep(.n-space) {
    justify-content: flex-start;
    flex-wrap: wrap;
    margin-left: 0 !important;
  }

  /* 列表行：精简 */
  .region-row {
    padding: 8px 12px;
  }
  .row-code {
    font-size: 11px;
    display: inline;
    margin-right: 4px;
  }
  .row-name {
    font-size: 14px;
    display: inline;
  }

  /* 桌面端操作列：移动端隐藏 */
  .row-actions--desktop {
    display: none;
  }

  /* 详情网格：单列 */
  .detail-grid {
    grid-template-columns: 1fr;
    gap: 0 16px;
  }
  .detail-item {
    font-size: 13px;
    line-height: 2.2;
  }
}
</style>
