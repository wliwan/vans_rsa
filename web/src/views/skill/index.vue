<script setup>
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import { computed, onMounted, onBeforeUnmount, ref, nextTick, reactive, watch } from 'vue'
import { useBreakpoints } from '@vueuse/core'
import {
  NButton,
  NInput,
  NList,
  NListItem,
  NModal,
  NSpace,
  NSelect,
  NPopconfirm,
  NForm,
  NFormItem,
  NTabs,
  NTabPane,
  useMessage,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

const { t } = useI18n()

defineOptions({ name: i18n.global.t('views.skill.title_cn_735ac607') })

const message = useMessage()

// 移动端适配：默认展开左侧面板，可手动折叠
const bp = reactive(useBreakpoints({ sm: 666, md: 991 }))
const isMobile = computed(() => bp.isSmaller('sm') || bp.between('sm', 'md'))
const panelVisible = ref(true)
// 窗口变小时自动折叠
watch(isMobile, (val) => { if (val) panelVisible.value = false })

// ---- 状态 ----
const skills = ref([])
const selectedSkill = ref(null)
const loading = ref(false)
const searchQuery = ref('')

const filteredSkills = computed(() => {
  if (!searchQuery.value) return skills.value
  const q = searchQuery.value.toLowerCase()
  return skills.value.filter((s) => s.title.toLowerCase().includes(q))
})

const accentColors = ['#6366f1', '#8b5cf6', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899']
function cardAccent(idx) {
  return accentColors[idx % accentColors.length]
}

// vditor 实例
let vditorInstance = null
const editorContainer = ref(null)

// 新建/编辑弹窗
const showModal = ref(false)
const modalTitle = ref('')
const modalForm = ref({ title: '', user_ids: [] })
const userOptions = ref([])
const isEditing = ref(false)

// 当前激活的创建模式 tab
const activeTab = ref('manual')
// AI 创建表单
const aiForm = ref({
  proxy_name: null,
  source_skill_id: null,
  prompt: '',
  user_ids: [],
})
const proxyOptions = ref([])
const skillOptions = ref([])
const aiCreating = ref(false)

// ---- 加载 Skill 列表 ----
async function loadSkills() {
  loading.value = true
  try {
    const res = await api.getSkillList({ page: 1, page_size: 9999 })
    skills.value = res.data || []
  } catch (e) {
    message.error(t('views.skill.message_cn_4a844e29'))
  } finally {
    loading.value = false
  }
}

// ---- 初始化/重建 vditor ----
function initVditor(markdown) {
  destroyVditor()
  nextTick(() => {
    if (!editorContainer.value) return
    const Vditor = window.Vditor
    vditorInstance = new Vditor(editorContainer.value, {
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

function destroyVditor() {
  if (vditorInstance) {
    vditorInstance.destroy()
    vditorInstance = null
  }
}

// ---- 选中 Skill ----
async function selectSkill(skill) {
  selectedSkill.value = skill
  try {
    const res = await api.getSkillById({ skill_id: skill.id })
    initVditor(res.data.content)
  } catch (e) {
    message.error(t('views.skill.message_cn_f21a879a'))
  }
}

// ---- 新建 Skill ----
function openCreate() {
  isEditing.value = false
  modalTitle.value = t('views.skill.title_cn_8c339e83')
  modalForm.value = { title: '', user_ids: [] }
  // 重置 AI 创建表单
  activeTab.value = 'manual'
  aiForm.value = { proxy_name: null, source_skill_id: null, prompt: '', user_ids: [] }
  aiCreating.value = false
  showModal.value = true
  loadUserOptions()
  loadProxyOptions()
}

// ---- 编辑 Skill ----
function openEdit() {
  if (!selectedSkill.value) {
    message.warning(t('views.skill.message_cn_5c2179ff'))
    return
  }
  isEditing.value = true
  modalTitle.value = t('views.skill.title_cn_50b11c40')
  const skill = selectedSkill.value
  const userIds = (skill.users || []).map((u) => u.id)
  modalForm.value = {
    title: skill.title,
    user_ids: userIds,
  }
  showModal.value = true
  loadUserOptions()
}

// ---- 加载用户选项 ----
async function loadUserOptions() {
  try {
    const res = await api.getSkillUsers()
    userOptions.value = (res.data || []).map((u) => ({
      label: u.alias ? `${u.username} (${u.alias})` : u.username,
      value: u.id,
    }))
  } catch (e) {
    // ignore
  }
}

// ---- 加载 AI 代理选项 ----
async function loadProxyOptions() {
  try {
    const res = await api.getAIProxyList({ page: 1, page_size: 9999 })
    proxyOptions.value = (res.data || []).map((p) => ({
      label: `${p.name} (${p.model || 'unknown'})`,
      value: p.name,
    }))
  } catch (e) {
    // ignore
  }
}

// ---- 加载技能选项（用于 AI 再创作） ----
async function loadSkillOptions() {
  if (skillOptions.value.length > 0) return
  try {
    const res = await api.getSkillList({ page: 1, page_size: 9999 })
    skillOptions.value = (res.data || []).map((s) => ({
      label: s.title,
      value: s.id,
    }))
  } catch (e) {
    // ignore
  }
}

// ---- 获取当前编辑器内容 ----
function getEditorContent() {
  return vditorInstance ? vditorInstance.getValue() : ''
}

// ---- 提交创建/更新（手动模式） ----
async function handleModalSubmit() {
  if (!modalForm.value.title) {
    message.warning(t('views.skill.placeholder_cn_96641a78'))
    return
  }
  try {
    const editorContent = getEditorContent()
    if (isEditing.value) {
      await api.updateSkill({
        id: selectedSkill.value.id,
        title: modalForm.value.title,
        content: editorContent,
        user_ids: modalForm.value.user_ids,
      })
      message.success(t('views.network.region.messages.updateSuccess'))
      selectedSkill.value.title = modalForm.value.title
      // 重新加载内容
      await selectSkill(selectedSkill.value)
    } else {
      await api.createSkill({
        title: modalForm.value.title,
        content: editorContent,
        user_ids: modalForm.value.user_ids,
      })
      message.success(t('views.skill.message_cn_04a691b3'))
    }
    showModal.value = false
    await loadSkills()
  } catch (e) {
    message.error(t('views.skill.message_cn_5fa802be'))
  }
}

// ---- AI 创建提交 ----
async function handleAICreate() {
  if (!aiForm.value.proxy_name) {
    message.warning(t('views.skill.placeholder_cn_ee488ec6'))
    return
  }
  if (!aiForm.value.prompt.trim()) {
    message.warning(t('views.skill.placeholder_cn_d47ed976'))
    return
  }
  aiCreating.value = true
  try {
    const res = await api.aiCreateSkill({
      proxy_name: aiForm.value.proxy_name,
      source_skill_id: aiForm.value.source_skill_id || undefined,
      prompt: aiForm.value.prompt,
      user_ids: aiForm.value.user_ids,
    })
    message.success(t('views.skill.message_cn_0c12e89f'))
    showModal.value = false
    await loadSkills()
    // 自动选中新创建的技能
    if (res.data?.id) {
      const newSkill = skills.value.find((s) => s.id === res.data.id)
      if (newSkill) {
        await selectSkill(newSkill)
      }
    }
  } catch (e) {
    message.error(e?.message || t('views.skill.message_cn_6c952981'))
  } finally {
    aiCreating.value = false
  }
}

// ---- 保存内容 ----
async function saveContent() {
  if (!selectedSkill.value) return
  try {
    const editorContent = getEditorContent()
    await api.updateSkill({
      id: selectedSkill.value.id,
      title: selectedSkill.value.title,
      content: editorContent,
      user_ids: (selectedSkill.value.users || []).map((u) => u.id),
    })
    message.success(t('views.skill.message_cn_3b108349'))
  } catch (e) {
    message.error(t('views.network.roadNetworkWorkbench.messages.saveFail'))
  }
}

// ---- 删除 Skill ----
async function deleteSkill() {
  if (!selectedSkill.value) {
    message.warning(t('views.skill.message_cn_5c2179ff'))
    return
  }
  try {
    await api.deleteSkill({ skill_id: selectedSkill.value.id })
    message.success(t('views.network.roadNetwork.messages.deleteSuccess'))
    selectedSkill.value = null
    destroyVditor()
    await loadSkills()
  } catch (e) {
    message.error(t('views.network.roadNetworkWorkbench.messages.deleteFail'))
  }
}

// ---- 导出 Skill ----
async function exportSkill() {
  if (!selectedSkill.value) {
    message.warning(t('views.skill.message_cn_5c2179ff'))
    return
  }
  try {
    const res = await api.exportSkill({ skill_id: selectedSkill.value.id })
    const blob = new Blob([res.data], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedSkill.value.title}.md`
    a.click()
    URL.revokeObjectURL(url)
    message.success(t('views.network.roadNetworkWorkbench.messages.exportSuccess'))
  } catch (e) {
    message.error(t('views.network.roadNetworkWorkbench.messages.exportFail'))
  }
}

// ---- 生命周期 ----
onMounted(() => {
  loadSkills()
})

onBeforeUnmount(() => {
  destroyVditor()
})
</script>

<template>
  <div class="flex" style="height: calc(100vh - 120px)">
    <!-- 左侧菜单栏 -->
    <div
      v-show="panelVisible"
      class="skill-panel"
      style="width: 280px"
    >
      <!-- 移动端关闭按钮 -->
      <div v-if="isMobile" class="flex justify-end mb-2">
        <NButton size="tiny" quaternary @click="panelVisible = false">
          <TheIcon icon="material-symbols:close" :size="18" />
        </NButton>
      </div>

      <!-- 面板头部 -->
      <div class="panel-header">
        <div class="flex items-center justify-between mb-3">
          <span class="panel-label">{{ $t('views.skill.title_cn_735ac607') }}</span>
          <span class="panel-count">{{ skills.length }}</span>
        </div>
        <NInput
          v-model:value="searchQuery"
          :placeholder="$t('views.skill.placeholder_cn_d6b4ce19') || '搜索技能...'"
          clearable
          size="small"
          class="search-input"
        >
          <template #prefix>
            <TheIcon icon="material-symbols:search" :size="16" class="text-gray-400" />
          </template>
        </NInput>
        <NButton type="primary" block @click="openCreate" class="create-btn" size="large">
          <TheIcon icon="material-symbols:add" :size="20" class="mr-1" />新建技能
        </NButton>
      </div>

      <!-- 卡片列表 -->
      <div class="card-list">
        <div
          v-for="(skill, idx) in filteredSkills"
          :key="skill.id"
          class="menu-card"
          :class="{ 'card-selected': selectedSkill?.id === skill.id }"
          @click="selectSkill(skill)"
        >
          <div class="card-accent" :style="{ background: cardAccent(idx) }" />
          <div class="card-avatar" :style="{ background: cardAccent(idx) }">
            {{ skill.title.charAt(0) }}
          </div>
          <div class="card-body">
            <div class="card-title">{{ skill.title }}</div>
            <div class="card-meta">
              <span class="card-date">{{ skill.updated_at?.slice(0, 10) }}</span>
              <span v-if="skill.users?.length" class="card-stat">
                <TheIcon icon="material-symbols:group" :size="14" class="mr-0.5" />{{ skill.users.length }}
              </span>
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-if="!filteredSkills.length && !loading" class="empty-state">
          <TheIcon icon="material-symbols:inbox-outline" :size="40" class="text-gray-300 dark:text-gray-600 mb-3" />
          <p class="text-sm text-gray-400">
            {{ searchQuery ? '无匹配技能' : '暂无技能，请新建' }}
          </p>
        </div>
      </div>
    </div>

    <!-- 右侧内容栏 -->
    <div class="flex-1 min-w-0 overflow-auto flex flex-col">
      <div v-if="!selectedSkill" class="flex items-center justify-center h-full text-gray-400 text-base">
        请在左侧选择一个技能
      </div>

      <div v-else class="h-full flex flex-col">
        <!-- 移动端展开按钮 + 顶部操作栏 -->
        <div class="flex items-center justify-between px-4 py-3 border-b">
          <div class="flex items-center gap-2">
              <NButton v-if="isMobile" size="tiny" quaternary @click="panelVisible = true">
              <TheIcon icon="material-symbols:menu" :size="18" />
            </NButton>
            <h2 class="text-lg font-bold m-0">{{ selectedSkill.title }}</h2>
          </div>
          <NSpace>
            <NButton size="small" @click="saveContent">
              <TheIcon icon="material-symbols:save" :size="16" class="mr-4" />保存
            </NButton>
            <NButton size="small" @click="openEdit">
              <TheIcon icon="material-symbols:edit" :size="16" class="mr-4" />属性
            </NButton>
            <NButton size="small" @click="exportSkill">
              <TheIcon icon="material-symbols:download" :size="16" class="mr-4" />导出
            </NButton>
            <NPopconfirm @positive-click="deleteSkill">
              <template #trigger>
                <NButton size="small" type="error">
                  <TheIcon icon="material-symbols:delete-outline" :size="16" class="mr-4" />删除
                </NButton>
              </template>
              确认删除该技能？
            </NPopconfirm>
          </NSpace>
        </div>

        <!-- vditor 编辑区 -->
        <div ref="editorContainer" class="flex-1" style="min-height: 0" />
      </div>
    </div>
  </div>

  <!-- 新建/编辑弹窗 -->
  <NModal
    v-model:show="showModal"
    :title="modalTitle"
    preset="card"
    style="width: 600px"
  >
    <!-- 编辑模式：无 Tab，直接显示表单 -->
    <template v-if="isEditing">
      <NForm
        ref="modalFormRef"
        :model="modalForm"
        label-placement="top"
      >
        <NFormItem :label="t('views.skill.label_cn_32c65d8d')" required>
          <NInput v-model:value="modalForm.title" :placeholder="t('views.skill.placeholder_cn_d6b4ce19')" />
        </NFormItem>
        <NFormItem :label="t('views.skill.label_cn_5f07f1ad')">
          <NSelect
            v-model:value="modalForm.user_ids"
            :options="userOptions"
            multiple
            :placeholder="t('views.skill.placeholder_cn_faa6f8dc')"
            filterable
          />
        </NFormItem>
      </NForm>
    </template>

    <!-- 新建模式：Tab 切换手动/AI -->
    <template v-else>
      <NTabs v-model:value="activeTab" type="line">
        <!-- 手动创建 Tab -->
        <NTabPane name="manual" :tab="t('views.skill.label_cn_4364e2f1')">
          <NForm
            ref="modalFormRef"
            :model="modalForm"
            label-placement="top"
          >
            <NFormItem :label="t('views.skill.label_cn_32c65d8d')" required>
              <NInput v-model:value="modalForm.title" :placeholder="t('views.skill.placeholder_cn_d6b4ce19')" />
            </NFormItem>
            <NFormItem :label="t('views.skill.label_cn_5f07f1ad')">
              <NSelect
                v-model:value="modalForm.user_ids"
                :options="userOptions"
                multiple
                :placeholder="t('views.skill.placeholder_cn_faa6f8dc')"
                filterable
              />
            </NFormItem>
          </NForm>
        </NTabPane>

        <!-- AI 创建 Tab -->
        <NTabPane name="ai" :tab="t('views.skill.label_cn_d9a6b4ad')">
          <NForm
            :model="aiForm"
            label-placement="top"
          >
            <NFormItem :label="t('views.skill.label_cn_c1dfc5cf')" required>
              <NSelect
                v-model:value="aiForm.proxy_name"
                :options="proxyOptions"
                :placeholder="t('views.skill.placeholder_cn_523369d2')"
                filterable
              />
            </NFormItem>
            <NFormItem :label="t('views.skill.label_cn_bae20831')">
              <NSelect
                v-model:value="aiForm.source_skill_id"
                :options="skillOptions"
                :placeholder="t('views.skill.placeholder_cn_00ca7a96')"
                filterable
                clearable
                @focus="loadSkillOptions"
              />
            </NFormItem>
            <NFormItem :label="t('views.skill.label_cn_47b7af95')" required>
              <NInput
                v-model:value="aiForm.prompt"
                type="textarea"
                :placeholder="t('views.skill.placeholder_cn_bf0d0c57')"
                :autosize="{ minRows: 4, maxRows: 10 }"
              />
            </NFormItem>
            <NFormItem :label="t('views.skill.label_cn_5f07f1ad')">
              <NSelect
                v-model:value="aiForm.user_ids"
                :options="userOptions"
                multiple
                :placeholder="t('views.skill.placeholder_cn_faa6f8dc')"
                filterable
              />
            </NFormItem>
          </NForm>
        </NTabPane>
      </NTabs>
    </template>

    <template #footer>
      <NSpace justify="end">
        <NButton @click="showModal = false">取消</NButton>
        <NButton
          v-if="isEditing || activeTab === 'manual'"
          type="primary"
          @click="handleModalSubmit"
        >
          确认
        </NButton>
        <NButton
          v-else
          type="primary"
          :loading="aiCreating"
          @click="handleAICreate"
        >
          AI生成
        </NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
.skill-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-right: 1px solid var(--n-border-color, #e5e7eb);
  background: var(--n-color, #fafbfc);
  overflow: hidden;
}

.panel-header {
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--n-border-color, #f0f0f0);
  flex-shrink: 0;
}

.panel-label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #9ca3af;
}

.panel-count {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  background: #f3f4f6;
  padding: 1px 8px;
  border-radius: 999px;
}
:root.dark .panel-count {
  background: #374151;
}

.search-input {
  margin-bottom: 12px;
}

.create-btn {
  background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
  border: none !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
  transition: all 0.2s;
}
.create-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
}

.card-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

.menu-card {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  margin-bottom: 4px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
  overflow: hidden;
}
.menu-card:hover {
  background: #f3f4f6;
  transform: translateX(2px);
}
:root.dark .menu-card:hover {
  background: rgba(255,255,255,0.05);
}

.card-selected {
  background: linear-gradient(135deg, #eef2ff, #e0e7ff) !important;
  box-shadow: 0 2px 6px rgba(99, 102, 241, 0.12);
}
:root.dark .card-selected {
  background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.1)) !important;
}

.card-accent {
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 2px 2px 0;
  opacity: 0;
  transition: opacity 0.2s;
}
.card-selected .card-accent {
  opacity: 1;
}

.card-avatar {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 700;
  font-size: 15px;
  flex-shrink: 0;
  margin-right: 10px;
  transition: transform 0.2s;
}
.card-selected .card-avatar {
  transform: scale(1.08);
}

.card-body {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}
:root.dark .card-title {
  color: #e5e7eb;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 3px;
  font-size: 12px;
  color: #9ca3af;
}

.card-date {
  opacity: 0.8;
}

.card-stat {
  display: flex;
  align-items: center;
  opacity: 0.7;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}
</style>
