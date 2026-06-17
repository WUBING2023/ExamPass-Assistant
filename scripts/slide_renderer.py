"""Render PDF pages as full-slide images and build slide rails for the
knowledge list's Notion-style PPT cross-reference panel.

Unlike image_extractor.py (which pulls *embedded* images out of slides),
this renders each whole PDF page to a raster image — matching the
"paste the original slide next to the note" workflow.
"""

import os
import io
import re
import base64
import json

try:
    import fitz  # pymupdf
except ImportError:
    fitz = None

try:
    from PIL import Image
except ImportError:
    Image = None


def render_pdf_pages(pdf_path, out_dir, dpi=110, only_pages=None):
    """Render each PDF page to a PNG in out_dir.

    only_pages: optional set of 1-based page numbers to render (others skipped).
    Returns a list of {"page": int, "img_path": str} in page order.
    """
    if fitz is None:
        raise RuntimeError("pymupdf (fitz) 未安装，无法渲染整页幻灯片")
    os.makedirs(out_dir, exist_ok=True)
    results = []
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for i in range(len(doc)):
        page_no = i + 1
        if only_pages is not None and page_no not in only_pages:
            continue
        page = doc[i]
        pix = page.get_pixmap(matrix=mat)
        fname = f"slide_p{page_no}.png"
        fpath = os.path.join(out_dir, fname)
        pix.save(fpath)
        results.append({"page": page_no, "img_path": fpath})
    doc.close()
    return results


def extract_page_texts(pdf_path):
    """Return {page_number(1-based): text} for a PDF."""
    if fitz is None:
        return {}
    texts = {}
    doc = fitz.open(pdf_path)
    for i in range(len(doc)):
        texts[i + 1] = doc[i].get_text().strip()
    doc.close()
    return texts


def _img_to_data_uri(img_path, max_width=900, quality=72):
    """Downscale + JPEG-compress an image, return (data_uri, width, height).

    Returning the final dimensions lets the HTML reserve correct space for
    each slide (no collapsed/short boxes before the image decodes).
    Keeps the HTML self-contained and portable while controlling size.
    """
    if Image is None:
        # Fallback: embed raw bytes as PNG, unknown dimensions
        with open(img_path, 'rb') as f:
            raw = f.read()
        b64 = base64.b64encode(raw).decode('ascii')
        return f"data:image/png;base64,{b64}", 0, 0
    img = Image.open(img_path)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    if img.width > max_width:
        h = int(img.height * max_width / img.width)
        img = img.resize((max_width, h), Image.LANCZOS)
    w, h = img.width, img.height
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    return f"data:image/jpeg;base64,{b64}", w, h


def _pages_from_spec(spec):
    """Parse the page part of a ref (after the PDF name): '19-24', '25', '第55页'."""
    pages = set()
    s = str(spec)
    for m in re.finditer(r'(\d+)\s*[-~–]\s*(\d+)', s):
        a, b = int(m.group(1)), int(m.group(2))
        if a <= b and b - a < 300:
            pages.update(range(a, b + 1))
    # remove already-consumed ranges, then grab singletons
    s_no_range = re.sub(r'\d+\s*[-~–]\s*\d+', ' ', s)
    for m in re.finditer(r'\d+', s_no_range):
        pages.add(int(m.group(0)))
    return pages


def parse_refs_by_pdf(source_refs):
    """Parse skeleton source_refs into {pdf_basename: set(pages)}.

    Expected form: "<pdf name>/<pages>" e.g. "3 分治-1.pdf/19-24".
    Falls back gracefully: a ref with no '.pdf/' is treated as pages for an
    unnamed key ('') so callers can still apply them.
    """
    by_pdf = {}
    for ref in source_refs or []:
        s = str(ref).strip()
        # Split on the .pdf/ boundary (case-insensitive)
        m = re.search(r'(.*?\.pdf)\s*[/／]\s*(.*)', s, re.IGNORECASE)
        if m:
            pdf_name = os.path.basename(m.group(1).strip())
            pages = _pages_from_spec(m.group(2))
        else:
            # No explicit pdf/page split: treat whole thing as page spec under ''
            pdf_name = ''
            pages = _pages_from_spec(s)
        if pages:
            by_pdf.setdefault(pdf_name, set()).update(pages)
    return by_pdf


def select_key_pages_by_pdf(skeleton, chapter_label):
    """Collect {pdf_basename: set(pages)} referenced by must/key KCs of a chapter."""
    result = {}
    for ch in skeleton.get('chapters', []):
        label = ch.get('label', '')
        if chapter_label and chapter_label not in label and label not in chapter_label:
            continue
        for kc in ch.get('kcs', []) or []:
            if kc.get('importance') in ('must', 'key'):
                for pdf_name, pages in parse_refs_by_pdf(kc.get('source_refs')).items():
                    result.setdefault(pdf_name, set()).update(pages)
    return result


def select_key_pages(skeleton, chapter_label):
    """Backward-compatible: flat set of key pages across all PDFs of a chapter."""
    flat = set()
    for pages in select_key_pages_by_pdf(skeleton, chapter_label).values():
        flat |= pages
    return flat


def build_chapter_slides(pdf_paths, out_dir, density='key', skeleton=None,
                         chapter_label=None, max_width=900, quality=72):
    """Build the slide rail data for one chapter.

    density: 'full' (all pages) | 'key' (only pages referenced by must/key KCs)
             | 'none' (empty).
    Returns a list of {"page": "N", "img": data_uri, "text": str}.
    """
    if density == 'none':
        return []

    key_by_pdf = {}
    if density == 'key' and skeleton is not None:
        key_by_pdf = select_key_pages_by_pdf(skeleton, chapter_label)

    slides = _render(pdf_paths, out_dir, density, key_by_pdf, max_width, quality)

    # Robustness: if 'key' density produced NO slides (e.g. skeleton source_refs
    # hallucinated page numbers beyond the PDF, or didn't map to any real page),
    # fall back to rendering every page — better a full rail than an empty one.
    if density == 'key' and not slides and any(
        os.path.exists(p) and p.lower().endswith('.pdf') for p in pdf_paths
    ):
        slides = _render(pdf_paths, out_dir, 'full', {}, max_width, quality)

    return slides


def _render(pdf_paths, out_dir, density, key_by_pdf, max_width, quality):
    """Render slides for the given density. Returns the slide list."""
    slides = []
    multi = len(pdf_paths) > 1
    for pdf_path in pdf_paths:
        if not os.path.exists(pdf_path):
            continue
        base = os.path.basename(pdf_path)

        only_pages = None
        if density == 'key':
            only_pages = set(key_by_pdf.get(base, set())) | set(key_by_pdf.get('', set()))
            if not only_pages:
                continue

        texts = extract_page_texts(pdf_path)
        rendered = render_pdf_pages(pdf_path, out_dir, only_pages=only_pages)
        pdf_tag = os.path.splitext(base)[0]
        for r in rendered:
            page = r['page']
            anchor = f"{pdf_tag}-{page}" if multi else str(page)
            uri, iw, ih = _img_to_data_uri(r['img_path'], max_width, quality)
            slides.append({
                "page": anchor,
                "pdf": base,
                "raw_page": page,
                "label": f"{pdf_tag} · 第{page}页" if multi else f"第{page}页",
                "img": uri,
                "iw": iw, "ih": ih,
                "text": texts.get(page, ''),
            })
    return slides
