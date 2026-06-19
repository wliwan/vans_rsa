<script setup>
import { computed, onMounted, onBeforeUnmount, ref, nextTick, reactive } from 'vue'
import { useBreakpoints } from '@vueuse/core'
import {
  NButton,
  NInput,
  NLayout,
  NLayoutSider,
  NLayoutContent,
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

defineOptions({ name: '技能管理' })

const message = useMessage()

// 移动端适配：默认折叠左侧 Sider
const bp = reactive(useBreakpoints({ sm: 666, md: 991 }))
const isMobileCollapsed = computed(() => bp.isSmaller('sm') || bp.between('sm', 'md'))

// ---- 状态 ----
const skills = ref([])
const selectedSkill = ref(null)
const loading = ref(false)

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
    message.error('加载技能列表失败')
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
      placeholder: '在此输入 Markdown 内容...',
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
    message.error('加载技能内容失败')
  }
}

// ---- 新建 Skill ----
function openCreate() {
  isEditing.value = false
  modalTitle.value = '新建技能'
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
    message.warning('请先选择一个技能')
    return
  }
  isEditing.value = true
  modalTitle.value = '编辑技能'
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
    message.warning('请输入标题')
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
      message.success('更新成功')
      selectedSkill.value.title = modalForm.value.title
      // 重新加载内容
      await selectSkill(selectedSkill.value)
    } else {
      await api.createSkill({
        title: modalForm.value.title,
        content: editorContent,
        user_ids: modalForm.value.user_ids,
      })
      message.success('创建成功')
    }
    showModal.value = false
    await loadSkills()
  } catch (e) {
    message.error('操作失败')
  }
}

// ---- AI 创建提交 ----
async function handleAICreate() {
  if (!aiForm.value.proxy_name) {
    message.warning('请选择AI代理')
    return
  }
  if (!aiForm.value.prompt.trim()) {
    message.warning('请输入提示词')
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
    message.success('AI创建成功')
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
    message.error(e?.message || 'AI创建失败')
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
    message.success('保存成功')
  } catch (e) {
    message.error('保存失败')
  }
}

// ---- 删除 Skill ----
async function deleteSkill() {
  if (!selectedSkill.value) {
    message.warning('请先选择一个技能')
    return
  }
  try {
    await api.deleteSkill({ skill_id: selectedSkill.value.id })
    message.success('删除成功')
    selectedSkill.value = null
    destroyVditor()
    await loadSkills()
  } catch (e) {
    message.error('删除失败')
  }
}

// ---- 导出 Skill ----
async function exportSkill() {
  if (!selectedSkill.value) {
    message.warning('请先选择一个技能')
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
    message.success('导出成功')
  } catch (e) {
    message.error('导出失败')
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
  <NLayout has-sider style="height: calc(100vh - 120px)">
    <!-- 左侧菜单栏 -->
    <NLayoutSider
      bordered
      width="280"
      :collapsed-width="0"
      :collapsed="isMobileCollapsed"
      show-trigger="arrow-circle"
      :native-scrollbar="false"
      content-style="padding: 12px"
    >
      <NSpace vertical>
        <NButton
          type="primary"
          block
          @click="openCreate"
        >
          <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新建技能
        </NButton>

        <NList
          hoverable
          clickable
          :show-divider="false"
        >
          <NListItem
            v-for="skill in skills"
            :key="skill.id"
            :class="{ 'bg-blue-50 dark:bg-blue-900': selectedSkill?.id === skill.id }"
            style="border-radius: 8px; margin-bottom: 4px; cursor: pointer"
            @click="selectSkill(skill)"
          >
            <div class="flex flex-col flex-1 min-w-0">
              <span class="font-medium truncate">{{ skill.title }}</span>
              <span class="text-gray-400">{{ skill.updated_at }}</span>
            </div>
          </NListItem>
        </NList>

        <div v-if="!skills.length && !loading" class="text-center text-gray-400 py-10">
          暂无技能，请新建
        </div>
      </NSpace>
    </NLayoutSider>

    <!-- 右侧内容栏 -->
    <NLayoutContent content-style="padding: 0">
      <div v-if="!selectedSkill" class="flex items-center justify-center h-full text-gray-400 text-base">
        请在左侧选择一个技能
      </div>

      <div v-else class="h-full flex flex-col">
        <!-- 顶部操作栏 -->
        <div class="flex items-center justify-between px-4 py-3 border-b">
          <div class="flex items-center gap-2">
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
    </NLayoutContent>
  </NLayout>

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
        <NFormItem label="标题" required>
          <NInput v-model:value="modalForm.title" placeholder="请输入技能标题" />
        </NFormItem>
        <NFormItem label="授权用户">
          <NSelect
            v-model:value="modalForm.user_ids"
            :options="userOptions"
            multiple
            placeholder="选择可访问该技能的用户"
            filterable
          />
        </NFormItem>
      </NForm>
    </template>

    <!-- 新建模式：Tab 切换手动/AI -->
    <template v-else>
      <NTabs v-model:value="activeTab" type="line">
        <!-- 手动创建 Tab -->
        <NTabPane name="manual" tab="手动创建">
          <NForm
            ref="modalFormRef"
            :model="modalForm"
            label-placement="top"
          >
            <NFormItem label="标题" required>
              <NInput v-model:value="modalForm.title" placeholder="请输入技能标题" />
            </NFormItem>
            <NFormItem label="授权用户">
              <NSelect
                v-model:value="modalForm.user_ids"
                :options="userOptions"
                multiple
                placeholder="选择可访问该技能的用户"
                filterable
              />
            </NFormItem>
          </NForm>
        </NTabPane>

        <!-- AI 创建 Tab -->
        <NTabPane name="ai" tab="AI创建">
          <NForm
            :model="aiForm"
            label-placement="top"
          >
            <NFormItem label="AI代理" required>
              <NSelect
                v-model:value="aiForm.proxy_name"
                :options="proxyOptions"
                placeholder="选择AI代理"
                filterable
              />
            </NFormItem>
            <NFormItem label="参考技能（可选）">
              <NSelect
                v-model:value="aiForm.source_skill_id"
                :options="skillOptions"
                placeholder="选择一个现有技能作为参考风格"
                filterable
                clearable
                @focus="loadSkillOptions"
              />
            </NFormItem>
            <NFormItem label="提示词" required>
              <NInput
                v-model:value="aiForm.prompt"
                type="textarea"
                placeholder="描述你想要创建的技能，例如：生成一个关于 Python 数据分析的技能文档，包含数据清洗、可视化和统计分析方法"
                :autosize="{ minRows: 4, maxRows: 10 }"
              />
            </NFormItem>
            <NFormItem label="授权用户">
              <NSelect
                v-model:value="aiForm.user_ids"
                :options="userOptions"
                multiple
                placeholder="选择可访问该技能的用户"
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
