<template>
  <router-link h-60 f-c-c to="/">
    <icon-custom-logo color-primary style="font-size: 15rem"></icon-custom-logo>
    <h2
      v-show="!appStore.collapsed"
      ml-2
      mr-8
      max-w-150
      flex-shrink-0
      font-bold
      color-primary
      style="font-size: 6rem"
    >
      {{ title }}
    </h2>
  </router-link>
</template>

<script setup>
import { useAppStore } from '@/store'
const title = import.meta.env.VITE_TITLE

const appStore = useAppStore()
</script>
