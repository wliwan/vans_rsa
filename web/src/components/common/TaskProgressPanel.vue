<script setup>
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'
import { NButton, NCard, NProgress, NSpace, NTag, NTooltip } from 'naive-ui'
import { useTaskProgressStore } from '@/store/modules/taskProgress'
import { storeToRefs } from 'pinia'


const { t } = useI18n()

const store = useTaskProgressStore()
const { tasks, collapsed } = storeToRefs(store)

const showPanel = computed(() => tasks.value.length > 0 && !collapsed.value)

const statusColors = { running: '#2080f0', done: '#18a058', error: '#d03050' }
const statusLabels = { running: '进行中', done: '已完成', error: t('views.network.roadNetwork.statusMap.FAILED') }

function onRetry(task) {
  store.removeTask(task.id)
  if (typeof task.retryHandler === 'function') {
    task.retryHandler()
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="showPanel" class="task-panel-container">
      <NCard size="small" :bordered="true" class="task-panel">
        <template #header>
          <div class="panel-header">
            <span class="panel-title">后台任务 ({{ tasks.length }})</span>
            <NSpace :size="4">
              <NButton size="tiny" quaternary @click="store.clearDone()">清除已完成</NButton>
              <NButton size="tiny" quaternary @click="store.toggleCollapsed()">收起</NButton>
            </NSpace>
          </div>
        </template>

        <div class="task-list">
          <div v-for="task in tasks" :key="task.id" class="task-item">
            <div class="task-head">
              <span class="task-title">{{ task.title }}</span>
              <NTag :color="{ color: statusColors[task.status], textColor: '#fff' }" size="tiny">
                {{ statusLabels[task.status] || task.status }}
              </NTag>
              <NButton
                v-if="task.status === 'error' && task.retryHandler"
                size="tiny"
                type="warning"
                quaternary
                @click="onRetry(task)"
              >重试</NButton>
              <NButton
                v-if="task.status !== 'running' && task.removable"
                size="tiny"
                quaternary
                type="error"
                @click="store.removeTask(task.id)"
              >✕</NButton>
            </div>
            <div class="task-body">
              <NProgress
                :percentage="task.progress"
                :status="task.status === 'error' ? 'error' : task.status === 'done' ? 'success' : 'default'"
                :height="6"
                :border-radius="3"
                :show-indicator="false"
              />
              <span class="task-msg">{{ task.message }}</span>
              <!-- 错误详情（截断 + tooltip） -->
              <NTooltip v-if="task.status === 'error' && task.detail" trigger="hover" placement="top" :width="360">
                <template #trigger>
                  <span class="task-error-detail">{{ task.detail }}</span>
                </template>
                {{ task.detail }}
              </NTooltip>
            </div>
          </div>
        </div>
      </NCard>
    </div>

    <!-- 最小化按钮 -->
    <div
      v-if="collapsed && store.hasRunning"
      class="task-mini-badge"
      @click="store.toggleCollapsed()"
    >
      <span class="mini-count">{{ store.runningTasks.length }}</span>
    </div>
  </Teleport>
</template>

<style scoped>
.task-panel-container {
  position: fixed;
  bottom: 16px;
  right: 16px;
  z-index: 2000;
}
.task-panel {
  width: 400px;
  max-height: 520px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.18);
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-title { font-weight: 600; font-size: 14px; }
.task-list { display: flex; flex-direction: column; gap: 10px; }
.task-item {
  padding-bottom: 10px;
  border-bottom: 1px solid #f0f0f0;
}
.task-item:last-child { border-bottom: none; padding-bottom: 0; }
.task-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.task-title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-body { display: flex; flex-direction: column; gap: 3px; }
.task-msg {
  font-size: 12px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-error-detail {
  font-size: 11px;
  color: #d03050;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}
.task-mini-badge {
  position: fixed;
  bottom: 16px;
  right: 16px;
  z-index: 2000;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #2080f0;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 10px rgba(32, 128, 240, 0.4);
  transition: transform 0.15s;
}
.task-mini-badge:hover { transform: scale(1.1); }
.mini-count { font-size: 16px; font-weight: 600; }
</style>
