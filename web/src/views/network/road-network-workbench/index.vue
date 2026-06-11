<script setup>
import { computed, h, nextTick, onMounted, ref, watch } from 'vue'
import {
  NButton, NCard, NCheckbox, NDataTable, NInputNumber,
  NSelect, NSpace, NSpin, NTabPane, NTabs, NTag, useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: '路网工作台' })
const message = useMessage()

// ── 三级选择器 ──
const treeData = ref([])
const selectedCountry = ref(null)
const selectedRegion = ref(null)
const selectedNetwork = ref(null)
const networkList = ref([])
const loading = ref(false)

// ── 路网分析数据 ──
const networkInfo = ref(null)
const geojsonData = ref(null)
const highwayTypes = ref([])
const analyzeLoading = ref(false)

// ── Canvas 预览 ──
const canvasRef = ref(null)
const canvasScale = ref(1)
const canvasOffset = ref({ x: 0, y: 0 })
const isDragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })

// ── TAB ──
const activeTab = ref('filter')
const selectedHighways = ref([])
const filterLoading = ref(false)
const segmentLength = ref(1000)
const segmentLoading = ref(false)

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

// ── 数据加载 ──
onMounted(async () => {
  const res = await api.getRegionTree()
  treeData.value = res.data || []
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

const countryOptions = computed(() =>
  allRegions.value.filter(r => r.region_type === 'COUNTRY').map(r => ({ label: r.label, value: r.id }))
)

const regionOptions = computed(() =>
  allRegions.value.filter(r => r.parent_id === selectedCountry.value || (selectedCountry.value && r._level > 0))
    .map(r => ({ label: '　'.repeat(r._level) + r.label, value: r.id }))
)

const networkOptions = computed(() =>
  networkList.value.map(n => ({ label: `${n.file_name} (${n.node_count}节点)`, value: n.id }))
)

async function onCountryChange(id) {
  selectedCountry.value = id
  selectedRegion.value = null
  selectedNetwork.value = null
  networkList.value = []
  clearData()
}

async function onRegionChange(id) {
  selectedRegion.value = id
  selectedNetwork.value = null
  networkList.value = []
  clearData()
  try {
    const res = await api.getRoadNetworksForRegion(id)
    networkList.value = res.data || []
  } catch (e) { networkList.value = [] }
}

async function onNetworkChange(id) {
  if (!id) { clearData(); return }
  selectedNetwork.value = id
  await loadAnalysis(id)
}

function clearData() {
  networkInfo.value = null
  geojsonData.value = null
  highwayTypes.value = []
}

async function loadAnalysis(networkId) {
  analyzeLoading.value = true
  try {
    const res = await api.analyzeNetwork({ network_id: networkId })
    const d = res.data || {}
    networkInfo.value = d.info
    geojsonData.value = d.geojson
    highwayTypes.value = d.highway_types || []
    await nextTick()
    fitCanvas()
  } catch (e) {
    message.error('分析失败')
  } finally {
    analyzeLoading.value = false
  }
}

// ── Canvas 渲染 ──
function fitCanvas() {
  canvasScale.value = 1
  canvasOffset.value = { x: 0, y: 0 }
  drawCanvas()
}

function drawCanvas() {
  const canvas = canvasRef.value
  if (!canvas || !geojsonData.value) return
  const ctx = canvas.getContext('2d')
  const w = canvas.clientWidth
  const h = canvas.clientHeight
  canvas.width = w
  canvas.height = h
  ctx.clearRect(0, 0, w, h)

  const features = geojsonData.value.features || []
  if (!features.length) return

  // 计算 bbox
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const f of features) {
    const coords = f.geometry?.coordinates || []
    for (const c of coords) {
      if (c[0] < minX) minX = c[0]
      if (c[0] > maxX) maxX = c[0]
      if (c[1] < minY) minY = c[1]
      if (c[1] > maxY) maxY = c[1]
    }
  }

  const dataW = maxX - minX || 0.01
  const dataH = maxY - minY || 0.01
  const scale = Math.min(w / dataW, h / dataH) * canvasScale.value * 0.9
  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2

  ctx.save()
  ctx.translate(w / 2 + canvasOffset.value.x, h / 2 + canvasOffset.value.y)
  ctx.scale(scale, -scale)
  ctx.translate(-cx, -cy)

  for (const f of features) {
    const coords = f.geometry?.coordinates || []
    if (coords.length < 2) continue
    const hw = f.properties?.highway || 'unclassified'
    ctx.strokeStyle = getColor(hw)
    ctx.lineWidth = 0.8 / canvasScale.value
    ctx.beginPath()
    ctx.moveTo(coords[0][0], coords[0][1])
    for (let i = 1; i < coords.length; i++) ctx.lineTo(coords[i][0], coords[i][1])
    ctx.stroke()
  }
  ctx.restore()
}

watch([canvasScale, canvasOffset], drawCanvas, { deep: true })

// Canvas 交互
function onCanvasWheel(e) {
  e.preventDefault()
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  canvasScale.value = Math.max(0.1, Math.min(10, canvasScale.value * delta))
}
function onCanvasMouseDown(e) {
  isDragging.value = true
  dragStart.value = { x: e.clientX, y: e.clientY }
}
function onCanvasMouseMove(e) {
  if (!isDragging.value) return
  canvasOffset.value = {
    x: canvasOffset.value.x + (e.clientX - dragStart.value.x),
    y: canvasOffset.value.y + (e.clientY - dragStart.value.y),
  }
  dragStart.value = { x: e.clientX, y: e.clientY }
}
function onCanvasMouseUp() { isDragging.value = false }

// ── TAB 功能 ──
async function onFilter() {
  if (!selectedNetwork.value || !selectedHighways.value.length) {
    message.warning('请选择道路等级'); return
  }
  filterLoading.value = true
  try {
    await api.filterNetwork({
      network_id: selectedNetwork.value,
      selected_types: selectedHighways.value,
      save_to_region: true,
    })
    message.success('筛选完成并已保存')
    onRegionChange(selectedRegion.value)
  } catch (e) {
    message.error('筛选失败')
  } finally { filterLoading.value = false }
}

async function onSegment() {
  if (!selectedNetwork.value || !segmentLength.value) {
    message.warning('请输入分段长度'); return
  }
  segmentLoading.value = true
  try {
    await api.segmentNetwork({
      network_id: selectedNetwork.value,
      segment_length: segmentLength.value,
      save_to_region: true,
    })
    message.success('分段完成并已保存')
    onRegionChange(selectedRegion.value)
  } catch (e) {
    message.error('分段失败')
  } finally { segmentLoading.value = false }
}

// 统计表格列
const statsColumns = [
  { title: '指标', key: 'label', width: 120 },
  { title: '值', key: 'value' },
]
</script>

<template>
  <CommonPage title="路网工作台">
    <!-- 三级选择器 -->
    <NSpace align="center" style="margin-bottom: 12px">
      <NSelect v-model:value="selectedCountry" :options="countryOptions" placeholder="选择国家" style="width:180px"
        @update:value="onCountryChange" clearable filterable />
      <NSelect v-model:value="selectedRegion" :options="regionOptions" placeholder="选择行政区" style="width:200px"
        @update:value="onRegionChange" clearable :disabled="!selectedCountry" filterable />
      <NSelect v-model:value="selectedNetwork" :options="networkOptions" placeholder="选择路网文件" style="width:260px"
        @update:value="onNetworkChange" clearable :disabled="!selectedRegion" filterable />
    </NSpace>

    <NSpin :show="analyzeLoading">
      <div v-if="!selectedNetwork" style="text-align: center; color: #999; padding: 80px 0">
        请选择 国家 → 行政区 → 路网文件 以加载数据
      </div>

      <div v-else>
        <!-- Canvas + 统计概要 -->
        <NSpace align="start" style="margin-bottom: 8px">
          <NCard size="small" style="width: 70%; height: 420px; padding: 0; overflow: hidden">
            <canvas ref="canvasRef" style="width:100%;height:100%;cursor:grab"
              @wheel="onCanvasWheel" @mousedown="onCanvasMouseDown"
              @mousemove="onCanvasMouseMove" @mouseup="onCanvasMouseUp" @mouseleave="onCanvasMouseUp" />
          </NCard>

          <NCard size="small" style="width: 30%; min-width: 260px">
            <template #header><span style="font-weight:600">路网统计概览</span></template>
            <template v-if="networkInfo">
              <div style="display:flex;flex-wrap:wrap;gap:8px">
                <NTag type="info" size="small">节点: {{ networkInfo.node_count?.toLocaleString() }}</NTag>
                <NTag type="info" size="small">边: {{ networkInfo.edge_count?.toLocaleString() }}</NTag>
                <NTag type="info" size="small">路口: {{ networkInfo.junction_count?.toLocaleString() }}</NTag>
                <NTag type="success" size="small">总里程: {{ networkInfo.total_length_km }} km</NTag>
                <NTag v-if="networkInfo.density_km_per_km2" type="warning" size="small">
                  密度: {{ networkInfo.density_km_per_km2 }} km/km²
                </NTag>
              </div>
              <div style="margin-top:12px;font-size:13px;color:#666">
                <div v-for="s in (networkInfo.highway_stats||[]).slice(0,8)" :key="s.type"
                  style="margin-bottom:4px">
                  <span :style="{display:'inline-block',width:10,height:10,borderRadius:2,background:getColor(s.type),marginRight:6}" />
                  {{ s.type }}: {{ s.count }}条 ({{ s.percent }}%)
                </div>
              </div>
            </template>
          </NCard>
        </NSpace>

        <!-- TAB 功能区 -->
        <NCard size="small">
          <NTabs v-model:value="activeTab" type="line" size="small">
            <NTabPane name="filter" tab="等级筛选">
              <NSpace vertical>
                <div style="font-size:13px;color:#666;margin-bottom:4px">选择需要保留的道路等级（未选中的将被移除）</div>
                <NSpace>
                  <NCheckbox v-for="hw in highwayTypes" :key="hw" :value="hw" :label="hw"
                    :checked="selectedHighways.includes(hw)"
                    @update:checked="(v) => v ? selectedHighways.push(hw) : selectedHighways=selectedHighways.filter(x=>x!==hw)" />
                </NSpace>
                <NButton type="primary" :loading="filterLoading" @click="onFilter" style="width:120px">
                  筛选并保存
                </NButton>
              </NSpace>
            </NTabPane>

            <NTabPane name="segment" tab="路网分段">
              <NSpace vertical>
                <NSpace align="center">
                  <span>分段长度(米):</span>
                  <NInputNumber v-model:value="segmentLength" :min="100" :step="500" style="width:160px" />
                </NSpace>
                <NButton type="primary" :loading="segmentLoading" @click="onSegment" style="width:120px">
                  分段并保存
                </NButton>
              </NSpace>
            </NTabPane>

            <NTabPane name="stats" tab="统计详情">
              <NDataTable
                v-if="networkInfo"
                :columns="statsColumns"
                :data="[
                  { label:'总里程', value: networkInfo.total_length_km + ' km' },
                  { label:'总里程(米)', value: networkInfo.total_length_m?.toLocaleString() + ' m' },
                  { label:'节点数', value: networkInfo.node_count?.toLocaleString() },
                  { label:'边数', value: networkInfo.edge_count?.toLocaleString() },
                  { label:'路口数', value: networkInfo.junction_count?.toLocaleString() },
                  { label:'路网密度', value: networkInfo.density_km_per_km2 ? networkInfo.density_km_per_km2 + ' km/km²' : '-' },
                ]"
                size="small" :bordered="true" style="max-width:400px"
              />
              <div v-if="networkInfo?.highway_stats?.length" style="margin-top:12px;font-weight:600;font-size:14px">道路类型统计</div>
              <NDataTable
                v-if="networkInfo?.highway_stats?.length"
                :columns="[{title:'类型',key:'type',width:120},{title:'数量',key:'count',width:80},{title:'占比',key:'percent',width:80,render:(r)=>r.percent+'%'}]"
                :data="networkInfo.highway_stats"
                size="small" :bordered="true" style="max-width:400px;margin-top:4px"
              />
            </NTabPane>
          </NTabs>
        </NCard>
      </div>
    </NSpin>
  </CommonPage>
</template>
