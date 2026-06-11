<script setup>
import { onMounted, onBeforeUnmount, ref, nextTick } from 'vue'
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
  useMessage,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

defineOptions({ name: '技能管理' })

const message = useMessage()

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
  showModal.value = true
  loadUserOptions()
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

// ---- 获取当前编辑器内容 ----
function getEditorContent() {
  return vditorInstance ? vditorInstance.getValue() : ''
}

// ---- 提交创建/更新 ----
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
    style="width: 560px"
  >
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
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showModal = false">取消</NButton>
        <NButton type="primary" @click="handleModalSubmit">确认</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
