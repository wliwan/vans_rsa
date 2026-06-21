<template>
  <div v-if="reloadFlag" class="relative">
    <slot></slot>
    <div v-show="showPlaceholder" class="absolute-lt h-full w-full" :class="placeholderClass">
      <div v-show="loading" class="absolute-center">
        <n-spin :show="true" :size="loadingSize" />
      </div>
      <div v-show="isEmpty" class="absolute-center">
        <div class="relative">
          <icon-custom-no-data :class="iconClass" />
          <p class="absolute-lb w-full text-center" :class="descClass">{{ emptyDesc }}</p>
        </div>
      </div>
      <div v-show="!network" class="absolute-center">
        <div
          class="relative"
          :class="{ 'cursor-pointer': showNetworkReload }"
          @click="handleReload"
        >
          <icon-custom-network-error :class="iconClass" />
          <p class="absolute-lb w-full text-center" :class="descClass">{{ networkErrorDesc }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { ref, computed, nextTick, watch, onUnmounted } from 'vue'


const { t } = useI18n()

defineOptions({ name: 'LoadingEmptyWrapper' })

const NETWORK_ERROR_MSG = t('common.label_cn_cd662c4a')

const props = {
  loading: false,
  empty: false,
  loadingSize: 'medium',
  placeholderClass: 'bg-white dark:bg-dark transition-background-color duration-300 ease-in-out',
  emptyDesc: t('views.tool.vehicle.no_data'),
  iconClass: 'text-320px text-primary',
  descClass: 'text-16px text-#666',
  showNetworkReload: false,
}

// 网络状态
const network = ref(window.navigator.onLine)
const reloadFlag = ref(true)

// 数据是否为空
const isEmpty = computed(() => props.empty && !props.loading && network.value)

const showPlaceholder = computed(() => props.loading || isEmpty.value || !network.value)

const networkErrorDesc = computed(() =>
  props.showNetworkReload ? `${NETWORK_ERROR_MSG}, 点击重试` : NETWORK_ERROR_MSG,
)

function handleReload() {
  if (!props.showNetworkReload) return
  reloadFlag.value = false
  nextTick(() => {
    reloadFlag.value = true
  })
}

const stopHandle = watch(
  () => props.loading,
  (newValue) => {
    // 结束加载判断一下网络状态
    if (!newValue) {
      network.value = window.navigator.onLine
    }
  },
)

onUnmounted(() => {
  stopHandle()
})
</script>

<style scoped></style>
