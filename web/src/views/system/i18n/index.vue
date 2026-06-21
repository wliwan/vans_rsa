<script setup>
import { useI18n } from 'vue-i18n'
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton,
  NDataTable,
  NInput,
  NModal,
  NRadio,
  NRadioGroup,
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

// ── AI 翻译 ──
const aiVisible = ref(false)
const aiGenerating = ref(false)
const aiProxyName = ref(null)
const aiTargetLanguage = ref(null)
const aiMode = ref('incremental')
const proxyOptions = ref([])

const modeOptions = [
  { label: '增量模式（只补充未翻译的条目，已有翻译保留）', value: 'incremental' },
  { label: '全量模式（全部重新翻译替换）', value: 'full' },
]

// 主流语言列表（除中文外）
const languageOptions = [
  { label: 'English（英文）', value: 'en' },
  { label: '日本語（日文）', value: 'jp' },
  { label: 'Français（法文）', value: 'fr' },
  { label: 'Deutsch（德文）', value: 'de' },
  { label: '한국어（韩文）', value: 'ko' },
  { label: 'Español（西班牙文）', value: 'es' },
  { label: 'Русский（俄文）', value: 'ru' },
  { label: 'العربية（阿拉伯文）', value: 'ar' },
  { label: 'Português（葡萄牙文）', value: 'pt' },
  { label: 'Italiano（意大利文）', value: 'it' },
  { label: 'Türkçe（土耳其文）', value: 'tr' },
  { label: 'ไทย（泰文）', value: 'th' },
  { label: 'Tiếng Việt（越南文）', value: 'vi' },
  { label: 'Nederlands（荷兰文）', value: 'nl' },
  { label: 'Polski（波兰文）', value: 'pl' },
]

async function openAIGenerate() {
  aiProxyName.value = null
  aiTargetLanguage.value = null
  aiMode.value = 'incremental'
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
  if (!aiProxyName.value || !aiTargetLanguage.value) {
    message.warning('请选择 AI 代理和目标语言')
    return
  }
  aiGenerating.value = true
  try {
    const res = await api.aiGenerateI18n({
      ai_proxy_name: aiProxyName.value,
      target_locale: aiTargetLanguage.value,
      mode: aiMode.value,
    })
    const failedBatches = res.data?.failed_batches
    const skipped = res.data?.skipped_count || 0
    let msg = `AI 翻译完成，共翻译 ${res.data?.translated_count || 0} / ${res.data?.total_count || 0} 条`
    if (skipped > 0) {
      msg += `（跳过 ${skipped} 条已有翻译）`
    }
    if (failedBatches && failedBatches.length > 0) {
      msg += `（${failedBatches.length} 个批次失败）`
    }
    message.success(msg)
    aiVisible.value = false
    $table.value?.handleSearch()
  } catch (e) {
    message.error('AI 翻译失败: ' + (e.message || t('views.network.roadNetworkWorkbench.messages.unknownError')))
  } finally {
    aiGenerating.value = false
  }
}

// ── 扫描新字段并添加 ──
const scanAddVisible = ref(false)
const scanAddProxyName = ref(null)
const scanAddLoading = ref(false)
const scanLoading = ref(false)
const scanAddProxyOptions = ref([])

async function openScanAdd() {
  scanAddProxyName.value = null
  scanAddVisible.value = true
  try {
    const res = await api.getAIProxyList({ page: 1, page_size: 9999 })
    scanAddProxyOptions.value = (res.data || []).map((p) => ({
      label: `${p.name} (${p.model || 'unknown'})`,
      value: p.name,
    }))
  } catch {
    // ignore
  }
}

async function handleScanAdd() {
  if (!scanAddProxyName.value) {
    message.warning('请选择 AI 代理')
    return
  }
  scanAddLoading.value = true
  scanLoading.value = true
  try {
    const res = await api.scanAndAddI18n({
      ai_proxy_name: scanAddProxyName.value,
    })
    const d = res.data || {}
    let msg = `扫描到 ${d.scanned_count || 0} 条新字段，成功添加 ${d.added_count || 0} 条`
    if (d.skipped_count > 0) msg += `，跳过 ${d.skipped_count} 条已有字段`
    if (d.failed_batches && d.failed_batches.length > 0) msg += `（${d.failed_batches.length} 个批次失败）`
    message.success(msg)
    scanAddVisible.value = false
    $table.value?.handleSearch()
  } catch (e) {
    message.error('扫描添加失败: ' + (e.message || '未知错误'))
  } finally {
    scanAddLoading.value = false
    scanLoading.value = false
  }
}

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
        <NButton type="warning" @click="openScanAdd">
          <TheIcon icon="material-symbols:search" :size="18" class="mr-5" />扫描新字段并添加
        </NButton>
        <NButton type="info" v-permission="'post/api/v1/i18n/ai-generate'" @click="openAIGenerate">
          <TheIcon icon="material-symbols:auto-awesome" :size="18" class="mr-5" />AI 翻译
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

    <!-- AI 翻译弹窗 -->
    <NModal v-model:show="aiVisible" preset="card" title="AI 翻译" style="width: 600px">
      <div>
        <label style="display: block; margin-bottom: 4px"><b>AI 代理</b></label>
        <NSelect
          v-model:value="aiProxyName"
          :options="proxyOptions"
          :placeholder="t('views.network.roadNetworkWorkbench.tabs.fields.selectAIProxy')"
          filterable
        />
      </div>
      <div style="margin-top: 16px">
        <label style="display: block; margin-bottom: 4px"><b>目标语言</b></label>
        <NSelect
          v-model:value="aiTargetLanguage"
          :options="languageOptions"
          placeholder="请选择要翻译成的目标语言"
          filterable
        />
      </div>
      <div style="margin-top: 16px">
        <label style="display: block; margin-bottom: 6px"><b>翻译模式</b></label>
        <NRadioGroup v-model:value="aiMode" name="aiMode">
          <NSpace vertical :size="8">
            <NRadio value="incremental">
              <span style="font-weight: 500">增量模式</span>
              <span style="color: #666; margin-left: 8px; font-size: 13px">只补充未翻译的条目，已有翻译保留</span>
            </NRadio>
            <NRadio value="full">
              <span style="font-weight: 500">全量模式</span>
              <span style="color: #666; margin-left: 8px; font-size: 13px">全部重新翻译并替换现有文件</span>
            </NRadio>
          </NSpace>
        </NRadioGroup>
      </div>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="aiVisible = false">取消</NButton>
          <NButton type="primary" :loading="aiGenerating" @click="handleAIGenerate">
            {{ aiGenerating ? '翻译中...' : '开始翻译' }}
          </NButton>
        </NSpace>
      </template>
    </NModal>

    <!-- 扫描新字段并添加弹窗 -->
    <NModal v-model:show="scanAddVisible" preset="card" title="扫描新字段并添加" style="width: 500px">
      <div>
        <label style="display: block; margin-bottom: 4px"><b>AI 代理</b></label>
        <NSelect
          v-model:value="scanAddProxyName"
          :options="scanAddProxyOptions"
          placeholder="请选择用于生成 key 的 AI 代理"
          filterable
        />
        <div style="margin-top: 8px; color: #888; font-size: 13px">
          将扫描前端代码中直接使用的中文文本，用 AI 生成合适的 i18n key 后追加到 cn.json。
        </div>
      </div>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="scanAddVisible = false">取消</NButton>
          <NButton type="primary" :loading="scanAddLoading" @click="handleScanAdd">
            {{ scanAddLoading ? '扫描中...' : '开始扫描并添加' }}
          </NButton>
        </NSpace>
      </template>
    </NModal>
  </CommonPage>
</template>

<style scoped>
/* UnoCSS 全局 html { font-size: 4px } 导致 text-* rem 类过小，用 px 覆盖 */
.cell-hover:hover {
  background: var(--n-color-hover, rgba(0, 0, 0, 0.04));
}
</style>