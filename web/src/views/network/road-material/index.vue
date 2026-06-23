<script setup>
import { computed, h, onMounted, onBeforeUnmount, ref, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import {


  NButton, NCard, NDataTable, NInput, NInputNumber,
  NModal, NSelect, NSpace, NTag, NUpload, NPopconfirm,
  NForm, NFormItem, NColorPicker,
  NDescriptions, NDescriptionsItem, NImage, NEmpty,
  NSlider,
  useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { useTaskProgressStore } from '@/store/modules/taskProgress'

const { t } = useI18n()

defineOptions({ name: i18n.global.t('views.network.title_cn_3cbec9cc') })

const message = useMessage()

// ── 三级下拉选择器 ──
const countryList = ref([])
const regionList = ref([])
const regionLoading = ref(false)
const selectedCountry = ref(null)
const selectedRegion = ref(null)

function displayLabel(node) {
  const name = node.label || node.name
  return node.local_name ? `${name}（${node.local_name}）` : name
}

const countryOptions = computed(() =>
  countryList.value.map(r => ({ label: displayLabel(r), value: r.id }))
)
const regionOptions = computed(() =>
  regionList.value.map(r => ({ label: '　'.repeat(r._level || 0) + displayLabel(r), value: r.id }))
)

// 当前选中的区域ID（优先 region，回退 country）
const activeRegionId = computed(() => selectedRegion.value || selectedCountry.value)

async function fetchDescendants(parentId, level = 0) {
  const res = await api.getRegionChildren(parentId)
  const children = (res.data || []).map(c => ({ ...c, _level: level }))
  const result = [...children]
  for (const child of children) {
    if (child.has_children) {
      const grandchildren = await fetchDescendants(child.id, level + 1)
      result.push(...grandchildren)
    }
  }
  return result
}

async function onCountryChange(id) {
  selectedCountry.value = id
  selectedRegion.value = null
  regionList.value = []
  previewMaterial.value = null
  selectedMaterialIds.value = []
  materialList.value = []
  if (!id) return
  regionLoading.value = true
  try {
    regionList.value = await fetchDescendants(id)
  } catch (_) { regionList.value = [] }
  finally { regionLoading.value = false }
}

async function onRegionChange(id) {
  selectedRegion.value = id
  previewMaterial.value = null
  selectedMaterialIds.value = []
  if (id) await loadMaterials(id)
  else materialList.value = []
}

// ── 素材列表 ──
const materialList = ref([])
const materialLoading = ref(false)
const selectedMaterialIds = ref([])
const previewMaterial = ref(null)

const columns = [
  { type: 'selection' },
  { title: t('views.network.title_cn_d4761865'), key: 'name', ellipsis: { tooltip: true }, width: 180 },
  { title: t('views.network.roadNetwork.fileColumns.fileSize'), key: 'file_size_str', width: 90, align: 'center', sorter: (a, b) => a.file_size - b.file_size },
  { title: t('views.network.title_cn_874a5816'), key: 'resolution', width: 110, align: 'center' },
  { title: t('views.network.roadNetwork.fileColumns.fileType'), key: 'format_type', width: 80, align: 'center' },
  { title: t('views.network.title_cn_26ca20b1'), key: 'source_label', width: 90, align: 'center' },
  {
    title: t('views.network.title_cn_d098e4f7'), key: 'short_url', width: 60, align: 'center',
    render: (row) => h(NButton, { size: 'tiny', quaternary: true, onClick: (e) => { e.stopPropagation(); copyShortUrl(row) } },
      { icon: () => h(TheIcon, { icon: 'material-symbols:content-copy-outline', size: 14 }) }),
  },
  { title: t('views.network.title_cn_a5de870a'), key: 'updated_at', width: 120, align: 'center', sorter: (a, b) => new Date(a.updated_at) - new Date(b.updated_at) },
]

const sourceLabels = {
  upload: '用户上传', import: '外部导入', ai_generated: 'AI生成', cv_processed: 'CV处理', [t('views.network.roadNetworkWorkbench.title')]: '路网工作台',
}

function formatFileSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

async function copyShortUrl(row) {
  const url = `${window.location.origin}/api/s/${row.short_url_token}`
  try {
    await navigator.clipboard.writeText(url)
    message.success(t('views.network.message_cn_20ad8798'))
  } catch {
    message.error(t('views.system.message_cn_41da1ca4'))
  }
}

// ── 初始化 ──
onMounted(async () => {
  try {
    const res = await api.getRegionList({ region_type: 'COUNTRY', page_size: 500, is_active: true })
    countryList.value = res.data || []
  } catch (_) { countryList.value = [] }
})

// ── 加载素材 ──
async function loadMaterials(regionId) {
  materialLoading.value = true
  try {
    const res = await api.getMaterialList({ region_id: regionId, page_size: 500 })
    materialList.value = (res.data || []).map(item => ({
      ...item,
      file_size_str: formatFileSize(item.file_size),
      resolution: item.width && item.height ? `${item.width}x${item.height}` : '-',
      source_label: sourceLabels[item.source] || item.source,
    }))
  } catch (e) {
    materialList.value = []
  } finally {
    materialLoading.value = false
  }
}

// ── 选择素材（多选时预览第一个）──
function handleSelect(keys) {
  selectedMaterialIds.value = keys
  if (keys.length >= 1) {
    previewMaterial.value = materialList.value.find(m => m.id === keys[0]) || null
  } else {
    previewMaterial.value = null
  }
}

// 行点击：非 checkbox 区域只选中当前项
const rowProps = (row) => ({
  style: 'cursor: pointer;',
  onClick: (e) => {
    // 排除 checkbox 区域点击（保留多选功能）
    if (e.target.closest('.n-checkbox') || e.target.closest('.n-data-table-checkbox')) return
    selectedMaterialIds.value = [row.id]
    previewMaterial.value = row
  },
})

// ── 上传 ──
const showUploadModal = ref(false)
const uploadName = ref('')
const uploadDesc = ref('')
const uploadFile = ref(null)

function onUploadOpen() {
  if (!activeRegionId.value) { message.warning(t('views.network.message_cn_0d71d357')); return }
  uploadName.value = ''
  uploadDesc.value = ''
  uploadFile.value = null
  showUploadModal.value = true
}

async function onUploadSubmit() {
  if (!uploadFile.value) { message.warning(t('views.network.placeholder_cn_9febf311')); return }
  try {
    const rawFile = uploadFile.value.file || uploadFile.value
    await api.uploadMaterial(activeRegionId.value, uploadName.value, uploadDesc.value, rawFile)
    message.success(t('views.network.roadNetwork.messages.uploadSuccess'))
    showUploadModal.value = false
    uploadFile.value = null
    loadMaterials(activeRegionId.value)
  } catch (e) { message.error('上传失败: ' + (e.message || t('views.network.roadNetworkWorkbench.messages.unknownError'))) }
}

// ── 编辑元数据 ──
const showEditModal = ref(false)
const editData = ref({ id: 0, name: '', description: '' })

function onEdit() {
  if (!previewMaterial.value) { message.warning(t('views.network.message_cn_31e89ba0')); return }
  editData.value = { id: previewMaterial.value.id, name: previewMaterial.value.name, description: previewMaterial.value.description || '' }
  showEditModal.value = true
}

async function onEditSubmit() {
  try {
    await api.updateMaterial(editData.value)
    message.success(t('views.network.region.messages.updateSuccess'))
    showEditModal.value = false
    if (activeRegionId.value) loadMaterials(activeRegionId.value)
  } catch (e) { message.error('更新失败: ' + (e.message || t('views.network.roadNetworkWorkbench.messages.unknownError'))) }
}

// ── 删除 ──
async function onDelete(ids) {
  const delIds = ids || selectedMaterialIds.value
  if (!delIds.length) { message.warning(t('views.network.message_cn_52ce3aa6')); return }
  try {
    for (const id of delIds) {
      await api.deleteMaterial({ material_id: id })
    }
    message.success(t('views.network.roadNetwork.messages.deleteSuccess'))
    previewMaterial.value = null
    selectedMaterialIds.value = []
    if (activeRegionId.value) loadMaterials(activeRegionId.value)
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.deleteFail')) }
}

// ── AI 处理 ──
const showAIModal = ref(false)
const aiProxyList = ref([])
const aiProxyId = ref(null)
const aiSkillId = ref(null)
const aiPrompt = ref('')
const skillList = ref([])
const aiLoading = ref(false)

async function onAIOpen() {
  if (!selectedMaterialIds.value.length) { message.warning(t('views.network.message_cn_52ce3aa6')); return }
  try {
    const [proxyRes, skillRes] = await Promise.all([
      api.getAIProxyList({ page_size: 500 }),
      api.getSkillList({ page_size: 500 }),
    ])
    aiProxyList.value = proxyRes.data || []
    skillList.value = skillRes.data || []
  } catch (e) { /* ignore */ }
  aiProxyId.value = null
  aiSkillId.value = null
  aiPrompt.value = ''
  showAIModal.value = true
}

async function onAISubmit() {
  if (!aiProxyId.value) { message.warning(t('views.skill.placeholder_cn_ee488ec6')); return }
  if (!aiPrompt.value && !aiSkillId.value) { message.warning(t('views.network.placeholder_cn_3d6a6a12')); return }
  aiLoading.value = true
  try {
    const res = await api.aiProcessMaterial({
      material_ids: selectedMaterialIds.value,
      ai_proxy_id: aiProxyId.value,
      prompt: aiPrompt.value || undefined,
      skill_id: aiSkillId.value || undefined,
    })
    const d = res.data || {}
    if (d.success_count > 0) message.success(`AI处理完成：成功 ${d.success_count} 个`)
    if (d.error_count > 0) message.warning(`部分失败：${d.error_count} 个`)
    showAIModal.value = false
    if (activeRegionId.value) loadMaterials(activeRegionId.value)
  } catch (e) { message.error('AI处理失败: ' + (e.message || t('views.network.roadNetworkWorkbench.messages.unknownError'))) }
  finally { aiLoading.value = false }
}

// ── OpenCV 处理 ──
const showCVModal = ref(false)
const cvOperation = ref('resize')
const cvParams = ref({})
const cvCanvasRef = ref(null)
const cvImgObj = ref(null)
const cvIsDragging = ref(false)
const cvCropRect = ref({ x: 0, y: 0, w: 0, h: 0 })
const cvPreviewDataUrl = ref('')
const cvPreviewLoading = ref(false)

const operationGroups = [
  { label: t('views.network.label_cn_20cdf86d'), ops: ['resize', 'rotate', 'crop', 'flip', 'border'] },
  { label: t('views.network.label_cn_99543f13'), ops: ['brightness', 'contrast', 'color_space'] },
  { label: t('views.network.label_cn_f9854a3e'), ops: ['blur', 'morphology', 'smooth', 'histogram_eq'] },
  { label: t('views.network.label_cn_a9cec4ef'), ops: ['remove_bg'] },
]

function loadCVImage() {
  if (!previewMaterial.value) {
    console.warn('[CV] previewMaterial is null, cannot load image')
    return
  }
  const url = `/api/s/${previewMaterial.value.short_url_token}`
  console.log('[CV] loading image from public URL:', url)
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    console.log('[CV] image loaded:', img.width, 'x', img.height)
    cvImgObj.value = img
    cvCropRect.value = { x: 0, y: 0, w: Math.min(img.width, 300), h: Math.min(img.height, 300) }
    drawCanvas()
  }
  img.onerror = (e) => console.error('[CV] image load error:', url, e)
  img.src = url
}

function drawCanvas(overlayDataUrl) {
  const canvas = cvCanvasRef.value
  const img = cvImgObj.value
  if (!canvas || !img) {
    console.warn('[CV] drawCanvas skip: canvas=', !!canvas, 'img=', !!img)
    return
  }
  if (!canvas.getContext) { console.warn('[CV] canvas.getContext not available'); return }
  const ctx = canvas.getContext('2d')
  const cw = canvas.width, ch = canvas.height
  ctx.clearRect(0, 0, cw, ch)

  const scale = Math.min(cw / img.width, ch / img.height)
  const dw = img.width * scale, dh = img.height * scale
  const dx = (cw - dw) / 2, dy = (ch - dh) / 2

  if (overlayDataUrl) {
    const overlay = new Image()
    overlay.onload = () => { ctx.drawImage(overlay, dx, dy, dw, dh) }
    overlay.src = overlayDataUrl
  } else {
    ctx.drawImage(img, dx, dy, dw, dh)
  }

  if (cvOperation.value === 'crop') {
    const r = cvCropRect.value
    ctx.strokeStyle = '#f0a020'
    ctx.lineWidth = 2
    ctx.setLineDash([6, 3])
    ctx.strokeRect(r.x + dx, r.y + dy, r.w, r.h)
    ctx.setLineDash([])

    cvParams.value.x = Math.round(r.x)
    cvParams.value.y = Math.round(r.y)
    cvParams.value.width = Math.round(r.w)
    cvParams.value.height = Math.round(r.h)
  }

  if (cvOperation.value === 'rotate') {
    ctx.save()
    ctx.translate(cw / 2, ch / 2)
    ctx.rotate((cvParams.value.angle || 0) * Math.PI / 180)
    ctx.drawImage(img, -dw / 2, -dh / 2, dw, dh)
    ctx.restore()
  }

  if (cvOperation.value === 'brightness' || cvOperation.value === 'contrast') {
    const val = cvParams.value.value ?? 1
    if (cvOperation.value === 'brightness') {
      ctx.globalAlpha = 0.5
      ctx.fillStyle = val > 1 ? '#fff' : '#000'
      ctx.globalAlpha = Math.abs(val - 1) * 0.5
      ctx.fillRect(0, 0, cw, ch)
      ctx.globalAlpha = 1
    }
  }
}

async function onCVOpen() {
  if (!selectedMaterialIds.value.length) { message.warning(t('views.network.message_cn_52ce3aa6')); return }
  if (!previewMaterial.value || !selectedMaterialIds.value.includes(previewMaterial.value.id)) {
    previewMaterial.value = materialList.value.find(m => m.id === selectedMaterialIds.value[0]) || null
  }
  cvOperation.value = 'resize'
  cvParams.value = {}
  cvPreviewDataUrl.value = ''
  showCVModal.value = true
  await import('vue').then(({ nextTick }) => nextTick())
  setTimeout(loadCVImage, 200)
}

function onCVOpChange(op) {
  cvOperation.value = op
  cvParams.value = {}
  cvPreviewDataUrl.value = ''
  setTimeout(drawCanvas, 50)
}

async function onCVSubmit() {
  const ids = [...selectedMaterialIds.value]
  if (!ids.length) { message.warning(t('views.network.message_cn_52ce3aa6')); return }
  const taskStore = useTaskProgressStore()
  const taskId = taskStore.startTask(`OpenCV ${cvOperation.value} 处理`)
  showCVModal.value = false
  let successCount = 0, failCount = 0
  for (let i = 0; i < ids.length; i++) {
    const pct = Math.round((i / ids.length) * 100)
    taskStore.updateProgress(taskId, { progress: pct, message: `处理中 ${i + 1}/${ids.length}`, phase: cvOperation.value })
    try {
      const res = await api.cvProcessMaterial({
        material_ids: [ids[i]],
        operation: cvOperation.value,
        params: cvParams.value,
      })
      const d = res.data || {}
      if (d.results && d.results.length > 0) {
        successCount++
      } else if (d.errors && d.errors.length > 0) {
        failCount++
        taskStore.updateProgress(taskId, { progress: pct, message: `第 ${i + 1} 张失败: ${d.errors[0].error}`, phase: cvOperation.value })
      } else {
        failCount++
        taskStore.updateProgress(taskId, { progress: pct, message: `第 ${i + 1} 张: 无返回结果`, phase: cvOperation.value })
      }
    } catch (e) {
      failCount++
      const errMsg = e?.response?.data?.msg || e?.message || String(e)
      taskStore.updateProgress(taskId, { progress: pct, message: `第 ${i + 1} 张失败: ${errMsg}`, phase: cvOperation.value })
    }
  }
  if (failCount > 0) {
    taskStore.failTask(taskId, { message: `完成: 成功 ${successCount}, 失败 ${failCount}` })
    message.warning(`处理完成: 成功 ${successCount} 张, 失败 ${failCount} 张`)
  } else {
    taskStore.finishTask(taskId, `成功处理 ${successCount} 张`)
    message.success(`成功处理 ${successCount} 张图片`)
  }
  if (activeRegionId.value) await loadMaterials(activeRegionId.value)
}

async function onCVPreview() {
  cvPreviewLoading.value = true
  try {
    const res = await api.cvProcessMaterial({
      material_ids: [selectedMaterialIds.value[0]],
      operation: cvOperation.value,
      params: cvParams.value,
    })
    const results = res.data?.results || []
    if (results.length > 0) {
      const newId = results[0].id
      cvPreviewDataUrl.value = `${import.meta.env.VITE_BASE_API}/region/road-material/download-file?material_id=${newId}`
      drawCanvas(cvPreviewDataUrl.value)
    }
  } catch (e) { message.error('预览失败: ' + (e.message || t('views.network.roadNetworkWorkbench.messages.unknownError'))) }
  finally { cvPreviewLoading.value = false }
}

function onCVMouseDown(e) {
  if (cvOperation.value !== 'crop') return
  const canvas = cvCanvasRef.value; if (!canvas || !cvImgObj.value) return
  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / rect.width; const scaleY = canvas.height / rect.height
  const cw = canvas.width; const ch = canvas.height
  const imgScale = Math.min(cw / cvImgObj.value.width, ch / cvImgObj.value.height)
  const dx = (cw - cvImgObj.value.width * imgScale) / 2
  const dy = (ch - cvImgObj.value.height * imgScale) / 2
  cvIsDragging.value = true
  cvCropRect.value = { x: (e.clientX - rect.left) * scaleX - dx, y: (e.clientY - rect.top) * scaleY - dy, w: 1, h: 1 }
}
function onCVMouseMove(e) {
  if (!cvIsDragging.value || cvOperation.value !== 'crop') return
  const canvas = cvCanvasRef.value; if (!canvas || !cvImgObj.value) return
  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / rect.width; const scaleY = canvas.height / rect.height
  const cw = canvas.width; const ch = canvas.height
  const imgScale = Math.min(cw / cvImgObj.value.width, ch / cvImgObj.value.height)
  const dx = (cw - cvImgObj.value.width * imgScale) / 2
  const dy = (ch - cvImgObj.value.height * imgScale) / 2
  cvCropRect.value.w = Math.max(10, (e.clientX - rect.left) * scaleX - dx - cvCropRect.value.x)
  cvCropRect.value.h = Math.max(10, (e.clientY - rect.top) * scaleY - dy - cvCropRect.value.y)
  drawCanvas()
}
function onCVMouseUp() { cvIsDragging.value = false }

// ── 图片预览 URL ──
const previewUrl = computed(() => {
  if (!previewMaterial.value) return ''
  return `/api/s/${previewMaterial.value.short_url_token}`
})

// ── 拖拽分隔条 ──
const leftPanelWidth = ref(60)
const isResizing = ref(false)

function onResizeStart(e) {
  isResizing.value = true
  e.target.setPointerCapture(e.pointerId)
  document.addEventListener('pointermove', onResizeMove)
  document.addEventListener('pointerup', onResizeEnd)
  e.preventDefault()
}

function onResizeMove(e) {
  if (!isResizing.value) return
  const container = document.querySelector('.dual-panel-layout')
  if (!container) return
  const rect = container.getBoundingClientRect()
  const x = e.clientX - rect.left
  const percentage = (x / rect.width) * 100
  leftPanelWidth.value = Math.round(Math.max(20, Math.min(80, percentage)))
}

function onResizeEnd(e) {
  if (!isResizing.value) return
  isResizing.value = false
  e.target.releasePointerCapture(e.pointerId)
  document.removeEventListener('pointermove', onResizeMove)
  document.removeEventListener('pointerup', onResizeEnd)
}

onBeforeUnmount(() => {
  document.removeEventListener('pointermove', onResizeMove)
  document.removeEventListener('pointerup', onResizeEnd)
  destroyMap()
})

// ── 预览缩放与旋转 ──
const previewScale = ref(1)
const previewRotation = ref(0)

function zoomIn() { previewScale.value = Math.min(5, previewScale.value + 0.25) }
function zoomOut() { previewScale.value = Math.max(0.1, previewScale.value - 0.25) }
function rotateLeft() { previewRotation.value = (previewRotation.value - 90) % 360 }
function rotateRight() { previewRotation.value = (previewRotation.value + 90) % 360 }
function resetPreview() { previewScale.value = 1; previewRotation.value = 0 }

// ── GPS 信息解析与地图预览 ──
const gpsLocation = ref(null)
const mapContainer = ref(null)
let mapInstance = null

/**
 * 从 Pillow 提取的 exif_data 中解析 GPS 坐标
 * Pillow 提取的 GPSInfo 格式: "{1: 'N', 2: (31.0, 12.0, 0.0), 3: 'E', 4: (121.0, 30.0, 0.0)}"
 * 也兼容更简单的 JSON 格式
 */
function parseGpsFromExif(exifData) {
  if (!exifData) return null
  const gpsRaw = exifData.GPSInfo || exifData.GPS || exifData.gps || exifData.gpsinfo
  if (!gpsRaw) return null

  let latRef, latParts, lonRef, lonParts

  // 如果 gpsRaw 是对象（非字符串），直接取值
  if (typeof gpsRaw === 'object') {
    latRef = gpsRaw.GPSLatitudeRef || gpsRaw[1]
    lonRef = gpsRaw.GPSLongitudeRef || gpsRaw[3]
    latParts = gpsRaw.GPSLatitude || gpsRaw[2]
    lonParts = gpsRaw.GPSLongitude || gpsRaw[4]
  } else if (typeof gpsRaw === 'string') {
    const str = gpsRaw

    // 提取方向标记
    const latRefMatch = str.match(/(?:GPSLatitudeRef|['"]?1['"]?)\s*[:=]\s*['"]?([NS])['"]?/)
    const lonRefMatch = str.match(/(?:GPSLongitudeRef|['"]?3['"]?)\s*[:=]\s*['"]?([EW])['"]?/)
    latRef = latRefMatch ? latRefMatch[1] : 'N'
    lonRef = lonRefMatch ? lonRefMatch[1] : 'E'

    // 提取坐标元组 - 支持多种分隔符格式
    const tupleRegex = /\(([^)]*(?:\d+\.?\d*)[^)]*)\)/
    const latMatch = str.match(new RegExp(`(?:GPSLatitude|['\"]?2['\"]?)\\s*[:=]\\s*${tupleRegex.source}`))
    const lonMatch = str.match(new RegExp(`(?:GPSLongitude|['\"]?4['\"]?)\\s*[:=]\\s*${tupleRegex.source}`))

    if (!latMatch || !lonMatch) return null

    const parseTuple = (s) => {
      const parts = s.split(/[,/\s]+/).map(v => parseFloat(v)).filter(v => !isNaN(v))
      return parts.length >= 2 ? parts : null
    }
    latParts = parseTuple(latMatch[1])
    lonParts = parseTuple(lonMatch[1])
  }

  if (!latParts || !lonParts || latParts.length < 2 || lonParts.length < 2) return null

  // 转换为十进制：度 + 分/60 + 秒/3600
  let lat = latParts[0] + (latParts[1] || 0) / 60 + (latParts[2] || 0) / 3600
  if (latRef === 'S') lat = -lat

  let lng = lonParts[0] + (lonParts[1] || 0) / 60 + (lonParts[2] || 0) / 3600
  if (lonRef === 'W') lng = -lng

  // 合理性检查
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null

  return { lat: Math.round(lat * 1000000) / 1000000, lng: Math.round(lng * 1000000) / 1000000 }
}

function initMap() {
  if (!mapContainer.value) return
  if (!gpsLocation.value) return
  if (mapInstance) {
    // 如果地图已存在，更新视图
    mapInstance.setView([gpsLocation.value.lat, gpsLocation.value.lng], 13)
    return
  }
  try {
    mapInstance = L.map(mapContainer.value, {
      center: [gpsLocation.value.lat, gpsLocation.value.lng],
      zoom: 13,
      zoomControl: true,
      attributionControl: false,
    })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
    }).addTo(mapInstance)
    L.marker([gpsLocation.value.lat, gpsLocation.value.lng]).addTo(mapInstance)
  } catch (e) {
    console.warn(t('views.network.label_leaflet_cn_92c60fc8'), e)
  }
}

function destroyMap() {
  if (mapInstance) {
    mapInstance.remove()
    mapInstance = null
  }
}

// 监听 exif_data 中 GPS 信息变化
function updateGpsFromPreview() {
  if (!previewMaterial.value) {
    gpsLocation.value = null
    return
  }
  const loc = parseGpsFromExif(previewMaterial.value.exif_data)
  gpsLocation.value = loc
}

// 当预览素材变化时更新 GPS 和地图
watch(previewMaterial, async (newVal) => {
  // 重置预览缩放旋转
  resetPreview()
  // 更新 GPS
  updateGpsFromPreview()
  // 销毁旧地图
  destroyMap()
  // 初始化新地图
  if (gpsLocation.value) {
    await nextTick()
    initMap()
  }
}, { immediate: false })

// 修复 Leaflet 默认图标路径（因为本地文件在 /lib/leaflet/images/）
// 在 onMounted 中设置，确保 L 已经可用
onMounted(() => {
  // 如果 leaflet 已经加载，修正图标路径
  const fixIcons = () => {
    if (typeof L !== 'undefined' && L.Icon && L.Icon.Default) {
      delete L.Icon.Default.prototype._getIconUrl
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: '/lib/leaflet/images/marker-icon-2x.png',
        iconUrl: '/lib/leaflet/images/marker-icon.png',
        shadowUrl: '/lib/leaflet/images/marker-shadow.png',
      })
    }
  }
  // 延迟尝试，确保 leaflet.js 在 index.html 中同步加载完成
  setTimeout(fixIcons, 100)
})
</script>

<template>
  <CommonPage :title="t('views.network.title_cn_3cbec9cc')">
    <!-- ── 三级下拉选择器 ── -->
    <NSpace align="center" wrap style="margin-bottom: 12px;">
      <NSelect
        v-model:value="selectedCountry"
        :options="countryOptions"
        :placeholder="t('views.network.placeholder_cn_67eaca9f')"
        style="width: 200px"
        @update:value="onCountryChange"
        clearable filterable
      />
      <NSelect
        v-model:value="selectedRegion"
        :options="regionOptions"
        :placeholder="t('views.network.placeholder_cn_748ca716')"
        style="width: 240px"
        @update:value="onRegionChange"
        :disabled="!selectedCountry"
        :loading="regionLoading"
        clearable filterable
      />
      <NButton v-if="activeRegionId" size="small" @click="loadMaterials(activeRegionId)">
        <template #icon><TheIcon icon="material-symbols:refresh" size="14" /></template>
      </NButton>
    </NSpace>

    <div class="dual-panel-layout" :class="{ 'is-resizing': isResizing }">
      <!-- ── 左面板：素材表格 ── -->
      <NCard class="left-panel" :bordered="true" size="small" :style="{ width: leftPanelWidth + '%' }">
        <template #header>
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <span style="font-weight: 600">素材列表</span>
            <span v-if="activeRegionId" style="font-size: 12px; color: #999;">
              {{ regionOptions.find(r => r.value === activeRegionId)?.label || countryOptions.find(r => r.value === activeRegionId)?.label || '' }}
            </span>
          </div>
        </template>

        <div v-if="!activeRegionId" style="flex: 1; display: flex; align-items: center; justify-content: center; color: #999;">
          <NEmpty :description="t('views.network.placeholder_cn_6b27c45a')" />
        </div>

        <div v-else style="display: flex; flex-direction: column; flex: 1; min-height: 0;">
          <!-- 工具栏 -->
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap;">
            <NButton size="small" type="primary" @click="onUploadOpen">
              <template #icon><TheIcon icon="material-symbols:upload" size="14" /></template>
              上传
            </NButton>
            <NButton size="small" @click="onEdit" :disabled="!previewMaterial">
              <template #icon><TheIcon icon="material-symbols:edit" size="14" /></template>
              编辑
            </NButton>
            <NButton size="small" type="info" @click="onAIOpen" :disabled="!selectedMaterialIds.length">
              <template #icon><TheIcon icon="carbon:ai-status" size="14" /></template>
              AI处理
            </NButton>
            <NButton size="small" @click="onCVOpen" :disabled="!selectedMaterialIds.length">
              <template #icon><TheIcon icon="material-symbols:tune" size="14" /></template>
              CV处理
            </NButton>
            <NPopconfirm @positive-click="() => onDelete()">
              <template #trigger>
                <NButton size="small" type="error" :disabled="!selectedMaterialIds.length" secondary>
                  <template #icon><TheIcon icon="material-symbols:delete-outline" size="14" /></template>
                  删除
                </NButton>
              </template>
              确认删除选中的素材？
            </NPopconfirm>
            <NButton size="small" style="margin-left: auto;" @click="loadMaterials(activeRegionId)">
              <template #icon><TheIcon icon="material-symbols:refresh" size="14" /></template>
              刷新
            </NButton>
          </div>

          <NDataTable
            :columns="columns"
            :data="materialList"
            :loading="materialLoading"
            :row-key="(row) => row.id"
            :checked-row-keys="selectedMaterialIds"
            :single-line="false"
            size="small"
            :max-height="'calc(100vh - 280px)'"
            virtual-scroll
            :row-props="rowProps"
            @update:checked-row-keys="handleSelect"
            @update:selected-row-keys="handleSelect"
          />
        </div>
      </NCard>

      <!-- ── 拖拽分隔条 ── -->
      <div class="resize-handle" @pointerdown="onResizeStart"></div>

      <!-- ── 右面板：预览工作区 ── -->
      <NCard class="right-panel" :bordered="true" size="small">
        <template #header>
          <span style="font-weight: 600">预览工作区</span>
        </template>
        <div v-if="!previewMaterial" class="empty-preview">
          <NEmpty :description="t('views.network.label_cn_8369a589')" />
        </div>
        <div v-else class="preview-content">
          <!-- 图片调节工具栏 -->
          <div class="preview-toolbar">
            <NSpace align="center" size="small">
              <NButton size="tiny" quaternary @click="zoomOut" :disabled="previewScale <= 0.1" :title="t('views.network.title_cn_b21ac253')">
                <template #icon><TheIcon icon="material-symbols:zoom-out" size="16" /></template>
              </NButton>
              <span class="preview-scale-label">{{ Math.round(previewScale * 100) }}%</span>
              <NButton size="tiny" quaternary @click="zoomIn" :disabled="previewScale >= 5" :title="t('views.network.title_cn_4f9b192c')">
                <template #icon><TheIcon icon="material-symbols:zoom-in" size="16" /></template>
              </NButton>
              <NButton size="tiny" quaternary @click="rotateLeft" :title="t('views.network.title_cn_ad0bdf9a')">
                <template #icon><TheIcon icon="material-symbols:rotate-left" size="16" /></template>
              </NButton>
              <NButton size="tiny" quaternary @click="rotateRight" :title="t('views.network.title_cn_f3f9358b')">
                <template #icon><TheIcon icon="material-symbols:rotate-right" size="16" /></template>
              </NButton>
              <NButton size="tiny" quaternary @click="resetPreview" :title="t('views.network.title_cn_4b9c3271')">
                <template #icon><TheIcon icon="material-symbols:refresh" size="14" /></template>
                重置
              </NButton>
            </NSpace>
          </div>

          <!-- 图片预览 -->
          <div class="preview-image-wrap">
            <img
              :src="previewUrl"
              :style="{
                transform: `scale(${previewScale}) rotate(${previewRotation}deg)`,
                transition: 'transform 0.2s ease',
                maxWidth: '100%',
                maxHeight: '300px',
                objectFit: 'contain',
                borderRadius: '8px',
              }"
              alt="preview"
            />
          </div>

          <!-- GPS 地图预览 -->
          <div v-if="gpsLocation" class="preview-map">
            <div class="preview-map-label">
              <TheIcon icon="material-symbols:location-on" size="14" />
              拍摄位置: {{ gpsLocation.lat.toFixed(6) }}, {{ gpsLocation.lng.toFixed(6) }}
            </div>
            <div ref="mapContainer" class="map-container"></div>
          </div>

          <!-- 元数据 -->
          <NDescriptions :column="1" size="small" label-placement="left" style="margin-top: 16px;">
            <NDescriptionsItem :label="t('views.network.region.formLabels.name')">{{ previewMaterial.name }}</NDescriptionsItem>
            <NDescriptionsItem :label="t('views.network.roadNetwork.fileColumns.fileSize')">{{ previewMaterial.file_size_str }}</NDescriptionsItem>
            <NDescriptionsItem :label="t('views.network.title_cn_874a5816')">{{ previewMaterial.resolution }}</NDescriptionsItem>
            <NDescriptionsItem :label="t('views.network.label_cn_90b6fb5f')">{{ previewMaterial.color_mode || '-' }}</NDescriptionsItem>
            <NDescriptionsItem :label="t('views.network.label_cn_beff9059')">{{ previewMaterial.bit_depth || '-' }}</NDescriptionsItem>
            <NDescriptionsItem label="DPI/PPI">{{ previewMaterial.dpi || '-' }}</NDescriptionsItem>
            <NDescriptionsItem :label="t('views.network.roadNetwork.fileColumns.fileType')">{{ previewMaterial.format_type || '-' }}</NDescriptionsItem>
            <NDescriptionsItem :label="t('views.network.title_cn_26ca20b1')">{{ previewMaterial.source_label }}</NDescriptionsItem>
            <NDescriptionsItem :label="t('views.system.title_cn_696f5a97')">{{ previewMaterial.created_at || '-' }}</NDescriptionsItem>
            <NDescriptionsItem :label="t('views.network.label_cn_34681d7f')">{{ previewMaterial.description || '-' }}</NDescriptionsItem>
            <NDescriptionsItem label="EXIF">
              <span v-if="previewMaterial.exif_data" style="font-size: 11px; word-break: break-all;">
                {{ JSON.stringify(previewMaterial.exif_data) }}
              </span>
              <span v-else>-</span>
            </NDescriptionsItem>
            <NDescriptionsItem :label="t('views.network.title_cn_d098e4f7')">
              <NButton size="tiny" quaternary @click="copyShortUrl(previewMaterial)">
                <template #icon><TheIcon icon="material-symbols:content-copy-outline" size="12" /></template>
                复制
              </NButton>
            </NDescriptionsItem>
          </NDescriptions>
        </div>
      </NCard>
    </div>

    <!-- ── 上传弹窗 ── -->
    <NModal v-model:show="showUploadModal" preset="card" :title="t('views.network.title_cn_6c9f54c5')" style="width: 500px;">
      <NForm label-placement="left" label-width="80">
        <NFormItem :label="t('views.network.title_cn_d4761865')">
          <NInput v-model:value="uploadName" :placeholder="t('views.network.placeholder_cn_2692291e')" />
        </NFormItem>
        <NFormItem :label="t('views.network.label_cn_34681d7f')">
          <NInput v-model:value="uploadDesc" type="textarea" :placeholder="t('views.network.placeholder_cn_a0753482')" :rows="2" />
        </NFormItem>
        <NFormItem :label="t('views.network.roadNetwork.buttons.selectFile')" required>
          <NUpload
            :show-file-list="false"
            accept="image/*"
            @change="({ file }) => uploadFile = file"
          >
            <NButton>
              <template #icon><TheIcon icon="material-symbols:upload" size="14" /></template>
              选择图片文件
            </NButton>
          </NUpload>
          <div v-if="uploadFile" style="margin-top: 4px; font-size: 12px; color: #999;">
            已选择: {{ uploadFile.name }}
          </div>
        </NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showUploadModal = false">取消</NButton>
          <NButton type="primary" @click="onUploadSubmit">上传</NButton>
        </NSpace>
      </template>
    </NModal>

    <!-- ── 编辑弹窗 ── -->
    <NModal v-model:show="showEditModal" preset="card" :title="t('views.network.title_cn_1ad7e5f0')" style="width: 450px;">
      <NForm label-placement="left" label-width="80">
        <NFormItem :label="t('views.network.title_cn_d4761865')">
          <NInput v-model:value="editData.name" />
        </NFormItem>
        <NFormItem :label="t('views.network.label_cn_34681d7f')">
          <NInput v-model:value="editData.description" type="textarea" :placeholder="t('views.network.placeholder_cn_b57447a7')" :rows="2" />
        </NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showEditModal = false">取消</NButton>
          <NButton type="primary" @click="onEditSubmit">保存</NButton>
        </NSpace>
      </template>
    </NModal>

    <!-- ── AI处理弹窗 ── -->
    <NModal v-model:show="showAIModal" preset="card" :title="t('views.network.title_ai_cn_ce365320')" style="width: 550px;">
      <NForm label-placement="left" label-width="80">
        <NFormItem :label="t('views.skill.label_cn_c1dfc5cf')" required>
          <NSelect
            v-model:value="aiProxyId"
            :options="aiProxyList.map(p => ({ label: p.name, value: p.id }))"
            :placeholder="t('views.skill.placeholder_cn_523369d2')"
            filterable
          />
        </NFormItem>
        <NFormItem label="Skill">
          <NSelect
            v-model:value="aiSkillId"
            :options="skillList.map(s => ({ label: s.title, value: s.id }))"
            :placeholder="t('views.network.placeholder_cn_a7308b85')"
            filterable
            clearable
          />
        </NFormItem>
        <NFormItem :label="t('views.skill.label_cn_47b7af95')">
          <NInput
            v-model:value="aiPrompt"
            type="textarea"
            :placeholder="t('views.network.placeholder_cn_a188a7c4')"
            :rows="4"
          />
        </NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showAIModal = false">取消</NButton>
          <NButton type="primary" :loading="aiLoading" @click="onAISubmit">开始处理</NButton>
        </NSpace>
      </template>
    </NModal>

    <!-- ── OpenCV处理弹窗 ── -->
    <NModal v-model:show="showCVModal" preset="card" :title="t('views.network.title_opencv_cn_65060ed5')" style="width: 800px;">
      <div style="display: flex; gap: 16px;">
        <!-- 左侧：图片预览 Canvas -->
        <div style="flex-shrink: 0; display: flex; flex-direction: column; gap: 8px;">
          <canvas
            ref="cvCanvasRef"
            width="360" height="300"
            style="border: 1px solid var(--n-border-color); border-radius: 4px; cursor: crosshair; background: #f5f5f5;"
            @mousedown="onCVMouseDown"
            @mousemove="onCVMouseMove"
            @mouseup="onCVMouseUp"
            @mouseleave="onCVMouseUp"
          />
          <div v-if="cvOperation === 'crop'" style="font-size: 11px; color: #999; text-align: center;">
            在图片上拖动鼠标选择裁剪区域
          </div>
        </div>
        <!-- 右侧：参数面板 -->
        <div style="flex: 1; min-width: 0; overflow-y: auto; max-height: 450px;">
      <NForm label-placement="left" label-width="80">
        <NFormItem :label="t('views.network.label_cn_de9cc3dd')">
          <div style="display: flex; flex-direction: column; gap: 8px;">
            <div v-for="group in operationGroups" :key="group.label" style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 12px; color: #999; width: 60px;">{{ group.label }}</span>
              <NButton
                v-for="op in group.ops" :key="op"
                :type="cvOperation === op ? 'primary' : 'default'"
                size="tiny"
                @click="onCVOpChange(op)"
              >
                {{ op }}
              </NButton>
            </div>
          </div>
        </NFormItem>
          <NFormItem v-if="cvOperation === 'resize'" :label="t('views.network.label_cn_c8339fd2')">
          <NSpace>
            <NInputNumber v-model:value="cvParams.width" :placeholder="t('views.network.placeholder_cn_c2847901')" :min="1" :max="10000" />
            <NInputNumber v-model:value="cvParams.height" :placeholder="t('views.network.placeholder_cn_babae8ea')" :min="0" :max="10000" />
          </NSpace>
        </NFormItem>
        <NFormItem v-if="cvOperation === 'rotate'" :label="t('views.network.label_cn_40d39c3b')">
            <NSpace align="center" vertical>
              <div style="font-size: 11px; color: #999;">拖动滑块实时预览旋转效果</div>
              <NSpace align="center">
            <NSlider v-model:value="cvParams.angle" :min="0" :max="360" :step="1" style="width: 200px;" @update:value="drawCanvas()" />
            <NInputNumber v-model:value="cvParams.angle" :min="0" :max="360" size="small" style="width: 80px;" />
              </NSpace>
              <NButton size="tiny" @click="drawCanvas()">刷新预览</NButton>
          </NSpace>
        </NFormItem>
          <NFormItem v-if="cvOperation === 'crop'" :label="t('views.network.label_cn_af67b0a2')">
          <NSpace vertical>
              <div style="font-size: 11px; color: #999;">左侧画布拖动选区后自动同步数值</div>
            <NSpace><span style="width: 30px;">X</span><NInputNumber v-model:value="cvParams.x" :min="0" size="small" /></NSpace>
            <NSpace><span style="width: 30px;">Y</span><NInputNumber v-model:value="cvParams.y" :min="0" size="small" /></NSpace>
            <NSpace><span style="width: 30px;t('views.network.label_cn_1b54418d')cvParams.width" :min="1" size="small" /></NSpace>
            <NSpace><span style="width: 30px;t('views.network.label_cn_1b61b036')cvParams.height" :min="1" size="small" /></NSpace>
          </NSpace>
        </NFormItem>
          <NFormItem v-if="cvOperation === 'flip'" :label="t('views.network.label_cn_a465db53')">
          <NSelect v-model:value="cvParams.direction" :options="[
            { label: '水平翻转', value: 1 }, { label: '垂直翻转', value: 0 }, { label: t('views.network.label_cn_a5eac949'), value: -1 }
          ]" />
        </NFormItem>
          <NFormItem v-if="cvOperation === 'border'" :label="t('views.network.label_cn_961534b4')">
          <NSpace vertical>
            <NSpace><NInputNumber v-model:value="cvParams.top" :min="0" size="small" :placeholder="t('views.network.placeholder_cn_af767b7e')" /></NSpace>
            <NSpace align="center"><NInputNumber v-model:value="cvParams.left" :min="0" size="small" :placeholder="t('views.network.placeholder_cn_d2aff141')" />
              <NColorPicker v-model:value="cvParams.color" :default-value="'#000000'" size="small" />
              <NInputNumber v-model:value="cvParams.right" :min="0" size="small" :placeholder="t('views.network.placeholder_cn_4d9c32c2')" /></NSpace>
            <NSpace><NInputNumber v-model:value="cvParams.bottom" :min="0" size="small" :placeholder="t('views.network.placeholder_cn_3850a186')" /></NSpace>
          </NSpace>
        </NFormItem>
          <NFormItem v-if="cvOperation === 'brightness'" :label="t('views.network.label_cn_cfd060d8')">
          <NSpace align="center">
            <NSlider v-model:value="cvParams.value" :min="0" :max="5" :step="0.1" style="width: 200px;" @update:value="drawCanvas()" />
            <NInputNumber v-model:value="cvParams.value" :min="0" :max="5" :step="0.1" size="small" style="width: 80px;" />
          </NSpace>
        </NFormItem>
          <NFormItem v-if="cvOperation === 'contrast'" :label="t('views.network.label_cn_adc0d88f')">
          <NSpace align="center">
            <NSlider v-model:value="cvParams.value" :min="0" :max="5" :step="0.1" style="width: 200px;" @update:value="drawCanvas()" />
            <NInputNumber v-model:value="cvParams.value" :min="0" :max="5" :step="0.1" size="small" style="width: 80px;" />
          </NSpace>
        </NFormItem>
          <NFormItem v-if="cvOperation === 'color_space'" :label="t('views.network.label_cn_8f5d2fd3')">
          <NSelect v-model:value="cvParams.target" :options="[
            { label: t('views.network.label_cn_678ac9a2'), value: 'GRAY' }, { label: 'HSV', value: 'HSV' }, { label: 'LAB', value: 'LAB' }, { label: 'RGB', value: 'RGB' }
          ]" />
        </NFormItem>
          <NFormItem v-if="cvOperation === 'blur'" :label="t('views.network.label_cn_6475031d')">
          <NSpace vertical>
            <NSpace><span style="width: 60px;t('views.network.label_cn_1552aba7')cvParams.kernel_size" :min="3" :max="31" size="small" /></NSpace>
            <NSpace><span style="width: 60px;">类型</span>
              <NSelect v-model:value="cvParams.type" size="small" :options="[
                { label: '高斯', value: 'gaussian' }, { label: '中值', value: 'median' }, { label: t('views.network.label_cn_8e126ead'), value: 'bilateral' }
              ]" /></NSpace>
          </NSpace>
        </NFormItem>
          <NFormItem v-if="cvOperation === 'morphology'" :label="t('views.network.label_cn_3c343574')">
          <NSpace vertical>
            <NSpace><span style="width: 60px;">操作</span>
              <NSelect v-model:value="cvParams.operation" size="small" :options="[
                { label: '腐蚀', value: 'erode' }, { label: '膨胀', value: 'dilate' }, { label: '开运算', value: 'open' }, { label: t('views.network.label_cn_7517eaf0'), value: 'close' }
              ]" /></NSpace>
            <NSpace><span style="width: 60px;t('views.network.label_cn_1552aba7')cvParams.kernel_size" :min="1" :max="15" size="small" /></NSpace>
            <NSpace><span style="width: 60px;t('views.network.label_cn_bc13a83e')cvParams.iterations" :min="1" :max="10" size="small" /></NSpace>
          </NSpace>
        </NFormItem>
          <NFormItem v-if="cvOperation === 'smooth'" :label="t('views.network.label_cn_219fb25a')">
          <NSpace vertical>
            <NSpace><span style="width: 60px;">方法</span>
              <NSelect v-model:value="cvParams.method" size="small" :options="[
                { label: '双边滤波', value: 'bilateral' }, { label: t('views.network.label_cn_48c27c2e'), value: 'nlmeans' }
              ]" /></NSpace>
            <NSpace><span style="width: 60px;t('views.network.label_cn_f068c426')cvParams.h" :min="1" :max="100" size="small" /></NSpace>
          </NSpace>
        </NFormItem>
          <NFormItem v-if="cvOperation === 'histogram_eq'" :label="t('views.network.label_cn_34bbeded')">
          <NSpace vertical>
            <NSpace><span style="width: 60px;">方法</span>
              <NSelect v-model:value="cvParams.method" size="small" :options="[
                { label: t('views.network.label_cn_5c4b14f0'), value: 'global' }, { label: 'CLAHE', value: 'clahe' }
              ]" /></NSpace>
            <NSpace v-if="cvParams.method === 'clahe'"><span style="width: 60px;t('views.network.label_cn_c9f59a1e')cvParams.clip_limit" :min="0.1" :max="10" :step="0.1" size="small" /></NSpace>
          </NSpace>
        </NFormItem>
          <NFormItem v-if="cvOperation === 'remove_bg'" :label="t('views.network.label_cn_a9cec4ef')">
          <NSpace vertical>
            <NSpace><span style="width: 60px;">方法</span>
              <NSelect v-model:value="cvParams.method" size="small" :options="[
                { label: 'GrabCut', value: 'grabcut' }, { label: t('views.network.label_cn_e01d3656'), value: 'threshold' }
              ]" /></NSpace>
            <NSpace><span style="width: 60px;t('views.network.label_cn_1663d7c7')cvParams.margin" :min="0" :max="100" size="small" /></NSpace>
          </NSpace>
        </NFormItem>
      </NForm>
        </div>
      </div>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showCVModal = false">取消</NButton>
          <NButton @click="onCVPreview" :loading="cvPreviewLoading" secondary>预览效果</NButton>
          <NButton type="primary" @click="onCVSubmit">开始处理</NButton>
        </NSpace>
      </template>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.dual-panel-layout {
  display: flex;
  height: calc(100vh - 220px);
  overflow: hidden;
  gap: 0;
}
.left-panel {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.right-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 拖拽分隔条 */
.resize-handle {
  width: 6px;
  flex-shrink: 0;
  cursor: col-resize;
  background: var(--n-border-color, #e5e7eb);
  transition: background 0.15s;
  border-radius: 3px;
  margin: 0 4px;
}
.resize-handle:hover,
.is-resizing .resize-handle {
  background: var(--n-color-primary, #2080f0);
}
.is-resizing {
  user-select: none;
  cursor: col-resize;
}

.left-panel :deep(.n-card__content) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.right-panel :deep(.n-card__content) {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.empty-preview {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-content {
  overflow: auto;
}

/* 预览工具栏 */
.preview-toolbar {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px 0 8px 0;
  border-bottom: 1px solid var(--n-border-color, #e5e7eb);
  margin-bottom: 8px;
}
.preview-scale-label {
  font-size: 12px;
  min-width: 40px;
  text-align: center;
  color: #666;
}

/* 图片预览容器 */
.preview-image-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100px;
  overflow: hidden;
  padding: 4px;
  background: var(--n-color-embedded, #fafafa);
  border-radius: 8px;
}

/* GPS 地图 */
.preview-map {
  margin-top: 12px;
}
.preview-map-label {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #666;
  display: flex;
  align-items: center;
  gap: 4px;
}
.map-container {
  width: 100%;
  height: 200px;
  border-radius: 8px;
  border: 1px solid var(--n-border-color, #e5e7eb);
  z-index: 0;
}

/* ── 移动端适配（≤768px）── */
@media (max-width: 768px) {
  /* 选择器栏：全宽堆叠 */
  :deep(.n-space--wrap) {
    gap: 6px;
  }
  /* 选择器在小屏上全宽 */
  :deep(.n-space--wrap .n-base-selection) {
    width: 100% !important;
  }

  /* 双面板 → 垂直堆叠 */
  .dual-panel-layout {
    flex-direction: column;
    height: auto;
    height: calc(100dvh - 180px);
    min-height: 400px;
    gap: 0;
  }

  /* 左面板：上半部分，动态高度 */
  .left-panel {
    width: 100% !important;
    flex-shrink: 1;
    max-height: 50vh;
    min-height: 160px;
    border-radius: 6px 6px 0 0;
  }

  /* 分隔条：移动端垂直堆叠时隐藏 */
  .resize-handle {
    display: none;
  }

  /* 右面板：下半部分 */
  .right-panel {
    flex: 1;
    min-height: 150px;
    border-radius: 0 0 6px 6px;
  }

  /* 工具栏按钮：紧凑换行 */
  .left-panel :deep(.n-card__content) > div:first-child > div:first-child {
    gap: 4px;
  }

  /* 表格：水平滚动 + 缩小字号 */
  :deep(.n-data-table) {
    font-size: 12px;
  }

  /* CV 弹窗：全宽 */
  :deep(.n-modal) {
    max-width: 96vw !important;
  }

  /* 图片预览 */
  .preview-image-wrap img {
    max-height: 200px !important;
  }

  /* GPS 地图 */
  .map-container {
    height: 150px;
  }
}
</style>