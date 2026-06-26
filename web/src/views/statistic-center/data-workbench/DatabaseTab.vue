<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NButton, NModal, NSpace, NSelect, NPopconfirm,
  NForm, NFormItem, NTag, NUpload, NUploadDragger,
  NCheckbox, NInput, NInputNumber, NText, NSpin,
  NBreadcrumb, NBreadcrumbItem,
  useMessage,
} from 'naive-ui'
import TheIcon from '@/components/icon/TheIcon.vue'
import api from '@/api'
import { useDataWorkbench } from '@/composables/useDataWorkbench'

const { t } = useI18n()
const message = useMessage()
const {
  selectedWs, loading, isMobileCollapsed,
  formatFileSize, downloadBlob, runWithProgress,
} = useDataWorkbench()

// ── 数据库数据状态 ──
const databaseDocs = ref([])
const selectedDatabaseDocIds = ref([])
const dbLoading = ref(false)

const showMySQLModal = ref(false)
const mysqlForm = ref({ host: '127.0.0.1', port: 3306, user: 'root', password: '', database: '' })
const mysqlTables = ref([])
const mysqlTested = ref(false)
const mysqlTesting = ref(false)
const mysqlSelectedTables = ref([])

const showSQLiteModal = ref(false)
const sqliteFilePath = ref('')
const sqliteFileName = ref('')
const sqliteTables = ref([])
const sqliteUploading = ref(false)
const sqliteUploadRef = ref(null)
const sqliteSelectedTables = ref([])

const showPixelModal = ref(false)
const pixelAccounts = ref([])
const pixelForm = ref({ pixel_account_id: null, table_name: '', table_label: '' })
const pixelTables = ref([])

const showRoadNetworkModal = ref(false)
const roadNetworkRegions = ref([])
const roadNetworkForm = ref({ region_id: null })
const roadNetworks = ref([])
const roadNetworkSelected = ref([])

const showCopyToModal = ref(false)
const copyToWorkspaces = ref([])
const copyToForm = ref({ target_workspace_id: null })

async function loadDatabaseDocs() {
  if (!selectedWs.value) return
  try {
    const res = await api.getDocumentList({ workspace_id: selectedWs.value.id, source_type: 'original' })
    databaseDocs.value = (res.data || []).filter(d => d.import_source && ['mysql', 'sqlite', 'pixel', 'road_network'].includes(d.import_source))
  } catch (e) {}
}

function toggleDatabaseDocSelect(id) { const idx = selectedDatabaseDocIds.value.indexOf(id); if (idx >= 0) selectedDatabaseDocIds.value.splice(idx, 1); else selectedDatabaseDocIds.value.push(id) }
function toggleAllDatabaseDocs() { if (selectedDatabaseDocIds.value.length === databaseDocs.value.length) selectedDatabaseDocIds.value = []; else selectedDatabaseDocIds.value = databaseDocs.value.map(d => d.id) }

async function deleteDatabaseDoc(doc) { try { await api.deleteDocument({ document_id: doc.id }); await loadDatabaseDocs() } catch (e) { message.error(t('views.statistic-center.message_cn_acf0664a')) } }

async function batchExportDatabaseDocs() {
  if (!selectedDatabaseDocIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_f3328c38')); return }
  try { const res = await api.batchExportDocuments({ document_ids: [...selectedDatabaseDocIds.value] }); const blob = new Blob([res.data], { type: 'application/zip' }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = t('views.statistic-center.label_cn_01470c4d'); a.click(); URL.revokeObjectURL(url); message.success(`已导出 ${selectedDatabaseDocIds.value.length} 条数据`) }
  catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_dd51ab50')) }
}

async function batchDeleteDatabaseDocs() {
  if (!selectedDatabaseDocIds.value.length) return
  try { await api.batchDeleteDocuments({ document_ids: [...selectedDatabaseDocIds.value] }); message.success(`已删除 ${selectedDatabaseDocIds.value.length} 条数据`); selectedDatabaseDocIds.value = []; await loadDatabaseDocs() }
  catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_acf0664a')) }
}

async function openCopyToModal() {
  if (!selectedDatabaseDocIds.value.length) { message.warning(t('views.statistic-center.placeholder_cn_f3328c38')); return }
  copyToForm.value = { target_workspace_id: null }; showCopyToModal.value = true
  try { const res = await api.getWorkspaceList({ page: 1, page_size: 500 }); copyToWorkspaces.value = (res.data || []).filter(w => w.id !== selectedWs.value.id).map(w => ({ label: w.name, value: w.id })) } catch (e) {}
}

async function handleCopyToWorkspace() {
  if (!copyToForm.value.target_workspace_id) { message.warning(t('views.statistic-center.placeholder_cn_946eef8d')); return }
  dbLoading.value = true; showCopyToModal.value = false
  try { const res = await api.copyToWorkspace({ target_workspace_id: copyToForm.value.target_workspace_id, document_ids: [...selectedDatabaseDocIds.value] }); message.success(res.msg || `成功复制 ${res.data?.documents || 0} 项数据`) }
  catch (e) { message.error(e?.response?.data?.msg || t('views.statistic-center.message_cn_5154ae17')) }
  dbLoading.value = false
}

// ── MySQL ──
function openMySQLModal() { mysqlForm.value = { host: '127.0.0.1', port: 3306, user: 'root', password: '', database: '' }; mysqlTables.value = []; mysqlTested.value = false; mysqlSelectedTables.value = []; showMySQLModal.value = true }

async function testMySQL() {
  if (!mysqlForm.value.host || !mysqlForm.value.database) { message.warning(t('views.statistic-center.placeholder_cn_8242c2cd')); return }
  mysqlTesting.value = true; mysqlTested.value = false
  try { const res = await api.testMySQLConnection(mysqlForm.value); mysqlTables.value = (res.data?.tables || []).map(t => ({ ...t, selected: false })); mysqlTested.value = true; message.success(res.msg || `连接成功，共 ${mysqlTables.value.length} 个表`) }
  catch (e) { message.error(e?.response?.data?.msg || e?.message || t('views.statistic-center.message_cn_0745fc09')) }
  mysqlTesting.value = false
}

async function importMySQL() {
  const selected = mysqlTables.value.filter(t => t.selected).map(t => t.name)
  if (!selected.length) { message.warning(t('views.statistic-center.placeholder_cn_ffd60b41')); return }
  if (!selectedWs.value) return
  dbLoading.value = true; showMySQLModal.value = false
  try { const res = await api.importMySQLTables({ workspace_id: selectedWs.value.id, ...mysqlForm.value, tables: selected }); message.success(res.msg || `成功导入 ${selected.length} 个表`); await loadDatabaseDocs() }
  catch (e) { message.error(e?.response?.data?.msg || e?.message || t('views.statistic-center.message_cn_fddcd7c6')) }
  dbLoading.value = false
}

// ── SQLite ──
function openSQLiteModal() { sqliteFilePath.value = ''; sqliteFileName.value = ''; sqliteTables.value = []; sqliteSelectedTables.value = []; showSQLiteModal.value = true }

async function handleSQLiteUpload({ file }) {
  if (!selectedWs.value) { message.warning(t('views.statistic-center.placeholder_cn_aac7e445')); return }
  sqliteUploading.value = true
  try { const res = await api.uploadSQLiteFile(selectedWs.value.id, file.file); sqliteFilePath.value = res.data.file_path; sqliteFileName.value = res.data.file_name; sqliteTables.value = (res.data.tables || []).map(t => ({ ...t, selected: false })); message.success(res.msg || `解析成功，共 ${sqliteTables.value.length} 个表`) }
  catch (e) { message.error(e?.response?.data?.msg || e?.message || t('views.statistic-center.message_cn_5348dcac')) }
  sqliteUploading.value = false
  // 清空 NUpload 内部文件列表，避免下次上传时重复上传旧文件
  sqliteUploadRef.value?.clear()
}

async function importSQLite() {
  const selected = sqliteTables.value.filter(t => t.selected).map(t => t.name)
  if (!selected.length) { message.warning(t('views.statistic-center.placeholder_cn_ffd60b41')); return }
  if (!selectedWs.value) return
  dbLoading.value = true; showSQLiteModal.value = false
  try { const res = await api.importSQLiteTables({ workspace_id: selectedWs.value.id, file_path: sqliteFilePath.value, tables: selected }); message.success(res.msg || `成功导入 ${selected.length} 个表`); await loadDatabaseDocs() }
  catch (e) { message.error(e?.response?.data?.msg || e?.message || t('views.statistic-center.message_cn_fddcd7c6')) }
  dbLoading.value = false
}

// ── 像素数据 ──
async function openPixelModal() {
  pixelForm.value = { pixel_account_id: null, table_name: '', table_label: '' }; pixelTables.value = []; showPixelModal.value = true
  try { const res = await api.getPixelAccountsForImport(); pixelAccounts.value = (res.data || []).map(a => ({ label: a.label || a.username, value: a.id })) }
  catch (e) { message.error(t('views.statistic-center.message_cn_5bbfb780')) }
}

async function onPixelAccountChange(accountId) {
  pixelForm.value.table_name = ''; pixelForm.value.table_label = ''; pixelTables.value = []
  if (!accountId) return
  try { const res = await api.getPixelTablesForImport({ pixel_account_id: accountId }); pixelTables.value = (res.data || []).map(t => ({ label: t.label || t.description, value: t.name, description: t.description })) }
  catch (e) { message.error(t('views.statistic-center.message_cn_dfe3f39d')) }
}

async function importPixel() {
  if (!pixelForm.value.pixel_account_id || !pixelForm.value.table_name) { message.warning(t('views.statistic-center.placeholder_cn_2162302a')); return }
  if (!selectedWs.value) return
  dbLoading.value = true; showPixelModal.value = false
  try { const res = await api.importPixelTable({ ...pixelForm.value, workspace_id: selectedWs.value.id }); message.success(res.msg || t('views.statistic-center.message_cn_b6d16a81')); await loadDatabaseDocs() }
  catch (e) { message.error(e?.response?.data?.msg || e?.message || t('views.statistic-center.message_cn_fddcd7c6')) }
  dbLoading.value = false
}

// ── 路网数据 ──
async function openRoadNetworkModal() {
  roadNetworkForm.value = { region_id: null }; roadNetworks.value = []; roadNetworkSelected.value = []; showRoadNetworkModal.value = true
  try { const res = await api.getRoadNetworkRegionsForImport(); roadNetworkRegions.value = (res.data || []).map(r => ({ label: r.label || r.name, value: r.id, network_count: r.network_count })) }
  catch (e) { message.error(t('views.statistic-center.message_cn_a495eb1d')) }
}

async function onRoadNetworkRegionChange(regionId) {
  roadNetworks.value = []; roadNetworkSelected.value = []
  if (!regionId) return
  try { const res = await api.getRoadNetworkListForImport({ region_id: regionId }); roadNetworks.value = (res.data || []).map(n => ({ ...n, selected: false })) }
  catch (e) { message.error(t('views.statistic-center.message_cn_52191929')) }
}

function toggleAllRoadNetworks() { if (!roadNetworks.value.length) return; const allSelected = roadNetworks.value.every(n => n.selected); roadNetworks.value.forEach(n => n.selected = !allSelected) }

async function importRoadNetwork() {
  const selected = roadNetworks.value.filter(n => n.selected).map(n => n.id)
  if (!selected.length) { message.warning(t('views.statistic-center.placeholder_cn_79e1b67e')); return }
  if (!selectedWs.value) return
  dbLoading.value = true; showRoadNetworkModal.value = false
  try { const res = await api.importRoadNetworkStats({ workspace_id: selectedWs.value.id, region_id: roadNetworkForm.value.region_id, road_network_ids: selected }); message.success(res.msg || `成功导入 ${res.data?.length || selected.length} 个路网统计`); await loadDatabaseDocs() }
  catch (e) { message.error(e?.response?.data?.msg || e?.message || t('views.statistic-center.message_cn_fddcd7c6')) }
  dbLoading.value = false
}

watch(() => selectedWs.value, (ws) => {
  if (ws) {
    loadDatabaseDocs()
  } else {
    databaseDocs.value = []
    selectedDatabaseDocIds.value = []
  }
}, { immediate: true })

defineExpose({ loadDatabaseDocs })
</script>

<template>
  <div class="flex-1 flex flex-col" style="min-height: 0; overflow: hidden">
    <!-- 工具栏 -->
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <div class="flex items-center gap-2">
        <TheIcon icon="material-symbols:database" :size="20" class="text-blue-500" />
        <span class="font-semibold text-base">{{ t('views.statistic-center.label_cn_c274dc20') }}</span>
        <NTag size="small" :bordered="false" type="info">{{ databaseDocs.length }}</NTag>
      </div>
      <NSpace size="small">
        <NButton size="small" type="primary" :disabled="!selectedDatabaseDocIds.length" @click="batchExportDatabaseDocs">
          <TheIcon icon="material-symbols:download" :size="16" class="mr-1" />导出({{ selectedDatabaseDocIds.length }})
        </NButton>
        <NPopconfirm @positive-click="batchDeleteDatabaseDocs" :disabled="!selectedDatabaseDocIds.length">
          <template #trigger><NButton size="small" type="warning" :disabled="!selectedDatabaseDocIds.length"><TheIcon icon="material-symbols:delete-outline" :size="16" />删除({{ selectedDatabaseDocIds.length }})</NButton></template>
          确认删除选中的 {{ selectedDatabaseDocIds.length }} 条数据库数据？
        </NPopconfirm>
        <NButton size="small" :disabled="!selectedDatabaseDocIds.length" @click="openCopyToModal">
          <TheIcon icon="material-symbols:content-copy" :size="16" class="mr-1" />复制到
        </NButton>
      </NSpace>
    </div>

    <!-- 导入按钮 -->
    <div class="flex flex-wrap items-center gap-2 mb-4">
      <NButton size="small" @click="openMySQLModal"><TheIcon icon="material-symbols:cloud-sync" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_00fb0e78') }}</NButton>
      <NButton size="small" @click="openSQLiteModal"><TheIcon icon="material-symbols:upload-file" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_827cdec1') }}</NButton>
      <NButton size="small" @click="openPixelModal"><TheIcon icon="material-symbols:satellite" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_40909c62') }}</NButton>
      <NButton size="small" @click="openRoadNetworkModal"><TheIcon icon="material-symbols:route" :size="16" class="mr-1" />{{ t('views.statistic-center.label_cn_63b03fa8') }}</NButton>
    </div>

    <!-- 数据列表 -->
    <div class="flex-1 overflow-auto rounded-lg border border-gray-100 bg-gray-50/50" style="min-height: 0">
      <div v-if="databaseDocs.length" class="p-2">
        <div class="flex items-center gap-2 mb-2 px-1">
          <NCheckbox size="small" :checked="selectedDatabaseDocIds.length === databaseDocs.length && databaseDocs.length > 0" :indeterminate="selectedDatabaseDocIds.length > 0 && selectedDatabaseDocIds.length < databaseDocs.length" @update:checked="toggleAllDatabaseDocs" />
          <span class="text-xs text-gray-400">已选 {{ selectedDatabaseDocIds.length }} / {{ databaseDocs.length }}</span>
        </div>
        <div class="grid gap-2">
          <div v-for="d in databaseDocs" :key="d.id" class="bg-white rounded-lg border border-gray-100 p-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3 min-w-0 flex-1">
                <NCheckbox size="small" :checked="selectedDatabaseDocIds.includes(d.id)" @update:checked="() => toggleDatabaseDocSelect(d.id)" class="flex-shrink-0" />
                <TheIcon
                  :icon="d.import_source === 'mysql' ? 'material-symbols:cloud' : d.import_source === 'sqlite' ? 'material-symbols:hard-drive' : d.import_source === 'pixel' ? 'material-symbols:satellite' : 'material-symbols:route'"
                  :size="18" class="text-blue-500 flex-shrink-0"
                />
                <div class="min-w-0 flex-1">
                  <div class="text-sm font-medium truncate">{{ d.name }}</div>
                  <div class="flex items-center gap-2 text-xs text-gray-400 mt-0.5 flex-wrap">
                    <NTag size="tiny" :bordered="false" :type="d.import_source === 'mysql' ? 'info' : d.import_source === 'sqlite' ? 'success' : d.import_source === 'pixel' ? 'warning' : 'default'">
                      {{ d.import_source === 'mysql' ? 'MySQL' : d.import_source === 'sqlite' ? 'SQLite' : d.import_source === 'pixel' ? t('views.statistic-center.label_cn_2374026f') : t('views.statistic-center.label_cn_75ec0658') }}
                    </NTag>
                    <span v-if="d.char_count">{{ d.char_count?.toLocaleString() }} 字符</span>
                    <span v-if="d.row_count">{{ d.row_count?.toLocaleString() }} 行</span>
                    <span v-if="d.file_size">{{ formatFileSize(d.file_size) }}</span>
                  </div>
                  <div v-if="d.source_table" class="text-xs text-gray-400 mt-0.5">源表: {{ d.source_table }}</div>
                  <div class="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
                    <span v-if="d.dump_date">dump: {{ d.dump_date?.slice(0, 10) }}</span>
                    <span v-if="d.source_last_updated">源更新: {{ d.source_last_updated?.slice(0, 10) }}</span>
                  </div>
                </div>
              </div>
              <NSpace size="small" class="flex-shrink-0 ml-3">
                <NButton size="tiny" quaternary @click="api.downloadDocument({ document_id: d.id }).then(r => { const blob = new Blob([r.data]); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = d.name; a.click(); URL.revokeObjectURL(url) })" :title="t('views.statistic-center.label_cn_f26ef914')">
                  <TheIcon icon="material-symbols:download" :size="18" />
                </NButton>
                <NPopconfirm @positive-click="deleteDatabaseDoc(d)">
                  <template #trigger><NButton size="tiny" type="error" quaternary><TheIcon icon="material-symbols:delete-outline" :size="18" /></NButton></template>
                </NPopconfirm>
              </NSpace>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="flex items-center justify-center h-full text-gray-400 py-12">
        <div class="text-center"><TheIcon icon="material-symbols:database" :size="48" class="mb-2 opacity-30" /><div class="text-base">暂无数据库导入数据</div><div class="text-sm mt-1">{{ t('views.statistic-center.label_cn_8ac56daa') }}</div></div>
      </div>
    </div>
  </div>

  <!-- ── MySQL 弹窗 ── -->
  <NModal v-model:show="showMySQLModal" :title="t('views.statistic-center.label_cn_16b3e029')" preset="card" style="width: 600px">
    <NForm label-placement="top">
      <div class="grid grid-cols-2 gap-x-4">
        <NFormItem :label="t('views.statistic-center.label_cn_aeb5271e')" required><NInput v-model:value="mysqlForm.host" placeholder="127.0.0.1" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_c76cfefe')" required><NInputNumber v-model:value="mysqlForm.port" :min="1" :max="65535" /></NFormItem>
      </div>
      <div class="grid grid-cols-2 gap-x-4">
        <NFormItem :label="t('views.statistic-center.label_cn_819767ad')"><NInput v-model:value="mysqlForm.user" placeholder="root" /></NFormItem>
        <NFormItem :label="t('views.statistic-center.label_cn_a8105204')"><NInput v-model:value="mysqlForm.password" type="password" :placeholder="t('views.statistic-center.label_cn_a8105204')" /></NFormItem>
      </div>
      <NFormItem :label="t('views.statistic-center.label_cn_5ccbbd01')" required><NInput v-model:value="mysqlForm.database" :placeholder="t('views.statistic-center.label_cn_d5f399b9')" /></NFormItem>
      <NButton size="small" @click="testMySQL" :loading="mysqlTesting" :disabled="!mysqlForm.host || !mysqlForm.database">{{ mysqlTested ? t('views.statistic-center.label_cn_671bfe2f') : t('views.statistic-center.label_cn_69e74756') }}</NButton>
      <div v-if="mysqlTested && mysqlTables.length" class="mt-3">
        <div class="text-sm text-gray-500 mb-2">{{ t('views.statistic-center.placeholder_cn_560d54bd') }}</div>
        <div class="max-h-60 overflow-auto border rounded-lg">
          <div v-for="t in mysqlTables" :key="t.name" class="flex items-center gap-2 p-2 hover:bg-gray-50 border-b border-gray-50 last:border-0">
            <NCheckbox size="small" :checked="t.selected" @update:checked="t.selected = !t.selected" />
            <span class="text-sm">{{ t.name }}</span>
            <span v-if="t.comment" class="text-xs text-gray-400">- {{ t.comment }}</span>
            <span v-if="t.estimated_rows" class="text-xs text-gray-400 ml-auto">~{{ t.estimated_rows?.toLocaleString() }} 行</span>
          </div>
        </div>
      </div>
    </NForm>
    <template #footer><NSpace justify="end"><NButton @click="showMySQLModal = false">取消</NButton><NButton type="primary" :disabled="!mysqlTested || !mysqlTables.some(t => t.selected)" :loading="dbLoading" @click="importMySQL">导入 ({{ mysqlTables.filter(t => t.selected).length }})</NButton></NSpace></template>
  </NModal>

  <!-- ── SQLite 弹窗 ── -->
  <NModal v-model:show="showSQLiteModal" :title="t('views.statistic-center.label_cn_e2846471')" preset="card" style="width: 600px">
    <div class="mb-4">
      <NUpload ref="sqliteUploadRef" :show-file-list="false" :default-upload="false" accept=".sqlite,.db,.sqlite3" @change="handleSQLiteUpload">
        <NButton :loading="sqliteUploading"><TheIcon icon="material-symbols:upload" :size="18" class="mr-1" />{{ sqliteFileName ? `已上传: ${sqliteFileName}` : t('views.statistic-center.label_cn_d895f612') }}</NButton>
      </NUpload>
    </div>
    <div v-if="sqliteTables.length" class="mt-3">
      <div class="text-sm text-gray-500 mb-2">{{ t('views.statistic-center.placeholder_cn_560d54bd') }}</div>
      <div class="max-h-60 overflow-auto border rounded-lg">
        <div v-for="t in sqliteTables" :key="t.name" class="flex items-center gap-2 p-2 hover:bg-gray-50 border-b border-gray-50 last:border-0">
          <NCheckbox size="small" :checked="t.selected" @update:checked="t.selected = !t.selected" />
          <span class="text-sm">{{ t.name }}</span>
        </div>
      </div>
    </div>
    <template #footer><NSpace justify="end"><NButton @click="showSQLiteModal = false">取消</NButton><NButton type="primary" :disabled="!sqliteTables.some(t => t.selected)" :loading="dbLoading" @click="importSQLite">导入 ({{ sqliteTables.filter(t => t.selected).length }})</NButton></NSpace></template>
  </NModal>

  <!-- ── 像素数据弹窗 ── -->
  <NModal v-model:show="showPixelModal" :title="t('views.statistic-center.label_cn_40909c62')" preset="card" style="width: 500px">
    <NForm label-placement="top">
      <NFormItem :label="t('views.statistic-center.label_cn_e034af06')" required><NSelect v-model:value="pixelForm.pixel_account_id" :options="pixelAccounts" :placeholder="t('views.statistic-center.placeholder_cn_9692c535')" @update:value="onPixelAccountChange" /></NFormItem>
      <NFormItem v-if="pixelTables.length" :label="t('views.statistic-center.label_cn_e9273484')"><NSelect v-model:value="pixelForm.table_name" :options="pixelTables" :placeholder="t('views.statistic-center.placeholder_cn_1acf0346')" /></NFormItem>
    </NForm>
    <template #footer><NSpace justify="end"><NButton @click="showPixelModal = false">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton><NButton type="primary" :disabled="!pixelForm.pixel_account_id || !pixelForm.table_name" :loading="dbLoading" @click="importPixel">导入</NButton></NSpace></template>
  </NModal>

  <!-- ── 路网数据弹窗 ── -->
  <NModal v-model:show="showRoadNetworkModal" :title="t('views.statistic-center.label_cn_63b03fa8')" preset="card" style="width: 680px; max-height: 85vh">
    <NForm label-placement="top">
      <NFormItem :label="t('views.statistic-center.placeholder_cn_97d03d46')" required>
        <NSelect v-model:value="roadNetworkForm.region_id" :options="roadNetworkRegions" :placeholder="t('views.statistic-center.placeholder_cn_b65a096f')" filterable clearable @update:value="onRoadNetworkRegionChange">
          <template #action>{{ t('views.statistic-center.placeholder_cn_7d7c8426') }}</template>
        </NSelect>
      </NFormItem>

      <!-- 无区域选中提示 -->
      <div v-if="!roadNetworkForm.region_id && !roadNetworks.length" class="flex flex-col items-center justify-center py-12 text-gray-400">
        <TheIcon icon="material-symbols:route" :size="56" class="mb-3 opacity-25" />
        <div class="text-base font-medium text-gray-500">{{ t('views.statistic-center.placeholder_cn_2eaae997') }}</div>
        <div class="text-sm mt-1">{{ t('views.statistic-center.label_cn_aa6aa60d') }}</div>
      </div>

      <!-- 已选区域但加载中 -->
      <div v-else-if="roadNetworkForm.region_id && !roadNetworks.length" class="flex items-center justify-center py-10 text-gray-400">
        <NSpin size="small" /><span class="ml-2 text-sm">{{ t('views.statistic-center.label_cn_a9da3576') }}</span>
      </div>

      <!-- 路网文件列表 -->
      <div v-else class="mt-2">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <NCheckbox
              size="small"
              :checked="roadNetworks.every(n => n.selected) && roadNetworks.length > 0"
              :indeterminate="roadNetworks.some(n => n.selected) && !roadNetworks.every(n => n.selected)"
              @update:checked="toggleAllRoadNetworks"
            />
            <span class="text-sm text-gray-500">
              已选 <strong class="text-gray-700">{{ roadNetworks.filter(n => n.selected).length }}</strong> / {{ roadNetworks.length }} 个路网文件
            </span>
          </div>
          <span class="text-xs text-gray-400">
            {{ roadNetworks.filter(n => n.selected).length ? roadNetworks.every(n => n.selected) ? t('views.statistic-center.label_cn_dfb9060b') : t('views.statistic-center.label_cn_ec68176e') : t('views.statistic-center.label_cn_f0409ecf') }}
          </span>
        </div>

        <div class="space-y-1.5 max-h-72 overflow-auto pr-1">
          <div
            v-for="n in roadNetworks"
            :key="n.id"
            class="flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all hover:shadow-sm"
            :class="{
              'border-blue-300 bg-blue-50/60 shadow-sm': n.selected,
              'border-gray-150 bg-white hover:border-gray-250': !n.selected
            }"
            @click="n.selected = !n.selected"
          >
            <!-- 选择框 -->
            <NCheckbox size="small" :checked="n.selected" class="flex-shrink-0" @click.stop />

            <!-- 主信息 -->
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="text-sm font-medium truncate">{{ n.file_name }}</span>
                <NTag size="tiny" :bordered="false" :type="n.download_mode === 'name' ? 'info' : 'success'" class="flex-shrink-0">
                  {{ n.download_mode === 'name' ? t('views.statistic-center.label_cn_d06a491f') : t('views.statistic-center.label_cn_1ded98db') }}
                </NTag>
                <NTag v-if="n.file_type" size="tiny" :bordered="false" class="flex-shrink-0">{{ n.file_type }}</NTag>
              </div>
              <div class="flex items-center gap-4 text-xs text-gray-400 mt-1.5">
                <span class="flex items-center gap-1"><TheIcon icon="material-symbols:account-tree" :size="13" />{{ (n.node_count || 0).toLocaleString() }} 节点</span>
                <span class="flex items-center gap-1"><TheIcon icon="material-symbols:timeline" :size="13" />{{ (n.edge_count || 0).toLocaleString() }} 边</span>
                <span v-if="n.junction_count" class="flex items-center gap-1"><TheIcon icon="material-symbols:polyline" :size="13" />{{ n.junction_count }} 路口</span>
                <span v-if="n.highway_count" class="flex items-center gap-1"><TheIcon icon="material-symbols:layers" :size="13" />{{ n.highway_count }} 等级</span>
                <span v-if="n.file_size" class="flex items-center gap-1"><TheIcon icon="material-symbols:hard-drive" :size="13" />{{ formatFileSize(n.file_size) }}</span>
              </div>
            </div>

            <!-- 选中标记 -->
            <div v-if="n.selected" class="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center flex-shrink-0">
              <TheIcon icon="material-symbols:check" :size="14" class="text-white" />
            </div>
          </div>
        </div>
      </div>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="showRoadNetworkModal = false">{{ t('views.statistic-center.label_cn_625fb26b') }}</NButton>
        <NButton
          type="primary"
          :disabled="!roadNetworks.some(n => n.selected)"
          :loading="dbLoading"
          @click="importRoadNetwork"
        >
          <template #icon><TheIcon icon="material-symbols:database-import" :size="16" /></template>
          {{ t('views.statistic-center.label_cn_8d9a071e') }} {{ roadNetworks.filter(n => n.selected).length || '' }} 个路网统计
        </NButton>
      </NSpace>
    </template>
  </NModal>

  <!-- ── 复制到弹窗 ── -->
  <NModal v-model:show="showCopyToModal" :title="t('views.statistic-center.label_cn_2008c3ff')" preset="card" style="width: 480px">
    <div class="text-sm text-gray-500 mb-4">将复制 {{ selectedDatabaseDocIds.length }} 项数据库导入数据到目标工作区。<br/>新建数据库记录指向源文件，共享同一物理文件。删除记录时不会影响其他工作区。</div>
    <NForm label-placement="top"><NFormItem :label="t('views.statistic-center.label_cn_9269a338')" required><NSelect v-model:value="copyToForm.target_workspace_id" :options="copyToWorkspaces" :placeholder="t('views.statistic-center.placeholder_cn_96d6caf0')" filterable /></NFormItem></NForm>
    <template #footer><NSpace justify="end"><NButton @click="showCopyToModal = false">取消</NButton><NButton type="primary" :disabled="!copyToForm.target_workspace_id" :loading="dbLoading" @click="handleCopyToWorkspace">{{ t('views.statistic-center.message_cn_d987a67e') }}</NButton></NSpace></template>
  </NModal>
</template>

<style scoped>
.text-xs { font-size: 12px !important; line-height: 16px !important; }
.text-sm { font-size: 14px !important; line-height: 20px !important; }
.text-base { font-size: 16px !important; line-height: 24px !important; }
.text-lg { font-size: 18px !important; line-height: 26px !important; }
.text-xl { font-size: 20px !important; line-height: 28px !important; }
</style>
