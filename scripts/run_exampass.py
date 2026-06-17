"""
Single entry-point for /exampass skill.
Usage: python scripts/run_exampass.py <target_directory>

Handles the full pipeline:
  1. Scan & group files (by subdirectory or by chapter-number prefix)
  2. Extract content (text + images)
  3. Save per-chapter extraction bundles for Claude analysis
  4. Print instructions for the next step

Output: <target>/EPA/  (.epa_work/ per chapter + final HTML files)
"""

import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scanner import scan_and_group, scan_and_group_by_chapter, get_group_name
from extractor import extract_file, merge_group_content
from image_extractor import extract_from_pptx
from ocr_backend import ocr_images, is_multimodal_hint


def _extract_one_group(target_dir, work_dir, group_label, files):
    """Extract a single group of files into one _extraction_bundle.json.

    Returns (bundle_path, image_count, merged_text_length).
    """
    os.makedirs(work_dir, exist_ok=True)
    img_dir = os.path.join(work_dir, '_images')
    os.makedirs(img_dir, exist_ok=True)

    results = []
    all_images = []

    for fpath in files:
        fname = os.path.basename(fpath)
        ext = os.path.splitext(fpath)[1].lower()
        print("  Extracting:", fname, "(" + ext + ")")
        result = extract_file(fpath, image_output_dir=img_dir)
        results.append(result)
        all_images.extend(result.get('images', []))

        txt_path = os.path.join(work_dir, fname + '_extracted.txt')
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(result['text_summary'])
        print("    Text:", len(result['text_summary']), "chars ->", txt_path)

    merged = merge_group_content(results)

    ocr_text = ''
    if all_images and not is_multimodal_hint():
        print("  Model is text-only; running OCR on", len(all_images), "image(s)...")
        ocr_text = ocr_images(all_images)
        if ocr_text:
            merged += "\n\n## 图片 OCR 文本\n" + ocr_text
            print("    OCR text:", len(ocr_text), "chars merged into bundle")

    bundle = {
        'group_name': group_label,
        'folder': work_dir,
        'merged_text': merged,
        'file_count': len(files),
        'image_count': len(all_images),
        'images': all_images,
        'ocr_used': bool(ocr_text),
        'individual_results': [
            {'filename': os.path.basename(f), 'text_length': len(r['text_summary'])}
            for f, r in zip(files, results)
        ],
    }
    bundle_path = os.path.join(work_dir, '_extraction_bundle.json')
    with open(bundle_path, 'w', encoding='utf-8') as f:
        json.dump(bundle, f, ensure_ascii=False)
    print("  Bundle saved:", bundle_path)
    print("  Total merged:", len(merged), "chars")
    return bundle_path, len(all_images), len(merged)


def main(target_dir):
    target = os.path.abspath(target_dir)
    if not os.path.isdir(target):
        print("ERROR: Directory not found:", target)
        sys.exit(1)

    # Use chapter-prefix grouping so flat directories get per-chapter bundles.
    groups = scan_and_group_by_chapter(target)
    if not groups:
        print("No supported files (PPTX/DOCX/PDF) found in", target)
        sys.exit(0)

    print("Found", len(groups), "chapter(s)\n")

    epa_dir = os.path.join(target, 'EPA')
    epa_work_dir = os.path.join(target, '.epa_work')
    chapters_work_dir = os.path.join(epa_work_dir, 'chapters')
    os.makedirs(epa_dir, exist_ok=True)
    os.makedirs(chapters_work_dir, exist_ok=True)

    # Also keep a legacy bundle at the top level for backward compat with
    # flows that don't yet know about per-chapter extraction.
    all_bundles = {}

    for group_label, files in groups.items():
        safe_label = group_label.replace('/', '_').replace('\\', '_').strip()
        print("=" * 56)
        print("Chapter:", group_label)
        print("Files: ", len(files))
        print("=" * 56)

        ch_work = os.path.join(chapters_work_dir, safe_label)
        bundle_path, img_count, text_len = _extract_one_group(target, ch_work, group_label, files)
        all_bundles[group_label] = {
            'bundle_path': bundle_path,
            'work_dir': ch_work,
            'file_count': len(files),
            'image_count': img_count,
            'text_length': text_len,
            # Absolute paths to this chapter's source files (PDFs etc.), so the
            # render step can build the PPT cross-reference rail without
            # re-deriving the grouping. PDFs first (the rail renders PDF pages).
            'source_files': sorted(
                (os.path.abspath(f) for f in files),
                key=lambda p: (os.path.splitext(p)[1].lower() != '.pdf', p),
            ),
        }
        print()

    # Write a manifest so downstream agents know what chapters exist.
    manifest = {
        'target_dir': target,
        'epa_dir': epa_dir,
        'chapters': all_bundles,
    }
    manifest_path = os.path.join(epa_work_dir, 'chapter_manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("Manifest:", manifest_path)
    print("Done. Extraction complete for", len(groups), "chapter(s).")
    print()
    print("Next: Claude reads each _extraction_bundle.json, produces")
    print("  knowledge list + test per chapter, and saves them to:")
    print(" ", epa_dir)
    print("  <chapter_label>-知识清单.html")
    print("  <chapter_label>-章节测试.html")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python run_exampass.py <target_directory>")
        sys.exit(1)
    main(sys.argv[1])
