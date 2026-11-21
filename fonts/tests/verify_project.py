#!/usr/bin/env python3
"""Sanity-check files and fixtures in the project directory."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "index.html"
DATA = ROOT / "font_audit.json"

fonts = sorted([*ROOT.glob("*.ttf"), *ROOT.glob("*.otf")])
assert len(fonts) == 54, f"Expected 54 font files, found {len(fonts)}"
assert HTML.exists(), "index.html missing"
assert (ROOT / "build_report.py").exists(), "build_report.py missing"
assert (ROOT / "README.md").exists(), "README.md missing"
html = HTML.read_text(encoding="utf-8")
assert "url(\"fonts/" not in html and "url('fonts/" not in html, "Report unexpectedly points to a fonts/ subfolder"
assert "<img" not in html.lower(), "Report should use live text, not image specimens"
assert "U+06D6" in html and "U+06DB" in html and "U+06DC" in html
assert "Allah's Messenger" in html and "ﷺ" in html
report = json.loads(DATA.read_text(encoding="utf-8"))
assert report["source_font_count"] == 54
assert len(report["madani_waqf_codepoints"]) == 6
assert len(report["extended_quranic_annotation_codepoints"]) == 54
assert len(report["fonts"]) == 54
for name in ["al_fatihah.txt", "madinah_pause_examples.txt", "waqf_glyph_fixture.txt", "extended_annotation_glyph_fixture.txt"]:
    assert (ROOT / "samples" / name).exists(), f"Missing sample: {name}"
waqf_fixture = (ROOT / "samples" / "waqf_glyph_fixture.txt").read_text(encoding="utf-8")
for cp in report["madani_waqf_codepoints"]:
    assert chr(cp) in waqf_fixture, f"Pause glyph U+{cp:04X} missing from fixture"
assert chr(0x06DC) in waqf_fixture, "Saktah U+06DC missing from fixture"
ext_fixture = (ROOT / "samples" / "extended_annotation_glyph_fixture.txt").read_text(encoding="utf-8")
for cp in report["extended_quranic_annotation_codepoints"]:
    assert chr(cp) in ext_fixture, f"Extended annotation U+{cp:04X} missing from fixture"
print("Project sanity check passed: 54 fonts, selectable live text, all six Madinah pause glyphs, Saktah, and all 54 extended annotation code points.")
