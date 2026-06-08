// === ExamPass Knowledge Graph Engine ===

// Keep in sync with CSS --bp-* variables.
var BRANCH_COLORS = [
  '#6b8ba4', '#7d9b7d', '#b88b64', '#8e6b7e',
  '#5f919b', '#9b8a6e', '#7b7599', '#7b967b'
];

var STORAGE_KEY = 'graph_settings';
var NODE_W = 156;
var COL_W = 230;     // column step (node + gap); no inline note cards needed
var ROW_GAP = 14;
var OFFSET_X = 28;
var OFFSET_Y = 28;

// ─── Tree model ────────────────────────────────────────────

function walkTree(nodes, branch, depth, callback) {
  for (var i = 0; i < nodes.length; i++) {
    var node = nodes[i];
    var leaf = !node.children || node.children.length === 0;
    callback(node, branch, depth, leaf);
    if (node.children && node.children.length > 0) {
      walkTree(node.children, branch, depth + 1, callback);
    }
  }
}

function assignBranchColors(nodes) {
  for (var i = 0; i < nodes.length; i++) {
    walkTree([nodes[i]], i % BRANCH_COLORS.length, 0, function(n, branch) {
      n._branch = branch;
    });
  }
}

function isLeafNode(node) {
  return !node.children || node.children.length === 0;
}

function walkVisible(nodes, cb, depth) {
  depth = depth || 0;
  for (var i = 0; i < nodes.length; i++) {
    var n = nodes[i];
    n._depth = depth;
    cb(n, depth);
    if (!n._collapsed && n.children && n.children.length > 0) {
      walkVisible(n.children, cb, depth + 1);
    }
  }
}

// ─── localStorage ──────────────────────────────────────────

function loadNotes(nodeId) {
  try { return localStorage.getItem('graph_' + nodeId + '_notes') || ''; }
  catch(e) { return ''; }
}

function saveNotes(nodeId, html) {
  try {
    if (html) localStorage.setItem('graph_' + nodeId + '_notes', html);
    else localStorage.removeItem('graph_' + nodeId + '_notes');
    localStorage.setItem('graph_' + nodeId + '_updated', new Date().toISOString());
  } catch(e) {
    if (e.name === 'QuotaExceededError') showToast('存储空间不足，请清理旧笔记');
  }
}

function loadImages(nodeId) {
  try {
    var raw = localStorage.getItem('graph_' + nodeId + '_images');
    return raw ? JSON.parse(raw) : [];
  } catch(e) { return []; }
}

function saveImages(nodeId, images) {
  try {
    if (images.length > 0) localStorage.setItem('graph_' + nodeId + '_images', JSON.stringify(images));
    else localStorage.removeItem('graph_' + nodeId + '_images');
  } catch(e) {
    if (e.name === 'QuotaExceededError') showToast('图片过大，请清理部分旧图片');
  }
}

function loadSettings() {
  try { var raw = localStorage.getItem(STORAGE_KEY); return raw ? JSON.parse(raw) : {}; }
  catch(e) { return {}; }
}

function saveSettings(s) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch(e) {}
}

// ─── State ─────────────────────────────────────────────────

var treeData = null;
var settings = loadSettings();
var selectedNodeId = null;

// DOM refs
var graphCanvas, treePanel, notesPanel, npPlaceholder, npContent, npTitle;
var npBody, npImages, connectionsLayer, tooltip, toast;
var zoomSlider, zoomLabel, headerTitle;

function cacheDomRefs() {
  graphCanvas = document.getElementById('graph-canvas');
  treePanel = document.getElementById('tree-panel');
  notesPanel = document.getElementById('notes-panel');
  npPlaceholder = document.getElementById('np-placeholder');
  npContent = document.getElementById('np-content');
  npTitle = document.getElementById('np-title');
  npBody = document.getElementById('np-body');
  npImages = document.getElementById('np-images');
  connectionsLayer = document.getElementById('connections-layer');
  tooltip = document.getElementById('tooltip');
  toast = document.getElementById('toast');
  zoomSlider = document.getElementById('zoom-slider');
  zoomLabel = document.getElementById('zoom-label');
  headerTitle = document.getElementById('header-title');
}

// ─── Notes panel (right) ───────────────────────────────────

function selectNode(node) {
  // save previous
  saveCurrentNotes();

  // clear old selection highlight
  var prev = document.querySelector('.gn.selected');
  if (prev) prev.classList.remove('selected');

  selectedNodeId = node.id;
  node._el.classList.add('selected');

  // populate panel
  npPlaceholder.style.display = 'none';
  npContent.style.display = 'flex';
  npTitle.textContent = node.label;
  npBody.innerHTML = loadNotes(node.id);
  renderNotesImages(node.id);

  // scroll node into view
  node._el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function saveCurrentNotes() {
  if (!selectedNodeId) return;
  var html = npBody.innerHTML;
  saveNotes(selectedNodeId, html);
  // refresh the node's has-notes marker
  var el = document.querySelector('.gn[data-id="' + selectedNodeId + '"]');
  if (el) {
    if (html || loadImages(selectedNodeId).length > 0) el.classList.add('has-notes');
    else el.classList.remove('has-notes');
  }
}

function renderNotesImages(nodeId) {
  npImages.innerHTML = '';
  var images = loadImages(nodeId);
  for (var i = 0; i < images.length; i++) {
    npImages.appendChild(createImageElement(images[i], nodeId));
  }
}

function createImageElement(src, nodeId) {
  var wrap = document.createElement('div');
  wrap.className = 'ge-img-wrap';
  var img = document.createElement('img');
  img.src = src; img.alt = '笔记图片';
  wrap.appendChild(img);
  var del = document.createElement('button');
  del.className = 'ge-img-del'; del.textContent = '✕';
  del.addEventListener('click', function(e) {
    e.stopPropagation();
    var images = loadImages(nodeId);
    var idx = images.indexOf(src);
    if (idx !== -1) { images.splice(idx, 1); saveImages(nodeId, images); }
    wrap.remove();
    if (!npBody.innerHTML && images.length === 0) {
      var el = document.querySelector('.gn[data-id="' + nodeId + '"]');
      if (el) el.classList.remove('has-notes');
    }
  });
  wrap.appendChild(del);
  return wrap;
}

// ─── Toolbar ───────────────────────────────────────────────

function initToolbar() {
  document.getElementById('np-bold').addEventListener('click', function() {
    document.execCommand('bold');
    npBody.focus();
    this.classList.toggle('active');
  });
}

// ─── Rendering ─────────────────────────────────────────────

function render(tree) {
  treeData = tree;
  if (!tree.nodes || tree.nodes.length === 0) {
    graphCanvas.innerHTML =
      '<div style="padding:60px;text-align:center;color:#999;">课程内容为空，无法生成知识图谱</div>';
    return;
  }

  assignBranchColors(tree.nodes);
  applyCollapsed(tree.nodes, settings.collapsed || []);
  applyRenamesData(tree.nodes);

  graphCanvas.innerHTML = '';
  graphCanvas.style.transformOrigin = 'top left';

  walkVisible(tree.nodes, function(node) {
    var el = renderNode(node);
    el.style.position = 'absolute';
    el.style.visibility = 'hidden';
    el.style.left = '0';
    el.style.top = '0';
    graphCanvas.appendChild(el);
    node._el = el;
  });

  graphCanvas.appendChild(connectionsLayer);

  measureNodes();
  layoutTree(tree.nodes);
  applyPositions();
  drawConnections();

  var zoom = settings.zoom || 1;
  graphCanvas.style.transform = 'scale(' + zoom + ')';
  zoomSlider.value = Math.round(zoom * 100);
  zoomLabel.textContent = Math.round(zoom * 100) + '%';

  headerTitle.textContent = (tree.title || '课程') + ' — 知识图谱';

  // Restore selection
  if (selectedNodeId) {
    var el = document.querySelector('.gn[data-id="' + selectedNodeId + '"]');
    if (el) el.classList.add('selected');
  }

  // Reselect if notes exist for current node
  if (selectedNodeId && npBody) {
    npBody.innerHTML = loadNotes(selectedNodeId);
    renderNotesImages(selectedNodeId);
  }
}

function renderNode(node) {
  var el = document.createElement('div');
  el.className = 'gn gn-lv' + (node._depth || 0);
  el.dataset.id = node.id;
  el.dataset.branch = node._branch;
  el.dataset.depth = node._depth;

  var label = document.createElement('span');
  label.className = 'gn-label';
  label.textContent = node.label;
  el.appendChild(label);

  if (loadNotes(node.id) || loadImages(node.id).length > 0) {
    el.classList.add('has-notes');
  }
  if (node._collapsed) el.classList.add('collapsed');

  if (node.summary) {
    el.addEventListener('mouseenter', function(e) { showTooltip(e, node.summary); });
    el.addEventListener('mouseleave', hideTooltip);
    el.addEventListener('mousemove', moveTooltip);
  }

  el.addEventListener('click', function(e) {
    e.stopPropagation();
    if (isLeafNode(node)) {
      selectNode(node);
    } else {
      toggleCollapse(node);
    }
  });

  el.addEventListener('dblclick', function(e) {
    e.stopPropagation();
    renameNode(node, label);
  });

  return el;
}

// ─── Layout (tidy tree, absolute positioning) ──────────────

function measureNodes() {
  walkVisible(treeData.nodes, function(node) {
    if (node._el) node._h = node._el.offsetHeight;
  });
}

function layoutTree(nodes) {
  var cursorY = OFFSET_Y;
  function place(node) {
    node._x = OFFSET_X + node._depth * COL_W;
    var kids = (!node._collapsed && node.children && node.children.length > 0) ? node.children : [];
    var nodeH = node._h || 34;
    if (kids.length === 0) {
      node._top = cursorY;
      node._y = cursorY + nodeH / 2;
      cursorY += nodeH + ROW_GAP;
    } else {
      for (var i = 0; i < kids.length; i++) place(kids[i]);
      node._y = (kids[0]._y + kids[kids.length - 1]._y) / 2;
      node._top = node._y - nodeH / 2;
    }
  }
  for (var i = 0; i < nodes.length; i++) place(nodes[i]);
  return cursorY;
}

function applyPositions() {
  var maxX = 0, maxY = 0;
  walkVisible(treeData.nodes, function(node) {
    node._el.style.left = node._x + 'px';
    node._el.style.top = node._top + 'px';
    node._el.style.visibility = 'visible';
    var r = node._x + NODE_W;
    var b = node._top + (node._h || 34);
    if (r > maxX) maxX = r;
    if (b > maxY) maxY = b;
  });
  graphCanvas.style.width = (maxX + 40) + 'px';
  graphCanvas.style.height = (maxY + 60) + 'px';
}

function relayout() {
  if (!treeData) return;
  saveCurrentNotes();
  measureNodes();
  layoutTree(treeData.nodes);
  applyPositions();
  drawConnections();
}

// ─── Connections (SVG bezier, parent→child only; no dependency lines) ──

function collectEdges(nodes, acc) {
  for (var i = 0; i < nodes.length; i++) {
    var p = nodes[i];
    if (!p._collapsed && p.children && p.children.length > 0) {
      for (var j = 0; j < p.children.length; j++) {
        acc.push({ p: p, c: p.children[j] });
      }
      collectEdges(p.children, acc);
    }
  }
}

function drawConnections() {
  var w = parseFloat(graphCanvas.style.width) || graphCanvas.scrollWidth;
  var h = parseFloat(graphCanvas.style.height) || graphCanvas.scrollHeight;
  connectionsLayer.style.width = w + 'px';
  connectionsLayer.style.height = h + 'px';
  connectionsLayer.setAttribute('viewBox', '0 0 ' + w + ' ' + h);

  var edges = [];
  collectEdges(treeData.nodes, edges);

  var html = '';
  for (var i = 0; i < edges.length; i++) {
    var p = edges[i].p, c = edges[i].c;
    var x1 = p._x + NODE_W, y1 = p._y;
    var x2 = c._x, y2 = c._y;
    var cx1 = x1 + (x2 - x1) * 0.4;
    var cx2 = x1 + (x2 - x1) * 0.6;
    html += '<path class="conn-path" data-branch="' + p._branch +
      '" stroke="' + BRANCH_COLORS[p._branch] + '"' +
      ' d="M' + x1 + ',' + y1 + ' C' + cx1 + ',' + y1 + ' ' + cx2 + ',' + y2 + ' ' + x2 + ',' + y2 + '" />';
  }
  connectionsLayer.innerHTML = html;
}

// ─── Collapse / Expand ─────────────────────────────────────

function applyCollapsed(nodes, collapsedIds) {
  for (var i = 0; i < nodes.length; i++) {
    var node = nodes[i];
    node._collapsed = collapsedIds.indexOf(node.id) !== -1;
    if (node.children && node.children.length > 0) {
      applyCollapsed(node.children, collapsedIds);
    }
  }
}

function toggleCollapse(node) {
  node._collapsed = !node._collapsed;
  var collapsed = settings.collapsed || [];
  if (node._collapsed) {
    if (collapsed.indexOf(node.id) === -1) collapsed.push(node.id);
  } else {
    var idx = collapsed.indexOf(node.id);
    if (idx !== -1) collapsed.splice(idx, 1);
  }
  settings.collapsed = collapsed;
  saveSettings(settings);
  saveCurrentNotes();
  render(treeData);
}

// ─── Rename ────────────────────────────────────────────────

function renameNode(node, labelEl) {
  var oldLabel = node.label;
  var input = document.createElement('input');
  input.type = 'text'; input.value = oldLabel;
  input.style.cssText = 'font-weight:600;font-size:0.9em;width:100%;border:1px solid #ccc;border-radius:4px;padding:2px 6px;box-sizing:border-box;';
  input.addEventListener('click', function(e) { e.stopPropagation(); });
  input.addEventListener('blur', function() { finishRename(node, input.value.trim() || oldLabel); });
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
    if (e.key === 'Escape') { input.value = oldLabel; input.blur(); }
  });
  labelEl.replaceWith(input);
  input.focus(); input.select();
}

function finishRename(node, newLabel) {
  node.label = newLabel;
  settings.renamed = settings.renamed || {};
  settings.renamed[node.id] = newLabel;
  saveSettings(settings);
  saveCurrentNotes();
  render(treeData);
}

function applyRenamesData(nodes) {
  var renamed = settings.renamed || {};
  walkTree(nodes, 0, 0, function(n) {
    if (renamed[n.id] != null) n.label = renamed[n.id];
  });
}

// ─── Tooltip ───────────────────────────────────────────────

function showTooltip(e, text) {
  tooltip.textContent = text;
  tooltip.classList.add('tooltip-show');
  moveTooltip(e);
}

function moveTooltip(e) {
  var x = e.clientX + 14, y = e.clientY + 14;
  if (x + 300 > window.innerWidth) x = e.clientX - 310;
  if (y + 80 > window.innerHeight) y = e.clientY - 90;
  tooltip.style.left = x + 'px';
  tooltip.style.top = y + 'px';
}

function hideTooltip() { tooltip.classList.remove('tooltip-show'); }

// ─── Toast ─────────────────────────────────────────────────

var toastTimer = null;
function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add('toast-show');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(function() { toast.classList.remove('toast-show'); }, 2200);
}

// ─── Image paste ───────────────────────────────────────────

function handlePaste(e) {
  var items = e.clipboardData && e.clipboardData.items;
  if (!items) return;
  for (var i = 0; i < items.length; i++) {
    if (items[i].type.indexOf('image') !== -1) {
      e.preventDefault();
      var blob = items[i].getAsFile();
      compressImage(blob, function(dataUrl) {
        if (!selectedNodeId) return;
        var images = loadImages(selectedNodeId);
        images.push(dataUrl);
        saveImages(selectedNodeId, images);
        npImages.appendChild(createImageElement(dataUrl, selectedNodeId));
        var el = document.querySelector('.gn[data-id="' + selectedNodeId + '"]');
        if (el) el.classList.add('has-notes');
      });
      return;
    }
  }
}

function compressImage(blob, callback) {
  var img = new Image();
  var url = URL.createObjectURL(blob);
  img.onload = function() {
    URL.revokeObjectURL(url);
    var canvas = document.createElement('canvas');
    var maxW = 800, w = img.width, h = img.height;
    if (w > maxW) { h = h * (maxW / w); w = maxW; }
    canvas.width = w; canvas.height = h;
    var ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, w, h);
    callback(canvas.toDataURL('image/jpeg', 0.7));
  };
  img.onerror = function() {
    URL.revokeObjectURL(url);
    showToast('图片加载失败，请重试');
  };
  img.src = url;
}

// ─── Search ────────────────────────────────────────────────

var searchTimer = null;
function doSearch() {
  var query = (document.getElementById('search-input') || {}).value;
  if (!query) query = '';
  query = query.trim().toLowerCase();
  var allNodes = document.querySelectorAll('.gn');
  var firstHit = null;
  for (var i = 0; i < allNodes.length; i++) allNodes[i].classList.remove('search-hit', 'search-dim');
  if (!query) return;
  for (var i = 0; i < allNodes.length; i++) {
    var el = allNodes[i];
    var label = (el.querySelector('.gn-label') || {}).textContent || '';
    if (label.toLowerCase().indexOf(query) !== -1) {
      el.classList.add('search-hit');
      if (!firstHit) firstHit = el;
    } else {
      el.classList.add('search-dim');
    }
  }
  if (firstHit) firstHit.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// ─── Zoom ──────────────────────────────────────────────────

function initZoom() {
  var slider = zoomSlider;
  var label = zoomLabel;
  var outBtn = document.getElementById('zoom-out');
  var inBtn = document.getElementById('zoom-in');
  var zoom = settings.zoom || 1;
  function applyZoom(z) {
    zoom = Math.max(0.5, Math.min(2, z));
    if (graphCanvas) graphCanvas.style.transform = 'scale(' + zoom + ')';
    slider.value = Math.round(zoom * 100);
    label.textContent = Math.round(zoom * 100) + '%';
    settings.zoom = zoom;
    saveSettings(settings);
  }
  slider.addEventListener('input', function() { applyZoom(this.value / 100); });
  if (outBtn) outBtn.addEventListener('click', function() { applyZoom(zoom - 0.1); });
  if (inBtn) inBtn.addEventListener('click', function() { applyZoom(zoom + 0.1); });

  // Narrow-screen zoom: fit tree on mobile
  document.getElementById('reset-btn').addEventListener('click', function() {
    settings.collapsed = [];
    settings.renamed = {};
    saveSettings(settings);
    document.getElementById('search-input').value = '';
    doSearch();
    applyZoom(1);
    saveCurrentNotes();
    render(treeData);
    npPlaceholder.style.display = 'block';
    npContent.style.display = 'none';
    selectedNodeId = null;
  });
}

// ─── Init ──────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function() {
  cacheDomRefs();
  initToolbar();
  initZoom();

  // Notes auto-save
  npBody.addEventListener('blur', function() { saveCurrentNotes(); });
  npBody.addEventListener('paste', handlePaste);

  // Search
  var si = document.getElementById('search-input');
  if (si) {
    si.addEventListener('input', function() {
      if (searchTimer) clearTimeout(searchTimer);
      searchTimer = setTimeout(doSearch, 200);
    });
    si.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') { si.value = ''; doSearch(); }
    });
  }

  if (typeof TREE_DATA === 'undefined') {
    graphCanvas.innerHTML =
      '<div style="padding:60px;text-align:center;color:#999;">未找到知识图谱数据</div>';
    return;
  }
  render(TREE_DATA);

  var resizeTimer = null;
  window.addEventListener('resize', function() {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(drawConnections, 300);
  });
});
