/**
 * Vite 插件：使用 @cybersailor/i18n-detect-vue 扫描前端硬编码中文
 *
 * 提供 dev server 端点 GET /__i18n-scan，返回 AST 级扫描结果。
 * 仅在开发模式下生效，生产构建时不包含此端点。
 */
import { readFileSync, readdirSync, statSync } from 'fs'
import { resolve, relative, extname, join } from 'path'

const SCAN_EXTENSIONS = new Set(['.vue', '.js', '.ts', '.jsx', '.tsx'])
const EXCLUDE_DIRS = new Set(['node_modules', 'dist', 'public', 'lib', 'i18n', '.git', '__pycache__'])

function walkFiles(dir, root, files = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.') && entry.name !== '.') continue
    const full = join(dir, entry.name)
    if (entry.isDirectory()) {
      if (EXCLUDE_DIRS.has(entry.name)) continue
      walkFiles(full, root, files)
    } else if (entry.isFile() && SCAN_EXTENSIONS.has(extname(entry.name))) {
      files.push(full)
    }
  }
  return files
}

export function i18nScanPlugin() {
  return {
    name: 'i18n-scan-plugin',

    configureServer(server) {
      server.middlewares.use('/__i18n-scan', async (_req, res) => {
        try {
          const root = process.cwd()
          const srcDir = join(root, 'src')
          const files = walkFiles(srcDir, root)

          const allDetections = []
          // 懒加载，避免构建时引入 Node-only 模块
          const { detectHardStrings } = await import('@cybersailor/i18n-detect-vue')

          for (const filePath of files) {
            try {
              const content = readFileSync(filePath, 'utf-8')
              const detections = detectHardStrings(filePath)
              const relPath = relative(root, filePath)

              for (const d of detections) {
                const line = content.substring(0, d.start).split('\n').length
                // 规范化文本
                let text = (d.text || '').replace(/\s+/g, ' ').trim()
                if (!text) continue

                allDetections.push({
                  file: relPath,
                  line,
                  start: d.start,
                  end: d.end,
                  text,
                  source: d.source || 'unknown',
                })
              }
            } catch (e) {
              // 单个文件失败不影响整体
              console.warn(`[i18n-scan] 跳过 ${filePath}: ${e.message}`)
            }
          }

          // 按文件+行号排序
          allDetections.sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line)

          res.setHeader('Content-Type', 'application/json')
          res.setHeader('Access-Control-Allow-Origin', '*')
          res.end(JSON.stringify({
            total: allDetections.length,
            items: allDetections,
          }))
        } catch (e) {
          res.statusCode = 500
          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify({ error: e.message }))
        }
      })
    },
  }
}
