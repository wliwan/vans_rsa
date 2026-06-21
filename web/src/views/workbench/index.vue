<template>
  <AppPage :show-footer="false">
    <div flex-1>
      <!-- 用户问候 + 统计区 -->
      <n-card rounded-10>
        <div class="greeting-row" flex items-center justify-between>
          <div class="greeting-left" flex items-center>
            <img class="greeting-avatar" rounded-full width="60" :src="userStore.avatar" />
            <div ml-10>
              <p text-20 font-semibold>
                {{ $t('views.workbench.text_hello', { username: userStore.name }) }}
              </p>
              <p mt-5 text-14 op-60>{{ $t('views.workbench.text_welcome') }}</p>
            </div>
          </div>
          <n-space :size="12" :wrap="isMobile" align="center">
            <n-statistic v-for="item in statisticData" :key="item.id" v-bind="item" />
            <!-- 编辑模式开关 -->
            <n-button
              size="small"
              :type="isEditing ? 'warning' : 'default'"
              @click="toggleEdit"
            >
              <template #icon>
                <span v-if="isEditing" class="i-mdi:check" />
                <span v-else class="i-mdi:pencil" />
              </template>
              {{ isEditing ? $t('views.workbench.label_done') : $t('views.workbench.label_edit') }}
            </n-button>
          </n-space>
        </div>
      </n-card>

      <!-- 功能卡片网格 -->
      <n-card
        :title="$t('views.workbench.label_project')"
        size="small"
        :segmented="true"
        mt-15
        rounded-10
      >
        <template v-if="isEditing" #header-extra>
          <n-space align="center">
            <span text-12 op-60>{{ $t('views.workbench.label_columns') }}</span>
            <n-button-group size="tiny">
              <n-button
                v-for="col in [2, 3, 4]"
                :key="col"
                :type="gridCols === col ? 'primary' : 'default'"
                @click="setCols(col)"
              >
                {{ col }}
              </n-button>
            </n-button-group>
          </n-space>
        </template>

        <div
          class="card-grid"
          :style="{ gridTemplateColumns: isMobile ? 'repeat(2, 1fr)' : `repeat(${gridCols}, 1fr)` }"
        >
          <n-card
            v-for="(card, idx) in orderedMenus"
            :key="card.name"
            class="menu-card"
            :class="{ 'card-editing': isEditing, 'card-dragging': draggingIdx === idx }"
            :draggable="isEditing"
            size="small"
            hover:card-shadow
            @click="onCardClick(card)"
            @dragstart="onDragStart($event, idx)"
            @dragover.prevent="onDragOver($event, idx)"
            @dragend="onDragEnd"
            @drop.prevent="onDrop(idx)"
          >
            <!-- 拖拽手柄 (编辑模式) -->
            <div v-if="isEditing" class="drag-handle">
              <span class="i-mdi:drag-vertical" text-18 />
            </div>

            <div class="card-body">
              <div class="card-icon" :style="{ color: cardIconColor(idx) }">
                <TheIcon :icon="card.meta?.icon || 'mdi:application'" size="32" />
              </div>
              <div class="card-info">
                <p class="card-title">{{ card.meta?.title || card.name }}</p>
                <p v-if="card.children?.length" class="card-sub">
                  {{ card.children.length }} {{ $t('views.workbench.label_sub_pages') }}
                </p>
              </div>
            </div>

            <!-- 子菜单预览 -->
            <div v-if="card.children?.length && !isEditing" class="card-children">
              <n-tag
                v-for="child in card.children.slice(0, 4)"
                :key="child.name"
                size="small"
                type="info"
                :bordered="false"
              >
                {{ child.meta?.title || child.name }}
              </n-tag>
              <n-tag v-if="card.children.length > 4" size="small" :bordered="false">
                +{{ card.children.length - 4 }}
              </n-tag>
            </div>
          </n-card>

          <!-- 空状态 -->
          <div v-if="!orderedMenus.length" class="empty-state">
            <span class="i-mdi:inbox-outline" text-48 op-30 />
            <p mt-10 op-40>{{ $t('views.workbench.text_no_pages') }}</p>
          </div>
        </div>
      </n-card>
    </div>
  </AppPage>
</template>

<script setup>
import { useUserStore, usePermissionStore } from '@/store'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import TheIcon from '@/components/icon/TheIcon.vue'


const { t } = useI18n({ useScope: 'global' })
const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()

// ── 响应式断点 ──
const BREAKPOINT = 768
const isMobile = ref(false)
function onResize() {
  isMobile.value = window.innerWidth < BREAKPOINT
}
onMounted(() => {
  onResize()
  window.addEventListener('resize', onResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
})

// ── 卡片颜色 ──
const cardColors = ['#0185F5', '#339DF7', '#006AC4', '#4098FC', '#1060C9', '#5BA0FA']
function cardIconColor(idx) {
  return cardColors[idx % cardColors.length]
}

// ── 菜单数据 ──
const allMenus = computed(() => {
  return permissionStore.menus
    .filter((m) => m.path !== '/profile' && m.path !== '/error-page')
    .sort((a, b) => (a.meta?.order ?? 99) - (b.meta?.order ?? 99))
})

// ── 布局持久化 key ──
const STORAGE_KEY = 'workbench_layout'
function loadLayout() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return null
}
function saveLayout(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
}

// ── 列数 ──
const savedLayout = loadLayout()
const gridCols = ref(savedLayout?.cols || 3)
function setCols(n) {
  gridCols.value = n
  persistLayout()
}

// ── 菜单排序 ──
const menuOrder = ref(savedLayout?.order || [])
const orderedMenus = computed(() => {
  const order = menuOrder.value
  const menus = [...allMenus.value]
  if (!order.length) return menus
  // 存在 order 则按 order 排序，缺失的追加在末尾
  menus.sort((a, b) => {
    const ai = order.indexOf(a.path)
    const bi = order.indexOf(b.path)
    if (ai === -1 && bi === -1) return 0
    if (ai === -1) return 1
    if (bi === -1) return -1
    return ai - bi
  })
  return menus
})

function persistLayout() {
  const paths = orderedMenus.value.map((m) => m.path)
  saveLayout({ cols: gridCols.value, order: paths })
}

// 初始化：如果 localStorage 无数据，用当前菜单顺序初始化
watch(allMenus, (menus) => {
  if (!menuOrder.value.length && menus.length) {
    menuOrder.value = menus.map((m) => m.path)
  }
}, { immediate: true })

// ── 编辑模式 ──
const isEditing = ref(false)
function toggleEdit() {
  if (isEditing.value) {
    // 保存
    persistLayout()
  }
  isEditing.value = !isEditing.value
}

// ── 拖拽 ──
const draggingIdx = ref(-1)
function onDragStart(e, idx) {
  draggingIdx.value = idx
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', String(idx))
}
function onDragOver(e, idx) {
  e.dataTransfer.dropEffect = 'move'
}
function onDrop(targetIdx) {
  const srcIdx = draggingIdx.value
  if (srcIdx === targetIdx || srcIdx < 0) return
  const newOrder = [...orderedMenus.value.map((m) => m.path)]
  const [moved] = newOrder.splice(srcIdx, 1)
  newOrder.splice(targetIdx, 0, moved)
  menuOrder.value = newOrder
}
function onDragEnd() {
  draggingIdx.value = -1
}

// ── 卡片点击 ──
function onCardClick(card) {
  if (isEditing.value) return
  const route = card.children?.[0]?.path
    ? `${card.path}/${card.children[0].path}`.replace(/\/+/g, '/')
    : card.path
  router.push(route)
}

// ── 统计数据 ──
const statisticData = computed(() => [
  {
    id: 0,
    label: t('views.workbench.label_number_of_items'),
    value: String(allMenus.value.length),
  },
  {
    id: 1,
    label: t('views.workbench.label_upcoming'),
    value: '4/16',
  },
  {
    id: 2,
    label: t('views.workbench.label_information'),
    value: '12',
  },
])
</script>

<style scoped>
.card-grid {
  display: grid;
  gap: 12px;
}

.menu-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  position: relative;
  overflow: hidden;
}
.menu-card:hover {
  transform: translateY(-2px);
}
.menu-card.card-editing {
  cursor: grab;
  border: 2px dashed var(--primary-color-hover);
}
.menu-card.card-editing:active {
  cursor: grabbing;
}
.menu-card.card-dragging {
  opacity: 0.4;
  transform: scale(0.95);
}

.drag-handle {
  position: absolute;
  top: 6px;
  right: 6px;
  color: var(--primary-color);
  cursor: grab;
  z-index: 2;
}

.card-body {
  display: flex;
  align-items: center;
  gap: 12px;
}
.card-icon {
  flex-shrink: 0;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 10px;
}
.card-icon::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 10px;
  background: currentColor;
  opacity: 0.12;
}
.card-icon :deep(svg) {
  position: relative;
  z-index: 1;
}
.card-info {
  flex: 1;
  min-width: 0;
}
.card-title {
  font-size: 15px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-sub {
  font-size: 12px;
  opacity: 0.5;
  margin-top: 2px;
}

.card-children {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.empty-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
}

/* ========== 移动端适配 ========== */
@media (max-width: 767px) {
  .greeting-row {
    flex-direction: column;
    align-items: flex-start !important;
    gap: 12px;
  }
  .greeting-left {
    width: 100%;
  }
  .greeting-avatar {
    width: 44px !important;
    height: 44px !important;
  }
  .greeting-row :deep(.n-space) {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
  .card-grid {
    gap: 8px;
  }
  .card-body {
    gap: 8px;
  }
  .card-icon {
    width: 36px;
    height: 36px;
    border-radius: 8px;
  }
  .card-title {
    font-size: 13px;
  }
  .card-sub {
    font-size: 11px;
  }
}
</style>