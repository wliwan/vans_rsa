<script setup>
import { onMounted, ref } from 'vue'
import {
  NButton, NCard, NForm, NFormItem, NInput, NInputNumber, NPopconfirm,
  NSpace, NTag, NSlider, NSwitch, NDivider, useMessage,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'

defineOptions({ name: '系统下载配置' })

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
      message.info('没有变更')
      return
    }
    await api.updateDownloadConfig(updates)
    message.success('保存成功')
    originalConfig.value = JSON.parse(JSON.stringify(config.value))
  } catch (_) {
    message.error('保存失败')
  } finally {
    saveLoading.value = false
  }
}

async function onTestProxy() {
  const proxy = config.value.download_proxy
  if (!proxy || !proxy.trim()) {
    message.warning('请先填写代理地址')
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
    proxyTestResult.value = { success: false, error: '测试请求失败' }
  } finally {
    proxyTesting.value = false
  }
}

function isChanged(key) {
  return String(config.value[key]) !== String(originalConfig.value[key])
}
</script>

<template>
  <CommonPage title="系统下载配置">
    <template #action>
      <NButton type="primary" :loading="saveLoading" @click="onSave">
        <TheIcon icon="material-symbols:save" :size="18" class="mr-5" />保存配置
      </NButton>
    </template>

    <div class="config-container">
      <NCard size="small" title="代理配置" :bordered="true">
        <NForm label-placement="left" label-width="130">
          <NFormItem label="HTTP 代理地址">
            <NSpace align="center">
              <NInput
                v-model:value="config.download_proxy"
                placeholder="如 http://127.0.0.1:7890"
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
              {{ proxyTestResult.success ? '✓ 连通' : '✗ 失败' }}
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

      <NCard size="small" title="分块下载" :bordered="true" style="margin-top: 12px">
        <NForm label-placement="left" label-width="130">
          <NFormItem label="线程数 (1-8)">
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

          <NFormItem label="块大小 (MB)">
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

      <NCard size="small" title="重试与超时" :bordered="true" style="margin-top: 12px">
        <NForm label-placement="left" label-width="130">
          <NFormItem label="最大重试次数 (0-10)">
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

          <NFormItem label="超时时间 (秒)">
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

          <NFormItem label="SSL 证书验证">
            <NSpace align="center">
              <NSwitch
                :value="config.download_ssl_verify !== 'false'"
                @update:value="(v) => config.download_ssl_verify = v ? 'true' : 'false'"
              />
              <span style="font-size: 12px; color: #999">
                {{ config.download_ssl_verify !== 'false' ? '开启（安全）' : '关闭（仅代理环境出现 SSL 错误时使用）' }}
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
