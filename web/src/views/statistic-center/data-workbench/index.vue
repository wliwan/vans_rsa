<script setup>
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, reactive } from 'vue'
import { useBreakpoints } from '@vueuse/core'
import {



  NButton, NInput, NInputNumber, NLayout, NLayoutSider, NLayoutContent,
  NList, NListItem, NModal, NSpace, NSelect, NPopconfirm,
  NForm, NFormItem, NTag, NUpload, NUploadDragger, NText,
  NCheckbox, NSpin, NTabs, NTabPane, NEmpty, NBreadcrumb, NBreadcrumbItem,
  NSlider, useMessage,
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

const wsAccentColors = ['#6366f1', '#8b5cf6', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899']
function wsAccent(idx) { return wsAccentColors[idx % wsAccentColors.length] }

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
      `${t('views.statistic-center.label_cn_55604525')} ${correlateForm.value.name}`,
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

// ── 静态文件数据状态 ──
const staticFileSourceType = ref('original')
const staticFiles = ref([])
const selectedStaticFileIds = ref([])
const selectedStaticFile = ref(null)
const staticFilesLoading = ref(false)
const staticFileUploadRef = ref(null)
const staticFileBaseUrl = ref('')

let staticFileUploadTimer = null
const staticFileUploadQueue = new Map()
let staticFileUploadLock = false

const showCVModal = ref(false)
const cvForm = ref({ operation: 'resize', params: {} })
const cvOperations = ref({})
const cvPreviewSrc = ref('')

const showAIModal = ref(false)
const aiForm = ref({ ai_proxy_id: null, skill_id: null, prompt: '' })

const ocrLoading = ref(false)

const showMaterialImportModal = ref(false)
const materialRegions = ref([])
const materialBreadcrumb = ref([])
const materialCurrentList = ref([])
const materialSelectedIds = ref([])

const showStaticFileCopyToModal = ref(false)
const staticFileCopyToWorkspaces = ref([])
const staticFileCopyToForm = ref({ target_workspace_id: null })

const showBaseUrlModal = ref(false)
const baseUrlForm = ref({ base_url: '' })

function formatResolution(w, h) {
  if (w == null && h == null) return ''
  return [w, h].filter(Boolean).join(' × ')
}

async function loadStaticFileBaseUrl() {
  try { const res = await api.getStaticFileBaseUrl(); staticFileBaseUrl.value = res.data?.base_url || '' } catch (e) {}
}

function getStaticFileShortUrl(file) {
  if (!file?.short_url) return ''
  return `${staticFileBaseUrl.value || window.location.origin}${file.short_url}`
}

function exifPreview(exif) {
  if (!exif || typeof exif !== 'object') return []
  const priorityKeys = [
    'Make', 'Model', 'Software', 'DateTime', 'DateTimeOriginal', 'DateTimeDigitized',
    'ImageWidth', 'ImageLength', 'Orientation', 'XResolution', 'YResolution', 'ResolutionUnit',
    'ExposureTime', 'FNumber', 'ISOSpeedRatings', 'ShutterSpeedValue', 'ApertureValue',
    'FocalLength', 'FocalLengthIn35mmFilm', 'Flash', 'WhiteBalance',
    'GPSLatitude', 'GPSLongitude', 'GPSAltitude', 'GPSLatitudeRef', 'GPSLongitudeRef',
    'ColorSpace', 'ExifImageWidth', 'ExifImageHeight', 'Compression',
    'Artist', 'Copyright', 'ImageDescription', 'UserComment',
  ]
  const seen = new Set(), result = []
  for (const key of priorityKeys) {
    if (exif[key] !== undefined && exif[key] !== null && exif[key] !== '') { seen.add(key); result.push([key, String(exif[key])]) }
  }
  for (const [key, val] of Object.entries(exif)) {
    if (!seen.has(key) && val !== null && val !== undefined && val !== '') result.push([key, String(val)])
  }
  return result
}

async function copyShortLink(file) {
  const url = getStaticFileShortUrl(file)
  if (!url) { message.warning(t('views.statistic-center.label_cn_9de9bf4c')); return }
  try { await navigator.clipboard.writeText(url); message.success(t('views.statistic-center.label_cn_20ad8798')) }
  catch { const input = document.createElement('input'); input.value = url; document.body.appendChild(input); input.select(); document.execCommand('copy'); document.body.removeChild(input); message.success(t('views.statistic-center.label_cn_20ad8798')) }
}

async function loadStaticFiles() {
  if (!selectedWs.value) return
  staticFilesLoading.value = true
  loadStaticFileBaseUrl()
  try {
    const res = await api.getStaticFileList({ workspace_id: selectedWs.value.id, source_type: staticFileSourceType.value, page: 1, page_size: 500 })
    staticFiles.value = res.data || []
    const validIds = new Set(staticFiles.value.map(f => f.id))
    selectedStaticFileIds.value = selectedStaticFileIds.value.filter(id => validIds.has(id))
    if (selectedStaticFile.value && !validIds.has(selectedStaticFile.value.id)) selectedStaticFile.value = null
  } catch (e) { message.error(t('views.statistic-center.message_cn_5f476ef2')) }
  staticFilesLoading.value = false
}

function onStaticFileSourceTypeChange() { selectedStaticFileIds.value = []; selectedStaticFile.value = null; loadStaticFiles() }

function toggleStaticFileSelect(id) {
  const idx = selectedStaticFileIds.value.indexOf(id)
  if (idx >= 0) selectedStaticFileIds.value.splice(idx, 1); else selectedStaticFileIds.value.push(id)
}

function toggleAllStaticFiles() {
  if (selectedStaticFileIds.value.length === staticFiles.value.length) selectedStaticFileIds.value = []
  else selectedStaticFileIds.value = staticFiles.value.map(f => f.id)
}

function onStaticFileRowClick(file) { selectedStaticFileIds.value = [file.id]; selectedStaticFile.value = file }

async function handleStaticFileUpload({ file, fileList }) {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_aac7e445')); return }
  if (staticFileUploadLock) return
  for (const f of fileList) { if (f.status === 'pending' && f.file) staticFileUploadQueue.set(`${f.file.name}__${f.file.size}`, f.file) }
  if (!staticFileUploadQueue.size) return
  clearTimeout(staticFileUploadTimer)
  staticFileUploadTimer = setTimeout(async () => {
    if (staticFileUploadLock) return
    staticFileUploadLock = true
    const files = [...staticFileUploadQueue.values()]
    staticFileUploadQueue.clear()
    try {
      const res = await api.batchUploadStaticFiles(selectedWs.value.id, staticFileSourceType.value, '', '', files)
      message.success(t('views.statistic-center.message_cn_509132eb', { count: res.data?.success_count || 0 }))
      await loadStaticFiles()
    } catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_54e5de42')) }
    staticFileUploadLock = false
  }, 300)
}

async function deleteStaticFileItem(file) {
  try { await api.deleteStaticFile({ file_id: file.id }); message.success(t('views.statistic-center.message_cn_0007d170')); await loadStaticFiles() }
  catch (e) { message.error(t('views.statistic-center.message_cn_acf0664a')) }
}

async function batchDeleteStaticFilesAction() {
  if (!selectedStaticFileIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_3c2412f9')); return }
  try {
    await api.batchDeleteStaticFiles({ file_ids: [...selectedStaticFileIds.value] })
    message.success(t('views.statistic-center.message_cn_eedd70c6'))
    selectedStaticFileIds.value = []; selectedStaticFile.value = null; await loadStaticFiles()
  } catch (e) { message.error(t('views.statistic-center.message_cn_1bac376d')) }
}

async function batchExportStaticFilesAction() {
  if (!selectedStaticFileIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_3c2412f9')); return }
  try {
    const res = await api.batchExportStaticFiles({ file_ids: [...selectedStaticFileIds.value] })
    const blob = new Blob([res.data], { type: 'application/zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = t('views.statistic-center.label_cn_f7b42666'); a.click()
    URL.revokeObjectURL(url)
    message.success(`已导出 ${selectedStaticFileIds.value.length} 个文件`)
  } catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_dd51ab50')) }
}

async function downloadStaticFileItem(file) {
  try {
    const res = await api.downloadStaticFile({ file_id: file.id })
    const blob = new Blob([res.data]); const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = file.file_name || file.name; a.click()
    URL.revokeObjectURL(url)
  } catch (e) { message.error(t('views.statistic-center.message_cn_65e200d3')) }
}

async function openCVModal() {
  if (!selectedStaticFileIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_7d69c1a5')); return }
  cvForm.value = { operation: 'resize', params: {} }; cvPreviewSrc.value = ''
  try { const res = await api.getStaticFileCVOperations(); cvOperations.value = res.data || {} } catch (e) {}
  const first = staticFiles.value.find(f => f.id === selectedStaticFileIds.value[0])
  if (first?.is_image) {
    try { const res = await api.downloadStaticFile({ file_id: first.id }); cvPreviewSrc.value = URL.createObjectURL(new Blob([res.data])) } catch (e) {}
  }
  showCVModal.value = true
}

function onCVOperationChange(op) { cvForm.value.operation = op; cvForm.value.params = {} }
function updateCVParam(key, value) { cvForm.value.params = { ...cvForm.value.params, [key]: value } }

async function handleCVSubmit() {
  loading.value = true; showCVModal.value = false
  if (cvPreviewSrc.value) URL.revokeObjectURL(cvPreviewSrc.value)
  try {
    await runWithProgress(`OpenCV处理 (${cvForm.value.operation})`, () => api.cvProcessStaticFiles({ file_ids: [...selectedStaticFileIds.value], operation: cvForm.value.operation, params: cvForm.value.params }), t('views.statistic-center.message_cn_c4ec4878'), async (res) => { message.success(`OpenCV 处理完成：成功 ${res.data?.success_count || 0} 个`); await loadStaticFiles() })
  } catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_fb005598')) }
  loading.value = false
}

async function openAIModal() {
  if (!selectedStaticFileIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_7d69c1a5')); return }
  aiForm.value = { ai_proxy_id: null, skill_id: null, prompt: '' }
  try { const [pr, sl] = await Promise.all([api.getAIProxyList({ page: 1, page_size: 9999 }), api.getSkillList({ page: 1, page_size: 9999 })]); proxyOptions.value = (pr.data || []).map(p => ({ label: p.name, value: p.id })); skillOptions.value = (sl.data || []).map(s => ({ label: s.title, value: s.id })) } catch (e) {}
  showAIModal.value = true
}

async function handleAISubmit() {
  if (!aiForm.value.ai_proxy_id) { message.warning(t('views.statistic-center.placeholder_cn_ee488ec6')); return }
  loading.value = true; showAIModal.value = false
  try {
    await runWithProgress(t('views.statistic-center.label_cn_a88a39d8'), () => api.aiProcessStaticFiles({ file_ids: [...selectedStaticFileIds.value], ai_proxy_id: aiForm.value.ai_proxy_id, skill_id: aiForm.value.skill_id || null, prompt: aiForm.value.prompt || '' }), t('views.statistic-center.message_cn_5f13f399'), async (res) => { message.success(`AI 处理完成：成功 ${res.data?.success_count || 0} 个`); await loadStaticFiles() })
  } catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_9ecb35a3')) }
  loading.value = false
}

async function handleOCRExtract() {
  if (!selectedStaticFileIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_7d69c1a5')); return }
  ocrLoading.value = true
  try { await runWithProgress(t('views.statistic-center.label_cn_aef2c23a'), () => api.ocrExtractStaticFiles({ file_ids: [...selectedStaticFileIds.value], workspace_id: selectedWs.value.id }), t('views.statistic-center.message_cn_8c3035a0'), (res) => { message.success(`OCR 提取完成：成功 ${res.data?.success_count || 0} 个`) }) }
  catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_13c8c69b')) }
  ocrLoading.value = false
}

async function openMaterialImportModal() {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_aac7e445')); return }
  materialBreadcrumb.value = []; materialCurrentList.value = []; materialSelectedIds.value = []
  showMaterialImportModal.value = true
  try {
    const res = await api.getStaticFileMaterialRegions()
    materialRegions.value = (res.data || []).sort((a, b) => { const order = { COUNTRY: 0, STATE: 1, CITY: 2 }; return (order[a.region_type] || 0) - (order[b.region_type] || 0) || a.name.localeCompare(b.name) })
    materialCurrentList.value = materialRegions.value
  } catch (e) { message.error(t('views.statistic-center.message_cn_bbb8fde2')) }
}

function onMaterialRegionClick(region) { materialBreadcrumb.value.push({ id: region.id, name: region.name }); loadMaterialChildren(region.id) }
async function loadMaterialChildren(regionId) {
  try { const res = await api.getStaticFileMaterialsByRegion({ region_id: regionId, page: 1, page_size: 500 }); materialCurrentList.value = (res.data || []).map(m => ({ ...m, _type: 'material' })) }
  catch (e) { message.error(t('views.statistic-center.message_cn_934bcb9c')) }
}
function onMaterialBreadcrumbClick(index) {
  materialBreadcrumb.value = materialBreadcrumb.value.slice(0, index)
  if (index === 0) materialCurrentList.value = materialRegions.value
  else { const last = materialBreadcrumb.value[materialBreadcrumb.value.length - 1]; if (last) loadMaterialChildren(last.id) }
}
function toggleMaterialSelect(id) { const idx = materialSelectedIds.value.indexOf(id); if (idx >= 0) materialSelectedIds.value.splice(idx, 1); else materialSelectedIds.value.push(id) }
function toggleAllMaterials() {
  const allIds = materialCurrentList.value.map(m => m.id)
  if (materialSelectedIds.value.length === allIds.length && allIds.length > 0) materialSelectedIds.value = []
  else materialSelectedIds.value = [...allIds]
}
async function handleMaterialImport() {
  if (!materialSelectedIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_8af38652')); return }
  loading.value = true; showMaterialImportModal.value = false
  try { const res = await api.importStaticFilesFromMaterial({ workspace_id: selectedWs.value.id, material_ids: [...materialSelectedIds.value] }); message.success(`导入完成：成功 ${res.data?.success_count || 0} 个`); await loadStaticFiles() }
  catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_fddcd7c6')) }
  loading.value = false
}

async function openStaticFileCopyToModal() {
  if (!selectedStaticFileIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_3c2412f9')); return }
  staticFileCopyToForm.value = { target_workspace_id: null }; showStaticFileCopyToModal.value = true
  try { const res = await api.getWorkspaceList({ page: 1, page_size: 9999 }); staticFileCopyToWorkspaces.value = (res.data || []).filter(w => w.id !== selectedWs.value.id).map(w => ({ label: w.name, value: w.id })) } catch (e) {}
}
async function handleStaticFileCopyToWorkspace() {
  if (!staticFileCopyToForm.value.target_workspace_id) { message.warning(t('views.statistic-center.placeholder_cn_946eef8d')); return }
  loading.value = true; showStaticFileCopyToModal.value = false
  try { const res = await api.copyStaticFileRecords({ file_ids: [...selectedStaticFileIds.value], target_workspace_id: staticFileCopyToForm.value.target_workspace_id }); message.success(res.msg || `成功复制 ${res.data?.success_count || 0} 个文件`) }
  catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_5154ae17')) }
  loading.value = false
}

function openBaseUrlModal() { baseUrlForm.value = { base_url: staticFileBaseUrl.value }; showBaseUrlModal.value = true }
async function handleBaseUrlSubmit() {
  try { const res = await api.setStaticFileBaseUrl({ base_url: baseUrlForm.value.base_url.trim() }); staticFileBaseUrl.value = res.data?.base_url || baseUrlForm.value.base_url.trim(); message.success(t('views.statistic-center.label_cn_df261b91')); showBaseUrlModal.value = false }
  catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_930442e2')) }
}

const _originalSelectWorkspace = selectWorkspace
selectWorkspace = async function(ws) { await _originalSelectWorkspace(ws); await loadStaticFiles(); await loadDatabaseDocs() }

// ── 数据库数据状态 ──
const databaseDocs = ref([])
const selectedDatabaseDocIds = ref([])
const dbLoading = ref(false)

const showMySQLModal = ref(false)
const mysqlForm = ref({ host: '127.0.0.1', port: 3306, user: 'root', password: '', database: '' })
const mysqlTables = ref([])
const mysqlTested = ref(false)
const mysqlTesting = ref(false)
const mysqlSelectedTables = ref([])

const showSQLiteModal = ref(false)
const sqliteFilePath = ref('')
const sqliteFileName = ref('')
const sqliteTables = ref([])
const sqliteUploading = ref(false)
const sqliteSelectedTables = ref([])

const showPixelModal = ref(false)
const pixelAccounts = ref([])
const pixelForm = ref({ pixel_account_id: null, table_name: '', table_label: '' })
const pixelTables = ref([])

const showRoadNetworkModal = ref(false)
const roadNetworkRegions = ref([])
const roadNetworkForm = ref({ region_id: null })
const roadNetworks = ref([])
const roadNetworkSelected = ref([])

const showCopyToModal = ref(false)
const copyToWorkspaces = ref([])
const copyToForm = ref({ target_workspace_id: null })

async function loadDatabaseDocs() {
  if (!selectedWs.value) return
  try {
    const res = await api.getDocumentList({ workspace_id: selectedWs.value.id, source_type: 'original' })
    databaseDocs.value = (res.data || []).filter(d => d.import_source && ['mysql', 'sqlite', 'pixel', 'road_network'].includes(d.import_source))
  } catch (e) {}
}

function toggleDatabaseDocSelect(id) { const idx = selectedDatabaseDocIds.value.indexOf(id); if (idx >= 0) selectedDatabaseDocIds.value.splice(idx, 1); else selectedDatabaseDocIds.value.push(id) }
function toggleAllDatabaseDocs() { if (selectedDatabaseDocIds.value.length === databaseDocs.value.length) selectedDatabaseDocIds.value = []; else selectedDatabaseDocIds.value = databaseDocs.value.map(d => d.id) }

async function deleteDatabaseDoc(doc) { try { await api.deleteDocument({ document_id: doc.id }); await loadDatabaseDocs() } catch (e) { message.error(t('views.statistic-center.message_cn_acf0664a')) } }

async function batchExportDatabaseDocs() {
  if (!selectedDatabaseDocIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_f3328c38')); return }
  try { const res = await api.batchExportDocuments({ document_ids: [...selectedDatabaseDocIds.value] }); const blob = new Blob([res.data], { type: 'application/zip' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = t('views.statistic-center.label_cn_01470c4d'); a.click(); URL.revokeObjectURL(url); message.success(`已导出 ${selectedDatabaseDocIds.value.length} 条数据`) }
  catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_dd51ab50')) }
}

async function batchDeleteDatabaseDocs() {
  if (!selectedDatabaseDocIds.value.length) return
  try { await api.batchDeleteDocuments({ document_ids: [...selectedDatabaseDocIds.value] }); message.success(`已删除 ${selectedDatabaseDocIds.value.length} 条数据`); selectedDatabaseDocIds.value = []; await loadDatabaseDocs() }
  catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_acf0664a')) }
}

async function openCopyToModal() {
  if (!selectedDatabaseDocIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_f3328c38')); return }
  copyToForm.value = { target_workspace_id: null }; showCopyToModal.value = true
  try { const res = await api.getWorkspaceList({ page: 1, page_size: 9999 }); copyToWorkspaces.value = (res.data || []).filter(w => w.id !== selectedWs.value.id).map(w => ({ label: w.name, value: w.id })) } catch (e) {}
}

async function handleCopyToWorkspace() {
  if (!copyToForm.value.target_workspace_id) { message.warning(t('views.statistic-center.placeholder_cn_946eef8d')); return }
  dbLoading.value = true; showCopyToModal.value = false
  try { const res = await api.copyToWorkspace({ target_workspace_id: copyToForm.value.target_workspace_id, document_ids: [...selectedDatabaseDocIds.value] }); message.success(res.msg || `成功复制 ${res.data?.documents || 0} 项数据`) }
  catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_5154ae17')) }
  dbLoading.value = false
}

// ── MySQL ──
function openMySQLModal() { mysqlForm.value = { host: '127.0.0.1', port: 3306, user: 'root', password: '', database: '' }; mysqlTables.value = []; mysqlTested.value = false; mysqlSelectedTables.value = []; showMySQLModal.value = true }

async function testMySQL() {
  if (!mysqlForm.value.host || !mysqlForm.value.database) { message.warning(t('views.statistic-center.placeholder_cn_8242c2cd')); return }
  mysqlTesting.value = true; mysqlTested.value = false
  try { const res = await api.testMySQLConnection(mysqlForm.value); mysqlTables.value = (res.data?.tables || []).map(t => ({ ...t, selected: false })); mysqlTested.value = true; message.success(res.msg || `连接成功，共 ${mysqlTables.value.length} 个表`) }
  catch (e) { message.error(e?.response?.data?.msg || e?.message || t('views.statistic-center.message_cn_0745fc09')) }
  mysqlTesting.value = false
}

async function importMySQL() {
  const selected = mysqlTables.value.filter(t => t.selected).map(t => t.name)
  if (!selected.length) { message.warning(t('views.statistic-center.placeholder_cn_ffd60b41')); return }
  if (!selectedWs.value) return
  dbLoading.value = true; showMySQLModal.value = false
  try { const res = await api.importMySQLTables({ workspace_id: selectedWs.value.id, ...mysqlForm.value, tables: selected }); message.success(res.msg || `成功导入 ${selected.length} 个表`); await loadDatabaseDocs() }
  catch (e) { message.error(e?.response?.data?.msg || e?.message || t('views.statistic-center.message_cn_fddcd7c6')) }
  dbLoading.value = false
}

// ── SQLite ──
function openSQLiteModal() { sqliteFilePath.value = ''; sqliteFileName.value = ''; sqliteTables.value = []; sqliteSelectedTables.value = []; showSQLiteModal.value = true }

async function handleSQLiteUpload({ file }) {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_aac7e445')); return }
  sqliteUploading.value = true
  try { const res = await api.uploadSQLiteFile(selectedWs.value.id, file.file); sqliteFilePath.value = res.data.file_path; sqliteFileName.value = res.data.file_name; sqliteTables.value = (res.data.tables || []).map(t => ({ ...t, selected: false })); message.success(res.msg || `解析成功，共 ${sqliteTables.value.length} 个表`) }
  catch (e) { message.error(e?.response?.data?.msg || e?.message || t('views.statistic-center.message_cn_5348dcac')) }
  sqliteUploading.value = false
}

async function importSQLite() {
  const selected = sqliteTables.value.filter(t => t.selected).map(t => t.name)
  if (!selected.length) { message.warning(t('views.statistic-center.placeholder_cn_ffd60b41')); return }
  if (!selectedWs.value) return
  dbLoading.value = true; showSQLiteModal.value = false
  try { const res = await api.importSQLiteTables({ workspace_id: selectedWs.value.id, file_path: sqliteFilePath.value, tables: selected }); message.success(res.msg || `成功导入 ${selected.length} 个表`); await loadDatabaseDocs() }
  catch (e) { message.error(e?.response?.data?.msg || e?.message || t('views.statistic-center.message_cn_fddcd7c6')) }
  dbLoading.value = false
}

// ── 像素数据 ──
async function openPixelModal() {
  pixelForm.value = { pixel_account_id: null, table_name: '', table_label: '' }; pixelTables.value = []; showPixelModal.value = true
  try { const res = await api.getPixelAccountsForImport(); pixelAccounts.value = (res.data || []).map(a => ({ label: a.label || a.username, value: a.id })) }
  catch (e) { message.error(t('views.statistic-center.message_cn_5bbfb780')) }
}

async function onPixelAccountChange(accountId) {
  pixelForm.value.table_name = ''; pixelForm.value.table_label = ''; pixelTables.value = []
  if (!accountId) return
  try { const res = await api.getPixelTablesForImport({ pixel_account_id: accountId }); pixelTables.value = (res.data || []).map(t => ({ label: t.label || t.description, value: t.name, description: t.description })) }
  catch (e) { message.error(t('views.statistic-center.message_cn_dfe3f39d')) }
}

async function importPixel() {
  if (!pixelForm.value.pixel_account_id || !pixelForm.value.table_name) { message.warning(t('views.statistic-center.placeholder_cn_2162302a')); return }
  if (!selectedWs.value) return
  dbLoading.value = true; showPixelModal.value = false
  try { const res = await api.importPixelTable({ ...pixelForm.value, workspace_id: selectedWs.value.id }); message.success(res.msg || t('views.statistic-center.message_cn_b6d16a81')); await loadDatabaseDocs() }
  catch (e) { message.error(e?.response?.data?.msg || e?.message || t('views.statistic-center.message_cn_fddcd7c6')) }
  dbLoading.value = false
}

// ── 路网数据 ──
async function openRoadNetworkModal() {
  roadNetworkForm.value = { region_id: null }; roadNetworks.value = []; roadNetworkSelected.value = []; showRoadNetworkModal.value = true
  try { const res = await api.getRoadNetworkRegionsForImport(); roadNetworkRegions.value = (res.data || []).map(r => ({ label: r.label || r.name, value: r.id, network_count: r.network_count })) }
  catch (e) { message.error(t('views.statistic-center.message_cn_a495eb1d')) }
}

async function onRoadNetworkRegionChange(regionId) {
  roadNetworks.value = []; roadNetworkSelected.value = []
  if (!regionId) return
  try { const res = await api.getRoadNetworkListForImport({ region_id: regionId }); roadNetworks.value = (res.data || []).map(n => ({ ...n, selected: false })) }
  catch (e) { message.error(t('views.statistic-center.message_cn_52191929')) }
}

function toggleAllRoadNetworks() { if (!roadNetworks.value.length) return; const allSelected = roadNetworks.value.every(n => n.selected); roadNetworks.value.forEach(n => n.selected = !allSelected) }

async function importRoadNetwork() {
  const selected = roadNetworks.value.filter(n => n.selected).map(n => n.id)
  if (!selected.length) { message.warning(t('views.statistic-center.placeholder_cn_79e1b67e')); return }
  if (!selectedWs.value) return
  dbLoading.value = true; showRoadNetworkModal.value = false
  try { const res = await api.importRoadNetworkStats({ workspace_id: selectedWs.value.id, region_id: roadNetworkForm.value.region_id, road_network_ids: selected }); message.success(res.msg || `成功导入 ${res.data?.length || selected.length} 个路网统计`); await loadDatabaseDocs() }
  catch (e) { message.error(e?.response?.data?.msg || e?.message || t('views.statistic-center.message_cn_fddcd7c6')) }
  dbLoading.value = false
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
          <TheIcon icon="material-symbols:add" :size="20" class="mr-2" />{{ t('views.statistic-center.label_cn_9cb11943') }}
        </NButton>
        <NList hoverable clickable :show-divider="false">
          <NListItem
            v-for="(ws, idx) in workspaces" :key="ws.id"
            :class="{ 'bg-blue-50 dark:bg-blue-900': selectedWs?.id === ws.id }"
            style="border-radius: 8px; margin-bottom: 4px; cursor: pointer"
            @click="selectWorkspace(ws)"
          >
            <div class="flex items-center gap-3 flex-1 min-w-0">
              <div class="ws-avatar" :style="{ background: wsAccent(idx) }">
                {{ ws.name.charAt(0) }}
              </div>
              <div class="flex flex-col flex-1 min-w-0">
                <span class="font-medium text-base truncate">{{ ws.name }}</span>
                <span class="text-gray-400 text-sm">{{ ws.updated_at }}</span>
              </div>
            </div>
          </NListItem>
        </NList>
        <div v-if="!workspaces.length" class="text-center text-gray-400 py-10">{{ t('views.statistic-center.label_cn_c3e99070') }}</div>
      </NSpace>
    </NLayoutSider>

    <!-- ── 右侧数据源区域 ── -->
    <NLayoutContent content-style="padding: 16px">
      <NSpin :show="loading">
        <div v-if="!selectedWs" class="flex items-center justify-center h-full text-gray-400 text-lg">
          {{ t('views.statistic-center.label_cn_aba2706f') }}
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
                <TheIcon icon="material-symbols:edit" :size="18" class="mr-1" />{{ t('views.statistic-center.label_cn_24d67862') }}
              </NButton>
              <NPopconfirm @positive-click="deleteWorkspace">
                <template #trigger>
                  <NButton size="small" type="error">
                    <TheIcon icon="material-symbols:delete-outline" :size="18" class="mr-1" />{{ t('views.statistic-center.label_cn_2f4aaddd') }}
                  </NButton>
                </template>
                {{ t('views.statistic-center.label_cn_9f1f93b6') }}
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
                        <div class="text-base font-semibold text-gray-700 dark:text-gray-300 mb-1">{{ t('views.statistic-center.label_cn_b26de1f0') }}</div>
                        <div class="text-sm text-gray-400 mb-3">{{ t('views.statistic-center.label_cn_b642b167') }}</div>
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

                <!-- 左右双栏布局 -->
                <div class="flex gap-3 flex-1" style="min-height: 0">
                  <!-- ── 左栏：原始表格 ── -->
                  <div class="flex-1 flex flex-col" style="min-width: 0">
                    <div class="flex items-center justify-between mb-2 px-1">
                      <div class="flex items-center gap-2">
                        <TheIcon icon="material-symbols:description" :size="20" class="text-blue-500" />
                        <span class="font-semibold text-base">{{ t('views.statistic-center.label_07c80637') }}</span>
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
                          <TheIcon icon="material-symbols:compare-arrows" :size="16" class="mr-1" />{{ t('views.statistic-center.label_5d47dd27') }}
                        </NButton>
                        <NButton size="small" type="primary" :disabled="!selectedAnalysisIds.length" @click="batchExportAnalyses">
                          <TheIcon icon="material-symbols:download" :size="16" class="mr-1" />导出({{ selectedAnalysisIds.length }})
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
                        <div class="text-base font-semibold text-gray-700 dark:text-gray-300 mb-1">{{ t('views.statistic-center.label_cn_c485b330') }}</div>
                        <div class="text-sm text-gray-400 mb-3">{{ t('views.statistic-center.label_cn_b642b167') }}</div>
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
                        <div class="text-base font-semibold text-purple-600 dark:text-purple-400 mb-3">{{ t('views.statistic-center.label_cn_d790356c') }}</div>
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
                        <span class="font-semibold text-base">{{ t('views.statistic-center.label_cn_d3182537') }}</span>
                        <NTag size="small" :bordered="false" type="info">{{ documents.length }}</NTag>
                      </div>
                      <NSpace v-if="documents.length" size="small">
                        <NButton size="small" type="primary" :disabled="!selectedDocIds.length" @click="openDocAnalyze">
                          <TheIcon icon="material-symbols:psychology" :size="16" class="mr-1" />AI分析({{ selectedDocIds.length }})
                        </NButton>
                        <NPopconfirm @positive-click="batchDeleteDocs" :disabled="!selectedDocIds.length">
                          <template #trigger>
                            <NButton size="small" type="warning" :disabled="!selectedDocIds.length">
                              <TheIcon icon="material-symbols:delete-outline" :size="16" />{{ t('views.statistic-center.label_cn_2f4aaddd') }}
                            </NButton>
                          </template>
                          确认删除选中的 {{ selectedDocIds.length }} 个文档？
                        </NPopconfirm>
                        <NPopconfirm @positive-click="clearAllDocs">
                          <template #trigger>
                            <NButton size="small" type="error">
                              <TheIcon icon="material-symbols:delete-sweep" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_288f0c40') }}
                            </NButton>
                          </template>
                          {{ t('views.statistic-center.label_cn_cf371c20') }}
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
                          <div class="text-base">{{ t('views.statistic-center.label_cn_ebb19d29') }}</div>
                          <div class="text-sm mt-1">{{ t('views.statistic-center.label_cn_53569a44') }}</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- ── 右栏：AI分析文档 ── -->
                  <div class="flex-1 flex flex-col" style="min-width: 0">
                    <div class="flex items-center justify-between mb-2 px-1">
                      <div class="flex items-center gap-2">
                        <TheIcon icon="material-symbols:analytics" :size="20" class="text-green-500" />
                        <span class="font-semibold text-base">{{ t('views.statistic-center.label_cn_c57e8ae8') }}</span>
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
                          <div class="text-base">{{ t('views.statistic-center.label_cn_01a41f3d') }}</div>
                          <div class="text-sm mt-1">{{ t('views.statistic-center.label_cn_e1f6cab2') }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- ═══════════════════════════════════════════
                   数据库数据 Tab
                   ═══════════════════════════════════════════ -->
              <div v-else-if="tab.name === 'database'" class="flex-1 flex flex-col" style="min-height: 0">
                <!-- 工具栏 -->
                <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
                  <div class="flex items-center gap-2">
                    <TheIcon icon="material-symbols:database" :size="20" class="text-blue-500" />
                    <span class="font-semibold text-base">{{ t('views.statistic-center.label_cn_c274dc20') }}</span>
                    <NTag size="small" :bordered="false" type="info">{{ databaseDocs.length }}</NTag>
                  </div>
                  <NSpace size="small">
                    <NButton size="small" type="primary" :disabled="!selectedDatabaseDocIds.length" @click="batchExportDatabaseDocs">
                      <TheIcon icon="material-symbols:download" :size="16" class="mr-1" />导出({{ selectedDatabaseDocIds.length }})
                    </NButton>
                    <NPopconfirm @positive-click="batchDeleteDatabaseDocs" :disabled="!selectedDatabaseDocIds.length">
                      <template #trigger><NButton size="small" type="warning" :disabled="!selectedDatabaseDocIds.length"><TheIcon icon="material-symbols:delete-outline" :size="16" />删除({{ selectedDatabaseDocIds.length }})</NButton></template>
                      确认删除选中的 {{ selectedDatabaseDocIds.length }} 条数据库数据？
                    </NPopconfirm>
                    <NButton size="small" :disabled="!selectedDatabaseDocIds.length" @click="openCopyToModal">
                      <TheIcon icon="material-symbols:content-copy" :size="16" class="mr-1" />复制到
                    </NButton>
                  </NSpace>
                </div>

                <!-- 导入按钮 -->
                <div class="flex flex-wrap items-center gap-2 mb-4">
                  <NButton size="small" @click="openMySQLModal"><TheIcon icon="material-symbols:cloud-sync" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_00fb0e78') }}</NButton>
                  <NButton size="small" @click="openSQLiteModal"><TheIcon icon="material-symbols:upload-file" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_827cdec1') }}</NButton>
                  <NButton size="small" @click="openPixelModal"><TheIcon icon="material-symbols:satellite" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_40909c62') }}</NButton>
                  <NButton size="small" @click="openRoadNetworkModal"><TheIcon icon="material-symbols:route" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_63b03fa8') }}</NButton>
                </div>

                <!-- 数据列表 -->
                <div class="flex-1 overflow-auto rounded-lg border border-gray-100 bg-gray-50/50" style="min-height: 0">
                  <div v-if="databaseDocs.length" class="p-2">
                    <div class="flex items-center gap-2 mb-2 px-1">
                      <NCheckbox size="small" :checked="selectedDatabaseDocIds.length === databaseDocs.length && databaseDocs.length > 0" :indeterminate="selectedDatabaseDocIds.length > 0 && selectedDatabaseDocIds.length < databaseDocs.length" @update:checked="toggleAllDatabaseDocs" />
                      <span class="text-xs text-gray-400">已选 {{ selectedDatabaseDocIds.length }} / {{ databaseDocs.length }}</span>
                    </div>
                    <div class="grid gap-2">
                      <div v-for="d in databaseDocs" :key="d.id" class="bg-white rounded-lg border border-gray-100 p-3">
                        <div class="flex items-center justify-between">
                          <div class="flex items-center gap-3 min-w-0 flex-1">
                            <NCheckbox size="small" :checked="selectedDatabaseDocIds.includes(d.id)" @update:checked="() => toggleDatabaseDocSelect(d.id)" class="flex-shrink-0" />
                            <TheIcon
                              :icon="d.import_source === 'mysql' ? 'material-symbols:cloud' : d.import_source === 'sqlite' ? 'material-symbols:hard-drive' : d.import_source === 'pixel' ? 'material-symbols:satellite' : 'material-symbols:route'"
                              :size="18" class="text-blue-500 flex-shrink-0"
                            />
                            <div class="min-w-0 flex-1">
                              <div class="text-sm font-medium truncate">{{ d.name }}</div>
                              <div class="flex items-center gap-2 text-xs text-gray-400 mt-0.5 flex-wrap">
                                <NTag size="tiny" :bordered="false" :type="d.import_source === 'mysql' ? 'info' : d.import_source === 'sqlite' ? 'success' : d.import_source === 'pixel' ? 'warning' : 'default'">
                                  {{ d.import_source === 'mysql' ? 'MySQL' : d.import_source === 'sqlite' ? 'SQLite' : d.import_source === 'pixel' ? t('views.statistic-center.label_cn_2374026f') : t('views.statistic-center.label_cn_75ec0658') }}
                                </NTag>
                                <span v-if="d.char_count">{{ d.char_count?.toLocaleString() }} 字符</span>
                                <span v-if="d.row_count">{{ d.row_count?.toLocaleString() }} 行</span>
                                <span v-if="d.file_size">{{ formatFileSize(d.file_size) }}</span>
                              </div>
                              <div v-if="d.source_table" class="text-xs text-gray-400 mt-0.5">源表: {{ d.source_table }}</div>
                              <div class="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
                                <span v-if="d.dump_date">dump: {{ d.dump_date?.slice(0, 10) }}</span>
                                <span v-if="d.source_last_updated">源更新: {{ d.source_last_updated?.slice(0, 10) }}</span>
                              </div>
                            </div>
                          </div>
                          <NSpace size="small" class="flex-shrink-0 ml-3">
                            <NButton size="tiny" quaternary @click="api.downloadDocument({ document_id: d.id }).then(r => { const blob = new Blob([r.data]); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = d.name; a.click(); URL.revokeObjectURL(url) })" :title="t('views.statistic-center.label_cn_f26ef914')">
                              <TheIcon icon="material-symbols:download" :size="18" />
                            </NButton>
                            <NPopconfirm @positive-click="deleteDatabaseDoc(d)">
                              <template #trigger><NButton size="tiny" type="error" quaternary><TheIcon icon="material-symbols:delete-outline" :size="18" /></NButton></template>
                            </NPopconfirm>
                          </NSpace>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-else class="flex items-center justify-center h-full text-gray-400 py-12">
                    <div class="text-center"><TheIcon icon="material-symbols:database" :size="48" class="mb-2 opacity-30" /><div class="text-base">暂无数据库导入数据</div><div class="text-sm mt-1">{{ t('views.statistic-center.label_cn_8ac56daa') }}</div></div>
                  </div>
                </div>
              </div>

              <!-- ═══════════════════════════════════════════
                   静态文件数据 Tab
                   ═══════════════════════════════════════════ -->
              <div v-else-if="tab.name === 'static-files'" class="flex-1 flex flex-col" style="min-height: 0">
                <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
                  <div class="flex items-center gap-2">
                    <TheIcon icon="material-symbols:folder" :size="20" class="text-blue-500" />
                    <NButton size="small" :type="staticFileSourceType === 'original' ? 'primary' : 'default'" @click="staticFileSourceType = 'original'; onStaticFileSourceTypeChange()">{{ t('views.statistic-center.label_cn_70ac56dc') }}</NButton>
                    <NButton size="small" :type="staticFileSourceType === 'ai_analysis' ? 'primary' : 'default'" @click="staticFileSourceType = 'ai_analysis'; onStaticFileSourceTypeChange()">{{ t('views.statistic-center.label_cn_907b787c') }}</NButton>
                    <NTag size="small" :bordered="false" type="info">{{ staticFiles.length }}</NTag>
                  </div>
                  <NSpace size="small">
                    <NButton v-if="staticFiles.length" size="small" type="primary" :disabled="!selectedStaticFileIds.length" @click="batchExportStaticFilesAction"><TheIcon icon="material-symbols:download" :size="16" class="mr-1" />导出({{ selectedStaticFileIds.length }})</NButton>
                    <NPopconfirm @positive-click="batchDeleteStaticFilesAction" :disabled="!selectedStaticFileIds.length">
                      <template #trigger><NButton size="small" type="warning" :disabled="!selectedStaticFileIds.length"><TheIcon icon="material-symbols:delete-outline" :size="16" />删除({{ selectedStaticFileIds.length }})</NButton></template>
                      确认删除已选中的 {{ selectedStaticFileIds.length }} 个文件？
                    </NPopconfirm>
                  </NSpace>
                </div>
                <div class="mb-4">
                  <NUpload ref="staticFileUploadRef" :show-file-list="false" :default-upload="false" accept="*" multiple @change="handleStaticFileUpload">
                    <NUploadDragger class="w-full" style="border-radius: 8px; --n-border-hover: 2px dashed #3b82f6">
                      <div class="flex flex-col items-center py-4">
                        <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center mb-2"><TheIcon icon="material-symbols:upload" :size="28" class="text-blue-500" /></div>
                        <div class="text-sm font-semibold text-gray-700">上传文件到{{ staticFileSourceType === 'original' ? t('views.statistic-center.label_cn_d3182537') : t('views.statistic-center.label_cn_c57e8ae8') }}目录</div>
                        <div class="text-xs text-gray-400 mt-0.5">{{ t('views.statistic-center.label_cn_fef7540f') }}</div>
                      </div>
                    </NUploadDragger>
                  </NUpload>
                </div>
                <div class="flex flex-wrap items-center gap-2 mb-4">
                  <NButton size="small" @click="openCVModal" :disabled="!selectedStaticFileIds.length"><TheIcon icon="material-symbols:tune" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_cedfaa94') }}</NButton>
                  <NButton size="small" @click="openAIModal" :disabled="!selectedStaticFileIds.length"><TheIcon icon="material-symbols:auto-awesome" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_98264bd9') }}</NButton>
                  <NButton size="small" @click="handleOCRExtract" :disabled="!selectedStaticFileIds.length"><TheIcon icon="material-symbols:text-scan" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_0ff045c8') }}</NButton>
                  <NButton size="small" @click="openMaterialImportModal"><TheIcon icon="material-symbols:drive-folder-upload" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_f747d2cc') }}</NButton>
                  <NButton size="small" :disabled="!selectedStaticFileIds.length" @click="openStaticFileCopyToModal"><TheIcon icon="material-symbols:content-copy" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_a9ac3f71') }}</NButton>
                  <NButton size="small" @click="openBaseUrlModal"><TheIcon icon="material-symbols:link" :size="16" class="mr-1" />BaseUrl</NButton>
                </div>
                <div class="flex-1 flex gap-3" style="min-height: 0">
                  <div class="flex flex-col" :style="{ width: selectedStaticFile ? '55%' : '100%', minWidth: 0, transition: 'width 0.2s' }" style="min-height: 0">
                    <div class="flex items-center gap-2 mb-2 px-1">
                      <NCheckbox size="small" :checked="selectedStaticFileIds.length === staticFiles.length && staticFiles.length > 0" :indeterminate="selectedStaticFileIds.length > 0 && selectedStaticFileIds.length < staticFiles.length" @update:checked="toggleAllStaticFiles" />
                      <span class="text-xs text-gray-400">已选 {{ selectedStaticFileIds.length }} / {{ staticFiles.length }}</span>
                    </div>
                    <div class="flex-1 overflow-auto rounded-lg border border-gray-100 bg-gray-50/50" style="min-height: 0">
                      <div v-if="staticFiles.length" class="p-2 grid gap-2">
                        <div v-for="f in staticFiles" :key="f.id" class="bg-white rounded-lg border p-3 cursor-pointer hover:shadow-sm transition-shadow" :class="{ 'border-blue-400 bg-blue-50/50': selectedStaticFileIds.includes(f.id), 'border-gray-100': !selectedStaticFileIds.includes(f.id) }" @click="onStaticFileRowClick(f)">
                          <div class="flex items-center justify-between">
                            <div class="flex items-center gap-3 min-w-0 flex-1">
                              <NCheckbox size="small" :checked="selectedStaticFileIds.includes(f.id)" @update:checked="() => toggleStaticFileSelect(f.id)" class="flex-shrink-0" @click.stop />
                              <TheIcon :icon="f.is_image ? 'material-symbols:image' : 'material-symbols:description'" :size="20" :class="f.is_image ? 'text-green-500' : 'text-blue-500'" class="flex-shrink-0" />
                              <div class="min-w-0 flex-1">
                                <div class="text-sm font-medium truncate" :title="f.name">{{ f.name }}</div>
                                <div class="flex items-center gap-2 text-xs text-gray-400 mt-0.5">
                                  <span v-if="f.file_size">{{ formatFileSize(f.file_size) }}</span>
                                  <span v-if="f.is_image && f.width">{{ formatResolution(f.width, f.height) }}</span>
                                  <span v-if="f.format_type">{{ f.format_type }}</span>
                                </div>
                              </div>
                            </div>
                            <NSpace size="small" class="flex-shrink-0 ml-2" @click.stop>
                              <NButton size="tiny" quaternary @click="copyShortLink(f)" :title="t('views.statistic-center.label_cn_0ed3d703')"><TheIcon icon="material-symbols:link" :size="16" /></NButton>
                              <NButton size="tiny" quaternary @click="downloadStaticFileItem(f)" :title="t('views.statistic-center.label_cn_f26ef914')"><TheIcon icon="material-symbols:download" :size="16" /></NButton>
                              <NPopconfirm @positive-click="deleteStaticFileItem(f)"><template #trigger><NButton size="tiny" type="error" quaternary><TheIcon icon="material-symbols:delete-outline" :size="16" /></NButton></template></NPopconfirm>
                            </NSpace>
                          </div>
                        </div>
                      </div>
                      <div v-else class="flex items-center justify-center h-full text-gray-400 py-12">
                        <div class="text-center"><TheIcon icon="material-symbols:folder-open" :size="48" class="mb-2 opacity-30" /><div class="text-base">暂无文件</div><div class="text-sm mt-1">上传文件到{{ staticFileSourceType === 'original' ? t('views.statistic-center.label_cn_d3182537') : t('views.statistic-center.label_cn_c57e8ae8') }}目录</div></div>
                      </div>
                    </div>
                  </div>
                  <div v-if="selectedStaticFile" class="flex-1 flex flex-col rounded-lg border border-gray-200 bg-white overflow-auto" style="min-width: 0; min-height: 0">
                    <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-gray-50/70 sticky top-0 z-10">
                      <div class="flex items-center gap-2.5 min-w-0 flex-1">
                        <div class="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" :class="selectedStaticFile.is_image ? 'bg-green-100 text-green-600' : 'bg-blue-100 text-blue-600'"><TheIcon :icon="selectedStaticFile.is_image ? 'material-symbols:image' : 'material-symbols:description'" :size="20" /></div>
                        <div class="min-w-0"><div class="text-sm font-semibold truncate">{{ selectedStaticFile.name }}</div><div class="flex items-center gap-1.5 text-xs text-gray-400 mt-0.5"><span>{{ selectedStaticFile.format_type || 'FILE' }}</span><span>·</span><span>{{ formatFileSize(selectedStaticFile.file_size) }}</span></div></div>
                      </div>
                      <NSpace size="small" class="flex-shrink-0">
                        <NButton size="tiny" quaternary @click="downloadStaticFileItem(selectedStaticFile)" :title="t('views.statistic-center.label_cn_f26ef914')"><TheIcon icon="material-symbols:download" :size="18" /></NButton>
                        <NButton size="tiny" quaternary @click="copyShortLink(selectedStaticFile)" :title="t('views.statistic-center.label_cn_0ed3d703')"><TheIcon icon="material-symbols:link" :size="18" /></NButton>
                        <NButton v-if="selectedStaticFile.is_image" size="tiny" quaternary :title="t('views.statistic-center.label_cn_80fb2db8')" @click="window.open(`/api/sf/${selectedStaticFile.short_url_token}`, '_blank')"><TheIcon icon="material-symbols:open-in-new" :size="18" /></NButton>
                        <NButton size="tiny" quaternary @click="selectedStaticFile = null" :title="t('views.statistic-center.label_cn_2f3a89be')"><TheIcon icon="material-symbols:close" :size="18" /></NButton>
                      </NSpace>
                    </div>
                    <div v-if="selectedStaticFile.is_image" class="border-b border-gray-100 bg-gray-100/50">
                      <div class="flex items-center justify-center p-3" style="min-height: 180px; max-height: 380px">
                        <img :src="`/api/sf/${selectedStaticFile.short_url_token}`" :alt="selectedStaticFile.name" class="max-w-full max-h-full object-contain rounded shadow-sm" style="max-height: 360px" @error="e => { e.target.style.display = 'none' }" />
                      </div>
                      <div class="flex items-center justify-center gap-3 px-4 pb-2 text-xs text-gray-400"><span v-if="selectedStaticFile.width">{{ formatResolution(selectedStaticFile.width, selectedStaticFile.height) }}</span><span v-if="selectedStaticFile.color_mode">{{ selectedStaticFile.color_mode }}</span><span v-if="selectedStaticFile.dpi">{{ selectedStaticFile.dpi }} DPI</span></div>
                    </div>
                    <div v-else class="flex flex-col items-center justify-center py-10 border-b border-gray-100 bg-gray-50/30"><div class="w-20 h-20 rounded-2xl bg-blue-100 flex items-center justify-center mb-3"><TheIcon icon="material-symbols:description" :size="44" class="text-blue-500" /></div><span class="text-sm text-gray-500">{{ selectedStaticFile.format_type || '文件' }}</span></div>
                    <div class="p-4 space-y-4">
                      <div>
                        <div class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2.5">{{ t('views.statistic-center.label_cn_43a262a5') }}</div>
                        <div class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                          <div class="flex items-center gap-2"><TheIcon icon="material-symbols:description" :size="14" class="text-gray-400 flex-shrink-0" /><span class="text-gray-400 flex-shrink-0 text-xs">名称</span><span class="truncate text-gray-700">{{ selectedStaticFile.file_name }}</span></div>
                          <div class="flex items-center gap-2"><TheIcon icon="material-symbols:database" :size="14" class="text-gray-400 flex-shrink-0" /><span class="text-gray-400 flex-shrink-0 text-xs">大小</span><span class="text-gray-700">{{ formatFileSize(selectedStaticFile.file_size) }}</span></div>
                          <div v-if="selectedStaticFile.is_image" class="flex items-center gap-2"><TheIcon icon="material-symbols:aspect-ratio" :size="14" class="text-gray-400 flex-shrink-0" /><span class="text-gray-400 flex-shrink-0 text-xs">分辨率</span><span class="text-gray-700">{{ formatResolution(selectedStaticFile.width, selectedStaticFile.height) }}</span></div>
                          <div v-if="selectedStaticFile.format_type" class="flex items-center gap-2"><TheIcon icon="material-symbols:image" :size="14" class="text-gray-400 flex-shrink-0" /><span class="text-gray-400 flex-shrink-0 text-xs">格式</span><span class="text-gray-700">{{ selectedStaticFile.format_type }}</span></div>
                          <div v-if="selectedStaticFile.color_mode" class="flex items-center gap-2"><TheIcon icon="material-symbols:palette" :size="14" class="text-gray-400 flex-shrink-0" /><span class="text-gray-400 flex-shrink-0 text-xs">色彩</span><span class="text-gray-700">{{ selectedStaticFile.color_mode }}</span></div>
                          <div v-if="selectedStaticFile.bit_depth" class="flex items-center gap-2"><TheIcon icon="material-symbols:layers" :size="14" class="text-gray-400 flex-shrink-0" /><span class="text-gray-400 flex-shrink-0 text-xs">位深</span><span class="text-gray-700">{{ selectedStaticFile.bit_depth }} bit</span></div>
                          <div v-if="selectedStaticFile.dpi" class="flex items-center gap-2"><TheIcon icon="material-symbols:grid-on" :size="14" class="text-gray-400 flex-shrink-0" /><span class="text-gray-400 flex-shrink-0 text-xs">DPI</span><span class="text-gray-700">{{ selectedStaticFile.dpi }}</span></div>
                          <div v-if="selectedStaticFile.source" class="flex items-center gap-2"><TheIcon icon="material-symbols:upload" :size="14" class="text-gray-400 flex-shrink-0" /><span class="text-gray-400 flex-shrink-0 text-xs">来源</span><span class="text-gray-700">{{ selectedStaticFile.source }}</span></div>
                          <div class="flex items-center gap-2"><TheIcon icon="material-symbols:calendar-today" :size="14" class="text-gray-400 flex-shrink-0" /><span class="text-gray-400 flex-shrink-0 text-xs">时间</span><span class="text-gray-700">{{ selectedStaticFile.created_at?.slice(0, 16) }}</span></div>
                        </div>
                      </div>
                      <div>
                        <div class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">{{ t('views.statistic-center.label_cn_738f3dc4') }}</div>
                        <div class="flex items-center gap-2"><code class="flex-1 text-xs bg-gray-100 px-2.5 py-1.5 rounded-md truncate text-gray-600 select-all">{{ getStaticFileShortUrl(selectedStaticFile) }}</code><NButton size="tiny" secondary @click="copyShortLink(selectedStaticFile)"><TheIcon icon="material-symbols:content-copy" :size="14" /></NButton></div>
                      </div>
                      <div v-if="selectedStaticFile.exif_data && Object.keys(selectedStaticFile.exif_data).length">
                        <div class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">{{ t('views.statistic-center.label_cn_5a1d8e9f') }}</div>
                        <div class="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs max-h-44 overflow-auto pr-1">
                          <div v-for="(v, k) in exifPreview(selectedStaticFile.exif_data)" :key="k" class="flex items-start gap-1.5"><span class="text-gray-400 flex-shrink-0">{{ k }}</span><span class="text-gray-600 truncate" :title="v">{{ v }}</span></div>
                        </div>
                      </div>
                      <div v-if="selectedStaticFile.description">
                        <div class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">{{ t('views.statistic-center.label_cn_34681d7f') }}</div>
                        <p class="text-sm text-gray-600 whitespace-pre-wrap leading-relaxed bg-gray-50 rounded-lg p-3">{{ selectedStaticFile.description }}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </NTabPane>
          </NTabs>
        </div>
      </NSpin>
    </NLayoutContent>
  </NLayout>

  <!-- ── OpenCV 处理弹窗 ── -->
  <NModal v-model:show="showCVModal" :title="t('views.statistic-center.label_cn_65060ed5')" preset="card" style="width: 650px">
    <NForm label-placement="top">
      <NFormItem :label="t('views.statistic-center.label_cn_de9cc3dd')" required><NSelect :value="cvForm.operation" :options="Object.keys(cvOperations).map(k => ({ label: k, value: k }))" @update:value="onCVOperationChange" /></NFormItem>
      <template v-if="cvForm.operation === 'resize'">
        <NFormItem :label="t('views.statistic-center.label_cn_d66218b0')" required><NInputNumber :value="cvForm.params.width || 800" :min="1" :max="8000" @update:value="v => updateCVParam('width', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_026c0953')"><NInputNumber :value="cvForm.params.height || 0" :min="0" :max="8000" @update:value="v => updateCVParam('height', v)" /></NFormItem>
      </template>
      <template v-if="cvForm.operation === 'rotate'">
        <NFormItem :label="t('views.statistic-center.label_cn_0fdb4804')" required><NInputNumber :value="cvForm.params.angle || 90" :min="-360" :max="360" @update:value="v => updateCVParam('angle', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_05853d9c')"><NInputNumber :value="cvForm.params.scale || 1.0" :min="0.1" :max="3" :step="0.1" @update:value="v => updateCVParam('scale', v)" /></NFormItem>
      </template>
      <template v-if="cvForm.operation === 'crop'">
        <NFormItem :label="t('views.statistic-center.label_cn_ac7c8f8c')"><NInputNumber :value="cvForm.params.x || 0" :min="0" @update:value="v => updateCVParam('x', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_8d50f63f')"><NInputNumber :value="cvForm.params.y || 0" :min="0" @update:value="v => updateCVParam('y', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_c2847901')" required><NInputNumber :value="cvForm.params.width || 200" :min="1" @update:value="v => updateCVParam('width', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_c1df04ee')" required><NInputNumber :value="cvForm.params.height || 200" :min="1" @update:value="v => updateCVParam('height', v)" /></NFormItem>
      </template>
      <template v-if="cvForm.operation === 'flip'">
        <NFormItem :label="t('views.statistic-center.label_cn_e4e5b3af')"><NSelect :value="cvForm.params.direction ?? 1" :options="[{label:'垂直翻转 (0)',value:0},{label:'水平翻转 (1)',value:1},{label:'两者 (-1)',value:-1}]" @update:value="v => updateCVParam('direction', v)" /></NFormItem>
      </template>
      <template v-if="cvForm.operation === 'border'">
        <NFormItem :label="t('views.statistic-center.label_cn_af767b7e')"><NInputNumber :value="cvForm.params.top || 10" :min="0" @update:value="v => updateCVParam('top', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_3850a186')"><NInputNumber :value="cvForm.params.bottom || 10" :min="0" @update:value="v => updateCVParam('bottom', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_d2aff141')"><NInputNumber :value="cvForm.params.left || 10" :min="0" @update:value="v => updateCVParam('left', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_4d9c32c2')"><NInputNumber :value="cvForm.params.right || 10" :min="0" @update:value="v => updateCVParam('right', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_b7ef3e5b')"><NInput :value="cvForm.params.color || '#000000'" @update:value="v => updateCVParam('color', v)" /></NFormItem>
      </template>
      <template v-if="cvForm.operation === 'brightness'">
        <NFormItem :label="t('views.statistic-center.label_cn_74da6ec4')"><NSlider :value="cvForm.params.value ?? 1" :min="0" :max="3" :step="0.1" @update:value="v => updateCVParam('value', v)" /><span class="text-xs text-gray-400 ml-2">{{ cvForm.params.value ?? 1 }}</span></NFormItem>
      </template>
      <template v-if="cvForm.operation === 'contrast'">
        <NFormItem :label="t('views.statistic-center.label_cn_272bec28')"><NSlider :value="cvForm.params.value ?? 1" :min="0" :max="5" :step="0.1" @update:value="v => updateCVParam('value', v)" /><span class="text-xs text-gray-400 ml-2">{{ cvForm.params.value ?? 1 }}</span></NFormItem>
      </template>
      <template v-if="cvForm.operation === 'color_space'">
        <NFormItem :label="t('views.statistic-center.label_cn_7c9e228a')"><NSelect :value="cvForm.params.target || 'GRAY'" :options="[{label:'灰度(GRAY)',value:'GRAY'},{label:'RGB',value:'RGB'},{label:'HSV',value:'HSV'},{label:'LAB',value:'LAB'}]" @update:value="v => updateCVParam('target', v)" /></NFormItem>
      </template>
      <template v-if="cvForm.operation === 'blur'">
        <NFormItem :label="t('views.statistic-center.label_cn_16f23db3')"><NSelect :value="cvForm.params.type || 'gaussian'" :options="[{label:'高斯(gaussian)',value:'gaussian'},{label:'中值(median)',value:'median'},{label:'双边(bilateral)',value:'bilateral'}]" @update:value="v => updateCVParam('type', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_26a9c662')"><NInputNumber :value="cvForm.params.kernel_size || 5" :min="1" :max="31" @update:value="v => updateCVParam('kernel_size', v)" /></NFormItem>
      </template>
      <template v-if="cvForm.operation === 'morphology'">
        <NFormItem :label="t('views.statistic-center.label_cn_2b6bc0f2')"><NSelect :value="cvForm.params.operation || 'erode'" :options="[{label:'腐蚀(erode)',value:'erode'},{label:'膨胀(dilate)',value:'dilate'},{label:'开(open)',value:'open'},{label:'闭(close)',value:'close'}]" @update:value="v => updateCVParam('operation', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_c5237285')"><NInputNumber :value="cvForm.params.kernel_size || 3" :min="1" :max="15" @update:value="v => updateCVParam('kernel_size', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_0877fae0')"><NInputNumber :value="cvForm.params.iterations || 1" :min="1" :max="10" @update:value="v => updateCVParam('iterations', v)" /></NFormItem>
      </template>
      <template v-if="cvForm.operation === 'smooth'">
        <NFormItem :label="t('views.statistic-center.label_cn_ea340b9d')"><NSelect :value="cvForm.params.method || 'bilateral'" :options="[{label:'双边(bilateral)',value:'bilateral'},{label:'非局部均值(nlmeans)',value:'nlmeans'}]" @update:value="v => updateCVParam('method', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_4aa9877e')"><NInputNumber :value="cvForm.params.h || 10" :min="1" :max="100" @update:value="v => updateCVParam('h', v)" /></NFormItem>
      </template>
      <template v-if="cvForm.operation === 'histogram_eq'">
        <NFormItem :label="t('views.statistic-center.label_cn_ea340b9d')"><NSelect :value="cvForm.params.method || 'global'" :options="[{label:'全局(global)',value:'global'},{label:'CLAHE',value:'clahe'}]" @update:value="v => updateCVParam('method', v)" /></NFormItem>
        <NFormItem v-if="cvForm.params.method === 'clahe'" :label="t('views.statistic-center.label_cn_23f2e5f1')"><NInputNumber :value="cvForm.params.clip_limit || 2.0" :min="0.1" :max="10" :step="0.1" @update:value="v => updateCVParam('clip_limit', v)" /></NFormItem>
        <NFormItem v-if="cvForm.params.method === 'clahe'" :label="t('views.statistic-center.label_cn_405bbef3')"><NInputNumber :value="cvForm.params.tile_size || 8" :min="2" :max="32" @update:value="v => updateCVParam('tile_size', v)" /></NFormItem>
      </template>
      <template v-if="cvForm.operation === 'remove_bg'">
        <NFormItem :label="t('views.statistic-center.label_cn_ea340b9d')"><NSelect :value="cvForm.params.method || 'grabcut'" :options="[{label:'GrabCut',value:'grabcut'},{label:'阈值(threshold)',value:'threshold'}]" @update:value="v => updateCVParam('method', v)" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_e8ed49e9')"><NInputNumber :value="cvForm.params.margin || 10" :min="0" :max="100" @update:value="v => updateCVParam('margin', v)" /></NFormItem>
      </template>
      <div v-if="cvPreviewSrc" class="mt-2 rounded overflow-hidden border bg-gray-100 flex items-center justify-center" style="max-height: 200px"><img :src="cvPreviewSrc" class="max-w-full max-h-48 object-contain" /></div>
    </NForm>
    <template #footer><NSpace justify="end"><NButton @click="showCVModal = false">取消</NButton><NButton type="primary" :loading="loading" @click="handleCVSubmit">处理 ({{ selectedStaticFileIds.length }} 张)</NButton></NSpace></template>
  </NModal>

  <!-- ── AI 处理弹窗 ── -->
  <NModal v-model:show="showAIModal" :title="t('views.statistic-center.label_cn_5748192d')" preset="card" style="width: 560px">
    <NForm :model="aiForm" label-placement="top">
      <NFormItem :label="t('views.statistic-center.label_cn_9697e5cf')" required><NSelect v-model:value="aiForm.ai_proxy_id" :options="proxyOptions" :placeholder="t('views.statistic-center.placeholder_cn_523369d2')" /></NFormItem>
      <NFormItem :label="t('views.statistic-center.label_cn_c7dd72e6')"><NSelect v-model:value="aiForm.skill_id" :options="skillOptions" :placeholder="t('views.statistic-center.placeholder_cn_1b115fe6')" clearable /></NFormItem>
      <NFormItem :label="t('views.statistic-center.label_cn_47b7af95')"><NInput v-model:value="aiForm.prompt" type="textarea" :placeholder="t('views.statistic-center.placeholder_cn_9e8f7099')" /></NFormItem>
    </NForm>
    <template #footer><NSpace justify="end"><NButton @click="showAIModal = false">取消</NButton><NButton type="primary" :loading="loading" @click="handleAISubmit">AI 优化 ({{ selectedStaticFileIds.length }} 张)</NButton></NSpace></template>
  </NModal>

  <!-- ── 路网素材导入弹窗 ── -->
  <NModal v-model:show="showMaterialImportModal" :title="t('views.statistic-center.label_cn_f747d2cc')" preset="card" style="width: 700px; max-height: 80vh">
    <NBreadcrumb class="mb-3">
      <NBreadcrumbItem><span class="cursor-pointer text-blue-500" @click="onMaterialBreadcrumbClick(0)">{{ t('views.statistic-center.label_cn_5bf32f76') }}</span></NBreadcrumbItem>
      <NBreadcrumbItem v-for="(item, idx) in materialBreadcrumb" :key="item.id"><span v-if="idx < materialBreadcrumb.length - 1" class="cursor-pointer text-blue-500" @click="onMaterialBreadcrumbClick(idx + 1)">{{ item.name }}</span><span v-else>{{ item.name }}</span></NBreadcrumbItem>
    </NBreadcrumb>
    <div class="overflow-auto" style="max-height: 50vh">
      <div v-if="!materialBreadcrumb.length" class="grid gap-2">
        <div v-for="r in materialCurrentList" :key="r.id" class="flex items-center justify-between p-3 rounded-lg border border-gray-100 cursor-pointer hover:bg-blue-50/50" @click="onMaterialRegionClick(r)">
          <div class="flex items-center gap-2"><TheIcon icon="material-symbols:folder" :size="18" class="text-blue-500" /><span class="text-sm font-medium">{{ r.label || r.name }}</span></div>
          <NTag size="small" :bordered="false" type="info">{{ r.material_count }} 素材</NTag>
        </div>
        <div v-if="!materialCurrentList.length" class="text-center text-gray-400 py-8">{{ t('views.statistic-center.label_cn_12809aa9') }}</div>
      </div>
      <div v-else class="grid gap-2">
        <div class="flex items-center gap-2 px-1 mb-1">
          <NCheckbox size="small" :checked="materialSelectedIds.length === materialCurrentList.length && materialCurrentList.length > 0" :indeterminate="materialSelectedIds.length > 0 && materialSelectedIds.length < materialCurrentList.length" @update:checked="toggleAllMaterials" />
          <span class="text-xs text-gray-400">全选 (已选 {{ materialSelectedIds.length }} / {{ materialCurrentList.length }})</span>
        </div>
        <div v-for="m in materialCurrentList" :key="m.id" class="flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors" :class="{ 'border-blue-400 bg-blue-50/50': materialSelectedIds.includes(m.id), 'border-gray-100': !materialSelectedIds.includes(m.id) }" @click="toggleMaterialSelect(m.id)">
          <div class="flex items-center gap-3 min-w-0 flex-1"><NCheckbox size="small" :checked="materialSelectedIds.includes(m.id)" /><TheIcon icon="material-symbols:image" :size="20" class="text-green-500 flex-shrink-0" /><div class="min-w-0"><div class="text-sm font-medium truncate">{{ m.name }}</div><div class="text-xs text-gray-400">{{ formatFileSize(m.file_size) }} · {{ formatResolution(m.width, m.height) }}</div></div></div>
        </div>
        <div v-if="!materialCurrentList.length" class="text-center text-gray-400 py-8">{{ t('views.statistic-center.label_cn_26e9154b') }}</div>
      </div>
    </div>
    <template #footer><NSpace justify="end"><NButton @click="showMaterialImportModal = false">取消</NButton><NButton type="primary" :disabled="!materialSelectedIds.length" :loading="loading" @click="handleMaterialImport">导入 ({{ materialSelectedIds.length }})</NButton></NSpace></template>
  </NModal>

  <!-- ── 复制到工作区弹窗 ── -->
  <NModal v-model:show="showStaticFileCopyToModal" :title="t('views.statistic-center.label_cn_86919bd3')" preset="card" style="width: 480px">
    <div class="text-sm text-gray-500 mb-4">将选中的 {{ selectedStaticFileIds.length }} 个文件复制到另一工作区。<br/>仅创建数据库记录指向同一文件，不拷贝物理文件。</div>
    <NForm label-placement="top"><NFormItem :label="t('views.statistic-center.label_cn_9269a338')" required><NSelect v-model:value="staticFileCopyToForm.target_workspace_id" :options="staticFileCopyToWorkspaces" :placeholder="t('views.statistic-center.placeholder_cn_96d6caf0')" filterable /></NFormItem></NForm>
    <template #footer><NSpace justify="end"><NButton @click="showStaticFileCopyToModal = false">取消</NButton><NButton type="primary" :disabled="!staticFileCopyToForm.target_workspace_id" :loading="loading" @click="handleStaticFileCopyToWorkspace">{{ t('views.statistic-center.message_cn_d987a67e') }}</NButton></NSpace></template>
  </NModal>

  <!-- ── MySQL 弹窗 ── -->
  <NModal v-model:show="showMySQLModal" :title="t('views.statistic-center.label_cn_16b3e029')" preset="card" style="width: 600px">
    <NForm label-placement="top">
      <div class="grid grid-cols-2 gap-x-4">
        <NFormItem :label="t('views.statistic-center.label_cn_aeb5271e')" required><NInput v-model:value="mysqlForm.host" placeholder="127.0.0.1" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_c76cfefe')" required><NInputNumber v-model:value="mysqlForm.port" :min="1" :max="65535" /></NFormItem>
      </div>
      <div class="grid grid-cols-2 gap-x-4">
        <NFormItem :label="t('views.statistic-center.label_cn_819767ad')"><NInput v-model:value="mysqlForm.user" placeholder="root" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_a8105204')"><NInput v-model:value="mysqlForm.password" type="password" :placeholder="t('views.statistic-center.label_cn_a8105204')" /></NFormItem>
      </div>
      <NFormItem :label="t('views.statistic-center.label_cn_5ccbbd01')" required><NInput v-model:value="mysqlForm.database" :placeholder="t('views.statistic-center.label_cn_d5f399b9')" /></NFormItem>
      <NButton size="small" @click="testMySQL" :loading="mysqlTesting" :disabled="!mysqlForm.host || !mysqlForm.database">{{ mysqlTested ? t('views.statistic-center.label_cn_671bfe2f') : t('views.statistic-center.label_cn_69e74756') }}</NButton>
      <div v-if="mysqlTested && mysqlTables.length" class="mt-3">
        <div class="text-sm text-gray-500 mb-2">{{ t('views.statistic-center.placeholder_cn_560d54bd') }}</div>
        <div class="max-h-60 overflow-auto border rounded-lg">
          <div v-for="t in mysqlTables" :key="t.name" class="flex items-center gap-2 p-2 hover:bg-gray-50 border-b border-gray-50 last:border-0">
            <NCheckbox size="small" :checked="t.selected" @update:checked="t.selected = !t.selected" />
            <span class="text-sm">{{ t.name }}</span>
            <span v-if="t.comment" class="text-xs text-gray-400">- {{ t.comment }}</span>
            <span v-if="t.estimated_rows" class="text-xs text-gray-400 ml-auto">~{{ t.estimated_rows?.toLocaleString() }} 行</span>
          </div>
        </div>
      </div>
    </NForm>
    <template #footer><NSpace justify="end"><NButton @click="showMySQLModal = false">取消</NButton><NButton type="primary" :disabled="!mysqlTested || !mysqlTables.some(t => t.selected)" :loading="dbLoading" @click="importMySQL">导入 ({{ mysqlTables.filter(t => t.selected).length }})</NButton></NSpace></template>
  </NModal>

  <!-- ── SQLite 弹窗 ── -->
  <NModal v-model:show="showSQLiteModal" :title="t('views.statistic-center.label_cn_e2846471')" preset="card" style="width: 600px">
    <div class="mb-4">
      <NUpload :show-file-list="false" :default-upload="false" accept=".sqlite,.db,.sqlite3" @change="handleSQLiteUpload">
        <NButton :loading="sqliteUploading"><TheIcon icon="material-symbols:upload" :size="18" class="mr-1" />{{ sqliteFileName ? `已上传: ${sqliteFileName}` : t('views.statistic-center.label_cn_d895f612') }}</NButton>
      </NUpload>
    </div>
    <div v-if="sqliteTables.length" class="mt-3">
      <div class="text-sm text-gray-500 mb-2">{{ t('views.statistic-center.placeholder_cn_560d54bd') }}</div>
      <div class="max-h-60 overflow-auto border rounded-lg">
        <div v-for="t in sqliteTables" :key="t.name" class="flex items-center gap-2 p-2 hover:bg-gray-50 border-b border-gray-50 last:border-0">
          <NCheckbox size="small" :checked="t.selected" @update:checked="t.selected = !t.selected" />
          <span class="text-sm">{{ t.name }}</span>
        </div>
      </div>
    </div>
    <template #footer><NSpace justify="end"><NButton @click="showSQLiteModal = false">取消</NButton><NButton type="primary" :disabled="!sqliteTables.some(t => t.selected)" :loading="dbLoading" @click="importSQLite">导入 ({{ sqliteTables.filter(t => t.selected).length }})</NButton></NSpace></template>
  </NModal>

  <!-- ── 像素数据弹窗 ── -->
  <NModal v-model:show="showPixelModal" :title="t('views.statistic-center.label_cn_40909c62')" preset="card" style="width: 500px">
    <NForm label-placement="top">
      <NFormItem :label="t('views.statistic-center.label_cn_e034af06')" required><NSelect v-model:value="pixelForm.pixel_account_id" :options="pixelAccounts" :placeholder="t('views.statistic-center.placeholder_cn_9692c535')" @update:value="onPixelAccountChange" /></NFormItem>
      <NFormItem v-if="pixelTables.length" :label="t('views.statistic-center.label_cn_e9273484')"><NSelect v-model:value="pixelForm.table_name" :options="pixelTables" :placeholder="t('views.statistic-center.placeholder_cn_1acf0346')" /></NFormItem>
    </NForm>
    <template #footer><NSpace justify="end"><NButton @click="showPixelModal = false">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton><NButton type="primary" :disabled="!pixelForm.pixel_account_id || !pixelForm.table_name" :loading="dbLoading" @click="importPixel">导入</NButton></NSpace></template>
  </NModal>

  <!-- ── 路网数据弹窗 ── -->
  <NModal v-model:show="showRoadNetworkModal" :title="t('views.statistic-center.label_cn_63b03fa8')" preset="card" style="width: 680px; max-height: 85vh">
    <NForm label-placement="top">
      <NFormItem :label="t('views.statistic-center.placeholder_cn_97d03d46')" required>
        <NSelect v-model:value="roadNetworkForm.region_id" :options="roadNetworkRegions" :placeholder="t('views.statistic-center.placeholder_cn_b65a096f')" filterable clearable @update:value="onRoadNetworkRegionChange">
          <template #action>{{ t('views.statistic-center.placeholder_cn_7d7c8426') }}</template>
        </NSelect>
      </NFormItem>

      <!-- 无区域选中提示 -->
      <div v-if="!roadNetworkForm.region_id && !roadNetworks.length" class="flex flex-col items-center justify-center py-12 text-gray-400">
        <TheIcon icon="material-symbols:route" :size="56" class="mb-3 opacity-25" />
        <div class="text-base font-medium text-gray-500">{{ t('views.statistic-center.placeholder_cn_2eaae997') }}</div>
        <div class="text-sm mt-1">{{ t('views.statistic-center.label_cn_aa6aa60d') }}</div>
      </div>

      <!-- 已选区域但加载中 -->
      <div v-else-if="roadNetworkForm.region_id && !roadNetworks.length" class="flex items-center justify-center py-10 text-gray-400">
        <NSpin size="small" /><span class="ml-2 text-sm">{{ t('views.statistic-center.label_cn_a9da3576') }}</span>
      </div>

      <!-- 路网文件列表 -->
      <div v-else class="mt-2">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <NCheckbox
              size="small"
              :checked="roadNetworks.every(n => n.selected) && roadNetworks.length > 0"
              :indeterminate="roadNetworks.some(n => n.selected) && !roadNetworks.every(n => n.selected)"
              @update:checked="toggleAllRoadNetworks"
            />
            <span class="text-sm text-gray-500">
              已选 <strong class="text-gray-700">{{ roadNetworks.filter(n => n.selected).length }}</strong> / {{ roadNetworks.length }} 个路网文件
            </span>
          </div>
          <span class="text-xs text-gray-400">
            {{ roadNetworks.filter(n => n.selected).length ? roadNetworks.every(n => n.selected) ? t('views.statistic-center.label_cn_dfb9060b') : t('views.statistic-center.label_cn_ec68176e') : t('views.statistic-center.label_cn_f0409ecf') }}
          </span>
        </div>

        <div class="space-y-1.5 max-h-72 overflow-auto pr-1">
          <div
            v-for="n in roadNetworks"
            :key="n.id"
            class="flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all hover:shadow-sm"
            :class="{
              'border-blue-300 bg-blue-50/60 shadow-sm': n.selected,
              'border-gray-150 bg-white hover:border-gray-250': !n.selected
            }"
            @click="n.selected = !n.selected"
          >
            <!-- 选择框 -->
            <NCheckbox size="small" :checked="n.selected" class="flex-shrink-0" @click.stop />

            <!-- 主信息 -->
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="text-sm font-medium truncate">{{ n.file_name }}</span>
                <NTag size="tiny" :bordered="false" :type="n.download_mode === 'name' ? 'info' : 'success'" class="flex-shrink-0">
                  {{ n.download_mode === 'name' ? t('views.statistic-center.label_cn_d06a491f') : t('views.statistic-center.label_cn_1ded98db') }}
                </NTag>
                <NTag v-if="n.file_type" size="tiny" :bordered="false" class="flex-shrink-0">{{ n.file_type }}</NTag>
              </div>
              <div class="flex items-center gap-4 text-xs text-gray-400 mt-1.5">
                <span class="flex items-center gap-1"><TheIcon icon="material-symbols:account-tree" :size="13" />{{ (n.node_count || 0).toLocaleString() }} 节点</span>
                <span class="flex items-center gap-1"><TheIcon icon="material-symbols:timeline" :size="13" />{{ (n.edge_count || 0).toLocaleString() }} 边</span>
                <span v-if="n.junction_count" class="flex items-center gap-1"><TheIcon icon="material-symbols:polyline" :size="13" />{{ n.junction_count }} 路口</span>
                <span v-if="n.highway_count" class="flex items-center gap-1"><TheIcon icon="material-symbols:layers" :size="13" />{{ n.highway_count }} 等级</span>
                <span v-if="n.file_size" class="flex items-center gap-1"><TheIcon icon="material-symbols:hard-drive" :size="13" />{{ formatFileSize(n.file_size) }}</span>
              </div>
            </div>

            <!-- 选中标记 -->
            <div v-if="n.selected" class="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center flex-shrink-0">
              <TheIcon icon="material-symbols:check" :size="14" class="text-white" />
            </div>
          </div>
        </div>
      </div>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showRoadNetworkModal = false">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton>
        <NButton
          type="primary"
          :disabled="!roadNetworks.some(n => n.selected)"
          :loading="dbLoading"
          @click="importRoadNetwork"
        >
          <template #icon><TheIcon icon="material-symbols:database-import" :size="16" /></template>
          {{ t('views.statistic-center.label_cn_8d9a071e') }} {{ roadNetworks.filter(n => n.selected).length || '' }} 个路网统计
        </NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- ── 复制到弹窗 ── -->
  <NModal v-model:show="showCopyToModal" :title="t('views.statistic-center.label_cn_2008c3ff')" preset="card" style="width: 480px">
    <div class="text-sm text-gray-500 mb-4">将复制 {{ selectedDatabaseDocIds.length }} 项数据库导入数据到目标工作区</div>
    <NForm label-placement="top"><NFormItem :label="t('views.statistic-center.label_cn_9269a338')" required><NSelect v-model:value="copyToForm.target_workspace_id" :options="copyToWorkspaces" :placeholder="t('views.statistic-center.placeholder_cn_96d6caf0')" filterable /></NFormItem></NForm>
    <template #footer><NSpace justify="end"><NButton @click="showCopyToModal = false">取消</NButton><NButton type="primary" :disabled="!copyToForm.target_workspace_id" :loading="dbLoading" @click="handleCopyToWorkspace">{{ t('views.statistic-center.message_cn_d987a67e') }}</NButton></NSpace></template>
  </NModal>

  <!-- ── BaseUrl 弹窗 ── -->
  <NModal v-model:show="showBaseUrlModal" :title="t('views.statistic-center.label_cn_cfc2af7c')" preset="card" style="width: 520px">
    <div class="text-sm text-gray-500 mb-4">{{ t('views.statistic-center.label_cn_3772c255') }}<br/>留空则自动使用当前访问地址。</div>
    <NForm label-placement="top"><NFormItem label="BaseUrl"><NInput v-model:value="baseUrlForm.base_url" :placeholder="t('views.statistic-center.placeholder_cn_44765919')" /></NFormItem></NForm>
    <template #footer><NSpace justify="end"><NButton @click="showBaseUrlModal = false">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton><NButton type="primary" @click="handleBaseUrlSubmit">保存</NButton></NSpace></template>
  </NModal>

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
        <NButton @click="showWsModal = false">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton>
        <NButton type="primary" @click="handleWsSubmit">{{ t('views.statistic-center.label_cn_e83a256e') }}</NButton>
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
        <NButton @click="showDocAnalyzeModal = false">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton>
        <NButton type="primary" :loading="loading" @click="handleDocAnalyzeSubmit">{{ t('views.statistic-center.label_cn_a7e17ae8') }}</NButton>
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
        <NButton @click="handleDocEditCancel">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton>
        <NButton type="primary" :loading="docSaving" @click="handleDocSave">{{ t('views.statistic-center.label_cn_be5fbbe3') }}</NButton>
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

.ws-avatar {
  width: 36px; height: 36px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-weight: 700; font-size: 15px;
  flex-shrink: 0;
  text-transform: uppercase;
}
</style>
