"""Template engine for ExamPass HTML generation.

Architecture:
  templates/page_template.html  -- HTML shell (__TITLE__, __CSS__, __BODY__, __EXTRA_JS__)
  templates/base.css            -- shared styles
  templates/test.css            -- quiz-specific styles
  templates/test_js_template.js -- JS for interactive quiz (__QUESTIONS_PLACEHOLDER__, __LABELS_PLACEHOLDER__)
  templates/test_labels.json    -- Chinese UI labels
"""

import os
import json

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')


def _read(filename):
    path = os.path.join(_TEMPLATES_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ''


_PAGE_TEMPLATE = _read('page_template.html')

_MATHJAX_CONFIG = '''<script>
MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\(', '\\)']],
    displayMath: [['$$', '$$'], ['\\[', '\\]']]
  }
};
</script>'''

_MATHJAX_SCRIPT = (
    '<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml-full.js"></script>'
)


def _build_page(title, body_html, css_extra='', js_extra=''):
    """Fill the page template. JS goes AFTER body -- critical for DOM access."""
    css = _read('base.css') + '\n' + css_extra
    return (
        _PAGE_TEMPLATE
        .replace('__TITLE__', title)
        .replace('__MATHJAX_CONFIG__', _MATHJAX_CONFIG)
        .replace('__MATHJAX_SCRIPT__', _MATHJAX_SCRIPT)
        .replace('__CSS__', css)
        .replace('__BODY__', body_html)
        .replace('__EXTRA_JS__', js_extra)
    )


# ─── Knowledge page ─────────────────────────────────────────────────

import re as _re

_TAG_LABELS = {'tag-must': '必考', 'tag-key': '重点', 'tag-freq': '高频', 'tag-info': '了解'}


def _normalize_tag_labels(html):
    """Fix tag chips whose text is the raw class name (a common note-agent slip:
    <span class="tag-info">tag-info</span> instead of …>了解</span>)."""
    if not html:
        return html
    def repl(m):
        cls, text = m.group(1), m.group(2).strip()
        if text in _TAG_LABELS or text == cls:
            return f'<span class="{cls}">{_TAG_LABELS.get(cls, text)}</span>'
        return m.group(0)
    return _re.sub(r'<span class="(tag-(?:must|key|freq|info))">([^<]*)</span>', repl, html)


def _strip_full_document(html):
    """If a note arrives as a *full* HTML document (some agents emit
    <!DOCTYPE><html><head><style>…</head><body>…</body></html>, sometimes with
    their own dark theme), keep only the <body> inner content and drop any
    leaked <head>/<style>/<script>. Otherwise return as-is.

    Without this, the note's own <style> overrides the page theme and the
    two-column layout — the cause of the dark background + broken widths.
    """
    if not html:
        return html
    m = _re.search(r'<body[^>]*>(.*)</body>', html, _re.DOTALL | _re.IGNORECASE)
    if m:
        html = m.group(1)
    html = _re.sub(r'<!DOCTYPE[^>]*>', '', html, flags=_re.IGNORECASE)
    html = _re.sub(r'</?html[^>]*>', '', html, flags=_re.IGNORECASE)
    html = _re.sub(r'<head[^>]*>.*?</head>', '', html, flags=_re.DOTALL | _re.IGNORECASE)
    html = _re.sub(r'<style[^>]*>.*?</style>', '', html, flags=_re.DOTALL | _re.IGNORECASE)
    html = _re.sub(r'<script[^>]*>.*?</script>', '', html, flags=_re.DOTALL | _re.IGNORECASE)
    return html.strip()


def _auto_toc_and_title(body_html, title):
    """Auto-inject H1 title + TOC block, and add anchor IDs to H2/H3 headings."""
    h1_html = '<h1>' + title + '</h1>\n'

    # Parse H2 and H3 headings, assign IDs
    toc_items = []

    def replace_heading(match):
        level = int(match.group(1))
        text = match.group(2).strip()
        # Drop page chips entirely (text + tag) so the TOC stays clean,
        # then strip remaining tags for the TOC entry.
        clean = _re.sub(r'<span class="pg-chip".*?</span>', '', text, flags=_re.DOTALL)
        clean = _re.sub(r'<[^>]+>', '', clean)
        # Generate anchor from a hash of the text (stable and safe)
        anchor = 's' + str(abs(hash(clean)))[:8]
        toc_items.append({'level': level, 'text': clean, 'anchor': anchor})
        return '<h' + str(level) + ' id="' + anchor + '">' + text + '</h' + str(level) + '>'

    body_html = _re.sub(r'<h([23])[^>]*?>(.+?)</h\1>', replace_heading, body_html, flags=_re.DOTALL)

    # Build TOC
    if toc_items:
        toc_html = '<div class="toc">\n<h2>目录</h2>\n<ul>\n'
        for item in toc_items:
            indent = '  ' if item['level'] == 3 else ''
            toc_html += indent + '<li><a href="#' + item['anchor'] + '">' + item['text'] + '</a></li>\n'
        toc_html += '</ul>\n</div>\n'
    else:
        toc_html = ''

    return h1_html + toc_html + body_html


def _build_slide_rail(slides):
    """Build the right-side Notion-style slide rail HTML from slide data.

    slides: list of {"page": str, "label": str, "img": data_uri, "text": str}
    Each card shows the rendered slide image + a collapsible original-text block.
    """
    cards = []
    for s in slides:
        page = s.get('page', '')
        label = s.get('label', f"第{page}页")
        img = s.get('img', '')
        text = (s.get('text') or '').strip()
        text_html = ''
        if text:
            # Escape minimal HTML, preserve line breaks
            safe = (text.replace('&', '&amp;').replace('<', '&lt;')
                        .replace('>', '&gt;').replace('\n', '<br>'))
            text_html = (
                '<details class="slide-text"><summary>原文文字</summary>'
                '<div class="slide-text-body">' + safe + '</div></details>'
            )
        iw = s.get('iw') or 0
        ih = s.get('ih') or 0
        dim_attr = (' width="' + str(iw) + '" height="' + str(ih) + '"') if (iw and ih) else ''
        cards.append(
            '<div class="slide-card" id="slide-p' + str(page) + '" data-page="' + str(page) + '">'
            '<div class="slide-card-label">' + label + '</div>'
            '<img class="slide-img"' + dim_attr + ' src="' + img + '" alt="' + label + '" '
            'onclick="window.__epaLightbox&&window.__epaLightbox(this.src)">'
            + text_html +
            '</div>'
        )
    return '\n'.join(cards)


_SLIDE_CSS = """
/* ── Notion-style slide cross-reference layout ── */
/* Override base.css body max-width (860px); fill the viewport edge-to-edge,
   capped only on ultra-wide screens for readability. */
body { max-width: 2400px; width: 96vw; padding-left: 2vw; padding-right: 2vw; }
.kn-layout { display: flex; gap: 36px; align-items: flex-start; width: 100%; margin: 0 auto; }
.kn-main { flex: 1 1 auto; min-width: 0; overflow-x: clip; }
.kn-main mjx-container[display="true"] { max-width: 100%; overflow-x: auto; overflow-y: hidden; }
.kn-rail { flex: 0 0 32%; max-width: 520px; min-width: 300px; position: sticky; top: 12px;
  align-self: flex-start; max-height: calc(100vh - 30px); overflow-y: auto; padding-right: 4px; }
.kn-rail-title { font-weight: 700; color: var(--ink-light); font-size: 0.9em; margin-bottom: 10px;
  padding-bottom: 6px; border-bottom: 1px solid var(--divider); }
.slide-card { border: 1px solid var(--card-border); border-radius: var(--radius);
  background: var(--card-bg); padding: 8px; margin-bottom: 14px; }
.slide-card-label { font-size: 0.78em; color: var(--ink-light); margin-bottom: 6px; }
.slide-img { width: 100%; height: auto; border-radius: 4px; cursor: zoom-in; display: block;
  border: 1px solid var(--divider); background: #fff; }
.slide-text { margin-top: 6px; font-size: 0.85em; }
.slide-text summary { cursor: pointer; color: var(--accent); user-select: none; }
.slide-text-body { margin-top: 6px; color: var(--ink-light); line-height: 1.6;
  max-height: 220px; overflow-y: auto; padding: 6px 8px; background: #fff;
  border-radius: 4px; border: 1px solid var(--divider); }
/* heading-side page chips */
.pg-chip { display: inline-block; font-size: 0.72em; font-weight: 600; color: var(--accent);
  background: #eff4ff; border: 1px solid #cfe0ff; border-radius: 10px; padding: 0 7px;
  margin-left: 6px; cursor: pointer; vertical-align: middle; }
.pg-chip:hover { background: #dbe8ff; }
.slide-card.flash { animation: slideflash 1.2s ease; }
@keyframes slideflash { 0%,100%{box-shadow:none;} 30%{box-shadow:0 0 0 3px var(--accent);} }
/* lightbox */
#epa-lightbox { position: fixed; inset: 0; background: rgba(0,0,0,0.82); display: none;
  align-items: center; justify-content: center; z-index: 9999; cursor: zoom-out; }
#epa-lightbox img { max-width: 94vw; max-height: 94vh; border-radius: 6px; }
/* Tablet / narrow desktop: keep two columns but rebalance + tighten margins */
@media (max-width: 1280px) {
  body { width: 98vw; padding-left: 1vw; padding-right: 1vw; }
  .kn-layout { gap: 24px; }
  .kn-main { flex: 1 1 54%; }
  .kn-rail { flex: 1 1 46%; }
}
/* Mobile: stack the rail below the notes */
@media (max-width: 900px) {
  body { width: 100%; padding-left: 12px; padding-right: 12px; }
  /* align-items:stretch is critical — in a COLUMN flex, flex-start would size
     children to max-content (overflowing the viewport). */
  .kn-layout { flex-direction: column; align-items: stretch; gap: 16px; }
  .kn-main { flex: none; width: 100%; }
  .kn-rail { position: static; flex: none; max-width: 100%; width: 100%; min-width: 0; max-height: none; }
}
"""

_SLIDE_JS = """<script>
window.__epaLightbox = function(src){
  var lb = document.getElementById('epa-lightbox');
  if(!lb){ lb = document.createElement('div'); lb.id='epa-lightbox';
    lb.innerHTML='<img>'; document.body.appendChild(lb);
    lb.addEventListener('click', function(){ lb.style.display='none'; }); }
  lb.querySelector('img').src = src; lb.style.display='flex';
};
document.addEventListener('click', function(e){
  var chip = e.target.closest('.pg-chip'); if(!chip) return;
  var pg = chip.getAttribute('data-page');
  var card = document.getElementById('slide-p'+pg);
  if(!card){
    // Fallback: notes may use "pdf-ref:pageN" format; extract trailing page number
    var m = pg.match(/(\\d+)\\s*$/);
    if(m){ var pgNum=m[1];
      card = document.querySelector('.slide-card[data-page$="-'+pgNum+'"]') ||
             document.querySelector('.slide-card[data-page="'+pgNum+'"]'); }
  }
  if(card){ card.scrollIntoView({behavior:'smooth', block:'center'});
    card.classList.remove('flash'); void card.offsetWidth; card.classList.add('flash'); }
});
// Shrink any display formula too wide for its column so it stays fully visible.
function __epaFitFormulas(){
  var list = document.querySelectorAll('.kn-main mjx-container[display="true"]');
  for(var i=0;i<list.length;i++){
    var m = list[i], parent = m.parentElement; if(!parent) continue;
    m.style.fontSize=''; // reset to measure natural width
    var avail = parent.clientWidth, w = m.scrollWidth;
    if(avail>0 && w>avail){ m.style.fontSize=(avail/w*0.97*100).toFixed(1)+'%'; }
  }
}
function __epaScheduleFit(){
  if(window.MathJax && MathJax.startup && MathJax.startup.promise){
    MathJax.startup.promise.then(__epaFitFormulas);
  } else { setTimeout(__epaFitFormulas, 900); }
}
if(document.readyState!=='loading'){ __epaScheduleFit(); }
else { document.addEventListener('DOMContentLoaded', __epaScheduleFit); }
var __epaFitT=null;
window.addEventListener('resize', function(){ clearTimeout(__epaFitT); __epaFitT=setTimeout(__epaFitFormulas,200); });
</script>"""


def _inject_heading_chips(body_html):
    """Turn heading-trailing <span data-slides="anchor1,anchor2"> markers into
    clickable [页N] chips that scroll the right rail to the matching slide.

    Notes agents may tag headings with data-slides; if absent this is a no-op.
    The chip label shows the trailing page number; data-page carries the full
    anchor id so the click handler can find the slide card.
    """
    def repl(m):
        anchors = m.group(1)
        chips = ''
        for a in anchors.split(','):
            a = a.strip()
            if not a:
                continue
            tail = _re.search(r'(\d+)\s*$', a)
            label = tail.group(1) if tail else a
            chips += ('<span class="pg-chip" data-page="' + a + '">页' + label + '</span>')
        return chips
    return _re.sub(r'<span\s+data-slides="([^"]*)"\s*></span>', repl, body_html)


def _norm_label(s):
    """Normalize a heading/KC label for fuzzy matching: strip tags, tag-words, spaces."""
    s = _re.sub(r'<[^>]+>', '', s)
    s = _re.sub(r'(必考|重点|高频|了解)', '', s)
    s = _re.sub(r'\s+', '', s)
    return s.strip()


def _auto_tag_headings(body_html, kcs, slides):
    """Auto-inject <span data-slides> into H2/H3 headings by matching their text
    to knowledge-component labels, mapping each KC's source_refs pages to the
    rendered slide anchors. Lets existing notes (no manual tags) get page chips.
    """
    if not kcs or not slides:
        return body_html

    # (pdf_basename, raw_page) -> anchor id
    anchor_of = {}
    for s in slides:
        anchor_of[(s.get('pdf', ''), int(s.get('raw_page', -1)))] = s.get('page')

    # Precompute each KC's available anchors (only pages that were actually rendered)
    from slide_renderer import parse_refs_by_pdf
    kc_anchors = []
    for kc in kcs:
        label = _norm_label(kc.get('label', ''))
        if not label:
            continue
        anchors = []
        by_pdf = parse_refs_by_pdf(kc.get('source_refs'))
        for pdf_name, pages in by_pdf.items():
            for pg in sorted(pages):
                # try exact pdf match, then any pdf (single-PDF chapters use '')
                anc = anchor_of.get((pdf_name, pg))
                if anc is None:
                    for (p2, pg2), a2 in anchor_of.items():
                        if pg2 == pg and (pdf_name == '' or p2 == pdf_name):
                            anc = a2
                            break
                if anc is not None and anc not in anchors:
                    anchors.append(anc)
        if anchors:
            kc_anchors.append((label, anchors))

    if not kc_anchors:
        return body_html

    def repl(m):
        level, attrs, inner = m.group(1), m.group(2), m.group(3)
        head_norm = _norm_label(inner)
        if not head_norm:
            return m.group(0)
        # find best KC whose label overlaps this heading
        best = None
        for label, anchors in kc_anchors:
            if label in head_norm or head_norm in label:
                if best is None or len(label) > len(best[0]):
                    best = (label, anchors)
        if not best:
            return m.group(0)
        # One chip per heading — jump to the section's first slide; the rail
        # holds the rest. (Avoids dozens of chips for wide page ranges.)
        marker = '<span data-slides="' + best[1][0] + '"></span>'
        return '<h' + level + attrs + '>' + inner + marker + '</h' + level + '>'

    return _re.sub(r'<h([23])([^>]*)>(.*?)</h\1>', repl, body_html, flags=_re.DOTALL)


def _knowledge_body(body_html, title, slides=None, kcs=None, add_h1=True):
    """Build the knowledge-list inner HTML + the CSS/JS it needs.

    Returns (body_html, css_extra, js_extra). Shared by save_knowledge_html and
    save_combined_html so the slide-rail layout is identical in both.
    """
    body_html = _strip_full_document(body_html)
    body_html = _normalize_tag_labels(body_html)
    if slides and kcs:
        body_html = _auto_tag_headings(body_html, kcs, slides)
    body_html = _inject_heading_chips(body_html)
    body_html = _auto_toc_and_title(body_html, title if add_h1 else '')

    css_extra = ''
    js_extra = ''
    if slides:
        rail = _build_slide_rail(slides)
        body_html = (
            '<div class="kn-layout"><div class="kn-main">' + body_html + '</div>'
            '<aside class="kn-rail"><div class="kn-rail-title">📑 原始幻灯片对照</div>'
            + rail + '</aside></div>'
        )
        css_extra = _SLIDE_CSS
        js_extra = _SLIDE_JS
    return body_html, css_extra, js_extra


def save_knowledge_html(body_html, output_path, title, slides=None, kcs=None):
    """Render the knowledge list. If `slides` is provided, add a Notion-style
    right-side slide rail (rendered PPT pages + collapsible original text).

    If `kcs` (the chapter's knowledge components) is also given, headings are
    auto-tagged with page chips that scroll the rail to the matching slide —
    so existing notes get the click-to-locate links without re-running agents.
    """
    body_html, css_extra, js_extra = _knowledge_body(body_html, title, slides, kcs)
    html = _build_page(title, body_html, css_extra=css_extra, js_extra=js_extra)
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

# ─── Knowledge graph page ─────────────────────────────────────────

def save_graph_html(tree_json: dict, output_path: str, title: str):
    """Generate an interactive knowledge graph page.

    tree_json: {"title": "...", "nodes": [...]}
    """
    tree_data_js = 'const TREE_DATA = ' + json.dumps(tree_json, ensure_ascii=False) + ';'

    graph_css = _read('graph.css')
    graph_js = _read('graph.js')
    graph_template = _read('graph_template.html')

    html = graph_template
    html = html.replace('__TITLE__', title)
    html = html.replace('__MATHJAX_CONFIG__', _MATHJAX_CONFIG)
    html = html.replace('__MATHJAX_SCRIPT__', _MATHJAX_SCRIPT)
    html = html.replace('__CSS__', graph_css)
    html = html.replace('__TREE_DATA__', tree_data_js)
    html = html.replace('__JS__', graph_js)

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


# ─── Interactive test page ──────────────────────────────────────────

# A well-formed HTML tag: <tag …>, </tag>, or <br/> — no < or > inside it.
_WELL_FORMED_TAG = _re.compile(r'</?[a-zA-Z][a-zA-Z0-9]*(?:\s[^<>]*)?/?>')


def _escape_stray_lt(text):
    """Escape every `<` that is NOT part of a well-formed HTML tag.

    Question/explanation text legitimately mixes real formatting tags
    (<pre>, <code>, <strong>…) with literal less-than signs from math/code
    (low<high, i<n, a<b). A raw `<high` with no matching `>` is parsed by the
    browser as an unclosed tag that swallows every following question. Keeping
    only complete `<tag…>` forms and escaping the rest is robust even when a
    tag name collides with a variable (b, i, a), because the literal has no `>`.
    """
    if not isinstance(text, str):
        return text
    parts = []
    last = 0
    for m in _WELL_FORMED_TAG.finditer(text):
        parts.append(text[last:m.start()].replace('<', '&lt;'))
        parts.append(m.group(0))
        last = m.end()
    parts.append(text[last:].replace('<', '&lt;'))
    return ''.join(parts)


def _sanitize_questions(questions):
    """Return a copy of the questions with stray `<` escaped in all rendered
    string fields, so malformed inequalities can't break the page structure."""
    out = []
    for q in questions:
        if not isinstance(q, dict):
            out.append(q)
            continue
        q = dict(q)
        for f in ('question', 'explanation', 'pitfall'):
            if isinstance(q.get(f), str):
                q[f] = _escape_stray_lt(q[f])
        if isinstance(q.get('options'), list):
            q['options'] = [_escape_stray_lt(o) if isinstance(o, str) else o for o in q['options']]
        if isinstance(q.get('answer'), str):
            q['answer'] = _escape_stray_lt(q['answer'])
        elif isinstance(q.get('answer'), list):
            q['answer'] = [_escape_stray_lt(a) if isinstance(a, str) else a for a in q['answer']]
        out.append(q)
    return out


def _test_body_and_js(questions, title, subtitle='', duration_minutes=30, add_h1=True):
    """Build the interactive-test inner HTML + its JS. Shared by save_test and
    save_combined_html. Returns (body_html, js_extra)."""
    questions = _sanitize_questions(questions)
    questions_json = json.dumps(questions, ensure_ascii=False)
    labels = json.loads(_read('test_labels.json'))
    labels_json = json.dumps(labels, ensure_ascii=False)

    js_template = _read('test_js_template.js')
    js = js_template.replace('__QUESTIONS_PLACEHOLDER__', questions_json)
    js = js.replace('__LABELS_PLACEHOLDER__', labels_json)
    js = '<script>\n' + js + '\n</script>'

    if subtitle:
        sub_html = '<p style="text-align:center;color:var(--ink-light);font-size:0.95em">' + subtitle + '</p>'
    else:
        sub_html = '<p style="text-align:center;color:var(--ink-light);font-size:0.95em">' + labels['duration_prefix'] + str(duration_minutes) + labels['duration_suffix'] + '</p>'

    rows = []
    if add_h1:
        rows.append('<h1>' + title + '</h1>')
    rows += [
        '<h2 style="text-align:center">' + labels['page_title'] + '</h2>',
        sub_html,
        '',
        '<div id="score-box"><div class="score-num" id="score-num">0</div><div class="score-label">' + labels['score_label'] + '</div></div>',
        '<div id="questions-container"></div>',
        '<div class="grading-bar no-print"><button onclick="gradeAll()" id="grade-btn">' + labels['grade_button'] + '</button></div>',
    ]
    return '\n'.join(rows), js


def save_test(questions, output_path, title, subtitle='', duration_minutes=30):
    """Generate an interactive test page.

    questions: list of {type, points, question, options, answer, explanation, pitfall}
    subtitle: optional custom subtitle (overrides auto-generated duration subtitle)
    duration_minutes: used in auto-generated subtitle if subtitle is empty
    """
    body, js = _test_body_and_js(questions, title, subtitle, duration_minutes)
    html = _build_page(title, body, css_extra=_read('test.css'), js_extra=js)
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


# ─── Combined page: knowledge list + test in one file with top tabs ──

_TAB_CSS = """
/* ── Combined page: top tab bar (清单 | 题目) ── */
#epa-tabs { display: flex; gap: 0; justify-content: center; margin: 6px auto 22px;
  max-width: 520px; border: 1px solid var(--divider); border-radius: 10px; overflow: hidden; }
#epa-tabs .tab-btn { flex: 1; padding: 10px 18px; cursor: pointer; border: none;
  background: var(--paper-dark); color: var(--ink-light); font-size: 1.02em; font-weight: 600;
  font-family: inherit; transition: background .15s, color .15s; }
#epa-tabs .tab-btn + .tab-btn { border-left: 1px solid var(--divider); }
#epa-tabs .tab-btn.active { background: var(--accent); color: #fff; }
#epa-tabs .tab-btn:not(.active):hover { background: #efe7d3; color: var(--ink); }
.tab-panel { display: none; }
.tab-panel.active { display: block; }
/* keep the test readable/centered even though the body is wide for the rail */
#panel-test { max-width: 980px; margin: 0 auto; }
@media print { #epa-tabs { display: none; } .tab-panel { display: block !important; } }
"""

_TAB_JS = """<script>
document.addEventListener('click', function(e){
  var btn = e.target.closest('#epa-tabs .tab-btn'); if(!btn) return;
  var tab = btn.getAttribute('data-tab');
  document.querySelectorAll('#epa-tabs .tab-btn').forEach(function(b){ b.classList.toggle('active', b===btn); });
  document.querySelectorAll('.tab-panel').forEach(function(p){
    p.classList.toggle('active', p.id === 'panel-' + tab); });
  // The test panel is display:none on load, so build()'s MathJax typeset ran
  // on hidden content (collapsing formula question cards to 0 height). Re-run
  // build() the first time the panel is visible so it renders + typesets at the
  // real size. Guarded so user answers aren't wiped on later switches.
  if(tab === 'test' && !window.__epaTestBuilt){
    window.__epaTestBuilt = true;
    if(typeof build === 'function'){ try { build(); } catch(err){} }
  }
  if(window.__epaFitFormulas) setTimeout(window.__epaFitFormulas, 50);
  window.scrollTo(0, 0);
});
</script>"""


def save_combined_html(body_html, questions, output_path, title,
                       slides=None, kcs=None, subtitle='', duration_minutes=30):
    """One page holding both the knowledge list and the test, switched by top
    tabs (📖 知识清单 | 📝 章节测试). Reuses the slide rail + quiz engines."""
    kn_body, kn_css, kn_js = _knowledge_body(body_html, title, slides, kcs, add_h1=False)
    test_body, test_js = _test_body_and_js(questions, title, subtitle, duration_minutes, add_h1=False)

    body = (
        '<h1>' + title + '</h1>'
        '<div id="epa-tabs" class="no-print">'
        '<button class="tab-btn active" data-tab="kn">📖 知识清单</button>'
        '<button class="tab-btn" data-tab="test">📝 章节测试</button>'
        '</div>'
        '<div id="panel-kn" class="tab-panel active">' + kn_body + '</div>'
        '<div id="panel-test" class="tab-panel">' + test_body + '</div>'
    )

    css_extra = _read('test.css') + '\n' + kn_css + '\n' + _TAB_CSS
    js_extra = kn_js + '\n' + test_js + '\n' + _TAB_JS

    # Expose the formula-fit helper globally so tab-switch can re-run it.
    js_extra = js_extra.replace('function __epaFitFormulas(', 'window.__epaFitFormulas = function __epaFitFormulas(')

    html = _build_page(title, body, css_extra=css_extra, js_extra=js_extra)
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
