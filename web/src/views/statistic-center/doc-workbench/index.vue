<script setup>
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import { computed, onMounted, onBeforeUnmount, onActivated, onDeactivated, ref, nextTick, watch } from 'vue'
import { useBreakpoints } from '@vueuse/core'
import {


  NButton, NButtonGroup, NInput,
  NModal, NSpace, NSelect, NPopconfirm,
  NForm, NFormItem, NTag, NDivider, NSpin, NSwitch, useMessage,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import DocWorkbenchSidebar from '@/components/common/DocWorkbenchSidebar.vue'
import api from '@/api'
import { useTaskProgressStore } from '@/store/modules/taskProgress'


const { t } = useI18n()

defineOptions({ name: i18n.global.t('views.statistic-center.title_cn_c56cb26a') })

const message = useMessage()

// 默认系统提示词（与后端 ReportService.DEFAULT_SYSTEM_PROMPT 保持一致）
const DEFAULT_SYSTEM_PROMPT = [
  '你是一个专业的数据分析文书生成专家。请根据提供的数据生成一份完整的HTML格式分析文书。',
  '文书需包含以下部分（使用HTML标签）：',
  '1. <h1> 文书标题',
  '2. <h2> 数据概览 — 数据来源、数据量等',
  '3. <h2> 核心发现 — 3-5个关键洞察',
  '4. <h2> 详细分析 — 多维度数据解读，包含 <table> 表格',
  '5. <h2> 结论与建议',
  '样式要求：使用内联CSS，简洁专业风格，配色为蓝白灰。',
].join('\n')

// 移动端适配
const bp = reactive(useBreakpoints({ sm: 640, md: 991 }))
const isMobile = computed(() => bp.isSmaller('sm'))
const panelVisible = ref(true)
watch(isMobile, (val) => { if (val) panelVisible.value = false })

// 数据源总数
const totalDataSourceCount = computed(() => {
  return allSheets.value.length + allAnalyses.value.length
    + allDocuments.value.length + allDatabaseDocs.value.length
    + allStaticFiles.value.length
})

// 分区统计（全选/部分选/全不选）
const sectionStats = computed(() => {
  const stats = {}
  const entries = [
    ['sheets', allSheets, checkedSheetIds],
    ['analyses', allAnalyses, checkedAnalysisIds],
    ['documents', allDocuments, checkedDocumentIds],
    ['database', allDatabaseDocs, checkedDatabaseDocIds],
    ['staticFiles', allStaticFiles, checkedStaticFileIds],
  ]
  for (const [key, all, checked] of entries) {
    const total = all.value.length
    const sel = checked.value.length
    stats[key] = { total, selected: sel, all: total > 0 && sel === total, partial: sel > 0 && sel < total }
  }
  return stats
})

function formatFileSize(bytes) {
  if (bytes == null || bytes === 0) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// 状态
const workspaces = ref([])
const selectedWs = ref(null)
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
  ai_proxy_id: null, skill_id: null, system_prompt: DEFAULT_SYSTEM_PROMPT, prompt: '',
})
const proxyOptions = ref([])
const skillOptions = ref([])
const workspaceOptions = ref([])

// 各分区完整对象列表
const allSheets = ref([])
const allAnalyses = ref([])
const allDocuments = ref([])      // 普通文档
const allDatabaseDocs = ref([])   // 数据库导入的文档
const allStaticFiles = ref([])

// 各分区选中 ID
const checkedSheetIds = ref([])
const checkedAnalysisIds = ref([])
const checkedDocumentIds = ref([])
const checkedDatabaseDocIds = ref([])
const checkedStaticFileIds = ref([])

// 分区数据（作为 computed，使 label 能正确调用 t()）
const dataSourceSections = computed(() => [
  { key: 'sheets', label: t('views.statistic-center.label_cn_642e5368'), icon: 'material-symbols:table', color: 'blue', list: allSheets.value },
  { key: 'analyses', label: t('views.statistic-center.label_cn_d93cc1b1'), icon: 'material-symbols:analytics', color: 'green', list: allAnalyses.value },
  { key: 'documents', label: t('views.statistic-center.label_cn_c35ee691'), icon: 'material-symbols:description', color: 'purple', list: allDocuments.value },
  { key: 'database', label: t('views.statistic-center.label_cn_5bac3fe5'), icon: 'material-symbols:database', color: 'orange', list: allDatabaseDocs.value },
  { key: 'staticFiles', label: t('views.statistic-center.label_cn_28f6e7a6'), icon: 'material-symbols:folder', color: 'teal', list: allStaticFiles.value },
])

// 分区展开状态
const expandedSections = ref({
  sheets: false, analyses: false, documents: false, database: false, staticFiles: false,
})

const dataSourcesLoading = ref(false)

// 预览数据
const previewData = ref(null)
const previewLoading = ref(false)

// 克隆弹窗
const showCloneModal = ref(false)
const cloneMode = ref('normal') // 'normal' | 'ai'
const cloneForm = ref({ id: 0, name: '', target_language: '', ai_proxy_id: null })
const cloneTranslateLoading = ref(false)
const cloneProxyOptions = ref([])
const languageOptions = [
  // 东亚
  { label: '中文 (Chinese)', value: 'Chinese' },
  { label: '日语 (Japanese)', value: 'Japanese' },
  { label: '韩语 (Korean)', value: 'Korean' },
  { label: '蒙古语 (Mongolian)', value: 'Mongolian' },
  // 东南亚
  { label: '越南语 (Vietnamese)', value: 'Vietnamese' },
  { label: '泰语 (Thai)', value: 'Thai' },
  { label: '印尼语 (Indonesian)', value: 'Indonesian' },
  { label: '马来语 (Malay)', value: 'Malay' },
  { label: '菲律宾语 (Filipino)', value: 'Filipino' },
  { label: '缅甸语 (Burmese)', value: 'Burmese' },
  { label: '高棉语 (Khmer)', value: 'Khmer' },
  { label: '老挝语 (Lao)', value: 'Lao' },
  // 南亚
  { label: '印地语 (Hindi)', value: 'Hindi' },
  { label: '孟加拉语 (Bengali)', value: 'Bengali' },
  { label: '乌尔都语 (Urdu)', value: 'Urdu' },
  { label: '泰米尔语 (Tamil)', value: 'Tamil' },
  { label: '泰卢固语 (Telugu)', value: 'Telugu' },
  { label: '马拉地语 (Marathi)', value: 'Marathi' },
  { label: '古吉拉特语 (Gujarati)', value: 'Gujarati' },
  { label: '旁遮普语 (Punjabi)', value: 'Punjabi' },
  { label: '僧伽罗语 (Sinhala)', value: 'Sinhala' },
  { label: '尼泊尔语 (Nepali)', value: 'Nepali' },
  // 中东 / 中亚
  { label: '阿拉伯语 (Arabic)', value: 'Arabic' },
  { label: '波斯语 (Persian)', value: 'Persian' },
  { label: '希伯来语 (Hebrew)', value: 'Hebrew' },
  { label: '土耳其语 (Turkish)', value: 'Turkish' },
  { label: '哈萨克语 (Kazakh)', value: 'Kazakh' },
  { label: '乌兹别克语 (Uzbek)', value: 'Uzbek' },
  // 欧洲 — 日耳曼
  { label: '英语 (English)', value: 'English' },
  { label: '德语 (German)', value: 'German' },
  { label: '荷兰语 (Dutch)', value: 'Dutch' },
  { label: '瑞典语 (Swedish)', value: 'Swedish' },
  { label: '丹麦语 (Danish)', value: 'Danish' },
  { label: '挪威语 (Norwegian)', value: 'Norwegian' },
  { label: '冰岛语 (Icelandic)', value: 'Icelandic' },
  { label: '南非荷兰语 (Afrikaans)', value: 'Afrikaans' },
  // 欧洲 — 罗曼
  { label: '法语 (French)', value: 'French' },
  { label: '西班牙语 (Spanish)', value: 'Spanish' },
  { label: '葡萄牙语 (Portuguese)', value: 'Portuguese' },
  { label: '意大利语 (Italian)', value: 'Italian' },
  { label: '罗马尼亚语 (Romanian)', value: 'Romanian' },
  { label: '加泰罗尼亚语 (Catalan)', value: 'Catalan' },
  { label: '加利西亚语 (Galician)', value: 'Galician' },
  // 欧洲 — 斯拉夫
  { label: '俄语 (Russian)', value: 'Russian' },
  { label: '波兰语 (Polish)', value: 'Polish' },
  { label: '捷克语 (Czech)', value: 'Czech' },
  { label: '乌克兰语 (Ukrainian)', value: 'Ukrainian' },
  { label: '保加利亚语 (Bulgarian)', value: 'Bulgarian' },
  { label: '克罗地亚语 (Croatian)', value: 'Croatian' },
  { label: '塞尔维亚语 (Serbian)', value: 'Serbian' },
  { label: '斯洛伐克语 (Slovak)', value: 'Slovak' },
  { label: '斯洛文尼亚语 (Slovenian)', value: 'Slovenian' },
  // 欧洲 — 其他
  { label: '希腊语 (Greek)', value: 'Greek' },
  { label: '匈牙利语 (Hungarian)', value: 'Hungarian' },
  { label: '芬兰语 (Finnish)', value: 'Finnish' },
  { label: '立陶宛语 (Lithuanian)', value: 'Lithuanian' },
  { label: '拉脱维亚语 (Latvian)', value: 'Latvian' },
  { label: '爱沙尼亚语 (Estonian)', value: 'Estonian' },
  { label: '巴斯克语 (Basque)', value: 'Basque' },
  // 非洲
  { label: '斯瓦希里语 (Swahili)', value: 'Swahili' },
  { label: '阿姆哈拉语 (Amharic)', value: 'Amharic' },
  { label: '豪萨语 (Hausa)', value: 'Hausa' },
  { label: '约鲁巴语 (Yoruba)', value: 'Yoruba' },
  { label: '祖鲁语 (Zulu)', value: 'Zulu' },
  // 美洲 / 大洋洲
  { label: '海地克里奥尔语 (Haitian Creole)', value: 'Haitian Creole' },
  { label: '毛利语 (Maori)', value: 'Maori' },
  { label: '夏威夷语 (Hawaiian)', value: 'Hawaiian' },
  // 其他
  { label: '世界语 (Esperanto)', value: 'Esperanto' },
  { label: '拉丁语 (Latin)', value: 'Latin' },
]

// 工作区列表
async function loadWorkspaces() {
  try {
    const res = await api.getWorkspaceList({ page: 1, page_size: 9999 })
    workspaces.value = res.data || []
  } catch (e) { message.error(t('views.statistic-center.message_cn_17eec3f1')) }
}

async function onReportSelect(r) {
  selectedReport.value = r
  panelVisible.value = false
  try {
    const res = await api.getReportById({ report_id: r.id })
    editContent.value = res.data.content || ''
    initCodeMirror()
  } catch (e) { message.error(t('views.statistic-center.message_cn_9e2437e3')) }
}

function onContentClick() {
  if (panelVisible.value && isMobile.value) {
    panelVisible.value = false
  }
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
      console.error(t('views.statistic-center.label_codemirror_cn_381dcca2'), e)
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

// ── 生成弹窗逻辑 ──

// 从 localStorage 读取用户自定义的系统提示词，没有则用默认值
function loadSystemPrompt() {
  try {
    const saved = localStorage.getItem('vfa_doc_system_prompt')
    if (saved && saved.trim()) return saved
  } catch (e) { /* ignore */ }
  return DEFAULT_SYSTEM_PROMPT
}

function resetSystemPrompt() {
  generateForm.value.system_prompt = DEFAULT_SYSTEM_PROMPT
  try { localStorage.removeItem('vfa_doc_system_prompt') } catch (e) { /* ignore */ }
  message.success('已恢复默认系统提示词')
}

function saveSystemPrompt() {
  const val = generateForm.value.system_prompt?.trim()
  if (!val) { message.warning('系统提示词不能为空'); return }
  try { localStorage.setItem('vfa_doc_system_prompt', val) } catch (e) { /* ignore */ }
  message.success('系统提示词已保存，下次打开弹窗将自动使用')
}

function openGenerate() {
  generateForm.value = {
    workspace_id: selectedWs.value?.id || null, name: t('views.statistic-center.label_cn_ad2f550c'),
    ai_proxy_id: null, skill_id: null, system_prompt: loadSystemPrompt(), prompt: '',
  }
  workspaceOptions.value = workspaces.value.map((w) => ({ label: w.name, value: w.id }))
  resetAllSources()
  previewData.value = null
  // 如果左侧已选工作区，预加载
  if (selectedWs.value) {
    generateForm.value.workspace_id = selectedWs.value.id
    loadAllDataSources(selectedWs.value.id)
  }
  api.getAIProxyList({ page: 1, page_size: 9999 }).then((res) => {
    proxyOptions.value = (res.data || []).map((p) => ({ label: p.name, value: p.id }))
  })
  api.getSkillList({ page: 1, page_size: 9999 }).then((res) => {
    skillOptions.value = (res.data || []).map((s) => ({ label: s.title, value: s.id }))
  })
  showGenerateModal.value = true
}

function resetAllSources() {
  allSheets.value = []; allAnalyses.value = []
  allDocuments.value = []; allDatabaseDocs.value = []; allStaticFiles.value = []
  checkedSheetIds.value = []; checkedAnalysisIds.value = []
  checkedDocumentIds.value = []; checkedDatabaseDocIds.value = []; checkedStaticFileIds.value = []
  expandedSections.value = { sheets: false, analyses: false, documents: false, database: false, staticFiles: false }
  previewData.value = null
}

async function onGenerateWsChange(wsId) {
  resetAllSources()
  if (wsId) {
    await loadAllDataSources(wsId)
  }
}

async function loadAllDataSources(wsId) {
  if (!wsId) return
  dataSourcesLoading.value = true
  try {
    const [sh, an, docs, sfs] = await Promise.all([
      api.getSheetList({ workspace_id: wsId }),
      api.getAnalysisList({ workspace_id: wsId }),
      api.getDocumentList({ workspace_id: wsId }),
      api.getStaticFileList({ workspace_id: wsId }),
    ])
    allSheets.value = sh.data || []
    allAnalyses.value = an.data || []
    const documents = docs.data || []
    allStaticFiles.value = sfs.data || []

    // 文档分为普通文档和数据库导入文档
    allDocuments.value = documents.filter((d) => !d.import_source || d.import_source === 'upload')
    allDatabaseDocs.value = documents.filter((d) => d.import_source && d.import_source !== 'upload')

    // 默认全选
    checkedSheetIds.value = allSheets.value.map((s) => s.id)
    checkedAnalysisIds.value = allAnalyses.value.map((a) => a.id)
    checkedDocumentIds.value = allDocuments.value.map((d) => d.id)
    checkedDatabaseDocIds.value = allDatabaseDocs.value.map((d) => d.id)
    checkedStaticFileIds.value = allStaticFiles.value.map((f) => f.id)
  } catch (e) {
    message.error(t('views.statistic-center.message_cn_049f7ea6'))
  }
  dataSourcesLoading.value = false
}

// ── 分区操作 ──

function toggleSection(key) {
  expandedSections.value[key] = !expandedSections.value[key]
}

function toggleSectionAll(key) {
  const map = {
    sheets: [allSheets, checkedSheetIds],
    analyses: [allAnalyses, checkedAnalysisIds],
    documents: [allDocuments, checkedDocumentIds],
    database: [allDatabaseDocs, checkedDatabaseDocIds],
    staticFiles: [allStaticFiles, checkedStaticFileIds],
  }
  const [all, checked] = map[key]
  if (checked.value.length === all.value.length) {
    checked.value = []
  } else {
    checked.value = all.value.map((it) => it.id)
  }
}

function isItemChecked(key, id) {
  const map = { sheets: checkedSheetIds, analyses: checkedAnalysisIds, documents: checkedDocumentIds, database: checkedDatabaseDocIds, staticFiles: checkedStaticFileIds }
  return (map[key]?.value || []).includes(id)
}

function toggleItem(key, id) {
  const map = { sheets: checkedSheetIds, analyses: checkedAnalysisIds, documents: checkedDocumentIds, database: checkedDatabaseDocIds, staticFiles: checkedStaticFileIds }
  const arr = map[key]?.value
  if (!arr) return
  const idx = arr.indexOf(id)
  if (idx >= 0) arr.splice(idx, 1)
  else arr.push(id)
}

// ── 预览 ──

async function handlePreview() {
  const sourceSheetIds = [...checkedSheetIds.value, ...checkedAnalysisIds.value]
  const sourceDocIds = [...checkedDocumentIds.value, ...checkedDatabaseDocIds.value]
  const sourceStaticIds = [...checkedStaticFileIds.value]

  const total = sourceSheetIds.length + sourceDocIds.length + sourceStaticIds.length
  if (total === 0) {
    message.warning(t('views.statistic-center.message_cn_2aec724b')); return
  }

  previewLoading.value = true
  try {
    const res = await api.previewSources({
      sheet_ids: sourceSheetIds,
      analysis_ids: [],
      document_ids: sourceDocIds,
      static_file_ids: sourceStaticIds,
    })
    previewData.value = res.data
  } catch (e) {
    message.error(t('views.statistic-center.message_cn_6a3a5ef0'))
  }
  previewLoading.value = false
}

// ── 提交 ──

async function handleGenerate() {
  if (!generateForm.value.workspace_id) { message.warning(t('views.statistic-center.placeholder_cn_9d91d621')); return }
  if (!generateForm.value.ai_proxy_id) { message.warning(t('views.skill.placeholder_cn_ee488ec6')); return }

  const sourceSheetIds = [...checkedSheetIds.value, ...checkedAnalysisIds.value]
  const sourceDocIds = [...checkedDocumentIds.value, ...checkedDatabaseDocIds.value]
  const sourceStaticIds = [...checkedStaticFileIds.value]

  const totalSources = sourceSheetIds.length + sourceDocIds.length + sourceStaticIds.length
  if (totalSources === 0) {
    message.warning(t('views.statistic-center.message_cn_2aec724b')); return
  }

  // 关闭弹窗，启动全局任务进度
  showGenerateModal.value = false
  doGenerateTask()
}

// 抽取为独立函数，供重试回调使用
function doGenerateTask() {
  const taskStore = useTaskProgressStore()
  const reportName = generateForm.value.name

  // 启动全局任务进度弹窗，标题直接显示文书名称
  const taskId = taskStore.startTask(
    `${t('views.statistic-center.label_cn_acc23771', { generateForm_value_name: reportName })}`,
    () => { doGenerateTask() }
  )

  const sourceSheetIds = [...checkedSheetIds.value, ...checkedAnalysisIds.value]
  const sourceDocIds = [...checkedDocumentIds.value, ...checkedDatabaseDocIds.value]
  const sourceStaticIds = [...checkedStaticFileIds.value]

  // 1. 发起异步生成请求 → 获取 task_id
  api.generateReport({
    workspace_id: generateForm.value.workspace_id,
    name: reportName,
    source_sheet_ids: sourceSheetIds,
    source_analysis_ids: [],
    source_document_ids: sourceDocIds,
    source_static_ids: sourceStaticIds,
    ai_proxy_id: generateForm.value.ai_proxy_id,
    skill_id: generateForm.value.skill_id,
    system_prompt: generateForm.value.system_prompt,
    prompt: generateForm.value.prompt,
  }).then(async (res) => {
    const backendTaskId = res?.data?.task_id
    if (!backendTaskId) {
      taskStore.failTask(taskId, { message: t('views.statistic-center.label_cn_53515592'), detail: '未获取到任务ID' })
      message.error(t('views.statistic-center.label_cn_53515592'))
      return
    }

    // 2. 轮询后端进度
    const pollInterval = 1500
    const maxPolls = 600 // 最多 15 分钟
    let pollCount = 0

    const poll = async () => {
      pollCount++
      try {
        const progressRes = await api.getReportGenerateProgress({ task_id: backendTaskId })
        const progress = progressRes?.data || {}

        if (progress.status === 'error') {
          taskStore.failTask(taskId, {
            message: t('views.statistic-center.label_cn_53515592'),
            detail: progress.detail || progress.message || t('views.network.roadNetworkWorkbench.messages.unknownError'),
          })
          message.error(t('views.statistic-center.label_cn_53515592'))
          return
        }

        if (progress.status === 'done') {
          // 3. 生成完成 → 获取结果
          taskStore.updateProgress(taskId, { progress: 95, message: progress.message || '文书生成完成，正在获取结果...' })
          try {
            const resultRes = await api.getReportGenerateResult({ task_id: backendTaskId })
            taskStore.finishTask(taskId, t('views.statistic-center.label_cn_844785de'))
            message.success(t('views.statistic-center.message_cn_23799178'))
            loadReports()
          } catch (resultErr) {
            const errMsg = resultErr?.response?.data?.msg || resultErr?.message || t('views.network.roadNetworkWorkbench.messages.unknownError')
            taskStore.failTask(taskId, { message: t('views.statistic-center.label_cn_53515592'), detail: errMsg })
            message.error(t('views.statistic-center.label_cn_53515592'))
          }
          return
        }

        // 4. 更新进度（来自后端的真实进度 + 阶段描述）
        const progressPct = progress.progress ?? 0
        const phaseLabel = getPhaseLabel(progress.phase)
        const displayMessage = phaseLabel
          ? `${phaseLabel}: ${progress.message || ''}`
          : (progress.message || t('views.statistic-center.label_ai_cn_7a58217b'))

        taskStore.updateProgress(taskId, {
          progress: progressPct,
          message: displayMessage,
          phase: progress.phase || '',
        })

        // 5. 继续轮询
        if (pollCount < maxPolls) {
          setTimeout(poll, pollInterval)
        } else {
          taskStore.failTask(taskId, {
            message: t('views.statistic-center.label_cn_53515592'),
            detail: '生成超时（超过 15 分钟）',
          })
          message.error(t('views.statistic-center.label_cn_53515592'))
        }
      } catch (pollErr) {
        // 轮询请求失败（网络波动等），继续重试
        if (pollCount < maxPolls) {
          setTimeout(poll, pollInterval * 2)
        } else {
          taskStore.failTask(taskId, {
            message: t('views.statistic-center.label_cn_53515592'),
            detail: pollErr?.response?.data?.msg || pollErr?.message || '轮询失败',
          })
        }
      }
    }

    // 启动第一次轮询
    poll()
  }).catch((e) => {
    const errMsg = e?.response?.data?.msg || e?.message || t('views.network.roadNetworkWorkbench.messages.unknownError')
    taskStore.failTask(taskId, { message: t('views.statistic-center.label_cn_53515592'), detail: errMsg })
    message.error(t('views.statistic-center.label_cn_53515592'))
  })
}

// 阶段中文标签映射
function getPhaseLabel(phase) {
  const map = {
    preparing: '准备素材',
    planning: '规划大纲',
    generating: '生成章节',
    assembling: '组装文书',
    saving: '保存文书',
  }
  return map[phase] || ''
}

// 保存编辑

// 处理 viewport + body min-width，在移动端保持桌面排版且自动缩放适配屏幕
function injectViewportMeta(html) {
  // 1. 如果 AI 生成的 HTML 带有 viewport meta，移除它（避免 width=device-width 导致响应式重排）
  //    没有 viewport meta 时浏览器默认视口 ~980px，会自动缩放适配屏幕
  if (/<meta[^>]*name=["']viewport["'][^>]*>/i.test(html)) {
    html = html.replace(/<meta[^>]*name=["']viewport["'][^>]*>/i, '')
  }

  // 2. 给 <body> 注入 min-width:1024px，CSS 层面守住桌面排版不被压缩
  if (/<body[^>]*>/i.test(html)) {
    if (/\sstyle=["']/i.test(html.match(/<body[^>]*>/i)[0])) {
      html = html.replace(
        /(<body[^>]*style=["'])([^"']*)/i,
        '$1min-width:1024px;$2'
      )
    } else {
      html = html.replace(
        /<body/i,
        '<body style="min-width:1024px"'
      )
    }
  }

  return html
}

// 预览 iframe 内容同步（沙箱隔离，防止文书 CSS 污染全局）
watch(editContent, (html) => {
  nextTick(() => {
    if (previewFrame.value) {
      previewFrame.value.srcdoc = injectViewportMeta(html)
    }
  })
})

async function saveEdit() {
  if (!selectedReport.value) return
  try {
    await api.updateReport({ id: selectedReport.value.id, content: editContent.value })
    message.success(t('views.skill.message_cn_3b108349'))
    if (cmInstance) cmInstance.setValue(editContent.value)
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.saveFail')) }
}

// 克隆
function openClone() {
  if (!selectedReport.value) { message.warning(t('views.statistic-center.placeholder_cn_0feed934')); return }
  cloneMode.value = 'normal'
  cloneForm.value = { id: selectedReport.value.id, name: selectedReport.value.name + t('views.statistic-center.label_cn_a3033ebf'), target_language: 'English', ai_proxy_id: null }
  // 预加载 AI 代理列表
  api.getAIProxyList({ page: 1, page_size: 9999 }).then((res) => {
    cloneProxyOptions.value = (res.data || []).map((p) => ({ label: p.name, value: p.id }))
  })
  showCloneModal.value = true
}

async function handleClone() {
  if (cloneMode.value === 'ai') {
    await handleCloneTranslate()
    return
  }
  try {
    await api.cloneReport(cloneForm.value)
    message.success(t('views.statistic-center.message_cn_473604c8'))
    showCloneModal.value = false
    await loadReports()
  } catch (e) { message.error(t('views.statistic-center.message_cn_6dc5b375')) }
}

async function handleCloneTranslate() {
  if (!cloneForm.value.target_language) { message.warning('请选择目标语言'); return }
  if (!cloneForm.value.ai_proxy_id) { message.warning('请选择AI代理'); return }
  cloneTranslateLoading.value = true
  try {
    const res = await api.cloneReportTranslate(cloneForm.value)
    message.success(res.msg || '翻译克隆成功')
    showCloneModal.value = false
    await loadReports()
  } catch (e) { message.error(e.message || '翻译克隆失败') }
  cloneTranslateLoading.value = false
}

// 删除
async function deleteReport() {
  if (!selectedReport.value) return
  try {
    await api.deleteReport({ report_id: selectedReport.value.id })
    selectedReport.value = null
    editContent.value = ''
    await loadReports()
  } catch (e) { message.error(t('views.network.roadNetworkWorkbench.messages.deleteFail')) }
}

// 导出
function downloadBlob(data, filename) {
  // data 是 axios responseType:'blob' 返回的 Blob，直接使用不重新包装
  const blob = data instanceof Blob ? data : new Blob([data])
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.style.display = 'none'
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  // 延迟释放 URL，确保浏览器有时间启动下载
  setTimeout(() => {
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  }, 150)
}

function printReport() {
  if (!selectedReport.value) return
  const html = editContent.value
  if (!html) { message.warning(t('views.statistic-center.message_cn_4de2b097')); return }
  const printWindow = window.open('', '_blank')
  if (!printWindow) { message.error(t('views.statistic-center.message_cn_525920bc')); return }
  printWindow.document.write(html)
  printWindow.document.close()
  printWindow.focus()
  printWindow.onload = () => {
    printWindow.print()
    printWindow.onafterprint = () => printWindow.close()
  }
}

async function exportReport(type) {
  if (!selectedReport.value) return
  const apiMap = { html: api.exportReportHtml, docx: api.exportReportDocx }
  const extMap = { html: '.html', docx: '.docx' }
  try {
    const res = await apiMap[type]({ report_id: selectedReport.value.id })
    downloadBlob(res.data, selectedReport.value.name + extMap[type])
  } catch (e) { message.error(t('views.statistic-center.message_cn_bfc4674f', { type: type })) }
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
  <div class="flex" style="height: calc(100vh - 120px)">
    <!-- 左侧侧边栏 -->
    <DocWorkbenchSidebar
      v-model:visible="panelVisible"
      :is-mobile="isMobile"
      :workspaces="workspaces"
      style="width: 300px; flex-shrink: 0"
      @select-ws="(ws) => selectedWs = ws"
      @select-report="onReportSelect"
      @hide="panelVisible = false"
      @generate="openGenerate"
    />

    <!-- 右侧内容 -->
    <div
      class="flex-1 min-w-0 overflow-hidden flex flex-col"
      @click="onContentClick"
    >
      <!-- 桌面端：侧边栏收起时的边栏拉手 -->
      <div
        v-if="!panelVisible && !isMobile"
        class="sidebar-pull-handle"
        @click.stop="panelVisible = true"
        :title="$t('views.statistic-center.title_cn_c56cb26a')"
      >
        <TheIcon icon="material-symbols:chevron-right" :size="18" />
      </div>

      <!-- 侧边栏收起时浮动展开按钮（右下角） -->
      <div
        v-if="!panelVisible"
        class="mobile-menu-btn"
        @click.stop="panelVisible = true"
      >
        <TheIcon icon="material-symbols:menu" :size="26" />
      </div>

      <!-- 操作栏（固定顶部） -->
      <div
        v-if="selectedReport"
        class="flex items-center justify-between px-4 py-3 border-b"
        style="flex-shrink: 0"
      >
        <div class="flex items-center gap-2">
          <h2 class="text-lg font-bold m-0">{{ selectedReport.name }}</h2>
        </div>
        <NSpace>
          <NSwitch v-model:value="viewMode" checked-value="edit" unchecked-value="preview">
            <template #checked>{{ t('views.statistic-center.label_cn_95b351c8') }}</template>
            <template #unchecked>{{ t('views.statistic-center.label_cn_645dbc55') }}</template>
          </NSwitch>
          <NButton v-if="viewMode === 'edit'" size="small" @click="saveEdit">
            <TheIcon icon="material-symbols:save" :size="16" class="mr-4" />{{ t('views.statistic-center.label_cn_be5fbbe3') }}
          </NButton>
          <NButton size="small" @click="openClone">
            <TheIcon icon="material-symbols:content-copy" :size="16" class="mr-4" />{{ t('views.statistic-center.label_cn_23b45f1a') }}
          </NButton>
          <NButton size="small" @click="exportReport('html')">
            <TheIcon icon="material-symbols:code" :size="16" class="mr-4" />HTML
          </NButton>
          <NButton size="small" @click="printReport">
            <TheIcon icon="material-symbols:print" :size="16" class="mr-4" />{{ t('views.statistic-center.label_cn_7e0362d9') }}
          </NButton>
          <NButton size="small" @click="exportReport('docx')">
            <TheIcon icon="material-symbols:article" :size="16" class="mr-4" />Word
          </NButton>
          <NPopconfirm @positive-click="deleteReport">
            <template #trigger>
              <NButton size="small" type="error">
                <TheIcon icon="material-symbols:delete-outline" :size="16" class="mr-4" />{{ t('views.statistic-center.label_cn_2f4aaddd') }}
              </NButton>
            </template>
          </NPopconfirm>
        </NSpace>
      </div>

      <!-- 内容区 -->
      <div style="flex: 1; min-height: 0; position: relative; contain: layout style">
        <div v-if="!selectedReport" class="flex items-center justify-center h-full text-gray-400 text-base">
          {{ t('views.statistic-center.label_cn_b5f0a318') }}
        </div>
        <template v-else>
          <div v-show="viewMode === 'edit'" ref="cmContainer" style="position: absolute; inset: 0"></div>
          <iframe
            v-show="viewMode !== 'edit'"
            ref="previewFrame"
            style="position: absolute; inset: 0; width: 100%; height: 100%; border: none"
            ::title="t('views.statistic-center.label_cn_f24f895f')"
          />
        </template>
        <div v-if="loading" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.6); z-index: 10">
          <NSpin :show="true" />
        </div>
      </div>
    </div>
  </div>

  <!-- 生成弹窗 -->
  <NModal v-model:show="showGenerateModal" :title="t('views.statistic-center.title_cn_ba5f594e')" preset="card" :style="bp.isSmaller('md') ? 'width: 92vw' : 'width: 680px'">
    <NForm :model="generateForm" label-placement="top" class="generate-form">
      <!-- 文书名称 -->
      <NFormItem :label="t('views.statistic-center.label_cn_387b3c0d')" required>
        <NInput v-model:value="generateForm.name" :placeholder="t('views.statistic-center.placeholder_cn_135b3f9d')" size="large" />
      </NFormItem>

      <!-- 数据工作区 -->
      <NFormItem :label="t('views.statistic-center.label_cn_4f361b2d')" required>
        <NSelect
          v-model:value="generateForm.workspace_id"
          :options="workspaceOptions"
          :placeholder="t('views.statistic-center.placeholder_cn_c45fe060')"
          @update:value="onGenerateWsChange"
          size="large"
        />
      </NFormItem>

      <!-- 数据来源分区 -->
      <NFormItem v-if="generateForm.workspace_id" :label="t('views.pixel.title_cn_a094e5b7')">
        <div v-if="dataSourcesLoading" class="flex justify-center py-6">
          <NSpin size="small" /><span class="ml-2 text-sm text-gray-400">{{ t('views.statistic-center.label_cn_6f6b9b2f') }}</span>
        </div>
        <div v-else-if="totalDataSourceCount === 0" class="text-sm text-gray-400 text-center py-6">
          {{ t('views.statistic-center.label_cn_4e86f1c9') }}
        </div>
        <div v-else class="ds-sections">
          <!-- 动态渲染 5 个分区 -->
          <template v-for="sec in dataSourceSections" :key="sec.key">
            <div
              v-if="sec.list.length"
              class="ds-section"
              :class="{ 'ds-section--expanded': expandedSections[sec.key] }"
            >
              <!-- 头部 -->
              <div class="ds-section__header" @click="toggleSection(sec.key)">
                <div class="ds-section__icon" :class="`ds-section__icon--${sec.color}`">
                  <TheIcon :icon="sec.icon" :size="22" />
                </div>
                <div class="ds-section__info">
                  <span class="ds-section__label">{{ sec.label }}</span>
                  <span class="ds-section__count">{{ sectionStats[sec.key]?.selected ?? 0 }} / {{ sec.list.length }} 项</span>
                </div>
                <div class="ds-section__actions">
                  <!-- 全选/取消全选 -->
                  <NButton
                    size="tiny"
                    quaternary
                    @click.stop="toggleSectionAll(sec.key)"
                    :type="sectionStats[sec.key]?.all ? 'primary' : 'default'"
                  >
                    {{ sectionStats[sec.key]?.all ? t('views.statistic-center.label_cn_625fb26b') : t('views.statistic-center.label_cn_66eeacd9') }}
                  </NButton>
                  <!-- 折叠箭头 -->
                  <div class="ds-section__arrow" :class="{ 'ds-section__arrow--open': expandedSections[sec.key] }">
                    <TheIcon icon="material-symbols:chevron-right" :size="18" />
                  </div>
                </div>
              </div>

              <!-- 展开：子项列表 -->
              <div v-if="expandedSections[sec.key]" class="ds-section__body">
                <div
                  v-for="item in sec.list"
                  :key="item.id"
                  class="ds-item"
                  :class="{ 'ds-item--checked': isItemChecked(sec.key, item.id) }"
                  @click="toggleItem(sec.key, item.id)"
                >
                  <div class="ds-item__check">
                    <TheIcon v-if="isItemChecked(sec.key, item.id)" icon="material-symbols:check-small" :size="16" />
                  </div>
                  <span class="ds-item__name">{{ item.name }}</span>
                  <span class="ds-item__size" v-if="item.file_size">{{ formatFileSize(item.file_size) }}</span>
                </div>
              </div>
            </div>
          </template>
        </div>
      </NFormItem>

      <!-- 统计预览区 -->
      <NFormItem v-if="previewData" :label="t('views.statistic-center.label_cn_1b7cba28')">
        <div class="preview-stats">
          <div class="preview-stats__grid">
            <div class="preview-stat">
              <span class="preview-stat__value">{{ previewData.source_counts?.total ?? 0 }}</span>
              <span class="preview-stat__label">{{ t('views.statistic-center.label_cn_c11322c9') }}</span>
            </div>
            <div class="preview-stat">
              <span class="preview-stat__value">{{ previewData.total_chars?.toLocaleString() ?? 0 }}</span>
              <span class="preview-stat__label">{{ t('views.statistic-center.label_cn_e0d421f2') }}</span>
            </div>
            <div class="preview-stat">
              <span class="preview-stat__value">{{ previewData.estimated_tokens?.toLocaleString() ?? 0 }}</span>
              <span class="preview-stat__label">{{ t('views.statistic-center.label_cn_df9703ad') }}</span>
            </div>
          </div>
          <div class="preview-stats__detail">
            <span v-if="previewData.source_counts?.sheets">{{ t('views.statistic-center.label_cn_c2f57bd6', { count: previewData.source_counts.sheets }) }} </span>
            <span v-if="previewData.source_counts?.analyses">{{ t('views.statistic-center.label_cn_809deb12', { count: previewData.source_counts.analyses }) }} </span>
            <span v-if="previewData.source_counts?.documents">{{ t('views.statistic-center.label_cn_b725b10f', { count: previewData.source_counts.documents }) }} </span>
            <span v-if="previewData.source_counts?.static_files">{{ t('views.statistic-center.label_cn_5d52e8a7', { count: previewData.source_counts.static_files }) }} </span>
          </div>
        </div>
      </NFormItem>

      <!-- AI 代理 -->
      <NFormItem :label="t('views.statistic-center.label_ai_cn_9697e5cf')" required>
        <NSelect
          v-model:value="generateForm.ai_proxy_id"
          :options="proxyOptions"
          :placeholder="t('views.network.roadNetworkWorkbench.tabs.fields.selectAIProxy')"
          size="large"
        />
      </NFormItem>

      <!-- 辅助 Skill -->
      <NFormItem :label="t('views.statistic-center.label_cn_998c41f2')">
        <NSelect
          v-model:value="generateForm.skill_id"
          :options="skillOptions"
          :placeholder="t('views.statistic-center.placeholder_cn_5ad8f962')"
          clearable
          size="large"
        />
      </NFormItem>

      <!-- 系统提示词 -->
      <NFormItem label="系统提示词">
        <NInput
          v-model:value="generateForm.system_prompt"
          type="textarea"
          :rows="8"
          placeholder="系统提示词，用于设定AI角色和行为规范"
        />
        <div class="flex justify-end gap-2 mt-2">
          <NButton size="tiny" quaternary @click="resetSystemPrompt">
            <TheIcon icon="material-symbols:restart-alt" :size="14" class="mr-1" />恢复默认
          </NButton>
          <NButton size="tiny" quaternary type="primary" @click="saveSystemPrompt">
            <TheIcon icon="material-symbols:save" :size="14" class="mr-1" />保存为默认
          </NButton>
        </div>
      </NFormItem>

      <!-- 提示词 -->
      <NFormItem :label="t('views.statistic-center.label_cn_cb9b4b45')">
        <NInput
          v-model:value="generateForm.prompt"
          type="textarea"
          :placeholder="t('views.statistic-center.placeholder_cn_757179d0')"
          :autosize="{ minRows: 2, maxRows: 5 }"
        />
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="space-between" style="width:100%">
        <NButton
          v-if="generateForm.workspace_id && totalDataSourceCount > 0"
          size="large"
          @click="handlePreview"
          :loading="previewLoading"
          :disabled="dataSourcesLoading"
        >
          <TheIcon icon="material-symbols:visibility" :size="18" class="mr-1" />{{ t('views.statistic-center.label_cn_2dc47e6a') }}
        </NButton>
        <div v-else />
        <NSpace>
          <NButton size="large" @click="showGenerateModal = false">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton>
          <NButton type="primary" size="large" @click="handleGenerate" :disabled="dataSourcesLoading">
            <TheIcon icon="material-symbols:smart-toy" :size="18" class="mr-1" />{{ t('views.statistic-center.label_cn_dac38a8b') }}
          </NButton>
        </NSpace>
      </NSpace>
    </template>
  </NModal>

  <!-- 克隆弹窗 -->
  <NModal v-model:show="showCloneModal" :title="t('views.statistic-center.title_cn_a3ce620d')" preset="card" style="width: 480px">
    <NForm :model="cloneForm" label-placement="top">
      <!-- 克隆模式选择 -->
      <NFormItem label="克隆模式">
        <NButtonGroup>
          <NButton :type="cloneMode === 'normal' ? 'primary' : 'default'" @click="cloneMode = 'normal'" size="small">普通克隆</NButton>
          <NButton :type="cloneMode === 'ai' ? 'primary' : 'default'" @click="cloneMode = 'ai'" size="small">
            <TheIcon icon="material-symbols:smart-toy" :size="14" class="mr-1" />AI 语言克隆
          </NButton>
        </NButtonGroup>
      </NFormItem>

      <!-- 文书名称 -->
      <NFormItem :label="t('views.statistic-center.label_cn_e4decf94')" required>
        <NInput v-model:value="cloneForm.name" :placeholder="t('views.statistic-center.placeholder_cn_dace5c08')" />
      </NFormItem>

      <!-- AI 语言克隆选项 -->
      <template v-if="cloneMode === 'ai'">
        <NFormItem label="目标语言" required>
          <NSelect
            v-model:value="cloneForm.target_language"
            :options="languageOptions"
            placeholder="选择目标语言"
            filterable
          />
        </NFormItem>
        <NFormItem label="AI 代理" required>
          <NSelect
            v-model:value="cloneForm.ai_proxy_id"
            :options="cloneProxyOptions"
            placeholder="选择AI代理"
          />
        </NFormItem>
      </template>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showCloneModal = false">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton>
        <NButton type="primary" @click="handleClone" :loading="cloneTranslateLoading">
          <template v-if="cloneMode === 'ai'">
            <TheIcon icon="material-symbols:translate" :size="16" class="mr-1" />
            {{ cloneTranslateLoading ? '翻译克隆中...' : '开始翻译克隆' }}
          </template>
          <template v-else>
            {{ t('views.statistic-center.message_cn_82f85866') }}
          </template>
        </NButton>
      </NSpace>
    </template>
  </NModal>

</template>

<style scoped>
/* UnoCSS text-* 类 px 覆盖：全局 html{font-size:4px} 导致 1rem=4px，text-* 全部缩到 1/4 */
.text-xs  { font-size: 12px !important; line-height: 16px !important; }
.text-sm  { font-size: 14px !important; line-height: 20px !important; }
.text-base { font-size: 16px !important; line-height: 24px !important; }
.text-lg  { font-size: 18px !important; line-height: 28px !important; }
.text-xl  { font-size: 20px !important; line-height: 28px !important; }

:global(.CodeMirror) {
  height: 100% !important;
}

/* ── 生成弹窗：分区面板 ── */
.ds-sections {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ds-section {
  border: 1.5px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
  transition: border-color 0.2s;
  background: #fff;
}

.ds-section:hover {
  border-color: #cbd5e1;
}

.ds-section--expanded {
  border-color: #93c5fd;
}

.ds-section__header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.ds-section__header:hover {
  background: #f8fafc;
}

.ds-section__icon {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ds-section__icon--blue   { background: #dbeafe; color: #2563eb; }
.ds-section__icon--green  { background: #dcfce7; color: #16a34a; }
.ds-section__icon--purple { background: #f3e8ff; color: #9333ea; }
.ds-section__icon--orange { background: #fff7ed; color: #ea580c; }
.ds-section__icon--teal   { background: #ccfbf1; color: #0d9488; }

.ds-section__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.ds-section__label {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.ds-section__count {
  font-size: 12px;
  color: #94a3b8;
}

.ds-section__actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.ds-section__arrow {
  transition: transform 0.2s ease;
  color: #94a3b8;
}

.ds-section__arrow--open {
  transform: rotate(90deg);
}

.ds-section__body {
  border-top: 1px solid #f1f5f9;
  max-height: 220px;
  overflow-y: auto;
  background: #fafbfc;
}

.ds-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px 7px 18px;
  cursor: pointer;
  transition: background 0.12s;
  font-size: 13px;
}

.ds-item:hover {
  background: #f1f5f9;
}

.ds-item--checked {
  background: #eff6ff;
}

.ds-item__check {
  width: 18px;
  height: 18px;
  border: 1.5px solid #cbd5e1;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s;
  background: #fff;
  color: #fff;
}

.ds-item--checked .ds-item__check {
  border-color: #3b82f6;
  background: #3b82f6;
}

.ds-item__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #334155;
}

.ds-item__size {
  font-size: 11px;
  color: #94a3b8;
  flex-shrink: 0;
}

/* ── 统计预览区 ── */
.preview-stats {
  border: 1.5px solid #dbeafe;
  border-radius: 10px;
  background: #f0f9ff;
  padding: 14px 16px;
}

.preview-stats__grid {
  display: flex;
  gap: 20px;
  margin-bottom: 8px;
}

.preview-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.preview-stat__value {
  font-size: 22px;
  font-weight: 700;
  color: #1e40af;
  line-height: 1.2;
}

.preview-stat__label {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.preview-stats__detail {
  font-size: 12px;
  color: #64748b;
  text-align: center;
  padding-top: 6px;
  border-top: 1px solid #bfdbfe;
}

/* 移动端适配 */
@media (max-width: 480px) {
  .ds-section__header {
    padding: 8px 10px;
    gap: 8px;
  }
  .ds-section__icon {
    width: 32px;
    height: 32px;
  }
  .ds-section__label {
    font-size: 13px;
  }
  .ds-item {
    padding: 6px 10px 6px 14px;
    font-size: 12px;
  }
  .preview-stats__grid {
    gap: 12px;
  }
  .preview-stat__value {
    font-size: 18px;
  }
}

/* 弹窗表单间距收紧 */
.generate-form :deep(.n-form-item) {
  margin-bottom: 16px;
}

/* 侧边栏收起时的边栏拉手（左侧边缘竖条） */
.sidebar-pull-handle {
  position: absolute;
  top: 50%;
  left: 0;
  transform: translateY(-50%);
  width: 24px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
  background: var(--n-color-embedded);
  border: 1px solid var(--n-border-color);
  border-left: none;
  border-radius: 0 8px 8px 0;
  color: var(--n-text-color-3);
  transition: width 0.15s, color 0.15s;
}
.sidebar-pull-handle:hover {
  width: 28px;
  color: var(--primary-color);
}

/* ── 移动端汉堡菜单浮动按钮 ── */
.mobile-menu-btn {
  position: fixed;
  bottom: 24px;
  right: 20px;
  z-index: 100;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--primary-color);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(0,0,0,0.25);
  transition: transform 0.2s, box-shadow 0.2s;
}
.mobile-menu-btn:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 20px rgba(0,0,0,0.3);
}
</style>


