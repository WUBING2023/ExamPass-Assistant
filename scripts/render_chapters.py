"""Render every chapter into a combined page (knowledge list + PPT rail + quiz).

This is the canonical Phase-4 render for the default flow: the PPT
cross-reference rail is ON by default, sourced from each chapter's
`source_files` recorded in chapter_manifest.json.

Usage: python scripts/render_chapters.py <target_dir> [full|key|none]
"""

import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slide_renderer import build_chapter_slides
from template_engine import save_combined_html


def main(target_dir, density='key'):
    target = os.path.abspath(target_dir)
    epa_work = os.path.join(target, '.epa_work')
    epa_dir = os.path.join(target, 'EPA')
    os.makedirs(epa_dir, exist_ok=True)

    with open(os.path.join(epa_work, 'chapter_manifest.json'), encoding='utf-8') as f:
        manifest = json.load(f)
    skeleton_path = os.path.join(epa_work, 'knowledge_skeleton.json')
    skeleton = None
    if os.path.exists(skeleton_path):
        with open(skeleton_path, encoding='utf-8') as f:
            skeleton = json.load(f)

    # Map skeleton chapter label -> kcs (for heading page chips)
    kcs_by_label = {}
    if skeleton:
        for ch in skeleton.get('chapters', []):
            kcs_by_label[ch.get('label', '')] = ch.get('kcs', [])

    notes_dir = os.path.join(epa_work, 'notes')
    q_dir = os.path.join(epa_work, 'questions')

    made = []
    for ch_label, info in manifest['chapters'].items():
        # notes/questions are keyed by chapter id (ch1..) or label; try both.
        note_path = _find(notes_dir, ch_label, '.html')
        q_path = _find(q_dir, ch_label, '.json')
        if not note_path or not q_path:
            print(f'[skip] {ch_label}: missing notes or questions')
            continue

        note = open(note_path, encoding='utf-8').read()
        qd = json.load(open(q_path, encoding='utf-8'))
        questions = qd.get('questions', qd if isinstance(qd, list) else [])

        # PDFs for this chapter come straight from the manifest.
        pdfs = [p for p in info.get('source_files', []) if p.lower().endswith('.pdf')]
        slides = None
        if pdfs and density != 'none':
            sd = os.path.join(info['work_dir'], '_slides')
            try:
                slides = build_chapter_slides(pdfs, sd, density=density,
                                              skeleton=skeleton, chapter_label=ch_label)
            except Exception as e:
                print(f'[warn] {ch_label}: slide render failed ({e})')

        kcs = _match_kcs(kcs_by_label, ch_label)
        out = os.path.join(epa_dir, f'{ch_label}.html')
        save_combined_html(note, questions, out, ch_label,
                           slides=slides, kcs=kcs,
                           subtitle=f'共 {len(questions)} 题')
        made.append((ch_label, len(questions), len(slides) if slides else 0))
        print(f'[ok] {ch_label}: {len(questions)} 题, {len(slides) if slides else 0} 幻灯片')

    print(f'\nRendered {len(made)} combined pages -> {epa_dir}')


def _find(d, label, ext):
    """Find a file by chapter label or by a chN id fallback."""
    if not os.path.isdir(d):
        return None
    cand = os.path.join(d, label + ext)
    if os.path.exists(cand):
        return cand
    # fallback: any file whose stem matches a number in the label
    import re
    m = re.match(r'\s*(\d+)', label)
    if m:
        cid = 'ch' + m.group(1)
        cand = os.path.join(d, cid + ext)
        if os.path.exists(cand):
            return cand
    return None


def _match_kcs(kcs_by_label, ch_label):
    for label, kcs in kcs_by_label.items():
        if label and (label in ch_label or ch_label in label):
            return kcs
    return None


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python render_chapters.py <target_dir> [full|key|none]')
        sys.exit(1)
    density = sys.argv[2] if len(sys.argv) > 2 else 'key'
    main(sys.argv[1], density)
