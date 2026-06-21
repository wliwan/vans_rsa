import { request } from '@/utils'

export default {
  login: (data) => request.post('/base/access_token', data, { noNeedToken: true }),
  getUserInfo: () => request.get('/base/userinfo'),
  getUserMenu: () => request.get('/base/usermenu'),
  getUserApi: () => request.get('/base/userapi'),
  // profile
  updatePassword: (data = {}) => request.post('/base/update_password', data),
  // users
  getUserList: (params = {}) => request.get('/user/list', { params }),
  getUserById: (params = {}) => request.get('/user/get', { params }),
  createUser: (data = {}) => request.post('/user/create', data),
  updateUser: (data = {}) => request.post('/user/update', data),
  deleteUser: (params = {}) => request.delete(`/user/delete`, { params }),
  resetPassword: (data = {}) => request.post(`/user/reset_password`, data),
  // role
  getRoleList: (params = {}) => request.get('/role/list', { params }),
  createRole: (data = {}) => request.post('/role/create', data),
  updateRole: (data = {}) => request.post('/role/update', data),
  deleteRole: (params = {}) => request.delete('/role/delete', { params }),
  updateRoleAuthorized: (data = {}) => request.post('/role/authorized', data),
  getRoleAuthorized: (params = {}) => request.get('/role/authorized', { params }),
  // menus
  getMenus: (params = {}) => request.get('/menu/list', { params }),
  createMenu: (data = {}) => request.post('/menu/create', data),
  updateMenu: (data = {}) => request.post('/menu/update', data),
  deleteMenu: (params = {}) => request.delete('/menu/delete', { params }),
  scanViews: () => request.get('/menu/scan-views'),
  // apis
  getApis: (params = {}) => request.get('/api/list', { params }),
  createApi: (data = {}) => request.post('/api/create', data),
  updateApi: (data = {}) => request.post('/api/update', data),
  deleteApi: (params = {}) => request.delete('/api/delete', { params }),
  refreshApi: (data = {}) => request.post('/api/refresh', data),
  // depts
  getDepts: (params = {}) => request.get('/dept/list', { params }),
  createDept: (data = {}) => request.post('/dept/create', data),
  updateDept: (data = {}) => request.post('/dept/update', data),
  deleteDept: (params = {}) => request.delete('/dept/delete', { params }),
  // auditlog
  getAuditLogList: (params = {}) => request.get('/auditlog/list', { params }),
  // pixel-accounts
  getPixelAccountList: (params = {}) => request.get('/pixel-account/list', { params }),
  getPixelAccountById: (params = {}) => request.get('/pixel-account/get', { params }),
  createPixelAccount: (data = {}) => request.post('/pixel-account/create', data),
  updatePixelAccount: (data = {}) => request.post('/pixel-account/update', data),
  deletePixelAccount: (params = {}) => request.delete('/pixel-account/delete', { params }),
  // defects
  getDefectAccounts: () => request.get('/defect/accounts'),
  getDefectList: (params = {}) => request.get('/defect/list', { params }),
  syncDefects: (data = {}) => request.post('/defect/sync', data, { timeout: 0 }),
  clearDefects: (data = {}) => request.post('/defect/clear', data),
  // tracks
  getTrackAccounts: () => request.get('/track/accounts'),
  getTrackCarTypes: (params = {}) => request.get('/track/car-types', { params }),
  getTrackCars: (params = {}) => request.get('/track/cars', { params }),
  getTrackList: (params = {}) => request.get('/track/list', { params }),
  syncTracks: (data = {}) => request.post('/track/sync', data, { timeout: 0 }),
  clearTracks: (data = {}) => request.post('/track/clear', data),
  // regions
  getRegionTree: () => request.get('/region/tree'),
  getRegionChildren: (parent_id) => request.get('/region/children', { params: { parent_id } }),
  getRegionById: (region_id) => request.get('/region/get', { params: { region_id } }),
  getRegionList: (params = {}) => request.get('/region/list', { params }),
  createRegion: (data = {}) => request.post('/region/create', data),
  updateRegion: (data = {}) => request.post('/region/update', data),
  deleteRegion: (params = {}) => request.delete('/region/delete', { params }),
  importRegions: () => request.post('/region/import', {}, { timeout: 0 }),
  clearRegions: () => request.post('/region/clear', {}, { timeout: 0 }),
  exportRegions: (data = {}) => request.post('/region/export', data),
  batchUpdateRegions: (data = {}) => request.post('/region/batch-update', data),
  fillGeonames: (force = false, proxy = null) =>
    request.post('/region/fill-geonames', { force_download: force, proxy }, { timeout: 0 }),
  getGeonamesProgress: () => request.get('/region/fill-geonames/progress'),
  // system-config
  getDownloadConfig: () => request.get('/system-config/download'),
  updateDownloadConfig: (data = {}) => request.post('/system-config/download', data),
  testProxy: (proxy_url) => request.post('/system-config/test-proxy', { proxy_url }),
  // region-boundary
  getBoundaryStatus: (region_id) => request.get('/region/region-boundary/status', { params: { region_id } }),
  downloadBoundary: (data = {}) => request.post('/region/region-boundary/download', data, { timeout: 0 }),
  uploadBoundary: (region_id, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post(`/region/region-boundary/upload?region_id=${region_id}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
  deleteBoundary: (params = {}) => request.delete('/region/region-boundary/delete', { params }),
  clearBoundaries: (params = {}) => request.delete('/region/region-boundary/clear', { params }),
  downloadBoundaryFile: (params = {}) => request.get('/region/region-boundary/download-file', {
    params, responseType: 'blob', timeout: 0,
  }),
  // road-network
  getRoadNetworkStatus: (region_id) => request.get('/region/road-network/status', { params: { region_id } }),
  downloadRoadNetwork: (data = {}) => request.post('/region/road-network/download', data, { timeout: 0 }),
  uploadRoadNetwork: (region_id, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post(`/region/road-network/upload?region_id=${region_id}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
  deleteRoadNetwork: (params = {}) => request.delete('/region/road-network/delete', { params }),
  clearRoadNetworks: (params = {}) => request.delete('/region/road-network/clear', { params }),
  downloadRoadNetworkFile: (params = {}) => request.get('/region/road-network/download-file', {
    params, responseType: 'blob', timeout: 0,
  }),
  // ai-proxy
  getAIProxyList: (params = {}) => request.get('/ai-proxy/list', { params }),
  getAIProxyByName: (name) => request.get('/ai-proxy/get', { params: { name } }),
  createAIProxy: (data = {}) => request.post('/ai-proxy/create', data),
  updateAIProxy: (data = {}) => request.post('/ai-proxy/update', data),
  deleteAIProxy: (params = {}) => request.delete('/ai-proxy/delete', { params }),
  getAIProxyUsers: () => request.get('/ai-proxy/users'),
  // workspace
  getWorkspaceList: (params = {}) => request.get('/workspace/list', { params }),
  createWorkspace: (data = {}) => request.post('/workspace/create', data),
  updateWorkspace: (data = {}) => request.post('/workspace/update', data),
  deleteWorkspace: (params = {}) => request.delete('/workspace/delete', { params }),
  getWorkspaceUsers: () => request.get('/workspace/users'),
  // workspace documents
  getDocumentList: (params = {}) => request.get('/workspace/document/list', { params }),
  uploadDocument: (workspace_id, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post(`/workspace/document/upload?workspace_id=${workspace_id}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
  downloadDocument: (params = {}) => request.get('/workspace/document/download', { params, responseType: 'blob', timeout: 0 }),
  deleteDocument: (params = {}) => request.delete('/workspace/document/delete', { params }),
  batchDeleteDocuments: (data = {}) => request.post('/workspace/document/batch-delete', data),
  clearDocuments: (params = {}) => request.delete('/workspace/document/clear', { params }),
  aiAnalyzeDocuments: (data = {}) => request.post('/workspace/document/ai-analyze', data, { timeout: 0 }),
  getDocumentContent: (params = {}) => request.get('/workspace/document/get-content', { params }),
  updateDocumentContent: (data = {}) => request.post('/workspace/document/update-content', data),
  batchExportDocuments: (data = {}) => request.post('/workspace/document/batch-export', data, { responseType: 'blob' }),
  batchUploadDocuments: (workspace_id, files) => {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    return request.post(`/workspace/document/batch-upload?workspace_id=${workspace_id}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
  createDocumentFromText: (data = {}) => request.post('/workspace/document/create-text', data),
  // workspace sheets
  uploadSheet: (workspace_id, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post(`/workspace/sheet/upload?workspace_id=${workspace_id}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
  getSheetList: (params = {}) => request.get('/workspace/sheet/list', { params }),
  deleteSheet: (params = {}) => request.delete('/workspace/sheet/delete', { params }),
  exportSheet: (params = {}) => request.get('/workspace/sheet/export', { params, responseType: 'blob' }),
  batchDeleteSheets: (data = {}) => request.post('/workspace/sheet/batch-delete', data),
  batchExportSheets: (data = {}) => request.post('/workspace/sheet/batch-export', data, { responseType: 'blob' }),
  batchUploadSheets: (workspace_id, files) => {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    return request.post(`/workspace/sheet/batch-upload?workspace_id=${workspace_id}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
  csvImportSheet: (data = {}) => request.post('/workspace/sheet/csv-import', data),
  // reports
  getReportList: (params = {}) => request.get("/report/list", { params }),
  generateReport: (data = {}) => request.post("/report/generate", data, { timeout: 0 }),
  getReportById: (params = {}) => request.get("/report/get", { params }),
  updateReport: (data = {}) => request.post("/report/update", data),
  cloneReport: (data = {}) => request.post("/report/clone", data),
  deleteReport: (params = {}) => request.delete("/report/delete", { params }),
  exportReportHtml: (params = {}) => request.get("/report/export/html", { params, responseType: "blob" }),
  exportReportPdf: (params = {}) => request.get("/report/export/pdf", { params, responseType: "blob" }),
  exportReportDocx: (params = {}) => request.get("/report/export/docx", { params, responseType: "blob" }),
  // workspace analysis
  analyzeSheet: (data = {}) => request.post('/workspace/analysis/analyze', data, { timeout: 0 }),
  correlateSheets: (data = {}) => request.post('/workspace/analysis/correlate', data, { timeout: 0 }),
  correlateAnalyses: (data = {}) => request.post('/workspace/analysis/correlate-analysis', data, { timeout: 0 }),
  getAnalysisList: (params = {}) => request.get('/workspace/analysis/list', { params }),
  deleteAnalysis: (params = {}) => request.delete('/workspace/analysis/delete', { params }),
  batchDeleteAnalyses: (data = {}) => request.post('/workspace/analysis/batch-delete', data),
  clearAnalyses: (params = {}) => request.delete('/workspace/analysis/clear', { params }),
  batchExportAnalyses: (data = {}) => request.post('/workspace/analysis/batch-export', data, { responseType: 'blob' }),
  exportAnalysis: (params = {}) => request.get('/workspace/analysis/export', { params, responseType: 'blob' }),
  // workspace database import
  testMySQLConnection: (data = {}) => request.post('/workspace/database/mysql/test-connection', data, { timeout: 0 }),
  importMySQLTables: (data = {}) => request.post('/workspace/database/mysql/import', data, { timeout: 0 }),
  uploadSQLiteFile: (workspace_id, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post(`/workspace/database/sqlite/upload?workspace_id=${workspace_id}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
  importSQLiteTables: (data = {}) => request.post('/workspace/database/sqlite/import', data, { timeout: 0 }),
  getPixelAccountsForImport: () => request.get('/workspace/database/pixel/accounts'),
  getPixelTablesForImport: (params = {}) => request.get('/workspace/database/pixel/tables', { params }),
  importPixelTable: (data = {}) => request.post('/workspace/database/pixel/import', data, { timeout: 0 }),
  getRoadNetworkRegionsForImport: () => request.get('/workspace/database/road-network/regions'),
  getRoadNetworkListForImport: (params = {}) => request.get('/workspace/database/road-network/list', { params }),
  importRoadNetworkStats: (data = {}) => request.post('/workspace/database/road-network/import', data, { timeout: 0 }),
  copyToWorkspace: (data = {}) => request.post('/workspace/copy-to-workspace', data, { timeout: 0 }),
  // workspace static files
  getStaticFileList: (params = {}) => request.get('/workspace/static-file/list', { params }),
  uploadStaticFile: (workspace_id, source_type, name, description, file) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', name || '')
    formData.append('description', description || '')
    return request.post(`/workspace/static-file/upload?workspace_id=${workspace_id}&source_type=${source_type}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
  batchUploadStaticFiles: (workspace_id, source_type, name_prefix, description, files) => {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    formData.append('name_prefix', name_prefix || '')
    formData.append('description', description || '')
    return request.post(`/workspace/static-file/batch-upload?workspace_id=${workspace_id}&source_type=${source_type}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
  getStaticFileById: (params = {}) => request.get('/workspace/static-file/get', { params }),
  updateStaticFile: (data = {}) => request.put('/workspace/static-file/update', data),
  deleteStaticFile: (params = {}) => request.delete('/workspace/static-file/delete', { params }),
  batchDeleteStaticFiles: (data = {}) => request.post('/workspace/static-file/batch-delete', data),
  batchExportStaticFiles: (data = {}) => request.post('/workspace/static-file/batch-export', data, { responseType: 'blob' }),
  copyStaticFileRecords: (data = {}) => request.post('/workspace/static-file/copy-records', data),
  getStaticFileBaseUrl: () => request.get('/workspace/static-file/base-url'),
  setStaticFileBaseUrl: (data = {}) => request.put('/workspace/static-file/base-url', data),
  downloadStaticFile: (params = {}) => request.get('/workspace/static-file/download-file', { params, responseType: 'blob' }),
  getStaticFileImages: (params = {}) => request.get('/workspace/static-file/images', { params }),
  getStaticFileCVOperations: () => request.get('/workspace/static-file/cv-operations'),
  cvProcessStaticFiles: (data = {}) => request.post('/workspace/static-file/cv-process', data, { timeout: 0 }),
  aiProcessStaticFiles: (data = {}) => request.post('/workspace/static-file/ai-process', data, { timeout: 0 }),
  ocrExtractStaticFiles: (data = {}) => request.post('/workspace/static-file/ocr', data, { timeout: 0 }),
  importStaticFilesFromMaterial: (data = {}) => request.post('/workspace/static-file/import-from-material', data, { timeout: 0 }),
  getStaticFileMaterialRegions: () => request.get('/workspace/static-file/material/regions'),
  getStaticFileMaterialsByRegion: (params = {}) => request.get('/workspace/static-file/material/list-by-region', { params }),
  // vehicle
  getVehicleAccounts: () => request.get('/vehicle/accounts'),
  getVehicleCarTypes: (params = {}) => request.get('/vehicle/car-types', { params }),
  getVehicleCars: (params = {}) => request.get('/vehicle/cars', { params }),
  getVehicleStatus: (params = {}) => request.get('/vehicle/status', { params }),
  getVehicleDeviceInfo: (params = {}) => request.get('/vehicle/device-info', { params }),
  getVehicleFullCheck: (params = {}) => request.get('/vehicle/full-check', { params }),
  refreshVehicleStatus: (params = {}) => request.get('/vehicle/refresh', { params }),
  getVehicleFlow: (params = {}) => request.get('/vehicle/flow', { params }),
  // road-material
  getMaterialList: (params = {}) => request.get('/region/road-material/list', { params }),
  getMaterialById: (params = {}) => request.get('/region/road-material/get', { params }),
  updateMaterial: (data = {}) => request.put('/region/road-material/update', data),
  deleteMaterial: (params = {}) => request.delete('/region/road-material/delete', { params }),
  uploadMaterial: (region_id, name, description, file, source = 'upload') => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', name || '')
    formData.append('description', description || '')
    formData.append('source', source || 'upload')
    return request.post(`/region/road-material/upload?region_id=${region_id}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
  downloadMaterialFile: (params = {}) => request.get('/region/road-material/download-file', {
    params, responseType: 'blob', timeout: 0,
  }),
  aiProcessMaterial: (data = {}) => request.post('/region/road-material/ai-process', data, { timeout: 0 }),
  cvProcessMaterial: (data = {}) => request.post('/region/road-material/cv-process', data, { timeout: 0 }),
  getCVOperations: () => request.get('/region/road-material/cv-operations'),
  // i18n
  getI18nList: () => request.get('/i18n/list'),
  updateI18n: (data = {}) => request.put('/i18n/update', data),
  batchUpdateI18n: (data = {}) => request.put('/i18n/batch-update', data),
  exportI18n: () => request.get('/i18n/export'),
  importI18n: (data = {}) => request.post('/i18n/import', data),
  aiGenerateI18n: (data = {}) => request.post('/i18n/ai-generate', data, { timeout: 0 }),

  scanDetectI18n: () => fetch('/__i18n-scan').then(r => r.json()),  // 旧端点（依赖未安装的 npm 包，已废弃）
  scanNewFieldsI18n: () => request.get('/i18n/scan-new-fields'),      // 新端点（Python 正则，始终可用）
  processScanI18n: (data = {}) => request.post('/i18n/process-scan', data, { timeout: 0 }),
  verifyI18nBuild: () => request.post('/i18n/verify-build', {}, { timeout: 0 }),
  gitRestoreI18n: (data = {}) => request.post('/i18n/git-restore', data),
  gitModifiedFilesI18n: () => request.get('/i18n/git-modified-files'),
  batchDeleteI18n: (data = {}) => request.post('/i18n/batch-delete', data),
  // skills
  getSkillList: (params = {}) => request.get('/skill/list', { params }),
  getSkillById: (params = {}) => request.get('/skill/get', { params }),
  createSkill: (data = {}) => request.post('/skill/create', data),
  aiCreateSkill: (data = {}) => request.post('/skill/ai-create', data, { timeout: 0 }),
  updateSkill: (data = {}) => request.post('/skill/update', data),
  deleteSkill: (params = {}) => request.delete('/skill/delete', { params }),
  exportSkill: (params = {}) => request.get('/skill/export', { params, responseType: 'blob' }),
  getSkillUsers: () => request.get('/skill/users'),
  // road-network workbench
  getRoadNetworksForRegion: (region_id) => request.get('/region/road-network/list-for-region', { params: { region_id } }),
  analyzeNetwork: (params = {}) => request.get('/region/road-network/analyze', { params, timeout: 0  }),
  filterNetwork: (data = {}) => request.post('/region/road-network/filter', data, { timeout: 0 }),
  segmentNetwork: (data = {}) => request.post('/region/road-network/segment', data, { timeout: 0 }),
  warmTileCache: (params = {}) => request.post('/region/road-network/warm-cache', null, { params }),
  clearTileCache: (params = {}) => request.delete('/region/road-network/tiles/cache', { params }),
  // road fields
  getRoadFields: (params = {}) => request.get('/region/road-network/fields', { params , timeout: 0 }),
  exportRoadFields: (params = {}) => request.get('/region/road-network/fields/export', { params, timeout: 0 }),
  importRoadFields: (data = {}) => request.post('/region/road-network/fields/import', data, { timeout: 0 }),
  batchUpdateRoadFields: (data = {}) => request.post('/region/road-network/fields/batch-update', data, { timeout: 0 }),
  aiProcessRoadFields: (data = {}) => request.post('/region/road-network/fields/ai-process', data, { timeout: 0 }),
  // filter templates
  getFilterTemplates: () => request.get('/region/road-network/filter-templates'),
  createFilterTemplate: (data = {}) => request.post('/region/road-network/filter-templates/create', data),
  deleteFilterTemplate: (params = {}) => request.delete('/region/road-network/filter-templates/delete', { params }),
}