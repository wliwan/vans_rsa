<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NButton, NModal, NSpace, NSelect, NPopconfirm,
  NForm, NFormItem, NTag, NUpload, NUploadDragger, NText,
  NCheckbox, NInput, useMessage,
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
} = useDataWorkbench()

// ── 文档状态 ──
const documents = ref([])
const analysisDocuments = ref([])
const selectedDocIds = ref([])
const uploadingDoc = ref(false)
let docUploadDebounceTimer = null

const showDocAnalyzeModal = ref(false)
const docAnalyzeForm = ref({ workspace_id: 0, document_ids: [], ai_proxy_id: null, skill_id: null, prompt: '' })

const selectedAnalysisDocIds = ref([])
const showDocCopyToModal = ref(false)
const docCopyToWorkspaces = ref([])
const docCopyToForm = ref({ target_workspace_id: null })
const showAnalysisDocCopyToModal = ref(false)
const analysisDocCopyToWorkspaces = ref([])
const analysisDocCopyToForm = ref({ target_workspace_id: null })

const showDocTextModal = ref(false)
const docTextForm = ref({ name: '', content: '' })

const showDocEditModal = ref(false)
const editingDoc = ref(null)
const editingDocName = ref('')
const editingDocContent = ref('')
const docSaving = ref(false)
const docEditorContainer = ref(null)
let docVditorInstance = null

const batchDocUploadRef = ref(null)

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

async function handleBatchDocUpload({ file, fileList }) {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_cb53b40f')); return }
  clearTimeout(docUploadDebounceTimer)
  docUploadDebounceTimer = setTimeout(async () => {
    const validFiles = fileList.filter(f => f.file && f.status !== 'removed')
    if (!validFiles.length) return
    uploadingDoc.value = true
    try {
      const files = validFiles.map(f => f.file)
      await api.batchUploadDocuments(selectedWs.value.id, files)
      message.success(`成功上传 ${validFiles.length} 个文件`)
      await loadOriginalDocuments()
    } catch (e) { message.error('批量上传失败') }
    uploadingDoc.value = false
    batchDocUploadRef.value?.clear()
  }, 150)
}

async function downloadDocument(doc) {
  try {
    const res = await api.downloadDocument({ document_id: doc.id })
    const blob = new Blob([res.data], { type: 'application/octet-stream' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    let filename = doc.name || 'document'
    if (doc.source_type === 'analysis' && !filename.endsWith('.md')) {
      filename += '.md'
    }
    a.href = url; a.download = filename; a.click()
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
  if (selectedDocIds.value.length === documents.value.length && documents.value.length > 0) {
    selectedDocIds.value = []
  } else {
    selectedDocIds.value = documents.value.map((d) => d.id)
  }
}

function toggleAnalysisDocSelect(id) {
  const idx = selectedAnalysisDocIds.value.indexOf(id)
  if (idx >= 0) selectedAnalysisDocIds.value.splice(idx, 1)
  else selectedAnalysisDocIds.value.push(id)
}

function toggleAllAnalysisDocs() {
  if (selectedAnalysisDocIds.value.length === analysisDocuments.value.length) {
    selectedAnalysisDocIds.value = []
  } else {
    selectedAnalysisDocIds.value = analysisDocuments.value.map((d) => d.id)
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

async function batchExportDocs() {
  if (!selectedDocIds.value.length) { message.warning('请先选择要导出的文档'); return }
  try {
    loading.value = true
    const res = await api.batchExportDocuments({ document_ids: [...selectedDocIds.value] })
    const blob = new Blob([res.data], { type: 'application/zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = '原始文档批量导出.zip'; a.click()
    URL.revokeObjectURL(url)
    message.success(`已导出 ${selectedDocIds.value.length} 个文档`)
  } catch (e) { message.error(e?.response?.data?.msg || '导出失败') }
  loading.value = false
}

async function batchDeleteAnalysisDocs() {
  if (!selectedAnalysisDocIds.value.length) { message.warning('请先选择要删除的分析文档'); return }
  try {
    loading.value = true
    await api.batchDeleteDocuments({ document_ids: [...selectedAnalysisDocIds.value] })
    selectedAnalysisDocIds.value = []
    message.success('批量删除成功')
    await loadAnalysisDocuments()
  } catch (e) { message.error(e?.response?.data?.msg || '删除失败') }
  loading.value = false
}

async function batchExportAnalysisDocs() {
  if (!selectedAnalysisDocIds.value.length) { message.warning('请先选择要导出的分析文档'); return }
  try {
    loading.value = true
    const res = await api.batchExportDocuments({ document_ids: [...selectedAnalysisDocIds.value] })
    const blob = new Blob([res.data], { type: 'application/zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = '分析文档批量导出.zip'; a.click()
    URL.revokeObjectURL(url)
    message.success(`已导出 ${selectedAnalysisDocIds.value.length} 个分析文档`)
  } catch (e) { message.error(e?.response?.data?.msg || '导出失败') }
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

async function openDocCopyToModal() {
  if (!selectedDocIds.value.length) { message.warning('请先选择要复制的文档'); return }
  docCopyToForm.value = { target_workspace_id: null }; showDocCopyToModal.value = true
  try { const res = await api.getWorkspaceList({ page: 1, page_size: 500 }); docCopyToWorkspaces.value = (res.data || []).filter(w => w.id !== selectedWs.value.id).map(w => ({ label: w.name, value: w.id })) } catch (e) {}
}

async function handleDocCopyToWorkspace() {
  if (!docCopyToForm.value.target_workspace_id) { message.warning('请选择目标工作区'); return }
  loading.value = true; showDocCopyToModal.value = false
  try {
    const res = await api.copyToWorkspace({ target_workspace_id: docCopyToForm.value.target_workspace_id, document_ids: [...selectedDocIds.value] })
    message.success(res.msg || `成功复制 ${res.data?.documents || 0} 个文档`)
    selectedDocIds.value = []
  } catch (e) { message.error(e?.response?.data?.msg || '复制失败') }
  loading.value = false
}

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
      api.getAIProxyList({ page: 1, page_size: 500 }),
      api.getSkillList({ page: 1, page_size: 500 }),
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

async function openAnalysisDocCopyToModal() {
  if (!selectedAnalysisDocIds.value.length) { message.warning('请先选择要复制的分析文档'); return }
  analysisDocCopyToForm.value = { target_workspace_id: null }; showAnalysisDocCopyToModal.value = true
  try { const res = await api.getWorkspaceList({ page: 1, page_size: 500 }); analysisDocCopyToWorkspaces.value = (res.data || []).filter(w => w.id !== selectedWs.value.id).map(w => ({ label: w.name, value: w.id })) } catch (e) {}
}

async function handleAnalysisDocCopyToWorkspace() {
  if (!analysisDocCopyToForm.value.target_workspace_id) { message.warning('请选择目标工作区'); return }
  loading.value = true; showAnalysisDocCopyToModal.value = false
  try {
    const res = await api.copyToWorkspace({ target_workspace_id: analysisDocCopyToForm.value.target_workspace_id, document_ids: [...selectedAnalysisDocIds.value] })
    message.success(res.msg || `成功复制 ${res.data?.documents || 0} 个分析文档`)
    selectedAnalysisDocIds.value = []
  } catch (e) { message.error(e?.response?.data?.msg || '复制失败') }
  loading.value = false
}

function openDocTextModal() {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_cb53b40f')); return }
  docTextForm.value = { name: '', content: '' }
  showDocTextModal.value = true
}

async function handleDocTextSubmit() {
  if (!docTextForm.value.name) { message.warning('请输入文档名称'); return }
  if (!docTextForm.value.content) { message.warning('请输入文档内容'); return }
  loading.value = true; showDocTextModal.value = false
  try {
    await api.createDocumentFromText({ workspace_id: selectedWs.value.id, name: docTextForm.value.name, content: docTextForm.value.content })
    message.success('文本导入成功')
    await loadOriginalDocuments()
  } catch (e) { message.error(e?.response?.data?.msg || '导入失败') }
  loading.value = false
}

// ── 文档编辑（Vditor） ──
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
  editingDocName.value = doc.name || ''
  showDocEditModal.value = true
  editingDocContent.value = ''
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
  const name = editingDocName.value?.trim()
  docSaving.value = true
  try {
    const payload = { document_id: editingDoc.value.id, content }
    if (name && name !== editingDoc.value.name) {
      payload.name = name
    }
    const res = await api.updateDocumentContent(payload)
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

// ── watch ──
watch(() => selectedWs.value, (ws) => {
  if (ws) {
    loadOriginalDocuments()
    loadAnalysisDocuments()
  } else {
    documents.value = []
    analysisDocuments.value = []
    selectedDocIds.value = []
    selectedAnalysisDocIds.value = []
  }
}, { immediate: true })

onBeforeUnmount(() => { destroyDocVditor() })

defineExpose({ loadOriginalDocuments, loadAnalysisDocuments })
</script>

<template>
              <div class="flex-1 flex flex-col" style="min-height: 0; overflow: hidden">
                <!-- 上传区 -->
                <div class="mb-5">
                  <div class="flex items-center gap-2 mb-2">
                    <NButton size="small" @click="openDocTextModal">
                      <TheIcon icon="material-symbols:edit-note" :size="16" class="mr-1" />文本导入
                    </NButton>
                  </div>
                  <NUpload ref="batchDocUploadRef" :show-file-list="false" :default-upload="false" accept=".txt,.md,.pdf,.docx,.ppt,.pptx,.xlsx,.xls,.csv" multiple @change="handleBatchDocUpload">
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

                <!-- 左右双栏布局（移动端堆叠） -->
                <div class="flex gap-3 flex-1" :class="{ 'mobile-stack': isMobileCollapsed }" style="min-height: 0; overflow: hidden">
                  <!-- ── 左栏：原始文档 ── -->
                  <div class="flex-1 flex flex-col" style="min-width: 0; min-height: 0; overflow: hidden">
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
                        <NButton size="small" :disabled="!selectedDocIds.length" @click="batchExportDocs">
                          <TheIcon icon="material-symbols:download" :size="16" class="mr-1" />导出({{ selectedDocIds.length }})
                        </NButton>
                        <NButton size="small" :disabled="!selectedDocIds.length" @click="openDocCopyToModal">
                          <TheIcon icon="material-symbols:content-copy" :size="16" class="mr-1" />复制到
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
                  <div class="flex-1 flex flex-col" style="min-width: 0; min-height: 0; overflow: hidden">
                    <div class="flex items-center justify-between mb-2 px-1">
                      <div class="flex items-center gap-2">
                        <NCheckbox
                          size="small"
                          :checked="selectedAnalysisDocIds.length === analysisDocuments.length && analysisDocuments.length > 0"
                          :indeterminate="selectedAnalysisDocIds.length > 0 && selectedAnalysisDocIds.length < analysisDocuments.length"
                          @update:checked="toggleAllAnalysisDocs"
                        />
                        <TheIcon icon="material-symbols:analytics" :size="20" class="text-green-500" />
                        <span class="font-semibold text-base">{{ t('views.statistic-center.label_cn_c57e8ae8') }}</span>
                        <NTag size="small" :bordered="false" type="success">{{ analysisDocuments.length }}</NTag>
                      </div>
                      <NSpace v-if="analysisDocuments.length" size="small">
                        <NButton size="small" :disabled="!selectedAnalysisDocIds.length" @click="batchExportAnalysisDocs">
                          <TheIcon icon="material-symbols:download" :size="16" class="mr-1" />导出({{ selectedAnalysisDocIds.length }})
                        </NButton>
                        <NButton size="small" :disabled="!selectedAnalysisDocIds.length" @click="openAnalysisDocCopyToModal">
                          <TheIcon icon="material-symbols:content-copy" :size="16" class="mr-1" />复制到
                        </NButton>
                        <NPopconfirm @positive-click="batchDeleteAnalysisDocs" :disabled="!selectedAnalysisDocIds.length">
                          <template #trigger>
                            <NButton size="small" type="warning" :disabled="!selectedAnalysisDocIds.length">
                              <TheIcon icon="material-symbols:delete-outline" :size="16" />{{ t('views.statistic-center.label_cn_2f4aaddd') }}
                            </NButton>
                          </template>
                          确认删除选中的 {{ selectedAnalysisDocIds.length }} 个分析文档？
                        </NPopconfirm>
                      </NSpace>
                    </div>
                    <div class="flex-1 overflow-auto rounded-lg border border-gray-100 bg-gray-50/50 dark:bg-gray-800/30" style="min-height: 0">
                      <div v-if="analysisDocuments.length" class="p-3 grid gap-3">
                        <div
                          v-for="a in analysisDocuments" :key="a.id"
                          class="bg-white dark:bg-gray-800 rounded-lg border border-gray-100 p-4 hover:shadow-sm transition-shadow"
                        >
                          <div class="flex items-center justify-between">
                            <div class="flex items-center gap-3 min-w-0 flex-1">
                              <NCheckbox
                                size="small"
                                :checked="selectedAnalysisDocIds.includes(a.id)"
                                @update:checked="() => toggleAnalysisDocSelect(a.id)"
                                class="flex-shrink-0"
                              />
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


<!-- 文档AI分析弹窗 -->
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


<!-- 文档编辑弹窗（Vditor） -->
  <NModal
    v-model:show="showDocEditModal"
    :title="t('views.statistic-center.title_cn_0b61ccf8') + (editingDocName || editingDoc?.name || '')"
    preset="card"
    style="width: 900px"
    @after-leave="destroyDocVditor"
  >
    <div class="mb-3">
      <div class="text-sm text-gray-500 mb-1">{{ $t('views.statistic-center.label_cn_59cd198d') }}名称</div>
      <NInput v-model:value="editingDocName" placeholder="输入文档名称" />
    </div>
    <div ref="docEditorContainer" style="height: 55vh; min-height: 380px" />
    <template #footer>
      <NSpace justify="end">
        <NButton @click="handleDocEditCancel">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton>
        <NButton type="primary" :loading="docSaving" @click="handleDocSave">{{ t('views.statistic-center.label_cn_be5fbbe3') }}</NButton>
      </NSpace>
    </template>
  </NModal>


<!-- 原始文档复制到弹窗 -->
  <NModal v-model:show="showDocCopyToModal" title="复制文档到其他工作区" preset="card" style="width: 480px">
    <div class="text-sm text-gray-500 mb-4">将复制 {{ selectedDocIds.length }} 个文档到目标工作区。<br/>新建数据库记录指向源文件，共享同一物理文件。删除记录时不会影响其他工作区。</div>
    <NForm label-placement="top">
      <NFormItem label="目标工作区" required>
        <NSelect v-model:value="docCopyToForm.target_workspace_id" :options="docCopyToWorkspaces" placeholder="选择目标工作区" filterable />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showDocCopyToModal = false">取消</NButton>
        <NButton type="primary" :disabled="!docCopyToForm.target_workspace_id" :loading="loading" @click="handleDocCopyToWorkspace">确认复制</NButton>
      </NSpace>
    </template>
  </NModal>


<!-- 分析文档复制到弹窗 -->
  <NModal v-model:show="showAnalysisDocCopyToModal" title="复制分析文档到其他工作区" preset="card" style="width: 480px">
    <div class="text-sm text-gray-500 mb-4">将复制 {{ selectedAnalysisDocIds.length }} 个分析文档到目标工作区。<br/>新建数据库记录指向源文件，共享同一物理文件。删除记录时不会影响其他工作区。</div>
    <NForm label-placement="top">
      <NFormItem label="目标工作区" required>
        <NSelect v-model:value="analysisDocCopyToForm.target_workspace_id" :options="analysisDocCopyToWorkspaces" placeholder="选择目标工作区" filterable />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showAnalysisDocCopyToModal = false">取消</NButton>
        <NButton type="primary" :disabled="!analysisDocCopyToForm.target_workspace_id" :loading="loading" @click="handleAnalysisDocCopyToWorkspace">确认复制</NButton>
      </NSpace>
    </template>
  </NModal>


<!-- 文档文本导入弹窗 -->
  <NModal v-model:show="showDocTextModal" title="文本导入文档" preset="card" style="width: 640px">
    <NForm :model="docTextForm" label-placement="top">
      <NFormItem label="文档名称" required>
        <NInput v-model:value="docTextForm.name" placeholder="例如：会议记录.md" />
      </NFormItem>
      <NFormItem label="文档内容（Markdown）" required>
        <NInput v-model:value="docTextForm.content" type="textarea" :rows="12" placeholder="输入 Markdown 格式的文档内容" />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showDocTextModal = false">取消</NButton>
        <NButton type="primary" :loading="loading" @click="handleDocTextSubmit">导入</NButton>
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
