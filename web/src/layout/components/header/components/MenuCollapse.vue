<script setup>
import { useAppStore } from '@/store'
import { useBreakpoints } from '@vueuse/core'

const appStore = useAppStore()

const breakpoints = reactive(useBreakpoints({
  sm: 666,
  md: 991,
}))
const isSmallScreen = computed(() => breakpoints.isSmaller('sm') || breakpoints.between('sm', 'md'))
</script>

<template>
  <!-- 移动端：汉堡菜单图标，控制 drawer 开关 -->
  <n-icon v-if="isSmallScreen" size="22" cursor-pointer @click="appStore.toggleMobileDrawer()">
    <icon-mdi:menu />
  </n-icon>

  <!-- PC 端：折叠/展开侧边栏图标 -->
  <n-icon v-else size="20" cursor-pointer @click="appStore.switchCollapsed">
    <icon-mdi:format-indent-increase v-if="appStore.collapsed" />
    <icon-mdi:format-indent-decrease v-else />
  </n-icon>
</template>
