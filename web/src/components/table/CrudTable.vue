<template>
  <div v-bind="$attrs">
    <QueryBar v-if="$slots.queryBar" mb-30 @search="handleSearch" @reset="handleReset">
      <slot name="queryBar" />
    </QueryBar>

    <!-- 桌面端：数据表格（保持不变） -->
    <n-data-table
      v-if="!isMobile"
      :remote="remote"
      :loading="loading"
      :columns="columns"
      :data="tableData"
      :scroll-x="scrollX"
      :row-key="(row) => row[rowKey]"
      :pagination="isPagination ? pagination : false"
      @update:checked-row-keys="onChecked"
      @update:page="onPageChange"
    />

    <!-- 移动端：卡片视图 -->
    <div v-else class="mobile-card-list">
      <n-spin :show="loading">
        <template v-if="tableData.length === 0 && !loading">
          <n-empty description="暂无数据" />
        </template>
        <template v-else-if="tableData.length > 0">
          <n-card
            v-for="row in tableData"
            :key="row[rowKey]"
            class="mobile-card"
            size="small"
            :bordered="true"
          >
            <div v-for="col in mobileColumns" :key="col.key || col.title" class="mobile-card-item">
              <span class="mobile-card-label">{{ col.title }}</span>
              <span class="mobile-card-value">
                <VNodeRenderer v-if="typeof col.render === 'function'" :nodes="col.render(row)" />
                <span v-else>{{ getCellText(row, col.key) }}</span>
              </span>
            </div>

            <!-- 操作列置于卡片底部 -->
            <div v-if="actionColumn" class="mobile-card-actions">
              <VNodeRenderer :nodes="actionColumn.render(row)" />
            </div>
          </n-card>
        </template>
      </n-spin>

      <!-- 移动端分页 -->
      <div v-if="isPagination && tableData.length > 0" class="mobile-pagination">
        <n-pagination
          :page="pagination.page"
          :page-size="pagination.page_size"
          :item-count="pagination.itemCount"
          :page-sizes="pagination.pageSizes"
          :show-size-picker="false"
          :prefix="pagination.prefix"
          @update:page="(p) => { pagination.page = p; onPageChange(p); }"
          @update:page-size="(s) => { pagination.page_size = s; pagination.page = 1; handleQuery(); }"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, Fragment } from 'vue'
import { useBreakpoints } from '@vueuse/core'

// ── VNode 渲染辅助组件 ──
// Naive UI 表格列定义的 render(row) 返回 VNode 或 VNode[]，
// 在模板中无法直接渲染，通过此组件桥接。
const VNodeRenderer = defineComponent({
  props: {
    nodes: { type: [Object, Array, String, Number, Boolean], default: null },
  },
  setup(props) {
    return () => {
      const v = props.nodes
      if (v == null || v === '') return h('span', '-')
      if (Array.isArray(v)) return h(Fragment, v)
      if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return h('span', String(v))
      return v
    }
  },
})

// ── 嵌套属性取值 ──
// 处理列 key 中的点路径，如 "dept.name"
function getNestedValue(obj, path) {
  if (obj == null || !path) return null
  const keys = String(path).split('.')
  let value = obj
  for (const k of keys) {
    if (value == null || typeof value !== 'object') return null
    value = value[k]
  }
  return value
}

function getCellText(row, key) {
  const val = getNestedValue(row, key)
  if (val === null || val === undefined) return '-'
  return String(val)
}

// ── 移动端检测 ──
const breakpoints = reactive(useBreakpoints({ sm: 768 }))
const isMobile = breakpoints.smaller('sm')

// ── Props ──
const props = defineProps({
  remote: { type: Boolean, default: true },
  isPagination: { type: Boolean, default: true },
  scrollX: { type: Number, default: 450 },
  rowKey: { type: String, default: 'id' },
  columns: { type: Array, required: true },
  queryItems: { type: Object, default: () => ({}) },
  extraParams: { type: Object, default: () => ({}) },
  getData: { type: Function, required: true },
})

const emit = defineEmits(['update:queryItems', 'onChecked', 'onDataChange'])

// ── 计算列 ──
// 移动端展示列：排除 selection 和 actions 列
const mobileColumns = computed(() =>
  props.columns.filter(
    (col) => col.type !== 'selection' && col.key !== 'actions'
  )
)

// 操作列（key === 'actions'）
const actionColumn = computed(() =>
  props.columns.find((col) => col.key === 'actions')
)

// ── 数据 & 分页（同原实现） ──
const loading = ref(false)
const initQuery = { ...props.queryItems }
const tableData = ref([])
const pagination = reactive({
  page: 1,
  page_size: 10,
  pageSizes: [10, 20, 50, 100],
  showSizePicker: true,
  prefix({ itemCount }) {
    return `共 ${itemCount} 条`
  },
  onChange: (page) => {
    pagination.page = page
  },
  onUpdatePageSize: (pageSize) => {
    pagination.page_size = pageSize
    pagination.page = 1
    handleQuery()
  },
})

async function handleQuery() {
  try {
    loading.value = true
    let paginationParams = {}
    if (props.isPagination && props.remote) {
      paginationParams = { page: pagination.page, page_size: pagination.page_size }
    }
    const { data, total } = await props.getData({
      ...props.queryItems,
      ...props.extraParams,
      ...paginationParams,
    })
    tableData.value = data
    pagination.itemCount = total || 0
  } catch {
    tableData.value = []
    pagination.itemCount = 0
  } finally {
    emit('onDataChange', tableData.value)
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  handleQuery()
}

async function handleReset() {
  const queryItems = { ...props.queryItems }
  for (const key in queryItems) {
    queryItems[key] = null
  }
  emit('update:queryItems', { ...queryItems, ...initQuery })
  await nextTick()
  pagination.page = 1
  handleQuery()
}

function onPageChange(currentPage) {
  pagination.page = currentPage
  if (props.remote) {
    handleQuery()
  }
}

function onChecked(rowKeys) {
  if (props.columns.some((item) => item.type === 'selection')) {
    emit('onChecked', rowKeys)
  }
}

defineExpose({
  handleSearch,
  handleReset,
  tableData,
})
</script>

<style scoped>
/* ========== 移动端卡片视图 ========== */
.mobile-card-list {
  padding-bottom: 12px;
}

.mobile-card {
  margin-bottom: 10px;
}

.mobile-card :deep(.n-card__content) {
  padding: 12px 14px;
}

.mobile-card-item {
  display: flex;
  align-items: flex-start;
  padding: 6px 0;
  border-bottom: 1px dashed #eee;
}

.mobile-card-item:last-of-type {
  border-bottom: none;
}

.mobile-card-label {
  flex-shrink: 0;
  width: 72px;
  font-size: 13px;
  color: #999;
  line-height: 1.6;
  padding-right: 8px;
}

.mobile-card-value {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  color: #333;
  line-height: 1.6;
  word-break: break-all;
}

.mobile-card-actions {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

/* 移动端分页 */
.mobile-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: center;
}

/* 暗色模式适配 */
:deep(.dark) .mobile-card-item {
  border-bottom-color: #333;
}
:deep(.dark) .mobile-card-actions {
  border-top-color: #333;
}
:deep(.dark) .mobile-card-label {
  color: #888;
}
:deep(.dark) .mobile-card-value {
  color: #ddd;
}
</style>
