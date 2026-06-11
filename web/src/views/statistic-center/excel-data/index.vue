<script setup>
import { onMounted, ref } from 'vue'
import {
  NButton, NInput, NLayout, NLayoutSider, NLayoutContent,
  NList, NListItem, NModal, NSpace, NSelect, NPopconfirm,
  NForm, NFormItem, NTag, NUpload, NUploadDragger, NText, NDivider,
  NCheckbox, NSpin, useMessage,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

defineOptions({ name: '统计中心' })

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
const sheets = ref([])
const analyses = ref([])
const selectedAnalysisIds = ref([])
const loading = ref(false)
const showWsModal = ref(false)
const wsModalForm = ref({ name: '', description: '', user_ids: [] })
const wsEditing = ref(false)
const userOptions = ref([])

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

// 上传中
const uploading = ref(false)

// 加载工作区列表
async function loadWorkspaces() {
  try {
    const res = await api.getWorkspaceList({ page: 1, page_size: 9999 })
    workspaces.value = res.data || []
  } catch (e) { message.error('加载工作区失败') }
}

// 选择工作区
async function selectWorkspace(ws) {
  selectedWs.value = ws
  await loadSheets()
  await loadAnalyses()
}

async function loadSheets() {
  if (!selectedWs.value) return
  try {
    const res = await api.getSheetList({ workspace_id: selectedWs.value.id })
    sheets.value = res.data || []
  } catch (e) { message.error('加载表格失败') }
}

async function loadAnalyses() {
  if (!selectedWs.value) return
  try {
    const res = await api.getAnalysisList({ workspace_id: selectedWs.value.id })
    analyses.value = res.data || []
  } catch (e) { message.error('加载分析失败') }
}

// 工作区弹窗
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
  if (!selectedWs.value) { message.warning('请选择工作区'); return }
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
  if (!wsModalForm.value.name) { message.warning('请输入名称'); return }
  try {
    if (wsEditing.value) {
      await api.updateWorkspace({ id: selectedWs.value.id, ...wsModalForm.value })
    } else {
      await api.createWorkspace(wsModalForm.value)
    }
    showWsModal.value = false
    await loadWorkspaces()
  } catch (e) { message.error('操作失败') }
}

async function deleteWorkspace() {
  if (!selectedWs.value) return
  try {
    await api.deleteWorkspace({ workspace_id: selectedWs.value.id })
    selectedWs.value = null
    sheets.value = []
    analyses.value = []
    await loadWorkspaces()
  } catch (e) { message.error('删除失败') }
}

// 上传文件
async function handleUpload({ file }) {
  if (!selectedWs.value) { message.warning('请选择工作区'); return }
  uploading.value = true
  try {
    await api.uploadSheet(selectedWs.value.id, file.file)
    message.success('上传成功')
    await loadSheets()
  } catch (e) { message.error('上传失败') }
  uploading.value = false
}

// 导出
async function exportSheet(sheet) {
  try {
    const res = await api.exportSheet({ sheet_id: sheet.id })
    downloadBlob(res.data, sheet.name)
  } catch (e) { message.error('导出失败') }
}

async function exportAnalysis(a) {
  try {
    const res = await api.exportAnalysis({ analysis_id: a.id })
    downloadBlob(res.data, a.name + '.xlsx')
  } catch (e) { message.error('导出失败') }
}

function downloadBlob(data, filename) {
  const blob = new Blob([data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

// AI 分析弹窗
async function openAnalyze(sheet) {
  analyzeForm.value = {
    workspace_id: selectedWs.value.id, sheet_id: sheet.id,
    name: sheet.name.replace(/\.[^.]+$/, '') + '_分析',
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
  if (!analyzeForm.value.ai_proxy_id) { message.warning('请选择AI代理'); return }
  try {
    loading.value = true
    await api.analyzeSheet(analyzeForm.value)
    message.success('分析完成')
    showAnalyzeModal.value = false
    await loadAnalyses()
  } catch (e) { message.error('分析失败') }
  loading.value = false
}

// 关联分析弹窗
function openCorrelate() {
  if (!selectedWs.value) { message.warning('请选择工作区'); return }
  correlateForm.value = {
    workspace_id: selectedWs.value.id, sheet_a_id: null, sheet_b_id: null,
    name: '关联分析', ai_proxy_id: null, skill_id: null, prompt: '',
  }
  showCorrelateModal.value = true
  // 复用选项
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
  if (!correlateForm.value.ai_proxy_id) { message.warning('请选择AI代理'); return }
  if (!correlateForm.value.sheet_a_id || !correlateForm.value.sheet_b_id) { message.warning('请选择两个表格'); return }
  try {
    loading.value = true
    await api.correlateSheets(correlateForm.value)
    message.success('关联分析完成')
    showCorrelateModal.value = false
    await loadAnalyses()
  } catch (e) { message.error('分析失败') }
  loading.value = false
}

// 删除表格
async function deleteSheet(sheet) {
  try {
    await api.deleteSheet({ sheet_id: sheet.id })
    await loadSheets()
  } catch (e) { message.error('删除失败') }
}

async function deleteAnalysisItem(a) {
  try {
    await api.deleteAnalysis({ analysis_id: a.id })
    await loadAnalyses()
  } catch (e) { message.error('删除失败') }
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
  if (!selectedAnalysisIds.value.length) { message.warning('请选择要删除的表格'); return }
  try {
    loading.value = true
    await api.batchDeleteAnalyses({ analysis_ids: [...selectedAnalysisIds.value] })
    selectedAnalysisIds.value = []
    message.success('批量删除成功')
    await loadAnalyses()
  } catch (e) { message.error('批量删除失败') }
  loading.value = false
}

async function clearAllAnalyses() {
  if (!selectedWs.value) return
  try {
    loading.value = true
    await api.clearAnalyses({ workspace_id: selectedWs.value.id })
    selectedAnalysisIds.value = []
    message.success('已清空全部分析表格')
    await loadAnalyses()
  } catch (e) { message.error('清空失败') }
  loading.value = false
}

async function batchExportAnalyses() {
  if (!selectedAnalysisIds.value.length) { message.warning('请选择要导出的表格'); return }
  try {
    loading.value = true
    const res = await api.batchExportAnalyses({ analysis_ids: [...selectedAnalysisIds.value] })
    downloadBlob(res.data, '分析表格批量导出.zip')
    message.success('批量导出成功')
  } catch (e) { message.error('批量导出失败') }
  loading.value = false
}

onMounted(() => loadWorkspaces())
</script>

<template>
  <NLayout has-sider style="height: calc(100vh - 120px)">
    <!-- 左侧工作区菜单 -->
    <NLayoutSider bordered width="300" :native-scrollbar="false" content-style="padding: 12px">
      <NSpace vertical>
        <NButton type="primary" block @click="openCreateWs">
          <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新建工作区
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
              <span class="text-gray-400 text-xs">{{ ws.updated_at }}</span>
            </div>
          </NListItem>
        </NList>
        <div v-if="!workspaces.length" class="text-center text-gray-400 py-10">暂无工作区</div>
      </NSpace>
    </NLayoutSider>

    <!-- 右侧操作区 -->
    <NLayoutContent content-style="padding: 16px">
      <NSpin :show="loading">
        <div v-if="!selectedWs" class="flex items-center justify-center h-full text-gray-400 text-base">
          请选择左侧工作区
        </div>
        <div v-else class="h-full flex flex-col">
          <!-- 工作区操作栏 -->
          <div class="flex items-center justify-between mb-4">
            <div>
              <h2 class="text-lg font-bold m-0">{{ selectedWs.name }}</h2>
              <p v-if="selectedWs.description" class="text-gray-500 text-sm m-0 mt-1">{{ selectedWs.description }}</p>
            </div>
            <NSpace>
              <NButton size="small" @click="openEditWs">
                <TheIcon icon="material-symbols:edit" :size="16" class="mr-4" />属性
              </NButton>
              <NPopconfirm @positive-click="deleteWorkspace">
                <template #trigger>
                  <NButton size="small" type="error">
                    <TheIcon icon="material-symbols:delete-outline" :size="16" class="mr-4" />删除
                  </NButton>
                </template>
                确认删除该工作区及所有数据？
              </NPopconfirm>
            </NSpace>
          </div>

          <!-- 上传区 -->
          <div class="mb-4 p-4 border rounded border-dashed">
            <div class="flex items-center justify-between mb-2">
              <span class="font-medium">上传原始表格</span>
              <NUpload :show-file-list="false" accept=".xlsx,.xls,.csv" @change="handleUpload">
                <NButton size="small" type="primary" :loading="uploading">
                  <TheIcon icon="material-symbols:upload" :size="16" class="mr-4" />选择文件
                </NButton>
              </NUpload>
            </div>
          </div>

          <!-- 原始表格列表 -->
          <div class="mb-4">
            <div class="font-medium mb-2">原始表格 ({{ sheets.length }})</div>
            <NList v-if="sheets.length" bordered style="max-height: 200px; overflow: auto">
              <NListItem v-for="s in sheets" :key="s.id">
                <template #prefix>
                  <TheIcon icon="material-symbols:description" :size="20" class="text-blue-500" />
                </template>
                <div class="flex-1 flex items-center justify-between">
                  <div>
                    <span class="font-medium">{{ s.name }}</span>
                    <span v-if="s.file_size" class="text-gray-400 text-xs ml-2">({{ formatFileSize(s.file_size) }})</span>
                    <span class="text-gray-400 text-xs ml-3">{{ s.created_at }}</span>
                  </div>
                  <NSpace>
                    <NButton size="tiny" @click="exportSheet(s)">
                      <TheIcon icon="material-symbols:download" :size="14" />
                    </NButton>
                    <NButton size="tiny" type="primary" @click="openAnalyze(s)">
                      <TheIcon icon="material-symbols:psychology" :size="14" class="mr-2" />AI分析
                    </NButton>
                    <NPopconfirm @positive-click="deleteSheet(s)">
                      <template #trigger>
                        <NButton size="tiny" type="error"><TheIcon icon="material-symbols:delete-outline" :size="14" /></NButton>
                      </template>
                    </NPopconfirm>
                  </NSpace>
                </div>
              </NListItem>
            </NList>
            <div v-else class="text-gray-400 text-sm py-4 text-center">暂无原始表格</div>
          </div>

          <NDivider />

          <!-- 拆解分析表格列表 -->
          <div>
            <div class="flex items-center justify-between mb-2">
              <NSpace align="center">
                <NCheckbox
                  :checked="selectedAnalysisIds.length === analyses.length && analyses.length > 0"
                  :indeterminate="selectedAnalysisIds.length > 0 && selectedAnalysisIds.length < analyses.length"
                  @update:checked="toggleAllAnalyses"
                />
                <span class="font-medium">拆解分析表格 ({{ analyses.length }})</span>
              </NSpace>
              <NSpace>
                <NButton size="small" @click="openCorrelate" :disabled="sheets.length < 2">
                  <TheIcon icon="material-symbols:compare-arrows" :size="16" class="mr-4" />关联分析
                </NButton>
                <NButton size="small" type="primary" :disabled="!selectedAnalysisIds.length" @click="batchExportAnalyses">
                  <TheIcon icon="material-symbols:download" :size="16" class="mr-4" />批量导出({{ selectedAnalysisIds.length }})
                </NButton>
                <NPopconfirm @positive-click="batchDeleteAnalyses" :disabled="!selectedAnalysisIds.length">
                  <template #trigger>
                    <NButton size="small" type="warning" :disabled="!selectedAnalysisIds.length">
                      <TheIcon icon="material-symbols:delete-outline" :size="16" class="mr-4" />批量删除({{ selectedAnalysisIds.length }})
                    </NButton>
                  </template>
                  确认删除已选中的 {{ selectedAnalysisIds.length }} 个分析表格？
                </NPopconfirm>
                <NPopconfirm @positive-click="clearAllAnalyses" :disabled="!analyses.length">
                  <template #trigger>
                    <NButton size="small" type="error" :disabled="!analyses.length">
                      <TheIcon icon="material-symbols:delete-sweep" :size="16" class="mr-4" />全部删除
                    </NButton>
                  </template>
                  确认清空当前工作区的所有分析表格？
                </NPopconfirm>
              </NSpace>
            </div>
            <NList v-if="analyses.length" bordered style="max-height: 250px; overflow: auto">
              <NListItem v-for="a in analyses" :key="a.id">
                <template #prefix>
                  <NCheckbox
                    :checked="selectedAnalysisIds.includes(a.id)"
                    @update:checked="() => toggleAnalysisSelect(a.id)"
                    style="margin-right: 8px"
                  />
                  <TheIcon icon="material-symbols:analytics" :size="20" class="text-green-500" />
                </template>
                <div class="flex-1 flex items-center justify-between">
                  <div>
                    <span class="font-medium">{{ a.name }}</span>
                    <span v-if="a.file_size" class="text-gray-400 text-xs ml-2">({{ formatFileSize(a.file_size) }})</span>
                    <NTag size="small" :type="a.source_type === 'correlation' ? 'warning' : 'info'" class="ml-2">
                      {{ a.source_type === 'correlation' ? '关联' : '分析' }}
                    </NTag>
                    <span class="text-gray-400 text-xs ml-3">{{ a.created_at }}</span>
                  </div>
                  <NSpace>
                    <NButton size="tiny" @click="exportAnalysis(a)">
                      <TheIcon icon="material-symbols:download" :size="14" />
                    </NButton>
                    <NPopconfirm @positive-click="deleteAnalysisItem(a)">
                      <template #trigger>
                        <NButton size="tiny" type="error"><TheIcon icon="material-symbols:delete-outline" :size="14" /></NButton>
                      </template>
                    </NPopconfirm>
                  </NSpace>
                </div>
              </NListItem>
            </NList>
            <div v-else class="text-gray-400 text-sm py-4 text-center">暂无分析结果</div>
          </div>
        </div>
      </NSpin>
    </NLayoutContent>
  </NLayout>

  <!-- 工作区弹窗 -->
  <NModal v-model:show="showWsModal" :title="wsEditing ? '编辑工作区' : '新建工作区'" preset="card" style="width: 500px">
    <NForm :model="wsModalForm" label-placement="top">
      <NFormItem label="名称" required>
        <NInput v-model:value="wsModalForm.name" placeholder="工作区名称" />
      </NFormItem>
      <NFormItem label="描述">
        <NInput v-model:value="wsModalForm.description" placeholder="描述" type="textarea" />
      </NFormItem>
      <NFormItem label="授权用户">
        <NSelect v-model:value="wsModalForm.user_ids" :options="userOptions" multiple placeholder="选择用户" filterable />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showWsModal = false">取消</NButton>
        <NButton type="primary" @click="handleWsSubmit">确认</NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- AI 分析弹窗 -->
  <NModal v-model:show="showAnalyzeModal" title="AI 分析" preset="card" style="width: 560px">
    <NForm :model="analyzeForm" label-placement="top">
      <NFormItem label="分析名称" required>
        <NInput v-model:value="analyzeForm.name" placeholder="分析结果名称" />
      </NFormItem>
      <NFormItem label="AI 代理" required>
        <NSelect v-model:value="analyzeForm.ai_proxy_id" :options="proxyOptions" placeholder="选择AI代理" />
      </NFormItem>
      <NFormItem label="辅助 Skill (可选)">
        <NSelect v-model:value="analyzeForm.skill_id" :options="skillOptions" placeholder="选择 Skill 作为分析框架" clearable />
      </NFormItem>
      <NFormItem label="分析提示词">
        <NInput v-model:value="analyzeForm.prompt" type="textarea" placeholder="额外的分析要求..." />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showAnalyzeModal = false">取消</NButton>
        <NButton type="primary" :loading="loading" @click="handleAnalyzeSubmit">开始分析</NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- 关联分析弹窗 -->
  <NModal v-model:show="showCorrelateModal" title="关联分析" preset="card" style="width: 560px">
    <NForm :model="correlateForm" label-placement="top">
      <NFormItem label="分析名称" required>
        <NInput v-model:value="correlateForm.name" placeholder="分析结果名称" />
      </NFormItem>
      <NFormItem label="表格 A" required>
        <NSelect v-model:value="correlateForm.sheet_a_id" :options="sheets.map(s=>({label:s.name,value:s.id}))" placeholder="选择表格A" />
      </NFormItem>
      <NFormItem label="表格 B" required>
        <NSelect v-model:value="correlateForm.sheet_b_id" :options="sheets.map(s=>({label:s.name,value:s.id}))" placeholder="选择表格B" />
      </NFormItem>
      <NFormItem label="AI 代理" required>
        <NSelect v-model:value="correlateForm.ai_proxy_id" :options="proxyOptions" placeholder="选择AI代理" />
      </NFormItem>
      <NFormItem label="辅助 Skill (可选)">
        <NSelect v-model:value="correlateForm.skill_id" :options="skillOptions" placeholder="选择 Skill" clearable />
      </NFormItem>
      <NFormItem label="分析提示词">
        <NInput v-model:value="correlateForm.prompt" type="textarea" placeholder="额外的分析要求..." />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showCorrelateModal = false">取消</NButton>
        <NButton type="primary" :loading="loading" @click="handleCorrelateSubmit">开始分析</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
