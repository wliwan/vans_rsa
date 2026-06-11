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
  getAIProxyById: (params = {}) => request.get('/ai-proxy/get', { params }),
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
  getAnalysisList: (params = {}) => request.get('/workspace/analysis/list', { params }),
  deleteAnalysis: (params = {}) => request.delete('/workspace/analysis/delete', { params }),
  batchDeleteAnalyses: (data = {}) => request.post('/workspace/analysis/batch-delete', data),
  clearAnalyses: (params = {}) => request.delete('/workspace/analysis/clear', { params }),
  batchExportAnalyses: (data = {}) => request.post('/workspace/analysis/batch-export', data, { responseType: 'blob' }),
  exportAnalysis: (params = {}) => request.get('/workspace/analysis/export', { params, responseType: 'blob' }),
  // vehicle
  getVehicleAccounts: () => request.get('/vehicle/accounts'),
  getVehicleCarTypes: (params = {}) => request.get('/vehicle/car-types', { params }),
  getVehicleCars: (params = {}) => request.get('/vehicle/cars', { params }),
  getVehicleStatus: (params = {}) => request.get('/vehicle/status', { params }),
  getVehicleDeviceInfo: (params = {}) => request.get('/vehicle/device-info', { params }),
  getVehicleFullCheck: (params = {}) => request.get('/vehicle/full-check', { params }),
  refreshVehicleStatus: (params = {}) => request.get('/vehicle/refresh', { params }),
  getVehicleFlow: (params = {}) => request.get('/vehicle/flow', { params }),
  // skills
  getSkillList: (params = {}) => request.get('/skill/list', { params }),
  getSkillById: (params = {}) => request.get('/skill/get', { params }),
  createSkill: (data = {}) => request.post('/skill/create', data),
  updateSkill: (data = {}) => request.post('/skill/update', data),
  deleteSkill: (params = {}) => request.delete('/skill/delete', { params }),
  exportSkill: (params = {}) => request.get('/skill/export', { params, responseType: 'blob' }),
  getSkillUsers: () => request.get('/skill/users'),
  // road-network workbench
  getRoadNetworksForRegion: (region_id) => request.get('/region/road-network/list-for-region', { params: { region_id } }),
  analyzeNetwork: (params = {}) => request.get('/region/road-network/analyze', { params, timeout: 0  }),
  filterNetwork: (data = {}) => request.post('/region/road-network/filter', data, { timeout: 0 }),
  segmentNetwork: (data = {}) => request.post('/region/road-network/segment', data, { timeout: 0 }),
}
