import { request } from '@/utils'

export default {
  login: (data) => request.post('/base/access_token', data, { noNeedToken: true }),
  getUserInfo: () => request.get('/base/userinfo'),
  getUserMenu: (params = {}) => request.get('/base/usermenu', { params }),
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
  aiAnalyzeViews: (data = {}) => request.post('/menu/ai-analyze-views', data, { timeout: 0 }),
  batchSaveMenus: (data = {}) => request.post('/menu/batch-save', data),
  exportMenus: () => request.get('/menu/export', { responseType: 'blob' }),
  // menu i18n
  getMenuI18nList: (params = {}) => request.get('/menu/i18n/list', { params }),
  saveMenuI18n: (data = {}) => request.post('/menu/i18n/save', data),
  deleteMenuI18n: (params = {}) => request.delete('/menu/i18n/delete', { params }),
  aiGenerateMenuI18n: (data = {}) => request.post('/menu/i18n/ai-generate', data, { timeout: 0 }),
  exportMenuI18n: (params = {}) => request.get('/menu/i18n/export', { params }),
  importMenuI18n: (data = {}) => request.post('/menu/i18n/import', data),
  importMenus: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/menu/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
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
  syncDefectsStream: (data = {}) => request.post('/defect/sync-stream', data, { timeout: 0, responseType: 'stream' }),
  clearDefects: (data = {}) => request.post('/defect/clear', data),
  // tracks
  getTrackAccounts: () => request.get('/track/accounts'),
  getTrackCarTypes: (params = {}) => request.get('/track/car-types', { params }),
  getTrackCars: (params = {}) => request.get('/track/cars', { params }),
  getTrackList: (params = {}) => request.get('/track/list', { params }),
  syncTracks: (data = {}) => request.post('/track/sync', data, { timeout: 0 }),
  syncTracksStream: (data = {}) => request.post('/track/sync-stream', data, { timeout: 0, responseType: 'stream' }),
  clearTracks: (data = {}) => request.post('/track/clear', data),
  // regions
  getRegionList: (params = {}) => request.get('/region/list', { params }),
  getRegionById: (regionId) => request.get('/region/get', { params: { region_id: regionId } }),
  createRegion: (data = {}) => request.post('/region/create', data),
  updateRegion: (data = {}) => request.post('/region/update', data),
  deleteRegion: (params = {}) => request.delete('/region/delete', { params }),
  getRegionBoundaries: (params = {}) => request.get('/region/boundaries', { params }),
  getRegionRoadNetworks: (params = {}) => request.get('/region/road-networks', { params }),
  downloadRegionBoundary: (data = {}) => request.post('/region/download-boundary', data, { timeout: 0 }),
  deleteRegionBoundary: (params = {}) => request.delete('/region/boundary/delete', { params }),
  downloadRegionRoadNetwork: (data = {}) => request.post('/region/road-network/download', data, { timeout: 0 }),
  getRoadNetworkStatus: (regionId) => request.get('/region/road-network/status', { params: { region_id: regionId } }),
  downloadRoadNetwork: (data = {}) => request.post('/region/road-network/download', data, { timeout: 0 }),
  downloadRoadNetworkFile: (params = {}) => request.get('/region/road-network/download-file', { params, responseType: 'blob' }),
  deleteRoadNetwork: (params = {}) => request.delete('/region/road-network/delete', { params }),
  clearRoadNetworks: (params = {}) => request.delete('/region/road-network/clear', { params }),
  setActiveBoundary: (data = {}) => request.post('/region/boundary/set-active', data),
  setActiveRoadNetwork: (data = {}) => request.post('/region/road-network/set-active', data),
  getActiveBoundary: (params = {}) => request.get('/region/boundary/active', { params }),
  getActiveRoadNetwork: (params = {}) => request.get('/region/road-network/active', { params }),
  getRegionCenter: (params = {}) => request.get('/region/center', { params }),
  getRegionChildren: (parentId) => request.get('/region/children', { params: { parent_id: parentId } }),
  getRegionTree: () => request.get('/region/tree'),
  importRegions: () => request.post('/region/import', {}, { timeout: 0 }),
  clearRegions: () => request.post('/region/clear', {}, { timeout: 0 }),
  exportRegions: (data = {}) => request.post('/region/export', data),
  fillGeonames: (forceDownload = false, proxy = null) => request.post('/region/fill-geonames', { force_download: forceDownload, proxy }, { timeout: 0 }),
  getGeonamesProgress: () => request.get('/region/fill-geonames/progress'),
  batchUpdateRegions: (data = {}) => request.post('/region/batch-update', data),
  // vehicle
  getVehicleList: (params = {}) => request.get('/vehicle/list', { params }),
  getVehicleById: (params = {}) => request.get('/vehicle/get', { params }),
  createVehicle: (data = {}) => request.post('/vehicle/create', data),
  updateVehicle: (data = {}) => request.post('/vehicle/update', data),
  deleteVehicle: (params = {}) => request.delete('/vehicle/delete', { params }),
  getVehicleAccounts: () => request.get('/vehicle/accounts'),
  getVehicleCarTypes: (params = {}) => request.get('/vehicle/car-types', { params }),
  getVehicleCars: (params = {}) => request.get('/vehicle/cars', { params }),
  checkVehicleStatus: (params = {}) => request.get('/vehicle/status', { params }),
  getVehicleDeviceInfo: (params = {}) => request.get('/vehicle/device-info', { params }),
  fullCheckVehicle: (params = {}) => request.get('/vehicle/full-check', { params }),
  refreshVehicleStatus: (params = {}) => request.get('/vehicle/refresh', { params }),
  queryVehicleFlow: (params = {}) => request.get('/vehicle/flow', { params }),
  // road-material
  getRoadMaterialList: (params = {}) => request.get('/road-material/list', { params }),
  getRoadMaterialById: (params = {}) => request.get('/road-material/get', { params }),
  createRoadMaterial: (data = {}) => request.post('/road-material/create', data),
  updateRoadMaterial: (data = {}) => request.post('/road-material/update', data),
  deleteRoadMaterial: (params = {}) => request.delete('/road-material/delete', { params }),
  // road-material upload
  uploadRoadMaterial: (file, check_duplicate = false, onUploadProgress) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post(`/road-material/upload?check_duplicate=${check_duplicate}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
      onUploadProgress,
    })
  },
  // road-material Export
  exportRoadMaterialImages: (params = {}) => request.get('/road-material/export-images', {
    params, responseType: 'blob', timeout: 0,
  }),
  // road-material Delete
  batchDeleteRoadMaterials: (data = {}) => request.post('/road-material/batch-delete', data),
  // road-material Batch move
  moveRoadMaterialsToDirectory: (data = {}) => request.post('/road-material/move-to-directory', data),
  // road-material Batch download
  batchDownloadRoadMaterials: (data = {}) => request.post('/road-material/batch-download', data),
  getBatchDownloadProgress: (params = {}) => request.get('/road-material/batch-download-progress', { params }),
  // ai-proxy
  getAIProxyList: (params = {}) => request.get('/ai-proxy/list', { params }),
  getAIProxyByName: (name) => request.get('/ai-proxy/get', { params: { name } }),
  createAIProxy: (data = {}) => request.post('/ai-proxy/create', data),
  updateAIProxy: (data = {}) => request.post('/ai-proxy/update', data),
  deleteAIProxy: (params = {}) => request.delete('/ai-proxy/delete', { params }),
  getAIProxyUsers: () => request.get('/ai-proxy/users'),
  // workspace
  getWorkspaceList: (params = {}) => request.get('/workspace/list', { params }),
  getWorkspaceById: (params = {}) => request.get('/workspace/get', { params }),
  createWorkspace: (data = {}) => request.post('/workspace/create', data),
  updateWorkspace: (data = {}) => request.post('/workspace/update', data),
  deleteWorkspace: (params = {}) => request.delete('/workspace/delete', { params }),
  getWorkspaceUsers: () => request.get('/workspace/users'),
  // workspace documents
  getDocumentList: (params = {}) => request.get('/workspace/document/list', { params }),
  getDocumentById: (params = {}) => request.get('/workspace/document/get', { params }),
  createDocument: (data = {}) => request.post('/workspace/document/create', data, { timeout: 0 }),
  deleteDocument: (params = {}) => request.delete('/workspace/document/delete', { params }),
  uploadDocument: (workspace_id, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post(`/workspace/document/upload?workspace_id=${workspace_id}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
  createDocumentFromText: (data = {}) => request.post('/workspace/document/create-text', data),
  importDocumentFromSurvey: (data = {}) => request.post('/workspace/document/import-from-survey', data),
  batchUploadDocuments: (workspace_id, files) => {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    return request.post(`/workspace/document/batch-upload?workspace_id=${workspace_id}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
  downloadDocument: (params = {}) => request.get('/workspace/document/download', { params, responseType: 'blob' }),
  batchDeleteDocuments: (data = {}) => request.post('/workspace/document/batch-delete', data),
  batchExportDocuments: (data = {}) => request.post('/workspace/document/batch-export', data, { responseType: 'blob' }),
  clearDocuments: (params = {}) => request.delete('/workspace/document/clear', { params }),
  aiAnalyzeDocuments: (data = {}) => request.post('/workspace/document/ai-analyze', data, { timeout: 0 }),
  getDocumentContent: (params = {}) => request.get('/workspace/document/get-content', { params }),
  updateDocumentContent: (data = {}) => request.post('/workspace/document/update-content', data),
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
  previewReportSources: (data = {}) => request.post("/report/preview-sources", data, { timeout: 0 }),
  getReportList: (params = {}) => request.get("/report/list", { params }),
  generateReport: (data = {}) => request.post("/report/generate", data, { timeout: 0 }),
  getReportGenerateProgress: (params = {}) => request.get("/report/generate-progress", { params }),
  getReportGenerateResult: (params = {}) => request.get("/report/generate-result", { params }),
  getReportById: (params = {}) => request.get("/report/get", { params }),
  updateReport: (data = {}) => request.post("/report/update", data),
  cloneReport: (data = {}) => request.post("/report/clone", data),
  cloneReportTranslate: (data = {}) => request.post("/report/clone-translate", data, { timeout: 0 }),
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
  getStaticFileBaseUrl: () => request.get('/workspace/static-file/base-url'),
  setStaticFileBaseUrl: (data = {}) => request.put('/workspace/static-file/base-url', data),
  downloadStaticFile: (params = {}) => request.get('/workspace/static-file/download-file', { params, responseType: 'blob' }),
  getStaticFileImages: (params = {}) => request.get('/workspace/static-file/images', { params }),
  // system config
  getSystemConfigList: (params = {}) => request.get('/system-config/list', { params }),
  getSystemConfigByKey: (key) => request.get('/system-config/get', { params: { key } }),
  setSystemConfig: (data = {}) => request.post('/system-config/set', data),
  getDownloadConfig: () => request.get('/system-config/download'),
  updateDownloadConfig: (data = {}) => request.post('/system-config/download', data),
  testProxy: (data = {}) => request.post('/system-config/test-proxy', data),
  getRoadHighwayStyle: () => request.get('/system-config/road-highway-style'),
  updateRoadHighwayStyle: (data = {}) => request.post('/system-config/road-highway-style', data),
  resetRoadHighwayStyle: () => request.delete('/system-config/road-highway-style'),
  // i18n
  getI18nList: (params = {}) => request.get('/i18n/list', { params }),
  createI18n: (data = {}) => request.post('/i18n/create', data),
  updateI18n: (data = {}) => request.post('/i18n/update', data),
  getI18nById: (params = {}) => request.get('/i18n/get', { params }),
  deleteI18n: (params = {}) => request.delete('/i18n/delete', { params }),
  getI18nBaseLang: () => request.get('/i18n/base-lang'),
  i18nApplyToVue: (data = {}) => request.post('/i18n/apply-to-vue', data),
  i18nScanFiles: () => request.get('/i18n/scan-files'),
  scanTranslateI18n: (data = {}) => request.post('/i18n/scan-translate', data, { timeout: 0 }),
  processScanI18n: (data = {}) => request.post('/i18n/process-scan', data, { timeout: 0 }),
  verifyI18nBuild: () => request.post('/i18n/verify-build', {}, { timeout: 0 }),
  gitRestoreI18n: (data = {}) => request.post('/i18n/git-restore', data),
  gitModifiedFilesI18n: () => request.get('/i18n/git-modified-files'),
  batchDeleteI18n: (data = {}) => request.post('/i18n/batch-delete', data),
  batchUpdateI18n: (data = {}) => request.put('/i18n/batch-update', data),
  exportI18n: () => request.get('/i18n/export'),
  importI18n: (data = {}) => request.post('/i18n/import', data),
  aiGenerateI18n: (data = {}) => request.post('/i18n/ai-generate', data, { timeout: 0 }),
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
  // boundary extract
  extractBoundary: (data = {}) => request.post('/region/road-network/extract-boundary', data, { timeout: 0 }),
  // filter templates
  getFilterTemplates: () => request.get('/region/road-network/filter-templates'),
  createFilterTemplate: (data = {}) => request.post('/region/road-network/filter-templates/create', data),
  deleteFilterTemplate: (params = {}) => request.delete('/region/road-network/filter-templates/delete', { params }),
  // survey - 调研问卷
  getSurveyList: (params = {}) => request.get('/survey/list', { params }),
  getSurveyById: (survey_id) => request.get('/survey/get', { params: { survey_id } }),
  createSurvey: (data = {}) => request.post('/survey/create', data, { timeout: 0 }),
  updateSurvey: (data = {}) => request.post('/survey/update', data),
  deleteSurvey: (params = {}) => request.delete('/survey/delete', { params }),
  getSurveySubmissions: (params = {}) => request.get('/survey/submissions', { params }),
  deleteSurveySubmission: (params = {}) => request.delete('/survey/submission/delete', { params }),
  getSurveyHtml: (params = {}) => request.get('/survey/html', { params }),
  getSurveyRisk: (params = {}) => request.get('/survey/risk', { params }),
  getSurveyCreateProgress: (params = {}) => request.get('/survey/create-progress', { params }),
  getSurveyCreateResult: (params = {}) => request.get('/survey/create-result', { params }),
  // deploy - 热更新
  updateFrontend: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/deploy/update-frontend', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
  updateBackend: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/deploy/update-backend', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0,
    })
  },
}
  // 标签