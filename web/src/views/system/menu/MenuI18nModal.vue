<script setup>
import { ref, computed, onMounted, h, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NSpin,
  NTable,
  NTag,
  NUpload,
  NDivider,
  NPopconfirm,
  useMessage,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import { renderIcon } from '@/utils'
import api from '@/api'

const { t } = useI18n()
const message = useMessage()

const props = defineProps({
  visible: Boolean,
})

const emit = defineEmits(['update:visible'])

const show = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

// ─── 状态 ──────────────────────────────────────────────────

const loading = ref(false)
const menus = ref([])
const translations = ref({})
const locales = ref(['en', 'tr', 'jp']) // 默认支持的语言
const editingLocale = ref('en')

// AI 生成
const aiLoading = ref(false)
const proxyOptions = ref([])
const selectedProxy = ref(null)
const aiMode = ref('incremental')
const aiTargetLocales = ref(['en', 'tr'])

// ─── 初始化 ────────────────────────────────────────────────

async function loadData() {
  loading.value = true
  try {
    const res = await api.getMenuI18nList()
    menus.value = res.data.menus || []
    translations.value = res.data.translations || {}
    // 从数据中提取已有的语言列表
    const locSet = new Set(['en', 'tr'])
    for (const tMap of Object.values(translations.value)) {
      for (const loc of Object.keys(tMap)) {
        locSet.add(loc)
      }
    }
    locales.value = [...locSet].sort()
  } catch (e) {
    message.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

async function loadProxies() {
  try {
    const res = await api.getAIProxyList({ page: 1, page_size: 100 })
    proxyOptions.value = (res.data || []).map((p) => ({
      label: p.name,
      value: p.name,
    }))
    if (proxyOptions.value.length > 0 && !selectedProxy.value) {
      selectedProxy.value = proxyOptions.value[0].value
    }
  } catch (e) {
    console.error('加载AI代理失败', e)
  }
}

onMounted(() => {
  if (show.value) {
    loadData()
    loadProxies()
  }
})

// 监听 visible 变化，打开时加载数据
watch(show, (val) => {
  if (val) {
    loadData()
    loadProxies()
  }
})

// ─── 表格列 ────────────────────────────────────────────────

const columns = computed(() => {
  const cols = [
    { title: 'ID', key: 'id', width: 50, align: 'center' },
    { title: '原始名称', key: 'name', width: 120, ellipsis: { tooltip: true } },
    { title: '路径', key: 'path', width: 120, ellipsis: { tooltip: true } },
  ]
  // 为每个语言添加一列
  for (const loc of locales.value) {
    cols.push({
      title: loc.toUpperCase(),
      key: `i18n_${loc}`,
      width: 120,
      render(row) {
        const val = (translations.value[row.id] || {})[loc] || ''
        return h(NInput, {
          size: 'small',
          value: val,
          placeholder: row.name,
          onUpdateValue: (v) => updateTranslation(row.id, loc, v),
        })
      },
    })
  }
  return cols
})

// ─── 翻译操作 ──────────────────────────────────────────────

async function updateTranslation(menuId, locale, name) {
  if (!name || !name.trim()) return
  try {
    await api.saveMenuI18n({ menu_id: menuId, locale, name: name.trim() })
    if (!translations.value[menuId]) {
      translations.value[menuId] = {}
    }
    translations.value[menuId][locale] = name.trim()
  } catch (e) {
    message.error('保存失败')
  }
}

// ─── AI 生成 ───────────────────────────────────────────────

async function handleAIGenerate() {
  if (!selectedProxy.value) {
    message.warning('请选择AI代理')
    return
  }
  if (aiTargetLocales.value.length === 0) {
    message.warning('请选择目标语言')
    return
  }

  aiLoading.value = true
  try {
    const res = await api.aiGenerateMenuI18n({
      proxy_name: selectedProxy.value,
      target_locales: aiTargetLocales.value,
      mode: aiMode.value,
    })
    const result = res.data
    message.success('AI翻译完成')
    // 重新加载数据
    await loadData()
  } catch (e) {
    message.error('AI翻译失败: ' + (e.message || '未知错误'))
  } finally {
    aiLoading.value = false
  }
}

// ─── 导出 ──────────────────────────────────────────────────

async function handleExport(locale) {
  try {
    const res = await api.exportMenuI18n({ locale })
    const data = res.data || res
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `menu-i18n-${locale}.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success(`语言 ${locale} 已导出`)
  } catch (e) {
    message.error('导出失败')
  }
}

// ─── 导入 ──────────────────────────────────────────────────

async function handleImport(locale, file) {
  if (!file) return
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    const entries = data.entries || []
    await api.importMenuI18n({ locale, entries })
    message.success(`语言 ${locale} 导入成功`)
    await loadData()
  } catch (e) {
    message.error('导入失败: ' + (e.message || '未知错误'))
  }
}
</script>

<template>
  <NModal
    v-model:show="show"
    title="菜单国际化管理"
    preset="card"
    style="width: 1100px; max-height: 85vh"
    @mask-click="null"
  >
    <template #header>
      <span style="display: flex; align-items: center; gap: 8px">
        <TheIcon icon="material-symbols:translate" :size="20" /> 菜单国际化管理
      </span>
    </template>

    <NSpin :show="loading">
      <div style="display: flex; flex-direction: column; gap: 12px; min-height: 400px">
        <!-- 操作栏 -->
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
          <span style="font-weight: 600; white-space: nowrap">AI代理：</span>
          <NSelect
            v-model:value="selectedProxy"
            :options="proxyOptions"
            placeholder="选择AI代理"
            style="width: 180px"
            clearable
          />
          <span style="font-weight: 600; white-space: nowrap">目标语言：</span>
          <NSelect
            v-model:value="aiTargetLocales"
            :options="locales.map(l => ({ label: l.toUpperCase(), value: l }))"
            placeholder="选择语言"
            multiple
            style="width: 180px"
          />
          <span style="font-weight: 600; white-space: nowrap">模式：</span>
          <NSelect
            v-model:value="aiMode"
            :options="[
              { label: '增量（只翻译缺失）', value: 'incremental' },
              { label: '全量（覆盖已有）', value: 'full' },
            ]"
            style="width: 160px"
          />
          <NButton type="primary" :loading="aiLoading" @click="handleAIGenerate">
            <TheIcon icon="material-symbols:auto-awesome" :size="16" class="mr-4" />AI翻译
          </NButton>
        </div>

        <!-- 导出/导入 语言选择 -->
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
          <span style="font-weight: 600; white-space: nowrap">导出/导入：</span>
          <template v-for="loc in locales" :key="loc">
            <NButton size="small" secondary @click="handleExport(loc)">
              <TheIcon icon="material-symbols:download" :size="14" class="mr-4" />导出 {{ loc.toUpperCase() }}
            </NButton>
            <NUpload
              :show-file-list="false"
              accept=".json"
              @change="({ file }) => handleImport(loc, file.file)"
            >
              <NButton size="small" secondary>
                <TheIcon icon="material-symbols:upload" :size="14" class="mr-4" />导入 {{ loc.toUpperCase() }}
              </NButton>
            </NUpload>
          </template>
        </div>

        <NDivider style="margin: 4px 0" />

        <!-- 翻译表格 -->
        <div style="overflow: auto; flex: 1">
          <NTable
            v-if="menus.length > 0"
            :columns="columns"
            :data="menus"
            :single-line="false"
            size="small"
            :bordered="true"
            style="min-width: 800px"
          />
          <div v-else style="text-align: center; color: var(--n-text-color-3); padding: 40px 0">
            暂无菜单数据
          </div>
        </div>
      </div>
    </NSpin>

    <template #footer>
      <NSpace justify="end">
        <NButton @click="show = false">关闭</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
