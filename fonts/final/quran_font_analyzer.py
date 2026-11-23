#!/usr/bin/env python3
"""Qur'anic and Arabic font/text analyzer.

Inspects TTF/OTF/WOFF2 font metadata, Unicode cmap coverage, OpenType features,
produces CSS unicode-range rules, and analyzes a supplied Arabic text for
Perso-Arabic character usage and evidence relevant to Qur'anic orthography.

Important: Uthmani, Imla'i and IndoPak are text/edition conventions, not font
properties. A Unicode-only heuristic cannot reliably certify them. For a
strong classification, provide a matching reference text in reference_texts/
(or use --reference-dir) with a filename beginning uthmani, imlaei/imlai, or
indopak. You may also pass --declared-layout when the source is already known.

Dependencies: Python 3.10+, fontTools, brotli (for WOFF2 support).
Install: python -m pip install -r requirements.txt

Examples:
  python quran_font_analyzer.py
  python quran_font_analyzer.py --text-only --text "اللَّهُمَّ اغْفِرْ لَنَا"
  python quran_font_analyzer.py "اللَّهُمَّ اغْفِرْ لَنَا" --text-only
  cat passage.txt | python quran_font_analyzer.py --stdin --text-only
  python quran_font_analyzer.py --text-file samples/al_fatihah_uthmani.txt --text-kind quran
  python quran_font_analyzer.py --text-file my_text.txt --text-kind hadith
  python quran_font_analyzer.py --text-file verse.txt --reference-dir reference_texts
  python quran_font_analyzer.py --text-file verse.txt --declared-layout uthmani
  python quran_font_analyzer.py --font-dir /path/to/fonts --output-dir /path/to/report
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import html
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    from fontTools.ttLib import TTFont
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: fontTools. Run: python -m pip install -r requirements.txt") from exc

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_FONT_DIR = SCRIPT_DIR
DEFAULT_TEXT = SCRIPT_DIR / "samples" / "hadith_quranohadith_original.txt"
DEFAULT_REFERENCE_DIR = SCRIPT_DIR / "reference_texts"
FONT_EXTENSIONS = {".ttf", ".otf", ".woff", ".woff2"}

NAME_IDS = {
    0: "copyright", 1: "family", 2: "subfamily", 3: "unique_id",
    4: "full_name", 5: "version", 6: "postscript_name", 7: "trademark",
    8: "manufacturer", 9: "designer", 10: "description", 11: "vendor_url",
    12: "designer_url", 13: "license_description", 14: "license_url",
    16: "typographic_family", 17: "typographic_subfamily", 18: "compatible_full_name",
    19: "sample_text", 21: "wws_family", 22: "wws_subfamily",
}

PERSO_ARABIC = {
    0x067E: ("پ", "Peheh", "Persian/Urdu-associated letter"),
    0x0679: ("ٹ", "Tteh", "Urdu-associated letter"),
    0x0686: ("چ", "Tcheh", "Persian/Urdu-associated letter"),
    0x0688: ("ڈ", "Ddal", "Urdu-associated letter"),
    0x0691: ("ڑ", "Rreh", "Urdu-associated letter"),
    0x0698: ("ژ", "Jeh", "Persian/Urdu-associated letter"),
    0x06A4: ("ڤ", "Veh", "Persian/Urdu and other language letter"),
    0x06A9: ("ک", "Keheh", "Persian/Urdu-associated form; compare Arabic ك U+0643"),
    0x06AF: ("گ", "Gaf", "Persian/Urdu-associated letter"),
    0x06BA: ("ں", "Noon Ghunna", "Urdu-associated letter"),
    0x06BE: ("ھ", "Heh Doachashmee", "Urdu-associated letter"),
    0x06C0: ("ۀ", "Heh with Yeh Above", "Persian/Urdu-associated letter"),
    0x06C1: ("ہ", "Heh Goal", "Urdu-associated form; compare Arabic ه U+0647"),
    0x06C2: ("ۂ", "Heh Goal with Hamza Above", "Urdu-associated letter"),
    0x06C3: ("ۃ", "Teh Marbuta Goal", "Urdu-associated form; compare Arabic ة U+0629"),
    0x06CC: ("ی", "Farsi Yeh", "Persian/Urdu-associated yeh; compare Arabic ي U+064A"),
    0x06D2: ("ے", "Yeh Barree", "Urdu-associated letter"),
    0x06D3: ("ۓ", "Yeh Barree with Hamza Above", "Urdu-associated letter"),
    0x06D4: ("۔", "Arabic Full Stop", "Punctuation common in Urdu/Persian-oriented writing; not a letter"),
}
PERSIAN_DISTINCTIVE = {0x067E, 0x0686, 0x0698, 0x06AF, 0x06CC, 0x06A9}
URDU_DISTINCTIVE = {0x0679, 0x0688, 0x0691, 0x06BA, 0x06BE, 0x06C1, 0x06C2, 0x06C3, 0x06D2, 0x06D3}
PERSIAN_DIGITS = set(range(0x06F0, 0x06FA))
ARABIC_INDIC_DIGITS = set(range(0x0660, 0x066A))

# Signals associated with Qur'anic/orthographic annotation. These are clues,
# not a proof that a text is an Uthmani edition.
QURANIC_MARKS = set(range(0x06D6, 0x06F0)) | set(range(0x08D3, 0x08E3)) | set(range(0x08F0, 0x08F4))
UTHMANI_ASSOCIATED = {
    0x0671,  # ALEF WASLA
    0x0670,  # SUPERSCRIPT ALEF
    0x06E5, 0x06E6, 0x06E7, 0x06E8,
    0x06EA, 0x06ED,
}
WAQF_MARKS = set(range(0x06D6, 0x06DD))

SCRIPT_RANGES = [
    (0x0000, 0x024F, "Latin"),
    (0x0600, 0x06FF, "Arabic"),
    (0x0700, 0x074F, "Syriac"),
    (0x0750, 0x077F, "Arabic Supplement"),
    (0x0780, 0x07BF, "Thaana"),
    (0x0870, 0x089F, "Arabic Extended-B"),
    (0x08A0, 0x08FF, "Arabic Extended-A"),
    (0x0980, 0x09FF, "Bengali"),
    (0xFB50, 0xFDFF, "Arabic Presentation Forms-A"),
    (0xFE70, 0xFEFF, "Arabic Presentation Forms-B"),
    (0xE000, 0xF8FF, "Private Use Area"),
    (0xF0000, 0xFFFFD, "Supplementary Private Use Area-A"),
]

LAYOUT_LABELS = {
    "uthmani": "Uthmani",
    "imlaei": "Imla'i / Simple",
    "indopak": "IndoPak",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def unicode_name(cp: int) -> str:
    return unicodedata.name(chr(cp), "UNASSIGNED / NO UNICODE NAME")


def cp_label(cp: int) -> str:
    return f"U+{cp:04X}"


def get_name_records(font: TTFont) -> dict[str, list[str]]:
    found: dict[str, list[str]] = defaultdict(list)
    if "name" not in font:
        return {}
    for record in font["name"].names:
        key = NAME_IDS.get(record.nameID)
        if not key:
            continue
        try:
            value = record.toUnicode().strip()
        except Exception:
            continue
        if value and value not in found[key]:
            found[key].append(value)
    return dict(found)


def best_name(names: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        values = names.get(key, [])
        if values:
            return values[0]
    return ""


def get_unicode_cmap(font: TTFont) -> dict[int, str]:
    result: dict[int, str] = {}
    if "cmap" not in font:
        return result
    # Prefer Unicode subtables, later full-repertoire subtables overwrite earlier ones.
    tables = [t for t in font["cmap"].tables if t.isUnicode()]
    tables.sort(key=lambda t: (t.platformID == 0, t.format in (12, 13)))
    for table in tables:
        result.update(table.cmap)
    return result


def compress_ranges(codepoints: list[int] | set[int]) -> list[tuple[int, int]]:
    values = sorted(set(codepoints))
    if not values:
        return []
    ranges: list[tuple[int, int]] = []
    start = prev = values[0]
    for cp in values[1:]:
        if cp == prev + 1:
            prev = cp
        else:
            ranges.append((start, prev))
            start = prev = cp
    ranges.append((start, prev))
    return ranges


def css_ranges(codepoints: list[int] | set[int]) -> str:
    bits = []
    for start, end in compress_ranges(codepoints):
        bits.append(f"U+{start:04X}" if start == end else f"U+{start:04X}-{end:04X}")
    return ", ".join(bits)


def get_feature_tags(font: TTFont, table_tag: str) -> list[str]:
    if table_tag not in font:
        return []
    try:
        records = font[table_tag].table.FeatureList.FeatureRecord
        return sorted({record.FeatureTag for record in records})
    except Exception:
        return []


def decode_fstype(value: int) -> list[str]:
    labels = []
    if value == 0:
        labels.append("Installable embedding (fsType=0)")
    if value & 0x0002:
        labels.append("Restricted License embedding")
    if value & 0x0004:
        labels.append("Preview & Print embedding")
    if value & 0x0008:
        labels.append("Editable embedding")
    if value & 0x0100:
        labels.append("No subsetting")
    if value & 0x0200:
        labels.append("Bitmap embedding only")
    if not labels:
        labels.append("Unclassified / reserved fsType bits")
    return labels


def script_distribution(codepoints: set[int]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for cp in codepoints:
        for start, end, label in SCRIPT_RANGES:
            if start <= cp <= end:
                counts[label] += 1
                break
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def guess_font_role(filename: str, family: str, subfamily: str, names: dict[str, list[str]]) -> list[str]:
    haystack = " ".join([filename, family, subfamily, *names.get("description", [])]).lower()
    roles: list[str] = []
    keywords = [
        ("qur'anic / mushaf", ["quran", "qur'an", "uthmani", "hafs", "mushaf", "qcf"]),
        ("IndoPak-associated", ["indopak", "indo-pak"]),
        ("Nastaliq", ["nastaliq"]),
        ("Naskh", ["naskh"]),
        ("Kufi", ["kufi"]),
        ("Bengali", ["bengali"]),
        ("Arabic prose / general Arabic", ["arabic", "scheherazade", "amiri", "kacst", "katibeh"]),
    ]
    for label, terms in keywords:
        if any(term in haystack for term in terms):
            roles.append(label)
    if not roles:
        roles.append("Not identified from metadata/name")
    return roles


def inspect_font(path: Path, text_codepoints: set[int]) -> dict[str, Any]:
    font = None
    try:
        font = TTFont(str(path), lazy=False, recalcBBoxes=False, recalcTimestamp=False)
        names = get_name_records(font)
        cmap = get_unicode_cmap(font)
        cmap_cps = set(cmap)
        missing = sorted(text_codepoints - cmap_cps)
        covered = sorted(text_codepoints & cmap_cps)
        os2 = font["OS/2"] if "OS/2" in font else None
        head = font["head"] if "head" in font else None
        hhea = font["hhea"] if "hhea" in font else None
        post = font["post"] if "post" in font else None
        maxp = font["maxp"] if "maxp" in font else None
        fstype = int(getattr(os2, "fsType", 0)) if os2 else None
        axes = []
        if "fvar" in font:
            for axis in font["fvar"].axes:
                axes.append({
                    "tag": axis.axisTag,
                    "name_id": axis.axisNameID,
                    "min": axis.minValue,
                    "default": axis.defaultValue,
                    "max": axis.maxValue,
                })
        table_tags = sorted(font.keys())
        color_tables = [tag for tag in ("COLR", "CPAL", "CBDT", "CBLC", "sbix", "SVG ") if tag in font]
        cmap_formats = sorted({int(t.format) for t in font["cmap"].tables if t.isUnicode()}) if "cmap" in font else []
        cmap_subtables = [
            {"platform_id": int(t.platformID), "encoding_id": int(t.platEncID), "format": int(t.format), "language": int(getattr(t, "language", 0)), "unicode": bool(t.isUnicode()), "mapping_count": len(getattr(t, "cmap", {}))}
            for t in font["cmap"].tables
        ] if "cmap" in font else []
        # Block distribution counts each mapped code point once.
        return {
            "filename": path.name,
            "extension": path.suffix.lower(),
            "file_size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "family": best_name(names, "typographic_family", "family") or path.stem,
            "subfamily": best_name(names, "typographic_subfamily", "subfamily"),
            "full_name": best_name(names, "full_name"),
            "postscript_name": best_name(names, "postscript_name"),
            "version": best_name(names, "version"),
            "names": names,
            "glyph_count": int(maxp.numGlyphs) if maxp else None,
            "unicode_cmap_count": len(cmap_cps),
            "unicode_cmap_formats": cmap_formats,
            "cmap_subtables": cmap_subtables,
            "sfnt_version": str(getattr(font, "sfntVersion", "")),
            "woff_flavor": str(getattr(font, "flavor", "sfnt") or "sfnt"),
            "script_coverage": script_distribution(cmap_cps),
            "arabic_codepoint_count": sum(1 for cp in cmap_cps if 0x0600 <= cp <= 0x08FF or 0xFB50 <= cp <= 0xFEFF),
            "perso_arabic_codepoint_count": sum(1 for cp in cmap_cps if cp in PERSO_ARABIC or cp in PERSIAN_DIGITS),
            "private_use_codepoint_count": sum(1 for cp in cmap_cps if 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0xFFFFD),
            "text_coverage": {
                "total": len(text_codepoints),
                "mapped": len(covered),
                "missing": len(missing),
                "percent": round((len(covered) / len(text_codepoints) * 100), 1) if text_codepoints else 100.0,
                "missing_codepoints": [cp_label(cp) for cp in missing],
            },
            "open_type": {
                "GSUB": get_feature_tags(font, "GSUB"),
                "GPOS": get_feature_tags(font, "GPOS"),
                "GDEF": "GDEF" in font,
                "kern_table": "kern" in font,
                "color_tables": color_tables,
                "variable_axes": axes,
                "all_tables": table_tags,
            },
            "metrics": {
                "units_per_em": int(head.unitsPerEm) if head else None,
                "font_revision": float(head.fontRevision) if head else None,
                "bbox": {
                    "xMin": int(head.xMin), "yMin": int(head.yMin),
                    "xMax": int(head.xMax), "yMax": int(head.yMax),
                } if head else None,
                "weight_class": int(os2.usWeightClass) if os2 else None,
                "weight_label": weight_label(int(os2.usWeightClass)) if os2 else None,
                "width_class": int(os2.usWidthClass) if os2 else None,
                "width_label": width_label(int(os2.usWidthClass)) if os2 else None,
                "vendor_id": str(os2.achVendID).strip() if os2 else None,
                "fs_selection": int(os2.fsSelection) if os2 else None,
                "first_char_index": int(os2.usFirstCharIndex) if os2 else None,
                "last_char_index": int(os2.usLastCharIndex) if os2 else None,
                "cap_height": int(os2.sCapHeight) if os2 and hasattr(os2, "sCapHeight") else None,
                "x_height": int(os2.sxHeight) if os2 and hasattr(os2, "sxHeight") else None,
                "max_context": int(os2.usMaxContext) if os2 and hasattr(os2, "usMaxContext") else None,
                "unicode_range_bits": [int(getattr(os2, f"ulUnicodeRange{i}", 0)) for i in range(1, 5)] if os2 else [],
                "codepage_range_bits": [int(getattr(os2, f"ulCodePageRange{i}", 0)) for i in range(1, 3)] if os2 else [],
                "panose": list(os2.panose.__dict__.values()) if os2 and hasattr(os2, "panose") else None,
                "fs_type": fstype,
                "embedding_permissions": decode_fstype(fstype) if fstype is not None else [],
                "typo_ascender": int(os2.sTypoAscender) if os2 else None,
                "typo_descender": int(os2.sTypoDescender) if os2 else None,
                "typo_line_gap": int(os2.sTypoLineGap) if os2 else None,
                "win_ascent": int(os2.usWinAscent) if os2 else None,
                "win_descent": int(os2.usWinDescent) if os2 else None,
                "hhea_ascender": int(hhea.ascent) if hhea else None,
                "hhea_descender": int(hhea.descent) if hhea else None,
                "hhea_line_gap": int(hhea.lineGap) if hhea else None,
                "italic_angle": float(post.italicAngle) if post else None,
                "underline_position": int(post.underlinePosition) if post else None,
                "underline_thickness": int(post.underlineThickness) if post else None,
                "number_of_h_metrics": int(hhea.numberOfHMetrics) if hhea else None,
                "head_created": head.created.toISO8601() if head and hasattr(head.created, "toISO8601") else None,
                "head_modified": head.modified.toISO8601() if head and hasattr(head.modified, "toISO8601") else None,
                "mac_style": int(head.macStyle) if head else None,
                "font_flags": int(head.flags) if head else None,
                "outline_tables": [tag for tag in ("glyf", "CFF ", "CFF2") if tag in font],
            },
            "possible_roles_from_names": guess_font_role(path.name, best_name(names, "typographic_family", "family"), best_name(names, "typographic_subfamily", "subfamily"), names),
            "cmap_codepoints": sorted(cmap_cps),
            "cmap": {str(cp): cmap[cp] for cp in sorted(cmap_cps)},
            "error": None,
        }
    except Exception as exc:
        return {
            "filename": path.name,
            "file_size_bytes": path.stat().st_size if path.exists() else None,
            "sha256": sha256_file(path) if path.exists() else None,
            "error": f"{type(exc).__name__}: {exc}",
            "text_coverage": {"total": len(text_codepoints), "mapped": 0, "missing": len(text_codepoints), "percent": 0.0, "missing_codepoints": [cp_label(cp) for cp in sorted(text_codepoints)]},
        }
    finally:
        if font is not None:
            try:
                font.close()
            except Exception:
                pass


def weight_label(weight: int) -> str:
    labels = {100:"Thin", 200:"Extra-light", 300:"Light", 400:"Regular", 500:"Medium", 600:"Semi-bold", 700:"Bold", 800:"Extra-bold", 900:"Black"}
    return labels.get(weight, "Custom / intermediate")


def width_label(width: int) -> str:
    labels = {1:"Ultra-condensed", 2:"Extra-condensed", 3:"Condensed", 4:"Semi-condensed", 5:"Medium", 6:"Semi-expanded", 7:"Expanded", 8:"Extra-expanded", 9:"Ultra-expanded"}
    return labels.get(width, "Unknown")


def is_arabic_letter_or_mark(ch: str) -> bool:
    cp = ord(ch)
    return (0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or
            0x0870 <= cp <= 0x089F or 0x08A0 <= cp <= 0x08FF or
            0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF)


def describe_character(ch: str) -> dict[str, Any]:
    cp = ord(ch)
    perso = PERSO_ARABIC.get(cp)
    if perso:
        group = "Perso-Arabic / Urdu-associated"
        note = perso[2]
    elif cp in PERSIAN_DIGITS:
        group = "Extended Arabic-Indic (Persian-style) digit"
        note = "Often used in Persian/Urdu contexts; not a language detector by itself."
    elif cp in ARABIC_INDIC_DIGITS:
        group = "Arabic-Indic digit"
        note = "Common in Arabic-script contexts; not a layout detector by itself."
    elif cp in UTHMANI_ASSOCIATED:
        group = "Qur'anic / Uthmani-associated sign or letter"
        note = "A clue only; the full text must be checked against a reference edition."
    elif cp in WAQF_MARKS:
        group = "Qur'anic pause/waqf mark"
        note = "Waqf notation is not by itself proof of a specific rasm or recitation."
    elif 0x064B <= cp <= 0x065F or cp in (0x0670, 0x06D6, 0x06D7, 0x06D8, 0x06D9, 0x06DA, 0x06DB, 0x06DC):
        group = "Arabic diacritic / Qur'anic mark"
        note = "Diacritics occur in several Arabic text traditions; not enough to classify script."
    elif 0x0600 <= cp <= 0x08FF or 0xFB50 <= cp <= 0xFEFF:
        group = "Arabic-script character"
        note = "The Unicode block alone does not identify the language or orthographic edition."
    else:
        group = "Other / punctuation / whitespace"
        note = ""
    return {
        "character": ch,
        "codepoint": cp_label(cp),
        "unicode_name": unicodedata.name(ch, "UNKNOWN"),
        "category": unicodedata.category(ch),
        "group": group,
        "note": note,
        "count": 0,
    }


def compact_for_match(text: str) -> str:
    # Normalise Unicode canonically, remove tatweel and whitespace. Preserve
    # diacritics for a stricter, layout-sensitive comparison.
    value = unicodedata.normalize("NFC", text).replace("\u0640", "")
    return "".join(ch for ch in value if not ch.isspace())


def load_references(reference_dir: Path | None) -> list[dict[str, Any]]:
    if not reference_dir or not reference_dir.exists():
        return []
    records = []
    for path in sorted(reference_dir.glob("*.txt")):
        low = path.stem.lower()
        if low.startswith("uthmani"):
            layout = "uthmani"
        elif low.startswith("imlaei") or low.startswith("imlai") or low.startswith("simple"):
            layout = "imlaei"
        elif low.startswith("indopak") or low.startswith("indo_pak"):
            layout = "indopak"
        else:
            continue
        raw = path.read_text(encoding="utf-8-sig")
        cleaned = compact_for_match(raw)
        if cleaned:
            records.append({"filename": path.name, "layout": layout, "text": raw, "compact": cleaned})
    return records


def layout_classification(text: str, args: argparse.Namespace) -> dict[str, Any]:
    cp_set = {ord(ch) for ch in text if not ch.isspace()}
    genre = args.text_kind
    if genre == "auto":
        lower_name = (args.label or "").lower()
        lower_text = text.lower()
        if "hadith" in lower_name or "bayhaqi" in lower_name or "hadith" in lower_text[:200]:
            genre = "hadith"
        elif cp_set & (QURANIC_MARKS | UTHMANI_ASSOCIATED):
            genre = "quran-candidate"
        else:
            genre = "unknown-arabic-or-mixed-text"

    persian_urdu_cps = sorted(cp_set & (set(PERSO_ARABIC) | PERSIAN_DIGITS))
    quranic_mark_cps = sorted(cp_set & QURANIC_MARKS)
    uthmani_cps = sorted(cp_set & UTHMANI_ASSOCIATED)
    waqf_cps = sorted(cp_set & WAQF_MARKS)
    reference_records = load_references(Path(args.reference_dir).resolve() if args.reference_dir else None)
    user_compact = compact_for_match(text)
    matches = []
    for ref in reference_records:
        ratio = difflib.SequenceMatcher(a=user_compact, b=ref["compact"]).ratio()
        # Best-effort textual identity check. A partial text against a whole
        # chapter can score low, so references should be the corresponding passage.
        matches.append({"filename": ref["filename"], "layout": ref["layout"], "similarity": round(ratio, 4)})
    matches.sort(key=lambda row: row["similarity"], reverse=True)
    strong_matches = [m for m in matches if m["similarity"] >= 0.985]
    moderate_matches = [m for m in matches if m["similarity"] >= 0.90]

    declared = args.declared_layout
    if declared:
        label = LAYOUT_LABELS[declared]
        status = "Source-declared classification"
        explanation = "This label was supplied explicitly with --declared-layout; it was not inferred from character frequencies."
    elif strong_matches:
        label = LAYOUT_LABELS[strong_matches[0]["layout"]]
        status = "Strong reference-text match"
        explanation = "The normalized input closely matches the corresponding reference file. Confirm that both files cover the same passage and edition."
    elif genre == "hadith":
        label = "Not applicable as a Qur'anic edition label"
        status = "Arabic prose / hadith sample"
        explanation = "Uthmani, Imla'i and IndoPak are labels used for Qur'anic text/edition representations. This sample is hadith prose; report its character encoding separately."
    else:
        label = "Inconclusive without a matching Qur'anic reference"
        status = "Heuristic evidence only"
        explanation = "Unicode markers can indicate Arabic-script variants or Qur'anic annotation, but cannot reliably distinguish Uthmani, Imla'i and IndoPak on their own. Supply the same passage from a known edition under reference_texts/."

    evidence = []
    if persian_urdu_cps:
        evidence.append({
            "title": "Perso-Arabic / Urdu-associated code points detected",
            "detail": ", ".join(f"{chr(cp)} {cp_label(cp)} {unicode_name(cp)}" for cp in persian_urdu_cps),
            "meaning": "Evidence of extended Perso-Arabic character encoding. This does not prove the language is Urdu/Persian or that the text is an IndoPak Qur'an edition."
        })
    else:
        evidence.append({"title":"No configured Perso-Arabic marker characters detected", "detail":"None of the configured distinctive code points occurred.", "meaning":"This does not prove that the spelling is standard Arabic or Imla'i."})
    if uthmani_cps:
        evidence.append({"title":"Uthmani/Qur'anic-associated signs detected", "detail":", ".join(f"{chr(cp)} {cp_label(cp)} {unicode_name(cp)}" for cp in uthmani_cps), "meaning":"Compatible with some Qur'anic orthographic encodings; not enough to certify Uthmani text."})
    if quranic_mark_cps:
        evidence.append({"title":"Qur'anic annotation code points detected", "detail":", ".join(f"{chr(cp)} {cp_label(cp)} {unicode_name(cp)}" for cp in quranic_mark_cps), "meaning":"These marks are used in Qur'anic text conventions. The subset varies by edition and font."})
    if waqf_cps:
        evidence.append({"title":"Waqf/pause marks detected", "detail":", ".join(f"{chr(cp)} {cp_label(cp)} {unicode_name(cp)}" for cp in waqf_cps), "meaning":"Presence of pause marks does not independently identify the rasm or the printed page layout."})
    if not uthmani_cps and not quranic_mark_cps:
        evidence.append({"title":"No strong Uthmani/Qur'anic annotation marker detected", "detail":"No configured Uthmani-associated signs or Qur'anic annotation characters were found.", "meaning":"Absence is not proof of Imla'i; a plain text may have marks stripped or be only a fragment."})
    if moderate_matches and not strong_matches and not declared:
        evidence.append({"title":"Possible reference similarity", "detail":", ".join(f"{m['layout']} ({m['similarity']:.1%}) via {m['filename']}" for m in moderate_matches[:3]), "meaning":"Similarity below the strong-match threshold is exploratory evidence only."})

    return {
        "genre_assessment": genre,
        "classification": label,
        "status": status,
        "explanation": explanation,
        "declared_layout": declared,
        "signals": {
            "perso_arabic_codepoints": [cp_label(cp) for cp in persian_urdu_cps],
            "uthmani_associated_codepoints": [cp_label(cp) for cp in uthmani_cps],
            "quranic_annotation_codepoints": [cp_label(cp) for cp in quranic_mark_cps],
            "waqf_codepoints": [cp_label(cp) for cp in waqf_cps],
        },
        "evidence": evidence,
        "reference_comparisons": matches,
        "reference_match_threshold": 0.985,
        "classifier_limitations": [
            "A font's name or glyph coverage cannot identify the orthography of a text rendered with it.",
            "Perso-Arabic characters indicate codepoint usage, not necessarily Urdu or Persian language.",
            "Imla'i cannot be established merely because Uthmani-specific characters are absent.",
            "IndoPak needs source/edition matching or an authoritative reference; it is not synonymous with Urdu characters or Nastaliq font style.",
            "A fixed Mushaf page layout (15-line/16-line/page number/line breaks) requires page and word positioning data, not a plain text string.",
        ],
    }


def analyze_text(text: str, args: argparse.Namespace) -> dict[str, Any]:
    visible = [ch for ch in text if not ch.isspace()]
    counts = Counter(visible)
    inventory = []
    for ch, count in sorted(counts.items(), key=lambda item: ord(item[0])):
        row = describe_character(ch)
        row["count"] = count
        inventory.append(row)
    cp_set = {ord(ch) for ch in counts}
    persian_cps = sorted(cp_set & PERSIAN_DISTINCTIVE)
    urdu_cps = sorted(cp_set & URDU_DISTINCTIVE)
    full_perso = sorted(cp_set & (set(PERSO_ARABIC) | PERSIAN_DIGITS))
    script_counts = Counter()
    for ch in visible:
        cp = ord(ch)
        if is_arabic_letter_or_mark(ch):
            script_counts["Arabic-script"] += 1
        elif 0x0980 <= cp <= 0x09FF:
            script_counts["Bengali"] += 1
        elif 0x0000 <= cp <= 0x024F:
            script_counts["Latin"] += 1
        else:
            script_counts["Other"] += 1
    normalization = {
        "NFC_changes_text": unicodedata.normalize("NFC", text) != text,
        "NFKC_changes_text": unicodedata.normalize("NFKC", text) != text,
        "contains_tatweel": "\u0640" in text,
        "tatweel_count": text.count("\u0640"),
        "combining_mark_count": sum(1 for ch in visible if unicodedata.category(ch).startswith("M")),
        "contains_zwnj": "\u200c" in text,
        "zwnj_count": text.count("\u200c"),
        "contains_zwj": "\u200d" in text,
        "zwj_count": text.count("\u200d"),
    }
    # Report character-level signals precisely. These are encoding observations,
    # not proof of the text's language, origin, or Qur'anic edition.
    perso_details = []
    for cp in full_perso:
        ch = chr(cp)
        description = PERSO_ARABIC.get(cp)
        perso_details.append({
            "character": ch,
            "codepoint": cp_label(cp),
            "unicode_name": unicode_name(cp),
            "count": counts[ch],
            "group": description[2] if description else "Persian-style digit",
        })
    digit_counts = {
        "arabic_indic_digits": sum(counts.get(chr(cp), 0) for cp in ARABIC_INDIC_DIGITS),
        "extended_arabic_indic_persian_style_digits": sum(counts.get(chr(cp), 0) for cp in PERSIAN_DIGITS),
    }
    presentation_forms = sorted(cp for cp in cp_set if 0xFB50 <= cp <= 0xFDFF or 0xFE70 <= cp <= 0xFEFF)
    private_use = sorted(cp for cp in cp_set if 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0xFFFFD)
    encoding_observations = {
        "has_perso_arabic_associated_characters": bool(full_perso),
        "perso_arabic_character_instances": sum(counts[chr(cp)] for cp in full_perso),
        "perso_arabic_codepoints": perso_details,
        "persian_style_codepoints": [cp_label(cp) for cp in persian_cps],
        "urdu_associated_codepoints": [cp_label(cp) for cp in urdu_cps],
        "arabic_vs_perso_character_pairs": {
            "kaf": {"Arabic_Kaf_U+0643_count": counts.get("\u0643", 0), "Persian_Keheh_U+06A9_count": counts.get("\u06A9", 0)},
            "yeh": {"Arabic_Yeh_U+064A_count": counts.get("\u064A", 0), "Farsi_Yeh_U+06CC_count": counts.get("\u06CC", 0)},
            "heh": {"Arabic_Heh_U+0647_count": counts.get("\u0647", 0), "Urdu_Heh_Goal_U+06C1_count": counts.get("\u06C1", 0)},
            "teh_marbuta": {"Arabic_Teh_Marbuta_U+0629_count": counts.get("\u0629", 0), "Urdu_Teh_Marbuta_Goal_U+06C3_count": counts.get("\u06C3", 0)},
        },
        "digit_counts": digit_counts,
        "arabic_punctuation": [
            {"character": chr(cp), "codepoint": cp_label(cp), "unicode_name": unicode_name(cp), "count": counts.get(chr(cp), 0)}
            for cp in sorted(cp_set & {0x060C, 0x061B, 0x061F, 0x06D4})
        ],
        "presentation_form_codepoints": [cp_label(cp) for cp in presentation_forms],
        "private_use_codepoints": [cp_label(cp) for cp in private_use],
        "format_controls": [
            {"character": chr(cp), "codepoint": cp_label(cp), "unicode_name": unicode_name(cp), "count": counts.get(chr(cp), 0)}
            for cp in sorted(cp_set & {0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069})
        ],
        "arabic_combining_mark_count": normalization["combining_mark_count"],
    }
    return {
        "label": args.label,
        "text_kind_requested": args.text_kind,
        "character_count_including_whitespace": len(text),
        "non_whitespace_character_count": len(visible),
        "unique_non_whitespace_codepoints": len(cp_set),
        "script_character_counts": dict(script_counts),
        "unique_perso_arabic_codepoints": [cp_label(cp) for cp in full_perso],
        "unique_persian_associated_codepoints": [cp_label(cp) for cp in persian_cps],
        "unique_urdu_associated_codepoints": [cp_label(cp) for cp in urdu_cps],
        "character_inventory": inventory,
        "normalization_observations": normalization,
        "encoding_observations": encoding_observations,
        "layout_analysis": layout_classification(text, args),
    }


def font_face_css(record: dict[str, Any], font_path: Path, report_dir: Path, index: int) -> str:
    if record.get("error"):
        return ""
    rel = os.path.relpath(font_path, report_dir).replace(os.sep, "/")
    ext = font_path.suffix.lower()
    fmt = {".ttf":"truetype", ".otf":"opentype", ".woff":"woff", ".woff2":"woff2"}.get(ext, "truetype")
    weight = (record.get("metrics") or {}).get("weight_class") or 400
    return f"@font-face{{font-family:'FontAudit{index}';src:url('{quote(rel)}') format('{fmt}');font-style:normal;font-weight:{weight};font-display:swap;}}"


def font_css_ranges(record: dict[str, Any], font_path: Path, report_dir: Path, index: int) -> str:
    if record.get("error"):
        return ""
    rel = os.path.relpath(font_path, report_dir).replace(os.sep, "/")
    ext = font_path.suffix.lower()
    fmt = {".ttf":"truetype", ".otf":"opentype", ".woff":"woff", ".woff2":"woff2"}.get(ext, "truetype")
    ranges = css_ranges(record.get("cmap_codepoints", []))
    weight = (record.get("metrics") or {}).get("weight_class") or 400
    return f"@font-face {{\n  font-family: 'FontAudit{index}';\n  src: url('{quote(rel)}') format('{fmt}');\n  font-style: normal;\n  font-weight: {weight};\n  font-display: swap;\n  unicode-range: {ranges};\n}}"


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return value


def h(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def render_inventory_table(inventory: list[dict[str, Any]], cmap_by_font: dict[str, set[int]], selected_font: str | None = None) -> str:
    rows = []
    for row in inventory:
        ch = row["character"]
        cp = int(row["codepoint"].split("+")[1], 16)
        supported_count = sum(1 for cmap in cmap_by_font.values() if cp in cmap)
        badge = f"{supported_count}/{len(cmap_by_font)}"
        rows.append(
            "<tr>" +
            f"<td class='glyph' dir='rtl'>{h(ch)}</td><td>{h(row['codepoint'])}</td>"+
            f"<td>{h(row['unicode_name'])}</td><td>{h(row['group'])}</td><td>{row['count']}</td><td>{badge}</td></tr>"
        )
    return "<table><thead><tr><th>Glyph</th><th>Code point</th><th>Unicode name</th><th>Observation</th><th>Count</th><th>Fonts mapping character</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def font_card(record: dict[str, Any], index: int, sample_text: str) -> str:
    if record.get("error"):
        return f"<details class='font-card'><summary>{h(record['filename'])} — inspection error</summary><pre>{h(record['error'])}</pre></details>"
    names = record.get("names", {})
    metrics = record.get("metrics", {})
    opentype = record.get("open_type", {})
    coverage = record.get("text_coverage", {})
    mappings = record.get("cmap_codepoints", [])
    script = ", ".join(f"{h(k)}: {v}" for k, v in record.get("script_coverage", {}).items()) or "—"
    selected_name = h(record.get("family", record["filename"]))
    cov = f"{coverage.get('mapped', 0)}/{coverage.get('total', 0)} ({coverage.get('percent', 0)}%)"

    name_rows = "".join(
        f"<tr><th>{h(key.replace('_', ' ').title())}</th><td>{h(' | '.join(values))}</td></tr>"
        for key, values in sorted(names.items()) if values
    ) or "<tr><td colspan='2'>No name-table records available.</td></tr>"
    metric_rows = "".join(
        f"<tr><th>{h(key.replace('_', ' ').title())}</th><td>{h(json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value)}</td></tr>"
        for key, value in metrics.items() if value is not None and value != []
    )
    open_type_rows = "".join(
        f"<tr><th>{h(key)}</th><td>{h(', '.join(value) if isinstance(value, list) else value)}</td></tr>"
        for key, value in opentype.items() if key not in ("all_tables", "variable_axes")
    )
    cmap_rows = "".join(
        f"<tr><th>Platform {row.get('platform_id')} / encoding {row.get('encoding_id')} / format {row.get('format')}</th><td>Unicode={row.get('unicode')}; language={row.get('language')}; mappings={row.get('mapping_count')}</td></tr>"
        for row in record.get("cmap_subtables", [])
    ) or "<tr><td colspan='2'>No cmap subtables.</td></tr>"
    css = css_ranges(mappings)
    gsub = ", ".join(opentype.get("GSUB", [])) or "—"
    gpos = ", ".join(opentype.get("GPOS", [])) or "—"
    variable = opentype.get("variable_axes", [])
    return f"""
<details class='font-card' id='font-{index}'>
 <summary><span class='font-title'>{selected_name}</span><span class='muted'>{h(record['filename'])}</span><span class='pill'>{cov} sample</span></summary>
 <div class='font-inner'>
  <div class='preview' style='font-family:FontAudit{index}' dir='rtl'>{h(sample_text[:500])}</div>
  <div class='grid-meta'>
   <div><b>Glyph count</b><span>{record.get('glyph_count')}</span></div>
   <div><b>Unicode mappings</b><span>{record.get('unicode_cmap_count')}</span></div>
   <div><b>Weight</b><span>{h(metrics.get('weight_label'))} ({h(metrics.get('weight_class'))})</span></div>
   <div><b>Width</b><span>{h(metrics.get('width_label'))} ({h(metrics.get('width_class'))})</span></div>
   <div><b>Units per em</b><span>{h(metrics.get('units_per_em'))}</span></div>
   <div><b>File size</b><span>{record.get('file_size_bytes',0):,} bytes</span></div>
   <div><b>Family / style</b><span>{h(record.get('family'))} / {h(record.get('subfamily'))}</span></div>
   <div><b>Version</b><span>{h(record.get('version'))}</span></div>
  </div>
  <h4>Possible font role (filename/name heuristic, not certification)</h4><p>{h(', '.join(record.get('possible_roles_from_names', [])))}</p>
  <h4>Unicode script coverage</h4><p>{script}</p>
  <h4>Character coverage for this input</h4><p><b>{cov}</b>. Missing: {h(', '.join(coverage.get('missing_codepoints', [])) or 'None')}.</p>
  <h4>OpenType features and tables</h4><p><b>GSUB:</b> {h(gsub)}</p><p><b>GPOS:</b> {h(gpos)}</p>
  <p><b>Variable axes:</b> {h(json.dumps(variable, ensure_ascii=False)) if variable else 'None detected'}</p>
  <table><thead><tr><th>OpenType property</th><th>Value</th></tr></thead><tbody>{open_type_rows}</tbody></table>
  <h4>Font name-table metadata</h4><table><thead><tr><th>Name record</th><th>Embedded value(s)</th></tr></thead><tbody>{name_rows}</tbody></table>
  <h4>Metrics, OS/2 metadata and embedding flags</h4><table><thead><tr><th>Property</th><th>Value</th></tr></thead><tbody>{metric_rows}</tbody></table>
  <h4>Unicode cmap subtables</h4><table><thead><tr><th>Platform / encoding / format</th><th>Details</th></tr></thead><tbody>{cmap_rows}</tbody></table>
  <h4>Table inventory</h4><p class='small'>{h(', '.join(opentype.get('all_tables', [])))}</p>
  <h4>CSS unicode-range</h4><textarea readonly rows='3' onclick='this.select()'>{h(css)}</textarea>
  <p class='small'>SHA-256: <code>{h(record.get('sha256'))}</code></p>
 </div>
</details>"""


def create_html(report: dict[str, Any], text: str, font_paths: dict[str, Path], output_dir: Path) -> str:
    font_records = report["fonts"]
    css_faces = []
    cards = []
    cmap_by_font = {}
    for i, rec in enumerate(font_records):
        path = font_paths.get(rec["filename"])
        if path:
            css_faces.append(font_face_css(rec, path, output_dir, i))
        cmap_by_font[rec["filename"]] = set(rec.get("cmap_codepoints", []))
        cards.append(font_card(rec, i, text))
    # HTML intentionally includes font cards with previews; the Unicode cmap
    # table remains the authoritative glyph-availability report.
    inventory_html = render_inventory_table(report["text_analysis"]["character_inventory"], cmap_by_font)
    layout = report["text_analysis"]["layout_analysis"]
    evidence_html = "".join(
        f"<article class='evidence'><h4>{h(item['title'])}</h4><p>{h(item['detail'])}</p><p class='muted'>{h(item['meaning'])}</p></article>"
        for item in layout.get("evidence", [])
    )
    refs_html = "".join(
        f"<tr><td>{h(m['layout'])}</td><td>{h(m['filename'])}</td><td>{m['similarity']:.1%}</td></tr>"
        for m in layout.get("reference_comparisons", [])
    ) or "<tr><td colspan='3'>No reference files supplied.</td></tr>"
    fonts_summary = Counter()
    for rec in font_records:
        if rec.get("error"):
            fonts_summary["Error"] += 1
        elif rec.get("arabic_codepoint_count", 0):
            fonts_summary["Arabic-capable cmap"] += 1
        else:
            fonts_summary["No Arabic-block cmap"] += 1
    font_rows = []
    for i, rec in enumerate(font_records):
        coverage = rec.get("text_coverage", {})
        font_rows.append(
            f"<tr><td><a href='#font-{i}'>{h(rec.get('family') or rec['filename'])}</a><div class='small muted'>{h(rec['filename'])}</div></td>"
            f"<td>{h(rec.get('subfamily',''))}</td><td>{h(rec.get('glyph_count','—'))}</td>"
            f"<td>{h(rec.get('unicode_cmap_count','—'))}</td><td>{coverage.get('mapped',0)}/{coverage.get('total',0)} ({coverage.get('percent',0)}%)</td>"
            f"<td>{h(', '.join(rec.get('possible_roles_from_names', [])))}</td></tr>"
        )
    all_css = "\n\n".join(font_css_ranges(rec, font_paths[rec["filename"]], output_dir, i) for i, rec in enumerate(font_records) if rec.get("filename") in font_paths and not rec.get("error"))
    sample_escaped = h(text)
    json_link = h(report.get("outputs", {}).get("json", "font_report.json"))
    csv_link = h(report.get("outputs", {}).get("csv", "character_inventory.csv"))
    css_link = h(report.get("outputs", {}).get("css", "font_unicode_ranges.css"))
    font_csv_link = h(report.get("outputs", {}).get("font_csv", "font_inventory.csv"))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Qur'anic Text & Font Analysis</title>
<style>
:root{{--ink:#18212b;--muted:#627080;--line:#dce3e9;--bg:#f4f7f9;--card:#fff;--accent:#176b5b;--soft:#eaf4f1}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}}main{{max-width:1240px;margin:0 auto;padding:28px 20px 70px}}h1{{font-size:32px;line-height:1.15;margin:0 0 8px}}h2{{margin:34px 0 12px;font-size:23px}}h3{{margin:18px 0 8px}}h4{{margin:16px 0 6px}}p{{margin:6px 0 12px}}.muted,.small{{color:var(--muted)}}.small{{font-size:12px}}.hero,.panel,.font-card{{background:var(--card);border:1px solid var(--line);border-radius:14px}}.hero{{padding:24px}}.panel{{padding:18px;margin:16px 0}}.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:18px}}.stat{{padding:14px;border:1px solid var(--line);border-radius:10px;background:#fff}}.stat b{{display:block;font-size:25px}}.stat span{{color:var(--muted);font-size:12px}}.tag{{display:inline-block;background:var(--soft);color:var(--accent);padding:4px 9px;border-radius:99px;font-size:12px;font-weight:650}}.notice{{border-left:4px solid #b27822;background:#fff9ed;padding:13px 15px;border-radius:8px}}.arabic{{font-family:serif;direction:rtl;text-align:right;line-height:2.15;font-size:23px;white-space:pre-wrap;word-break:normal}}.text-preview{{max-height:340px;overflow:auto;border:1px solid var(--line);padding:18px;border-radius:10px;background:#fff}}table{{border-collapse:collapse;width:100%;font-size:13px;margin:10px 0 18px}}th,td{{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}th{{background:#f1f5f7;position:sticky;top:0}}td.glyph{{font-size:25px;text-align:center;min-width:58px}}code,textarea{{font-family:ui-monospace,monospace}}textarea{{width:100%;border:1px solid var(--line);border-radius:8px;padding:10px;font-size:11px}}.font-list{{display:grid;gap:10px}}.font-card{{overflow:hidden}}.font-card summary{{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:13px 15px;cursor:pointer;list-style:none}}.font-card summary::-webkit-details-marker{{display:none}}.font-title{{font-weight:700}}.pill{{margin-left:auto;background:#eef2f5;border-radius:99px;padding:3px 8px;font-size:12px}}.font-inner{{padding:14px 18px;border-top:1px solid var(--line)}}.preview{{font-size:28px;line-height:2.2;text-align:right;direction:rtl;border:1px solid var(--line);padding:12px;border-radius:10px;max-height:170px;overflow:auto;unicode-bidi:plaintext}}.grid-meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin-top:12px}}.grid-meta>div{{padding:9px;background:#f6f8f9;border-radius:8px}}.grid-meta b,.grid-meta span{{display:block}}.grid-meta b{{font-size:11px;color:var(--muted)}}.grid-meta span{{font-weight:650;overflow-wrap:anywhere}}.evidence{{padding:12px 14px;border:1px solid var(--line);border-radius:10px;margin:9px 0}}.evidence h4{{margin:0 0 4px}}.evidence p{{margin:4px 0}}.actions a{{margin-right:14px}}.filter{{margin:10px 0;padding:10px;border:1px solid var(--line);border-radius:8px;width:100%}}@media(max-width:640px){{main{{padding:14px}}h1{{font-size:26px}}table{{display:block;overflow-x:auto}}}}
{''.join(css_faces)}
</style></head><body><main>
<header class="hero"><span class="tag">Generated by quran_font_analyzer.py</span><h1>Qur'anic Text & Font Analysis</h1><p class="muted">Generated {h(report['generated_at'])}. The report is rebuilt from the font binaries and the selected text input.</p><p class="small">Font scan folder: <code>{h(report.get('input', {}).get('font_dir', ''))}</code> · {h(report.get('input', {}).get('font_scan_mode', 'current folder only'))}</p>
<div class="stats"><div class="stat"><b>{len(font_records)}</b><span>Font files inspected</span></div><div class="stat"><b>{fonts_summary.get('Arabic-capable cmap',0)}</b><span>Fonts with Arabic-block mappings</span></div><div class="stat"><b>{report['text_analysis']['unique_non_whitespace_codepoints']}</b><span>Unique non-whitespace code points in text</span></div><div class="stat"><b>{len(report['text_analysis']['unique_perso_arabic_codepoints'])}</b><span>Perso-Arabic-associated code points</span></div></div></header>
<section class="panel"><h2>1. Input text</h2><p><b>{h(report['text_analysis']['label'])}</b> · {report['text_analysis']['character_count_including_whitespace']} total characters · {report['text_analysis']['non_whitespace_character_count']} non-whitespace characters.</p><div class="text-preview arabic" dir="rtl">{sample_escaped}</div><div class="actions"><a href="{json_link}">Full JSON data</a><a href="{csv_link}">Text character inventory CSV</a><a href="{font_csv_link}">Font metadata CSV</a><a href="{css_link}">CSS unicode-range file</a></div></section>
<section class="panel"><h2>2. Text script and character-encoding observations</h2>
<p><b>Character inventory</b> shows exact Unicode code points. The presence of a Perso-Arabic-associated character is an encoding observation, not proof that the language is Urdu/Persian.</p>
{inventory_html}
<h3>Normalization observations</h3><pre>{h(json.dumps(report['text_analysis']['normalization_observations'], ensure_ascii=False, indent=2))}</pre>
<h3>Distinctive Perso-Arabic / Urdu-associated code points</h3><p>{h(', '.join(report['text_analysis']['unique_perso_arabic_codepoints']) or 'None detected')}</p>
<h3>Encoding observations</h3><pre>{h(json.dumps(report['text_analysis'].get('encoding_observations', {}), ensure_ascii=False, indent=2))}</pre>
</section>
<section class="panel"><h2>3. Can this text be classified as Uthmani, Imla'i or IndoPak?</h2>
<p><span class="tag">{h(layout['status'])}</span></p><h3>{h(layout['classification'])}</h3><p>{h(layout['explanation'])}</p>
{evidence_html}
<h3>Reference-text comparison</h3><p class="small">For automatic identification, place the same passage from a known source in reference_texts/ using filenames such as uthmani.txt, imlaei.txt or indopak.txt. Similarity uses NFC-normalised text with whitespace/tatweel removed, so use the same passage/edition.</p><table><thead><tr><th>Candidate</th><th>Reference file</th><th>Similarity</th></tr></thead><tbody>{refs_html}</tbody></table>
<h3>Classification limitations</h3><ul>{''.join(f'<li>{h(x)}</li>' for x in layout['classifier_limitations'])}</ul>
</section>
<section class="panel"><h2>4. Font overview</h2><p>Glyph count, Unicode cmap mappings and OpenType features measure different things. A cmap match does not prove good mark positioning; visual shaping should also be tested in a real browser.</p>
<input class="filter" id="fontFilter" placeholder="Filter fonts by family or filename…" oninput="filterFonts()">
<table id="fontTable"><thead><tr><th>Family / file</th><th>Subfamily</th><th>Glyphs</th><th>Unicode mappings</th><th>Text coverage</th><th>Possible role inferred from name</th></tr></thead><tbody>{''.join(font_rows)}</tbody></table>
</section>
<section class="panel"><h2>5. Detailed per-font metadata</h2><p>Each record includes name-table metadata, copyright/licence strings when present, weight/width class, embedding flags, font metrics, Unicode block coverage, table inventory, GSUB/GPOS tags, variable-font axes and exact text coverage.</p><div class="font-list">{''.join(cards)}</div></section>
<section class="panel"><h2>6. CSS unicode-range declarations</h2><p>Generated from each font's actual Unicode cmap. The ranges describe mapped code points, not a guarantee of correct shaping or a recommendation to load every font on one page.</p><textarea rows="16" readonly onclick="this.select()">{h(all_css)}</textarea><p class="small">A browser can still use fallback fonts for missing glyphs. Use the cmap coverage table when validating the selected font.</p></section>
<section class="panel"><h2>7. Orthography and page-layout reference</h2>
<p><b>Orthography / text type:</b> Uthmani and Imla'i are two Qur'anic writing conventions; IndoPak is a separately identified Qur'anic text representation, often paired with Nastaliq rendering. Typeface (Naskh/Nastaliq/Kufi) is a different property.</p>
<p><b>Mushaf page layout:</b> a page format such as 15-line or 16-line requires page/line boundaries and verse/word positions. A plain continuous paragraph cannot reveal a printed Mushaf page layout.</p>
<ul>
<li><a href="https://tanzil.net/docs/quran_text_types" target="_blank" rel="noopener">Tanzil: Quran text types</a> — Uthmani and Simple/Imla'i distinction.</li>
<li><a href="https://api-docs.quran.com/docs/api/field-reference/" target="_blank" rel="noopener">Quran Foundation: field reference</a> — separate `text_uthmani`, `text_imlaei` and `text_indopak_nastaleeq` fields.</li>
<li><a href="https://api-docs.quran.com/docs/tutorials/fonts/page-layout/" target="_blank" rel="noopener">Quran Foundation: page layout guide</a> — distinct Mushaf IDs and page/line pagination.</li>
<li><a href="https://www.unicode.org/Public/UCD/latest/charts/nameslist/0600/" target="_blank" rel="noopener">Unicode Arabic names list</a> — code point names and usage notes.</li>
</ul></section>
<footer class="small">Generated by quran_font_analyzer.py. Font metadata and Unicode mappings were read from the supplied font binaries. Orthography classification is evidence-based and deliberately returns inconclusive when the input cannot support a reliable label.</footer>
</main><script>function filterFonts(){{const q=document.getElementById('fontFilter').value.toLowerCase();document.querySelectorAll('#fontTable tbody tr').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(q)?'':'none')}}
</script></body></html>"""


def find_font_files(font_dir: Path, recursive: bool = False) -> list[Path]:
    """Find supported font binaries directly in font_dir (or recursively if requested)."""
    iterator = font_dir.rglob("*") if recursive else font_dir.iterdir()
    return sorted(
        [p for p in iterator if p.is_file() and p.suffix.lower() in FONT_EXTENSIONS],
        key=lambda p: (p.name.casefold(), str(p.parent).casefold()),
    )


def read_text_input(args: argparse.Namespace) -> tuple[str, str, str]:
    """Return (text, label, input_source) for CLI argument, file, or stdin."""
    explicit_modes = sum([args.text is not None, args.text_file is not None, bool(args.stdin)])
    if explicit_modes > 1:
        raise SystemExit("Choose only one of --text, --text-file, or --stdin.")
    if args.text_arg is not None and explicit_modes:
        raise SystemExit("Do not combine positional TEXT with --text, --text-file, or --stdin.")

    if args.text is not None:
        return args.text, args.label or "Command-line text", "--text"
    if args.text_file is not None:
        text_path = args.text_file.expanduser().resolve()
        if not text_path.is_file():
            raise SystemExit(f"Text file not found: {text_path}")
        return text_path.read_text(encoding="utf-8-sig"), args.label or text_path.name, str(text_path)
    if args.stdin:
        text = sys.stdin.read()
        if not text:
            raise SystemExit("No text was received on stdin.")
        return text, args.label or "Standard input", "stdin"
    if args.text_arg is not None:
        return args.text_arg, args.label or "Positional command-line text", "positional argument"

    default_path = DEFAULT_TEXT.resolve()
    if not default_path.is_file():
        raise SystemExit(f"Default sample text not found: {default_path}")
    return default_path.read_text(encoding="utf-8-sig"), args.label or default_path.name, str(default_path)


def print_text_summary(analysis: dict[str, Any], output_format: str = "text") -> None:
    if output_format == "json":
        print(json.dumps(json_safe(analysis), ensure_ascii=False, indent=2))
        return

    print("TEXT CHARACTERISTICS")
    print("=" * 72)
    print(f"Label:                     {analysis.get('label')}")
    print(f"Characters (all):          {analysis['character_count_including_whitespace']}")
    print(f"Characters (non-space):    {analysis['non_whitespace_character_count']}")
    print(f"Distinct code points:      {analysis['unique_non_whitespace_codepoints']}")
    print(f"Script character counts:   {analysis['script_character_counts']}")

    encoding = analysis.get("encoding_observations", {})
    print("\nCHARACTER-ENCODING OBSERVATIONS")
    print("-" * 72)
    print(f"Perso-Arabic-associated characters present: {encoding.get('has_perso_arabic_associated_characters')}")
    print(f"Perso-Arabic-associated character instances: {encoding.get('perso_arabic_character_instances', 0)}")
    print(f"Arabic combining marks:                     {encoding.get('arabic_combining_mark_count', 0)}")
    print(f"Arabic-Indic digits:                         {encoding.get('digit_counts', {}).get('arabic_indic_digits', 0)}")
    print(f"Persian-style digits:                        {encoding.get('digit_counts', {}).get('extended_arabic_indic_persian_style_digits', 0)}")
    print(f"Contains tatweel:                            {analysis['normalization_observations'].get('contains_tatweel')}")
    print(f"Contains ZWNJ / ZWJ:                          {analysis['normalization_observations'].get('contains_zwnj')} / {analysis['normalization_observations'].get('contains_zwj')}")

    perso_rows = encoding.get("perso_arabic_codepoints", [])
    if perso_rows:
        print("\nPerso-Arabic-associated code points:")
        for row in perso_rows:
            print(f"  {row['character']}  {row['codepoint']}  {row['unicode_name']}  count={row['count']}  [{row['group']}]")
    else:
        print("\nNo configured distinctive Perso-Arabic-associated code points were detected.")

    print("\nARABIC / PERSO-ARABIC CHARACTER PAIRS")
    print("-" * 72)
    for key, values in encoding.get("arabic_vs_perso_character_pairs", {}).items():
        print(f"{key}: " + ", ".join(f"{name}={count}" for name, count in values.items()))

    layout = analysis.get("layout_analysis", {})
    print("\nTEXT TYPE / ORTHOGRAPHY ASSESSMENT")
    print("-" * 72)
    print(f"Genre assessment: {layout.get('genre_assessment')}")
    print(f"Classification:   {layout.get('classification')}")
    print(f"Status:           {layout.get('status')}")
    print(f"Explanation:      {layout.get('explanation')}")
    if layout.get("reference_comparisons"):
        print("Reference comparisons:")
        for match in layout["reference_comparisons"]:
            print(f"  {match['layout']}: {match['similarity']:.1%}  ({match['filename']})")
    print("\nImportant: character signals alone cannot certify Uthmani, Imla'i, or IndoPak.")
    print("Use a same-passage reference text or source-declared edition for stronger identification.")

    print("\nCHARACTER INVENTORY")
    print("-" * 72)
    for row in analysis.get("character_inventory", []):
        # json.dumps makes invisible, combining and spacing characters explicit.
        visible = json.dumps(row["character"], ensure_ascii=False)
        print(f"{visible:8} {row['codepoint']:10} {row['unicode_name']} | {row['group']} | count={row['count']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect fonts in the current project folder and analyze Arabic/Qur'anic text encoding.",
        epilog=(
            "Examples:\n"
            "  python quran_font_analyzer.py\n"
            "  python quran_font_analyzer.py --text-only --text 'اللَّهُمَّ اغْفِرْ لَنَا'\n"
            "  python quran_font_analyzer.py 'اللَّهُمَّ اغْفِرْ لَنَا' --text-only\n"
            "  cat passage.txt | python quran_font_analyzer.py --stdin --text-only\n"
            "  python quran_font_analyzer.py --text-file passage.txt --text-kind quran\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("text_arg", nargs="?", help="Optional text string as a positional argument")
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--text-file", type=Path, help="UTF-8 text file to analyze")
    input_group.add_argument("--text", help="Text string to analyze (quote it in the shell)")
    input_group.add_argument("--stdin", action="store_true", help="Read text from standard input; pipes are also detected automatically")
    parser.add_argument("--label", default=None, help="Human-readable name for the input text")
    parser.add_argument("--text-kind", choices=["auto", "quran", "hadith", "arabic-prose", "unknown"], default="auto", help="Context of the input; hadith avoids Qur'anic edition labels")
    parser.add_argument("--declared-layout", choices=["uthmani", "imlaei", "indopak"], help="Known source label; recorded as declared, not inferred")
    parser.add_argument("--reference-dir", type=Path, default=DEFAULT_REFERENCE_DIR, help="Folder containing same-passage reference files named uthmani*.txt, imlaei*.txt, indopak*.txt")
    parser.add_argument("--font-dir", type=Path, default=SCRIPT_DIR, help="Folder containing font files; defaults to the same folder as this Python script")
    parser.add_argument("--recursive-fonts", action="store_true", help="Also scan fonts in nested subfolders")
    parser.add_argument("--output-dir", type=Path, default=SCRIPT_DIR / "report-output", help="Directory where HTML/JSON/CSV/CSS reports are written")
    parser.add_argument("--text-only", "--analyze-text", "--no-report", dest="text_only", action="store_true", help="Print text characteristics only; do not inspect fonts or generate report files")
    parser.add_argument("--output-format", "--format", choices=["text", "json"], default="text", help="Output format for --text-only (default: text)")
    parser.add_argument("--list-fonts", action="store_true", help="List font files found in --font-dir and exit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    text, label, input_source = read_text_input(args)
    args.label = label
    args.reference_dir = args.reference_dir.expanduser().resolve() if args.reference_dir else None

    text_analysis = analyze_text(text, args)
    if args.text_only:
        print_text_summary(text_analysis, args.output_format)
        return 0

    args.font_dir = args.font_dir.expanduser().resolve()
    args.output_dir = args.output_dir.expanduser().resolve()
    if not args.font_dir.is_dir():
        raise SystemExit(f"Font directory not found: {args.font_dir}")
    paths = find_font_files(args.font_dir, recursive=args.recursive_fonts)
    if args.list_fonts:
        for path in paths:
            print(path.name)
        print(f"\n{len(paths)} font file(s) found in {args.font_dir}")
        return 0
    if not paths:
        raise SystemExit(f"No TTF/OTF/WOFF/WOFF2 fonts found in {args.font_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    codepoints = {ord(ch) for ch in text if not ch.isspace()}
    font_records = [inspect_font(path, codepoints) for path in paths]
    report = {
        "tool": "quran_font_analyzer.py",
        "tool_version": "1.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": {
            "label": label,
            "source": input_source,
            "text_kind": args.text_kind,
            "font_dir": str(args.font_dir),
            "font_scan_mode": "recursive" if args.recursive_fonts else "current folder only",
            "reference_dir": str(args.reference_dir) if args.reference_dir else None,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        },
        "text_analysis": text_analysis,
        "font_count": len(font_records),
        "font_files": [path.name for path in paths],
        "fonts": font_records,
        "interpretation_notes": [
            "Font inventory is discovered at runtime from the selected font folder; add or remove font files and rerun to refresh the report.",
            "Font family/style metadata describes the font file, not the orthography of text rendered using it.",
            "Unicode cmap counts direct character mappings, not internal glyphs reached through OpenType substitutions.",
            "GSUB/GPOS feature tags indicate feature availability, not quality of shaping in every browser.",
            "Uthmani, Imla'i and IndoPak require source/edition evidence or comparison with a matching reference text.",
            "A fixed Mushaf page layout requires page and line position metadata; it cannot be inferred from a paragraph alone.",
        ],
        "sources": [
            {"title":"Tanzil Quran Text Types", "url":"https://tanzil.net/docs/quran_text_types"},
            {"title":"Quran Foundation Field Reference", "url":"https://api-docs.quran.com/docs/api/field-reference/"},
            {"title":"Quran Foundation Page Layout API Guide", "url":"https://api-docs.quran.com/docs/tutorials/fonts/page-layout/"},
            {"title":"Unicode Arabic names list", "url":"https://www.unicode.org/Public/UCD/latest/charts/nameslist/0600/"},
        ],
    }
    json_path = args.output_dir / "font_report.json"
    text_json_path = args.output_dir / "text_analysis.json"
    csv_path = args.output_dir / "character_inventory.csv"
    css_path = args.output_dir / "font_unicode_ranges.css"
    font_csv_path = args.output_dir / "font_inventory.csv"
    html_path = args.output_dir / "report.html"
    report["outputs"] = {"json": json_path.name, "text_json": text_json_path.name, "csv": csv_path.name, "font_csv": font_csv_path.name, "css": css_path.name, "html": html_path.name}

    json_path.write_text(json.dumps(json_safe(report), ensure_ascii=False, indent=2), encoding="utf-8")
    text_json_path.write_text(json.dumps(json_safe(text_analysis), ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Character", "Code point", "Unicode name", "Observation", "Unicode category", "Count"])
        for row in text_analysis["character_inventory"]:
            writer.writerow([row["character"], row["codepoint"], row["unicode_name"], row["group"], row["category"], row["count"]])

    font_columns = [
        "filename", "family", "subfamily", "full_name", "postscript_name", "version",
        "designer", "manufacturer", "copyright", "license_description", "license_url",
        "glyph_count", "unicode_cmap_count", "arabic_codepoint_count", "perso_arabic_codepoint_count",
        "private_use_codepoint_count", "weight_class", "weight_label", "width_class", "width_label",
        "units_per_em", "vendor_id", "fs_type", "embedding_permissions", "GSUB", "GPOS",
        "color_tables", "outline_tables", "text_coverage_mapped", "text_coverage_total",
        "text_coverage_missing", "sha256", "error",
    ]
    with font_csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=font_columns, extrasaction="ignore")
        writer.writeheader()
        for rec in font_records:
            names = rec.get("names", {})
            metrics = rec.get("metrics", {})
            ot = rec.get("open_type", {})
            coverage = rec.get("text_coverage", {})
            row = {key: rec.get(key) for key in font_columns}
            row.update({
                "designer": " | ".join(names.get("designer", [])),
                "manufacturer": " | ".join(names.get("manufacturer", [])),
                "copyright": " | ".join(names.get("copyright", [])),
                "license_description": " | ".join(names.get("license_description", [])),
                "license_url": " | ".join(names.get("license_url", [])),
                "weight_class": metrics.get("weight_class"),
                "weight_label": metrics.get("weight_label"),
                "width_class": metrics.get("width_class"),
                "width_label": metrics.get("width_label"),
                "units_per_em": metrics.get("units_per_em"),
                "vendor_id": metrics.get("vendor_id"),
                "fs_type": metrics.get("fs_type"),
                "embedding_permissions": "; ".join(metrics.get("embedding_permissions", [])),
                "GSUB": ", ".join(ot.get("GSUB", [])),
                "GPOS": ", ".join(ot.get("GPOS", [])),
                "color_tables": ", ".join(ot.get("color_tables", [])),
                "outline_tables": ", ".join(metrics.get("outline_tables", [])),
                "text_coverage_mapped": coverage.get("mapped"),
                "text_coverage_total": coverage.get("total"),
                "text_coverage_missing": ", ".join(coverage.get("missing_codepoints", [])),
            })
            writer.writerow(row)

    css_blocks = []
    font_path_map = {path.name: path for path in paths}
    for i, rec in enumerate(font_records):
        css_blocks.append(font_css_ranges(rec, font_path_map[rec["filename"]], args.output_dir, i))
    css_path.write_text("\n\n".join(block for block in css_blocks if block), encoding="utf-8")
    html_path.write_text(create_html(report, text, font_path_map, args.output_dir), encoding="utf-8")

    good = sum(1 for rec in font_records if not rec.get("error"))
    arabic = sum(1 for rec in font_records if rec.get("arabic_codepoint_count", 0))
    print(f"Scanned folder: {args.font_dir} ({'recursive' if args.recursive_fonts else 'direct files only'}).")
    print(f"Inspected {good}/{len(font_records)} font files ({arabic} with Arabic-block mappings).")
    print(f"Text: {label} [{input_source}] — {len(codepoints)} distinct non-whitespace code points.")
    print(f"Text layout assessment: {text_analysis['layout_analysis']['classification']} [{text_analysis['layout_analysis']['status']}].")
    print(f"HTML report: {html_path}")
    print(f"Font JSON:   {json_path}")
    print(f"Text JSON:   {text_json_path}")
    print(f"Text CSV:    {csv_path}")
    print(f"Font CSV:    {font_csv_path}")
    print(f"CSS ranges:  {css_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
