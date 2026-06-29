<script setup>
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton, NCard, NDataTable, NInput, NModal, NPopconfirm,
  NSelect, NSpace, NSpin, NTag, NForm, NFormItem,
  useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { useTaskProgressStore } from '@/store/modules/taskProgress'

defineOptions({ name: 'SurveyWorkbench' })

const message = useMessage()
const s = (key) => key  // simple i18n placeholder
const taskProgress = useTaskProgressStore()

// ── 问卷列表 ──
const surveyList = ref([])
const listLoading = ref(false)
const listSearch = ref('')
const selectedSurvey = ref(null)

const fullShortUrl = computed(() => {
  if (!selectedSurvey.value?.short_url) return ''
  return window.location.origin + selectedSurvey.value.short_url
})

const filteredList = computed(() => {
  if (!listSearch.value) return surveyList.value
  const kw = listSearch.value.toLowerCase()
  return surveyList.value.filter(item =>
    (item.name || '').toLowerCase().includes(kw)
  )
})

async function loadSurveys() {
  listLoading.value = true
  try {
    const res = await api.getSurveyList({ page_size: 100 })
    surveyList.value = res.data || []
  } catch (e) {
    surveyList.value = []
  } finally {
    listLoading.value = false
  }
}

function onClickSurvey(row) {
  selectedSurvey.value = row
  loadSubmissions()
}

async function onDeleteSurvey(row) {
  try {
    await api.deleteSurvey({ survey_id: row.id })
    message.success('问卷已删除')
    if (selectedSurvey.value?.id === row.id) selectedSurvey.value = null
    loadSurveys()
  } catch (e) {
    message.error('删除失败：' + (e.message || '未知错误'))
  }
}

// ── 创建问卷弹窗 ──
const showCreateModal = ref(false)
const createLoading = ref(false)
const createForm = ref({
  name: '',
  ai_proxy_id: null,
  skill_id: null,
  prompt: '',
  user_ids: [],
})
const aiProxyOptions = ref([])
const skillOptions = ref([])
const userOptions = ref([])

async function openCreateModal() {
  createForm.value = { name: '', ai_proxy_id: null, skill_id: null, prompt: '', user_ids: [] }
  showCreateModal.value = true
  // 加载选项
  try {
    const [proxyRes, skillRes, userRes] = await Promise.all([
      api.getAIProxyList({ page_size: 100 }),
      api.getSkillList({ page_size: 100 }),
      api.getUserList({ page_size: 500 }),
    ])
    aiProxyOptions.value = (proxyRes.data || []).map(p => ({ label: p.name, value: p.id }))
    skillOptions.value = (skillRes.data || []).map(s => ({ label: s.title, value: s.id }))
    userOptions.value = (userRes.data || []).map(u => ({ label: u.username + (u.alias ? ` (${u.alias})` : ''), value: u.id }))
  } catch (e) {
    message.warning('加载选项失败')
  }
}

async function doCreateSurvey() {
  if (!createForm.value.name) { message.warning('请输入问卷名称'); return }
  if (!createForm.value.ai_proxy_id) { message.warning('请选择AI代理'); return }
  if (!createForm.value.prompt) { message.warning('请输入Prompt'); return }

  createLoading.value = true
  try {
    const res = await api.createSurvey({
      name: createForm.value.name,
      ai_proxy_id: createForm.value.ai_proxy_id,
      skill_id: createForm.value.skill_id,
      prompt: createForm.value.prompt,
      user_ids: createForm.value.user_ids,
    })
    if (res.code !== 200 || !res.data?.task_id) {
      message.error(res.msg || '创建失败')
      return
    }

    const taskId = res.data.task_id
    showCreateModal.value = false

    // 注册到全局进度面板
    const progressId = taskProgress.startTask('创建问卷: ' + createForm.value.name)

    // 轮询直到完成
    const poll = async () => {
      try {
        const pRes = await api.getSurveyCreateProgress({ task_id: taskId })
        const data = pRes.data || pRes
        if (data.status === 'done') {
          taskProgress.finishTask(progressId, data.message || '问卷创建成功')
          loadSurveys()
          const resultRes = await api.getSurveyCreateResult({ task_id: taskId })
          if (resultRes.code === 200 && resultRes.data) {
            selectedSurvey.value = resultRes.data
          }
          return
        }
        if (data.status === 'error') {
          taskProgress.failTask(progressId, { message: '问卷创建失败', detail: data.detail || data.message || '' })
          return
        }
        // 更新进度
        taskProgress.updateProgress(progressId, {
          progress: data.progress || 0,
          message: data.message || '',
          phase: data.phase || '',
        })
        setTimeout(poll, 800)
      } catch (e) {
        taskProgress.failTask(progressId, { message: '轮询进度失败', detail: e.message || '' })
      }
    }
    setTimeout(poll, 500)

  } catch (e) {
    message.error('创建失败：' + (e.message || '未知错误'))
  } finally {
    createLoading.value = false
  }
}

// ── 提交记录 ──
const submissions = ref([])
const submissionsLoading = ref(false)

async function loadSubmissions() {
  if (!selectedSurvey.value) return
  submissionsLoading.value = true
  try {
    const res = await api.getSurveySubmissions({
      survey_id: selectedSurvey.value.id,
      page_size: 100,
    })
    submissions.value = res.data || []
  } catch (e) {
    submissions.value = []
  } finally {
    submissionsLoading.value = false
  }
}

async function onDeleteSubmission(row) {
  try {
    await api.deleteSurveySubmission({ submission_id: row.id })
    message.success('提交记录已删除')
    loadSubmissions()
  } catch (e) {
    message.error('删除失败')
  }
}

// ── 预览弹窗 ──
const showPreviewModal = ref(false)
const previewHtml = ref('')
const previewLoading = ref(false)

async function openPreview(submission) {
  if (!selectedSurvey.value) return
  showPreviewModal.value = true
  previewLoading.value = true
  try {
    const res = await api.getSurveyHtml({ survey_id: selectedSurvey.value.id })
    if (res.data?.html) {
      // 替换占位符为短链接令牌，注入提交数据
      let html = res.data.html
      html = html.replace('__SURVEY_TOKEN__', selectedSurvey.value.short_url_token || '')
      // 注入已有数据到表单（用作展示）
      if (submission?.raw_data) {
        const rd = submission.raw_data
        Object.keys(rd).forEach(key => {
          html = html.replace(
            new RegExp(`name="${key}"`, 'g'),
            `name="${key}" value="${String(rd[key]).replace(/"/g, '&quot;')}"`
          )
        })
      }
      previewHtml.value = html
    }
  } catch (e) {
    previewHtml.value = '<p>无法加载网页内容</p>'
  } finally {
    previewLoading.value = false
  }
}

// ── 问卷详情更新 ──
const showEditModal = ref(false)
const editForm = ref({ name: '', user_ids: [] })

function openEditModal() {
  if (!selectedSurvey.value) return
  editForm.value = {
    name: selectedSurvey.value.name,
    user_ids: [],
  }
  showEditModal.value = true
}

// ── 风险信息弹窗 ──
const showRiskModal = ref(false)
const riskInfo = ref(null)
const riskLoading = ref(false)

async function doShowRisk() {
  if (!selectedSurvey.value) return
  riskLoading.value = true
  showRiskModal.value = true
  try {
    const res = await api.getSurveyRisk({ survey_id: selectedSurvey.value.id })
    riskInfo.value = res.data?.security || null
  } catch (e) {
    riskInfo.value = { passed: true, issues: [], detail: '加载失败: ' + (e.message || '未知错误') }
  } finally {
    riskLoading.value = false
  }
}

async function doUpdateSurvey() {
  try {
    await api.updateSurvey({
      id: selectedSurvey.value.id,
      name: editForm.value.name,
      user_ids: editForm.value.user_ids,
    })
    message.success('更新成功')
    showEditModal.value = false
    loadSurveys()
  } catch (e) {
    message.error('更新失败')
  }
}

const submissionColumns = [
  { title: '标题', key: 'title', width: 150, ellipsis: { tooltip: true }, render: (row) => row.title || '-' },
  { title: '提交时间', key: 'created_at', width: 170, render: (row) => row.created_at?.replace('T', ' ').substring(0, 19) || '-' },
  { title: '提交者', key: 'submitter_name', width: 100 },
  { title: '类型', key: 'save_type', width: 80, render: (row) => row.save_type === 'submit' ? '提交' : '保存' },
  { title: '总字数', key: 'word_count', width: 80 },
  { title: '提交数据', key: 'content', ellipsis: { tooltip: true }, maxWidth: 300, render: (row) => { try { const d = JSON.parse(row.content); return Object.keys(d).length + ' 个字段'; } catch(e) { return (row.content || '').substring(0, 60); } } },
  {
    title: '操作', key: 'actions', width: 180,
    render(row) {
      return h(NSpace, { justify: 'center' }, {
        default: () => [
          h(NButton, { size: 'tiny', quaternary: true, type: 'primary', onClick: () => openPreview(row) }, { default: () => '预览' }),
          h(NPopconfirm, { onPositiveClick: () => onDeleteSubmission(row) }, {
            trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' }, { default: () => '删除' }),
          }),
        ],
      })
    },
  },
]

// ── 复制 / 打开短链接 ──
function copyShortUrl() {
  if (!fullShortUrl.value) return
  navigator.clipboard.writeText(fullShortUrl.value).then(() => {
    message.success('完整链接已复制：' + fullShortUrl.value)
  }).catch(() => {
    message.warning('复制失败，请手动复制')
  })
}

function openShortUrl() {
  if (!fullShortUrl.value) return
  window.open(fullShortUrl.value, '_blank')
}

onMounted(loadSurveys)
</script>

<template>
  <CommonPage title="问卷工作台">
    <div class="main-layout">
      <!-- 左侧：问卷列表 -->
      <NCard size="small" :bordered="true" class="left-panel">
        <template #header>
          <div class="panel-header-row">
            <span class="panel-title">问卷列表</span>
            <NButton size="small" type="primary" @click="openCreateModal" style="margin-left: auto">
              <template #icon><TheIcon icon="material-symbols:add" /></template>
              创建问卷
            </NButton>
          </div>
        </template>
        <NInput v-model:value="listSearch" placeholder="搜索问卷..." clearable size="small" style="margin-bottom: 8px" />
        <NSpin :show="listLoading" style="flex: 1; min-height: 0">
          <div v-if="filteredList.length" class="survey-list">
            <div
              v-for="row in filteredList" :key="row.id"
              class="survey-row"
              :class="{ active: selectedSurvey?.id === row.id }"
              @click="onClickSurvey(row)"
            >
              <div class="row-info">
                <span class="row-name">{{ row.name }}</span>
                <div class="row-meta">
                  <NTag :type="row.is_valid ? 'success' : 'error'" size="tiny">{{ row.is_valid ? '安全' : '未审核' }}</NTag>
                  <span class="row-date">{{ row.created_at?.substring(0, 10) || '-' }}</span>
                </div>
              </div>
              <NPopconfirm @positive-click="onDeleteSurvey(row)">
                <template #trigger>
                  <NButton size="tiny" quaternary type="error" @click.stop style="flex-shrink: 0">
                    <TheIcon icon="material-symbols:delete-outline" />
                  </NButton>
                </template>
                确定删除此问卷及其所有提交记录？
              </NPopconfirm>
            </div>
          </div>
          <div v-else class="empty-state">{{ listLoading ? '加载中...' : '暂无问卷，点击"创建问卷"开始' }}</div>
        </NSpin>
      </NCard>

      <!-- 右侧：详情 + 提交记录 -->
      <NCard size="small" :bordered="true" class="right-panel">
        <template #header>
          <div class="panel-header-row">
            <span class="panel-title">
              {{ selectedSurvey ? selectedSurvey.name : '问卷详情' }}
            </span>
            <div v-if="selectedSurvey" class="panel-actions">
              <NButton size="small" @click="openEditModal">编辑</NButton>
              <NButton size="small" type="primary" @click="openPreview()">预览网页</NButton>
              <NButton size="small" type="warning" @click="doShowRisk">查看风险</NButton>
              <NTag v-if="selectedSurvey.short_url" type="info" size="small" style="cursor: pointer" @click="copyShortUrl" @dblclick="openShortUrl">
                {{ fullShortUrl }}
              </NTag>
            </div>
          </div>
        </template>

        <div v-if="!selectedSurvey" class="empty-state">请从左侧选择一个问卷</div>

        <div v-else class="detail-content">
          <!-- 问卷信息 -->
          <div class="info-grid">
            <div class="info-item"><span class="info-label">状态</span><NTag :type="selectedSurvey.is_valid ? 'success' : 'error'" size="small">{{ selectedSurvey.is_valid ? '已审核通过' : '安全审核未通过' }}</NTag></div>
            <div class="info-item"><span class="info-label">创建时间</span><span>{{ selectedSurvey.created_at?.replace('T', ' ').substring(0, 19) || '-' }}</span></div>
            <div class="info-item"><span class="info-label">完整链接</span><span v-if="fullShortUrl" style="font-family: monospace; font-size: 12px; color: #2080f0; cursor: pointer" @click="copyShortUrl" :title="'点击复制，双击打开'">{{ fullShortUrl }}</span><span v-else style="font-family: monospace; font-size: 12px">无（审核未通过）</span></div>
            <div class="info-item"><span class="info-label">文件名</span><span style="font-family: monospace; font-size: 12px">{{ selectedSurvey.file_name || '-' }}</span></div>
          </div>

          <!-- 提交记录 -->
          <div style="margin-top: 16px">
            <div class="section-title" style="display: flex; align-items: center; gap: 8px">
              <span>提交记录 ({{ submissions.length }})</span>
              <NButton size="tiny" quaternary @click="loadSubmissions" :loading="submissionsLoading">
                <template #icon><TheIcon icon="material-symbols:refresh" /></template>
              </NButton>
            </div>
            <NSpin :show="submissionsLoading">
              <NDataTable
                v-if="submissions.length"
                :columns="submissionColumns"
                :data="submissions"
                :row-key="(row) => row.id"
                size="small"
                :bordered="true"
                stripe
                :max-height="'calc(100vh - 480px)'"
              />
              <div v-else class="empty-state" style="padding: 20px 0">暂无提交记录</div>
            </NSpin>
          </div>
        </div>
      </NCard>
    </div>

    <!-- 创建问卷弹窗 -->
    <NModal v-model:show="showCreateModal" title="AI 创建问卷" preset="card" style="width: 640px">
      <NForm label-placement="left" label-width="100">
        <NFormItem label="问卷名称" required>
          <NInput v-model:value="createForm.name" placeholder="例如：客户满意度调查" />
        </NFormItem>
        <NFormItem label="AI代理" required>
          <NSelect v-model:value="createForm.ai_proxy_id" :options="aiProxyOptions" placeholder="选择AI代理" filterable />
        </NFormItem>
        <NFormItem label="技能">
          <NSelect v-model:value="createForm.skill_id" :options="skillOptions" placeholder="选择技能（可选）" filterable clearable />
        </NFormItem>
        <NFormItem label="Prompt" required>
          <NInput
            v-model:value="createForm.prompt"
            type="textarea"
            placeholder="描述你想要的问卷字段，例如：请创建一个客户满意度调查网页，包含以下字段：姓名(必填)、联系电话、年龄(18-80)、满意度评分(1-5星)、改进建议(多行文本)、是否愿意推荐(是/否开关)"
            :autosize="{ minRows: 4, maxRows: 10 }"
          />
        </NFormItem>
        <NFormItem label="授权用户">
          <NSelect v-model:value="createForm.user_ids" :options="userOptions" multiple placeholder="选择可访问此问卷的用户（默认当前用户）" filterable />
        </NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showCreateModal = false">取消</NButton>
          <NButton type="primary" :loading="createLoading" @click="doCreateSurvey">确认创建</NButton>
        </NSpace>
      </template>
    </NModal>

    <!-- 风险信息弹窗 -->
    <NModal v-model:show="showRiskModal" title="风险评估" preset="card" style="width: 640px; max-height: 80vh">
      <NSpin :show="riskLoading">
        <div v-if="riskInfo" style="max-height: 55vh; overflow-y: auto">
          <div v-if="!riskInfo.issues || riskInfo.issues.length === 0" style="text-align: center; padding: 40px 0; color: #18a058">
            ✓ 未检测到风险
          </div>
          <div v-else>
            <div style="margin-bottom: 12px; font-size: 13px; color: #666">
              检测到 {{ riskInfo.issues.length }} 条风险信息：
            </div>
            <div
              v-for="(issue, idx) in riskInfo.issues" :key="idx"
              style="padding: 10px 12px; margin-bottom: 8px; background: #fff7e6; border: 1px solid #ffd591; border-radius: 6px; font-size: 13px"
            >
              <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 4px">
                <NTag size="tiny" type="warning">行 {{ issue.line }}</NTag>
                <span style="font-weight: 500; color: #d46b08">{{ issue.message }}</span>
              </div>
              <div v-if="issue.snippet" style="font-family: monospace; font-size: 11px; color: #999; word-break: break-all; background: #fff; padding: 4px 8px; border-radius: 3px; margin-top: 4px">
                {{ issue.snippet }}
              </div>
            </div>
          </div>
        </div>
        <div v-else-if="!riskLoading" style="text-align: center; padding: 40px 0; color: #999">
          无风险数据
        </div>
      </NSpin>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showRiskModal = false">关闭</NButton>
        </NSpace>
      </template>
    </NModal>

    <!-- 编辑问卷弹窗 -->
    <NModal v-model:show="showEditModal" title="编辑问卷" preset="card" style="width: 480px">
      <NForm label-placement="left" label-width="80">
        <NFormItem label="问卷名称">
          <NInput v-model:value="editForm.name" />
        </NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showEditModal = false">取消</NButton>
          <NButton type="primary" @click="doUpdateSurvey">保存</NButton>
        </NSpace>
      </template>
    </NModal>

    <!-- 预览弹窗 -->
    <NModal v-model:show="showPreviewModal" title="问卷预览" preset="card" style="width: 90vw; max-width: 800px">
      <NSpin :show="previewLoading">
        <iframe
          v-if="previewHtml"
          :srcdoc="previewHtml"
          style="width: 100%; height: 70vh; border: 1px solid #e8e8e8; border-radius: 8px"
        />
        <div v-else class="empty-state">无法加载预览</div>
      </NSpin>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showPreviewModal = false">关闭</NButton>
        </NSpace>
      </template>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.main-layout { display: flex; height: calc(100vh - 180px); overflow: hidden; gap: 8px; }

.left-panel { width: 300px; flex-shrink: 0; display: flex; flex-direction: column; overflow: hidden; }
.right-panel { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; }
.left-panel :deep(.n-card__content),
.right-panel :deep(.n-card__content) { flex: 1; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; }

.panel-header-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.panel-title { font-weight: 600; flex-shrink: 0; }
.panel-actions { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; margin-left: auto; }

.survey-list { flex: 1; min-height: 0; }
.survey-row {
  display: flex; align-items: center; padding: 8px 10px; cursor: pointer;
  border-bottom: 1px solid #f0f0f0; transition: background 0.15s; gap: 6px;
}
.survey-row:hover { background: #f5f7fa; }
.survey-row.active { background: #e6f4ff; border-left: 3px solid #1890ff; padding-left: 7px; }
.row-info { flex: 1; min-width: 0; }
.row-name { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; }
.row-meta { display: flex; align-items: center; gap: 6px; margin-top: 2px; }
.row-date { font-size: 11px; color: #999; }

.empty-state { text-align: center; color: #999; padding: 40px 0; font-size: 14px; }

.detail-content { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.info-item { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.info-label { color: #999; min-width: 60px; flex-shrink: 0; }
.section-title { font-weight: 600; font-size: 14px; margin-bottom: 8px; color: #333; }

.left-panel :deep(.n-card__content)::-webkit-scrollbar,
.right-panel :deep(.n-card__content)::-webkit-scrollbar { width: 5px; }
.left-panel :deep(.n-card__content)::-webkit-scrollbar-thumb,
.right-panel :deep(.n-card__content)::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }

@media (max-width: 768px) {
  .main-layout { flex-direction: column; height: auto; min-height: 400px; }
  .left-panel { width: 100%; max-height: 35vh; flex-shrink: 1; }
  .right-panel { flex: 1; min-height: 200px; }
  .info-grid { grid-template-columns: 1fr; }
}
</style>
