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


def _normalize_math_delimiters(html):
    """Convert \\(...\\) and \\[...\\] to $...$ and $$...$$ outside code/pre blocks.

    MathJax may misparse \\([...)\\) when [ immediately follows \\( because some
    TeX parsers treat [ as an optional-argument opener. Dollar delimiters are
    unambiguous and more portable. Leaves <pre>/<code> blocks untouched.
    """
    if not html:
        return html
    result = []
    last = 0
    for blk in _re.finditer(r'<(?:pre|code)[^>]*>.*?</(?:pre|code)>', html, _re.DOTALL | _re.IGNORECASE):
        chunk = html[last:blk.start()]
        chunk = _re.sub(r'\\\[(.+?)\\\]', r'$$\1$$', chunk, flags=_re.DOTALL)
        chunk = _re.sub(r'\\\((.+?)\\\)', r'$\1$', chunk, flags=_re.DOTALL)
        result.append(chunk)
        result.append(blk.group(0))
        last = blk.end()
    chunk = html[last:]
    chunk = _re.sub(r'\\\[(.+?)\\\]', r'$$\1$$', chunk, flags=_re.DOTALL)
    chunk = _re.sub(r'\\\((.+?)\\\)', r'$\1$', chunk, flags=_re.DOTALL)
    result.append(chunk)
    return ''.join(result)


def _inject_heading_chips(body_html, slides=None):
    """Turn heading-trailing <span data-slides="..."> markers into clickable [页N] chips.

    When slides is provided, resolves page numbers to actual slide card anchor IDs
    (which for multi-PDF chapters look like "3 分治-1-19", not just "19"), fixing
    the format mismatch between manually-written notes and the slide renderer output.
    """
    page_to_anchor = {}
    if slides:
        for s in slides:
            raw = s.get('raw_page')
            if raw is not None:
                page_to_anchor[int(raw)] = s.get('page', '')

    def repl(m):
        anchors_str = m.group(1)
        chips = ''
        for a in anchors_str.split(','):
            a = a.strip()
            if not a:
                continue
            # "3-1:19-21" → first page after : or / is the display page
            colon_m = _re.search(r'[:/](\d+)', a)
            if colon_m:
                pg_num = int(colon_m.group(1))
                label = colon_m.group(1)
            else:
                tail = _re.search(r'(\d+)', a)
                label = tail.group(1) if tail else a
                pg_num = int(label) if tail else None
            anchor = page_to_anchor.get(pg_num, a) if (page_to_anchor and pg_num is not None) else a
            chips += ('<span class="pg-chip" data-page="' + anchor + '">页' + label + '</span>')
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
    body_html = _normalize_math_delimiters(body_html)
    if slides and kcs:
        body_html = _auto_tag_headings(body_html, kcs, slides)
    body_html = _inject_heading_chips(body_html, slides)
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
    string fields, so malformed inequalities can't break the page structure.
    Also normalizes tf answers: numeric 0/1 → boolean (0→false, 1→true),
    string "0"/"1" → boolean, so the JS grading logic always sees consistent types."""
    out = []
    for q in questions:
        if not isinstance(q, dict):
            out.append(q)
            continue
        q = dict(q)
        # Normalize tf answer to boolean BEFORE escaping
        if q.get('type') == 'tf':
            ans = q.get('answer')
            if isinstance(ans, (int, float)):
                q['answer'] = bool(ans)
            elif isinstance(ans, str):
                s = ans.strip().lower()
                if s in ('0', 'false', '错误', '错', '否', 'no', 'n', 'f', '×', 'x'):
                    q['answer'] = False
                elif s in ('1', 'true', '正确', '对', '是', 'yes', 'y', 't', '√', '✓'):
                    q['answer'] = True
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
        '<div class="save-bar no-print"><button onclick="saveForGrading()">🤖 AI一键批改</button></div>',
        '<div id="epa-grade-modal">'
        '<div class="epa-grade-dialog">'
        '<h3>📋 AI批改任务已生成</h3>'
        '<p>答案已下载为 JSON 文件（通常在<strong>下载</strong>文件夹）。'
        '将以下命令发送给 Claude Code EPA skill，AI 会自动批改并生成报告：</p>'
        '<div class="epa-grade-cmd" id="epa-grade-cmd-text">/exampass grade "&lt;路径&gt;"</div>'
        '<p style="font-size:0.85em;color:#999;margin:0 0 14px">将 &lt;路径&gt; 替换为刚下载的 JSON 文件的完整路径。</p>'
        '<div class="epa-grade-dialog-btns">'
        '<button class="btn-copy" id="epa-grade-copy-btn" onclick="__epaCopyGradeCmd()">复制命令</button>'
        '<button class="btn-close-modal" onclick="__epaCloseGradeModal()">关闭</button>'
        '</div></div></div>',
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
/* ── Combined page: top tab bar (清单 | 题目) ──
   Sticky so 清单/测试 switching stays reachable after scrolling. This replaces
   the old floating FAB, which was pinned bottom-right and permanently covered
   (and click-blocked) the bottom-right slide card of the PPT 对照 rail. */
#epa-tabs { position: sticky; top: 4px; z-index: 1000;
  display: flex; gap: 0; justify-content: center; margin: 6px auto 22px;
  max-width: 520px; border: 1px solid var(--divider); border-radius: 10px; overflow: hidden;
  background: var(--paper); box-shadow: 0 2px 10px rgba(0,0,0,0.10); }
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
/* When the tab bar is pinned at the top, drop the sticky slide rail below it so
   the bar never covers the first slide card. `top` only affects the PINNED
   position — initial layout still top-aligns the rail with the notes column. */
.kn-rail { top: 60px; max-height: calc(100vh - 74px); }
@media print { #epa-tabs { position: static; display: none; } .tab-panel { display: block !important; } }
"""

_TAB_JS = """<script>
function __epaSwitch(tab) {
  document.querySelectorAll('#epa-tabs .tab-btn').forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-tab') === tab); });
  document.querySelectorAll('.tab-panel').forEach(function(p){
    p.classList.toggle('active', p.id === 'panel-' + tab); });
  // The test panel is display:none on load, so build()'s MathJax typeset ran
  // on hidden content. Re-run build() the first time the panel is visible so
  // it renders + typesets at the real size. Guarded so answers aren't wiped.
  if(tab === 'test' && !window.__epaTestBuilt){
    window.__epaTestBuilt = true;
    if(typeof build === 'function'){ try { build(); } catch(err){} }
  } else if(tab === 'test' && window.MathJax && MathJax.typesetPromise){
    var panel = document.getElementById('panel-test');
    if(panel) MathJax.typesetPromise([panel]).catch(function(){});
  }
  if(window.__epaFitFormulas) setTimeout(window.__epaFitFormulas, 50);
  window.scrollTo(0, 0);
}
document.addEventListener('click', function(e){
  var btn = e.target.closest('#epa-tabs .tab-btn'); if(!btn) return;
  __epaSwitch(btn.getAttribute('data-tab'));
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


# ─── Grade report page ───────────────────────────────────────────────

_GRADE_REPORT_CSS = """
body { font-family: 'PingFang SC','Noto Sans SC','Segoe UI',sans-serif;
  max-width: 860px; margin: 0 auto; padding: 20px 24px 60px;
  background: #faf8f3; color: #2d2a24; line-height: 1.7; }
a { color: #6060d0; }
.gr-header { text-align: center; padding: 20px 0 8px; border-bottom: 2px solid #e0d8c8; margin-bottom: 24px; }
.gr-brand { font-size: 0.9em; color: #888; letter-spacing: 0.5px; }
.gr-title { font-size: 1.6em; font-weight: 700; margin: 6px 0 4px; }
.gr-meta { font-size: 0.88em; color: #777; }
.gr-score-box { display: flex; gap: 16px; flex-wrap: wrap; margin: 20px 0 28px;
  background: #fff; border-radius: 10px; padding: 16px 20px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.07); border: 1px solid #e0d8c8; }
.gr-score-item { flex: 1; min-width: 120px; text-align: center; }
.gr-score-num { font-size: 2em; font-weight: 700; }
.gr-score-num.total { color: #6060d0; }
.gr-score-num.ok { color: #16a34a; }
.gr-score-num.sub { color: #d97706; }
.gr-score-label { font-size: 0.82em; color: #888; margin-top: 2px; }
.gr-section { margin: 28px 0 10px; font-size: 1.12em; font-weight: 700;
  border-left: 4px solid #6060d0; padding-left: 10px; }
.gr-qcard { background: #fff; border: 1px solid #e0d8c8; border-radius: 8px;
  padding: 12px 16px; margin: 10px 0; }
.gr-qcard.gr-correct { border-left: 3px solid #16a34a; }
.gr-qcard.gr-wrong { border-left: 3px solid #dc2626; }
.gr-qcard.gr-partial { border-left: 3px solid #f59e0b; }
.gr-qcard.gr-ref { border-left: 3px solid #6060d0; }
.gr-qnum { font-weight: 700; font-size: 0.9em; color: #888; margin-bottom: 4px; }
.gr-qtext { margin-bottom: 6px; }
.gr-badge { display: inline-block; padding: 1px 8px; border-radius: 3px;
  font-size: 0.8em; font-weight: 700; margin-right: 6px; }
.badge-ok  { background: #dcfce7; color: #166534; }
.badge-no  { background: #fee2e2; color: #991b1b; }
.badge-par { background: #fef3c7; color: #92400e; }
.badge-ref { background: #dbeafe; color: #1e40af; }
.gr-answer { font-size: 0.9em; color: #555; margin: 4px 0; }
.gr-comment { font-size: 0.9em; color: #444; margin: 4px 0; background: #f0f4ff;
  border-radius: 4px; padding: 6px 10px; }
.gr-explanation { font-size: 0.88em; color: #666; margin-top: 4px; }
.gr-kc-table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.93em; }
.gr-kc-table th { background: #f0ede0; padding: 7px 10px; text-align: left; }
.gr-kc-table td { padding: 6px 10px; border-bottom: 1px solid #e8e0d0; }
.gr-bar-wrap { background: #e8e0d0; border-radius: 6px; height: 8px; width: 120px;
  display: inline-block; vertical-align: middle; overflow: hidden; }
.gr-bar { border-radius: 6px; height: 8px; background: #6060d0; }
.gr-bar.low  { background: #dc2626; }
.gr-bar.mid  { background: #f59e0b; }
.gr-bar.high { background: #16a34a; }
.gr-footer { text-align: center; margin-top: 40px; padding-top: 16px;
  border-top: 1px solid #e0d8c8; font-size: 0.82em; color: #999; }
.gr-footer a { color: #6060d0; text-decoration: none; }
"""

_GRADE_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>__TITLE__</title>
__MATHJAX_CONFIG__
__MATHJAX_SCRIPT__
<style>
__CSS__
</style>
</head>
<body>
__BODY__
</body>
</html>"""


def save_grade_report_html(grade_data: dict, output_path: str):
    """Generate a standalone HTML grade report.

    grade_data keys:
        chapter, submitted_at, graded_at, grade_count,
        total_score, max_score, objective_score, objective_max,
        subjective_score, subjective_max,
        results (list of per-question dicts),
        kc_mastery { kc_id: {label, score, max, pct} },
        wrong_questions (list of result indices)

    Each result: index, type, question, options, user_answer, correct_answer,
                 score, max_points, verdict, comment, explanation, kc_id, images
    """
    chapter = grade_data.get('chapter', '章节测试')
    submitted = grade_data.get('submitted_at', '')[:16].replace('T', ' ')
    graded = grade_data.get('graded_at', '')[:16].replace('T', ' ')
    grade_count = grade_data.get('grade_count', 1)
    total = grade_data.get('total_score', 0)
    max_s = grade_data.get('max_score', 100)
    obj = grade_data.get('objective_score', 0)
    obj_max = grade_data.get('objective_max', 0)
    sub = grade_data.get('subjective_score', 0)
    sub_max = grade_data.get('subjective_max', 0)
    results = grade_data.get('results', [])
    kc_mastery = grade_data.get('kc_mastery', {})

    pct = round(total / max_s * 100) if max_s else 0
    report_title = chapter + ' · 第' + str(grade_count) + '次批改'

    def fmt_ans(q_type, ans, options=None):
        if ans is None:
            return '（未作答）'
        if q_type == 'tf':
            if isinstance(ans, int):
                return '正确' if ans == 0 else '错误'
            return '正确' if ans else '错误'
        if q_type == 'choice' and options and isinstance(ans, int) and ans < len(options):
            return chr(65 + ans) + '. ' + str(options[ans])
        if q_type == 'multi' and isinstance(ans, list) and options:
            return '  '.join(chr(65 + i) + '. ' + str(options[i]) for i in sorted(ans) if i < len(options))
        if q_type == 'fill' and isinstance(ans, list):
            return '  /  '.join(str(a) for a in ans)
        return str(ans) if not isinstance(ans, list) else '  /  '.join(str(a) for a in ans)

    def verdict_badge(v):
        m = {
            'correct':   ('<span class="gr-badge badge-ok">正确</span>', 'gr-correct'),
            'partial':   ('<span class="gr-badge badge-par">部分正确</span>', 'gr-partial'),
            'wrong':     ('<span class="gr-badge badge-no">错误</span>', 'gr-wrong'),
            'reference': ('<span class="gr-badge badge-ref">参考答案</span>', 'gr-ref'),
        }
        return m.get(v, ('<span class="gr-badge badge-ref">-</span>', 'gr-ref'))

    _SUBJ = {'short', 'calc', 'code', 'essay', 'comprehensive'}

    q_rows = ''
    for r in results:
        badge_html, card_cls = verdict_badge(r.get('verdict', 'reference'))
        opts = r.get('options')
        user_str = _escape_stray_lt(fmt_ans(r['type'], r.get('user_answer'), opts))
        user_ans_html = '<div class="gr-answer">你的答案：' + user_str + '</div>'
        correct_ans_html = ''
        if r.get('verdict') in ('wrong', 'partial') and r.get('correct_answer') is not None and r['type'] not in _SUBJ:
            correct_ans_html = '<div class="gr-answer">正确答案：<strong>' + _escape_stray_lt(fmt_ans(r['type'], r.get('correct_answer'), opts)) + '</strong></div>'
        comment_html = '<div class="gr-comment">💬 ' + r['comment'] + '</div>' if r.get('comment') else ''
        exp_html = '<div class="gr-explanation">解析：' + r['explanation'] + '</div>' if r.get('explanation') else ''
        imgs_html = ''.join(
            '<img src="' + img + '" style="max-width:100%;max-height:200px;border-radius:4px;border:1px solid #e0d8c8;display:block;margin:4px 0">'
            for img in (r.get('images') or [])
        )
        q_rows += (
            '<div class="gr-qcard ' + card_cls + '">'
            '<div class="gr-qnum">' + str(r['index'] + 1) + '. (' + str(r['max_points']) + '分) ' + badge_html +
            '<span style="float:right;font-weight:700;color:#555">' + str(r.get('score', 0)) + ' / ' + str(r['max_points']) + '</span></div>'
            '<div class="gr-qtext">' + r['question'] + '</div>'
            + imgs_html + user_ans_html + correct_ans_html + comment_html + exp_html +
            '</div>'
        )

    wrong_items = [r for r in results if r.get('verdict') in ('wrong', 'partial')]
    wrong_html = ''
    if wrong_items:
        wrong_html = '<div class="gr-section">❌ 错题整理</div>'
        for r in wrong_items:
            badge_html, card_cls = verdict_badge(r.get('verdict', 'wrong'))
            opts = r.get('options')
            correct_ans = ''
            if r.get('correct_answer') is not None and r['type'] not in _SUBJ:
                correct_ans = '（正确答案：' + fmt_ans(r['type'], r.get('correct_answer'), opts) + '）'
            comment = ('<div class="gr-comment">' + r['comment'] + '</div>') if r.get('comment') else ''
            exp = ('<div class="gr-explanation">解析：' + r['explanation'] + '</div>') if r.get('explanation') else ''
            wrong_html += (
                '<div class="gr-qcard ' + card_cls + '">'
                '<div class="gr-qnum">' + str(r['index'] + 1) + '. ' + badge_html + correct_ans + '</div>'
                '<div class="gr-qtext">' + r['question'] + '</div>'
                + comment + exp + '</div>'
            )

    kc_html = ''
    if kc_mastery:
        kc_html = '<div class="gr-section">📊 知识点掌握分析</div><table class="gr-kc-table"><thead><tr><th>知识点</th><th>得分</th><th>掌握度</th></tr></thead><tbody>'
        for kc_id, info in kc_mastery.items():
            p = info.get('pct', 0)
            bar_cls = 'high' if p >= 80 else ('mid' if p >= 50 else 'low')
            kc_html += (
                '<tr><td>' + info.get('label', kc_id) + '</td>'
                '<td>' + str(info.get('score', 0)) + ' / ' + str(info.get('max', 0)) + '</td>'
                '<td><span class="gr-bar-wrap"><span class="gr-bar ' + bar_cls + '" style="width:' + str(max(0, min(100, int(p)))) + '%"></span></span> ' + str(p) + '%</td></tr>'
            )
        kc_html += '</tbody></table>'

    body = (
        '<div class="gr-header">'
        '<div class="gr-brand">ExamPass Assistant &nbsp;·&nbsp; <a href="https://github.com/WUBING2023/ExamPass-Assistant" target="_blank">github.com/WUBING2023/ExamPass-Assistant</a></div>'
        '<div class="gr-title">' + chapter + '</div>'
        '<div class="gr-meta">第 ' + str(grade_count) + ' 次批改 &nbsp;·&nbsp; 提交：' + submitted + ' &nbsp;·&nbsp; 批改：' + graded + '</div>'
        '</div>'
        '<div class="gr-score-box">'
        '<div class="gr-score-item"><div class="gr-score-num total">' + str(round(total, 1)) + '</div><div class="gr-score-label">总分 / ' + str(max_s) + '（' + str(pct) + '%）</div></div>'
        + ('<div class="gr-score-item"><div class="gr-score-num ok">' + str(round(obj, 1)) + '</div><div class="gr-score-label">客观题 / ' + str(obj_max) + '</div></div>' if obj_max else '')
        + ('<div class="gr-score-item"><div class="gr-score-num sub">' + str(round(sub, 1)) + '</div><div class="gr-score-label">主观题 / ' + str(sub_max) + '</div></div>' if sub_max else '')
        + '</div>'
        '<div class="gr-section">📝 逐题批改</div>'
        + q_rows
        + wrong_html
        + kc_html
        + '<div class="gr-footer">Generated by <a href="https://github.com/WUBING2023/ExamPass-Assistant" target="_blank">ExamPass Assistant</a></div>'
    )

    html = (
        _GRADE_REPORT_TEMPLATE
        .replace('__TITLE__', report_title)
        .replace('__MATHJAX_CONFIG__', _MATHJAX_CONFIG)
        .replace('__MATHJAX_SCRIPT__', _MATHJAX_SCRIPT)
        .replace('__CSS__', _GRADE_REPORT_CSS)
        .replace('__BODY__', body)
    )

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
