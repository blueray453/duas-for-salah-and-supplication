#!/usr/bin/env python3
"""check_font_coverage.py — print the Unicode codepoint ranges a font actually supports."""

import sys
from fontTools.ttLib import TTFont

def get_coverage(path):
    font = TTFont(path, fontNumber=0, lazy=True)
    cmap = font.getBestCmap()
    codepoints = sorted(cmap.keys())
    if not codepoints:
        return []

    # Collapse into contiguous ranges
    ranges = []
    start = prev = codepoints[0]
    for cp in codepoints[1:]:
        if cp == prev + 1:
            prev = cp
        else:
            ranges.append((start, prev))
            start = prev = cp
    ranges.append((start, prev))
    return ranges

def format_ranges(ranges):
    return ", ".join(f"U+{s:04X}" if s == e else f"U+{s:04X}-{e:04X}" for s, e in ranges)

if __name__ == "__main__":
    import glob

    paths = sys.argv[1:]
    if not paths:
        paths = glob.glob("fonts/*.ttf") + glob.glob("fonts/*.otf")

    if not paths:
        print("No font files found. Pass paths explicitly or place fonts in ./fonts/")
        sys.exit(1)

    for path in paths:
        print(f"\n=== {path} ===")
        try:
            ranges = get_coverage(path)
            print(format_ranges(ranges))
        except Exception as e:
            print(f"Error reading font: {e}")
