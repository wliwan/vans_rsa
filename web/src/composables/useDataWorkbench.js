import { ref, computed, reactive, watch, provide, inject } from 'vue'
import { useI18n } from 'vue-i18n'
import { useBreakpoints } from '@vueuse/core'
import api from '@/api'
import { useTaskProgressStore } from '@/store/modules/taskProgress'
import { useMessage } from 'naive-ui'

const DATA_WORKBENCH_KEY = Symbol('dataWorkbench')

/**
 * 数据工作台共享状态 composable
 * 在父组件中调用 provideDataWorkbench()，子组件中调用 useDataWorkbench() 获取共享状态
 */
export function createDataWorkbenchState() {
  const { t } = useI18n()
  const message = useMessage()
  const taskStore = useTaskProgressStore()

  // 移动端适配
  const bp = reactive(useBreakpoints({ sm: 640, md: 991 }))
  const isMobileCollapsed = computed(() => bp.isSmaller('sm'))
  const sidebarVisible = ref(true)

  // 工作区状态
  const workspaces = ref([])
  const selectedWs = ref(null)
  const userOptions = ref([])
  const loading = ref(false)

  // 搜索
  const searchQuery = ref('')
  const filteredWorkspaces = computed(() => {
    if (!searchQuery.value) return workspaces.value
    const q = searchQuery.value.toLowerCase()
    return workspaces.value.filter((w) => w.name.toLowerCase().includes(q))
  })

  // 工作区 CRUD 弹窗
  const showWsModal = ref(false)
  const wsModalForm = ref({ name: '', description: '', user_ids: [] })
  const wsEditing = ref(false)

  // AI 代理和 Skill 选项（跨 TAB 共享）
  const proxyOptions = ref([])
  const skillOptions = ref([])

  // 颜色数组
  const wsAccentColors = ['#6366f1', '#8b5cf6', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899']
  function wsAccent(idx) { return wsAccentColors[idx % wsAccentColors.length] }

  function formatFileSize(bytes) {
    if (bytes == null || bytes === 0) return ''
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  function downloadBlob(data, filename) {
    const blob = new Blob([data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = filename; a.click()
    URL.revokeObjectURL(url)
  }

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

  // 工作区 CRUD
  async function loadWorkspaces() {
    try {
      const res = await api.getWorkspaceList({ page: 1, page_size: 500 })
      workspaces.value = res.data || []
    } catch (e) { message.error('加载工作区列表失败') }
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
    if (!selectedWs.value) { message.warning('请先选择一个工作区'); return }
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
    if (!wsModalForm.value.name) { message.warning('名称不能为空'); return }
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
      await loadWorkspaces()
    } catch (e) { message.error('删除失败') }
  }

  // 加载 AI 代理和 Skill 选项（供 TAB 共享）
  async function loadProxyOptions() {
    if (proxyOptions.value.length) return
    try {
      const res = await api.getAIProxyList({ page: 1, page_size: 500 })
      proxyOptions.value = (res.data || []).map(p => ({ label: p.name, value: p.id }))
    } catch (e) { /* ignore */ }
  }

  async function loadSkillOptions() {
    if (skillOptions.value.length) return
    try {
      const res = await api.getSkillList({ page: 1, page_size: 500 })
      skillOptions.value = (res.data || []).map(s => ({ label: s.title, value: s.id }))
    } catch (e) { /* ignore */ }
  }

  const state = {
    isMobileCollapsed, sidebarVisible,
    workspaces, selectedWs, userOptions, loading,
    searchQuery, filteredWorkspaces,
    showWsModal, wsModalForm, wsEditing,
    proxyOptions, skillOptions,
    formatFileSize, wsAccent, downloadBlob, runWithProgress,
    loadWorkspaces, loadUserOptions,
    openCreateWs, openEditWs, handleWsSubmit, deleteWorkspace,
    loadProxyOptions, loadSkillOptions,
  }

  provide(DATA_WORKBENCH_KEY, state)

  return state
}

export function useDataWorkbench() {
  const state = inject(DATA_WORKBENCH_KEY)
  if (!state) throw new Error('useDataWorkbench() must be used within a component that calls createDataWorkbenchState()')
  return state
}
