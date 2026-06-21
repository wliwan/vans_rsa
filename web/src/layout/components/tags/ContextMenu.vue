<template>
  <n-dropdown
    :show="show"
    :options="options"
    :x="x"
    :y="y"
    placement="bottom-start"
    @clickoutside="handleHideDropdown"
    @select="handleSelect"
  />
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { useTagsStore, useAppStore } from '@/store'
import { renderIcon } from '@/utils'


const { t } = useI18n()

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
  currentPath: {
    type: String,
    default: '',
  },
  x: {
    type: Number,
    default: 0,
  },
  y: {
    type: Number,
    default: 0,
  },
})

const emit = defineEmits(['update:show'])

const tagsStore = useTagsStore()
const appStore = useAppStore()

const options = computed(() => [
  {
    label: t('layout.label_cn_64ca9bab'),
    key: 'reload',
    disabled: props.currentPath !== tagsStore.activeTag,
    icon: renderIcon('mdi:refresh', { size: '14px' }),
  },
  {
    label: t('layout.label_cn_b15d9127'),
    key: 'close',
    disabled: tagsStore.tags.length <= 1,
    icon: renderIcon('mdi:close', { size: '14px' }),
  },
  {
    label: t('layout.label_cn_6816da19'),
    key: 'close-other',
    disabled: tagsStore.tags.length <= 1,
    icon: renderIcon('mdi:arrow-expand-horizontal', { size: '14px' }),
  },
  {
    label: t('layout.label_cn_e9290eaa'),
    key: 'close-left',
    disabled: tagsStore.tags.length <= 1 || props.currentPath === tagsStore.tags[0].path,
    icon: renderIcon('mdi:arrow-expand-left', { size: '14px' }),
  },
  {
    label: t('layout.label_cn_649d90ab'),
    key: 'close-right',
    disabled:
      tagsStore.tags.length <= 1 ||
      props.currentPath === tagsStore.tags[tagsStore.tags.length - 1].path,
    icon: renderIcon('mdi:arrow-expand-right', { size: '14px' }),
  },
])

const route = useRoute()
const actionMap = new Map([
  [
    'reload',
    () => {
      if (route.meta?.keepAlive) {
        // 重置keepAlive
        appStore.setAliveKeys(route.name, +new Date())
      }
      appStore.reloadPage()
    },
  ],
  [
    'close',
    () => {
      tagsStore.removeTag(props.currentPath)
    },
  ],
  [
    'close-other',
    () => {
      tagsStore.removeOther(props.currentPath)
    },
  ],
  [
    'close-left',
    () => {
      tagsStore.removeLeft(props.currentPath)
    },
  ],
  [
    'close-right',
    () => {
      tagsStore.removeRight(props.currentPath)
    },
  ],
])

function handleHideDropdown() {
  emit('update:show', false)
}

function handleSelect(key) {
  const actionFn = actionMap.get(key)
  actionFn && actionFn()
  handleHideDropdown()
}
</script>
