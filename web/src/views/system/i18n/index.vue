<script setup>
import { useI18n } from 'vue-i18n'
import { computed, h, onMounted, ref } from 'vue'
import {



  NButton,
  NDataTable,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NTag,
  useMessage,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'

const { t } = useI18n()

defineOptions({ name: '国际化管理' })

const message = useMessage()
const $table = ref(null)

// locales 响应式数据，由 getData 内部更新
const locales = ref([])

// 编辑状态
const editingCells = ref({})
const editingValues = ref({})

// Key 搜索过滤
const searchText = ref('')

// ── getData：适配 CrudTable，内部做前端分页 ──
async function getData({ page = 1, page_size = 10 } = {}) {
  const res = await api.getI18nList()
  locales.value = res.data.locales || []
  const allEntries = res.data.entries || []
  const start = (page - 1) * page_size
  return {
    data: allEntries.slice(start, start + page_size),
    total: allEntries.length,
  }
}

// ── 动态构建列（locales 更新后自动重新计算） ──
const columns = computed(() => {
  const cols = [
    {
      title: 'Key',
      key: 'key',
      width: 280,
      fixed: 'left',
      ellipsis: { tooltip: true },
      filterOptionValue: searchText.value || null,
      filter(value, row) {
        if (!value) return true
        return row.key.toLowerCase().includes(value.toLowerCase())
      },
    },
    {
      title: t('views.network.regionBoundary.fileColumns.fileType'),
      key: 'type',
      width: 70,
      align: 'center',
      render(row) {
        const typeMap = { string: '文本', array: '数组', number: '数字', boolean: '布尔' }
        return h(NTag, { type: row.type === 'string' ? 'info' : 'warning', size: 'small' }, {
          default: () => typeMap[row.type] || row.type,
        })
      },
    },
  ]

  locales.value.forEach((loc) => {
    const langNames = { cn: t('lang'), en: 'English', tr: 'Türkçe', jp: '日本語', fr: 'Français', de: 'Deutsch', ko: '한국어', es: 'Español', ru: 'Русский', ar: 'العربية' }
    cols.push({
      title: langNames[loc] || loc.toUpperCase(),
      key: `locale_${loc}`,
      width: 200,
      ellipsis: { tooltip: true },
      render(row) {
        const cellKey = `${row.key}_${loc}`
        const isEditing = editingCells.value[cellKey]
        const val = row.translations[loc]

        if (row.type !== 'string' || !isEditing) {
          const display = val === null || val === undefined
            ? h('span', { style: 'color: #999; font-style: italic' }, '—')
            : typeof val === 'string'
              ? val
              : JSON.stringify(val).slice(0, 60) + (JSON.stringify(val).length > 60 ? '...' : '')
          return h('div', {
            style: 'cursor: pointer; min-height: 28px; padding: 4px 8px; border-radius: 4px;',
            class: 'cell-hover',
            onClick() {
              if (row.type === 'string') {
                startEdit(row, loc, val || '')
              }
            },
          }, display)
        }

        return h(NInput, {
          size: 'small',
          value: editingValues.value[cellKey],
          autofocus: true,
          onUpdateValue(v) {
            editingValues.value[cellKey] = v
          },
          onBlur() {
            commitEdit(row, loc)
          },
          onKeydown(e) {
            if (e.key === 'Enter') {
              commitEdit(row, loc)
            } else if (e.key === 'Escape') {
              cancelEdit(row, loc)
            }
          },
        })
      },
    })
  })

  return cols
})

// ── 行内编辑（逻辑不变） ──
function startEdit(row, loc, currentValue) {
  const cellKey = `${row.key}_${loc}`
  editingCells.value = { ...editingCells.value, [cellKey]: true }
  editingValues.value = { ...editingValues.value, [cellKey]: currentValue }
}

function cancelEdit(row, loc) {
  const cellKey = `${row.key}_${loc}`
  const next = { ...editingCells.value }
  delete next[cellKey]
  editingCells.value = next
  const nextVals = { ...editingValues.value }
  delete nextVals[cellKey]
  editingValues.value = nextVals
}

async function commitEdit(row, loc) {
  const cellKey = `${row.key}_${loc}`
  const newValue = editingValues.value[cellKey]
  cancelEdit(row, loc)

  if (newValue === row.translations[loc]) return

  try {
    await api.updateI18n({ key: row.key, locale: loc, value: newValue })
    row.translations[loc] = newValue
    message.success('已保存')
  } catch (e) {
    message.error(t('views.network.roadNetworkWorkbench.messages.saveFail'))
  }
}

// ── 导出 ──
async function handleExport() {
  try {
    const res = await api.exportI18n()
    const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `i18n_export_${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success(t('views.network.roadNetworkWorkbench.messages.exportSuccess'))
  } catch (e) {
    message.error(t('views.network.roadNetworkWorkbench.messages.exportFail'))
  }
}

// ── 导入 ──
const importVisible = ref(false)
const importLocale = ref('')
const importJsonStr = ref('')
const importLoading = ref(false)

function openImport() {
  importLocale.value = ''
  importJsonStr.value = ''
  importVisible.value = true
}

async function handleImport() {
  if (!importLocale.value || !importJsonStr.value) {
    message.warning('请填写语言代码和翻译数据')
    return
  }
  let data
  try {
    data = JSON.parse(importJsonStr.value)
  } catch {
    message.error('JSON 格式错误')
    return
  }
  importLoading.value = true
  try {
    await api.importI18n({ locale: importLocale.value, data })
    message.success(`语言 ${importLocale.value} 导入成功`)
    importVisible.value = false
    $table.value?.handleSearch()
  } catch (e) {
    message.error(t('views.network.region.messages.importFail'))
  } finally {
    importLoading.value = false
  }
}

// ── AI 生成 ──
const aiVisible = ref(false)
const aiGenerating = ref(false)
const aiProxyName = ref(null)
const aiTargetLocale = ref('')
const aiTargetLangName = ref('')
const aiPromptExtra = ref('')
const proxyOptions = ref([])

async function openAIGenerate() {
  aiProxyName.value = null
  aiTargetLocale.value = ''
  aiTargetLangName.value = ''
  aiPromptExtra.value = ''
  aiVisible.value = true
  try {
    const res = await api.getAIProxyList({ page: 1, page_size: 9999 })
    proxyOptions.value = (res.data || []).map((p) => ({
      label: `${p.name} (${p.model || 'unknown'})`,
      value: p.name,
    }))
  } catch {
    // ignore
  }
}

async function handleAIGenerate() {
  if (!aiProxyName.value || !aiTargetLocale.value || !aiTargetLangName.value) {
    message.warning('请完善 AI 生成参数')
    return
  }
  aiGenerating.value = true
  try {
    const res = await api.aiGenerateI18n({
      ai_proxy_name: aiProxyName.value,
      target_locale: aiTargetLocale.value,
      target_lang_name: aiTargetLangName.value,
      prompt_extra: aiPromptExtra.value || null,
    })
    message.success(`AI 翻译生成完成，共翻译 ${res.data?.translated_count || 0} 条`)
    aiVisible.value = false
    $table.value?.handleSearch()
  } catch (e) {
    message.error('AI 翻译生成失败: ' + (e.message || t('views.network.roadNetworkWorkbench.messages.unknownError')))
  } finally {
    aiGenerating.value = false
  }
}

// ── 前端扫描（弹窗内保持 NDataTable） ──
const scanVisible = ref(false)
const scanResults = ref([])
const scanTotal = ref(0)
const scanLoading = ref(false)

async function handleScanFrontend() {
  scanLoading.value = true
  try {
    const res = await api.scanFrontendI18n()
    scanResults.value = res.data.items || []
    scanTotal.value = res.data.total || 0
    scanVisible.value = true
    message.success(`扫描完成，发现 ${scanTotal.value} 处硬编码字符串`)
  } catch (e) {
    message.error('扫描失败')
  } finally {
    scanLoading.value = false
  }
}

const scanColumns = [
  { title: t('views.network.roadNetworkWorkbench.stats.fileSize'), key: 'file', width: 200, ellipsis: { tooltip: true } },
  { title: '行号', key: 'line', width: 60, align: 'center' },
  { title: '文本', key: 'text', width: 150, ellipsis: { tooltip: true } },
  { title: '建议 Key', key: 'suggested_key', width: 200, ellipsis: { tooltip: true } },
  {
    title: '上下文',
    key: 'context',
    ellipsis: { tooltip: true },
    render(row) {
      return h('code', { style: 'font-size: 12px; color: #888;' }, row.context)
    },
  },
]

onMounted(() => {
  // CrudTable 不会自动加载，需要手动触发
  $table.value?.handleSearch()
})
</script>

<template>
  <CommonPage title="国际化管理">
    <template #action>
      <NSpace>
        <NButton type="primary" @click="$table?.handleSearch()">
          <TheIcon icon="material-symbols:refresh" :size="18" class="mr-5" />刷新
        </NButton>
        <NButton @click="handleExport">
          <TheIcon icon="material-symbols:download" :size="18" class="mr-5" />导出
        </NButton>
        <NButton @click="openImport">
          <TheIcon icon="material-symbols:upload" :size="18" class="mr-5" />导入
        </NButton>
        <NButton type="warning" @click="handleScanFrontend" :loading="scanLoading">
          <TheIcon icon="material-symbols:search" :size="18" class="mr-5" />扫描前端硬编码
        </NButton>
        <NButton type="info" v-permission="'post/api/v1/i18n/ai-generate'" @click="openAIGenerate">
          <TheIcon icon="material-symbols:auto-awesome" :size="18" class="mr-5" />AI 生成新语言
        </NButton>
      </NSpace>
    </template>

    <CrudTable
      ref="$table"
      :columns="columns"
      :get-data="getData"
      :is-pagination="true"
      row-key="key"
      :scroll-x="1800"
      style="margin-top: 12px"
    />

    <!-- 导入弹窗（不变） -->
    <NModal v-model:show="importVisible" preset="card" title="导入国际化数据" style="width: 700px">
      <div>
        <label style="display: block; margin-bottom: 4px"><b>语言代码</b>（如 jp, fr, de）</label>
        <NInput v-model:value="importLocale" placeholder="如: jp" />
      </div>
      <div style="margin-top: 12px">
        <label style="display: block; margin-bottom: 4px"><b>翻译 JSON 数据</b></label>
        <NInput v-model:value="importJsonStr" type="textarea" :rows="14" placeholder="粘贴完整翻译 JSON..." />
      </div>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="importVisible = false">取消</NButton>
          <NButton type="primary" :loading="importLoading" @click="handleImport">确认导入</NButton>
        </NSpace>
      </template>
    </NModal>

    <!-- AI 生成弹窗 -->
    <NModal v-model:show="aiVisible" preset="card" title="AI 生成新语言翻译" style="width: 550px">
      <div>
        <label style="display: block; margin-bottom: 4px"><b>AI 代理</b></label>
        <NSelect
          v-model:value="aiProxyName"
          :options="proxyOptions"
          :placeholder="t('views.network.roadNetworkWorkbench.tabs.fields.selectAIProxy')"
          filterable
        />
      </div>
      <div style="margin-top: 12px">
        <label style="display: block; margin-bottom: 4px"><b>目标语言代码</b>（如 jp, fr, de）</label>
        <NInput v-model:value="aiTargetLocale" placeholder="如: jp" />
      </div>
      <div style="margin-top: 12px">
        <label style="display: block; margin-bottom: 4px"><b>目标语言名称（中文描述）</b></label>
        <NInput v-model:value="aiTargetLangName" placeholder="如: 日文、法文、德文" />
      </div>
      <div style="margin-top: 12px">
        <label style="display: block; margin-bottom: 4px"><b>额外提示词</b>（可选）</label>
        <NInput v-model:value="aiPromptExtra" placeholder="额外的翻译要求..." />
      </div>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="aiVisible = false">取消</NButton>
          <NButton type="primary" :loading="aiGenerating" @click="handleAIGenerate">
            {{ aiGenerating ? '生成中...' : '开始生成' }}
          </NButton>
        </NSpace>
      </template>
    </NModal>

    <!-- 扫描结果弹窗 -->
    <NModal v-model:show="scanVisible" preset="card" title="前端硬编码扫描结果" style="width: 900px">
      <div style="margin-bottom: 12px; color: #666">
        共发现 <b>{{ scanTotal }}</b> 处硬编码字符串
      </div>
      <NDataTable
        :columns="scanColumns"
        :data="scanResults"
        :max-height="500"
        virtual-scroll
        size="small"
        striped
      />
    </NModal>
  </CommonPage>
</template>

<style scoped>
/* UnoCSS 全局 html { font-size: 4px } 导致 text-* rem 类过小，用 px 覆盖 */
.cell-hover:hover {
  background: var(--n-color-hover, rgba(0, 0, 0, 0.04));
}
</style>