<template>
  <div
    class="query-bar"
    bg="#fafafc"
    min-h-60
    flex
    items-start
    justify-between
    b-1
    rounded-8
    p-15
    bc-ccc
    dark:bg-black
  >
    <n-space class="query-bar__actions" wrap :size="[35, 15]">
      <slot />
      <div class="query-bar__btns">
        <n-button secondary type="primary" @click="emit('reset')">重置</n-button>
        <n-button ml-20 type="primary" @click="emit('search')">搜索</n-button>
      </div>
    </n-space>
  </div>
</template>

<script setup>
const emit = defineEmits(['search', 'reset'])
</script>

<style scoped>
@media (max-width: 767px) {
  .query-bar {
    padding: 10px;
  }
  .query-bar__actions {
    width: 100%;
  }
  .query-bar__btns {
    width: 100%;
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
}
</style>
