<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NButton, NModal, NSpace, NSelect, NPopconfirm,
  NForm, NFormItem, NTag, NUpload, NUploadDragger, NText,
  NCheckbox, NInput, NInputNumber, NSlider, NSpin,
  NBreadcrumb, NBreadcrumbItem,
  useMessage,
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

// ── 静态文件数据状态 ──
const staticFileSourceType = ref('original')
const staticFiles = ref([])
const selectedStaticFileIds = ref([])
const selectedStaticFile = ref(null)
const staticFilesLoading = ref(false)
const staticFileUploadRef = ref(null)
const staticFileBaseUrl = ref('')
const staticFileUploading = ref(false)

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

// 图片提取弹窗
const showImageExtractModal = ref(false)
const imageExtractUploading = ref(false)
const imageExtractLoading = ref(false)
const extractedImages = ref([])
const extractedTempPaths = ref([])
const extractedSourceName = ref('')
const extractedSelectedIds = ref([])

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
  try { await navigator.clipboard.writeText(url); message.success(t('views.statistic-center.message_cn_6235f28c')) }
  catch (e) { message.error(t('views.statistic-center.message_cn_7f0e8de3')) }
}

async function loadStaticFiles() {
  if (!selectedWs.value) return
  staticFilesLoading.value = true
  try {
    const res = await api.getStaticFileList({ workspace_id: selectedWs.value.id, source_type: staticFileSourceType.value, page: 1, page_size: 500 })
    staticFiles.value = res.data || []
    selectedStaticFileIds.value = []
    selectedStaticFile.value = null
    await loadStaticFileBaseUrl()
  } catch (e) { message.error(t('views.statistic-center.message_cn_a1fac25d')) }
  staticFilesLoading.value = false
}

function onStaticFileSourceTypeChange() { selectedStaticFileIds.value = []; selectedStaticFile.value = null; loadStaticFiles() }

function toggleStaticFileSelect(id) {
  const idx = selectedStaticFileIds.value.indexOf(id)
  if (idx >= 0) selectedStaticFileIds.value.splice(idx, 1)
  else selectedStaticFileIds.value.push(id)
}

function toggleAllStaticFiles() {
  if (selectedStaticFileIds.value.length === staticFiles.value.length && staticFiles.value.length > 0) selectedStaticFileIds.value = []
  else selectedStaticFileIds.value = staticFiles.value.map(f => f.id)
}

function onStaticFileRowClick(file) {
  selectedStaticFile.value = selectedStaticFile.value?.id === file.id ? null : file
}

async function handleStaticFileUpload({ file, fileList }) {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_aac7e445')); return }
  if (staticFileUploadLock) return
  for (const f of fileList) { if (f.status === 'pending' && f.file) staticFileUploadQueue.set(`${f.file.name}__${f.file.size}`, f.file) }
  if (!staticFileUploadQueue.size) return
  clearTimeout(staticFileUploadTimer)
  staticFileUploading.value = true
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
    staticFileUploading.value = false
    // 清空 NUpload 内部文件列表，避免下次上传时重复上传旧文件
    staticFileUploadRef.value?.clear()
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
  try { const [pr, sl] = await Promise.all([api.getAIProxyList({ page: 1, page_size: 500 }), api.getSkillList({ page: 1, page_size: 500 })]); proxyOptions.value = (pr.data || []).map(p => ({ label: p.name, value: p.id })); skillOptions.value = (sl.data || []).map(s => ({ label: s.title, value: s.id })) } catch (e) {}
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
  try { const res = await api.getWorkspaceList({ page: 1, page_size: 500 }); staticFileCopyToWorkspaces.value = (res.data || []).filter(w => w.id !== selectedWs.value.id).map(w => ({ label: w.name, value: w.id })) } catch (e) {}
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

// ── 图片提取 ──
function openImageExtractModal() {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_aac7e445')); return }
  extractedImages.value = []
  extractedTempPaths.value = []
  extractedSourceName.value = ''
  extractedSelectedIds.value = []
  imageExtractUploading.value = false
  imageExtractLoading.value = false
  showImageExtractModal.value = true
}

async function handleImageExtractUpload({ file }) {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_aac7e445')); return }
  imageExtractUploading.value = true
  imageExtractLoading.value = true
  try {
    const res = await api.extractImagesFromDoc(file.file)
    extractedImages.value = res.data?.images || []
    extractedTempPaths.value = res.data?.temp_paths || []
    extractedSourceName.value = res.data?.source_name || file.file.name || ''
    extractedSelectedIds.value = []
    message.success(res.msg || t('views.statistic-center.message_cn_509132eb'))
  } catch (e) {
    message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_54e5de42'))
    extractedImages.value = []
    extractedTempPaths.value = []
  }
  imageExtractUploading.value = false
  imageExtractLoading.value = false
}

function toggleAllExtractedImages() {
  if (extractedSelectedIds.value.length === extractedImages.value.length && extractedImages.value.length > 0) {
    extractedSelectedIds.value = []
  } else {
    extractedSelectedIds.value = extractedImages.value.map(img => img.index)
  }
}

function toggleExtractedImageSelect(index) {
  const idx = extractedSelectedIds.value.indexOf(index)
  if (idx >= 0) extractedSelectedIds.value.splice(idx, 1)
  else extractedSelectedIds.value.push(index)
}

async function handleImageExtractImport() {
  if (!extractedSelectedIds.value.length) { message.warning('请选择要导入的图片'); return }
  if (!selectedWs.value) return
  imageExtractLoading.value = true
  try {
    const selectedPaths = extractedSelectedIds.value.map(i => extractedTempPaths.value[i])
    const selectedNames = extractedSelectedIds.value.map(i => {
      const img = extractedImages.value.find(img => img.index === i)
      return img?.file_name || ''
    })
    const res = await api.importExtractedImages({
      workspace_id: selectedWs.value.id,
      source_type: staticFileSourceType.value,
      temp_paths: selectedPaths,
      file_names: selectedNames,
      source_doc_name: extractedSourceName.value,
    })
    message.success(res.msg || `成功导入 ${res.data?.success_count || 0} 张图片`)
    showImageExtractModal.value = false
    await loadStaticFiles()
  } catch (e) {
    message.error(e?.response?.data?.msg || '导入失败')
  }
  imageExtractLoading.value = false
}

watch(() => selectedWs.value, (ws) => {
  if (ws) {
    loadStaticFiles()
  } else {
    staticFiles.value = []
    selectedStaticFileIds.value = []
    selectedStaticFile.value = null
  }
}, { immediate: true })

defineExpose({ loadStaticFiles })
</script>

<template>
  <div class="flex-1 flex flex-col" style="min-height: 0; overflow: hidden">
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <div class="flex items-center gap-2">
        <TheIcon icon="material-symbols:folder" :size="20" class="text-blue-500" />
        <NButton size="small" :type="staticFileSourceType === 'original' ? 'primary' : 'default'" @click="staticFileSourceType = 'original'; onStaticFileSourceTypeChange()">{{ t('views.statistic-center.label_cn_70ac56dc') }}</NButton>
        <NButton size="small" :type="staticFileSourceType === 'ai_analysis' ? 'primary' : 'default'" @click="staticFileSourceType = 'ai_analysis'; onStaticFileSourceTypeChange()">{{ t('views.statistic-center.label_cn_907b787c') }}</NButton>
        <NTag size="small" :bordered="false" type="info">{{ staticFiles.length }}</NTag>
      </div>
      <NSpace size="small">
        <div v-if="staticFiles.length"><NButton size="small" type="primary" :disabled="!selectedStaticFileIds.length" @click="batchExportStaticFilesAction"><TheIcon icon="material-symbols:download" :size="16" class="mr-1" />导出({{ selectedStaticFileIds.length }})</NButton></div>
        <NPopconfirm @positive-click="batchDeleteStaticFilesAction" :disabled="!selectedStaticFileIds.length">
          <template #trigger><NButton size="small" type="warning" :disabled="!selectedStaticFileIds.length"><TheIcon icon="material-symbols:delete-outline" :size="16" />删除({{ selectedStaticFileIds.length }})</NButton></template>
          确认删除已选中的 {{ selectedStaticFileIds.length }} 个文件？
        </NPopconfirm>
      </NSpace>
    </div>
    <div class="mb-4">
      <NUpload ref="staticFileUploadRef" :show-file-list="false" :default-upload="false" accept="*" multiple @change="handleStaticFileUpload">
        <NUploadDragger class="w-full" style="border-radius: 8px; --n-border-hover: 2px dashed #3b82f6">
          <div v-if="!staticFileUploading" class="flex flex-col items-center py-4">
            <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center mb-2"><TheIcon icon="material-symbols:upload" :size="28" class="text-blue-500" /></div>
            <div class="text-sm font-semibold text-gray-700">上传文件到{{ staticFileSourceType === 'original' ? t('views.statistic-center.label_cn_d3182537') : t('views.statistic-center.label_cn_c57e8ae8') }}目录</div>
            <div class="text-xs text-gray-400 mt-0.5">{{ t('views.statistic-center.label_cn_fef7540f') }}</div>
          </div>
          <div v-else class="flex flex-col items-center py-4">
            <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center mb-2">
              <TheIcon icon="material-symbols:cloud-upload" :size="28" class="text-blue-500 animate-pulse" />
            </div>
            <div class="text-sm font-semibold text-blue-600 mb-2">正在上传...</div>
            <div class="w-36 h-1 bg-gray-200 rounded-full overflow-hidden">
              <div class="h-full bg-blue-500 rounded-full animate-pulse" style="width: 60%" />
            </div>
          </div>
        </NUploadDragger>
      </NUpload>
    </div>
    <div class="flex flex-wrap items-center gap-2 mb-4">
      <NButton size="small" @click="openCVModal" :disabled="!selectedStaticFileIds.length"><TheIcon icon="material-symbols:tune" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_cedfaa94') }}</NButton>
      <NButton size="small" @click="openAIModal" :disabled="!selectedStaticFileIds.length"><TheIcon icon="material-symbols:auto-awesome" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_98264bd9') }}</NButton>
      <NButton size="small" @click="handleOCRExtract" :disabled="!selectedStaticFileIds.length"><TheIcon icon="material-symbols:text-scan" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_0ff045c8') }}</NButton>
      <NButton size="small" type="primary" @click="openImageExtractModal"><TheIcon icon="material-symbols:image-search" :size="16" class="mr-1" />图片提取</NButton>
      <NButton size="small" @click="openMaterialImportModal"><TheIcon icon="material-symbols:drive-folder-upload" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_f747d2cc') }}</NButton>
      <NButton size="small" :disabled="!selectedStaticFileIds.length" @click="openStaticFileCopyToModal"><TheIcon icon="material-symbols:content-copy" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_a9ac3f71') }}</NButton>
      <NButton size="small" @click="openBaseUrlModal"><TheIcon icon="material-symbols:link" :size="16" class="mr-1" />BaseUrl</NButton>
    </div>
    <div class="flex-1 flex gap-3" :class="{ 'mobile-stack': isMobileCollapsed }" style="min-height: 0; overflow: hidden">
      <div class="flex flex-col" :style="isMobileCollapsed ? 'width: 100%, minWidth: 0' : { width: selectedStaticFile ? '55%' : '100%', minWidth: 0, transition: 'width 0.2s' }" style="min-height: 0; overflow: hidden">
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
            <div v-if="selectedStaticFile.is_image"><NButton size="tiny" quaternary :title="t('views.statistic-center.label_cn_80fb2db8')" @click="window.open(`/api/sf/${selectedStaticFile.short_url_token}`, '_blank')"><TheIcon icon="material-symbols:open-in-new" :size="18" /></NButton></div>
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

  <!-- ── BaseUrl 弹窗 ── -->
  <NModal v-model:show="showBaseUrlModal" :title="t('views.statistic-center.label_cn_cfc2af7c')" preset="card" style="width: 520px">
    <div class="text-sm text-gray-500 mb-4">{{ t('views.statistic-center.label_cn_3772c255') }}<br/>留空则自动使用当前访问地址。</div>
    <NForm label-placement="top"><NFormItem label="BaseUrl"><NInput v-model:value="baseUrlForm.base_url" :placeholder="t('views.statistic-center.placeholder_cn_44765919')" /></NFormItem></NForm>
    <template #footer><NSpace justify="end"><NButton @click="showBaseUrlModal = false">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton><NButton type="primary" @click="handleBaseUrlSubmit">保存</NButton></NSpace></template>
  </NModal>

  <!-- ── 图片提取弹窗 ── -->
  <NModal v-model:show="showImageExtractModal" title="图片提取" preset="card" style="width: 750px; max-height: 85vh">
    <div class="flex flex-col" style="max-height: 65vh">
      <!-- 上传区 -->
      <div v-if="!extractedImages.length" class="mb-4">
        <NUpload :show-file-list="false" :default-upload="false" accept=".ppt,.pptx,.doc,.docx,.xls,.xlsx,.pdf" @change="handleImageExtractUpload">
          <NUploadDragger class="w-full" style="border-radius: 8px; --n-border-hover: 2px dashed #10b981">
            <div v-if="!imageExtractUploading" class="flex flex-col items-center py-6">
              <div class="w-14 h-14 rounded-xl bg-green-50 flex items-center justify-center mb-3">
                <TheIcon icon="material-symbols:image-search" :size="32" class="text-green-500" />
              </div>
              <div class="text-base font-semibold text-gray-700">上传文档提取图片</div>
              <div class="text-sm text-gray-400 mt-1">支持 PPT、Word、Excel、PDF 文件</div>
              <div class="flex items-center gap-2 mt-3 text-xs text-gray-400 bg-gray-100 rounded-full px-3 py-1">
                <span>.ppt</span><span>.pptx</span><span>.doc</span><span>.docx</span><span>.xls</span><span>.xlsx</span><span>.pdf</span>
              </div>
            </div>
            <div v-else class="flex flex-col items-center py-6">
              <TheIcon icon="material-symbols:cloud-upload" :size="32" class="text-green-500 animate-pulse mb-2" />
              <div class="text-sm font-semibold text-green-600">正在提取图片...</div>
            </div>
          </NUploadDragger>
        </NUpload>
      </div>

      <!-- 提取结果 -->
      <div v-else>
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <TheIcon icon="material-symbols:image" :size="18" class="text-green-500" />
            <span class="font-semibold text-sm">提取结果：{{ extractedImages.length }} 张图片</span>
            <NTag size="small" :bordered="false" type="info">{{ extractedSourceName }}</NTag>
          </div>
          <div class="flex items-center gap-2">
            <NCheckbox size="small" :checked="extractedSelectedIds.length === extractedImages.length && extractedImages.length > 0" :indeterminate="extractedSelectedIds.length > 0 && extractedSelectedIds.length < extractedImages.length" @update:checked="toggleAllExtractedImages">
              全选
            </NCheckbox>
          </div>
        </div>

        <div class="overflow-auto rounded-lg border border-gray-100 bg-gray-50/50 p-2" style="max-height: 380px">
          <div class="grid gap-2" style="grid-template-columns: repeat(auto-fill, minmax(180px, 1fr))">
            <div
              v-for="(img, idx) in extractedImages"
              :key="img.index"
              class="bg-white rounded-lg border p-2 cursor-pointer hover:shadow-sm transition-shadow"
              :class="{ 'border-green-400 bg-green-50/50': extractedSelectedIds.includes(img.index), 'border-gray-100': !extractedSelectedIds.includes(img.index) }"
              @click="toggleExtractedImageSelect(img.index)"
            >
              <div class="flex items-center gap-2 mb-1.5">
                <NCheckbox size="small" :checked="extractedSelectedIds.includes(img.index)" @click.stop />
                <span class="text-xs text-gray-400">#{{ idx + 1 }}</span>
              </div>
              <div class="text-xs font-medium truncate mb-1" :title="img.file_name">{{ img.file_name }}</div>
              <div class="flex items-center gap-1.5 text-xs text-gray-400 flex-wrap">
                <span v-if="img.format_type">{{ img.format_type }}</span>
                <span v-if="img.width">{{ img.width }}×{{ img.height }}</span>
                <span>{{ formatFileSize(img.file_size) }}</span>
              </div>
            </div>
          </div>
          <div v-if="!extractedImages.length" class="text-center text-gray-400 py-8">
            未提取到图片
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <NSpace justify="end">
        <NButton @click="showImageExtractModal = false">关闭</NButton>
        <NButton
          v-if="extractedImages.length"
          type="primary"
          :disabled="!extractedSelectedIds.length"
          :loading="imageExtractLoading"
          @click="handleImageExtractImport"
        >
          导入选中图片 ({{ extractedSelectedIds.length }})
        </NButton>
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
