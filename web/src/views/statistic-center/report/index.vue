<script setup>
import { onMounted, onBeforeUnmount, onActivated, onDeactivated, ref, nextTick, watch } from 'vue'
import {
  NButton, NInput, NLayout, NLayoutSider, NLayoutContent,
  NList, NListItem, NModal, NSpace, NSelect, NPopconfirm,
  NForm, NFormItem, NTag, NDivider, NSpin, NSwitch, useMessage,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

defineOptions({ name: '报告生成' })

const message = useMessage()

function formatFileSize(bytes) {
  if (bytes == null || bytes === 0) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// 状态
const workspaces = ref([])
const selectedWs = ref(null)
const reports = ref([])
const selectedReport = ref(null)
const loading = ref(false)
const viewMode = ref('preview') // 'edit' | 'preview'
const editContent = ref('')
let cmInstance = null
const cmContainer = ref(null)
const previewFrame = ref(null)

// 生成弹窗
const showGenerateModal = ref(false)
const generateForm = ref({
  workspace_id: 0, name: '',
  source_sheet_ids: [], source_analysis_ids: [],
  ai_proxy_id: null, skill_id: null, prompt: '',
})
const proxyOptions = ref([])
const skillOptions = ref([])
const sheetOptions = ref([])
const analysisOptions = ref([])
const workspaceOptions = ref([])

// 克隆弹窗
const showCloneModal = ref(false)
const cloneForm = ref({ id: 0, name: '' })

// 工作区列表
async function loadWorkspaces() {
  try {
    const res = await api.getWorkspaceList({ page: 1, page_size: 9999 })
    workspaces.value = res.data || []
  } catch (e) { message.error('加载工作区失败') }
}

async function selectWorkspace(ws) {
  selectedWs.value = ws
  selectedReport.value = null
  editContent.value = ''
  await loadReports()
}

// 报告列表
async function loadReports() {
  if (!selectedWs.value) return
  try {
    const res = await api.getReportList({ workspace_id: selectedWs.value.id })
    reports.value = res.data || []
  } catch (e) { message.error('加载报告失败') }
}

// 选中报告
async function selectReport(r) {
  selectedReport.value = r
  try {
    const res = await api.getReportById({ report_id: r.id })
    editContent.value = res.data.content || ''
    initCodeMirror()
  } catch (e) { message.error('加载报告内容失败') }
}

function initCodeMirror() {
  nextTick(() => {
    try {
      if (!cmContainer.value) return
      if (cmInstance) {
        cmInstance.setValue(editContent.value)
        cmInstance.refresh()
        return
      }
      if (!window.CodeMirror) return
      cmInstance = window.CodeMirror(cmContainer.value, {
        value: editContent.value,
        mode: 'htmlmixed',
        theme: 'dracula',
        lineNumbers: true,
        lineWrapping: true,
        tabSize: 2,
      })
      cmInstance.setSize('100%', '100%')
      cmInstance.on('change', () => {
        editContent.value = cmInstance.getValue()
      })
    } catch (e) {
      console.error('CodeMirror 初始化失败:', e)
      cmInstance = null
    }
  })
}

function destroyCodeMirror() {
  if (cmInstance) {
    try { cmInstance.toTextArea() } catch (e) { /* ignore */ }
    cmInstance = null
  }
}

// 生成报告
function openGenerate() {
  generateForm.value = {
    workspace_id: selectedWs.value?.id || null, name: '数据分析报告',
    source_sheet_ids: [], source_analysis_ids: [],
    ai_proxy_id: null, skill_id: null, prompt: '',
  }
  // 加载工作区选项
  workspaceOptions.value = workspaces.value.map((w) => ({ label: w.name, value: w.id }))
  sheetOptions.value = []
  analysisOptions.value = []
  // 如果左侧已选工作区，预加载其数据源
  if (selectedWs.value) {
    generateForm.value.workspace_id = selectedWs.value.id
    loadGenerateDataSources(selectedWs.value.id)
  }
  api.getAIProxyList({ page: 1, page_size: 9999 }).then((res) => {
    proxyOptions.value = (res.data || []).map((p) => ({ label: p.name, value: p.id }))
  })
  api.getSkillList({ page: 1, page_size: 9999 }).then((res) => {
    skillOptions.value = (res.data || []).map((s) => ({ label: s.title, value: s.id }))
  })
  showGenerateModal.value = true
}

async function onGenerateWsChange(wsId) {
  generateForm.value.source_sheet_ids = []
  generateForm.value.source_analysis_ids = []
  await loadGenerateDataSources(wsId)
}

async function loadGenerateDataSources(wsId) {
  if (!wsId) return
  try {
    const [sh, an] = await Promise.all([
      api.getSheetList({ workspace_id: wsId }),
      api.getAnalysisList({ workspace_id: wsId }),
    ])
    sheetOptions.value = (sh.data || []).map((s) => ({
      label: s.name + (s.file_size ? ` (${formatFileSize(s.file_size)})` : ''),
      value: s.id,
    }))
    analysisOptions.value = (an.data || []).map((a) => ({
      label: a.name + (a.file_size ? ` (${formatFileSize(a.file_size)})` : ''),
      value: a.id,
    }))
  } catch (e) { /* ignore */ }
}

async function handleGenerate() {
  if (!generateForm.value.workspace_id) { message.warning('请选择数据工作区'); return }
  if (!generateForm.value.ai_proxy_id) { message.warning('请选择AI代理'); return }
  if (!generateForm.value.source_sheet_ids.length && !generateForm.value.source_analysis_ids.length) {
    message.warning('请至少选择一个数据源'); return
  }
  try {
    loading.value = true
    showGenerateModal.value = false
    await api.generateReport(generateForm.value)
    message.success('报告生成成功')
    await loadReports()
  } catch (e) { message.error('生成失败') }
  loading.value = false
}

// 保存编辑
// 预览 iframe 内容同步（沙箱隔离，防止报告 CSS 污染全局）
watch(editContent, (html) => {
  nextTick(() => {
    if (previewFrame.value) {
      previewFrame.value.srcdoc = html
    }
  })
})

async function saveEdit() {
  if (!selectedReport.value) return
  try {
    await api.updateReport({ id: selectedReport.value.id, content: editContent.value })
    message.success('保存成功')
    if (cmInstance) cmInstance.setValue(editContent.value)
  } catch (e) { message.error('保存失败') }
}

// 克隆
function openClone() {
  if (!selectedReport.value) { message.warning('请选择报告'); return }
  cloneForm.value = { id: selectedReport.value.id, name: selectedReport.value.name + ' (副本)' }
  showCloneModal.value = true
}

async function handleClone() {
  try {
    await api.cloneReport(cloneForm.value)
    message.success('克隆成功')
    showCloneModal.value = false
    await loadReports()
  } catch (e) { message.error('克隆失败') }
}

// 删除
async function deleteReport() {
  if (!selectedReport.value) return
  try {
    await api.deleteReport({ report_id: selectedReport.value.id })
    selectedReport.value = null
    editContent.value = ''
    await loadReports()
  } catch (e) { message.error('删除失败') }
}

// 导出
function downloadBlob(data, filename) {
  const blob = new Blob([data])
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

async function exportReport(type) {
  if (!selectedReport.value) return
  const apiMap = { html: api.exportReportHtml, pdf: api.exportReportPdf, docx: api.exportReportDocx }
  const extMap = { html: '.html', pdf: '.pdf', docx: '.docx' }
  try {
    const res = await apiMap[type]({ report_id: selectedReport.value.id })
    downloadBlob(res.data, selectedReport.value.name + extMap[type])
  } catch (e) { message.error(`导出${type}失败`) }
}

onMounted(() => loadWorkspaces())

// KeepAlive 缓存时进入/离开的生命周期
onActivated(() => {
  if (viewMode.value === 'edit') initCodeMirror()
})
onDeactivated(() => destroyCodeMirror())

// 组件真正销毁时（不在 KeepAlive 缓存中）
onBeforeUnmount(() => destroyCodeMirror())
</script>

<template>
  <NLayout has-sider style="height: calc(100vh - 120px)">
    <!-- 左侧 -->
    <NLayoutSider bordered width="300" :native-scrollbar="false" content-style="padding: 12px">
      <NSpace vertical>
        <NButton type="primary" block @click="openGenerate">
          <TheIcon icon="material-symbols:smart-toy" :size="18" class="mr-5" />生成报告
        </NButton>
        <NList hoverable clickable :show-divider="false">
          <NListItem
            v-for="ws in workspaces" :key="ws.id"
            :class="{ 'bg-blue-50 dark:bg-blue-900': selectedWs?.id === ws.id }"
            style="border-radius: 8px; margin-bottom: 4px; cursor: pointer"
            @click="selectWorkspace(ws)"
          >
            <div class="flex flex-col flex-1 min-w-0">
              <span class="font-medium truncate">{{ ws.name }}</span>
              <span class="text-xs text-gray-400">{{ ws.updated_at }}</span>
            </div>
          </NListItem>
        </NList>
        <div v-if="!workspaces.length" class="text-center text-gray-400 py-10">暂无工作区</div>

        <template v-if="selectedWs">
          <NDivider />
          <div class="text-sm font-medium text-gray-500 mb-1">报告 ({{ reports.length }})</div>
          <NList hoverable clickable :show-divider="false">
            <NListItem
              v-for="r in reports" :key="r.id"
              :class="{ 'bg-green-50 dark:bg-green-900': selectedReport?.id === r.id }"
              style="border-radius: 8px; margin-bottom: 4px; cursor: pointer"
              @click="selectReport(r)"
            >
              <div class="flex flex-col flex-1 min-w-0">
                <span class="truncate">{{ r.name }}</span>
                <span class="text-xs text-gray-400">{{ r.updated_at }}</span>
              </div>
            </NListItem>
            <div v-if="!reports.length" class="text-xs text-gray-400 py-2 text-center">无</div>
          </NList>
        
</template>
      </NSpace>
    </NLayoutSider>

    <!-- 右侧 -->
    <NLayoutContent content-style="padding: 0; display: flex; flex-direction: column; overflow: hidden">
      <!-- 操作栏（固定顶部） -->
      <div
        v-if="selectedReport"
        class="flex items-center justify-between px-4 py-3 border-b"
        style="flex-shrink: 0"
      >
        <h2 class="text-lg font-bold m-0">{{ selectedReport.name }}</h2>
        <NSpace>
          <NSwitch v-model:value="viewMode" checked-value="edit" unchecked-value="preview">
            <template #checked>编辑</template>
            <template #unchecked>预览</template>
          </NSwitch>
          <NButton v-if="viewMode === 'edit'" size="small" @click="saveEdit">
            <TheIcon icon="material-symbols:save" :size="16" class="mr-4" />保存
          </NButton>
          <NButton size="small" @click="openClone">
            <TheIcon icon="material-symbols:content-copy" :size="16" class="mr-4" />克隆
          </NButton>
          <NButton size="small" @click="exportReport('html')">
            <TheIcon icon="material-symbols:code" :size="16" class="mr-4" />HTML
          </NButton>
          <NButton size="small" @click="exportReport('pdf')">
            <TheIcon icon="material-symbols:picture-as-pdf" :size="16" class="mr-4" />PDF
          </NButton>
          <NButton size="small" @click="exportReport('docx')">
            <TheIcon icon="material-symbols:article" :size="16" class="mr-4" />Word
          </NButton>
          <NPopconfirm @positive-click="deleteReport">
            <template #trigger>
              <NButton size="small" type="error">
                <TheIcon icon="material-symbols:delete-outline" :size="16" class="mr-4" />删除
              </NButton>
            </template>
          </NPopconfirm>
        </NSpace>
      </div>

      <!-- 内容区（绝对定位 + CSS containment，隔离 CodeMirror） -->
      <div style="flex: 1; min-height: 0; position: relative; contain: layout style">
        <!-- 空态 -->
        <div v-if="!selectedReport" class="flex items-center justify-center h-full text-gray-400 text-base">
          请选择左侧报告
        </div>
        <template v-else>
          <!-- 编辑模式：CodeMirror 绝对定位填满 -->
          <div v-show="viewMode === 'edit'" ref="cmContainer" style="position: absolute; inset: 0"></div>
          <!-- 预览模式：iframe 沙箱隔离，防止报告内 CSS 污染全局 -->
          <iframe
            v-show="viewMode !== 'edit'"
            ref="previewFrame"
            style="position: absolute; inset: 0; width: 100%; height: 100%; border: none"
            title="报告预览"
          />
        </template>
        <!-- Loading 覆盖层 -->
        <div v-if="loading" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.6); z-index: 10">
          <NSpin :show="true" />
        </div>
      </div>
    </NLayoutContent>
  </NLayout>

  <!-- 生成弹窗 -->
  <NModal v-model:show="showGenerateModal" title="生成报告" preset="card" style="width: 640px">
    <NForm :model="generateForm" label-placement="top">
      <NFormItem label="报告名称" required>
        <NInput v-model:value="generateForm.name" placeholder="报告名称" />
      </NFormItem>
      <NFormItem label="数据工作区" required>
        <NSelect v-model:value="generateForm.workspace_id" :options="workspaceOptions" placeholder="选择Excel数据工作区" @update:value="onGenerateWsChange" />
      </NFormItem>
      <NFormItem label="原始表格">
        <NSelect v-model:value="generateForm.source_sheet_ids" :options="sheetOptions" multiple placeholder="选择原始表格" />
      </NFormItem>
      <NFormItem label="分析表格">
        <NSelect v-model:value="generateForm.source_analysis_ids" :options="analysisOptions" multiple placeholder="选择分析表格" />
      </NFormItem>
      <NFormItem label="AI 代理" required>
        <NSelect v-model:value="generateForm.ai_proxy_id" :options="proxyOptions" placeholder="选择AI代理" />
      </NFormItem>
      <NFormItem label="辅助 Skill">
        <NSelect v-model:value="generateForm.skill_id" :options="skillOptions" placeholder="选择Skill" clearable />
      </NFormItem>
      <NFormItem label="提示词">
        <NInput v-model:value="generateForm.prompt" type="textarea" placeholder="额外分析要求..." />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showGenerateModal = false">取消</NButton>
        <NButton type="primary" @click="handleGenerate">开始生成</NButton>
      </NSpace>
    
</template>
  </NModal>

  <!-- 克隆弹窗 -->
  <NModal v-model:show="showCloneModal" title="克隆报告" preset="card" style="width: 400px">
    <NForm :model="cloneForm" label-placement="top">
      <NFormItem label="新名称" required>
        <NInput v-model:value="cloneForm.name" placeholder="新报告名称" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showCloneModal = false">取消</NButton>
        <NButton type="primary" @click="handleClone">确认克隆</NButton>
      </NSpace>
    
</template>
  </NModal>

</template>

<style scoped>
:global(.CodeMirror) {
  height: 100% !important;
}
</style>
