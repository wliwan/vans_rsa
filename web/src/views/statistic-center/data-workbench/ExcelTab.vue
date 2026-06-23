<script setup>
import { ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NButton, NModal, NSpace, NSelect, NPopconfirm,
  NForm, NFormItem, NTag, NUpload, NUploadDragger, NText,
  NCheckbox, NSpin, NInput, useMessage,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { useDataWorkbench } from '@/composables/useDataWorkbench'

const { t } = useI18n()
const message = useMessage()
const {
  selectedWs, loading, isMobileCollapsed,
  proxyOptions, skillOptions,
  formatFileSize, downloadBlob, runWithProgress,
  loadProxyOptions, loadSkillOptions,
} = useDataWorkbench()

// ── Excel 数据源状态 ──
const sheets = ref([])
const analyses = ref([])
const selectedAnalysisIds = ref([])
const selectedSheetIds = ref([])
const uploading = ref(false)
let uploadDebounceTimer = null

// CSV 文本导入弹窗
const showCsvImportModal = ref(false)
const csvImportForm = ref({ name: '', csv_text: '' })

// 原始表格复制到弹窗
const showSheetCopyToModal = ref(false)
const sheetCopyToWorkspaces = ref([])
const sheetCopyToForm = ref({ target_workspace_id: null })

// 分析表格复制到弹窗
const showAnalysisCopyToModal = ref(false)
const analysisCopyToWorkspaces = ref([])
const analysisCopyToForm = ref({ target_workspace_id: null })

// AI 分析弹窗
const showAnalyzeModal = ref(false)
const analyzeForm = ref({
  workspace_id: 0, sheet_id: null, name: '',
  ai_proxy_id: null, skill_id: null, prompt: '',
})

// 关联分析弹窗
const showCorrelateModal = ref(false)
const correlateForm = ref({
  workspace_id: 0, sheet_a_id: null, sheet_b_id: null, name: '',
  ai_proxy_id: null, skill_id: null, prompt: '',
})

// ── 分析-分析关联 ──
const showCorrelateAnalysisModal = ref(false)
const correlateAnalysisForm = ref({
  workspace_id: 0, analysis_a_id: null, analysis_b_id: null, name: '',
  ai_proxy_id: null, skill_id: null, prompt: '',
})

const batchSheetUploadRef = ref(null)

async function loadSheets() {
  if (!selectedWs.value) return
  try {
    const res = await api.getSheetList({ workspace_id: selectedWs.value.id })
    sheets.value = res.data || []
  } catch (e) { message.error(t('views.statistic-center.message_cn_51117ae0')) }
}

async function loadAnalyses() {
  if (!selectedWs.value) return
  try {
    const res = await api.getAnalysisList({ workspace_id: selectedWs.value.id })
    analyses.value = res.data || []
  } catch (e) { message.error(t('views.statistic-center.message_cn_67dc5b1a')) }
}

// ── 文件上传 ──
async function handleUpload({ file }) {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_cb53b40f')); return }
  uploading.value = true
  try {
    await api.uploadSheet(selectedWs.value.id, file.file)
    message.success(t('views.network.roadNetwork.messages.uploadSuccess'))
    await loadSheets()
  } catch (e) { message.error(t('views.statistic-center.message_cn_54e5de42')) }
  uploading.value = false
}

// ── 导出 ──
async function exportSheet(sheet) {
  try {
    const res = await api.exportSheet({ sheet_id: sheet.id })
    downloadBlob(res.data, sheet.name)
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.exportFail')) }
}

async function exportAnalysis(a) {
  try {
    const res = await api.exportAnalysis({ analysis_id: a.id })
    downloadBlob(res.data, a.name + '.xlsx')
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.exportFail')) }
}

// ── AI 分析 ──
async function openAnalyze(sheet) {
  analyzeForm.value = {
    workspace_id: selectedWs.value.id, sheet_id: sheet.id,
    name: sheet.name.replace(/\.[^.]+$/, '') + t('views.statistic-center.label_cn_d93cc1b1'),
    ai_proxy_id: null, skill_id: null, prompt: '',
  }
  try {
    const [pr, sl] = await Promise.all([
      api.getAIProxyList({ page: 1, page_size: 500 }),
      api.getSkillList({ page: 1, page_size: 500 }),
    ])
    proxyOptions.value = (pr.data || []).map((p) => ({ label: p.name, value: p.id }))
    skillOptions.value = (sl.data || []).map((s) => ({ label: s.title, value: s.id }))
  } catch (e) { /* ignore */ }
  showAnalyzeModal.value = true
}

async function handleAnalyzeSubmit() {
  if (!analyzeForm.value.ai_proxy_id) { message.warning(t('views.skill.placeholder_cn_ee488ec6')); return }
  loading.value = true
  showAnalyzeModal.value = false
  try {
    await runWithProgress(
      `${t('views.statistic-center.label_cn_af9f3bf6')} ${analyzeForm.value.name}`,
      () => api.analyzeSheet(analyzeForm.value),
      t('views.statistic-center.label_cn_0b5bf802'),
    )
    message.success(t('views.statistic-center.message_cn_a1220190'))
    await loadAnalyses()
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.analyzeFail')) }
  loading.value = false
}

// ── 关联分析 ──
function openCorrelate() {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_cb53b40f')); return }
  correlateForm.value = {
    workspace_id: selectedWs.value.id, sheet_a_id: null, sheet_b_id: null,
    name: t('views.statistic-center.label_cn_5d47dd27'), ai_proxy_id: null, skill_id: null, prompt: '',
  }
  showCorrelateModal.value = true
  if (!proxyOptions.value.length) {
    api.getAIProxyList({ page: 1, page_size: 500 }).then((res) => {
      proxyOptions.value = (res.data || []).map((p) => ({ label: p.name, value: p.id }))
    })
  }
  if (!skillOptions.value.length) {
    api.getSkillList({ page: 1, page_size: 500 }).then((res) => {
      skillOptions.value = (res.data || []).map((s) => ({ label: s.title, value: s.id }))
    })
  }
}

async function handleCorrelateSubmit() {
  if (!correlateForm.value.ai_proxy_id) { message.warning(t('views.skill.placeholder_cn_ee488ec6')); return }
  if (!correlateForm.value.sheet_a_id || !correlateForm.value.sheet_b_id) { message.warning(t('views.statistic-center.placeholder_cn_0b253166')); return }
  loading.value = true
  showCorrelateModal.value = false
  try {
    await runWithProgress(
      `${t('views.statistic-center.label_cn_55604525')} ${correlateForm.value.name}`,
      () => api.correlateSheets(correlateForm.value),
      t('views.statistic-center.message_cn_aa8f059c'),
    )
    message.success(t('views.statistic-center.message_cn_aa8f059c'))
    await loadAnalyses()
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.analyzeFail')) }
  loading.value = false
}

// ── 分析-分析关联 ──
function openCorrelateAnalyses() {
  if (!selectedWs.value) { message.warning('请先选择工作区'); return }
  correlateAnalysisForm.value = {
    workspace_id: selectedWs.value.id, analysis_a_id: null, analysis_b_id: null,
    name: '分析关联', ai_proxy_id: null, skill_id: null, prompt: '',
  }
  showCorrelateAnalysisModal.value = true
  if (!proxyOptions.value.length) {
    api.getAIProxyList({ page: 1, page_size: 500 }).then((res) => {
      proxyOptions.value = (res.data || []).map((p) => ({ label: p.name, value: p.id }))
    })
  }
  if (!skillOptions.value.length) {
    api.getSkillList({ page: 1, page_size: 500 }).then((res) => {
      skillOptions.value = (res.data || []).map((s) => ({ label: s.title, value: s.id }))
    })
  }
}

async function handleCorrelateAnalysesSubmit() {
  if (!correlateAnalysisForm.value.ai_proxy_id) { message.warning('请选择AI代理'); return }
  if (!correlateAnalysisForm.value.analysis_a_id || !correlateAnalysisForm.value.analysis_b_id) { message.warning('请选择两个分析表格'); return }
  loading.value = true
  showCorrelateAnalysisModal.value = false
  try {
    await runWithProgress(
      `分析关联 ${correlateAnalysisForm.value.name}`,
      () => api.correlateAnalyses(correlateAnalysisForm.value),
      '分析关联完成',
    )
    message.success('分析关联完成')
    await loadAnalyses()
  } catch (e) { message.error('分析关联失败') }
  loading.value = false
}

// ── 删除 ──
async function deleteSheet(sheet) {
  try {
    await api.deleteSheet({ sheet_id: sheet.id })
    await loadSheets()
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.deleteFail')) }
}

async function deleteAnalysisItem(a) {
  try {
    await api.deleteAnalysis({ analysis_id: a.id })
    await loadAnalyses()
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.deleteFail')) }
}

function toggleAnalysisSelect(id) {
  const idx = selectedAnalysisIds.value.indexOf(id)
  if (idx >= 0) selectedAnalysisIds.value.splice(idx, 1)
  else selectedAnalysisIds.value.push(id)
}

function toggleAllAnalyses() {
  if (selectedAnalysisIds.value.length === analyses.value.length) {
    selectedAnalysisIds.value = []
  } else {
    selectedAnalysisIds.value = analyses.value.map((a) => a.id)
  }
}

async function batchDeleteAnalyses() {
  if (!selectedAnalysisIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_5ec88707')); return }
  try {
    loading.value = true
    await api.batchDeleteAnalyses({ analysis_ids: [...selectedAnalysisIds.value] })
    selectedAnalysisIds.value = []
    message.success(t('views.statistic-center.message_cn_eedd70c6'))
    await loadAnalyses()
  } catch (e) { message.error(t('views.statistic-center.message_cn_1bac376d')) }
  loading.value = false
}

async function clearAllAnalyses() {
  if (!selectedWs.value) return
  try {
    loading.value = true
    await api.clearAnalyses({ workspace_id: selectedWs.value.id })
    selectedAnalysisIds.value = []
    message.success(t('views.statistic-center.message_cn_e1424291'))
    await loadAnalyses()
  } catch (e) { message.error(t('views.network.region.messages.clearFail')) }
  loading.value = false
}

async function batchExportAnalyses() {
  if (!selectedAnalysisIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_95a97ff9')); return }
  try {
    loading.value = true
    const res = await api.batchExportAnalyses({ analysis_ids: [...selectedAnalysisIds.value] })
    downloadBlob(res.data, t('views.statistic-center.label_cn_fd0d0f30'))
    message.success(t('views.statistic-center.message_cn_382c07d0'))
  } catch (e) { message.error(t('views.statistic-center.message_cn_08d6cb0e')) }
  loading.value = false
}

// ── 原始表格多选 ──
function toggleSheetSelect(id) {
  const idx = selectedSheetIds.value.indexOf(id)
  if (idx >= 0) selectedSheetIds.value.splice(idx, 1)
  else selectedSheetIds.value.push(id)
}

function toggleAllSheets() {
  if (selectedSheetIds.value.length === sheets.value.length && sheets.value.length > 0) {
    selectedSheetIds.value = []
  } else {
    selectedSheetIds.value = sheets.value.map((s) => s.id)
  }
}

// ── 原始表格批量操作 ──
async function batchExportSheets() {
  if (!selectedSheetIds.value.length) { message.warning('请先选择要导出的表格'); return }
  try {
    loading.value = true
    const res = await api.batchExportSheets({ sheet_ids: [...selectedSheetIds.value] })
    downloadBlob(res.data, '原始表格批量导出.zip')
    message.success(`已导出 ${selectedSheetIds.value.length} 个表格`)
  } catch (e) { message.error(e?.response?.data?.msg || '导出失败') }
  loading.value = false
}

async function batchDeleteSheets() {
  if (!selectedSheetIds.value.length) { message.warning('请先选择要删除的表格'); return }
  try {
    loading.value = true
    await api.batchDeleteSheets({ sheet_ids: [...selectedSheetIds.value] })
    selectedSheetIds.value = []
    message.success('批量删除成功')
    await loadSheets()
  } catch (e) { message.error(e?.response?.data?.msg || '删除失败') }
  loading.value = false
}

// ── 原始表格复制到 ──
async function openSheetCopyToModal() {
  if (!selectedSheetIds.value.length) { message.warning('请先选择要复制的表格'); return }
  sheetCopyToForm.value = { target_workspace_id: null }; showSheetCopyToModal.value = true
  try {
    const res = await api.getWorkspaceList({ page: 1, page_size: 500 })
    sheetCopyToWorkspaces.value = (res.data || []).filter(w => w.id !== selectedWs.value.id).map(w => ({ label: w.name, value: w.id }))
  } catch (e) {}
}

async function handleSheetCopyToWorkspace() {
  if (!sheetCopyToForm.value.target_workspace_id) { message.warning('请选择目标工作区'); return }
  loading.value = true; showSheetCopyToModal.value = false
  try {
    const res = await api.copyToWorkspace({ target_workspace_id: sheetCopyToForm.value.target_workspace_id, sheet_ids: [...selectedSheetIds.value] })
    message.success(res.msg || `成功复制 ${res.data?.sheets || 0} 个表格`)
    selectedSheetIds.value = []
  } catch (e) { message.error(e?.response?.data?.msg || '复制失败') }
  loading.value = false
}

// ── 分析表格复制到 ──
async function openAnalysisCopyToModal() {
  if (!selectedAnalysisIds.value.length) { message.warning('请先选择要复制的分析表格'); return }
  analysisCopyToForm.value = { target_workspace_id: null }; showAnalysisCopyToModal.value = true
  try {
    const res = await api.getWorkspaceList({ page: 1, page_size: 500 })
    analysisCopyToWorkspaces.value = (res.data || []).filter(w => w.id !== selectedWs.value.id).map(w => ({ label: w.name, value: w.id }))
  } catch (e) {}
}

async function handleAnalysisCopyToWorkspace() {
  if (!analysisCopyToForm.value.target_workspace_id) { message.warning('请选择目标工作区'); return }
  loading.value = true; showAnalysisCopyToModal.value = false
  try {
    const res = await api.copyToWorkspace({ target_workspace_id: analysisCopyToForm.value.target_workspace_id, analysis_ids: [...selectedAnalysisIds.value] })
    message.success(res.msg || `成功复制 ${res.data?.analyses || 0} 个分析表格`)
    selectedAnalysisIds.value = []
  } catch (e) { message.error(e?.response?.data?.msg || '复制失败') }
  loading.value = false
}

// ── CSV 文本导入 ──
function openCsvImport() {
  if (!selectedWs.value) { message.warning('请先选择工作区'); return }
  csvImportForm.value = { name: '', csv_text: '' }
  showCsvImportModal.value = true
}

async function handleCsvImportSubmit() {
  if (!csvImportForm.value.name) { message.warning('请输入表格名称'); return }
  if (!csvImportForm.value.csv_text.trim()) { message.warning('请输入CSV文本内容'); return }
  loading.value = true; showCsvImportModal.value = false
  try {
    await api.csvImportSheet({ workspace_id: selectedWs.value.id, name: csvImportForm.value.name, csv_text: csvImportForm.value.csv_text })
    message.success('CSV导入成功')
    await loadSheets()
  } catch (e) { message.error(e?.response?.data?.msg || 'CSV导入失败') }
  loading.value = false
}

// ── 批量上传 ──
async function handleBatchUpload({ file, fileList }) {
  if (!selectedWs.value) { message.warning('请先选择工作区'); return }
  clearTimeout(uploadDebounceTimer)
  uploadDebounceTimer = setTimeout(async () => {
    const validFiles = fileList.filter(f => {
      const name = (f.file?.name || f.name || '').toLowerCase()
      return name.endsWith('.xlsx') || name.endsWith('.xls') || name.endsWith('.csv')
    })
    if (!validFiles.length) return
    uploading.value = true
    try {
      const files = validFiles.map(f => f.file)
      await api.batchUploadSheets(selectedWs.value.id, files)
      message.success(`成功上传 ${validFiles.length} 个文件`)
      await loadSheets()
    } catch (e) { message.error(e?.response?.data?.msg || '批量上传失败') }
    uploading.value = false
    // 清空 NUpload 内部文件列表，避免下次上传时重复上传旧文件
    batchSheetUploadRef.value?.clear()
  }, 150)
}

// watch selectedWs 自动加载数据
watch(() => selectedWs.value, (ws) => {
  if (ws) {
    loadSheets()
    loadAnalyses()
  } else {
    sheets.value = []
    analyses.value = []
    selectedSheetIds.value = []
    selectedAnalysisIds.value = []
  }
}, { immediate: true })

defineExpose({ loadSheets, loadAnalyses })
</script>

<template>
  <div class="flex-1 flex flex-col" style="min-height: 0">
    <!-- 上传区 -->
    <div class="mb-5" :class="{ 'upload-dragger-mobile': isMobileCollapsed }">
      <div class="flex items-center gap-2 mb-2">
        <NButton size="small" @click="openCsvImport">
          <TheIcon icon="material-symbols:edit-note" :size="16" class="mr-1" />CSV文本导入
        </NButton>
      </div>
      <NUpload ref="batchSheetUploadRef" :show-file-list="false" :default-upload="false" accept=".xlsx,.xls,.csv" multiple @change="handleBatchUpload">
        <NUploadDragger
          class="w-full"
          style="border-radius: 12px; --n-border-hover: 2px dashed #3b82f6"
        >
          <div v-if="!uploading" class="flex flex-col items-center py-8 px-4">
            <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 flex items-center justify-center mb-4">
              <TheIcon icon="material-symbols:upload-file" :size="36" class="text-blue-500" />
            </div>
            <div class="text-base font-semibold text-gray-700 dark:text-gray-300 mb-1">{{ t('views.statistic-center.label_cn_b26de1f0') }}</div>
            <div class="text-sm text-gray-400 mb-3">支持批量上传，点击或拖拽多个文件</div>
            <div class="flex items-center gap-2 text-xs text-gray-400 bg-gray-100 dark:bg-gray-800 rounded-full px-3 py-1">
              <TheIcon icon="material-symbols:description" :size="14" />
              <span>.xlsx</span>
              <span>.xls</span>
              <span>.csv</span>
            </div>
          </div>
          <div v-else class="flex flex-col items-center py-8 px-4">
            <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 flex items-center justify-center mb-4">
              <TheIcon icon="material-symbols:cloud-upload" :size="36" class="text-blue-500 animate-pulse" />
            </div>
            <div class="text-base font-semibold text-blue-600 dark:text-blue-400 mb-3">{{ t('views.statistic-center.label_cn_d790356c') }}</div>
            <div class="w-48 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div class="h-full bg-blue-500 rounded-full animate-pulse" style="width: 60%" />
            </div>
          </div>
        </NUploadDragger>
      </NUpload>
    </div>

    <!-- 左右双栏布局（移动端堆叠） -->
    <div class="flex gap-3 flex-1" :class="{ 'mobile-stack': isMobileCollapsed }" style="min-height: 0">
      <!-- ── 左栏：原始表格 ── -->
      <div class="flex-1 flex flex-col" style="min-width: 0">
        <div class="flex items-center justify-between mb-2 px-1">
          <div class="flex items-center gap-2">
            <NCheckbox
              size="small"
              :checked="selectedSheetIds.length === sheets.length && sheets.length > 0"
              :indeterminate="selectedSheetIds.length > 0 && selectedSheetIds.length < sheets.length"
              @update:checked="toggleAllSheets"
            />
            <TheIcon icon="material-symbols:description" :size="20" class="text-blue-500" />
            <span class="font-semibold text-base">{{ t('views.statistic-center.label_07c80637') }}</span>
            <NTag size="small" :bordered="false" type="info">{{ sheets.length }}</NTag>
          </div>
          <NSpace v-if="sheets.length" size="small">
            <NButton size="small" type="primary" :disabled="!selectedSheetIds.length" @click="batchExportSheets">
              <TheIcon icon="material-symbols:download" :size="16" class="mr-1" />导出({{ selectedSheetIds.length }})
            </NButton>
            <NPopconfirm @positive-click="batchDeleteSheets" :disabled="!selectedSheetIds.length">
              <template #trigger>
                <NButton size="small" type="warning" :disabled="!selectedSheetIds.length">
                  <TheIcon icon="material-symbols:delete-outline" :size="16" />删除({{ selectedSheetIds.length }})
                </NButton>
              </template>
              确认删除已选中的 {{ selectedSheetIds.length }} 个表格？
            </NPopconfirm>
            <NButton size="small" :disabled="!selectedSheetIds.length" @click="openSheetCopyToModal">
              <TheIcon icon="material-symbols:content-copy" :size="16" class="mr-1" />复制到
            </NButton>
          </NSpace>
        </div>
        <div class="flex-1 overflow-auto rounded-lg border border-gray-100 bg-gray-50/50 dark:bg-gray-800/30" style="min-height: 0">
          <div v-if="sheets.length" class="p-3 grid gap-3">
            <div
              v-for="s in sheets" :key="s.id"
              class="bg-white dark:bg-gray-800 rounded-lg border border-gray-100 p-4 hover:shadow-sm transition-shadow"
            >
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3 min-w-0 flex-1">
                  <NCheckbox
                    size="small"
                    :checked="selectedSheetIds.includes(s.id)"
                    @update:checked="() => toggleSheetSelect(s.id)"
                    class="flex-shrink-0"
                  />
                  <TheIcon icon="material-symbols:table" :size="22" class="text-blue-500 flex-shrink-0" />
                  <div class="min-w-0">
                    <div class="font-medium text-base truncate">{{ s.name }}</div>
                    <div class="flex items-center gap-2 text-sm text-gray-400 mt-0.5">
                      <span v-if="s.file_size">{{ formatFileSize(s.file_size) }}</span>
                      <span>{{ s.created_at?.slice(0, 10) }}</span>
                    </div>
                  </div>
                </div>
                <NSpace size="small" class="flex-shrink-0 ml-3">
                  <NButton size="small" quaternary @click="exportSheet(s)" :title="t('views.tool.vehicle.label_receive')">
                    <TheIcon icon="material-symbols:download" :size="18" />
                  </NButton>
                  <NButton size="small" type="primary" @click="openAnalyze(s)">
                    <TheIcon icon="material-symbols:psychology" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_fcc18e0f') }}
                  </NButton>
                  <NPopconfirm @positive-click="deleteSheet(s)">
                    <template #trigger>
                      <NButton size="small" type="error" quaternary>
                        <TheIcon icon="material-symbols:delete-outline" :size="18" />
                      </NButton>
                    </template>
                  </NPopconfirm>
                </NSpace>
              </div>
            </div>
          </div>
          <div v-else class="flex items-center justify-center h-full text-gray-400 py-12">
            <div class="text-center">
              <TheIcon icon="material-symbols:cloud-upload" :size="48" class="mb-2 opacity-30" />
              <div class="text-base">{{ t('views.statistic-center.label_cn_1c64ab34') }}</div>
              <div class="text-sm mt-1">{{ t('views.statistic-center.label_cn_3359cfdd') }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── 右栏：拆解分析表格 ── -->
      <div class="flex-1 flex flex-col" style="min-width: 0">
        <div class="flex items-center justify-between mb-2 px-1">
          <div class="flex items-center gap-2">
            <NCheckbox
              size="small"
              :checked="selectedAnalysisIds.length === analyses.length && analyses.length > 0"
              :indeterminate="selectedAnalysisIds.length > 0 && selectedAnalysisIds.length < analyses.length"
              @update:checked="toggleAllAnalyses"
            />
            <TheIcon icon="material-symbols:analytics" :size="20" class="text-green-500" />
            <span class="font-semibold text-base">{{ t('views.statistic-center.label_cn_2a1e0410') }}</span>
            <NTag size="small" :bordered="false" type="success">{{ analyses.length }}</NTag>
          </div>
          <NSpace v-if="analyses.length" size="small">
            <NButton size="small" @click="openCorrelate" :disabled="sheets.length < 2">
              <TheIcon icon="material-symbols:compare-arrows" :size="16" class="mr-1" />原始关联
            </NButton>
            <NButton size="small" @click="openCorrelateAnalyses" :disabled="analyses.length < 2">
              <TheIcon icon="material-symbols:compare-arrows" :size="16" class="mr-1" />分析关联
            </NButton>
            <NButton size="small" type="primary" :disabled="!selectedAnalysisIds.length" @click="batchExportAnalyses">
              <TheIcon icon="material-symbols:download" :size="16" class="mr-1" />导出({{ selectedAnalysisIds.length }})
            </NButton>
            <NButton size="small" :disabled="!selectedAnalysisIds.length" @click="openAnalysisCopyToModal">
              <TheIcon icon="material-symbols:content-copy" :size="16" class="mr-1" />复制到
            </NButton>
            <NPopconfirm @positive-click="batchDeleteAnalyses" :disabled="!selectedAnalysisIds.length">
              <template #trigger>
                <NButton size="small" type="warning" :disabled="!selectedAnalysisIds.length">
                  <TheIcon icon="material-symbols:delete-outline" :size="16" />{{ t('views.statistic-center.label_cn_2f4aaddd') }}
                </NButton>
              </template>
              确认删除已选中的 {{ selectedAnalysisIds.length }} 个分析表格？
            </NPopconfirm>
            <NPopconfirm @positive-click="clearAllAnalyses">
              <template #trigger>
                <NButton size="small" type="error">
                  <TheIcon icon="material-symbols:delete-sweep" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_288f0c40') }}
                </NButton>
              </template>
              {{ t('views.statistic-center.label_cn_329a20fa') }}
            </NPopconfirm>
          </NSpace>
        </div>
        <div class="flex-1 overflow-auto rounded-lg border border-gray-100 bg-gray-50/50 dark:bg-gray-800/30" style="min-height: 0">
          <div v-if="analyses.length" class="p-3 grid gap-3">
            <div
              v-for="a in analyses" :key="a.id"
              class="bg-white dark:bg-gray-800 rounded-lg border border-gray-100 p-4 hover:shadow-sm transition-shadow"
            >
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3 min-w-0 flex-1">
                  <NCheckbox
                    size="small"
                    :checked="selectedAnalysisIds.includes(a.id)"
                    @update:checked="() => toggleAnalysisSelect(a.id)"
                    class="flex-shrink-0"
                  />
                  <TheIcon icon="material-symbols:analytics" :size="22" class="text-green-500 flex-shrink-0" />
                  <div class="min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="font-medium text-base truncate">{{ a.name }}</span>
                      <NTag size="small" :type="a.source_type === 'correlation' ? 'warning' : 'info'" :bordered="false">
                        {{ a.source_type === 'correlation' ? '关联' : t('views.statistic-center.label_cn_72fa7c88') }}
                      </NTag>
                    </div>
                    <div class="flex items-center gap-2 text-sm text-gray-400 mt-0.5">
                      <span v-if="a.file_size">{{ formatFileSize(a.file_size) }}</span>
                      <span>{{ a.created_at?.slice(0, 10) }}</span>
                    </div>
                  </div>
                </div>
                <NSpace size="small" class="flex-shrink-0 ml-3">
                  <NButton size="small" quaternary @click="exportAnalysis(a)" :title="t('views.tool.vehicle.label_receive')">
                    <TheIcon icon="material-symbols:download" :size="18" />
                  </NButton>
                  <NPopconfirm @positive-click="deleteAnalysisItem(a)">
                    <template #trigger>
                      <NButton size="small" type="error" quaternary>
                        <TheIcon icon="material-symbols:delete-outline" :size="18" />
                      </NButton>
                    </template>
                  </NPopconfirm>
                </NSpace>
              </div>
            </div>
          </div>
          <div v-else class="flex items-center justify-center h-full text-gray-400 py-12">
            <div class="text-center">
              <TheIcon icon="material-symbols:psychology" :size="48" class="mb-2 opacity-30" />
              <div class="text-base">{{ t('views.statistic-center.label_cn_2e9506a3') }}</div>
              <div class="text-sm mt-1">{{ t('views.statistic-center.label_cn_c521be84') }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ── CSV 导入弹窗 ── -->
  <NModal v-model:show="showCsvImportModal" title="CSV文本导入" preset="card" style="width: 640px">
    <NForm :model="csvImportForm" label-placement="top">
      <NFormItem label="表格名称" required>
        <NInput v-model:value="csvImportForm.name" placeholder="例如：导入的CSV数据" />
      </NFormItem>
      <NFormItem label="CSV文本内容" required>
        <NInput v-model:value="csvImportForm.csv_text" type="textarea" :rows="12" placeholder="粘贴CSV文本，第一行为表头&#10;例如：&#10;name,age,city&#10;张三,25,北京&#10;李四,30,上海" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showCsvImportModal = false">取消</NButton>
        <NButton type="primary" :loading="loading" @click="handleCsvImportSubmit">导入</NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- ── 原始表格复制到弹窗 ── -->
  <NModal v-model:show="showSheetCopyToModal" title="复制表格到其他工作区" preset="card" style="width: 480px">
    <div class="text-sm text-gray-500 mb-4">将复制 {{ selectedSheetIds.length }} 个表格到目标工作区（仅创建记录，不拷贝文件）</div>
    <NForm label-placement="top">
      <NFormItem label="目标工作区" required>
        <NSelect v-model:value="sheetCopyToForm.target_workspace_id" :options="sheetCopyToWorkspaces" placeholder="选择目标工作区" filterable />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showSheetCopyToModal = false">取消</NButton>
        <NButton type="primary" :disabled="!sheetCopyToForm.target_workspace_id" :loading="loading" @click="handleSheetCopyToWorkspace">确认复制</NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- ── 分析表格复制到弹窗 ── -->
  <NModal v-model:show="showAnalysisCopyToModal" title="复制分析表格到其他工作区" preset="card" style="width: 480px">
    <div class="text-sm text-gray-500 mb-4">将复制 {{ selectedAnalysisIds.length }} 个分析表格到目标工作区（仅创建记录，不拷贝文件）</div>
    <NForm label-placement="top">
      <NFormItem label="目标工作区" required>
        <NSelect v-model:value="analysisCopyToForm.target_workspace_id" :options="analysisCopyToWorkspaces" placeholder="选择目标工作区" filterable />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showAnalysisCopyToModal = false">取消</NButton>
        <NButton type="primary" :disabled="!analysisCopyToForm.target_workspace_id" :loading="loading" @click="handleAnalysisCopyToWorkspace">确认复制</NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- ── 分析表格关联分析弹窗 ── -->
  <NModal v-model:show="showCorrelateAnalysisModal" title="分析表格关联分析" preset="card" style="width: 560px">
    <NForm :model="correlateAnalysisForm" label-placement="top">
      <NFormItem label="分析表格 A" required>
        <NSelect v-model:value="correlateAnalysisForm.analysis_a_id" :options="analyses.map(a => ({ label: a.name, value: a.id }))" placeholder="选择第一个分析表格" filterable />
      </NFormItem>
      <NFormItem label="分析表格 B" required>
        <NSelect v-model:value="correlateAnalysisForm.analysis_b_id" :options="analyses.map(a => ({ label: a.name, value: a.id }))" placeholder="选择第二个分析表格" filterable />
      </NFormItem>
      <NFormItem label="AI代理" required>
        <NSelect v-model:value="correlateAnalysisForm.ai_proxy_id" :options="proxyOptions" placeholder="选择AI代理" filterable />
      </NFormItem>
      <NFormItem label="Skill（可选）">
        <NSelect v-model:value="correlateAnalysisForm.skill_id" :options="skillOptions" placeholder="选择Skill" filterable clearable />
      </NFormItem>
      <NFormItem label="分析名称">
        <NInput v-model:value="correlateAnalysisForm.name" placeholder="关联分析名称" />
      </NFormItem>
      <NFormItem label="自定义提示词">
        <NInput v-model:value="correlateAnalysisForm.prompt" type="textarea" :rows="3" placeholder="可选的附加提示词" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showCorrelateAnalysisModal = false">取消</NButton>
        <NButton type="primary" :disabled="!correlateAnalysisForm.ai_proxy_id || !correlateAnalysisForm.analysis_a_id || !correlateAnalysisForm.analysis_b_id" :loading="loading" @click="handleCorrelateAnalysesSubmit">开始分析</NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- ── AI 分析弹窗 ── -->
  <NModal v-model:show="showAnalyzeModal" :title="t('views.statistic-center.title_ai_cn_74d49b5a')" preset="card" style="width: 560px">
    <NForm :model="analyzeForm" label-placement="top">
      <NFormItem :label="t('views.statistic-center.label_cn_99757729')" required>
        <NInput v-model:value="analyzeForm.name" :placeholder="t('views.statistic-center.placeholder_cn_cfd1692e')" />
      </NFormItem>
      <NFormItem :label="t('views.statistic-center.label_ai_cn_9697e5cf')" required>
        <NSelect v-model:value="analyzeForm.ai_proxy_id" :options="proxyOptions" :placeholder="t('views.skill.placeholder_cn_523369d2')" />
      </NFormItem>
      <NFormItem :label="t('views.statistic-center.label_cn_59cd198d')">
        <NSelect v-model:value="analyzeForm.skill_id" :options="skillOptions" :placeholder="t('views.statistic-center.placeholder_cn_7395e01f')" clearable />
      </NFormItem>
      <NFormItem :label="t('views.statistic-center.label_cn_5d4e5198')">
        <NInput v-model:value="analyzeForm.prompt" type="textarea" :placeholder="t('views.statistic-center.placeholder_cn_16c348b7')" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showAnalyzeModal = false">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton>
        <NButton type="primary" :loading="loading" @click="handleAnalyzeSubmit">{{ t('views.statistic-center.label_cn_a7e17ae8') }}</NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- ── 关联分析弹窗 ── -->
  <NModal v-model:show="showCorrelateModal" :title="t('views.statistic-center.label_cn_5d47dd27')" preset="card" style="width: 560px">
    <NForm :model="correlateForm" label-placement="top">
      <NFormItem :label="t('views.statistic-center.label_cn_99757729')" required>
        <NInput v-model:value="correlateForm.name" :placeholder="t('views.statistic-center.placeholder_cn_cfd1692e')" />
      </NFormItem>
      <NFormItem :label="t('views.statistic-center.label_cn_4f6c09ef')" required>
        <NSelect v-model:value="correlateForm.sheet_a_id" :options="sheets.map(s=>({label:s.name,value:s.id}))" :placeholder="t('views.statistic-center.placeholder_cn_6d728351')" />
      </NFormItem>
      <NFormItem :label="t('views.statistic-center.label_cn_aae5ac8a')" required>
        <NSelect v-model:value="correlateForm.sheet_b_id" :options="sheets.map(s=>({label:s.name,value:s.id}))" :placeholder="t('views.statistic-center.placeholder_cn_a531dc62')" />
      </NFormItem>
      <NFormItem :label="t('views.statistic-center.label_ai_cn_9697e5cf')" required>
        <NSelect v-model:value="correlateForm.ai_proxy_id" :options="proxyOptions" :placeholder="t('views.skill.placeholder_cn_523369d2')" />
      </NFormItem>
      <NFormItem :label="t('views.statistic-center.label_cn_59cd198d')">
        <NSelect v-model:value="correlateForm.skill_id" :options="skillOptions" :placeholder="t('views.statistic-center.placeholder_cn_e2dd3849')" clearable />
      </NFormItem>
      <NFormItem :label="t('views.statistic-center.label_cn_5d4e5198')">
        <NInput v-model:value="correlateForm.prompt" type="textarea" :placeholder="t('views.statistic-center.placeholder_cn_16c348b7')" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showCorrelateModal = false">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton>
        <NButton type="primary" :loading="loading" @click="handleCorrelateSubmit">{{ t('views.statistic-center.label_cn_a7e17ae8') }}</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
.text-xs { font-size: 12px !important; line-height: 16px !important; }
.text-sm { font-size: 14px !important; line-height: 20px !important; }
.text-base { font-size: 16px !important; line-height: 24px !important; }
.text-lg { font-size: 18px !important; line-height: 26px !important; }
.text-xl { font-size: 20px !important; line-height: 28px !important; }
</style>
