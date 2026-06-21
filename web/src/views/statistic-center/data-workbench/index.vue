<script setup>
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, reactive } from 'vue'
import { useBreakpoints } from '@vueuse/core'
import {



  NButton, NInput, NLayout, NLayoutSider, NLayoutContent,
  NList, NListItem, NModal, NSpace, NSelect, NPopconfirm,
  NForm, NFormItem, NTag, NUpload, NUploadDragger, NText,
  NCheckbox, NSpin, NTabs, NTabPane, NEmpty, useMessage,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { useTaskProgressStore } from '@/store/modules/taskProgress'

const { t } = useI18n()

defineOptions({ name: i18n.global.t('views.statistic-center.title_cn_aad781ad') })

const message = useMessage()
const taskStore = useTaskProgressStore()

// 模拟进度工具：在后台逐步推进进度条直到 API 调用完成
function runWithProgress(taskTitle, apiCall, onSuccessMsg, onSuccess = null) {
  const taskId = taskStore.startTask(taskTitle)
  let progress = 0
  let phase = t('views.statistic-center.label_cn_22a360c4')

  const timer = setInterval(() => {
    if (progress < 10) {
      progress += 2
      phase = t('views.statistic-center.label_cn_1a5e2f0b')
    } else if (progress < 40) {
      progress += 1
      phase = t('views.statistic-center.label_cn_32922c6b')
    } else if (progress < 75) {
      progress += 0.5
      phase = t('views.statistic-center.label_cn_e320a5a0')
    }
    if (progress >= 75) progress = 75
    taskStore.updateProgress(taskId, { progress: Math.round(progress), message: '', phase })
  }, 800)

  return apiCall()
    .then((res) => {
      clearInterval(timer)
      taskStore.finishTask(taskId, onSuccessMsg)
      if (onSuccess) onSuccess(res)
    })
    .catch((e) => {
      clearInterval(timer)
      const detail = e?.response?.data?.msg || e?.message || t('views.network.roadNetworkWorkbench.messages.unknownError')
      taskStore.failTask(taskId, { message: t('views.network.roadNetworkWorkbench.messages.analyzeFail'), detail })
      throw e
    })
}

// 移动端适配
const bp = reactive(useBreakpoints({ sm: 666, md: 991 }))
const isMobileCollapsed = computed(() => bp.isSmaller('sm') || bp.between('sm', 'md'))

function formatFileSize(bytes) {
  if (bytes == null || bytes === 0) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// ── 工作区状态 ──
const workspaces = ref([])
const selectedWs = ref(null)
const userOptions = ref([])
const showWsModal = ref(false)
const wsModalForm = ref({ name: '', description: '', user_ids: [] })
const wsEditing = ref(false)
const loading = ref(false)

// ── 数据源 Tab ──
const activeDataSource = ref('excel')
const dataSourceTabs = [
  { name: 'excel', label: t('views.statistic-center.label_cn_a7d53e8d'), icon: 'material-symbols:table' },
  { name: 'documents', label: t('views.statistic-center.label_cn_c35ee691'), icon: 'material-symbols:description' },
  { name: 'database', label: t('views.statistic-center.label_cn_5bac3fe5'), icon: 'material-symbols:database' },
  { name: 'static-files', label: t('views.statistic-center.label_cn_6856e820'), icon: 'material-symbols:folder' },
]

// ── Excel 数据源状态 ──
const sheets = ref([])
const analyses = ref([])
const selectedAnalysisIds = ref([])
const uploading = ref(false)

// AI 分析弹窗
const showAnalyzeModal = ref(false)
const analyzeForm = ref({
  workspace_id: 0, sheet_id: null, name: '',
  ai_proxy_id: null, skill_id: null, prompt: '',
})
const proxyOptions = ref([])
const skillOptions = ref([])

// 关联分析弹窗
const showCorrelateModal = ref(false)
const correlateForm = ref({
  workspace_id: 0, sheet_a_id: null, sheet_b_id: null, name: '',
  ai_proxy_id: null, skill_id: null, prompt: '',
})

// ── 文档数据源状态 ──
const documents = ref([])
const analysisDocuments = ref([])
const selectedDocIds = ref([])
const uploadingDoc = ref(false)

// 文档AI分析弹窗
const showDocAnalyzeModal = ref(false)
const docAnalyzeForm = ref({
  workspace_id: 0, document_ids: [],
  ai_proxy_id: null, skill_id: null, prompt: '',
})

// ── 工作区 CRUD ──
async function loadWorkspaces() {
  try {
    const res = await api.getWorkspaceList({ page: 1, page_size: 9999 })
    workspaces.value = res.data || []
  } catch (e) { message.error(t('views.statistic-center.message_cn_17eec3f1')) }
}

async function selectWorkspace(ws) {
  selectedWs.value = ws
  await loadSheets()
  await loadAnalyses()
  await loadOriginalDocuments()
  await loadAnalysisDocuments()
}

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

async function loadUserOptions() {
  try {
    const res = await api.getWorkspaceUsers()
    userOptions.value = (res.data || []).map((u) => ({
      label: u.alias ? `${u.username} (${u.alias})` : u.username, value: u.id,
    }))
  } catch (e) { /* ignore */ }
}

function openCreateWs() {
  wsEditing.value = false
  wsModalForm.value = { name: '', description: '', user_ids: [] }
  showWsModal.value = true
  loadUserOptions()
}

function openEditWs() {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_cb53b40f')); return }
  wsEditing.value = true
  const ws = selectedWs.value
  wsModalForm.value = {
    name: ws.name, description: ws.description || '',
    user_ids: (ws.users || []).map((u) => u.id),
  }
  showWsModal.value = true
  loadUserOptions()
}

async function handleWsSubmit() {
  if (!wsModalForm.value.name) { message.warning(t('views.network.region.formRules.nameRequired')); return }
  try {
    if (wsEditing.value) {
      await api.updateWorkspace({ id: selectedWs.value.id, ...wsModalForm.value })
    } else {
      await api.createWorkspace(wsModalForm.value)
    }
    showWsModal.value = false
    await loadWorkspaces()
  } catch (e) { message.error(t('views.skill.message_cn_5fa802be')) }
}

async function deleteWorkspace() {
  if (!selectedWs.value) return
  try {
    await api.deleteWorkspace({ workspace_id: selectedWs.value.id })
    selectedWs.value = null
    sheets.value = []
    analyses.value = []
    await loadWorkspaces()
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.deleteFail')) }
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

function downloadBlob(data, filename) {
  const blob = new Blob([data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
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
      api.getAIProxyList({ page: 1, page_size: 9999 }),
      api.getSkillList({ page: 1, page_size: 9999 }),
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
      `AI分析: ${analyzeForm.value.name}`,
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
    api.getAIProxyList({ page: 1, page_size: 9999 }).then((res) => {
      proxyOptions.value = (res.data || []).map((p) => ({ label: p.name, value: p.id }))
    })
  }
  if (!skillOptions.value.length) {
    api.getSkillList({ page: 1, page_size: 9999 }).then((res) => {
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
      `关联分析: ${correlateForm.value.name}`,
      () => api.correlateSheets(correlateForm.value),
      t('views.statistic-center.message_cn_aa8f059c'),
    )
    message.success(t('views.statistic-center.message_cn_aa8f059c'))
    await loadAnalyses()
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.analyzeFail')) }
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

// ── 文档 CRUD ──
async function loadOriginalDocuments() {
  if (!selectedWs.value) return
  try {
    const res = await api.getDocumentList({ workspace_id: selectedWs.value.id, source_type: 'original' })
    documents.value = res.data || []
  } catch (e) { /* ignore */ }
}

async function loadAnalysisDocuments() {
  if (!selectedWs.value) return
  try {
    const res = await api.getDocumentList({ workspace_id: selectedWs.value.id, source_type: 'analysis' })
    analysisDocuments.value = res.data || []
  } catch (e) { /* ignore */ }
}

async function handleDocUpload({ file }) {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_cb53b40f')); return }
  uploadingDoc.value = true
  try {
    await api.uploadDocument(selectedWs.value.id, file.file)
    message.success(t('views.network.roadNetwork.messages.uploadSuccess'))
    await loadOriginalDocuments()
  } catch (e) { message.error(t('views.statistic-center.message_cn_54e5de42')) }
  uploadingDoc.value = false
}

async function downloadDocument(doc) {
  try {
    const res = await api.downloadDocument({ document_id: doc.id })
    const blob = new Blob([res.data], { type: 'application/octet-stream' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = doc.name; a.click()
    URL.revokeObjectURL(url)
  } catch (e) { message.error(t('views.network.label_cn_65e200d3')) }
}

async function deleteSingleDocument(doc) {
  try {
    await api.deleteDocument({ document_id: doc.id })
    await loadOriginalDocuments()
    await loadAnalysisDocuments()
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.deleteFail')) }
}

function toggleDocSelect(id) {
  const idx = selectedDocIds.value.indexOf(id)
  if (idx >= 0) selectedDocIds.value.splice(idx, 1)
  else selectedDocIds.value.push(id)
}

function toggleAllDocs() {
  if (selectedDocIds.value.length === documents.value.length) {
    selectedDocIds.value = []
  } else {
    selectedDocIds.value = documents.value.map((d) => d.id)
  }
}

async function batchDeleteDocs() {
  if (!selectedDocIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_f7870cc4')); return }
  try {
    loading.value = true
    await api.batchDeleteDocuments({ document_ids: [...selectedDocIds.value] })
    selectedDocIds.value = []
    message.success(t('views.statistic-center.message_cn_eedd70c6'))
    await loadOriginalDocuments()
    await loadAnalysisDocuments()
  } catch (e) { message.error(t('views.statistic-center.message_cn_1bac376d')) }
  loading.value = false
}

async function clearAllDocs() {
  if (!selectedWs.value) return
  try {
    loading.value = true
    await api.clearDocuments({ workspace_id: selectedWs.value.id })
    selectedDocIds.value = []
    message.success(t('views.statistic-center.message_cn_5a81209b'))
    await loadOriginalDocuments()
    await loadAnalysisDocuments()
  } catch (e) { message.error(t('views.network.region.messages.clearFail')) }
  loading.value = false
}

// ── 文档 AI 分析 ──
async function openDocAnalyze() {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_cb53b40f')); return }
  if (!selectedDocIds.value.length) { message.warning(t('views.statistic-center.message_cn_fdea36ae')); return }
  docAnalyzeForm.value = {
    workspace_id: selectedWs.value.id,
    document_ids: [...selectedDocIds.value],
    ai_proxy_id: null, skill_id: null, prompt: '',
  }
  try {
    const [pr, sl] = await Promise.all([
      api.getAIProxyList({ page: 1, page_size: 9999 }),
      api.getSkillList({ page: 1, page_size: 9999 }),
    ])
    proxyOptions.value = (pr.data || []).map((p) => ({ label: p.name, value: p.id }))
    skillOptions.value = (sl.data || []).map((s) => ({ label: s.title, value: s.id }))
  } catch (e) { /* ignore */ }
  showDocAnalyzeModal.value = true
}

async function handleDocAnalyzeSubmit() {
  if (!docAnalyzeForm.value.ai_proxy_id) { message.warning(t('views.skill.placeholder_cn_ee488ec6')); return }
  loading.value = true
  showDocAnalyzeModal.value = false
  try {
    await runWithProgress(
      t('views.statistic-center.label_cn_3a236690'),
      () => api.aiAnalyzeDocuments(docAnalyzeForm.value),
      t('views.statistic-center.label_cn_603de948'),
    )
    message.success(t('views.statistic-center.message_cn_57c52570'))
    await loadAnalysisDocuments()
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.analyzeFail')) }
  loading.value = false
}

// ── 文档编辑（Vditor） ──
const showDocEditModal = ref(false)
const editingDoc = ref(null)
const editingDocContent = ref('')
const docSaving = ref(false)
const docEditorContainer = ref(null)
let docVditorInstance = null

function initDocVditor(markdown) {
  destroyDocVditor()
  nextTick(() => {
    if (!docEditorContainer.value) return
    const Vditor = window.Vditor
    docVditorInstance = new Vditor(docEditorContainer.value, {
      mode: 'wysiwyg',
      height: '100%',
      placeholder: t('views.skill.placeholder_cn_7de77ab9'),
      value: markdown || '',
      toolbar: [
        'emoji', 'headings', 'bold', 'italic', 'strike', 'link', '|',
        'list', 'ordered-list', 'check', 'outdent', 'indent', '|',
        'quote', 'line', 'code', 'inline-code', 'insert-before', 'insert-after', '|',
        'table', '|', 'undo', 'redo', '|',
        'fullscreen', 'outline', 'preview',
      ],
      cache: { enable: false },
    })
  })
}

function destroyDocVditor() {
  if (docVditorInstance) {
    docVditorInstance.destroy()
    docVditorInstance = null
  }
}

async function openDocEditor(doc) {
  editingDoc.value = doc
  editingDocContent.value = ''
  showDocEditModal.value = true
  try {
    const res = await api.getDocumentContent({ document_id: doc.id })
    editingDocContent.value = res.data?.content || ''
  } catch (e) {
    editingDocContent.value = ''
  }
  initDocVditor(editingDocContent.value)
}

async function handleDocSave() {
  const content = docVditorInstance ? docVditorInstance.getValue() : editingDocContent.value
  docSaving.value = true
  try {
    const res = await api.updateDocumentContent({ document_id: editingDoc.value.id, content })
    message.success(t('views.skill.message_cn_3b108349'))
    // 更新列表中的文档信息
    const idx = analysisDocuments.value.findIndex((d) => d.id === editingDoc.value.id)
    if (idx >= 0 && res.data) {
      Object.assign(analysisDocuments.value[idx], res.data)
    }
    showDocEditModal.value = false
    destroyDocVditor()
  } catch (e) {
    message.error(t('views.network.roadNetworkWorkbench.messages.saveFail'))
  }
  docSaving.value = false
}

function handleDocEditCancel() {
  showDocEditModal.value = false
  destroyDocVditor()
}

onMounted(() => loadWorkspaces())

onBeforeUnmount(() => {
  destroyDocVditor()
})
</script>

<template>
  <NLayout has-sider style="height: calc(100vh - 120px)">
    <!-- ── 左侧工作区列表 ── -->
    <NLayoutSider
      bordered width="320" :collapsed-width="0"
      :collapsed="isMobileCollapsed" show-trigger="arrow-circle"
      :native-scrollbar="false" content-style="padding: 12px"
    >
      <NSpace vertical>
        <NButton type="primary" block @click="openCreateWs">
          <TheIcon icon="material-symbols:add" :size="20" class="mr-2" />新建工作区
        </NButton>
        <NList hoverable clickable :show-divider="false">
          <NListItem
            v-for="ws in workspaces" :key="ws.id"
            :class="{ 'bg-blue-50 dark:bg-blue-900': selectedWs?.id === ws.id }"
            style="border-radius: 8px; margin-bottom: 4px; cursor: pointer"
            @click="selectWorkspace(ws)"
          >
            <div class="flex flex-col flex-1 min-w-0">
              <span class="font-medium text-base truncate">{{ ws.name }}</span>
              <span class="text-gray-400 text-sm">{{ ws.updated_at }}</span>
            </div>
          </NListItem>
        </NList>
        <div v-if="!workspaces.length" class="text-center text-gray-400 py-10">暂无工作区</div>
      </NSpace>
    </NLayoutSider>

    <!-- ── 右侧数据源区域 ── -->
    <NLayoutContent content-style="padding: 16px">
      <NSpin :show="loading">
        <div v-if="!selectedWs" class="flex items-center justify-center h-full text-gray-400 text-lg">
          请选择左侧工作区
        </div>

        <div v-else class="h-full flex flex-col">
          <!-- 工作区标题栏 -->
          <div class="flex items-center justify-between mb-4">
            <div>
              <h2 class="text-xl font-bold m-0">{{ selectedWs.name }}</h2>
              <p v-if="selectedWs.description" class="text-gray-500 text-sm m-0 mt-1">{{ selectedWs.description }}</p>
            </div>
            <NSpace>
              <NButton size="small" @click="openEditWs">
                <TheIcon icon="material-symbols:edit" :size="18" class="mr-1" />属性
              </NButton>
              <NPopconfirm @positive-click="deleteWorkspace">
                <template #trigger>
                  <NButton size="small" type="error">
                    <TheIcon icon="material-symbols:delete-outline" :size="18" class="mr-1" />删除
                  </NButton>
                </template>
                确认删除该工作区及所有数据？
              </NPopconfirm>
            </NSpace>
          </div>

          <!-- 数据源 Tab 切换 -->
          <NTabs v-model:value="activeDataSource" type="card" class="flex-1 flex flex-col" style="min-height: 0">
            <NTabPane v-for="tab in dataSourceTabs" :key="tab.name" :name="tab.name">
              <template #tab>
                <TheIcon :icon="tab.icon" :size="18" class="mr-2" />{{ tab.label }}
              </template>

              <!-- ═══════════════════════════════════════════
                   Excel表格数据 Tab
                   ═══════════════════════════════════════════ -->
              <div v-if="tab.name === 'excel'" class="flex-1 flex flex-col" style="min-height: 0">
                <!-- 上传区 -->
                <div class="mb-5">
                  <NUpload :show-file-list="false" :default-upload="false" accept=".xlsx,.xls,.csv" @change="handleUpload">
                    <NUploadDragger
                      class="w-full"
                      style="border-radius: 12px; --n-border-hover: 2px dashed #3b82f6"
                    >
                      <div v-if="!uploading" class="flex flex-col items-center py-8 px-4">
                        <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 flex items-center justify-center mb-4">
                          <TheIcon icon="material-symbols:upload-file" :size="36" class="text-blue-500" />
                        </div>
                        <div class="text-base font-semibold text-gray-700 dark:text-gray-300 mb-1">上传原始表格</div>
                        <div class="text-sm text-gray-400 mb-3">点击或拖拽文件到此区域上传</div>
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
                        <div class="text-base font-semibold text-blue-600 dark:text-blue-400 mb-3">正在上传...</div>
                        <div class="w-48 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                          <div class="h-full bg-blue-500 rounded-full animate-pulse" style="width: 60%" />
                        </div>
                      </div>
                    </NUploadDragger>
                  </NUpload>
                </div>

                <!-- 左右双栏布局 -->
                <div class="flex gap-3 flex-1" style="min-height: 0">
                  <!-- ── 左栏：原始表格 ── -->
                  <div class="flex-1 flex flex-col" style="min-width: 0">
                    <div class="flex items-center justify-between mb-2 px-1">
                      <div class="flex items-center gap-2">
                        <TheIcon icon="material-symbols:description" :size="20" class="text-blue-500" />
                        <span class="font-semibold text-base">原始表格</span>
                        <NTag size="small" :bordered="false" type="info">{{ sheets.length }}</NTag>
                      </div>
                    </div>
                    <div class="flex-1 overflow-auto rounded-lg border border-gray-100 bg-gray-50/50 dark:bg-gray-800/30" style="min-height: 0">
                      <div v-if="sheets.length" class="p-3 grid gap-3">
                        <div
                          v-for="s in sheets" :key="s.id"
                          class="bg-white dark:bg-gray-800 rounded-lg border border-gray-100 p-4 hover:shadow-sm transition-shadow"
                        >
                          <div class="flex items-center justify-between">
                            <div class="flex items-center gap-3 min-w-0 flex-1">
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
                                <TheIcon icon="material-symbols:psychology" :size="16" class="mr-1" />AI分析
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
                          <div class="text-base">暂无原始表格</div>
                          <div class="text-sm mt-1">上传 Excel 或 CSV 文件开始分析</div>
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
                        <span class="font-semibold text-base">拆解分析表格</span>
                        <NTag size="small" :bordered="false" type="success">{{ analyses.length }}</NTag>
                      </div>
                      <NSpace v-if="analyses.length" size="small">
                        <NButton size="small" @click="openCorrelate" :disabled="sheets.length < 2">
                          <TheIcon icon="material-symbols:compare-arrows" :size="16" class="mr-1" />关联分析
                        </NButton>
                        <NButton size="small" type="primary" :disabled="!selectedAnalysisIds.length" @click="batchExportAnalyses">
                          <TheIcon icon="material-symbols:download" :size="16" class="mr-1" />导出({{ selectedAnalysisIds.length }})
                        </NButton>
                        <NPopconfirm @positive-click="batchDeleteAnalyses" :disabled="!selectedAnalysisIds.length">
                          <template #trigger>
                            <NButton size="small" type="warning" :disabled="!selectedAnalysisIds.length">
                              <TheIcon icon="material-symbols:delete-outline" :size="16" />删除
                            </NButton>
                          </template>
                          确认删除已选中的 {{ selectedAnalysisIds.length }} 个分析表格？
                        </NPopconfirm>
                        <NPopconfirm @positive-click="clearAllAnalyses">
                          <template #trigger>
                            <NButton size="small" type="error">
                              <TheIcon icon="material-symbols:delete-sweep" :size="16" class="mr-1" />清空
                            </NButton>
                          </template>
                          确认清空当前工作区的所有分析表格？
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
                          <div class="text-base">暂无分析结果</div>
                          <div class="text-sm mt-1">对原始表格执行 AI 分析后生成</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- ═══════════════════════════════════════════
                   文档数据 Tab（占位）
                   ═══════════════════════════════════════════ -->
              <div v-else-if="tab.name === 'documents'" class="flex-1 flex flex-col" style="min-height: 0">
                <!-- 上传区 -->
                <div class="mb-5">
                  <NUpload :show-file-list="false" :default-upload="false" accept=".txt,.md,.pdf,.docx,.ppt,.pptx,.xlsx,.xls,.csv" @change="handleDocUpload">
                    <NUploadDragger
                      class="w-full"
                      style="border-radius: 12px; --n-border-hover: 2px dashed #3b82f6"
                    >
                      <div v-if="!uploadingDoc" class="flex flex-col items-center py-8 px-4">
                        <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 flex items-center justify-center mb-4">
                          <TheIcon icon="material-symbols:description" :size="36" class="text-purple-500" />
                        </div>
                        <div class="text-base font-semibold text-gray-700 dark:text-gray-300 mb-1">上传文档</div>
                        <div class="text-sm text-gray-400 mb-3">点击或拖拽文件到此区域上传</div>
                        <div class="flex items-center gap-2 text-xs text-gray-400 bg-gray-100 dark:bg-gray-800 rounded-full px-3 py-1">
                          <TheIcon icon="material-symbols:article" :size="14" />
                          <span>.txt</span>
                          <span>.md</span>
                          <span>.pdf</span>
                          <span>.docx</span>
                          <span>.xlsx</span>
                          <span>.ppt</span>
                        </div>
                      </div>
                      <div v-else class="flex flex-col items-center py-8 px-4">
                        <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 flex items-center justify-center mb-4">
                          <TheIcon icon="material-symbols:cloud-upload" :size="36" class="text-purple-500 animate-pulse" />
                        </div>
                        <div class="text-base font-semibold text-purple-600 dark:text-purple-400 mb-3">正在上传...</div>
                        <div class="w-48 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                          <div class="h-full bg-purple-500 rounded-full animate-pulse" style="width: 60%" />
                        </div>
                      </div>
                    </NUploadDragger>
                  </NUpload>
                </div>

                <!-- 左右双栏布局 -->
                <div class="flex gap-3 flex-1" style="min-height: 0">
                  <!-- ── 左栏：原始文档 ── -->
                  <div class="flex-1 flex flex-col" style="min-width: 0">
                    <div class="flex items-center justify-between mb-2 px-1">
                      <div class="flex items-center gap-2">
                        <NCheckbox
                          size="small"
                          :checked="selectedDocIds.length === documents.length && documents.length > 0"
                          :indeterminate="selectedDocIds.length > 0 && selectedDocIds.length < documents.length"
                          @update:checked="toggleAllDocs"
                        />
                        <TheIcon icon="material-symbols:description" :size="20" class="text-blue-500" />
                        <span class="font-semibold text-base">原始文档</span>
                        <NTag size="small" :bordered="false" type="info">{{ documents.length }}</NTag>
                      </div>
                      <NSpace v-if="documents.length" size="small">
                        <NButton size="small" type="primary" :disabled="!selectedDocIds.length" @click="openDocAnalyze">
                          <TheIcon icon="material-symbols:psychology" :size="16" class="mr-1" />AI分析({{ selectedDocIds.length }})
                        </NButton>
                        <NPopconfirm @positive-click="batchDeleteDocs" :disabled="!selectedDocIds.length">
                          <template #trigger>
                            <NButton size="small" type="warning" :disabled="!selectedDocIds.length">
                              <TheIcon icon="material-symbols:delete-outline" :size="16" />删除
                            </NButton>
                          </template>
                          确认删除选中的 {{ selectedDocIds.length }} 个文档？
                        </NPopconfirm>
                        <NPopconfirm @positive-click="clearAllDocs">
                          <template #trigger>
                            <NButton size="small" type="error">
                              <TheIcon icon="material-symbols:delete-sweep" :size="16" class="mr-1" />清空
                            </NButton>
                          </template>
                          确认清空所有文档？
                        </NPopconfirm>
                      </NSpace>
                    </div>
                    <div class="flex-1 overflow-auto rounded-lg border border-gray-100 bg-gray-50/50 dark:bg-gray-800/30" style="min-height: 0">
                      <div v-if="documents.length" class="p-3 grid gap-3">
                        <div
                          v-for="d in documents" :key="d.id"
                          class="bg-white dark:bg-gray-800 rounded-lg border border-gray-100 p-4 hover:shadow-sm transition-shadow"
                        >
                          <div class="flex items-center justify-between">
                            <div class="flex items-center gap-3 min-w-0 flex-1">
                              <NCheckbox
                                size="small"
                                :checked="selectedDocIds.includes(d.id)"
                                @update:checked="() => toggleDocSelect(d.id)"
                                class="flex-shrink-0"
                              />
                              <TheIcon icon="material-symbols:article" :size="22" class="text-blue-500 flex-shrink-0" />
                              <div class="min-w-0">
                                <div class="font-medium text-base truncate">{{ d.name }}</div>
                                <div class="flex items-center gap-3 text-sm text-gray-400 mt-0.5">
                                  <span v-if="d.file_size">{{ formatFileSize(d.file_size) }}</span>
                                  <span>{{ d.char_count?.toLocaleString() }} 字符</span>
                                  <span>{{ d.created_at?.slice(0, 10) }}</span>
                                </div>
                              </div>
                            </div>
                            <NSpace size="small" class="flex-shrink-0 ml-3">
                              <NButton size="small" quaternary @click="downloadDocument(d)" :title="t('views.tool.vehicle.label_receive')">
                                <TheIcon icon="material-symbols:download" :size="18" />
                              </NButton>
                              <NPopconfirm @positive-click="deleteSingleDocument(d)">
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
                          <div class="text-base">暂无原始文档</div>
                          <div class="text-sm mt-1">上传 txt / pdf / word / ppt 文档开始分析</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- ── 右栏：AI分析文档 ── -->
                  <div class="flex-1 flex flex-col" style="min-width: 0">
                    <div class="flex items-center justify-between mb-2 px-1">
                      <div class="flex items-center gap-2">
                        <TheIcon icon="material-symbols:analytics" :size="20" class="text-green-500" />
                        <span class="font-semibold text-base">AI分析文档</span>
                        <NTag size="small" :bordered="false" type="success">{{ analysisDocuments.length }}</NTag>
                      </div>
                    </div>
                    <div class="flex-1 overflow-auto rounded-lg border border-gray-100 bg-gray-50/50 dark:bg-gray-800/30" style="min-height: 0">
                      <div v-if="analysisDocuments.length" class="p-3 grid gap-3">
                        <div
                          v-for="a in analysisDocuments" :key="a.id"
                          class="bg-white dark:bg-gray-800 rounded-lg border border-gray-100 p-4 hover:shadow-sm transition-shadow"
                        >
                          <div class="flex items-center justify-between">
                            <div class="flex items-center gap-3 min-w-0 flex-1">
                              <TheIcon icon="material-symbols:psychology" :size="22" class="text-green-500 flex-shrink-0" />
                              <div class="min-w-0">
                                <div class="font-medium text-base truncate">{{ a.name }}</div>
                                <div class="flex items-center gap-3 text-sm text-gray-400 mt-0.5">
                                  <span v-if="a.file_size">{{ formatFileSize(a.file_size) }}</span>
                                  <span>{{ a.char_count?.toLocaleString() }} 字符</span>
                                  <span>{{ a.created_at?.slice(0, 10) }}</span>
                                </div>
                              </div>
                            </div>
                            <NSpace size="small" class="flex-shrink-0 ml-3">
                              <NButton size="small" quaternary @click="openDocEditor(a)" :title="t('views.workbench.label_edit')">
                                <TheIcon icon="material-symbols:edit" :size="18" />
                              </NButton>
                              <NButton size="small" quaternary @click="downloadDocument(a)" :title="t('views.tool.vehicle.label_receive')">
                                <TheIcon icon="material-symbols:download" :size="18" />
                              </NButton>
                              <NPopconfirm @positive-click="deleteSingleDocument(a)">
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
                          <div class="text-base">暂无分析文档</div>
                          <div class="text-sm mt-1">选择原始文档执行 AI 分析后生成</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- ═══════════════════════════════════════════
                   数据库数据 Tab（占位）
                   ═══════════════════════════════════════════ -->
              <div v-else-if="tab.name === 'database'" class="flex-1 flex items-center justify-center py-20">
                <NEmpty description="数据库数据功能即将上线">
                  <template #extra>
                    <NText depth="3" class="text-center" style="max-width: 400px">
                      支持连接 MySQL、PostgreSQL、SQLite 等数据库，通过 AI 生成 SQL 查询并可视化结果。
                    </NText>
                  </template>
                </NEmpty>
              </div>

              <!-- ═══════════════════════════════════════════
                   静态文件数据 Tab（占位）
                   ═══════════════════════════════════════════ -->
              <div v-else-if="tab.name === 'static-files'" class="flex-1 flex items-center justify-center py-20">
                <NEmpty description="静态文件数据功能即将上线">
                  <template #extra>
                    <NText depth="3" class="text-center" style="max-width: 400px">
                      支持管理图片、JSON、XML、CSV 等静态数据文件，提供预览、格式转换与批量处理能力。
                    </NText>
                  </template>
                </NEmpty>
              </div>
            </NTabPane>
          </NTabs>
        </div>
      </NSpin>
    </NLayoutContent>
  </NLayout>

  <!-- ── 工作区弹窗 ── -->
  <NModal v-model:show="showWsModal" :title="wsEditing ? '编辑工作区' : t('views.statistic-center.title_cn_9cb11943')" preset="card" style="width: 500px">
    <NForm :model="wsModalForm" label-placement="top">
      <NFormItem :label="t('views.network.region.formLabels.name')" required>
        <NInput v-model:value="wsModalForm.name" :placeholder="t('views.statistic-center.placeholder_cn_042874e1')" />
      </NFormItem>
      <NFormItem :label="t('views.statistic-center.label_cn_3bdd08ad')">
        <NInput v-model:value="wsModalForm.description" :placeholder="t('views.statistic-center.label_cn_3bdd08ad')" type="textarea" />
      </NFormItem>
      <NFormItem :label="t('views.skill.label_cn_5f07f1ad')">
        <NSelect v-model:value="wsModalForm.user_ids" :options="userOptions" multiple :placeholder="t('views.statistic-center.placeholder_cn_6674b18c')" filterable />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showWsModal = false">取消</NButton>
        <NButton type="primary" @click="handleWsSubmit">确认</NButton>
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
        <NButton @click="showAnalyzeModal = false">取消</NButton>
        <NButton type="primary" :loading="loading" @click="handleAnalyzeSubmit">开始分析</NButton>
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
        <NButton @click="showCorrelateModal = false">取消</NButton>
        <NButton type="primary" :loading="loading" @click="handleCorrelateSubmit">开始分析</NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- ── 文档AI分析弹窗 ── -->
  <NModal v-model:show="showDocAnalyzeModal" :title="t('views.statistic-center.label_cn_3a236690')" preset="card" style="width: 560px">
    <NForm :model="docAnalyzeForm" label-placement="top">
      <NFormItem :label="t('views.statistic-center.label_ai_cn_9697e5cf')" required>
        <NSelect v-model:value="docAnalyzeForm.ai_proxy_id" :options="proxyOptions" :placeholder="t('views.skill.placeholder_cn_523369d2')" />
      </NFormItem>
      <NFormItem :label="t('views.statistic-center.label_cn_59cd198d')">
        <NSelect v-model:value="docAnalyzeForm.skill_id" :options="skillOptions" :placeholder="t('views.statistic-center.placeholder_cn_7395e01f')" clearable />
      </NFormItem>
      <NFormItem :label="t('views.statistic-center.label_cn_5d4e5198')">
        <NInput v-model:value="docAnalyzeForm.prompt" type="textarea" :placeholder="t('views.statistic-center.placeholder_cn_16c348b7')" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showDocAnalyzeModal = false">取消</NButton>
        <NButton type="primary" :loading="loading" @click="handleDocAnalyzeSubmit">开始分析</NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- ── 文档编辑弹窗（Vditor） ── -->
  <NModal
    v-model:show="showDocEditModal"
    :title="t('views.statistic-center.title_cn_0b61ccf8') + (editingDoc?.name || '')"
    preset="card"
    style="width: 900px"
    @after-leave="destroyDocVditor"
  >
    <div ref="docEditorContainer" style="height: 60vh; min-height: 400px" />
    <template #footer>
      <NSpace justify="end">
        <NButton @click="handleDocEditCancel">取消</NButton>
        <NButton type="primary" :loading="docSaving" @click="handleDocSave">保存</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
/*
  全局 html { font-size: 4px } 导致 UnoCSS 的 text-* 类（基于 rem）
  实际渲染只有预期的 1/4。此处用 px 覆盖 font-size 和 line-height。
*/
.text-xs { font-size: 12px !important; line-height: 16px !important; }
.text-sm { font-size: 14px !important; line-height: 20px !important; }
.text-base { font-size: 16px !important; line-height: 24px !important; }
.text-lg { font-size: 18px !important; line-height: 26px !important; }
.text-xl { font-size: 20px !important; line-height: 28px !important; }
</style>
