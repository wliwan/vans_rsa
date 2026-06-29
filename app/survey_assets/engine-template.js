/**
 * Survey Engine v3.0 — 由后端自动注入，AI 无需感知
 *
 * 职责：数据采集 / 本地保存恢复 / 服务器提交 / 动态表格管理
 * AI 只需声明 data-* 属性，引擎处理所有逻辑。
 */
(function () {
  'use strict';
  var cfg = window.__SURVEY_CONFIG__ || {};
  var TOKEN = cfg.surveyToken || '__SURVEY_TOKEN__';
  var LS_KEY = 'survey_' + TOKEN;

  // ── 数据采集 ──
  function collectData() {
    var data = {}, seen = {};
    var els = document.querySelectorAll('[name]');
    for (var i = 0; i < els.length; i++) {
      var el = els[i], nm = el.getAttribute('name');
      if (!nm) continue;
      if ((el.type === 'radio' || el.type === 'checkbox') && !el.checked) continue;
      if (el.type === 'checkbox' && /\[\]$/.test(nm)) {
        if (!seen[nm]) { data[nm] = []; seen[nm] = true; }
        data[nm].push(el.value);
      } else {
        data[el.id || nm] = el.value;
      }
    }
    return data;
  }

  // ── 本地保存 ──
  function saveLocal() {
    try {
      var data = collectData();
      var list = JSON.parse(localStorage.getItem(LS_KEY) || '[]');
      list.push({ data: data, savedAt: new Date().toISOString() });
      localStorage.setItem(LS_KEY, JSON.stringify(list));
      showToast('已保存到本地 \u2713', 'success');
    } catch (e) { showToast('保存失败：' + e.message, 'error'); }
  }

  // ── 恢复数据（含兜底） ──
  function restoreData(data) {
    if (!data) return { restored: 0, skipped: 0 };
    var restored = 0, skipped = 0;

    for (var key in data) {
      if (!/\[\]$/.test(key)) continue;
      var vals = Array.isArray(data[key]) ? data[key] : [data[key]];
      var cbs = document.querySelectorAll('input[type="checkbox"][name="' + key + '"]');
      var seenValues = {};
      for (var ci = 0; ci < cbs.length; ci++) {
        cbs[ci].checked = vals.indexOf(cbs[ci].value) !== -1;
        seenValues[cbs[ci].value] = true;
      }
      // 重建 DOM 中不存在的 checkbox（动态添加后刷新页面丢失的项）
      for (var vi = 0; vi < vals.length; vi++) {
        var v = vals[vi];
        if (seenValues[v]) continue;
        var container = document.querySelector('[data-survey-custom-container="' + key + '"]');
        if (!container && cbs.length > 0) {
          var p = cbs[0].parentNode;
          container = p && p.parentNode ? p.parentNode : document.body;
        }
        if (!container) container = document.body;
        var wrapper = document.createElement('div');
        var cb = document.createElement('input');
        cb.type = 'checkbox'; cb.name = key; cb.value = v;
        cb.checked = true; cb.style.cssText = 'margin-right:6px;';
        // id: 去掉 [] 后缀 + _restored_ + 序号
        var base = key.replace(/\[\]$/, '');
        cb.id = base + '_restored_' + vi;
        var lbl = document.createElement('label');
        lbl.appendChild(cb);
        lbl.appendChild(document.createTextNode(v));
        wrapper.appendChild(lbl);
        container.appendChild(wrapper);
        restored++;
      }
      restored++;
    }

    for (var key in data) {
      if (/\[\]$/.test(key)) continue;
      var v = data[key];
      ensureRowForKey(key);
      var el = document.getElementById(key) || document.querySelector('[name="' + key + '"]');
      if (!el) {
        try {
          var hidden = document.createElement('input');
          hidden.type = 'hidden'; hidden.name = key; hidden.id = key;
          hidden.value = String(v == null ? '' : v);
          document.body.appendChild(hidden);
          restored++;
        } catch (e) { skipped++; }
        continue;
      }
      if (el.type === 'radio') {
        var rn = el.getAttribute('name');
        var radios = document.querySelectorAll('[name="' + rn + '"]');
        for (var ri = 0; ri < radios.length; ri++)
          radios[ri].checked = (radios[ri].value === String(v));
      } else if (el.type === 'checkbox') {
        el.checked = (v === true || v === 'true' || v === 'on' || v === '1' || String(v) === el.value);
      } else {
        el.value = v;
      }
      restored++;
    }
    return { restored: restored, skipped: skipped };
  }

  function restoreLast() {
    try {
      var list = JSON.parse(localStorage.getItem(LS_KEY) || '[]');
      if (list.length === 0) return;
      var record = list[list.length - 1];
      if (!record || !record.data) return;
      ensureAllRows(record.data);
      restoreData(record.data);
      showToast('已恢复上次保存 \u2713', 'success');
    } catch (e) {}
  }

  // ── 提交 ──
  function doSubmit() {
    var data = collectData();
    var payload = {
      survey_token: TOKEN,
      submitter_name: '',
      content: JSON.stringify(data),
      word_count: JSON.stringify(data).replace(/\s/g, '').length,
      raw_data: data,
      save_type: 'submit'
    };
    fetch('/api/v1/survey/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function (r) { return r.json(); })
      .then(function (res) {
        showToast(res.code === 200 ? '提交成功 \u2713' : '提交失败：' + (res.msg || '未知错误'),
          res.code === 200 ? 'success' : 'error');
        if (res.code === 200) localStorage.removeItem(LS_KEY);
      })
      .catch(function (err) { showToast('提交失败：' + err.message, 'error'); });
  }

  // ── Toast ──
  function showToast(msg, type) {
    type = type || 'info';
    var colors = {
      success: 'background:#e6f7e6;color:#2e7d32;border:1px solid #a5d6a7;',
      error: 'background:#fdecea;color:#c62828;border:1px solid #ef9a9a;',
      info: 'background:#e3f2fd;color:#1565c0;border:1px solid #90caf9;'
    };
    var t = document.createElement('div');
    t.textContent = msg;
    t.style.cssText = 'position:fixed;top:20px;right:20px;z-index:99999;padding:12px 24px;border-radius:6px;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,0.15);animation:svFadeIn 0.3s ease;font-family:sans-serif;' + (colors[type] || colors.info);
    document.body.appendChild(t);
    setTimeout(function () { t.style.opacity = '0'; t.style.transition = 'opacity 0.3s'; }, 2200);
    setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 2600);
  }

  // ═══════ 动态表格引擎 ═══════
  var tableDefs = {};

  function initTables() {
    var tables = document.querySelectorAll('[data-survey-table]');
    for (var i = 0; i < tables.length; i++) registerTable(tables[i]);
    bindTableAddButtons();
  }

  function registerTable(tableEl) {
    var name = tableEl.getAttribute('data-survey-table');
    if (!name || tableDefs[name]) return;
    var colsStr = tableEl.getAttribute('data-survey-columns') || '';
    var cols = [], types = [];
    var parts = colsStr.split(',');
    for (var j = 0; j < parts.length; j++) {
      var pair = parts[j].split(':');
      var rawType = (pair.pop() || 'text').trim();
      var colName = (pair.pop() || '').trim();
      // select 类型: 倒数第二段可能是 "select"，需吞并
      if (colName === 'select') {
        rawType = 'select:' + rawType;
        colName = (pair.pop() || colName).trim();
      }
      if (!colName) continue;
      cols.push(colName);
      types.push(rawType || 'text');
    }
    if (cols.length === 0) return;
    var tbody = tableEl.querySelector('tbody');
    if (!tbody) return;
    // 只将含表单控件的行视为数据行，忽略纯 th 行
    var allTrs = tbody.querySelectorAll('tr');
    var dataRows = [];
    for (var ri = 0; ri < allTrs.length; ri++) {
      if (allTrs[ri].querySelector('input, select, textarea')) dataRows.push(allTrs[ri]);
    }
    var templateRow = dataRows.length > 0 ? dataRows[0] : null;
    tableDefs[name] = { cols: cols, types: types, tbody: tbody, templateRow: templateRow, rowCount: 0 };
    if (dataRows.length === 0) {
      addTableRow(name);
    } else {
      tableDefs[name].rowCount = dataRows.length;
      for (var r = 0; r < dataRows.length; r++) bindRowDeleteBtn(dataRows[r], name);
    }
  }

  function addTableRow(name) {
    var def = tableDefs[name]; if (!def) return;
    var idx = def.rowCount++;
    var tr;
    // 模板行必须包含表单控件，否则从零创建
    if (def.templateRow && def.templateRow.querySelector('input, select, textarea')) {
      tr = def.templateRow.cloneNode(true);
      var inputs = tr.querySelectorAll('input, select, textarea');
      for (var k = 0; k < inputs.length; k++) {
        inputs[k].value = '';
        if (inputs[k].type === 'checkbox' || inputs[k].type === 'radio')
          inputs[k].checked = false;
        refreshElementId(inputs[k], name, def.cols, idx);
      }
    } else {
      tr = document.createElement('tr');
      for (var j = 0; j < def.cols.length; j++) {
        var td = document.createElement('td');
        var inp = makeTableInput(name, def.cols[j], def.types[j], idx);
        td.appendChild(inp);
        tr.appendChild(td);
      }
    }
    var tdDel = document.createElement('td');
    var delBtn = document.createElement('button');
    delBtn.type = 'button'; delBtn.className = 'survey-row-delete';
    delBtn.textContent = '\u00d7'; delBtn.title = '删除此行';
    tdDel.appendChild(delBtn); tr.appendChild(tdDel);
    def.tbody.appendChild(tr);
    bindRowDeleteBtn(delBtn, name);
    return tr;
  }

  function makeTableInput(tableName, col, type, idx) {
    var id = tableName + '_' + col + '_' + idx;
    // select 类型: select:opt1/opt2/...
    if (type.indexOf('select:') === 0) {
      var sel = document.createElement('select');
      sel.id = id; sel.name = id;
      var opts = type.substring(7).split('/');
      for (var oi = 0; oi < opts.length; oi++) {
        var opt = document.createElement('option');
        opt.value = opts[oi]; opt.textContent = opts[oi];
        if (oi === 0) opt.selected = true;
        sel.appendChild(opt);
      }
      return sel;
    }
    var inp = document.createElement('input');
    if (type === 'number') inp.type = 'number';
    else if (type === 'date') inp.type = 'date';
    else inp.type = 'text';
    inp.id = id; inp.name = id; inp.placeholder = col;
    return inp;
  }

  function refreshElementId(el, tableName, cols, newIdx) {
    var old = el.id || el.getAttribute('name') || '';
    for (var c = 0; c < cols.length; c++) {
      var prefix = tableName + '_' + cols[c] + '_';
      if (old.indexOf(prefix) === 0) {
        var newId = prefix + newIdx; el.id = newId;
        el.setAttribute('name', newId); return;
      }
    }
  }

  function bindRowDeleteBtn(btn, name) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      var tr = btn.closest('tr'); if (!tr) return;
      var tbody = tableDefs[name] ? tableDefs[name].tbody : tr.parentNode;
      if (tbody.querySelectorAll('tr').length <= 1) {
        showToast('至少保留一行', 'info'); return;
      }
      tr.parentNode.removeChild(tr);
    });
  }

  function bindTableAddButtons() {
    var btns = document.querySelectorAll('[data-survey-table-add]');
    for (var i = 0; i < btns.length; i++) {
      (function (b) {
        var n = b.getAttribute('data-survey-table-add');
        b.addEventListener('click', function (e) { e.preventDefault(); addTableRow(n); });
      })(btns[i]);
    }
  }

  // ── 恢复辅助：根据数据中实际存在的索引创建行（修复空洞）──
  function ensureAllRows(data) {
    if (!data) return;
    for (var name in tableDefs) ensureTableRows(name, data);
  }

  function ensureTableRows(name, data) {
    var def = tableDefs[name]; if (!def || !def.cols) return;
    var prefix = name + '_';
    var indices = {};
    for (var key in data) {
      if (key.indexOf(prefix) !== 0) continue;
      var idx = parseInt(key.split('_').pop(), 10);
      if (!isNaN(idx)) indices[idx] = true;
    }
    var sorted = Object.keys(indices).map(Number).sort(function (a, b) { return a - b; });
    if (sorted.length === 0) return;
    var current = def.tbody.querySelectorAll('tr').length;
    for (var i = 0; i < sorted.length; i++) {
      while (current <= sorted[i]) { addTableRow(name); current++; }
    }
  }

  function ensureRowForKey(key) {
    for (var name in tableDefs) {
      var prefix = name + '_';
      if (key.indexOf(prefix) !== 0) continue;
      var idx = parseInt(key.split('_').pop(), 10);
      if (isNaN(idx)) continue;
      var def = tableDefs[name];
      var current = def.tbody.querySelectorAll('tr').length;
      while (current <= idx) { addTableRow(name); current++; }
      return;
    }
  }

  // ── 绑定 ──
  function bind() {
    document.addEventListener('click', function (e) {
      var b = e.target.closest('.sv-save');
      if (b) { e.preventDefault(); saveLocal(); return; }
      b = e.target.closest('.sv-submit');
      if (b) { e.preventDefault(); doSubmit(); }
    });
    var inputs = document.querySelectorAll('input[name], textarea[name], select[name]');
    var has = false;
    for (var i = 0; i < inputs.length; i++) {
      var el = inputs[i];
      if (el.type === 'checkbox' || el.type === 'radio') {
        if (el.checked) { has = true; break; }
      } else if (el.value && el.value.trim()) { has = true; break; }
    }
    // 延迟恢复，确保在所有自定义脚本初始化之后执行
    // 始终尝试恢复（有数据则恢复，无数据则静默跳过）
    setTimeout(function () { restoreLast(); }, 150);
  }

  var style = document.createElement('style');
  style.textContent = '@keyframes svFadeIn{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:translateY(0)}}';
  document.head.appendChild(style);

  initTables();
  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', bind);
  else bind();

  window.__engineCollectData = collectData;
  window.__engineRestoreData = restoreData;
  window.__engineSaveLocal = saveLocal;
  window.__engineRestoreLast = restoreLast;
  window.__engineDoSubmit = doSubmit;
  window.__engineShowToast = showToast;
  window.__engineAddTableRow = addTableRow;
})();
