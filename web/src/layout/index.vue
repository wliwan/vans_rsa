<template>
  <!-- ============ PC 端布局 ============ -->
  <n-layout v-if="!isSmallScreen" has-sider wh-full>
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="220"
      :native-scrollbar="false"
      :collapsed="appStore.collapsed"
    >
      <SideBar />
    </n-layout-sider>

    <article flex-col flex-1 overflow-hidden>
      <header
        class="flex items-center border-b bg-white px-15 bc-eee"
        dark="bg-dark border-0"
        :style="`height: ${header.height}px`"
      >
        <AppHeader />
      </header>
      <section v-if="tags.visible" hidden border-b bc-eee sm:block dark:border-0>
        <AppTags :style="{ height: `${tags.height}px` }" />
      </section>
      <section flex-1 overflow-hidden bg-hex-f5f6fb dark:bg-hex-101014>
        <AppMain />
      </section>
    </article>
  </n-layout>

  <!-- ============ 移动端布局 ============ -->
  <n-layout v-else wh-full>
    <!-- 移动端抽屉式侧边栏 -->
    <n-drawer
      v-model:show="appStore.mobileDrawerVisible"
      :width="260"
      placement="left"
      :mask-closable="true"
      :block-scroll="true"
      :show-mask="true"
      :trap-focus="false"
      :z-index="1001"
    >
      <n-drawer-content :native-scrollbar="false" body-content-style="padding:0">
        <template #header>
          <SideLogo />
        </template>
        <SideMenu />
      </n-drawer-content>
    </n-drawer>

    <article flex-col flex-1 overflow-hidden>
      <header
        class="flex items-center border-b bg-white px-10 bc-eee"
        dark="bg-dark border-0"
        :style="`height: ${header.height}px`"
      >
        <AppHeader />
      </header>
      <section flex-1 overflow-hidden bg-hex-f5f6fb dark:bg-hex-101014>
        <AppMain />
      </section>
    </article>
  </n-layout>

  <!-- 全局任务进度面板（跨页面保持） -->
  <TaskProgressPanel />
</template>

<script setup>
import AppHeader from './components/header/index.vue'
import TaskProgressPanel from '@/components/common/TaskProgressPanel.vue'
import SideBar from './components/sidebar/index.vue'
import SideLogo from './components/sidebar/components/SideLogo.vue'
import SideMenu from './components/sidebar/components/SideMenu.vue'
import AppMain from './components/AppMain.vue'
import AppTags from './components/tags/index.vue'
import { useAppStore } from '@/store'
import { header, tags } from '~/settings'

import { useBreakpoints } from '@vueuse/core'

const appStore = useAppStore()
const breakpointsEnum = {
  xl: 1600,
  lg: 1199,
  md: 991,
  sm: 666,
  xs: 575,
}
const breakpoints = reactive(useBreakpoints(breakpointsEnum))
const isMobile = breakpoints.smaller('sm')
const isPad = breakpoints.between('sm', 'md')
const isSmallScreen = computed(() => isMobile.value || isPad.value)
const isPC = breakpoints.greater('md')

watchEffect(() => {
  if (isSmallScreen.value) {
    // Mobile / Pad：侧边栏默认完全隐藏，由按钮触发 drawer
    appStore.setFullScreen(false)
    appStore.setMobileDrawer(false)
  }

  if (isPC.value) {
    // PC：恢复正常侧边栏
    appStore.setCollapsed(false)
    appStore.setFullScreen(true)
    appStore.setMobileDrawer(false)
  }
})
</script>
