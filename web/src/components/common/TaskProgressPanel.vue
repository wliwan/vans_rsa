<script setup>
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'
import { NButton, NProgress, NScrollbar, NTag } from 'naive-ui'
import { useTaskProgressStore } from '@/store/modules/taskProgress'
import { storeToRefs } from 'pinia'
import TheIcon from '@/components/icon/TheIcon.vue'

const { t } = useI18n()

const store = useTaskProgressStore()
const { tasks, collapsed } = storeToRefs(store)

const showPanel = computed(() => tasks.value.length > 0 && !collapsed.value)

const statusConfig = {
  running: {
    color: '#3b82f6',
    bgColor: '#eff6ff',
    icon: 'material-symbols:progress-activity',
    label: '进行中',
  },
  done: {
    color: '#10b981',
    bgColor: '#ecfdf5',
    icon: 'material-symbols:check-circle',
    label: '已完成',
  },
  error: {
    color: '#ef4444',
    bgColor: '#fef2f2',
    icon: 'material-symbols:error',
    label: t('views.network.roadNetwork.statusMap.FAILED'),
  },
}

function onRetry(task) {
  store.removeTask(task.id)
  if (typeof task.retryHandler === 'function') {
    task.retryHandler()
  }
}
</script>

<template>
  <Teleport to="body">
    <!-- 展开面板 -->
    <Transition name="panel-slide">
      <div v-if="showPanel" class="task-panel-wrapper">
        <div class="task-panel">
          <!-- 头部 -->
          <div class="panel-header">
            <div class="panel-header-left">
              <div class="panel-icon-wrap">
                <TheIcon icon="material-symbols:list-alt" :size="18" color="#fff" />
              </div>
              <span class="panel-title">后台任务</span>
              <span class="panel-badge">{{ tasks.length }}</span>
            </div>
            <div class="panel-header-right">
              <NButton
                size="tiny"
                quaternary
                class="header-btn"
                @click="store.clearDone()"
              >
                清除已完成
              </NButton>
              <NButton
                size="tiny"
                quaternary
                class="header-btn"
                @click="store.toggleCollapsed()"
              >
                <TheIcon icon="material-symbols:chevron-right" :size="16" class="collapse-icon" />
              </NButton>
            </div>
          </div>

          <!-- 任务列表 -->
          <NScrollbar class="task-scroll" :style="{ maxHeight: '380px' }">
            <TransitionGroup name="task-list" tag="div" class="task-list">
              <div
                v-for="task in tasks"
                :key="task.id"
                class="task-item"
              >
                <!-- 左侧状态图标 -->
                <div
                  class="task-indicator"
                  :class="[`indicator-${task.status}`]"
                >
                  <TheIcon
                    v-if="task.status === 'running'"
                    icon="material-symbols:progress-activity"
                    :size="16"
                    :color="statusConfig.running.color"
                    class="spin-icon"
                  />
                  <TheIcon
                    v-else-if="task.status === 'done'"
                    icon="material-symbols:check-circle"
                    :size="16"
                    :color="statusConfig.done.color"
                  />
                  <TheIcon
                    v-else-if="task.status === 'error'"
                    icon="material-symbols:error"
                    :size="16"
                    :color="statusConfig.error.color"
                  />
                </div>

                <!-- 任务内容 -->
                <div class="task-content">
                  <div class="task-head">
                    <span class="task-title">{{ task.title }}</span>
                    <NTag
                      :color="{
                        color: statusConfig[task.status].color,
                        textColor: '#fff',
                      }"
                      size="tiny"
                      :bordered="false"
                    >
                      {{ statusConfig[task.status].label || task.status }}
                    </NTag>
                  </div>

                  <!-- 进度条 -->
                  <div class="task-progress-wrap">
                    <NProgress
                      :percentage="task.progress"
                      :status="task.status === 'error' ? 'error' : task.status === 'done' ? 'success' : 'default'"
                      :height="6"
                      :border-radius="3"
                      :show-indicator="false"
                      :color="task.status === 'error' ? '#ef4444' : task.status === 'done' ? '#10b981' : '#3b82f6'"
                      :rail-color="task.status === 'error' ? '#fee2e2' : task.status === 'done' ? '#d1fae5' : '#dbeafe'"
                    />
                    <span
                      v-if="task.status !== 'done'"
                      class="task-progress-text"
                      :style="{ color: statusConfig[task.status].color }"
                    >
                      {{ task.progress }}%
                    </span>
                  </div>

                  <!-- 消息 -->
                  <span v-if="task.message" class="task-msg">{{ task.message }}</span>

                  <!-- 错误详情 -->
                  <div v-if="task.status === 'error' && task.detail" class="task-error-detail">
                    <TheIcon icon="material-symbols:info-outline" :size="12" class="error-icon" />
                    <span class="error-text" :title="task.detail">{{ task.detail }}</span>
                  </div>
                </div>

                <!-- 操作按钮 -->
                <div class="task-actions">
                  <NButton
                    v-if="task.status === 'error' && task.retryHandler"
                    size="tiny"
                    type="warning"
                    quaternary
                    class="task-action-btn"
                    @click="onRetry(task)"
                  >
                    重试
                  </NButton>
                  <NButton
                    v-if="task.status !== 'running' && task.removable"
                    size="tiny"
                    quaternary
                    class="task-action-btn task-close-btn"
                    @click="store.removeTask(task.id)"
                  >
                    <TheIcon icon="material-symbols:close" :size="14" />
                  </NButton>
                </div>
              </div>

              <!-- 空状态 -->
              <div v-if="tasks.length === 0" key="empty" class="empty-state">
                <TheIcon icon="material-symbols:check-circle-outline" :size="32" color="#d1d5db" />
                <span>所有任务已完成</span>
              </div>
            </TransitionGroup>
          </NScrollbar>
        </div>
      </div>
    </Transition>

    <!-- 最小化浮动按钮 -->
    <Transition name="badge-pop">
      <div
        v-if="collapsed && store.hasRunning"
        class="task-mini-float"
        @click="store.toggleCollapsed()"
      >
        <div class="mini-pulse-ring" />
        <div class="mini-inner">
          <TheIcon icon="material-symbols:progress-activity" :size="18" color="#fff" class="mini-spin" />
          <span class="mini-count">{{ store.runningTasks.length }}</span>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ==================== Panel Wrapper ==================== */
.task-panel-wrapper {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 2000;
}

/* ==================== Panel Card ==================== */
.task-panel {
  width: 420px;
  border-radius: 14px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.03),
    0 4px 16px rgba(0, 0, 0, 0.06),
    0 8px 32px rgba(0, 0, 0, 0.1),
    0 20px 48px rgba(0, 0, 0, 0.04);
}

/* ==================== Header ==================== */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.5);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  backdrop-filter: blur(8px);
}

.panel-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.panel-icon-wrap {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: linear-gradient(135deg, #3b82f6, #6366f1);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  letter-spacing: -0.01em;
}

.panel-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
}

.panel-header-right {
  display: flex;
  align-items: center;
  gap: 2px;
}

.header-btn {
  color: #64748b !important;
  font-size: 12px;
  transition: color 0.2s;
}
.header-btn:hover {
  color: #3b82f6 !important;
}
.collapse-icon {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

/* ==================== Task Scroll Area ==================== */
.task-scroll {
  padding: 6px 8px;
}
.task-scroll :deep(.n-scrollbar-content) {
  padding: 0 8px;
}
.task-scroll :deep(.n-scrollbar-rail__bar) {
  width: 4px !important;
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.1) !important;
  transition: background 0.2s;
}

/* ==================== Task List ==================== */
.task-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* ==================== Task Item ==================== */
.task-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  transition: background 0.15s ease;
  position: relative;
}
.task-item:hover {
  background: rgba(0, 0, 0, 0.02);
}

/* ==================== Status Indicator ==================== */
.task-indicator {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
}

.indicator-running {
  background: rgba(59, 130, 246, 0.08);
}
.indicator-done {
  background: rgba(16, 185, 129, 0.08);
}
.indicator-error {
  background: rgba(239, 68, 68, 0.08);
}

.spin-icon {
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ==================== Task Content ==================== */
.task-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.task-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.3;
}

/* ==================== Progress ==================== */
.task-progress-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-progress-wrap :deep(.n-progress) {
  flex: 1;
}

.task-progress-text {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  min-width: 28px;
  text-align: right;
}

/* ==================== Message ==================== */
.task-msg {
  font-size: 12px;
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

/* ==================== Error Detail ==================== */
.task-error-detail {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  padding: 6px 8px;
  border-radius: 6px;
  background: #fef2f2;
  border: 1px solid #fee2e2;
}

.error-icon {
  flex-shrink: 0;
  margin-top: 1px;
  color: #ef4444;
}

.error-text {
  font-size: 11px;
  color: #dc2626;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

/* ==================== Task Actions ==================== */
.task-actions {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s;
}
.task-item:hover .task-actions {
  opacity: 1;
}

.task-action-btn {
  color: #94a3b8 !important;
  padding: 2px 4px !important;
  min-width: 24px !important;
  height: 24px !important;
}
.task-action-btn:hover {
  color: #3b82f6 !important;
}
.task-close-btn:hover {
  color: #ef4444 !important;
}

/* ==================== Empty State ==================== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px 16px;
  color: #94a3b8;
  font-size: 13px;
}

/* ==================== Minimized Float ==================== */
.task-mini-float {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 2000;
  width: 48px;
  height: 48px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mini-pulse-ring {
  position: absolute;
  inset: -6px;
  border-radius: 50%;
  border: 2px solid rgba(59, 130, 246, 0.3);
  animation: pulse-ring 2s ease-out infinite;
}

@keyframes pulse-ring {
  0% {
    transform: scale(0.85);
    opacity: 0.8;
  }
  100% {
    transform: scale(1.15);
    opacity: 0;
  }
}

.mini-inner {
  position: relative;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #6366f1);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    0 4px 12px rgba(59, 130, 246, 0.4),
    0 0 0 4px rgba(59, 130, 246, 0.1);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.mini-inner:hover {
  transform: scale(1.08);
  box-shadow:
    0 6px 20px rgba(59, 130, 246, 0.5),
    0 0 0 8px rgba(59, 130, 246, 0.12);
}

.mini-spin {
  animation: spin 1.5s linear infinite;
}

.mini-count {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 18px;
  height: 18px;
  border-radius: 9px;
  background: #ef4444;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
  box-shadow: 0 2px 4px rgba(239, 68, 68, 0.4);
  line-height: 1;
}

/* ==================== Transitions ==================== */
/* Panel slide */
.panel-slide-enter-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.panel-slide-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 1, 1);
}
.panel-slide-enter-from {
  opacity: 0;
  transform: translateY(16px) scale(0.96);
}
.panel-slide-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.98);
}

/* Badge pop */
.badge-pop-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.badge-pop-leave-active {
  transition: all 0.2s ease-in;
}
.badge-pop-enter-from {
  opacity: 0;
  transform: scale(0);
}
.badge-pop-leave-to {
  opacity: 0;
  transform: scale(0.5);
}

/* Task items */
.task-list-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.task-list-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 1, 1);
  position: absolute;
}
.task-list-enter-from {
  opacity: 0;
  transform: translateX(16px);
}
.task-list-leave-to {
  opacity: 0;
  transform: translateX(-24px);
}
.task-list-move {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

/* ==================== Reduced Motion ==================== */
@media (prefers-reduced-motion: reduce) {
  .spin-icon,
  .mini-spin {
    animation: none;
  }
  .mini-pulse-ring {
    animation: none;
    opacity: 0;
  }
  .panel-slide-enter-active,
  .panel-slide-leave-active,
  .badge-pop-enter-active,
  .badge-pop-leave-active,
  .task-list-enter-active,
  .task-list-leave-active,
  .task-list-move {
    transition: none;
  }
  .panel-slide-enter-from,
  .panel-slide-leave-to,
  .badge-pop-enter-from,
  .badge-pop-leave-to,
  .task-list-enter-from,
  .task-list-leave-to {
    opacity: 0;
    transform: none;
  }
}

/* ==================== Dark Mode ==================== */
:root.dark .task-panel {
  background: rgba(15, 23, 42, 0.92);
  border-color: rgba(255, 255, 255, 0.08);
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.03),
    0 8px 32px rgba(0, 0, 0, 0.4),
    0 2px 8px rgba(0, 0, 0, 0.3);
}
:root.dark .panel-header {
  background: rgba(15, 23, 42, 0.5);
  border-bottom-color: rgba(255, 255, 255, 0.06);
}
:root.dark .panel-title {
  color: #e2e8f0;
}
:root.dark .panel-badge {
  background: rgba(255, 255, 255, 0.08);
  color: #94a3b8;
}
:root.dark .task-title {
  color: #e2e8f0;
}
:root.dark .task-item:hover {
  background: rgba(255, 255, 255, 0.03);
}
:root.dark .task-msg {
  color: #64748b;
}
:root.dark .indicator-running {
  background: rgba(59, 130, 246, 0.15);
}
:root.dark .indicator-done {
  background: rgba(16, 185, 129, 0.15);
}
:root.dark .indicator-error {
  background: rgba(239, 68, 68, 0.15);
}
:root.dark .task-error-detail {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.2);
}
:root.dark .error-text {
  color: #fca5a5;
}
:root.dark .header-btn {
  color: #94a3b8 !important;
}
:root.dark .header-btn:hover {
  color: #60a5fa !important;
}
:root.dark .empty-state {
  color: #475569;
}
:root.dark .task-scroll :deep(.n-scrollbar-rail__bar) {
  background: rgba(255, 255, 255, 0.12) !important;
}
</style>
