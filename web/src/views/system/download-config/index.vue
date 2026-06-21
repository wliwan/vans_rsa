<script setup>
import { useI18n } from 'vue-i18n'
import i18n from '~/i18n'
import { onMounted, ref } from 'vue'
import {



  NButton, NCard, NForm, NFormItem, NInput, NInputNumber, NPopconfirm,
  NSpace, NTag, NSlider, NSwitch, NDivider, useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

const { t } = useI18n()

defineOptions({ name: i18n.global.t('views.system.title_cn_6da31e6c') })

const message = useMessage()

const config = ref({})
const originalConfig = ref({})
const configLoading = ref(false)
const saveLoading = ref(false)
const proxyTesting = ref(false)
const proxyTestResult = ref(null)

onMounted(loadConfig)

async function loadConfig() {
  configLoading.value = true
  try {
    const res = await api.getDownloadConfig()
    const raw = res.data || {}
    const parsed = {}
    for (const [k, v] of Object.entries(raw)) {
      parsed[k] = v.value
    }
    config.value = parsed
    originalConfig.value = JSON.parse(JSON.stringify(parsed))
  } catch (_) {} finally {
    configLoading.value = false
  }
}

async function onSave() {
  saveLoading.value = true
  try {
    const updates = {}
    for (const [k, v] of Object.entries(config.value)) {
      if (v !== originalConfig.value[k]) {
        updates[k] = String(v)
      }
    }
    if (!Object.keys(updates).length) {
      message.info(t('views.system.label_cn_257b9c3a'))
      return
    }
    await api.updateDownloadConfig(updates)
    message.success(t('views.skill.message_cn_3b108349'))
    originalConfig.value = JSON.parse(JSON.stringify(config.value))
  } catch (_) {
    message.error(t('views.network.roadNetworkWorkbench.messages.saveFail'))
  } finally {
    saveLoading.value = false
  }
}

async function onTestProxy() {
  const proxy = config.value.download_proxy
  if (!proxy || !proxy.trim()) {
    message.warning(t('views.system.message_cn_b12be20d'))
    return
  }
  proxyTesting.value = true
  proxyTestResult.value = null
  try {
    const res = await api.testProxy(proxy.trim())
    proxyTestResult.value = res.data
    if (res.data.success) {
      message.success(res.data.message)
    } else {
      message.error(res.data.error)
    }
  } catch (_) {
    proxyTestResult.value = { success: false, error: t('views.system.label_cn_b9ba20b2') }
  } finally {
    proxyTesting.value = false
  }
}

function isChanged(key) {
  return String(config.value[key]) !== String(originalConfig.value[key])
}
</script>

<template>
  <CommonPage :title="t('views.system.title_cn_6da31e6c')">
    <template #action>
      <NButton type="primary" :loading="saveLoading" @click="onSave">
        <TheIcon icon="material-symbols:save" :size="18" class="mr-5" />保存配置
      </NButton>
    </template>

    <div class="config-container">
      <NCard size="small" :title="t('views.system.title_cn_95bf0bfd')" :bordered="true">
        <NForm label-placement="left" label-width="130">
          <NFormItem :label="t('views.system.label_http_cn_5b2abce3')">
            <NSpace align="center">
              <NInput
                v-model:value="config.download_proxy"
                :placeholder="t('views.system.placeholder_cn_ef8dec06')"
                style="width: 380px"
                :status="isChanged('download_proxy') ? 'warning' : undefined"
              />
              <NButton
                type="primary"
                :loading="proxyTesting"
                @click="onTestProxy"
                secondary
              >测试连通性</NButton>
            </NSpace>
          </NFormItem>

          <div v-if="proxyTestResult" style="margin-top: 8px">
            <NTag :type="proxyTestResult.success ? 'success' : 'error'" size="small">
              {{ proxyTestResult.success ? '✓ 连通' : t('views.system.label_cn_3dc27dd7') }}
            </NTag>
            <span v-if="proxyTestResult.success" style="margin-left: 8px; font-size: 12px; color: #999">
              响应码 {{ proxyTestResult.status_code }}，耗时 {{ proxyTestResult.elapsed_ms }}ms
            </span>
            <span v-if="!proxyTestResult.success" style="margin-left: 8px; font-size: 12px; color: #d03050">
              {{ proxyTestResult.error }}
            </span>
          </div>
        </NForm>
      </NCard>

      <NCard size="small" :title="t('views.system.title_cn_a4b7e1d4')" :bordered="true" style="margin-top: 12px">
        <NForm label-placement="left" label-width="130">
          <NFormItem :label="t('views.system.label_cn_c1555cf6')">
            <NSpace align="center">
              <NSlider
                v-model:value="config.download_chunk_count"
                :min="1" :max="8" :step="1"
                style="width: 280px"
                :marks="{ 1: '1', 4: '4', 8: '8' }"
              />
              <span style="min-width: 30px; font-weight: 600">{{ config.download_chunk_count }}</span>
              <NTag v-if="isChanged('download_chunk_count')" type="warning" size="small">已修改</NTag>
            </NSpace>
          </NFormItem>

          <NFormItem :label="t('views.system.label_cn_1949301e')">
            <NSpace align="center">
              <NInputNumber
                v-model:value="config.download_chunk_size_mb"
                :min="10" :max="500" :step="10"
                style="width: 120px"
              />
              <NTag v-if="isChanged('download_chunk_size_mb')" type="warning" size="small">已修改</NTag>
            </NSpace>
          </NFormItem>
        </NForm>
      </NCard>

      <NCard size="small" :title="t('views.system.title_cn_15b4408d')" :bordered="true" style="margin-top: 12px">
        <NForm label-placement="left" label-width="130">
          <NFormItem :label="t('views.system.label_cn_efa1500a')">
            <NSpace align="center">
              <NInputNumber
                v-model:value="config.download_max_retries"
                :min="0" :max="10" :step="1"
                style="width: 120px"
              />
              <span style="font-size: 12px; color: #999">0 = 不重试</span>
              <NTag v-if="isChanged('download_max_retries')" type="warning" size="small">已修改</NTag>
            </NSpace>
          </NFormItem>

          <NFormItem :label="t('views.system.label_cn_e2e97eee')">
            <NSpace align="center">
              <NInputNumber
                v-model:value="config.download_timeout_seconds"
                :min="60" :max="3600" :step="60"
                style="width: 120px"
              />
              <span style="font-size: 12px; color: #999">60-3600 秒</span>
              <NTag v-if="isChanged('download_timeout_seconds')" type="warning" size="small">已修改</NTag>
            </NSpace>
          </NFormItem>

          <NFormItem :label="t('views.system.label_ssl_cn_854ee827')">
            <NSpace align="center">
              <NSwitch
                :value="config.download_ssl_verify !== 'false'"
                @update:value="(v) => config.download_ssl_verify = v ? 'true' : 'false'"
              />
              <span style="font-size: 12px; color: #999">
                {{ config.download_ssl_verify !== 'false' ? '开启（安全）' : t('views.system.label_cn_dddc5e68') }}
              </span>
              <NTag v-if="isChanged('download_ssl_verify')" type="warning" size="small">已修改</NTag>
            </NSpace>
          </NFormItem>
        </NForm>
      </NCard>
    </div>
  </CommonPage>
</template>

<style scoped>
.config-container {
  max-width: 800px;
}
</style>
