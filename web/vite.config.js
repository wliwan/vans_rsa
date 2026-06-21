import { defineConfig, loadEnv } from 'vite'

import { convertEnv, getSrcPath, getRootPath } from './build/utils'
import { viteDefine } from './build/config'
import { createVitePlugins } from './build/plugin'
import { i18nScanPlugin } from './vite-plugin-i18n-scan'
import { OUTPUT_DIR, PROXY_CONFIG } from './build/constant'

export default defineConfig(({ command, mode }) => {
  const srcPath = getSrcPath()
  const rootPath = getRootPath()
  const isBuild = command === 'build'

  const env = loadEnv(mode, process.cwd())
  const viteEnv = convertEnv(env)
  const { VITE_PORT, VITE_PUBLIC_PATH, VITE_USE_PROXY, VITE_BASE_API } = viteEnv

  return {
    base: VITE_PUBLIC_PATH || '/',
    resolve: {
      alias: {
        '~': rootPath,
        '@': srcPath,
      },
    },
    define: viteDefine,
    // i18n-scan 插件仅在 dev 模式下工作
    plugins: [...createVitePlugins(viteEnv, isBuild), i18nScanPlugin()],
    server: {
      host: '0.0.0.0',
      port: VITE_PORT,
      open: true,
      proxy: VITE_USE_PROXY
        ? {
            '/api': {
              target: 'http://127.0.0.1:9999',
              changeOrigin: true,
            },
          }
        : undefined,
    },
    build: {
      target: 'es2015',
      outDir: OUTPUT_DIR || 'dist',
      reportCompressedSize: false, // 启用/禁用 gzip 压缩大小报告
      chunkSizeWarningLimit: 1024, // chunk 大小警告的限制（单位kb）
    },
  }
})