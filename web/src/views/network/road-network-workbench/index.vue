<script setup>
import { computed, h, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import {


  NButton, NCard, NCheckbox, NDataTable, NInput, NInputNumber,
  NModal, NSelect, NSpace, NSpin, NTabPane, NTabs, NTag, useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'
import { useTaskProgressStore } from '@/store/modules/taskProgress'

const { t } = useI18n()

defineOptions({ name: i18n.global.t('views.network.roadNetworkWorkbench.title') })
const message = useMessage()

// ── 底图图层 ──
const baseLayers = [
  { label: 'Stadia Outdoors', value: 'outdoors', url: 'https://tiles.stadiamaps.com/tiles/outdoors/{z}/{x}/{y}.png?api_key=51f5f64e-7006-4a22-9bfb-86357ce5530c', attribution: '&copy; Stadia Maps' },
  { label: 'Stadia Dark', value: 'dark', url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}.png?api_key=51f5f64e-7006-4a22-9bfb-86357ce5530c', attribution: '&copy; Stadia Maps' },
  { label: 'Stadia Toner', value: 'toner', url: 'https://tiles.stadiamaps.com/tiles/stamen_toner/{z}/{x}/{y}.png?api_key=51f5f64e-7006-4a22-9bfb-86357ce5530c', attribution: '&copy; Stadia Maps' },
  { label: 'Stadia Imagery', value: 'imagery', url: 'https://tiles.stadiamaps.com/data/imagery/{z}/{x}/{y}.jpg', attribution: '&copy; Stadia Maps' },
  { label: 'Yandex Map', value: 'yandex', url: 'https://core-renderer-tiles.maps.yandex.net/tiles?l=map&v=3.2008.0&x={x}&y={y}&z={z}&scale=1&lang=ru_RU', attribution: '&copy; Yandex' },
  { label: 'Yandex Satellite', value: 'yandex-sat', url: 'https://core-sat.maps.yandex.net/tiles?l=sat&v=3.2008.0&x={x}&y={y}&z={z}&scale=1&lang=ru_RU', attribution: '&copy; Yandex' },
  { label: 'Bing Satellite', value: 'bing', url: 'https://ecn.t3.tiles.virtualearth.net/tiles/a{q}.jpeg?g=0&dir=dir_n{z}', attribution: '&copy; Microsoft', quadkey: true },
  { label: 'OpenStreetMap', value: 'osm', url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: '&copy; OSM' },
  { label: 'Google Satellite', value: 'google-sat', url: 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attribution: '&copy; Google' },
  // ── 通过后端代理转发的底图（后端从系统配置读取 download_proxy 发起请求）──
  { label: t('views.network.label_google_sat_cn_2a004f97'), value: 'google-sat-proxy', targetTemplate: 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attribution: '&copy; Google', proxy: true },
  { label: t('views.network.label_bing_sat_cn_814bdbcf'), value: 'bing-proxy', targetTemplate: 'https://ecn.t3.tiles.virtualearth.net/tiles/a{q}.jpeg?g=0&dir=dir_n{z}', attribution: '&copy; Microsoft', proxy: true, quadkey: true },
  { label: t('views.network.label_yandex_map_cn_afaa6170'), value: 'yandex-proxy', targetTemplate: 'https://core-renderer-tiles.maps.yandex.net/tiles?l=map&v=3.2008.0&x={x}&y={y}&z={z}&scale=1&lang=ru_RU', attribution: '&copy; Yandex', proxy: true },
  { label: t('views.network.label_yandex_sat_cn_e9a6bd97'), value: 'yandex-sat-proxy', targetTemplate: 'https://core-sat.maps.yandex.net/tiles?l=sat&v=3.2008.0&x={x}&y={y}&z={z}&scale=1&lang=ru_RU', attribution: '&copy; Yandex', proxy: true },
]
const selectedBaseLayer = ref('outdoors')

// ── Bing Maps quadkey 转换 ──
function toQuadKey(x, y, z) {
  let key = ''
  for (let i = z; i > 0; i--) {
    let digit = 0
    const mask = 1 << (i - 1)
    if ((x & mask) !== 0) digit += 1
    if ((y & mask) !== 0) digit += 2
    key += digit.toString()
  }
  return key
}

// ── 创建兼容底图图层 ──
function createBaseTileLayer(layer) {
  const opts = { attribution: layer.attribution, maxZoom: 19 }

  // 代理模式：通过后端转发瓦片请求（后端从系统配置读取 download_proxy）
  if (layer.proxy) {
    const proxyBase = `${tileApiBase.value}/region/road-network/tile-proxy`
    return L.tileLayer('', {
      ...opts,
      getTileUrl: (coords) => {
        let targetUrl = layer.targetTemplate
        if (layer.quadkey) {
          const qk = toQuadKey(coords.x, coords.y, coords.z)
          targetUrl = layer.targetTemplate.replace('{q}', qk).replace('{z}', coords.z)
        } else {
          targetUrl = layer.targetTemplate
            .replace('{x}', coords.x)
            .replace('{y}', coords.y)
            .replace('{z}', coords.z)
        }
        const encoded = btoa(targetUrl)
        return `${proxyBase}/${coords.z}/${coords.x}/${coords.y}.png?url=${encodeURIComponent(encoded)}`
      },
    })
  }

  if (layer.quadkey) {
    // Bing: 用自定义 getTileUrl 将 x/y/z 转为 quadkey
    return L.tileLayer('', {
      ...opts,
      getTileUrl: (coords) => {
        const qk = toQuadKey(coords.x, coords.y, coords.z)
        return layer.url.replace('{q}', qk).replace('{z}', coords.z)
      },
    })
  }
  if (layer.value === 'google-sat') {
    // Google: 多子域名防限流
    return L.tileLayer(layer.url, {
      ...opts,
      subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
    })
  }
  return L.tileLayer(layer.url, opts)
}

// ── 三级选择器 ──
const treeData = ref([])
const selectedCountry = ref(null)
const selectedRegion = ref(null)
const selectedNetwork = ref(null)
const networkList = ref([])
const loading = ref(false)

// ── 路网分析数据 ──
const networkInfo = ref(null)
const highwayTypes = ref([])
const analyzeLoading = ref(false)
const viewportCenter = ref(null)
const viewportZoom = ref(null)

// ── Leaflet ──
const mapContainer = ref(null)
const mapWrapper = ref(null)
let mapInstance = null
let baseTileLayer = null   // 底图图层引用
let roadTileLayer = null   // 路网瓦片图层（替代原来的 L.geoJSON）
let mapResizeObserver = null // 地图容器尺寸变化观察器

// ── TAB ──
const activeTab = ref('filter')

// ── 控件可见性 ──
const controlVisible = ref({
  compass: true,
  legend: true,
  scale: true,
  coords: true,
})

function toggleControl(key) {
  controlVisible.value[key] = !controlVisible.value[key]
  applyControlDOM()
}

function applyControlDOM() {
  if (!mapWrapper.value) return
  const root = mapWrapper.value
  const v = controlVisible.value
  ;['compass','legend','scale','coords'].forEach(k => {
    const sel = { compass: '.leaflet-compass', legend: '.map-legend', scale: '.leaflet-control-scale', coords: '.map-coords' }[k]
    const el = root.querySelector(sel)
    if (el) el.style.display = v[k] ? '' : 'none'
  })
}

const selectedHighways = ref([])
const filterLoading = ref(false)
const segmentLength = ref(1000)
const segmentLoading = ref(false)

// ── 路网渲染配置 ──
const styleColors = ref({})
const styleWeights = ref({})
const styleLoading = ref(false)

// ── 拖拽分隔条（Pointer 事件，同时支持鼠标和触屏）──
const LK_SPLIT = 'rwb_split_pct'
const LK_MAIN_H = 'rwb_main_h_pct'
const splitPercent = ref(Number(localStorage.getItem(LK_SPLIT)) || 75)
const isDragging = ref(false)
const workbenchRef = ref(null)

function onResizerPointerDown(e) {
  isDragging.value = true
  e.target.setPointerCapture(e.pointerId)
  e.preventDefault()
}

function onResizerPointerMove(e) {
  if (!isDragging.value || !workbenchRef.value) return
  const rect = workbenchRef.value.getBoundingClientRect()
  const pct = ((e.clientX - rect.left) / rect.width) * 100
  splitPercent.value = Math.max(30, Math.min(85, pct))
}

function onResizerPointerUp(e) {
  if (!isDragging.value) return
  isDragging.value = false
  e.target.releasePointerCapture(e.pointerId)
  if (mapInstance) mapInstance.invalidateSize()
  localStorage.setItem(LK_SPLIT, splitPercent.value)
}

// ── 垂直拖拽（地图区 ↔ TAB 功能区）──
const mainHeightPercent = ref(Number(localStorage.getItem(LK_MAIN_H)) || 60)
const isHDragging = ref(false)
const fullscreenRefLocal = ref(null)  // 不用 fullscreenRef（已被全屏占用），另取一个

function onHResizerPointerDown(e) {
  isHDragging.value = true
  e.target.setPointerCapture(e.pointerId)
  e.preventDefault()
}

function onHResizerPointerMove(e) {
  if (!isHDragging.value) return
  const el = fullscreenRef.value || fullscreenRefLocal.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  // 排除选择栏高度（约 40px）
  const topOffset = 44
  const availH = rect.height - topOffset - 8  // 8px 分隔条
  const pct = ((e.clientY - rect.top - topOffset) / availH) * 100
  mainHeightPercent.value = Math.max(25, Math.min(80, pct))
}

function onHResizerPointerUp(e) {
  if (!isHDragging.value) return
  isHDragging.value = false
  e.target.releasePointerCapture(e.pointerId)
  if (mapInstance) mapInstance.invalidateSize()
  localStorage.setItem(LK_MAIN_H, mainHeightPercent.value)
}

// ── 颜色映射 ──
const highwayColors = {
  motorway: '#e64a19', motorway_link: '#e64a19',
  trunk: '#d84315', trunk_link: '#d84315',
  primary: '#ef6c00', primary_link: '#ef6c00',
  secondary: '#f9a825', secondary_link: '#f9a825',
  tertiary: '#43a047', tertiary_link: '#43a047',
  residential: '#1e88e5', living_street: '#1e88e5',
  unclassified: '#9e9e9e', road: '#9e9e9e',
  service: '#757575', footway: '#a1887f',
  cycleway: '#66bb6a', path: '#8d6e63',
  track: '#795548', pedestrian: '#ffb74d',
}
function getColor(hw) { return highwayColors[hw] || '#9e9e9e' }

// ── 初始化地图 ──
function initMap() {
  if (mapInstance) return

  // 防御：确保容器有可见尺寸（移动端布局可能尚未完成）
  const container = mapContainer.value
  if (!container || container.clientWidth === 0 || container.clientHeight === 0) {
    // 延迟重试（移动端布局渲染较慢）
    setTimeout(() => initMap(), 100)
    return
  }

  const layer = baseLayers.find(l => l.value === selectedBaseLayer.value)
  mapInstance = L.map(container, { zoomControl: true, attributionControl: true }).setView([35, 105], 4)
  baseTileLayer = createBaseTileLayer(layer).addTo(mapInstance)
  mapInstance.on('zoomend moveend', onMapMove)

  // ── ResizeObserver：监听容器尺寸变化，自动校准地图 ──
  if (typeof ResizeObserver !== 'undefined') {
    mapResizeObserver = new ResizeObserver(() => {
      if (mapInstance) mapInstance.invalidateSize()
    })
    mapResizeObserver.observe(container)
  }

  // ── 二次校准：Layout 完成后强制重算（解决移动端首次加载不触发 ResizeObserver 的问题）──
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      if (mapInstance) mapInstance.invalidateSize()
    })
  })

  // 比例尺
  L.control.scale({ metric: true, imperial: false, position: 'bottomleft' }).addTo(mapInstance)

  // 方位罗盘（右上角）
  const CompassControl = L.Control.extend({
    onAdd: function () {
      const div = L.DomUtil.create('div', 'leaflet-compass')
      div.innerHTML = `
        <div class="compass-outer">
          <div class="compass-ring">
            <span class="compass-dir dir-n">N</span>
            <span class="compass-dir dir-e">E</span>
            <span class="compass-dir dir-s">S</span>
            <span class="compass-dir dir-w">W</span>
            <svg class="compass-ticks" viewBox="0 0 100 100">
              <line x1="50" y1="8"  x2="50" y2="16" stroke="#bbb" stroke-width="1.5"/>
              <line x1="50" y1="84" x2="50" y2="92" stroke="#bbb" stroke-width="1.5"/>
              <line x1="8"  y1="50" x2="16" y2="50" stroke="#bbb" stroke-width="1.5"/>
              <line x1="84" y1="50" x2="92" y2="50" stroke="#bbb" stroke-width="1.5"/>
            </svg>
            <div class="compass-needle">
              <div class="needle-north"></div>
              <div class="needle-south"></div>
            </div>
          </div>
        </div>`
      return div
    },
  })
  new CompassControl({ position: 'topright' }).addTo(mapInstance)

  // 图层导出按钮（缩放控件下方）
  const ExportControl = L.Control.extend({
    onAdd: function () {
      const div = L.DomUtil.create('div', 'leaflet-export-btn')
      div.title = t('views.network.title_cn_d35c5853')
      div.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="#555"><path d="M19 12v7H5v-7H3v7c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zm-6 .67l2.59-2.58L17 11.5l-5 5-5-5 1.41-1.41L11 12.67V3h2v9.67z"/></svg>'
      L.DomEvent.on(div, 'click', function (e) {
        L.DomEvent.stopPropagation(e)
        openExportModal()
      })
      return div
    },
  })
  new ExportControl({ position: 'topleft' }).addTo(mapInstance)
}

function switchBaseLayer(value) {
  if (!mapInstance) return
  selectedBaseLayer.value = value
  // 只移除底图，保留路网瓦片
  if (baseTileLayer) {
    mapInstance.removeLayer(baseTileLayer)
    baseTileLayer = null
  }
  const layer = baseLayers.find(l => l.value === value)
  baseTileLayer = createBaseTileLayer(layer).addTo(mapInstance)
  // 确保路网图层在底图之上
  if (roadTileLayer) roadTileLayer.bringToFront()
}

// ── 瓦片图层管理（替代原来的 L.geoJSON 渲染） ──

const cacheVersion = ref(0)

const tileApiBase = computed(() => {
  const base = import.meta.env.VITE_BASE_API || ''
  return base.replace(/\/$/, '')
})

function buildTileUrl(networkId, types) {
  // 防御：确保 types 是字符串数组，过滤掉非字符串值
  const safe = (Array.isArray(types) ? types : [])
    .filter(t => typeof t === 'string' && t.length > 0 && t.length < 50)
    .map(t => t.replace(/[^a-z_]/g, ''))
  let params = safe.length ? `?types=${safe.join(',')}` : '?'
  params += `${params.includes('?') && params.length > 1 ? '&' : ''}_v=${cacheVersion.value}`
  return `${tileApiBase.value}/region/road-network/tiles/${networkId}/{z}/{x}/{y}.png${params}`
}

function updateTileLayer() {
  if (!mapInstance || !selectedNetwork.value) return

  // 移除旧瓦片图层
  if (roadTileLayer) {
    mapInstance.removeLayer(roadTileLayer)
    roadTileLayer = null
  }

  const url = buildTileUrl(selectedNetwork.value, selectedHighways.value)
  roadTileLayer = L.tileLayer(url, {
    maxZoom: 19,
    minZoom: 8,
    opacity: 0.85,
    errorTileUrl: '',  // 空字符串 = 加载失败时不显示占位图
  }).addTo(mapInstance)
  roadTileLayer.bringToFront()
}

// ── 实时视图追踪 ──
const liveZoom = ref(4)
const liveCenter = ref({ lat: 35, lon: 105 })

function onMapMove() {
  if (!mapInstance) return
  const c = mapInstance.getCenter()
  liveZoom.value = mapInstance.getZoom()
  liveCenter.value = { lat: +c.lat.toFixed(4), lon: +c.lng.toFixed(4) }
}

// ── 图层导出 ──
const showExportModal = ref(false)
const selectedExportLayers = ref([])
const exportLayerPreview = ref(false)
const exportName = ref('')
const exportLoading = ref(false)
const exportProgress = ref('')

const exportLayerOptions = computed(() => {
  const layers = []
  const bl = baseLayers.find(l => l.value === selectedBaseLayer.value)
  if (bl) layers.push({ key: 'basemap', label: `底图 — ${bl.label}`, type: 'basemap' })
  if (roadTileLayer && selectedNetwork.value) {
    const nw = networkList.value.find(n => n.id === selectedNetwork.value)
    layers.push({ key: 'road', label: `路网 — ${nw?.file_name || '当前路网'}`, type: 'road' })
  }
  // 控件图层
  layers.push(
    { key: 'compass', label: t('views.network.label_cn_5bc1ed6c'), type: 'control' },
    { key: 'legend', label: t('views.network.label_cn_9d7b554a'), type: 'control' },
    { key: 'scale', label: t('views.network.label_cn_3aefa0b5'), type: 'control' },
    { key: 'coords', label: t('views.network.label_cn_8ba51a39'), type: 'control' },
  )
  return layers
})

function openExportModal() {
  if (!selectedRegion.value) { message.warning(t('views.network.message_cn_f13e2993')); return }
  selectedExportLayers.value = exportLayerOptions.value.map(l => l.key)
  exportLayerPreview.value = false
  exportName.value = `地图导出_${new Date().toLocaleString('zh-CN')}`
  showExportModal.value = true
}

function toggleExportPreview() {
  exportLayerPreview.value = !exportLayerPreview.value
  if (exportLayerPreview.value) {
    // 预览模式：只显示选中的图层
    applyExportPreview()
  } else {
    // 恢复全部图层
    restoreAllLayers()
  }
}

function applyExportPreview() {
  const sel = selectedExportLayers.value
  if (baseTileLayer) {
    sel.includes('basemap') ? baseTileLayer.setOpacity(1) : baseTileLayer.setOpacity(0)
  }
  if (roadTileLayer) {
    sel.includes('road') ? roadTileLayer.setOpacity(0.85) : roadTileLayer.setOpacity(0)
  }
}

function restoreAllLayers() {
  if (baseTileLayer) baseTileLayer.setOpacity(1)
  if (roadTileLayer) roadTileLayer.setOpacity(0.85)
}

async function doExportLayers() {
  if (!selectedExportLayers.value.length) { message.warning(t('views.network.message_cn_a4ea0f49')); return }
  if (!selectedRegion.value) { message.warning(t('views.network.message_cn_f13e2993')); return }

  exportLoading.value = true
  exportProgress.value = t('views.network.label_cn_eaeef6e8')

  try {
    // Canvas 仅能处理同源路网瓦片；底图（跨域）或控件需 html-to-image
    const hasCrossOrigin = selectedExportLayers.value.some(k => {
      const type = exportLayerOptions.value.find(l => l.key === k)?.type
      return type === 'control' || type === 'basemap'
    })

    hideUIControls()
    if (hasCrossOrigin) applyControlVisibility()

    let blob
    if (hasCrossOrigin) {
      // 底图/控件：html-to-image 截取完整地图容器
      await new Promise(r => setTimeout(r, 400))
      await waitForTiles()
      blob = await captureFullMap()
    } else {
      // 仅瓦片：Canvas 合成，透明背景
      await new Promise(r => setTimeout(r, 500))
      await waitForTiles()
      blob = await captureTilesToBlob()
    }

    restoreAllExportVisibility()

    if (!blob) {
      showExportModal.value = false
      return
    }

    // 上传到路网素材
    exportProgress.value = t('views.network.label_cn_d790356c')

    // 构建元数据
    const center = mapInstance ? mapInstance.getCenter() : null
    const zoom = mapInstance ? mapInstance.getZoom() : null
    const meta = {
      center: center ? { lat: +center.lat.toFixed(6), lon: +center.lng.toFixed(6) } : null,
      zoom,
      camera: 'VansRSA',
      author: 'VansRSA',
      network_stats: networkInfo.value ? {
        total_length_km: networkInfo.value.total_length_km,
        total_length_m: networkInfo.value.total_length_m,
        node_count: networkInfo.value.node_count,
        edge_count: networkInfo.value.edge_count,
      } : null,
      exported_layers: [...selectedExportLayers.value],
      base_layer: selectedBaseLayer.value,
    }
    const description = JSON.stringify(meta, null, 2)

    const file = new File([blob], `road_export_${Date.now()}.png`, { type: 'image/png' })
    await api.uploadMaterial(selectedRegion.value, exportName.value, description, file, t('views.network.roadNetworkWorkbench.title'))
    message.success(t('views.network.message_cn_26ea4d51'))
    showExportModal.value = false
  } catch (e) {
    restoreAllExportVisibility()
    message.error(t('views.network.message_cn_2e0d8c60') + (e?.message || e))
  } finally {
    exportLoading.value = false
    exportProgress.value = ''
  }
}

/** 隐藏 UI 控件（缩放/导出按钮 — 始终不出现于截图中） */
function hideUIControls() {
  if (!mapWrapper.value) return
  const root = mapWrapper.value
  const zoomCtrl = root.querySelector('.leaflet-control-zoom')
  if (zoomCtrl) zoomCtrl.style.display = 'none'
  const exportBtn = root.querySelector('.leaflet-export-btn')
  if (exportBtn) exportBtn.style.display = 'none'
}

/** 内容控件按选择显示/隐藏 */
function applyControlVisibility() {
  if (!mapWrapper.value) return
  const root = mapWrapper.value
  const sel = selectedExportLayers.value
  const compass = root.querySelector('.leaflet-compass')
  if (compass) compass.style.display = sel.includes('compass') ? '' : 'none'
  const legend = root.querySelector('.map-legend')
  if (legend) legend.style.display = sel.includes('legend') ? '' : 'none'
  const scale = root.querySelector('.leaflet-control-scale')
  if (scale) scale.style.display = sel.includes('scale') ? '' : 'none'
  const coords = root.querySelector('.map-coords')
  if (coords) coords.style.display = sel.includes('coords') ? '' : 'none'
}

/** 恢复所有可见性 */
function restoreAllExportVisibility() {
  if (!mapWrapper.value) return
  const root = mapWrapper.value
  const zoomCtrl = root.querySelector('.leaflet-control-zoom')
  if (zoomCtrl) zoomCtrl.style.display = ''
  const exportBtn = root.querySelector('.leaflet-export-btn')
  if (exportBtn) exportBtn.style.display = ''
  const compass = root.querySelector('.leaflet-compass')
  if (compass) compass.style.display = ''
  const legend = root.querySelector('.map-legend')
  if (legend) legend.style.display = ''
  const scale = root.querySelector('.leaflet-control-scale')
  if (scale) scale.style.display = ''
  const coords = root.querySelector('.map-coords')
  if (coords) coords.style.display = ''
}

/** 从 Leaflet tile 提取实际 <img>（el 可能是 div 包裹 img） */
function getTileImage(tile) {
  if (!tile) return null
  const el = tile.el || tile
  if (!el) return null
  if (el instanceof HTMLImageElement) return el
  if (el instanceof HTMLElement) {
    const img = el.querySelector('img')
    if (img) return img
  }
  return null
}
/** 等待瓦片加载 */
function waitForTiles() {
  return new Promise((resolve) => {
    const layers = []
    if (selectedExportLayers.value.includes('road') && roadTileLayer) layers.push(roadTileLayer)
    if (selectedExportLayers.value.includes('basemap') && baseTileLayer) layers.push(baseTileLayer)
    if (!layers.length) return resolve()

    let remaining = 3
    const check = () => {
      let pending = 0
      for (const layer of layers) {
        const tiles = layer._tiles || {}
        for (const key in tiles) {
          const img = getTileImage(tiles[key])
          if (img && !img.complete) pending++
        }
      }
      if (pending === 0 || --remaining <= 0) {
        console.log(`[capture] tiles ready, pending=${pending}`)
        resolve()
      } else {
        setTimeout(check, 600)
      }
    }
    check()
  })
}

/** 完整地图容器截取（含控件） */
function captureFullMap() {
  if (!mapWrapper.value) return null
  // htmlToImage 全局可用（index.html 中引入）
  return htmlToImage.toBlob(mapWrapper.value, {
    backgroundColor: null, // 透明背景
    pixelRatio: 1,
    skipAutoScale: true,
    skipFonts: true,
  }).catch(() => null)
}

/** 仅瓦片截取（透明背景） */
async function captureTilesToBlob() {
  if (!mapInstance) return null
  const size = mapInstance.getSize()
  const canvas = document.createElement('canvas')
  canvas.width = size.x
  canvas.height = size.y
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, size.x, size.y)

  let hasContent = false

  function drawTilesFromLayer(tileLayer) {
    if (!tileLayer) return 0
    const tiles = tileLayer._tiles || {}
    const mapEl = mapContainer.value
    const mapRect = mapEl ? mapEl.getBoundingClientRect() : null
    let drawn = 0
    for (const key in tiles) {
      const tile = tiles[key]
      const img = getTileImage(tile)
      if (!img || !img.complete || img.naturalWidth === 0) continue
      if (mapRect) {
        const tileRect = img.getBoundingClientRect()
        const left = tileRect.left - mapRect.left
        const top = tileRect.top - mapRect.top
        try {
          ctx.drawImage(img, left, top); hasContent = true; drawn++
        } catch (_) {}
      }
    }
    return drawn
  }

  let roadCount = 0, baseCount = 0
  if (selectedExportLayers.value.includes('road')) roadCount = drawTilesFromLayer(roadTileLayer)
  if (selectedExportLayers.value.includes('basemap')) baseCount = drawTilesFromLayer(baseTileLayer)

  if (!hasContent) return null
  return new Promise(resolve => canvas.toBlob(resolve, 'image/png'))
}

// 弹窗关闭时恢复图层
function onExportModalClose() {
  if (exportLayerPreview.value) {
    restoreAllLayers()
    exportLayerPreview.value = false
  }
}

// ── 图例 ──
const legendTypes = computed(() =>
  highwayTypes.value.map(hw => ({
    type: typeof hw === 'string' ? hw : hw.type,
    name_zh: typeof hw === 'string' ? hw : (hw.name_zh || hw.type),
    color: getColor(typeof hw === 'string' ? hw : hw.type),
  }))
)

// ── 数据加载 ──
onMounted(async () => {
  const res = await api.getRegionTree()
  treeData.value = res.data || []
  loadTemplates()

  // 修正 Leaflet 默认图标路径（本地库）
  if (typeof L !== 'undefined' && L.Icon && L.Icon.Default) {
    delete L.Icon.Default.prototype._getIconUrl
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: '/lib/leaflet/images/marker-icon-2x.png',
      iconUrl: '/lib/leaflet/images/marker-icon.png',
      shadowUrl: '/lib/leaflet/images/marker-shadow.png',
    })
  }

  // ── 使用双重 rAF + setTimeout 确保 CSS 布局在移动端完整计算后再初始化地图 ──
  await nextTick()
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      setTimeout(() => initMap(), 50)
    })
  })
})

onUnmounted(() => {
  if (mapResizeObserver) { mapResizeObserver.disconnect(); mapResizeObserver = null }
  if (mapInstance) { mapInstance.remove(); mapInstance = null }
})

function flattenTree(nodes, level = 0) {
  const result = []
  for (const n of nodes) {
    result.push({ ...n, _level: level })
    if (n.children) result.push(...flattenTree(n.children, level + 1))
  }
  return result
}
const allRegions = computed(() => flattenTree(treeData.value))

function displayLabel(node) {
  return node.local_name ? `${node.label}（${node.local_name}）` : node.label
}
const countryOptions = computed(() =>
  allRegions.value.filter(r => r.region_type === 'COUNTRY').map(r => ({ label: displayLabel(r), value: r.id }))
)
const regionOptions = computed(() =>
  allRegions.value.filter(r => r.parent_id === selectedCountry.value || (selectedCountry.value && r._level > 0))
    .map(r => ({ label: '　'.repeat(r._level) + displayLabel(r), value: r.id }))
)
const networkOptions = computed(() =>
  networkList.value.map(n => ({ label: `${n.file_name} (${n.node_count}${t('views.network.roadNetworkWorkbench.stats.nodesShort')})`, value: n.id }))
)

async function onCountryChange(id) {
  selectedCountry.value = id; selectedRegion.value = null; selectedNetwork.value = null; networkList.value = []; clearData()
}
async function onRegionChange(id) {
  selectedRegion.value = id; selectedNetwork.value = null; networkList.value = []; clearData()
  try {
    const res = await api.getRoadNetworksForRegion(id)
    networkList.value = res.data || []
  } catch (_) { networkList.value = [] }
}
async function onNetworkChange(id) {
  if (!id) { clearData(); return }
  selectedNetwork.value = id
  await loadAnalysis(id)
  loadFields()
}
function clearData() {
  networkInfo.value = null; highwayTypes.value = []
  viewportCenter.value = null; viewportZoom.value = null
  fieldsData.value = []; fieldsTotal.value = 0; fieldsDefs.value = []; fieldsPage.value = 1
  if (roadTileLayer) { mapInstance?.removeLayer(roadTileLayer); roadTileLayer = null }
}

async function loadAnalysis(networkId) {
  analyzeLoading.value = true
  try {
    const res = await api.analyzeNetwork({ network_id: networkId })
    const d = res.data || {}
    networkInfo.value = d.info
    // highway_types: [{type, name_zh}, ...]
    highwayTypes.value = d.highway_types || []
    // selectedHighways 保持字符串列表（用于 API 调用）
    selectedHighways.value = (d.highway_types || []).map(h => typeof h === 'string' ? h : h.type)
    await nextTick()
    updateTileLayer()
    viewportCenter.value = d.center
    viewportZoom.value = d.zoom
    // 自适应视野：优先 fitBounds（自动处理 padding + 右侧面板遮挡），回退 setView
    if (d.geojson && d.geojson.features?.length > 0) {
      try {
        const bounds = L.geoJSON(d.geojson).getBounds()
        if (bounds.isValid()) mapInstance.fitBounds(bounds, { padding: [30, 30] })
      } catch (_) {}
    } else if (d.center && d.center.lat && d.zoom) {
      mapInstance.setView([d.center.lat, d.center.lon], d.zoom)
    }
  } catch (_) {
    message.error(t('views.network.roadNetworkWorkbench.messages.analyzeFail'))
  } finally {
    analyzeLoading.value = false
  }
  // 后台预热图缓存（不阻塞 UI）
  api.warmTileCache({ network_id: networkId }).catch(() => {})
}

// ── TAB 功能 ──

// 筛选模板
const filterTemplates = ref([])
const selectedTemplate = ref(null)
const newTemplateName = ref('')
const showTemplateInput = ref(false)

async function loadTemplates() {
  try {
    const res = await api.getFilterTemplates()
    filterTemplates.value = (res.data || []).map(t_ => ({
      label: t_.name + (t_.is_preset ? ` (${t('views.network.roadNetworkWorkbench.tabs.filter.preset')})` : ''),
      value: t_.id,
      types: t_.selected_types,
      isPreset: t_.is_preset,
    }))
  } catch (_) { filterTemplates.value = [] }
}

function applyTemplate(id) {
  const tmpl = filterTemplates.value.find(t_ => t_.value === id)
  if (tmpl) {
    selectedHighways.value = [...tmpl.types]
    selectedTemplate.value = id
    message.success(t('views.network.roadNetworkWorkbench.messages.templateLoaded', { name: tmpl.label }))
  }
}

async function saveTemplate() {
  const name = newTemplateName.value.trim()
  if (!name) { message.warning(t('views.network.roadNetworkWorkbench.messages.enterTemplateName')); return }
  if (!selectedHighways.value.length) { message.warning(t('views.network.roadNetworkWorkbench.messages.selectHighwayFirst')); return }
  try {
    await api.createFilterTemplate({ name, selected_types: [...selectedHighways.value] })
    message.success(t('views.network.roadNetworkWorkbench.messages.templateSaved'))
    newTemplateName.value = ''
    showTemplateInput.value = false
    await loadTemplates()
  } catch (e) { message.error(e?.response?.data?.msg || t('views.network.roadNetworkWorkbench.messages.saveFail')) }
}

async function deleteTemplate() {
  if (!selectedTemplate.value) { message.warning(t('views.network.roadNetworkWorkbench.messages.selectTemplateFirst')); return }
  const tmpl = filterTemplates.value.find(t_ => t_.value === selectedTemplate.value)
  if (tmpl?.isPreset) { message.warning(t('views.network.roadNetworkWorkbench.messages.presetTemplateCannotDelete')); return }
  try {
    await api.deleteFilterTemplate({ template_id: selectedTemplate.value })
    message.success(t('views.network.roadNetworkWorkbench.messages.templateDeleted'))
    selectedTemplate.value = null
    await loadTemplates()
  } catch (e) { message.error(e?.response?.data?.msg || t('views.network.roadNetworkWorkbench.messages.deleteFail')) }
}

// 筛选条件变化 → 即时更新瓦片
watch(selectedHighways, () => {
  if (selectedNetwork.value && roadTileLayer) {
    updateTileLayer()
  }
}, { deep: true })

// ── 切换到渲染配置 tab 时加载最新配置 ──
watch(activeTab, (tab) => {
  if (tab === 'style') loadHighwayStyle()
})

async function onFilter() {
  if (!selectedNetwork.value || !selectedHighways.value.length) { message.warning(t('views.network.roadNetworkWorkbench.messages.selectHighwayFirst')); return }
  filterLoading.value = true
  try {
    await api.filterNetwork({ network_id: selectedNetwork.value, selected_types: selectedHighways.value, save_to_region: true })
    message.success(t('views.network.roadNetworkWorkbench.messages.filterSuccess'))
    onRegionChange(selectedRegion.value)
  } catch (_) { message.error(t('views.network.roadNetworkWorkbench.messages.filterFail')) } finally { filterLoading.value = false }
}

// ── 路网渲染配置 ──
async function loadHighwayStyle() {
  styleLoading.value = true
  try {
    const res = await api.getRoadHighwayStyle()
    if (res.data) {
      styleColors.value = res.data.colors || {}
      styleWeights.value = res.data.weights || {}
    }
  } catch (_) { /* ignore */ }
  styleLoading.value = false
}

function getHighwayColor(highway) {
  const c = styleColors.value[highway]
  if (!c) return '#9e9e9e'
  if (Array.isArray(c)) return `rgb(${c[0]},${c[1]},${c[2]})`
  return c
}

function setHighwayColor(highway, hexColor) {
  const r = parseInt(hexColor.slice(1, 3), 16)
  const g = parseInt(hexColor.slice(3, 5), 16)
  const b = parseInt(hexColor.slice(5, 7), 16)
  styleColors.value = { ...styleColors.value, [highway]: [r, g, b] }
}

async function saveHighwayStyle() {
  styleLoading.value = true
  try {
    await api.updateRoadHighwayStyle({ colors: styleColors.value, weights: styleWeights.value })
    message.success('渲染配置已保存，新瓦片将立即生效')
  } catch (_) { message.error('保存失败') }
  styleLoading.value = false
}

async function resetHighwayStyle() {
  styleLoading.value = true
  try {
    await api.resetRoadHighwayStyle()
    await loadHighwayStyle()
    message.success('已恢复默认渲染配置')
  } catch (_) { message.error('重置失败') }
  styleLoading.value = false
}

async function onSegment() {
  if (!selectedNetwork.value || !segmentLength.value) { message.warning(t('views.network.roadNetworkWorkbench.messages.enterSegmentLength')); return }
  segmentLoading.value = true
  try {
    await api.segmentNetwork({ network_id: selectedNetwork.value, segment_length: segmentLength.value, save_to_region: true })
    message.success(t('views.network.roadNetworkWorkbench.messages.segmentSuccess'))
    onRegionChange(selectedRegion.value)
  } catch (_) { message.error(t('views.network.roadNetworkWorkbench.messages.segmentFail')) } finally { segmentLoading.value = false }
}

async function onClearCache() {
  if (!selectedNetwork.value) { message.warning(t('views.network.roadNetworkWorkbench.messages.selectNetworkFirst')); return }
  try {
    await api.clearTileCache({ network_id: selectedNetwork.value })
    cacheVersion.value++
    updateTileLayer()
    message.success(t('views.network.roadNetworkWorkbench.messages.cacheCleared'))
  } catch (_) { message.error(t('views.network.roadNetworkWorkbench.messages.clearCacheFail')) }
}

// ── 全屏 ──
const fullscreenRef = ref(null)
const isFullscreen = ref(false)

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
  if (!isFullscreen.value && mapInstance) {
    // 退出全屏后重新计算地图大小
    setTimeout(() => mapInstance.invalidateSize(), 100)
  }
}

async function toggleFullscreen() {
  if (!fullscreenRef.value) return
  if (isFullscreen.value) {
    await document.exitFullscreen()
  } else {
    await fullscreenRef.value.requestFullscreen()
    if (mapInstance) {
      setTimeout(() => mapInstance.invalidateSize(), 200)
    }
  }
}

const _onWindowResize = () => {
  if (mapInstance) mapInstance.invalidateSize()
}
onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  window.addEventListener('resize', _onWindowResize)
})
onUnmounted(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  window.removeEventListener('resize', _onWindowResize)
  if (mapResizeObserver) { mapResizeObserver.disconnect(); mapResizeObserver = null }
  if (mapInstance) { mapInstance.remove(); mapInstance = null }
})

const statsColumns = [
  { title: t('views.network.roadNetworkWorkbench.statsDetail.label'), key: 'label', width: 120 },
  { title: t('views.network.roadNetworkWorkbench.statsDetail.value'), key: 'value' },
]

// ── 字段参数表 ──
const fieldsData = ref([])
const fieldsTotal = ref(0)
const fieldsPage = ref(1)
const fieldsPageSize = ref(50)
const fieldsLoading = ref(false)
const fieldsDefs = ref([])
const fieldsSearch = ref('')

const fieldsColumns = computed(() => {
  const cols = [
    { title: '#', key: 'u', width: 80, ellipsis: { tooltip: true } },
  ]
  for (const f of fieldsDefs.value) {
    cols.push({
      title: f, key: f, width: 120, ellipsis: { tooltip: true },
      render(row) {
        const v = row[f]
        return v != null ? String(v) : ''
      },
    })
  }
  cols.push({
    title: t('views.network.roadNetworkWorkbench.tabs.fields.colActions'), key: '_actions', width: 80, fixed: 'right',
    render(row) {
      return h(NButton, { size: 'tiny', onClick: () => openFieldEditor(row) }, { default: () => t('views.network.roadNetworkWorkbench.tabs.fields.edit') })
    },
  })
  return cols
})

const pendingEdits = ref([])  // [{ u, v, k, field, value }]
const showFieldEditor = ref(false)
const fieldEditRow = ref(null)
const fieldEditName = ref('')
const fieldEditValue = ref('')
const fieldsExporting = ref(false)
const fieldsImporting = ref(false)

function fieldRowKey(r) { return `${r.u}_${r.v}_${r.k || 0}` }

function openFieldEditor(row) {
  fieldEditRow.value = row
  fieldEditName.value = fieldsDefs.value[0] || ''
  fieldEditValue.value = ''
  showFieldEditor.value = true
}

function saveFieldEdit() {
  if (!fieldEditRow.value || !fieldEditName.value) return
  const row = fieldEditRow.value
  const edit = { u: row.u, v: row.v, k: row.k || 0, field: fieldEditName.value, value: fieldEditValue.value }
  const idx = pendingEdits.value.findIndex(e => e.u === edit.u && e.v === edit.v && e.k === edit.k && e.field === edit.field)
  if (idx >= 0) {
    pendingEdits.value[idx] = edit
  } else {
    pendingEdits.value.push(edit)
  }
  row[fieldEditName.value] = fieldEditValue.value
  showFieldEditor.value = false
}

function isRowEdited(row) {
  return pendingEdits.value.some(e => e.u === row.u && e.v === row.v && e.k === (row.k || 0))
}

// 导出全部边数据为 JSON 文件下载
async function exportFieldsJson() {
  if (!selectedNetwork.value) return
  fieldsExporting.value = true
  try {
    const res = await api.exportRoadFields({ network_id: selectedNetwork.value })
    const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `road_fields_${selectedNetwork.value}.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success(t('views.network.roadNetworkWorkbench.messages.exportSuccess'))
  } catch (_) { message.error(t('views.network.roadNetworkWorkbench.messages.exportFail')) }
  finally { fieldsExporting.value = false }
}

// 导入 JSON 文件
function importFieldsJson() {
  if (!selectedNetwork.value) return
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    fieldsImporting.value = true
    try {
      const text = await file.text()
      const data = JSON.parse(text)
      const edges = data.edges || data
      if (!Array.isArray(edges)) { message.error(t('views.network.roadNetworkWorkbench.messages.jsonFormatError')); return }
      await api.importRoadFields({ network_id: selectedNetwork.value, edges })
      message.success(t('views.network.roadNetworkWorkbench.messages.importSuccess'))
      pendingEdits.value = []
      loadFields()
      onRegionChange(selectedRegion.value)
    } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.importFail', { error: e?.message || e })) }
    finally { fieldsImporting.value = false }
  }
  input.click()
}

let _fieldsReqId = 0

async function loadFields() {
  if (!selectedNetwork.value) return
  const reqId = ++_fieldsReqId
  const netId = selectedNetwork.value
  fieldsLoading.value = true
  try {
    const res = await api.getRoadFields({
      network_id: netId,
      page: fieldsPage.value,
      page_size: fieldsPageSize.value,
      search: fieldsSearch.value,
    })
    // 竞态保护：已发新请求则丢弃旧响应
    if (reqId !== _fieldsReqId) return
    fieldsData.value = res.data || []
    fieldsTotal.value = res.total || 0
    // 从返回数据提取字段列表（仅首页时更新，避免重复计算）
    if (fieldsPage.value === 1 && fieldsData.value.length > 0) {
      const keys = new Set()
      fieldsData.value.forEach(r => Object.keys(r).forEach(k => { if (k !== 'u' && k !== 'v' && k !== 'k') keys.add(k) }))
      fieldsDefs.value = [...keys].sort()
    }
  } catch (_) {
    if (reqId === _fieldsReqId) fieldsData.value = []
  }
  finally {
    if (reqId === _fieldsReqId) fieldsLoading.value = false
  }
}

// 批量操作
const showBatchOp = ref(false)
const batchField = ref('')
const batchMode = ref('sanitize')
const batchValue = ref('')

async function runBatchOp() {
  if (!batchField.value) { message.warning(t('views.network.roadNetworkWorkbench.messages.selectTargetField')); return }
  try {
    const res = await api.batchUpdateRoadFields({
      network_id: selectedNetwork.value,
      field: batchField.value,
      mode: batchMode.value,
      value: batchMode.value === 'set' ? batchValue.value : '',
    })
    message.success(t('views.network.roadNetworkWorkbench.messages.batchOpSuccess', { count: res.data?.affected || 0 }))
    showBatchOp.value = false
    loadFields()
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.batchOpFail')) }
}

// ── AI 处理 ──
const showAIProcess = ref(false)
const aiProxyId = ref(null)
const skillId = ref(null)
const aiPrompt = ref('')
const aiProxyOptions = ref([])
const aiProxyLoading = ref(false)
const skillOptions = ref([])
const skillLoading = ref(false)

function openAIProcess() {
  aiProxyId.value = null
  skillId.value = null
  aiPrompt.value = ''
  showAIProcess.value = true
  loadAIProxies()
  loadSkills()
}

async function loadAIProxies() {
  aiProxyLoading.value = true
  try {
    const res = await api.getAIProxyList({ page: 1, page_size: 100 })
    aiProxyOptions.value = (res.data || []).map(p => ({ label: p.name, value: p.id }))
  } catch (_) { aiProxyOptions.value = [] }
  finally { aiProxyLoading.value = false }
}

async function loadSkills() {
  skillLoading.value = true
  try {
    const res = await api.getSkillList({ page: 1, page_size: 100 })
    skillOptions.value = (res.data || []).map(s => ({ label: s.title, value: s.id }))
  } catch (_) { skillOptions.value = [] }
  finally { skillLoading.value = false }
}

async function runAIProcess() {
  if (!aiProxyId.value || (!skillId.value && !aiPrompt.value.trim())) return
  const taskStore = useTaskProgressStore()
  const taskId = taskStore.startTask(t('views.network.roadNetworkWorkbench.messages.aiProcessTask'))
  showAIProcess.value = false
  await nextTick()
  try {
    // 取当前表格第一条边作为样本（不含 u/v/k 的字段信息）
    const sample = fieldsData.value?.[0] || {}
    const res = await api.aiProcessRoadFields({
      network_id: selectedNetwork.value,
      ai_proxy_id: aiProxyId.value,
      skill_id: skillId.value || null,
      prompt: aiPrompt.value.trim(),
      sample,
      fields_list: fieldsDefs.value,
    })
    const result = res.data
    if (result?.network_id) {
      taskStore.finishTask(taskId, result.message || t('views.network.roadNetworkWorkbench.messages.aiProcessDone', { count: result.edge_count || 0 }))
      // 刷新路网列表（不重置选中区域）
      try {
        const listRes = await api.getRoadNetworksForRegion(selectedRegion.value)
        networkList.value = listRes.data || []
      } catch (_) {}
      // 自动选中 AI 生成的新文件
      selectedNetwork.value = result.network_id
      await onNetworkChange(result.network_id)
    } else {
      taskStore.failTask(taskId, { message: result?.message || t('views.network.roadNetworkWorkbench.messages.aiNoValidData') })
    }
  } catch (e) {
    const errMsg = e?.response?.data?.msg || e?.message || t('views.network.roadNetworkWorkbench.messages.unknownError')
    taskStore.failTask(taskId, { message: t('views.network.roadNetworkWorkbench.messages.aiProcessFail'), detail: errMsg })
  }
}
</script>

<template>
  <CommonPage :title="t('views.network.roadNetworkWorkbench.title')">
    <template #action>
      <NButton v-if="!isFullscreen" size="small" @click="toggleFullscreen">⛶ {{ t('views.network.roadNetworkWorkbench.fullscreen') }}</NButton>
    </template>

    <div ref="fullscreenRef" :class="['fullscreen-area', { 'is-fullscreen': isFullscreen, 'is-h-dragging': isHDragging }]">
    <!-- 三级选择器 -->
    <NSpace class="selector-bar" align="center" wrap style="margin-bottom: 12px">
      <NSelect v-model:value="selectedCountry" :options="countryOptions" :placeholder="t('views.network.roadNetworkWorkbench.selectors.country')" style="width:200px"
        @update:value="onCountryChange" clearable filterable />
      <NSelect v-model:value="selectedRegion" :options="regionOptions" :placeholder="t('views.network.roadNetworkWorkbench.selectors.region')" style="width:220px"
        @update:value="onRegionChange" clearable :disabled="!selectedCountry" filterable />
      <NSelect v-model:value="selectedNetwork" :options="networkOptions" :placeholder="t('views.network.roadNetworkWorkbench.selectors.network')" style="width:280px"
        @update:value="onNetworkChange" clearable :disabled="!selectedRegion" filterable />
      <NButton size="small" :disabled="!selectedNetwork" @click="onClearCache" secondary>🗑 {{ t('views.network.roadNetworkWorkbench.clearCache') }}</NButton>
      <!-- 底图选择 -->
      <NSelect v-model:value="selectedBaseLayer" :options="baseLayers" :placeholder="t('views.network.roadNetworkWorkbench.basemap')" style="width:160px"
        @update:value="switchBaseLayer" />
    </NSpace>

    <div ref="workbenchRef" class="workbench-main" :class="{ 'is-dragging': isDragging }" :style="{ flex: `0 0 ${mainHeightPercent}%` }">
      <!-- 地图（始终渲染） -->
      <div ref="mapWrapper" class="map-wrapper" :style="{ flex: `0 0 ${splitPercent}%` }">
        <div ref="mapContainer" class="map-container" />
        <!-- 空状态覆盖 -->
        <div v-if="!selectedNetwork" class="map-empty-overlay">
          <span>{{ t('views.network.roadNetworkWorkbench.mapEmpty') }}</span>
        </div>
        <!-- 实时坐标 -->
        <div class="map-coords">
          <span>Z: {{ liveZoom }}</span>
          <span style="margin-left:8px">{{ liveCenter.lat }}, {{ liveCenter.lon }}</span>
        </div>
        <!-- 图例 -->
        <div v-if="legendTypes.length && selectedNetwork" class="map-legend">
          <div class="legend-title">{{ t('views.network.roadNetworkWorkbench.legend.title') }}</div>
          <div v-for="lt in legendTypes" :key="lt.type" class="legend-item">
            <span class="legend-color" :style="{ background: lt.color }" />
            <span class="legend-label">{{ lt.type }}<span v-if="lt.name_zh !== lt.type" style="color:#999">（{{ lt.name_zh }}）</span></span>
          </div>
        </div>
      </div>

      <!-- 拖拽分隔条 -->
      <div class="resizer" @pointerdown="onResizerPointerDown" @pointermove="onResizerPointerMove" @pointerup="onResizerPointerUp" />

      <!-- 统计面板 -->
      <NCard v-if="selectedNetwork" size="small" class="stats-card">
        <template #header><span style="font-weight:600">{{ t('views.network.roadNetworkWorkbench.stats.title') }}</span></template>
        <NSpin :show="analyzeLoading">
          <div v-if="networkInfo">
            <div style="display:flex;flex-wrap:wrap;gap:8px">
              <NTag type="info" size="small">{{ t('views.network.roadNetworkWorkbench.stats.nodes') }}: {{ networkInfo.node_count?.toLocaleString() }}</NTag>
              <NTag type="info" size="small">{{ t('views.network.roadNetworkWorkbench.stats.edges') }}: {{ networkInfo.edge_count?.toLocaleString() }}</NTag>
              <NTag type="info" size="small">{{ t('views.network.roadNetworkWorkbench.stats.junctions') }}: {{ networkInfo.junction_count?.toLocaleString() }}</NTag>
              <NTag type="success" size="small">{{ t('views.network.roadNetworkWorkbench.stats.totalLength') }}: {{ networkInfo.total_length_km }} km</NTag>
              <NTag v-if="networkInfo.density_km_per_km2" type="warning" size="small">
                {{ t('views.network.roadNetworkWorkbench.stats.density') }}: {{ networkInfo.density_km_per_km2 }} km/km²
              </NTag>
              <NTag v-if="networkInfo.file_size" type="default" size="small">
                {{ t('views.network.roadNetworkWorkbench.stats.fileSize') }}: {{ (networkInfo.file_size / 1024 / 1024).toFixed(1) }} MB
              </NTag>
              <NTag v-if="networkInfo.srid" type="default" size="small">
                {{ t('views.network.roadNetworkWorkbench.stats.srid') }}: {{ networkInfo.srid }}
              </NTag>
            </div>
            <div v-if="viewportCenter" style="margin-top:8px;display:flex;flex-wrap:wrap;gap:8px">
              <NTag type="info" size="small">
                {{ t('views.network.roadNetworkWorkbench.stats.center') }}: {{ viewportCenter.lat }}, {{ viewportCenter.lon }}
              </NTag>
              <NTag v-if="viewportZoom != null" type="info" size="small">
                {{ t('views.network.roadNetworkWorkbench.stats.zoom') }}: L{{ viewportZoom }}
              </NTag>
            </div>
            <div style="margin-top:12px;font-size:13px;color:#666">
              <div v-for="s in (networkInfo.highway_stats||[]).slice(0,8)" :key="s.type" style="margin-bottom:4px">
                <span :style="{display:'inline-block',width:10,height:10,borderRadius:2,background:getColor(s.type),marginRight:6}" />
                {{ s.name_zh || s.type }}: {{ s.count }}{{ t('views.network.roadNetworkWorkbench.stats.unitItem') }} ({{ s.percent }}%)
              </div>
            </div>
          </div>
        </NSpin>
      </NCard>
    </div>

    <!-- 垂直拖拽分隔条 -->
    <div class="h-resizer" @pointerdown="onHResizerPointerDown" @pointermove="onHResizerPointerMove" @pointerup="onHResizerPointerUp" />

    <!-- TAB 功能区 -->
    <NCard size="small" class="tab-card">
      <NTabs v-model:value="activeTab" type="line" size="small">
        <NTabPane name="filter" :tab="t('views.network.roadNetworkWorkbench.tabs.filter.label')">
              <NSpace vertical>
                <!-- 模板管理栏 -->
                <NSpace align="center">
                  <NSelect
                    v-model:value="selectedTemplate"
                    :options="filterTemplates"
                    :placeholder="t('views.network.roadNetworkWorkbench.tabs.filter.selectTemplate')"
                    style="width:180px"
                    clearable
                    @update:value="applyTemplate"
                  />
                  <NButton size="small" @click="showTemplateInput = !showTemplateInput">
                    {{ showTemplateInput ? t('views.network.roadNetworkWorkbench.tabs.filter.cancel') : t('views.network.roadNetworkWorkbench.tabs.filter.saveTemplate') }}
                  </NButton>
                  <NButton size="small" type="error" @click="deleteTemplate" secondary>
                    {{ t('views.network.roadNetworkWorkbench.tabs.filter.delete') }}
                  </NButton>
                </NSpace>
                <NSpace v-if="showTemplateInput" align="center">
                  <NInput v-model:value="newTemplateName" :placeholder="t('views.network.roadNetworkWorkbench.tabs.filter.templateName')" style="width:160px" size="small" />
                  <NButton size="small" type="primary" @click="saveTemplate">{{ t('views.network.roadNetworkWorkbench.tabs.filter.confirmSave') }}</NButton>
                </NSpace>
                <!-- 等级选择 -->
                <div style="font-size:13px;color:#666;margin-bottom:4px">{{ t('views.network.roadNetworkWorkbench.tabs.filter.selectHint') }}</div>
                <NSpace>
                  <NCheckbox
                  v-for="hw in highwayTypes"
                  :key="typeof hw === 'string' ? hw : hw.type"
                  :value="typeof hw === 'string' ? hw : hw.type"
                  :label="(typeof hw === 'string' ? hw : (hw.type + (hw.name_zh && hw.name_zh !== hw.type ? '（' + hw.name_zh + '）' : '')))"
                  :checked="selectedHighways.includes(typeof hw === 'string' ? hw : hw.type)"
                  @update:checked="(v) => {
                    const t = typeof hw === 'string' ? hw : hw.type
                    v ? selectedHighways.push(t) : selectedHighways = selectedHighways.filter(x => x !== t)
                  }"
                />
                </NSpace>
                <NButton type="primary" :loading="filterLoading" @click="onFilter" style="width:120px">{{ t('views.network.roadNetworkWorkbench.tabs.filter.saveAndFilter') }}</NButton>
              </NSpace>
            </NTabPane>
            <NTabPane name="style" tab="路网渲染配置">
              <NSpace vertical>
                <div style="font-size:13px;color:#666;margin-bottom:6px">调整道路颜色的线宽。修改后点击「保存」立即生效到瓦片渲染。</div>
                <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 6px; max-height: 320px; overflow-y: auto">
                  <div v-for="hw in highwayTypes" :key="typeof hw === 'string' ? hw : hw.type"
                    style="display:flex; align-items:center; gap: 8px; padding: 4px 8px; border-radius: 6px; border: 1px solid #e5e7eb; font-size:13px">
                    <span style="min-width:80px;text-align:right;color:#555">{{ typeof hw === 'string' ? hw : (hw.name_zh || hw.type) }}</span>
                    <input type="color"
                      :value="getHighwayColor(typeof hw === 'string' ? hw : hw.type)"
                      @input="e => setHighwayColor(typeof hw === 'string' ? hw : hw.type, e.target.value)"
                      style="width:28px;height:22px;border:none;cursor:pointer;padding:0" />
                    <NInputNumber
                      :value="styleWeights[typeof hw === 'string' ? hw : hw.type]"
                      :min="0.1" :max="5" :step="0.05"
                      size="tiny" style="width:60px"
                      placeholder="粗细"
                      @update:value="v => styleWeights = { ...styleWeights, [(typeof hw === 'string' ? hw : hw.type)]: v }"
                    />
                  </div>
                </div>
                <NSpace style="margin-top:8px">
                  <NButton type="primary" :loading="styleLoading" @click="saveHighwayStyle" size="small">保存配置</NButton>
                  <NButton size="small" @click="resetHighwayStyle" :loading="styleLoading">恢复默认</NButton>
                </NSpace>
              </NSpace>
            </NTabPane>
            <NTabPane name="segment" :tab="t('views.network.roadNetworkWorkbench.tabs.segment.label')">
              <NSpace vertical>
                <NSpace align="center">
                  <span>{{ t('views.network.roadNetworkWorkbench.tabs.segment.lengthLabel') }}</span>
                  <NInputNumber v-model:value="segmentLength" :min="100" :step="500" style="width:160px" />
                </NSpace>
                <NButton type="primary" :loading="segmentLoading" @click="onSegment" style="width:120px">{{ t('views.network.roadNetworkWorkbench.tabs.segment.segmentAndSave') }}</NButton>
              </NSpace>
            </NTabPane>
            <NTabPane name="stats" :tab="t('views.network.roadNetworkWorkbench.tabs.stats.label')">
              <NDataTable v-if="networkInfo" :columns="statsColumns"
                :data="[
                  { label: t('views.network.roadNetworkWorkbench.statsDetail.totalLength'), value: networkInfo.total_length_km + ' km' },
                  { label: t('views.network.roadNetworkWorkbench.statsDetail.totalLengthM'), value: networkInfo.total_length_m?.toLocaleString() + ' m' },
                  { label: t('views.network.roadNetworkWorkbench.statsDetail.nodeCount'), value: networkInfo.node_count?.toLocaleString() },
                  { label: t('views.network.roadNetworkWorkbench.statsDetail.edgeCount'), value: networkInfo.edge_count?.toLocaleString() },
                  { label: t('views.network.roadNetworkWorkbench.statsDetail.junctionCount'), value: networkInfo.junction_count?.toLocaleString() },
                  { label: t('views.network.roadNetworkWorkbench.statsDetail.density'), value: networkInfo.density_km_per_km2 ? networkInfo.density_km_per_km2 + ' km/km²' : '-' },
                ]" size="small" :bordered="true" style="max-width:400px" />
            </NTabPane>
            <NTabPane name="fields" :tab="t('views.network.roadNetworkWorkbench.tabs.fields.label')">
              <NSpace vertical>
                <NSpace align="center">
                  <NInput v-model:value="fieldsSearch" :placeholder="t('views.network.roadNetworkWorkbench.tabs.fields.search')" size="small" style="width:180px" @keyup.enter="loadFields" />
                  <NButton size="small" @click="loadFields">{{ t('views.network.roadNetworkWorkbench.tabs.fields.query') }}</NButton>
                  <NButton size="small" @click="showBatchOp = true">{{ t('views.network.roadNetworkWorkbench.tabs.fields.batchOp') }}</NButton>
                  <NButton size="small" type="info" @click="openAIProcess">{{ t('views.network.roadNetworkWorkbench.tabs.fields.aiProcess') }}</NButton>
                  <NButton size="small" :loading="fieldsExporting" @click="exportFieldsJson">{{ t('views.network.roadNetworkWorkbench.tabs.fields.exportJson') }}</NButton>
                  <NButton size="small" :loading="fieldsImporting" @click="importFieldsJson">{{ t('views.network.roadNetworkWorkbench.tabs.fields.importJson') }}</NButton>
                </NSpace>
                <NDataTable
                  :columns="fieldsColumns"
                  :data="fieldsData"
                  :loading="fieldsLoading"
                  :row-key="fieldRowKey"
                  :pagination="{ page: fieldsPage, pageSize: fieldsPageSize, itemCount: fieldsTotal, showSizePicker: true, pageSizes: [20, 50, 100, 200], prefix: (info) => t('views.network.roadNetworkWorkbench.tabs.fields.paginationPrefix', { total: info.itemCount }), remote: true, onUpdatePage: (p) => { fieldsPage = p; loadFields() }, onUpdatePageSize: (ps) => { fieldsPageSize = ps; fieldsPage = 1; loadFields() } }"
                  size="small"
                  :bordered="true"
                  :scroll-x="Math.max(800, fieldsDefs.length * 130)"
                  max-height="380"
                  virtual-scroll
                  :row-class-name="(row) => isRowEdited(row) ? 'row-edited' : ''"
                />
              </NSpace>

              <!-- 行编辑弹窗 -->
              <NModal v-model:show="showFieldEditor" :title="t('views.network.roadNetworkWorkbench.tabs.fields.editField')" preset="card">
                <NSpace vertical>
                  <NSelect v-model:value="fieldEditName" :options="fieldsDefs.map(f => ({ label: f, value: f }))" :placeholder="t('views.network.roadNetworkWorkbench.tabs.fields.selectField')" />
                  <NInput v-model:value="fieldEditValue" :placeholder="t('views.network.roadNetworkWorkbench.tabs.fields.newValue')" />
                </NSpace>
                <template #footer>
                  <NSpace justify="end">
                    <NButton @click="showFieldEditor = false">{{ t('views.network.roadNetworkWorkbench.tabs.fields.cancel') }}</NButton>
                    <NButton type="primary" @click="saveFieldEdit">{{ t('views.network.roadNetworkWorkbench.tabs.fields.save') }}</NButton>
                  </NSpace>
                </template>
              </NModal>

              <!-- 批量操作弹窗 -->
              <NModal v-model:show="showBatchOp" :title="t('views.network.roadNetworkWorkbench.tabs.fields.batchOpTitle')" preset="card" style="max-width: 480px">
                <NSpace vertical>
                  <NSelect v-model:value="batchField" :options="fieldsDefs.map(f => ({ label: f, value: f }))" :placeholder="t('views.network.roadNetworkWorkbench.tabs.fields.selectTargetField')" />
                  <NSelect v-model:value="batchMode" :options="[
                    { label: t('views.network.roadNetworkWorkbench.tabs.fields.batchSanitize'), value: 'sanitize' },
                    { label: t('views.network.roadNetworkWorkbench.tabs.fields.batchSet'), value: 'set' },
                  ]" />
                  <NInput v-if="batchMode === 'set'" v-model:value="batchValue" :placeholder="t('views.network.roadNetworkWorkbench.tabs.fields.unifiedValue')" />
                </NSpace>
                <template #footer>
                  <NSpace justify="end">
                    <NButton @click="showBatchOp = false">{{ t('views.network.roadNetworkWorkbench.tabs.fields.cancel') }}</NButton>
                    <NButton type="primary" @click="runBatchOp">{{ t('views.network.roadNetworkWorkbench.tabs.fields.execute') }}</NButton>
                  </NSpace>
                </template>
              </NModal>

              <!-- AI 处理弹窗 -->
              <NModal v-model:show="showAIProcess" :title="t('views.network.roadNetworkWorkbench.tabs.fields.aiTitle')" preset="card" style="max-width: 560px">
                <NSpace vertical>
                  <NSelect v-model:value="aiProxyId" :options="aiProxyOptions" :placeholder="t('views.network.roadNetworkWorkbench.tabs.fields.selectAIProxy')" :loading="aiProxyLoading" />
                  <NSelect v-model:value="skillId" :options="skillOptions" :placeholder="t('views.network.roadNetworkWorkbench.tabs.fields.selectSkill')" :loading="skillLoading" clearable />
                  <NInput
                    v-model:value="aiPrompt"
                    type="textarea"
                    :placeholder="t('views.network.roadNetworkWorkbench.tabs.fields.aiPromptPlaceholder')"
                    :autosize="{ minRows: 3, maxRows: 6 }"
                  />
                </NSpace>
                <template #footer>
                  <NSpace justify="end">
                    <NButton @click="showAIProcess = false">{{ t('views.network.roadNetworkWorkbench.tabs.fields.cancel') }}</NButton>
                    <NButton type="primary" :disabled="!aiProxyId || (!skillId && !aiPrompt.trim())" @click="runAIProcess">
                      {{ t('views.network.roadNetworkWorkbench.tabs.fields.execute') }}
                    </NButton>
                  </NSpace>
                </template>
              </NModal>
            </NTabPane>
            <NTabPane name="controls" :tab="t('views.network.label_cn_e1b2f870')">
              <NSpace vertical>
                <div style="font-size:13px;color:#666;margin-bottom:4px">显示/隐藏地图控件</div>
                <NCheckbox
                  v-for="item in [
                    { key: 'compass', label: t('views.network.label_cn_5bc1ed6c') },
                    { key: 'legend', label: t('views.network.label_cn_9d7b554a') },
                    { key: 'scale', label: t('views.network.label_cn_3aefa0b5') },
                    { key: 'coords', label: t('views.network.label_cn_8ba51a39') },
                  ]"
                  :key="item.key"
                  :checked="controlVisible[item.key]"
                  :label="item.label"
                  @update:checked="() => toggleControl(item.key)"
                />
              </NSpace>
            </NTabPane>
          </NTabs>
        </NCard>
    </div>

    <!-- 图层导出弹窗 -->
    <NModal v-model:show="showExportModal" preset="card" :title="t('views.network.title_cn_d35c5853')" style="width: 420px;" :to="isFullscreen ? fullscreenRef : undefined" @update:show="(v) => { if (!v) onExportModalClose() }">
      <NSpace vertical>
        <NDataTable
          :columns="[{ type: 'selection' }, { title: t('views.network.title_cn_12f5177d'), key: 'label' }]"
          :data="exportLayerOptions"
          :row-key="(row) => row.key"
          :checked-row-keys="selectedExportLayers"
          size="small"
          :single-line="true"
          :bordered="false"
          max-height="260"
          @update:checked-row-keys="(keys) => { selectedExportLayers = keys }"
        />
        <NFormItem :label="t('views.network.label_cn_160f1630')" label-placement="left" label-width="80">
          <NInput v-model:value="exportName" :placeholder="t('views.network.placeholder_cn_7cc5266d')" />
        </NFormItem>
        <div style="font-size: 12px; color: #999;">提示：路网图层为同源瓦片，导出效果最佳。底图可能因跨域无法完整截取。</div>
        <NButton size="small" quaternary @click="toggleExportPreview" :type="exportLayerPreview ? 'warning' : 'default'">
          {{ exportLayerPreview ? '取消预览' : t('views.network.label_cn_84ba804e') }}
        </NButton>
      </NSpace>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showExportModal = false; onExportModalClose()">取消</NButton>
          <NButton type="primary" :loading="exportLoading" @click="doExportLayers">
            {{ exportLoading ? exportProgress : t('views.network.label_cn_d1a0b055') }}
          </NButton>
        </NSpace>
      </template>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.fullscreen-area { display: flex; flex-direction: column; height: calc(100vh - 140px); min-height: 500px; }
.fullscreen-area.is-h-dragging { cursor: row-resize; user-select: none; }
.fullscreen-area.is-h-dragging .h-resizer { background: #409eff; }
.workbench-main { display: flex; gap: 0; min-height: 200px; min-width: 0; }
.workbench-main.is-dragging { cursor: col-resize; user-select: none; }
.workbench-main.is-dragging .resizer { background: #409eff; }
.map-wrapper { flex: 3; min-width: 200px; position: relative; border-radius: 6px; overflow: hidden; border: 1px solid #e0e0e0; }
.map-container { width: 100%; height: 100%; touch-action: manipulation; }
.map-empty-overlay {
  position: absolute; inset: 0; z-index: 999;
  display: flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,0.7); color: #999; font-size: 15px; pointer-events: none;
}
.resizer {
  width: 6px; flex-shrink: 0; cursor: col-resize;
  background: transparent; transition: background 0.15s;
  margin: 0 4px; border-radius: 3px;
}
.resizer:hover { background: #e0e0e0; }
.h-resizer {
  height: 6px; flex-shrink: 0; cursor: row-resize;
  background: transparent; transition: background 0.15s;
  margin: 4px 0; border-radius: 3px;
}
.h-resizer:hover { background: #e0e0e0; }
.stats-card { flex: 1; min-width: 180px; overflow-y: auto; }
.tab-card { flex: 1; min-height: 100px; overflow-y: auto; }

/* 导出按钮 */
:deep(.leaflet-export-btn) {
  width: 30px;
  height: 30px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 5px rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-bottom: 1px solid #ccc;
}
:deep(.leaflet-export-btn:hover) {
  background: #f4f4f4;
}

.map-legend {
  position: absolute; bottom: 10px; right: 10px; z-index: 1000;
  background: rgba(255,255,255,0.92); border-radius: 4px; padding: 6px 10px;
  box-shadow: 0 1px 5px rgba(0,0,0,0.2); font-size: 12px; max-height: 60%; overflow-y: auto;
}
.legend-title { font-weight: 600; margin-bottom: 4px; font-size: 13px; }
.legend-item { display: flex; align-items: center; gap: 6px; margin-bottom: 2px; }
.legend-color { width: 14px; height: 4px; border-radius: 2px; flex-shrink: 0; }
.legend-label { color: #555; }

.map-coords {
  position: absolute; bottom: 30px; left: 10px; z-index: 1000;
  background: rgba(255,255,255,0.88); border-radius: 4px; padding: 3px 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.15); font-size: 11px; color: #444;
  font-family: monospace; white-space: nowrap; pointer-events: none;
}

.fullscreen-area.is-fullscreen {
  background: #fff; padding: 12px; overflow-y: auto;
  height: 100vh;
}
.fullscreen-area.is-fullscreen .workbench-main {
  min-height: 200px;
}
.fullscreen-area.is-fullscreen .stats-card {
  min-width: 200px;
}

/* 字段参数表 — 已修改行高亮 */
:deep(.row-edited td) {
  background: #fffbe6 !important;
}

/* 方位罗盘 */
:deep(.leaflet-compass) {
  background: transparent;
  pointer-events: none;
  margin-top: 10px !important;
  margin-right: 10px !important;
}
:deep(.compass-outer) {
  width: 68px;
  height: 68px;
  position: relative;
}
:deep(.compass-ring) {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(6px);
  box-shadow: 0 2px 12px rgba(0,0,0,0.15), inset 0 1px 2px rgba(255,255,255,0.6);
  border: 2px solid rgba(0,0,0,0.08);
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}
:deep(.compass-dir) {
  position: absolute;
  font-size: 10px;
  font-weight: 600;
  color: #888;
  line-height: 1;
}
:deep(.dir-n) { top: 6px;  left: 50%; transform: translateX(-50%); color: #333; font-weight: 700; font-size: 11px; }
:deep(.dir-e) { top: 50%; right: 6px; transform: translateY(-50%); }
:deep(.dir-s) { bottom: 6px; left: 50%; transform: translateX(-50%); }
:deep(.dir-w) { top: 50%; left: 6px; transform: translateY(-50%); }
:deep(.compass-ticks) {
  position: absolute;
  inset: 4px;
  width: calc(100% - 8px);
  height: calc(100% - 8px);
  pointer-events: none;
}
:deep(.compass-needle) {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 12px;
  height: 32px;
}
:deep(.needle-north) {
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-bottom: 18px solid #e74c3c;
  filter: drop-shadow(0 0 2px rgba(231,76,60,0.4));
}
:deep(.needle-south) {
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 12px solid #bbb;
  margin-top: 2px;
}

/* ── 移动端适配（≤768px）── */
@media (max-width: 768px) {
  .fullscreen-area {
    height: calc(100vh - 100px);
    height: calc(100dvh - 100px); /* 动态视口，适应移动端地址栏 */
    min-height: 400px;
  }
  .fullscreen-area.is-fullscreen {
    padding: 8px;
    height: 100vh;
    height: 100dvh; /* 动态视口，适应移动端地址栏 */
  }

  /* ── 选择器栏：全宽 + 换行 ── */
  .selector-bar {
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 8px;
  }
  .selector-bar :deep(.n-select),
  .selector-bar :deep(.n-base-selection),
  .selector-bar :deep(.n-button) {
    width: 100% !important;
    min-width: 0;
  }
  /* 让每个选择器/按钮容器占据合适的宽度 */
  .selector-bar > * {
    flex: 1 1 calc(50% - 4px);
    min-width: 130px;
  }

  /* ── 工作区：垂直堆叠 ── */
  .workbench-main {
    flex-direction: column;
    flex: none !important;
    min-height: 0;
    height: auto;
  }

  /* ── 地图：占上半部分，固定高度 ── */
  .map-wrapper {
    flex: none !important;
    width: 100%;
    height: min(50vh, 400px);
    min-height: 250px;
    border-radius: 6px 6px 0 0;
  }

  /* ── 水平拖拽条：隐藏（移动端垂直堆叠，无需水平拖拽）── */
  .resizer {
    display: none;
  }

  /* ── 统计面板：全宽 ── */
  .stats-card {
    flex: none !important;
    width: 100%;
    min-width: 0;
    max-height: 35vh;
    border-radius: 0 0 6px 6px;
  }

  /* ── 垂直拖拽条：加高方便手指操作 ── */
  .h-resizer {
    height: 12px;
    margin: 6px 0;
  }

  /* ── 地图控件：放大触摸目标 ── */
  :deep(.leaflet-control-zoom a) {
    width: 36px !important;
    height: 36px !important;
    line-height: 36px !important;
    font-size: 20px !important;
  }
  :deep(.leaflet-export-btn) {
    width: 36px !important;
    height: 36px !important;
  }
  :deep(.leaflet-export-btn svg) {
    width: 22px !important;
    height: 22px !important;
  }
  .map-legend {
    font-size: 11px;
    padding: 4px 8px;
    bottom: 6px;
    right: 6px;
    max-height: 45%;
  }
  .map-coords {
    font-size: 10px;
    padding: 2px 6px;
    bottom: 20px;
    left: 6px;
  }

  /* ── TAB 功能区：全宽 ── */
  .tab-card {
    flex: none !important;
    width: 100%;
    min-height: 120px;
  }

  /* ── 表格在小屏上横向滚动 ── */
  :deep(.n-data-table) {
    font-size: 12px;
  }
}
</style>