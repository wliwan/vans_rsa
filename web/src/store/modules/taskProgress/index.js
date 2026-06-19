import { defineStore } from 'pinia'

let _id = 0

export const useTaskProgressStore = defineStore('taskProgress', {
  state() {
    return {
      /** @type {Array<{id:number, title:string, status:'running'|'done'|'error', progress:number, message:string, phase:string, detail:string, removable:boolean, retryHandler:Function|null}>} */
      tasks: [],
      collapsed: false,
    }
  },
  getters: {
    runningTasks(state) {
      return state.tasks.filter(t => t.status === 'running')
    },
    hasRunning(state) {
      return state.tasks.some(t => t.status === 'running')
    },
  },
  actions: {
    upsertTask({ id, title, status, progress, message, phase, detail = '', removable = true, retryHandler = null }) {
      const idx = this.tasks.findIndex(t => t.id === id)
      const task = { id, title, status, progress: progress ?? 0, message: message ?? '', phase: phase ?? '', detail, removable, retryHandler }
      if (idx >= 0) {
        this.tasks[idx] = { ...this.tasks[idx], ...task }
      } else {
        this.tasks.push(task)
      }
    },
    startTask(title, retryHandler = null) {
      const id = ++_id
      this.upsertTask({ id, title, status: 'running', progress: 0, message: '', phase: '', retryHandler })
      return id
    },
    updateProgress(id, { progress, message, phase }) {
      this.upsertTask({ id, status: 'running', progress, message, phase })
    },
    finishTask(id, message = '') {
      this.upsertTask({ id, status: 'done', progress: 100, message, removable: true })
      setTimeout(() => {
        this.removeTask(id)
      }, 5000)
    },
    failTask(id, { message, detail = '' }) {
      this.upsertTask({ id, status: 'error', progress: 0, message, detail, removable: true })
    },
    removeTask(id) {
      this.tasks = this.tasks.filter(t => t.id !== id)
    },
    clearDone() {
      this.tasks = this.tasks.filter(t => t.status === 'running')
    },
    toggleCollapsed() {
      this.collapsed = !this.collapsed
    },
  },
})
