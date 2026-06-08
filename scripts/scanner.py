"""Recursively scan directories and group support files by parent folder
or by chapter-number prefix when files are flat."""

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from utils import is_supported


def _parse_chapter_prefix(filename: str) -> Tuple[int, str]:
    """Extract chapter number from a filename like '3 分治-1.pdf' -> (3, '3 分治').

    Returns (0, '') when no prefix is found.
    """
    m = re.match(r'^(\d+)\s+(.+)', filename)
    if m:
        num = int(m.group(1))
        base = m.group(2)
        # Strip extension
        base = re.sub(r'\.[^.]+$', '', base)
        # Strip trailing variant suffix: -1, -2, _new, _final etc.
        base = re.sub(r'[_-]\d+$', '', base)
        base = re.sub(r'[_-]new$', '', base)
        base = re.sub(r'[_-]final$', '', base)
        base = base.strip()
        return num, f"{m.group(1)} {base}"
    return 0, ''


def scan_and_group(root_dir: str) -> Dict[str, List[str]]:
    """
    Recursively scan root_dir for supported files, group by direct parent folder.
    Files in root_dir itself are grouped under '.'.
    Returns {folder_path: [file_paths]}.
    """
    groups: Dict[str, List[str]] = defaultdict(list)

    for dirpath, _dirnames, filenames in os.walk(root_dir):
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            if is_supported(fpath):
                groups[dirpath].append(fpath)

    for key in groups:
        groups[key].sort()

    return dict(groups)


def scan_and_group_by_chapter(root_dir: str) -> Dict[str, List[str]]:
    """Like scan_and_group, but when all files live in one flat directory,
    split them by chapter-number prefix (e.g. '3 分治-1.pdf', '3 分治-2.pdf'
    → same chapter). Subdirectories are still grouped by folder.

    Returns {chapter_key: [file_paths]} where chapter_key is like
    '3 分治' for prefixed files or the folder basename for subdirectories.
    """
    raw = scan_and_group(root_dir)
    if not raw:
        return {}

    # Only split flat-directory groups — leave subdirectory groups alone.
    out: Dict[str, List[str]] = {}
    for folder, files in raw.items():
        if folder == root_dir:
            # Flat directory: try to split by chapter prefix.
            by_ch: Dict[str, List[str]] = defaultdict(list)
            unmatched: List[str] = []
            for fp in files:
                fname = os.path.basename(fp)
                num, label = _parse_chapter_prefix(fname)
                if num > 0:
                    by_ch[label].append(fp)
                else:
                    unmatched.append(fp)
            for label, fpaths in sorted(by_ch.items()):
                fpaths.sort()
                out[label] = fpaths
            if unmatched:
                out[os.path.basename(root_dir) or "课程资料"] = unmatched
        else:
            out[os.path.basename(folder)] = files

    return out


def get_group_name(folder_path: str, root_dir: str) -> str:
    """Return a human-readable name for a folder group."""
    if folder_path == root_dir:
        return os.path.basename(root_dir) or "课程资料"
    return os.path.basename(folder_path)
