/**
 * 跨境业务企业信息查询工具 — 前端状态机
 * 状态: idle → uploading → running → done / cancelled
 */

const API_BASE = '';

const DEFAULTS = {
  deepseek_official: { base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  claude_proxy:      { base_url: '', model: 'claude-sonnet-4-6' },
};

const STORAGE_KEY = 'cbt_config_v2';

// 自定义字段 ID 计数器
let _customFieldCounter = 0;

const app = (() => {
  let state = {
    stage: 'idle',
    llmProvider: 'deepseek_official',
    metaInfo: null,
    file: null,
    jobId: null,
    eventSource: null,
    total: 0,
    completed: 0,
    failed: 0,
    skipped: 0,
    // 字段状态：key=field.id, value=true/false（是否启用）
    fieldEnabled: {},
    // 字段目录：包含内置字段 + 运行时添加的自定义字段
    fieldCatalog: [],
  };

  // 公司索引和 trace 数据
  const _nameToIdx = {};
  const _traceData = {};

  // ── 初始化 ────────────────────────────────────────────────────
  async function init() {
    loadSavedConfig();
    bindSliders();
    await fetchMeta();
    updateSubmitBtn();
    updateSearchLimitHint();
  }

  async function fetchMeta() {
    try {
      const resp = await fetch(`${API_BASE}/api/meta`);
      if (!resp.ok) return;
      state.metaInfo = await resp.json();
      applyMeta();
    } catch (_) {}
  }

  function applyMeta() {
    const meta = state.metaInfo;
    if (!meta) return;

    // 搜索源预置 Key 徽章
    const metasoProv = meta.search_providers?.find(p => p.id === 'metaso');
    const baiduProv  = meta.search_providers?.find(p => p.id === 'baidu');
    const volProv    = meta.search_providers?.find(p => p.id === 'volcengine');
    if (metasoProv?.has_preset_key) document.getElementById('metasoPresetBadge').style.display = 'inline';
    if (baiduProv?.has_preset_key)  document.getElementById('baiduPresetBadge').style.display  = 'inline';
    if (volProv?.has_preset_key)    document.getElementById('volcenginePresetBadge').style.display = 'inline';

    // 字段目录（内置字段来自后端，确保前后端一致）
    if (meta.field_catalog?.length) {
      const backendFields = meta.field_catalog.map(f => ({
        ...f,
        is_builtin: true,
      }));
      const customFields = state.fieldCatalog.filter(f => !f.is_builtin);
      state.fieldCatalog = [...backendFields, ...customFields];

      backendFields.forEach(f => {
        if (!(f.id in state.fieldEnabled)) {
          state.fieldEnabled[f.id] = f.enabled_by_default !== false;
        }
      });
    }

    refreshFieldPanel();
    refreshLLMPresetBadge();
  }

  function refreshLLMPresetBadge() {
    const meta = state.metaInfo;
    if (!meta) return;
    const provider = meta.llm_providers?.find(p => p.id === state.llmProvider);
    document.getElementById('llmPresetBadge').style.display = provider?.has_preset_key ? 'inline' : 'none';
  }

  // ── 字段面板渲染 ──────────────────────────────────────────────
  function refreshFieldPanel() {
    const summaryFields = state.fieldCatalog.filter(f => f.group === 'summary' && f.is_builtin);
    const customFields  = state.fieldCatalog.filter(f => !f.is_builtin);

    renderFieldList('fieldListSummary', summaryFields);
    renderFieldList('fieldListCustom',  customFields, true);

    // 更新计数
    const sumEnabled = summaryFields.filter(f => state.fieldEnabled[f.id]).length;
    const cusEnabled = customFields.filter(f => state.fieldEnabled[f.id]).length;
    document.getElementById('summaryCount').textContent = `${sumEnabled}/${summaryFields.length}`;
    document.getElementById('customCount').textContent  = `${cusEnabled}/${customFields.length}`;

    const customBlock = document.getElementById('customFieldsBlock');
    customBlock.style.display = customFields.length ? 'block' : 'none';
  }

  function renderFieldList(containerId, fields, isDeletable = false) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    fields.forEach(f => {
      const row = document.createElement('div');
      row.className = 'field-check-row';
      const checked = state.fieldEnabled[f.id] ? 'checked' : '';
      const typeTag = `<span class="field-type-tag">${f.field_type || ''}</span>`;
      const delBtn  = isDeletable
        ? `<button class="btn-field-del" title="删除" onclick="app.deleteCustomField('${f.id}')">×</button>`
        : '';
      row.innerHTML = `
        <label class="field-check-label" title="${escHtml(f.instruction || '')}">
          <input type="checkbox" class="field-checkbox" data-field-id="${f.id}"
            ${checked} onchange="app.onFieldToggle('${f.id}', this.checked)" />
          <span class="field-check-name">${escHtml(f.label)}</span>
          ${typeTag}
        </label>
        ${delBtn}`;
      container.appendChild(row);
    });
  }

  function onFieldToggle(fieldId, checked) {
    state.fieldEnabled[fieldId] = checked;
    refreshFieldCounters();
    saveConfig();
  }

  function refreshFieldCounters() {
    const summaryFields = state.fieldCatalog.filter(f => f.group === 'summary' && f.is_builtin);
    const customFields  = state.fieldCatalog.filter(f => !f.is_builtin);
    const sumEnabled = summaryFields.filter(f => state.fieldEnabled[f.id]).length;
    const cusEnabled = customFields.filter(f => state.fieldEnabled[f.id]).length;
    document.getElementById('summaryCount').textContent = `${sumEnabled}/${summaryFields.length}`;
    document.getElementById('customCount').textContent  = `${cusEnabled}/${customFields.length}`;
  }

  function toggleFieldGroup(group) {
    const listId  = 'fieldListSummary';
    const arrowId = 'summaryArrow';
    const list    = document.getElementById(listId);
    const arrow   = document.getElementById(arrowId);
    if (!list) return;
    const collapsed = list.style.display === 'none';
    list.style.display  = collapsed ? '' : 'none';
    arrow.textContent   = collapsed ? '▾' : '▸';
  }

  function selectAllFields() {
    state.fieldCatalog.forEach(f => { state.fieldEnabled[f.id] = true; });
    refreshFieldPanel();
    _syncCheckboxes();
    saveConfig();
  }

  function clearAllFields() {
    state.fieldCatalog.forEach(f => { state.fieldEnabled[f.id] = false; });
    refreshFieldPanel();
    _syncCheckboxes();
    saveConfig();
  }

  function resetFields() {
    state.fieldCatalog.forEach(f => {
      state.fieldEnabled[f.id] = f.is_builtin ? (f.enabled_by_default !== false) : true;
    });
    refreshFieldPanel();
    _syncCheckboxes();
    saveConfig();
  }

  function _syncCheckboxes() {
    document.querySelectorAll('.field-checkbox[data-field-id]').forEach(cb => {
      cb.checked = !!state.fieldEnabled[cb.dataset.fieldId];
    });
  }

  // ── 自定义字段 ────────────────────────────────────────────────
  function toggleAddFieldForm() {
    const form = document.getElementById('addFieldForm');
    const btn  = document.getElementById('addFieldBtn');
    const visible = form.style.display !== 'none';
    form.style.display = visible ? 'none' : 'block';
    btn.textContent    = visible ? '+ 添加自定义字段' : '− 收起';
    if (!visible) document.getElementById('newFieldLabel').focus();
  }

  function addCustomField() {
    const label       = document.getElementById('newFieldLabel').value.trim();
    const group       = document.getElementById('newFieldGroup').value;
    const fieldType   = document.getElementById('newFieldType').value;
    const instruction = document.getElementById('newFieldInstruction').value.trim();

    if (!label) {
      alert('请填写字段名称');
      return;
    }

    _customFieldCounter++;
    const id = `custom_${_customFieldCounter}`;
    const newField = {
      id,
      label,
      group,
      col_name:           label,   // Excel 列名默认与显示名称相同
      instruction:        instruction || `根据实际情况提取${label}信息`,
      field_type:         fieldType,
      enabled_by_default: true,
      is_builtin:         false,
    };

    state.fieldCatalog.push(newField);
    state.fieldEnabled[id] = true;

    // 清空表单
    document.getElementById('newFieldLabel').value = '';
    document.getElementById('newFieldInstruction').value = '';
    toggleAddFieldForm();

    refreshFieldPanel();
    saveConfig();
  }

  function deleteCustomField(fieldId) {
    state.fieldCatalog = state.fieldCatalog.filter(f => f.id !== fieldId);
    delete state.fieldEnabled[fieldId];
    refreshFieldPanel();
    saveConfig();
  }

  // ── 搜索源变化 ────────────────────────────────────────────────
  function onSourceChange() {
    const metasoChecked = document.getElementById('sourceMetaso').checked;
    const baiduChecked = document.getElementById('sourceBaidu').checked;
    const volcengineChecked = document.getElementById('sourceVolcengine').checked;
    document.getElementById('metasoConfigRow').style.display = metasoChecked ? '' : 'none';
    document.getElementById('baiduConfigRow').style.display = baiduChecked ? '' : 'none';
    document.getElementById('volcengineConfigRow').style.display = volcengineChecked ? '' : 'none';
    updateSearchLimitHint();
    saveConfig();
  }

  function updateSearchLimitHint() {
    const metaso = document.getElementById('sourceMetaso').checked;
    const baidu  = document.getElementById('sourceBaidu').checked;
    const volcengine = document.getElementById('sourceVolcengine').checked;

    const metasoLimit = parseInt(document.getElementById('metasoLimit').value) || 10;
    const baiduLimit = parseInt(document.getElementById('baiduLimit').value) || 10;
    const volcengineLimit = parseInt(document.getElementById('volcengineLimit').value) || 10;

    const sources = [];
    let total = 0;
    if (metaso) { sources.push(`秘塔${metasoLimit}条`); total += metasoLimit; }
    if (baidu) { sources.push(`百度${baiduLimit}条`); total += baiduLimit; }
    if (volcengine) { sources.push(`火山${volcengineLimit}条`); total += volcengineLimit; }

    if (!sources.length) {
      document.getElementById('searchLimitHint').textContent = '请至少选一个搜索源';
      return;
    }
    document.getElementById('searchLimitHint').textContent =
      `将检索：${sources.join(' + ')}，去重后最多 ${total} 条`;
  }

  // ── 配置持久化 ────────────────────────────────────────────────
  function loadSavedConfig() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      if (saved.llmProvider)  { state.llmProvider = saved.llmProvider; syncProviderButtons(); }
      if (saved.metasoKey)    document.getElementById('metasoKey').value = saved.metasoKey;
      if (saved.baiduKey)     document.getElementById('baiduKey').value  = saved.baiduKey;
      if (saved.volcengineKey) document.getElementById('volcengineKey').value = saved.volcengineKey;
      if (saved.metasoUsePreset !== undefined)
        document.getElementById('metasoUsePreset').checked = saved.metasoUsePreset;
      if (saved.baiduUsePreset !== undefined)
        document.getElementById('baiduUsePreset').checked = saved.baiduUsePreset;
      if (saved.volcengineUsePreset !== undefined)
        document.getElementById('volcengineUsePreset').checked = saved.volcengineUsePreset;
      if (saved.sourceBaidu !== undefined)
        document.getElementById('sourceBaidu').checked = saved.sourceBaidu;
      if (saved.sourceVolcengine !== undefined)
        document.getElementById('sourceVolcengine').checked = saved.sourceVolcengine;
      if (saved.metasoLimit)
        document.getElementById('metasoLimit').value = saved.metasoLimit;
      if (saved.baiduLimit)
        document.getElementById('baiduLimit').value = saved.baiduLimit;
      if (saved.volcengineLimit)
        document.getElementById('volcengineLimit').value = saved.volcengineLimit;
      if (saved.llmKey)       document.getElementById('llmKey').value = saved.llmKey;
      if (saved.llmUsePreset !== undefined)
        document.getElementById('llmUsePreset').checked = saved.llmUsePreset;
      if (saved.llmBaseUrl)   document.getElementById('llmBaseUrl').value = saved.llmBaseUrl;
      if (saved.llmModel)     document.getElementById('llmModel').value   = saved.llmModel;
      if (saved.searchConcurrency) {
        document.getElementById('searchConcurrency').value = saved.searchConcurrency;
        document.getElementById('searchConcurrencyVal').textContent = saved.searchConcurrency;
      }
      if (saved.llmConcurrency) {
        document.getElementById('llmConcurrency').value = saved.llmConcurrency;
        document.getElementById('llmConcurrencyVal').textContent = saved.llmConcurrency;
      }
      // 恢复字段状态和自定义字段
      if (saved.fieldEnabled)  state.fieldEnabled  = saved.fieldEnabled;
      if (saved.customFields?.length) {
        state.fieldCatalog = [...(state.fieldCatalog || []), ...saved.customFields];
        saved.customFields.forEach(f => {
          if (!(f.id in state.fieldEnabled)) state.fieldEnabled[f.id] = true;
        });
      }
      syncPresetInputState();
      updateThroughputHint();
      onSourceChange();
    } catch (_) {}
  }

  function saveConfig() {
    try {
      const customFields = state.fieldCatalog.filter(f => !f.is_builtin);
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        llmProvider:        state.llmProvider,
        metasoKey:          document.getElementById('metasoKey').value,
        metasoUsePreset:    document.getElementById('metasoUsePreset').checked,
        metasoLimit:        parseInt(document.getElementById('metasoLimit').value) || 10,
        baiduKey:           document.getElementById('baiduKey').value,
        baiduUsePreset:     document.getElementById('baiduUsePreset').checked,
        baiduLimit:         parseInt(document.getElementById('baiduLimit').value) || 10,
        sourceBaidu:        document.getElementById('sourceBaidu').checked,
        volcengineKey:      document.getElementById('volcengineKey').value,
        volcengineUsePreset: document.getElementById('volcengineUsePreset').checked,
        volcengineLimit:    parseInt(document.getElementById('volcengineLimit').value) || 10,
        sourceVolcengine:   document.getElementById('sourceVolcengine').checked,
        llmKey:             document.getElementById('llmKey').value,
        llmUsePreset:       document.getElementById('llmUsePreset').checked,
        llmBaseUrl:         document.getElementById('llmBaseUrl').value,
        llmModel:           document.getElementById('llmModel').value,
        searchConcurrency:  document.getElementById('searchConcurrency').value,
        llmConcurrency:     document.getElementById('llmConcurrency').value,
        fieldEnabled:       state.fieldEnabled,
        customFields,
      }));
    } catch (_) {}
  }

  // ── LLM Provider 切换 ─────────────────────────────────────────
  function selectLLM(provider) {
    state.llmProvider = provider;
    syncProviderButtons();
    const d = DEFAULTS[provider] || {};
    const baseUrlEl = document.getElementById('llmBaseUrl');
    const modelEl   = document.getElementById('llmModel');
    if (!baseUrlEl.value || Object.values(DEFAULTS).some(x => x.base_url === baseUrlEl.value))
      baseUrlEl.value = d.base_url || '';
    if (!modelEl.value || Object.values(DEFAULTS).some(x => x.model === modelEl.value))
      modelEl.value = d.model || '';
    refreshLLMPresetBadge();
    saveConfig();
  }

  function syncProviderButtons() {
    document.getElementById('btnDeepseek').classList.toggle('active', state.llmProvider === 'deepseek_official');
    document.getElementById('btnClaude').classList.toggle('active',   state.llmProvider === 'claude_proxy');
  }

  function syncPresetInputState() {
    document.getElementById('metasoKey').disabled = document.getElementById('metasoUsePreset').checked;
    document.getElementById('baiduKey').disabled  = document.getElementById('baiduUsePreset').checked;
    document.getElementById('volcengineKey').disabled = document.getElementById('volcengineUsePreset').checked;
    document.getElementById('llmKey').disabled    = document.getElementById('llmUsePreset').checked;
  }

  // ── 滑块 ──────────────────────────────────────────────────────
  function bindSliders() {
    ['searchConcurrency', 'llmConcurrency'].forEach(id => {
      document.getElementById(id).addEventListener('input', () => {
        document.getElementById(id + 'Val').textContent = document.getElementById(id).value;
        updateThroughputHint();
        saveConfig();
      });
    });
    // searchResultLimit 已移除，改为每源独立配置
  }

  function updateThroughputHint() {
    const sc = parseInt(document.getElementById('searchConcurrency').value);
    const lc = parseInt(document.getElementById('llmConcurrency').value);
    const perCompanyS = (3 / sc) * 2 + (1 / lc) * 8;
    const perHour = Math.round(3600 / perCompanyS);
    document.getElementById('throughputHint').textContent = `≈ ${perHour.toLocaleString()} 企业/小时`;
  }

  // ── API 连通性测试 ────────────────────────────────────────────
  async function testSearch() {
    const btn = document.getElementById('testSearchBtn');
    const resultEl = document.getElementById('testSearchResult');

    // 收集当前勾选的搜索源
    const sources = [];
    if (document.getElementById('sourceMetaso').checked) sources.push('metaso');
    if (document.getElementById('sourceBaidu').checked) sources.push('baidu');
    if (document.getElementById('sourceVolcengine').checked) sources.push('volcengine');

    if (!sources.length) {
      resultEl.textContent = '请先勾选至少一个搜索源';
      resultEl.className = 'api-test-result fail';
      return;
    }

    btn.disabled = true;
    btn.textContent = '测试中…';
    resultEl.textContent = '';
    resultEl.className = 'api-test-result';

    const keyMap = {
      metaso:      { keyId: 'metasoKey',      presetId: 'metasoUsePreset' },
      baidu:       { keyId: 'baiduKey',       presetId: 'baiduUsePreset' },
      volcengine:  { keyId: 'volcengineKey',  presetId: 'volcengineUsePreset' },
    };

    const results = [];
    for (const src of sources) {
      const { keyId, presetId } = keyMap[src];
      const usePreset = document.getElementById(presetId).checked;
      const apiKey = usePreset ? null : (document.getElementById(keyId).value.trim() || null);
      try {
        const resp = await fetch('/api/test/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider_id: src, api_key: apiKey }),
        });
        const data = await resp.json();
        results.push(`${src}: ${data.ok ? '✓ ' + data.message : '✗ ' + data.message}`);
      } catch (e) {
        results.push(`${src}: ✗ 请求失败`);
      }
    }

    const allOk = results.every(r => r.includes('✓'));
    resultEl.textContent = results.join('\n');
    resultEl.className = 'api-test-result ' + (allOk ? 'ok' : 'fail');
    btn.disabled = false;
    btn.textContent = '测试搜索 API';
  }

  async function testLLM() {
    const btn = document.getElementById('testLLMBtn');
    const resultEl = document.getElementById('testLLMResult');

    btn.disabled = true;
    btn.textContent = '测试中…';
    resultEl.textContent = '';
    resultEl.className = 'api-test-result';

    const usePreset = document.getElementById('llmUsePreset').checked;
    const apiKey = usePreset ? null : (document.getElementById('llmKey').value.trim() || null);
    const payload = {
      provider: state.llmProvider,
      base_url: document.getElementById('llmBaseUrl').value.trim() || null,
      api_key:  apiKey,
      model:    document.getElementById('llmModel').value.trim() || null,
    };

    try {
      const resp = await fetch('/api/test/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      resultEl.textContent = data.ok
        ? `✓ ${data.message}${data.reply ? '：' + data.reply : ''}`
        : `✗ ${data.message}`;
      resultEl.className = 'api-test-result ' + (data.ok ? 'ok' : 'fail');
    } catch (e) {
      resultEl.textContent = '✗ 请求失败';
      resultEl.className = 'api-test-result fail';
    }

    btn.disabled = false;
    btn.textContent = '测试大模型连接';
  }

  // ── 文件处理 ──────────────────────────────────────────────────
  function onFileChange(e) { if (e.target.files[0]) setFile(e.target.files[0]); }
  function onDragOver(e)   { e.preventDefault(); document.getElementById('uploadZone').classList.add('drag-over'); }
  function onDragLeave()   { document.getElementById('uploadZone').classList.remove('drag-over'); }
  function onDrop(e) {
    e.preventDefault();
    document.getElementById('uploadZone').classList.remove('drag-over');
    if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
  }
  function setFile(file) {
    state.file = file;
    document.getElementById('uploadFilename').textContent = `📄 ${file.name}`;
    updateSubmitBtn();
  }

  // ── 提交 ──────────────────────────────────────────────────────
  function updateSubmitBtn() {
    document.getElementById('submitBtn').disabled = !(state.file && state.stage === 'idle');
  }

  async function submitJob() {
    if (!state.file) return;

    // 收集已启用的字段定义列表（按目录顺序）
    const enabledFieldDefs = state.fieldCatalog.filter(f => state.fieldEnabled[f.id]);
    if (!enabledFieldDefs.length) {
      alert('请至少选择一个抽取字段');
      return;
    }

    // 构建搜索源配置列表（新结构）
    const searchProviders = [];

    if (document.getElementById('sourceMetaso').checked) {
      searchProviders.push({
        id: 'metaso',
        num_results: parseInt(document.getElementById('metasoLimit').value) || 10,
        api_key: document.getElementById('metasoUsePreset').checked
          ? null : (document.getElementById('metasoKey').value || null)
      });
    }

    if (document.getElementById('sourceBaidu').checked) {
      searchProviders.push({
        id: 'baidu',
        num_results: parseInt(document.getElementById('baiduLimit').value) || 10,
        api_key: document.getElementById('baiduUsePreset').checked
          ? null : (document.getElementById('baiduKey').value || null)
      });
    }

    if (document.getElementById('sourceVolcengine').checked) {
      searchProviders.push({
        id: 'volcengine',
        num_results: parseInt(document.getElementById('volcengineLimit').value) || 10,
        api_key: document.getElementById('volcengineUsePreset').checked
          ? null : (document.getElementById('volcengineKey').value || null)
      });
    }

    if (!searchProviders.length) {
      alert('请至少选择一个搜索源');
      return;
    }

    console.log('提交配置 - 搜索源:', searchProviders);

    setStage('uploading');

    const config = {
      search_providers: searchProviders,  // 新的配置结构
      field_defs: enabledFieldDefs.map(f => ({
        id:          f.id,
        label:       f.label,
        group:       f.group,
        col_name:    f.col_name,
        instruction: f.instruction,
        field_type:  f.field_type,
      })),
      llm: {
        provider: state.llmProvider,
        base_url: document.getElementById('llmBaseUrl').value || null,
        api_key:  document.getElementById('llmUsePreset').checked
          ? null : (document.getElementById('llmKey').value || null),
        model:    document.getElementById('llmModel').value || null,
      },
      concurrency: {
        search: parseInt(document.getElementById('searchConcurrency').value),
        llm:    parseInt(document.getElementById('llmConcurrency').value),
      },
    };

    const formData = new FormData();
    formData.append('file', state.file);
    formData.append('config', JSON.stringify(config));

    document.getElementById('submitBtn').classList.add('loading');

    try {
      const resp = await fetch(`${API_BASE}/api/jobs`, { method: 'POST', body: formData });
      const data = await resp.json();

      console.log('服务器响应:', { status: resp.status, ok: resp.ok, data });

      if (!resp.ok) {
        const errorMsg = data.detail || '创建任务失败';
        console.error('任务创建失败:', errorMsg);
        alert(`任务创建失败: ${errorMsg}`);
        appendLog(`错误: ${errorMsg}`, 'error');
        setStage('idle');
        return;
      }

      state.jobId     = data.job_id;
      state.total     = data.total;
      state.completed = 0;
      state.failed    = 0;
      state.skipped   = 0;
      Object.keys(_nameToIdx).forEach(k => delete _nameToIdx[k]);
      Object.keys(_traceData).forEach(k => delete _traceData[k]);

      document.getElementById('progressTotal').textContent = data.total;
      if (data.pre_done > 0)
        appendLog(`断点续传：检测到 ${data.pre_done} 家已处理企业，将自动跳过`, '');

      initCompanyList(data.total);
      showRunningUI();
      setStage('searching');
      startSSE(data.job_id);

    } catch (err) {
      console.error('提交任务异常:', err);
      alert(`网络错误: ${err.message}`);
      appendLog(`网络错误: ${err.message}`, 'error');
      setStage('idle');
    } finally {
      document.getElementById('submitBtn').classList.remove('loading');
    }
  }

  // ── 取消 ──────────────────────────────────────────────────────
  async function cancelJob() {
    if (!state.jobId) return;
    const btn = document.getElementById('cancelBtn');
    btn.disabled = true;
    btn.textContent = '停止中...';
    try {
      const resp = await fetch(`${API_BASE}/api/jobs/${state.jobId}/cancel`, { method: 'POST' });
      const data = await resp.json();
      if (resp.ok) {
        appendLog(`已发送停止信号：${data.message}`, 'warn');
      } else {
        appendLog(`停止失败: ${data.detail}`, 'error');
        btn.disabled = false;
        btn.textContent = '■ 停止处理';
      }
    } catch (err) {
      appendLog(`停止请求失败: ${err.message}`, 'error');
      btn.disabled = false;
      btn.textContent = '■ 停止处理';
    }
  }

  // ── SSE ───────────────────────────────────────────────────────
  function startSSE(jobId) {
    if (state.eventSource) state.eventSource.close();
    state.eventSource = new EventSource(`${API_BASE}/api/jobs/${jobId}/events`);
    state.eventSource.onmessage = e => handleSSEEvent(JSON.parse(e.data));
    state.eventSource.onerror   = () => appendLog('SSE 连接中断，等待重连...', 'warn');
  }

  function handleSSEEvent(ev) {
    const { event, total, completed, failed, skipped = 0,
            company_name, message, elapsed_s, eta_s, detail } = ev;

    if (total)          state.total     = total;
    state.completed   = completed || 0;
    state.failed      = failed    || 0;
    state.skipped     = skipped   || 0;

    const done = state.completed + state.failed + state.skipped;
    const pct  = state.total > 0 ? (done / state.total) * 100 : 0;

    document.getElementById('progressBar').style.width     = `${pct}%`;
    document.getElementById('progressDone').textContent    = done;
    document.getElementById('progressSuccess').textContent = state.completed;
    document.getElementById('progressFail').textContent    = state.failed;

    let timing = elapsed_s ? `已用 ${formatSeconds(elapsed_s)}` : '';
    if (eta_s) timing += `  ETA ${formatSeconds(eta_s)}`;
    document.getElementById('progressTiming').textContent = timing;

    if (company_name)
      document.getElementById('progressCurrentCompany').textContent = `正在处理：${company_name}`;

    switch (event) {
      case 'start':
      case 'log':
        appendLog(message, '');
        break;
      case 'company_done':
        if (detail?.trace) _traceData[company_name] = detail.trace;
        updateCompanyRow(company_name, detail?.resumed ? 'resumed' : 'done', detail);
        appendLog(`✓ ${company_name} — ${message}`, 'done');
        break;
      case 'company_error':
        if (detail?.trace) _traceData[company_name] = detail.trace;
        updateCompanyRow(company_name, 'error', { error: message });
        appendLog(`✗ ${company_name} — ${message}`, 'error');
        break;
      case 'done': {
        state.eventSource.close();
        const cancelled = message.includes('停止');
        setStage(cancelled ? 'cancelled' : 'done');
        document.getElementById('progressCurrentCompany').textContent =
          cancelled ? '已停止（含部分结果）' : '全部完成';
        document.getElementById('cancelBtn').style.display   = 'none';
        document.getElementById('downloadBtn').style.display = 'inline-flex';
        appendLog(message, 'done');
        updateSubmitBtn();
        break;
      }
    }
  }

  function formatSeconds(s) {
    const m = Math.floor(s / 60), sec = Math.round(s % 60);
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  }

  // ── 企业列表 ──────────────────────────────────────────────────
  function initCompanyList(total) {
    const body = document.getElementById('companyListBody');
    body.innerHTML = '';
    for (let i = 0; i < total; i++) {
      const row = document.createElement('div');
      row.className = 'company-row';
      row.id = `company-row-${i}`;
      row.innerHTML = `
        <div class="company-row-header" onclick="app.toggleTrace(${i})">
          <span class="row-idx">${i + 1}</span>
          <span class="row-name" id="row-name-${i}">加载中…</span>
          <span class="row-status-dot pending" id="row-dot-${i}"></span>
          <div class="row-capsules" id="row-caps-${i}"></div>
          <span class="row-toggle" id="row-toggle-${i}">▶</span>
        </div>
        <div class="row-trace" id="row-trace-${i}"></div>`;
      body.appendChild(row);
    }
    document.getElementById('companyListCount').textContent = `${total} 家`;
  }

  function toggleTrace(idx) {
    const row = document.getElementById(`company-row-${idx}`);
    if (!row) return;
    const isExpanded = row.classList.toggle('expanded');
    if (isExpanded) {
      const name = document.getElementById(`row-name-${idx}`)?.textContent || '';
      renderTrace(idx, name);
    }
  }

  function renderTrace(idx, companyName) {
    const container = document.getElementById(`row-trace-${idx}`);
    if (!container) return;
    const trace = _traceData[companyName];
    if (!trace) {
      container.innerHTML = '<div class="trace-empty">暂无详细数据（处理中或无数据）</div>';
      return;
    }

    let html = '';

    // 搜索关键词
    if (trace.search_queries?.length) {
      html += `<div class="trace-section">
        <div class="trace-section-title">搜索关键词（${trace.search_queries.length} 组）</div>
        <div class="trace-content trace-compact">${trace.search_queries.map(q => escHtml(q)).join('\n')}</div>
      </div>`;
    }

    // 搜索原始响应（含 provider 来源标签）
    if (trace.search_raw_responses?.length) {
      html += `<div class="trace-section">
        <div class="trace-section-title">搜索 API 原始响应（${trace.search_raw_responses.length} 次，含多源）</div>
        <div class="trace-content">${trace.search_raw_responses.map(r => {
          const providerBadge = r.provider_name ? `[${escHtml(r.provider_name)}] ` : '';
          return `${providerBadge}[${escHtml(r.query || '')}]\n${escHtml(JSON.stringify(r.raw, null, 2).substring(0, 600))}`;
        }).join('\n---\n')}</div>
      </div>`;
    }

    // 去重后的合并搜索结果（含来源）
    if (trace.search_parsed_results?.length) {
      html += `<div class="trace-section">
        <div class="trace-section-title">合并去重后的搜索结果（${trace.search_parsed_results.length} 条）</div>
        <div class="trace-content">${trace.search_parsed_results.map(r => `
          <div class="trace-result-item">
            <div class="trace-result-title">${escHtml(r.title || '')}
              ${r.provider_name ? `<span class="trace-provider-badge">${escHtml(r.provider_name)}</span>` : ''}
            </div>
            <div class="trace-result-url">${escHtml(r.url || '')}</div>
            <div class="trace-result-snippet">${escHtml(r.snippet || '')}</div>
          </div>`).join('')}</div>
      </div>`;
    }

    // 送给 LLM 的证据摘要
    if (trace.llm_evidence_summary) {
      html += `<div class="trace-section">
        <div class="trace-section-title">送给 LLM 的完整 Prompt</div>
        <div class="trace-content">${escHtml(trace.llm_evidence_summary)}</div>
      </div>`;
    }

    // LLM 原始输出
    if (trace.llm_raw_output) {
      html += `<div class="trace-section">
        <div class="trace-section-title">LLM 原始输出</div>
        <div class="trace-content">${escHtml(trace.llm_raw_output)}</div>
      </div>`;
    }

    // 最终结构化结果
    if (trace.final_result) {
      const result = trace.final_result;
      let resultHtml = '<div class="trace-section"><div class="trace-section-title">最终结构化结果</div>';

      // Summary fields with notes
      if (result.summary && Object.keys(result.summary).length > 0) {
        resultHtml += '<div class="trace-content"><div class="result-group-title">概要信息</div>';
        for (const [fieldId, value] of Object.entries(result.summary)) {
          const fieldDef = state.fieldCatalog.find(f => f.id === fieldId);
          const label = fieldDef?.label || fieldId;
          const note = result.summary_notes?.[fieldId];
          resultHtml += `<div class="result-field">
            <div class="result-field-label">${escHtml(label)}</div>
            <div class="result-field-value">${escHtml(value || '无')}</div>
            ${note ? `<div class="field-note">${escHtml(note)}</div>` : ''}
          </div>`;
        }
        resultHtml += '</div>';
      }


      // Other fields (evidence_count, sources, error)
      if (result.evidence_count !== undefined || result.sources?.length || result.error) {
        resultHtml += '<div class="trace-content"><div class="result-group-title">其他信息</div>';
        if (result.evidence_count !== undefined) {
          resultHtml += `<div class="result-field">
            <div class="result-field-label">证据数量</div>
            <div class="result-field-value">${result.evidence_count}</div>
          </div>`;
        }
        if (result.sources?.length) {
          resultHtml += `<div class="result-field">
            <div class="result-field-label">来源</div>
            <div class="result-field-value">${result.sources.map(s => escHtml(s)).join(', ')}</div>
          </div>`;
        }
        if (result.error) {
          resultHtml += `<div class="result-field">
            <div class="result-field-label">错误</div>
            <div class="result-field-value" style="color: var(--stamp);">${escHtml(result.error)}</div>
          </div>`;
        }
        resultHtml += '</div>';
      }

      resultHtml += '</div>';
      html += resultHtml;
    }

    container.innerHTML = html || '<div class="trace-empty">无详细数据</div>';
  }

  function updateCompanyRow(name, status, detail) {
    if (_nameToIdx[name] === undefined) {
      const els = document.querySelectorAll('[id^="row-name-"]');
      for (const el of els) {
        if (el.textContent === '加载中…') {
          const idx = parseInt(el.id.replace('row-name-', ''));
          el.textContent = name;
          _nameToIdx[name] = idx;
          break;
        }
      }
    }
    const idx = _nameToIdx[name];
    if (idx === undefined) return;

    const dot  = document.getElementById(`row-dot-${idx}`);
    const caps = document.getElementById(`row-caps-${idx}`);
    if (!dot) return;

    dot.className = `row-status-dot ${{ done:'done', resumed:'done', error:'error', running:'running' }[status] || 'pending'}`;

    if ((status === 'done' || status === 'resumed') && detail) {
      const capArr = [];
      if (detail.resumed) capArr.push(`<span class="capsule capsule-evidence">续传</span>`);
      if (detail.evidence_count !== undefined)
        capArr.push(`<span class="capsule capsule-evidence">证据 ${detail.evidence_count} 条</span>`);
      caps.innerHTML = capArr.join('');
    } else if (status === 'error' && detail?.error) {
      caps.innerHTML = `<span class="capsule capsule-error" title="${escHtml(detail.error)}">失败</span>`;
    }

    const row = document.getElementById(`company-row-${idx}`);
    if (row?.classList.contains('expanded')) renderTrace(idx, name);
  }

  function escHtml(s) {
    return String(s).replace(/[&<>"']/g, c =>
      ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
  }

  // ── 日志 ──────────────────────────────────────────────────────
  function appendLog(msg, level) {
    const body  = document.getElementById('logBody');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    const ts = new Date().toTimeString().slice(0, 8);
    entry.innerHTML = `<span class="log-ts">${ts}</span><span class="log-msg ${level || ''}">${escHtml(msg)}</span>`;
    body.appendChild(entry);
    body.scrollTop = body.scrollHeight;
    while (body.children.length > 300) body.removeChild(body.firstChild);
  }

  function clearLog() { document.getElementById('logBody').innerHTML = ''; }

  // ── 阶段管理 ──────────────────────────────────────────────────
  function setStage(stage) {
    state.stage = stage;
    const order = ['idle', 'uploading', 'searching', 'extracting', 'done'];
    const cur   = order.indexOf(stage === 'cancelled' ? 'done' : stage);
    document.querySelectorAll('.stage-item').forEach(el => {
      const idx = order.indexOf(el.dataset.stage);
      el.classList.remove('active', 'done');
      if (idx === cur) el.classList.add('active');
      else if (idx < cur) el.classList.add('done');
    });
    const running = ['searching', 'extracting', 'running'].includes(stage);
    const cancelBtn = document.getElementById('cancelBtn');
    if (cancelBtn) {
      cancelBtn.style.display = running ? 'inline-flex' : 'none';
      cancelBtn.disabled = false;
      cancelBtn.textContent = '■ 停止处理';
    }
    updateSubmitBtn();
  }

  function showRunningUI() {
    document.getElementById('emptyState').style.display      = 'none';
    document.getElementById('progressCard').style.display    = 'flex';
    document.getElementById('logCard').style.display         = 'block';
    document.getElementById('companyListCard').style.display = 'block';
    document.getElementById('downloadBtn').style.display     = 'none';
  }

  // ── 下载 ──────────────────────────────────────────────────────
  function downloadResult(e) {
    e.preventDefault();
    if (state.jobId) window.location.href = `${API_BASE}/api/jobs/${state.jobId}/download`;
  }

  // ── 自动保存输入框 ────────────────────────────────────────────
  ['metasoKey', 'baiduKey', 'volcengineKey', 'llmKey', 'llmBaseUrl', 'llmModel'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', saveConfig);
  });

  return {
    init, selectLLM, submitJob, cancelJob, downloadResult,
    onFileChange, onDragOver, onDragLeave, onDrop,
    clearLog, toggleTrace,
    onSourceChange, updateSearchLimitHint,
    toggleFieldGroup, onFieldToggle,
    selectAllFields, clearAllFields, resetFields,
    toggleAddFieldForm, addCustomField, deleteCustomField,
    syncPresetInputState, saveConfig,
    testSearch, testLLM,
    // 调试方法
    getState: () => state,
  };
})();

document.addEventListener('DOMContentLoaded', () => app.init());
