<script setup>
import { useI18n } from 'vue-i18n'
import { computed, h, onMounted, ref } from 'vue'
import { useTaskProgressStore } from '@/store/modules/taskProgress'
import {
  NButton,
  NCheckbox,
  NDataTable,
  NInput,
  NModal,
  NPopconfirm,
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

const taskStore = useTaskProgressStore()

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

// 未翻译筛选：选定语言后只显示该语言未翻译的行
const filterUntranslated = ref(null)

// 全量条目（用于统计和分页）
const allEntries = ref([])

// 根据筛选条件过滤后的条目
const filteredEntries = computed(() => {
  const entries = allEntries.value
  const loc = filterUntranslated.value
  if (!loc) return entries
  return entries.filter(e => {
    const v = e.translations[loc]
    return v === null || v === undefined || (typeof v === 'string' && v.trim() === '')
  })
})

// ── getData：适配 CrudTable，内部做前端分页 ──
async function getData({ page = 1, page_size = 10 } = {}) {
  const res = await api.getI18nList()
  locales.value = res.data.locales || []
  allEntries.value = res.data.entries || []
  const entries = filteredEntries.value
  const start = (page - 1) * page_size
  return {
    data: entries.slice(start, start + page_size),
    total: entries.length,
  }
}

// 统计：每种语言已翻译的条目数
const translationStats = computed(() => {
  const entries = allEntries.value
  const total = entries.length
  const stats = {}
  for (const loc of locales.value) {
    let count = 0
    for (const entry of entries) {
      const v = entry.translations[loc]
      if (v !== null && v !== undefined && (typeof v !== 'string' || v.trim() !== '')) {
        count++
      }
    }
    stats[loc] = { count, total }
  }
  return stats
})

// 多选
const checkedKeys = ref([])

// ── 动态构建列（locales 更新后自动重新计算） ──
const columns = computed(() => {
  const cols = [
    { type: 'selection' },
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
    const st = translationStats.value[loc]
    cols.push({
      title: st ? `${langNames[loc] || loc.toUpperCase()} ${st.count}/${st.total}` : (langNames[loc] || loc.toUpperCase()),
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
    // 筛选激活时刷新表格，已翻译行自动消失；无筛选时不刷新保持原位置
    if (filterUntranslated.value) $table.value?.handleSearch()
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
const aiTargetLanguages = ref([])
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
  aiTargetLanguages.value = []
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
  if (!aiProxyName.value || aiTargetLanguages.value.length === 0) {
    message.warning('请选择 AI 代理和目标语言')
    return
  }

  aiVisible.value = false
  const mode = aiMode.value
  const proxy = aiProxyName.value
  const languageNames = { en: '英文', jp: '日文', fr: '法文', de: '德文', ko: '韩文', es: '西班牙文', ru: '俄文', ar: '阿拉伯文', pt: '葡萄牙文', it: '意大利文', tr: '土耳其文', th: '泰文', vi: '越南文', nl: '荷兰文', pl: '波兰文' }

  const tasks = aiTargetLanguages.value.map(async (locale) => {
    const langName = languageNames[locale] || locale.toUpperCase()
    const taskId = taskStore.startTask(`AI 翻译 → ${langName}`)
    taskStore.updateProgress(taskId, { progress: 10, message: '正在翻译...' })
    try {
      const res = await api.aiGenerateI18n({
        ai_proxy_name: proxy,
        target_locale: locale,
        mode,
      })
      const d = res.data || {}
      let msg = `翻译完成，${d.translated_count || 0} / ${d.total_count || 0} 条`
      if (d.skipped_count > 0) msg += `（跳过 ${d.skipped_count} 条已有翻译）`
      if (d.failed_batches && d.failed_batches.length > 0) msg += `（${d.failed_batches.length} 批次失败）`
      taskStore.finishTask(taskId, msg)
    } catch (e) {
      taskStore.failTask(taskId, { message: `翻译失败`, detail: e.message || '未知错误' })
    }
    })

  try {
    await Promise.allSettled(tasks)
    $table.value?.handleSearch()
  } catch (e) {
    // 不应到达此处，错误已在各 task 内处理
  }
}

// ── 扫描新字段 ──
const scanAddVisible = ref(false)
const scanAddResults = ref([])
const scanAddTotal = ref(0)
const scanAddProxyName = ref(null)
const scanAddLoading = ref(false)
const scanAddScanning = ref(false)
const scanAddProxyOptions = ref([])

const hideMixedFields = ref(false)

const scanAddColumns = [
  { title: '文件', key: 'file', width: 200, ellipsis: { tooltip: true } },
  { title: '行号', key: 'line', width: 60, align: 'center' },
  { title: '中文文本', key: 'text', width: 240, ellipsis: { tooltip: true } },
  { title: '检测来源', key: 'source', width: 100, align: 'center' },
]

// 根据开关过滤显示结果
const scanAddDisplayed = computed(() => {
  if (!hideMixedFields.value) return scanAddResults.value
  return scanAddResults.value.filter(it => {
    if ((it.source === 'html-inline' || it.source === 'html-attribute') && it.text.length < 20) {
      return !/\b[$\w]*t\s*\(/.test(it._lineContent || '')
    }
    return true
  })
})

async function openScanAdd() {
  scanAddProxyName.value = null
  scanAddResults.value = []
  scanAddTotal.value = 0
  scanAddVisible.value = true
  try {
    const res = await api.getAIProxyList({ page: 1, page_size: 9999 })
    scanAddProxyOptions.value = (res.data || []).map(p => ({ label: `${p.name} (${p.model || 'unknown'})`, value: p.name }))
  } catch {
    // ignore
  }
  // 自动开始扫描
  await doScan()
}

async function doScan() {
  scanAddScanning.value = true
  try {
    const res = await api.scanDetectI18n()
    scanAddResults.value = res.items || []
    scanAddTotal.value = res.total || scanAddResults.value.length
  } catch (e) {
    message.error('扫描失败: ' + (e.message || '未知错误'))
  } finally {
    scanAddScanning.value = false
  }
}

async function handleScanAdd() {
  if (!scanAddProxyName.value) {
    message.warning('请选择 AI 代理')
    return
  }
  if (scanAddTotal.value === 0) {
    message.info('没有待处理的新字段')
    return
  }
  scanAddLoading.value = true
  // 将前端扫描结果发送给后端做 AI 处理（保留 start/end 用于回写源文件）
  const items = scanAddResults.value.map(it => ({ file: it.file, line: it.line, text: it.text, start: it.start, end: it.end, source: it.source }))
  try {
    const res = await api.processScanI18n({ ai_proxy_name: scanAddProxyName.value, items })
    const d = (res && res.data) || {}
    const added = d.added_count || 0
    const scanned = d.scanned_count || 0
    const replaced = d.replaced_count || 0
    let msg = `成功添加 ${added} 条`
    if (replaced > 0) msg += `，已替换源文件 ${replaced} 处`
    if (d.skipped_count > 0) msg += `，跳过 ${d.skipped_count} 条已有字段`
    message.success(msg)
    scanAddVisible.value = false
    $table.value?.handleSearch()
  } catch (e) {
    message.error('批量处理失败: ' + (e.message || '未知错误'))
  } finally {
    scanAddLoading.value = false
  }
}

async function handleBatchDelete() {
  if (checkedKeys.value.length === 0) return
  try {
    await api.batchDeleteI18n({ keys: checkedKeys.value })
    message.success(`已删除 ${checkedKeys.value.length} 个字段`)
    checkedKeys.value = []
    $table.value?.handleSearch()
  } catch (e) {
    message.error('批量删除失败: ' + (e.message || '未知错误'))
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
        <NButton type="warning" @click="openScanAdd" :loading="scanAddScanning && !scanAddVisible">
          <TheIcon icon="material-symbols:search" :size="18" class="mr-5" />扫描新字段并添加
        </NButton>
        <NButton type="info" v-permission="'post/api/v1/i18n/ai-generate'" @click="openAIGenerate">
          <TheIcon icon="material-symbols:auto-awesome" :size="18" class="mr-5" />AI 翻译
        </NButton>
        <NPopconfirm @positive-click="handleBatchDelete" v-if="checkedKeys.length > 0">
          <template #trigger>
            <NButton type="error" secondary>
              <TheIcon icon="material-symbols:delete-outline" :size="18" class="mr-5" />批量删除 ({{ checkedKeys.length }})
            </NButton>
          </template>
          确定删除选中的 {{ checkedKeys.length }} 个字段？此操作不可撤销。
        </NPopconfirm>
      </NSpace>
    </template>

    <!-- 翻译统计条 -->
    <div style="margin-top: 8px; display: flex; align-items: center; gap: 16px; font-size: 13px; color: #666">
      <span>共 <b style="color: #333">{{ allEntries.length }}</b> 个键值</span>
      <template v-for="loc in locales" :key="loc">
        <span v-if="translationStats[loc]" style="display: flex; align-items: center; gap: 4px; cursor: pointer; padding: 0 4px; border-radius: 4px"
              :style="filterUntranslated === loc ? { background: '#e8f0fe', fontWeight: 600 } : {}"
              @click="filterUntranslated = filterUntranslated === loc ? null : loc; $table?.handleSearch()">
          <span style="width: 8px; height: 8px; border-radius: 50%; display: inline-block"
                :style="{ background: translationStats[loc].count === translationStats[loc].total ? '#18a058' : translationStats[loc].count > 0 ? '#2080f0' : '#ddd' }" />
          <span>{{ { cn: t('lang'), en: 'EN', tr: 'TR', jp: 'JP', fr: 'FR', de: 'DE', ko: 'KO', es: 'ES', ru: 'RU', ar: 'AR', pt: 'PT', it: 'IT', th: 'TH', vi: 'VI', nl: 'NL', pl: 'PL' }[loc] || loc.toUpperCase() }}</span>
          <b :style="{ color: translationStats[loc].count === translationStats[loc].total ? '#18a058' : translationStats[loc].count > 0 ? '#2080f0' : '#999' }">
            {{ translationStats[loc].count }}
          </b>
        </span>
      </template>
    </div>
    <div v-if="filterUntranslated" style="margin-top: 4px; font-size: 12px; color: #2080f0">
      筛选「{{ { cn: t('lang'), en: 'English', tr: 'Türkçe', jp: '日本語', fr: 'Français', de: 'Deutsch', ko: '한국어', es: 'Español', ru: 'Русский', ar: 'العربية', pt: 'Português', it: 'Italiano', th: 'ไทย', vi: 'Tiếng Việt', nl: 'Nederlands', pl: 'Polski' }[filterUntranslated] || filterUntranslated }}」未翻译的行
      <NButton size="tiny" quaternary @click="filterUntranslated = null; $table?.handleSearch()">清除</NButton>
    </div>

    <CrudTable
      ref="$table"
      :columns="columns"
      :get-data="getData"
      :is-pagination="true"
      row-key="key"
      :scroll-x="1800"
      style="margin-top: 12px"
      @on-checked="(keys) => checkedKeys = keys"
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
          v-model:value="aiTargetLanguages"
          :options="languageOptions"
          placeholder="可选择多个语言同时翻译"
          multiple
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
            开始翻译
          </NButton>
        </NSpace>
      </template>
    </NModal>

    <!-- 扫描新字段并添加弹窗 -->
    <NModal v-model:show="scanAddVisible" preset="card" title="扫描新字段并添加" style="width: 800px">
      <div style="margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between">
        <span v-if="scanAddScanning" style="color: #888">正在扫描前端代码...</span>
        <span v-else style="color: #666">共发现 <b>{{ scanAddTotal }}</b> 条待翻译字段，显示 <b>{{ scanAddDisplayed.length }}</b> 条</span>
        <NButton size="small" @click="doScan" :loading="scanAddScanning">重新扫描</NButton>
      </div>
      <div v-if="!scanAddScanning && scanAddTotal > 0" style="margin-bottom: 4px">
        <NCheckbox v-model:checked="hideMixedFields" size="small">隐藏已混用 i18n 的组合字段</NCheckbox>
      </div>
      <NDataTable
        v-if="scanAddDisplayed.length > 0"
        :columns="scanAddColumns"
        :data="scanAddDisplayed"
        :max-height="320"
        virtual-scroll
        size="small"
        striped
      />
      <div v-else-if="!scanAddScanning" style="text-align: center; padding: 40px; color: #999">
        {{ scanAddTotal > 0 ? '已全部过滤' : '暂无待翻译字段' }}
      </div>
      <div style="margin-top: 12px; display: flex; align-items: center; gap: 12px">
        <label style="white-space: nowrap; font-weight: 600">AI 代理</label>
        <NSelect
          v-model:value="scanAddProxyName"
          :options="scanAddProxyOptions"
          placeholder="选择 AI 代理后批量生成 key"
          filterable
          style="flex: 1"
        />
      </div>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="scanAddVisible = false">关闭</NButton>
          <NButton type="primary" :loading="scanAddLoading" @click="handleScanAdd">
            {{ scanAddLoading ? '处理中...' : '批量处理' }}
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