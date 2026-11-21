#!/usr/bin/env python3
"""Build a self-contained HTML report from the TTF/OTF files beside this script.

Requirements: Python 3.10+ and fonttools (`pip install -r requirements.txt`).
The generated index.html expects the font binaries in the same directory.
"""
from __future__ import annotations

from pathlib import Path
from html import escape
from urllib.parse import quote
from fontTools.ttLib import TTFont
import json
import unicodedata

ROOT = Path(__file__).resolve().parent
OUT_HTML = ROOT / "index.html"
OUT_JSON = ROOT / "font_audit.json"

FATIHA_LINES = [
    "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ",
    "ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَٰلَمِينَ",
    "ٱلرَّحْمَٰنِ ٱلرَّحِيمِ",
    "مَٰلِكِ يَوْمِ ٱلدِّينِ",
    "إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ",
    "ٱهْدِنَا ٱلصِّرَٰطَ ٱلْمُسْتَقِيمَ",
    "صِرَٰطَ ٱلَّذِينَ أَنْعَمْتَ عَلَيْهِمْ غَيْرِ ٱلْمَغْضُوبِ عَلَيْهِمْ وَلَا ٱلضَّآلِّينَ",
]
FATIHA_CPS = sorted({ord(c) for line in FATIHA_LINES for c in line if not c.isspace()})
SAW = "ﷺ"
SAW_CP = ord(SAW)
EXPANDED_SALAWAT = "صَلَّى اللّٰهُ عَلَيْهِ وَسَلَّمَ"
EXPANDED_CPS = sorted({ord(c) for c in EXPANDED_SALAWAT if not c.isspace()})

# The six pause-mark classes listed for the Madinah Mushaf by Tanzil.
# The interchangeable pause is represented by the same U+06DB glyph twice.
MADANI_WAQF = [0x06D6, 0x06D7, 0x06D8, 0x06D9, 0x06DA, 0x06DB]
SAKTAH = [0x06DC]
STRUCTURAL = [0x06DD, 0x06DE, 0x06E9]  # end of ayah, rub-el-hizb, sajdah

# A broader Unicode test set for Quranic/recitation annotation signs across
# traditions. This is deliberately broader than the six Madinah pause classes.
EXTENDED_QURANIC = (
    [0x0615] + list(range(0x0617, 0x061B))
    + list(range(0x06D6, 0x06EE))
    + list(range(0x08CC, 0x08D1))
    + list(range(0x08D3, 0x08E3))
    + list(range(0x08F0, 0x08F4))
)


# Engineering classification from supplied font metadata, filenames, Unicode
# coverage and OpenType features. This does NOT determine the rasm/riwayah of
# an arbitrary source text or a fixed printed Mushaf page layout.
FONT_ROLE_INFO = {
    "KFGQPC Uthman Taha Naskh Regular.ttf": ("Unicode Arabic Naskh typeface", "Arabic prose and hadith-style text; maps the U+FDFA honorific used by Sunnah.com.", "Not a fixed Mushaf page layout; does not directly map the six U+06D6–U+06DB Madinah pause signs."),
    "KFGQPC Uthmanic Script HAFS Regular.otf": ("Qur'anic Uthmani/Hafs typeface (font name and character map)", "Qur'anic Unicode text with all six Madinah pause signs mapped.", "Does not directly map U+FDFA in this supplied file; no 15-line page map."),
    "UthmanicHafs_V22.ttf": ("Qur'anic Uthmani/Hafs typeface (version 2.2 metadata)", "Qur'anic Hafs text with a broad mapped Qur'anic annotation repertoire, including the six pause signs.", "Does not directly map U+FDFA; not a fixed-page 15-line font."),
    "AlQuran-IndoPak-by-QuranWBW.v.4.2.2-WL.ttf": ("Indo-Pak Qur'anic typeface", "Indo-Pak style text when the text source's encoding and glyph conventions match.", "Contains many Private Use Area mappings; do not feed arbitrary Unicode Qur'an text without checking the matching encoding."),
    "DigitalKhattIndoPak.otf": ("Indo-Pak Arabic typeface", "Indo-Pak calligraphic text with its supported shaping features.", "The font does not encode a 15-/16-line page map; some Qur'anic marks are not directly mapped."),
    "AmiriQuran.ttf": ("Qur'anic Arabic typeface", "Qur'anic Arabic text; maps the six Madinah pause signs and U+FDFA in this supplied file.", "Font coverage alone does not verify a text's rasm/riwayah or match a printed page."),
    "AmiriQuranColored.ttf": ("Qur'anic Arabic colour typeface", "Qur'anic Arabic text with colour-font design; maps the six Madinah pause signs and U+FDFA.", "Colour-font rendering varies by browser/platform; not a Mushaf page-layout file."),
    "Amiri-Regular.ttf": ("General Arabic Naskh typeface", "Arabic prose and mixed Arabic text; broad Arabic Unicode and annotation coverage.", "Broad coverage does not make it a specific Uthmani or Indo-Pak text edition."),
    "NotoNaskhArabic-Regular.ttf": ("General Arabic Naskh typeface", "General Arabic Unicode text and web interfaces.", "Not a dedicated Madani Mushaf page layout; visually verify Qur'anic mark placement."),
    "NotoKufiArabic-Regular.ttf": ("Kufi-style Arabic typeface", "Display headings and design-led Arabic text.", "Not a conventional Naskh Mushaf page face or page layout."),
    "NotoNastaliqUrdu-Regular.ttf": ("Nastaliq Urdu typeface", "Urdu and Nastaliq-style text when text and language shaping match.", "Not a substitute for a Madani Naskh Qur'an font; test Arabic-only Qur'anic marks separately."),
    "Scheherazade-Regular.ttf": ("Unicode Arabic-script typeface", "Arabic-script languages and extended Unicode text; maps all six pause signs.", "Not an edition-specific Mushaf font; U+FDFA is not directly mapped."),
    "Scheherazade-Bold.ttf": ("Unicode Arabic-script typeface, bold", "Bold Arabic-script text and extended Unicode content; maps all six pause signs.", "Not an edition-specific Mushaf font; U+FDFA is not directly mapped."),
    "Al Qalam Quran Majeed Web Regular.ttf": ("Qur'an-oriented Arabic typeface (font family/name)", "Use with a compatible Qur'anic text sample; maps U+FDFA.", "The name alone does not prove Uthmani rasm, Hafs riwayah or a fixed printed-page layout."),
    "_PDMS_Saleem_QuranFont Regular.ttf": ("Qur'an-oriented Arabic typeface (font family/name)", "Use with a compatible source text/encoding and inspect the live rendered result.", "Contains Private Use Area characters; the exact source encoding is important."),
    "MUHAMMADI QURANIC FONT.ttf": ("Qur'an-oriented Arabic typeface (font family/name)", "Use with a verified sample from the font's intended text source.", "Name and Unicode map alone do not identify rasm, riwayah or page layout."),
    "Katibeh-Regular.ttf": ("Decorative Arabic display typeface", "Headings and display text.", "Not a dedicated Qur'anic text or Mushaf page-layout font."),
    "KacstBook.ttf": ("General Arabic book typeface", "General Arabic text where its character set is sufficient.", "Its character map does not cover the full tested Qur'anic specimen or pause-sign set."),
}


def get_font_role(filename: str, arabic_count: int) -> dict[str, str]:
    info = FONT_ROLE_INFO.get(filename)
    if info:
        return {"class": info[0], "use": info[1], "limit": info[2]}
    if arabic_count == 0:
        return {"class": "Non-Arabic font in this supplied set", "use": "Its Arabic character map is empty; not suitable for Arabic/Qur'anic text by itself.", "limit": "Browser fallback may hide missing-glyph problems in a visual preview."}
    return {"class": "Arabic-capable typeface; role not confidently classified", "use": "Inspect its intended text source, visual style and shaping behaviour before selection.", "limit": "Font file alone does not identify rasm, riwayah or a printed Mushaf page layout."}

# Verbatim verse examples reproduced from Tanzil's Pause Marks documentation.
# Verse strings intentionally remain unchanged; see README for source/license.
PAUSE_EXAMPLES = [
    {
        "type": "Compulsory pause (م)", "cp": "U+06D8", "glyph": "ۘ", "ref": "36:76",
        "text": "فَلَا يَحْزُنكَ قَوْلُهُمْ ۘ إِنَّا نَعْلَمُ مَا يُسِرُّونَ وَمَا يُعْلِنُونَ",
    },
    {
        "type": "Impermissible pause (لا)", "cp": "U+06D9", "glyph": "ۙ", "ref": "16:57",
        "text": "وَيَجْعَلُونَ لِلَّـهِ الْبَنَاتِ سُبْحَانَهُ ۙ وَلَهُم مَّا يَشْتَهُونَ",
    },
    {
        "type": "Permissible pause (ج)", "cp": "U+06DA", "glyph": "ۚ", "ref": "2:45",
        "text": "وَاسْتَعِينُوا بِالصَّبْرِ وَالصَّلَاةِ ۚ وَإِنَّهَا لَكَبِيرَةٌ إِلَّا عَلَى الْخَاشِعِينَ",
    },
    {
        "type": "Pause preferred (قلى)", "cp": "U+06D7", "glyph": "ۗ", "ref": "16:17",
        "text": "أَفَمَن يَخْلُقُ كَمَن لَّا يَخْلُقُ ۗ أَفَلَا تَذَكَّرُونَ",
    },
    {
        "type": "Continuation preferred (صلى)", "cp": "U+06D6", "glyph": "ۖ", "ref": "16:21",
        "text": "أَمْوَاتٌ غَيْرُ أَحْيَاءٍ ۖ وَمَا يَشْعُرُونَ أَيَّانَ يُبْعَثُونَ",
    },
    {
        "type": "Interchangeable pause (paired three dots)", "cp": "U+06DB", "glyph": "ۛ", "ref": "2:2",
        "text": "ذَٰلِكَ الْكِتَابُ لَا رَيْبَ ۛ فِيهِ ۛ هُدًى لِّلْمُتَّقِينَ",
    },
]

# Hafs saktah example in al-Kahf 18:1; the saktah symbol is U+06DC.
SAKTAH_EXAMPLE = {
    "type": "Saktah (brief silence without taking a breath)",
    "cp": "U+06DC", "glyph": "ۜ", "ref": "18:1",
    "text": "عِوَجَاۜ",
}

WAQF_FIXTURE = "بَابٌۖ  بَابٌۗ  بَابٌۘ  بَابٌۙ  بَابٌۚ  بَابٌۛ  بَابٌۛ  بَابٌۜ"
STRUCTURE_FIXTURE = "۝  ۞  ۩"

ARABIC_BLOCKS = [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
                 (0xFB50, 0xFDFF), (0xFE70, 0xFEFF), (0x1EE00, 0x1EEFF)]
BENGALI_BLOCK = (0x0980, 0x09FF)
LATIN_BLOCKS = [(0x0000, 0x024F)]


def get_name(font: TTFont, name_id: int) -> str:
    if "name" not in font:
        return ""
    for rec in font["name"].names:
        if rec.nameID == name_id:
            try:
                val = rec.toUnicode().strip().replace("\r", " ").replace("\n", " ")
                if val:
                    return val[:240]
            except Exception:
                pass
    return ""


def compress_ranges(codepoints: list[int] | set[int]) -> list[tuple[int, int]]:
    cps = sorted(set(codepoints))
    if not cps:
        return []
    ranges: list[tuple[int, int]] = []
    start = prev = cps[0]
    for cp in cps[1:]:
        if cp == prev + 1:
            prev = cp
        else:
            ranges.append((start, prev))
            start = prev = cp
    ranges.append((start, prev))
    return ranges


def range_css(ranges: list[tuple[int, int]]) -> str:
    def one(a: int, b: int) -> str:
        return f"U+{a:04X}" if a == b else f"U+{a:04X}-{b:04X}"
    return ", ".join(one(a, b) for a, b in ranges) or "/* no Unicode mappings */"


def codepoint_name(cp: int) -> str:
    try:
        return unicodedata.name(chr(cp))
    except ValueError:
        return "UNASSIGNED / NO NAME IN THIS PYTHON UNICODE DATABASE"


def get_features(font: TTFont, table_name: str) -> list[str]:
    try:
        fl = font[table_name].table.FeatureList
        return sorted({r.FeatureTag.strip() for r in fl.FeatureRecord}) if fl else []
    except Exception:
        return []


def css_face(rec: dict) -> str:
    fmt = "opentype" if rec["ext"] == ".otf" else "truetype"
    return (
        f'@font-face {{\n'
        f'  font-family: "{rec["alias"]}";\n'
        f'  src: url("{quote(rec["filename"])}") format("{fmt}");\n'
        f'  font-style: normal;\n'
        f'  font-weight: {rec["weight"]};\n'
        f'  font-display: swap;\n'
        f'  unicode-range: {range_css(rec["ranges"])};\n'
        f'}}'
    )


def esc(value: object) -> str:
    return escape(str(value), quote=True)


def cp_list(values: list[int]) -> str:
    return ", ".join(f"U+{v:04X}" for v in values) if values else "None"


def status_class(have: int, total: int) -> str:
    if have == total:
        return "good"
    if have == 0:
        return "bad"
    return "warn"


def make_font_record(path: Path, index: int) -> dict:
    font = TTFont(str(path), lazy=False)
    cmap = font.getBestCmap() or {}
    cps = set(cmap)
    fatiha_missing = [cp for cp in FATIHA_CPS if cp not in cps]
    waqf_missing = [cp for cp in MADANI_WAQF if cp not in cps]
    ext_missing = [cp for cp in EXTENDED_QURANIC if cp not in cps]
    struct_missing = [cp for cp in STRUCTURAL if cp not in cps]
    os2 = font["OS/2"] if "OS/2" in font else None
    record = {
        "index": index,
        "filename": path.name,
        "ext": path.suffix.lower(),
        "family": get_name(font, 16) or get_name(font, 1) or path.stem,
        "subfamily": get_name(font, 17) or get_name(font, 2) or "Regular",
        "alias": f"AuditFont{index}",
        "bytes": path.stat().st_size,
        "glyphs": font["maxp"].numGlyphs if "maxp" in font else 0,
        "cmap_count": len(cps),
        "arabic_count": sum(1 for cp in cps if any(a <= cp <= b for a, b in ARABIC_BLOCKS)),
        "bengali_count": sum(1 for cp in cps if BENGALI_BLOCK[0] <= cp <= BENGALI_BLOCK[1]),
        "latin_count": sum(1 for cp in cps if any(a <= cp <= b for a, b in LATIN_BLOCKS)),
        "fatiha_have": len(FATIHA_CPS) - len(fatiha_missing),
        "fatiha_missing": fatiha_missing,
        "waqf_have": len(MADANI_WAQF) - len(waqf_missing),
        "waqf_missing": waqf_missing,
        "saktah": 0x06DC in cps,
        "structure_have": len(STRUCTURAL) - len(struct_missing),
        "structure_missing": struct_missing,
        "extended_have": len(EXTENDED_QURANIC) - len(ext_missing),
        "extended_missing": ext_missing,
        "saw": SAW_CP in cps,
        "expanded_have": sum(1 for cp in EXPANDED_CPS if cp in cps),
        "expanded_total": len(EXPANDED_CPS),
        "ranges": compress_ranges(cps),
        "weight": os2.usWeightClass if os2 else 400,
        "gsub": get_features(font, "GSUB"),
        "gpos": get_features(font, "GPOS"),
        "fs_type": os2.fsType if os2 else None,
        "license_string": get_name(font, 13),
        "font_role": get_font_role(path.name, sum(1 for cp in cps if any(a <= cp <= b for a, b in ARABIC_BLOCKS))),
    }
    font.close()
    record["css"] = css_face(record)
    return record


def create_row(rec: dict) -> str:
    s = status_class(rec["fatiha_have"], len(FATIHA_CPS))
    w = status_class(rec["waqf_have"], len(MADANI_WAQF))
    e = status_class(rec["extended_have"], len(EXTENDED_QURANIC))
    saw = "good" if rec["saw"] else "bad"
    search = f'{rec["filename"]} {rec["family"]} {rec["subfamily"]} {rec["font_role"]["class"]}'.lower()
    return f'''<tr data-search="{esc(search)}">
<td><strong>{esc(rec['filename'])}</strong><div class="subtle">{esc(rec['family'])} · {esc(rec['subfamily'])}</div></td>
<td class="num">{rec['glyphs']:,}</td>
<td><span class="status {s}">{rec['fatiha_have']}/{len(FATIHA_CPS)}</span><small>Al-Fātiḥah</small></td>
<td><span class="status {w}">{rec['waqf_have']}/{len(MADANI_WAQF)}</span><small>Six Madinah pause types</small><small>Missing: {esc(cp_list(rec['waqf_missing']))}</small></td>
<td><span class="status {'good' if rec['saktah'] else 'bad'}">{'Mapped' if rec['saktah'] else 'Missing'}</span><small>U+06DC Saktah</small></td>
<td><span class="status {status_class(rec['structure_have'], len(STRUCTURAL))}">{rec['structure_have']}/{len(STRUCTURAL)}</span><small>Ayah / hizb / sajdah</small></td>
<td><span class="status {e}">{rec['extended_have']}/{len(EXTENDED_QURANIC)}</span><small>Extended annotation set</small></td>
<td><span class="status {saw}">{'Mapped' if rec['saw'] else 'Missing'}</span><small>U+FDFA ﷺ</small></td>
<td class="num">{rec['bytes'] / 1024:.0f} KB</td>
<td><details><summary>Font role</summary><p>{esc(rec['font_role']['class'])}</p><p>{esc(rec['font_role']['use'])}</p><p class="note">{esc(rec['font_role']['limit'])}</p></details><details><summary>OpenType shaping</summary><pre>GSUB: {esc(', '.join(rec['gsub']) or 'none')}
GPOS: {esc(', '.join(rec['gpos']) or 'none')}</pre></details><details><summary>CSS ranges</summary><pre>{esc(rec['css'])}</pre></details><details><summary>Missing code points</summary><pre>Al-Fātiḥah: {esc(cp_list(rec['fatiha_missing']))}
Madinah pause marks: {esc(cp_list(rec['waqf_missing']))}
Extended annotation set: {esc(cp_list(rec['extended_missing']))}</pre></details></td>
</tr>'''


def make_specimen_card(rec: dict) -> str:
    style = f"font-family:'{rec['alias']}',serif"
    status = "good" if rec["waqf_have"] == len(MADANI_WAQF) else "warn"
    lines = "".join(f'<div class="ayah">{esc(line)}</div>' for line in FATIHA_LINES)
    pause_rows = "".join(
        f'''<div class="verse-test"><div class="verse-meta"><b>{esc(x['type'])}</b><span>{esc(x['ref'])} · {esc(x['cp'])} {esc(x['glyph'])}</span></div>
        <div class="arabic-text" lang="ar" dir="rtl" style="{style}">{esc(x['text'])}</div></div>'''
        for x in PAUSE_EXAMPLES
    )
    extended_chars = "".join(
        f'<span class="annotation-chip" title="U+{cp:04X} {esc(codepoint_name(cp))}"><bdi lang="ar" dir="rtl">بَ{esc(chr(cp))}</bdi><small>U+{cp:04X}</small></span>'
        for cp in EXTENDED_QURANIC
    )
    return f'''<article class="font-card" data-font-card="{rec['index']}">
<div class="font-card-head"><div><h3>{esc(rec['filename'])}</h3><div class="subtle">{esc(rec['family'])} · {esc(rec['subfamily'])} · {rec['glyphs']:,} glyphs · {rec['cmap_count']:,} mapped code points</div><div class="subtle">{esc(rec['font_role']['class'])}</div></div>
<div class="quick-metrics"><span class="status {status}">Waqf {rec['waqf_have']}/{len(MADANI_WAQF)}</span><span class="status {status_class(rec['fatiha_have'], len(FATIHA_CPS))}">Fātiḥah {rec['fatiha_have']}/{len(FATIHA_CPS)}</span></div></div>
<div class="note">{esc(rec['font_role']['use'])} {esc(rec['font_role']['limit'])}</div>
<div class="preview-label">Al-Fātiḥah · live HTML text</div><div class="arabic-panel quran" lang="ar" dir="rtl" style="{style}">{lines}</div>
<div class="metrics-line">Pause marks: <b>{rec['waqf_have']}/{len(MADANI_WAQF)}</b> · Saktah: <b>{'yes' if rec['saktah'] else 'no'}</b> · U+FDFA ﷺ: <b>{'yes' if rec['saw'] else 'no'}</b> · Extended set: <b>{rec['extended_have']}/{len(EXTENDED_QURANIC)}</b></div>
<details><summary>Show all six real pause-mark examples</summary><div class="verse-list">{pause_rows}</div></details>
<details><summary>Show complete pause-mark glyph fixture (not a Qur'anic verse)</summary><div class="arabic-panel quran" lang="ar" dir="rtl" style="{style}">{esc(WAQF_FIXTURE)}</div><p class="note">The repeated word is only an anchor to expose each glyph. It is a typography test, not Qur'anic wording.</p></details>
<details><summary>Show extended Qur'anic annotation glyph gallery</summary><div class="annotation-grid" style="{style}">{extended_chars}</div><p class="note">Each mark is anchored to a test letter for visual inspection. The set contains Unicode annotations from more than one regional/text convention; they are not all used together in one Mushaf.</p></details>
<details><summary>OpenType shaping and positioning features</summary><p><b>GSUB:</b> {esc(', '.join(rec['gsub']) or 'none')}</p><p><b>GPOS:</b> {esc(', '.join(rec['gpos']) or 'none')}</p><p class="note">GSUB features cover substitutions such as contextual forms and ligatures; GPOS features include cursive attachment and mark positioning. Feature tags are evidence of shaping support, not a complete quality score.</p></details>
<div class="phrase-line"><span>Allah's Messenger (</span><bdi lang="ar" dir="rtl" style="{style}">ﷺ</bdi><span>)</span><small>U+FDFA { 'mapped' if rec['saw'] else 'not mapped in this font' }</small></div>
</article>'''


def make_cp_table(cps: list[int], rec: dict | None = None) -> str:
    if rec is None:
        rows = []
        for cp in cps:
            glyph = "بَ" + chr(cp) if unicodedata.category(chr(cp)) in {"Mn", "Me"} else chr(cp)
            rows.append(f'<tr><td class="glyph" lang="ar" dir="rtl">{esc(glyph)}</td><td>U+{cp:04X}</td><td>{esc(codepoint_name(cp))}</td></tr>')
    else:
        cmap_cps = set()
        # Re-open this font to access its map for per-codepoint detail.
        f = TTFont(str(ROOT / rec['filename']), lazy=True)
        cmap_cps = set((f.getBestCmap() or {}).keys())
        f.close()
        rows = []
        for cp in cps:
            status = "good" if cp in cmap_cps else "bad"
            rows.append(f'<tr><td class="glyph">{esc(chr(cp))}</td><td>U+{cp:04X}</td><td>{esc(codepoint_name(cp))}</td><td><span class="status {status}">{"mapped" if cp in cmap_cps else "missing"}</span></td></tr>')
    cols = '<th>Glyph</th><th>Code point</th><th>Unicode name</th>' + ('<th>Status</th>' if rec else '')
    return f'<div class="table-scroll"><table><thead><tr>{cols}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def main() -> None:
    font_files = sorted([p for p in ROOT.iterdir() if p.suffix.lower() in {".ttf", ".otf"}], key=lambda p: p.name.casefold())
    records = [make_font_record(path, i) for i, path in enumerate(font_files, 1)]
    arabic_records = [r for r in records if r["arabic_count"] > 0]
    non_arabic_records = [r for r in records if r["arabic_count"] == 0]
    full_fatiha = sum(r["fatiha_have"] == len(FATIHA_CPS) for r in records)
    full_waqf = sum(r["waqf_have"] == len(MADANI_WAQF) for r in records)
    saw_support = sum(r["saw"] for r in records)
    all_rows = "".join(create_row(r) for r in records)
    cards = "".join(make_specimen_card(r) for r in arabic_records)

    # Produce style declarations for all supplied fonts. Each file lives beside index.html.
    font_faces = "\n".join(r["css"] for r in records)
    fatiha_chip_html = "".join(
        f'<span class="chip"><b>U+{cp:04X}</b> {esc(codepoint_name(cp))}</span>' for cp in FATIHA_CPS
    )
    annotation_html = make_cp_table(EXTENDED_QURANIC)
    kfg = next((r for r in records if r["filename"] == "KFGQPC Uthman Taha Naskh Regular.ttf"), None)
    kfg_hafs = next((r for r in records if r["filename"] == "KFGQPC Uthmanic Script HAFS Regular.otf"), None)

    report_json = {
        "generated_by": "build_report.py",
        "source_font_count": len(records),
        "fatiha_codepoints": FATIHA_CPS,
        "madani_waqf_codepoints": MADANI_WAQF,
        "saktah_codepoints": SAKTAH,
        "structural_codepoints": STRUCTURAL,
        "extended_quranic_annotation_codepoints": EXTENDED_QURANIC,
        "honorific_codepoint": SAW_CP,
        "font_inventory_scope": "54 TTF/OTF files from the user-supplied archive; no external font binaries included",
        "layout_note": "Rasm, riwayah and fixed Mushaf page layout are text/edition/page-data properties, not recoverable from font cmap alone.",
        "fonts": [{k: v for k, v in r.items() if k not in {"css"}} | {"unicode_ranges": [[a, b] for a, b in r["ranges"]]} for r in records],
    }
    OUT_JSON.write_text(json.dumps(report_json, ensure_ascii=False, indent=2), encoding="utf-8")

    css = f"""<style>
{font_faces}
:root{{--ink:#182230;--muted:#667386;--line:#dce3eb;--panel:#fff;--page:#f4f6f9;--accent:#245c91;--green:#176b45;--greenbg:#e9f6ef;--amber:#875b08;--amberbg:#fff4d7;--red:#9e3131;--redbg:#fdecec}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
.wrap{{max-width:1320px;margin:auto;padding:22px}}header{{background:#15283b;color:white;padding:30px;border-radius:15px;margin-bottom:16px}}header h1{{margin:0 0 8px;font-size:clamp(26px,4vw,36px)}}header p{{margin:0;color:#d5e1ed;max-width:900px}}.eyebrow{{text-transform:uppercase;letter-spacing:.12em;font-size:11px;color:#a9c4df;margin-bottom:8px}}
section{{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:22px;margin:14px 0}}h2{{margin:0 0 10px;font-size:22px}}h3{{margin:0;font-size:16px;overflow-wrap:anywhere}}p{{margin:8px 0 12px}}.muted,.subtle,.note{{color:var(--muted)}}.subtle{{font-size:12px}}.note{{font-size:12px}}
.stats{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:16px 0}}.stat{{border:1px solid var(--line);border-radius:10px;padding:14px}}.stat strong{{display:block;font-size:28px;line-height:1.2}}.stat span{{color:var(--muted);font-size:12px}}
.callout{{background:#f0f6fb;border-left:4px solid var(--accent);padding:13px 15px;border-radius:8px;margin:14px 0}}code,pre{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}}code{{background:#eef2f6;border-radius:4px;padding:1px 4px}}
.toolbar{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:13px 0}}input[type=search]{{padding:10px 12px;border:1px solid var(--line);border-radius:8px;font:inherit;min-width:min(100%,340px)}}
.table-scroll{{overflow:auto;border:1px solid var(--line);border-radius:9px;margin:10px 0}}table{{border-collapse:collapse;width:100%;font-size:12px;min-width:850px}}th,td{{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{background:#f5f7fa;position:sticky;top:0;color:#536173;text-transform:uppercase;font-size:10px;letter-spacing:.04em}}td small{{display:block;color:var(--muted);margin-top:3px}}tr:last-child td{{border-bottom:0}}.num{{white-space:nowrap;text-align:right;font-variant-numeric:tabular-nums}}
.status{{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap}}.good{{color:var(--green);background:var(--greenbg)}}.warn{{color:var(--amber);background:var(--amberbg)}}.bad{{color:var(--red);background:var(--redbg)}}
.font-grid{{display:grid;grid-template-columns:1fr;gap:13px}}.font-card{{border:1px solid var(--line);border-radius:11px;padding:15px;overflow:hidden}}.font-card-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px}}.quick-metrics{{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}}.preview-label{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin:8px 0}}
.arabic-panel{{background:#fbfcfe;border:1px solid #e6ebf1;border-radius:9px;padding:12px 16px;overflow-x:auto}}.quran{{font-size:28px;line-height:2.1;text-align:right;direction:rtl;unicode-bidi:plaintext;text-rendering:optimizeLegibility;font-synthesis:none}}.ayah{{min-height:1.7em}}.metrics-line{{margin:9px 0;color:var(--muted);font-size:12px}}details{{margin-top:10px;border-top:1px solid #edf0f3;padding-top:9px}}summary{{cursor:pointer;color:var(--accent);font-weight:650}}.verse-list{{display:grid;gap:10px;margin-top:10px}}.verse-test{{border:1px solid #e8edf2;border-radius:8px;padding:9px 11px}}.verse-meta{{display:flex;gap:12px;justify-content:space-between;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-bottom:4px}}.arabic-text{{font-size:24px;line-height:2;text-align:right;direction:rtl}}.annotation-strip{{font-size:27px;line-height:2.3;text-align:right;white-space:normal;word-spacing:.6em}}.annotation-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:6px;margin-top:10px}}.annotation-chip{{display:flex;align-items:center;justify-content:space-between;gap:8px;border:1px solid var(--line);border-radius:7px;padding:5px 8px;background:#fbfcfe;font-size:23px}}.annotation-chip small{{font:10px ui-monospace,monospace;color:var(--muted)}}.phrase-line{{display:flex;gap:3px;align-items:center;direction:ltr;justify-content:flex-start;border-top:1px solid #edf0f3;padding-top:10px;margin-top:10px;font-size:17px}}.phrase-line bdi{{font-size:1.25em}}.phrase-line small{{color:var(--muted);font-size:11px;margin-left:8px}}
.chips{{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}}.chip{{background:#f6f8fa;border:1px solid var(--line);border-radius:7px;padding:5px 7px;color:var(--muted);font-size:11px}}.chip b{{font-family:ui-monospace,monospace;color:var(--ink)}}.glyph{{font-size:24px;text-align:center;width:75px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#101d2b;color:#e6edf5;border-radius:8px;padding:12px;font-size:11px;line-height:1.45;max-height:360px;overflow:auto;min-width:400px}}
footer{{font-size:12px;color:var(--muted);padding:10px}}a{{color:#145f9a}}ul{{padding-left:22px}}li{{margin:5px 0}}
@media(max-width:850px){{.wrap{{padding:10px}}section{{padding:15px}}.stats{{grid-template-columns:repeat(2,minmax(0,1fr))}}header{{padding:22px}}.font-card-head{{flex-direction:column}}.quick-metrics{{justify-content:flex-start}}.quran{{font-size:23px}}.arabic-text{{font-size:21px}}}}
</style>"""

    kfg_note = ""
    if kfg:
        kfg_note = (f"KFGQPC Uthman Taha Naskh maps {'U+FDFA ﷺ' if kfg['saw'] else 'not U+FDFA ﷺ'}, "
                    f"but maps {kfg['waqf_have']}/{len(MADANI_WAQF)} of the six Madinah pause-mark code points "
                    f"and {kfg['extended_have']}/{len(EXTENDED_QURANIC)} characters in the broader annotation test set.")
    hafs_note = ""
    if kfg_hafs:
        hafs_note = (f"KFGQPC Uthmanic Script HAFS maps {kfg_hafs['waqf_have']}/{len(MADANI_WAQF)} Madinah pause marks, "
                     f"{kfg_hafs['fatiha_have']}/{len(FATIHA_CPS)} Al-Fātiḥah test characters, and "
                     f"{'does' if kfg_hafs['saw'] else 'does not'} map U+FDFA.")

    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Qur'anic Font & Waqf Sign Audit</title>
{css}</head><body><main class="wrap">
<header><div class="eyebrow">Unicode coverage · OpenType shaping · text-layout guide · live Arabic HTML text</div><h1>Qur'anic fonts: coverage, shaping and text layout</h1><p>Static coverage analysis and browser-rendered specimens for {len(records)} supplied TTF/OTF files. Every font file is placed in this same directory as <code>index.html</code>; no <code>fonts/</code> subfolder is required. Specimens are selectable text, not images.</p></header>
<section><h2>At a glance</h2><div class="stats">
<div class="stat"><strong>{len(records)}</strong><span>font files audited</span></div>
<div class="stat"><strong>{len(arabic_records)}</strong><span>fonts with Arabic Unicode mappings</span></div>
<div class="stat"><strong>{full_fatiha}</strong><span>fonts covering every Al-Fātiḥah specimen code point ({len(FATIHA_CPS)})</span></div>
<div class="stat"><strong>{full_waqf}</strong><span>fonts mapping all six Madinah pause types</span></div>
</div><div class="callout"><strong>Do not read the pause-mark score as a general font-quality score.</strong> KFGQPC Uthman Taha Naskh is a Unicode Arabic Naskh face with U+FDFA and Arabic GSUB/GPOS shaping features. Its missing six Madinah pause mappings matter for Qur'anic annotation-heavy text, not for the narrower Sunnah.com hadith-text requirement.</div>
<p><strong>Other KFGQPC file:</strong> {esc(hafs_note)}</p>
<p>The Latin words in <b>Allah's Messenger (ﷺ)</b> should use the site's regular Latin/UI font. The Arabic font is being tested for the single honorific character <code>U+FDFA</code>.</p></section>

<section><h2>Text layout: what a font can and cannot tell you</h2>
<p><b>Important:</b> a font file does not contain the complete identity of the Qur'anic text being rendered. This report tests glyph coverage and OpenType shaping/positioning, and gives a cautious role classification for each supplied font. It cannot infer the rasm or riwayah of an unseen text string.</p>
<div class="table-scroll"><table><thead><tr><th>Layer</th><th>Technical meaning</th><th>Examples</th><th>Where it comes from</th></tr></thead><tbody>
<tr><td><b>Orthography / Rasm</b></td><td>How words are spelled, including Qur'anic spelling conventions versus modern Arabic spelling.</td><td>Rasm Uthmani; Imla'i</td><td>The source text and its edition, not the font name.</td></tr>
<tr><td><b>Riwayah / Qira'ah</b></td><td>The transmitted reading represented by the text, including its authorised vocalisation and variant readings.</td><td>Hafs 'an 'Asim; Warsh 'an Nafi'; Qalun</td><td>The verified text edition and editorial metadata. A font may be designed for one or more readings, but does not choose the reading.</td></tr>
<tr><td><b>Script / Typeface</b></td><td>The shapes and typographic construction of letters.</td><td>Naskh; Nastaliq; Kufi; Maghribi</td><td>The font design and its metadata/visual specimen.</td></tr>
<tr><td><b>Mushaf page layout</b></td><td>Fixed page breaks, line breaks, word positions, page numbering and line count.</td><td>Madani 15-line; Indo-Pak 15-line or 16-line</td><td>Separate page/word layout data or page-specific glyph fonts. An ordinary Unicode font does not provide this.</td></tr>
<tr><td><b>Browser text flow</b></td><td>RTL direction, Arabic joining, mark placement, line wrapping and fallback.</td><td><code>dir="rtl"</code>, GSUB/GPOS, CSS line-height</td><td>HTML/CSS, browser shaping engine and font OpenType tables.</td></tr>
</tbody></table></div>
<p>A line-wrapped Arabic paragraph in a browser is not the same thing as a printed 15-line Mushaf page. To reproduce a specific Mushaf page, you need that edition's page boundaries and word/line placement data. Quran Foundation documents separate IDs for QCF V1/V2, IndoPak, Uthmani Hafs and IndoPak 15-/16-line pagination.</p>
<h3>Role of the Arabic-capable fonts in this upload</h3>
<div class="table-scroll"><table><thead><tr><th>Supplied font</th><th>Likely script/typeface role</th><th>Suitable use</th><th>Limits</th></tr></thead><tbody>
<tr><td><b>KFGQPC Uthman Taha Naskh Regular.ttf</b></td><td>Unicode Arabic Naskh typeface</td><td>Arabic prose/hadith; maps U+FDFA and has Arabic GSUB/GPOS shaping tables.</td><td>Does not map the six Madinah pause signs; no fixed Mushaf page layout.</td></tr>
<tr><td><b>KFGQPC Uthmanic Script HAFS Regular.otf</b></td><td>Qur'anic Uthmani/Hafs typeface</td><td>Qur'anic Unicode text with all six Madinah pause signs mapped.</td><td>Does not map U+FDFA in the supplied file; no page map.</td></tr>
<tr><td><b>UthmanicHafs_V22.ttf</b></td><td>Qur'anic Uthmani/Hafs typeface, v2.2 metadata</td><td>Broad Qur'anic mark coverage, including the six pause signs.</td><td>Does not map U+FDFA; not a fixed 15-line page font.</td></tr>
<tr><td><b>AmiriQuran.ttf / AmiriQuranColored.ttf</b></td><td>Qur'anic Arabic typefaces</td><td>Both map the six pause signs and U+FDFA in this upload.</td><td>Coverage does not verify the text's rasm/riwayah or match a printed page.</td></tr>
<tr><td><b>AlQuran-IndoPak... / DigitalKhattIndoPak.otf</b></td><td>Indo-Pak typefaces</td><td>Indo-Pak text when paired with matching encoding/conventions.</td><td>Not a 15-/16-line page map; PUA encodings require matching source data.</td></tr>
<tr><td><b>Amiri / Noto Naskh / Scheherazade</b></td><td>General Unicode Arabic or Arabic-script typefaces</td><td>General Arabic text and a range of Unicode marks, depending on the individual file.</td><td>Not inherently an Uthmani or Indo-Pak text edition.</td></tr>
<tr><td><b>Noto Kufi / Noto Nastaliq Urdu / Katibeh / KacstBook</b></td><td>Display, Nastaliq or general Arabic typefaces</td><td>Specific design or language use cases.</td><td>Not a general recommendation for Madani Mushaf body text.</td></tr>
</tbody></table></div>
<p class="note">This is an engineering classification based on supplied names, OpenType metadata and cmap results. It is not scholarly certification of a text edition.</p></section>

<section><h2>Why Sunnah.com recommends KFGQPC Uthman Taha Naskh</h2>
<p>Sunnah.com's Fonts note recommends this font, but explicitly says any Arabic font with a complete set of ligatures will do. It specifically calls out Unicode character <code>ﷺ</code> (U+FDFA). This is an Arabic prose/hadith rendering requirement, not a requirement that the font contain all Qur'anic pause marks.</p>
<div class="callout"><b>The supplied KFGQPC Uthman Taha Naskh file meets the key observable requirements:</b> it maps U+FDFA; its GSUB table includes Arabic contextual-form/ligature features (<code>init</code>, <code>medi</code>, <code>fina</code>, <code>liga</code>, <code>calt</code>); and its GPOS table includes cursive and mark positioning (<code>curs</code>, <code>mark</code>, <code>mkmk</code>).</div>
<p>Its metadata reports <b>637 glyphs</b> but only <b>293 Unicode cmap mappings</b>. These figures are not contradictory: many glyphs are contextual forms, ligature outputs or alternates reached through OpenType shaping rather than separate Unicode characters. A low cmap count is not a reliable font-quality ranking.</p>
<p>The earlier report made a <b>test-target mismatch</b>: it scored this Naskh font against pause marks that Sunnah.com does not name as its requirement. For Sunnah.com's stated use case, the font is a reasonable match. For Qur'anic Hafs text with the six Madinah pause marks, use a Qur'anic/Hafs font such as the supplied <code>UthmanicHafs_V22.ttf</code> or <code>AmiriQuran.ttf</code>, then verify the exact source text and visual rendering.</p>
<p class="note">Feature tags are technical evidence, not a complete quality score. Actual text sequences still need visual review in the target browser.</p></section>

<section><h2>Pause marks: the full Madinah set</h2>
<p>Tanzil documents six Madinah Mushaf pause-mark classes. The set is represented by six distinct code points; the interchangeable-pause mark appears twice in its real example. A separate Saktah sign (U+06DC) is also tested below because it matters in Hafs reading but is not one of Tanzil's six listed classes.</p>
<div class="table-scroll"><table><thead><tr><th>Displayed sign</th><th>Code point</th><th>Meaning</th><th>Qur'anic reference example</th></tr></thead><tbody>
<tr><td class="glyph">ۖ</td><td>U+06D6</td><td>Continuation preferred (ṣلى)</td><td>16:21</td></tr>
<tr><td class="glyph">ۗ</td><td>U+06D7</td><td>Pause preferred (قلى)</td><td>16:17</td></tr>
<tr><td class="glyph">ۘ</td><td>U+06D8</td><td>Compulsory pause (م)</td><td>36:76</td></tr>
<tr><td class="glyph">ۙ</td><td>U+06D9</td><td>Impermissible pause (لا)</td><td>16:57</td></tr>
<tr><td class="glyph">ۚ</td><td>U+06DA</td><td>Permissible pause (ج)</td><td>2:45</td></tr>
<tr><td class="glyph">ۛ ۛ</td><td>U+06DB</td><td>Interchangeable pause (paired three dots)</td><td>2:2</td></tr>
<tr><td class="glyph">ۜ</td><td>U+06DC</td><td>Saktah mark (additional Hafs recitation annotation)</td><td>18:1–2</td></tr>
</tbody></table></div>
<p class="note">The six pause-mark descriptions and the first six example references follow Tanzil's documentation. Saktah is shown as an additional recitation mark, not a seventh Madinah pause class.</p></section>

<section><h2>Verified verse examples with all six pause types</h2>
<p>There is no single short Qur'anic passage containing every one of the six pause-mark types. Instead, this project includes the actual example passages listed by Tanzil for each type, so the font can be tested against real text rather than an invented verse.</p>
<div class="verse-list">{''.join(f'''<div class="verse-test"><div class="verse-meta"><b>{esc(x['type'])}</b><span>{esc(x['ref'])} · {esc(x['cp'])} ({esc(x['glyph'])})</span></div><div class="arabic-text" lang="ar" dir="rtl">{esc(x['text'])}</div></div>''' for x in PAUSE_EXAMPLES)}
<div class="verse-test"><div class="verse-meta"><b>{esc(SAKTAH_EXAMPLE['type'])}</b><span>{esc(SAKTAH_EXAMPLE['ref'])} · {esc(SAKTAH_EXAMPLE['cp'])} ({esc(SAKTAH_EXAMPLE['glyph'])})</span></div><div class="arabic-text" lang="ar" dir="rtl">{esc(SAKTAH_EXAMPLE['text'])}</div></div></div>
<p class="note">Pause examples: <a href="https://tanzil.net/docs/pause_marks" target="_blank" rel="noopener">Tanzil — Pause Marks</a>. Saktah example: <a href="https://quran.com/al-kahf/1" target="_blank" rel="noopener">al-Kahf 18:1</a>; the Saktah is the small high seen after عِوَجَا.</p></section>

<section><h2>Constructed glyph stress test (not Qur'anic wording)</h2>
<p>This test repeats a neutral Arabic word and places every Madinah pause-mark glyph, plus the separate Saktah glyph, after it. It is only a typographic fixture; do not quote it as an ayah or as a recitation text.</p>
<div class="arabic-panel quran" lang="ar" dir="rtl">{esc(WAQF_FIXTURE)}</div>
<div class="arabic-panel quran" lang="ar" dir="rtl">{esc(STRUCTURE_FIXTURE)}</div>
<p class="note">Structural glyphs above: U+06DD end-of-ayah, U+06DE rub-el-hizb and U+06E9 place of sajdah.</p></section>

<section><h2>Live specimen comparison by font</h2>
<p>These are live HTML text previews. The static cmap report below tells you whether each character is mapped by that font. A browser may still substitute system fallback glyphs for missing characters, so a glyph appearing on screen does not prove the selected font supplied it.</p>
<div class="toolbar"><input id="fontSearch" type="search" placeholder="Filter font previews by filename"><span id="fontCount" class="muted">{len(arabic_records)} Arabic-capable font previews</span></div>
<div class="font-grid">{cards}</div></section>

<section><h2>Al-Fātiḥah specimen code points</h2><p>The original Al-Fātiḥah sample contains {len(FATIHA_CPS)} distinct non-space code points. Coverage here is separate from the pause-mark tests.</p><div class="chips">{fatiha_chip_html}</div></section>
<section><h2>Broader Unicode Qur'anic annotation inventory</h2>
<p>This extra test set includes Unicode characters identified as Qur'anic annotation signs or additions for Qur'anic orthographies, including regional and less commonly encountered signs. Not every sign is used in every Mushaf tradition, and they are not all pause signs. This broader set is intended to reveal gaps beyond the standard six Madinah pause types.</p>
{annotation_html}</section>

<section><h2>Full font inventory and CSS unicode-ranges</h2>
<p>Each CSS block below is generated from the font's Unicode cmap. It is exact to the mapped code-point table, not a broad guessed Arabic range. File URLs point to the font files in this same directory.</p>
<div class="toolbar"><input id="inventorySearch" type="search" placeholder="Filter all 54 font files"><span id="inventoryCount" class="muted">{len(records)} font files</span></div>
<div class="table-scroll"><table id="fontInventoryTable"><thead><tr><th>Font file / family</th><th class="num">Glyphs</th><th>Al-Fātiḥah</th><th>Six pause types</th><th>Saktah</th><th>Structure</th><th>Extended marks</th><th>ﷺ</th><th class="num">Size</th><th>Font role / OpenType / CSS</th></tr></thead><tbody>{all_rows}</tbody></table></div></section>

<section><h2>Suggested font selection by content type</h2>
<p>Use different faces for different content. Do not select one font solely because it wins the largest Unicode count.</p>
<pre>/* Hadith / ordinary Arabic prose: Sunnah.com-style use case */
.hadith-arabic {{
  font-family: "KFGQPC Uthman Taha Naskh", "Amiri", serif;
}}

/* Qur'anic Hafs text with Madinah pause annotations */
.quran-hafs {{
  font-family: "Uthmanic Hafs V22", "Amiri Quran", serif;
}}

/* Standalone honorific in a separate element */
.honorific {{
  font-family: "KFGQPC Uthman Taha Naskh", "Amiri Quran", serif;
}}</pre>
<p>Define each <code>@font-face</code> using the supplied file names. Keep text in <code>lang="ar" dir="rtl"</code> containers. Do not assign an Indo-Pak font to Uthmani text unless the source's orthography and marks are compatible.</p>
<p class="note">Fallback is relatively safe for a standalone symbol like U+FDFA. Fallback across combining marks in the middle of an Arabic word can produce mismatched placement, so visually validate it and prefer a single font that covers the complete target text.</p></section>

<section><h2>How to interpret this report</h2><ul>
<li><b>Font inventory scope:</b> the binary audit covers the 54 TTF/OTF files in the original user-supplied archive. No external font binary was silently added. External references are used to explain categories and intended use.</li>
<li><b>Unicode cmap:</b> confirms a direct character-to-glyph mapping. It does not count every glyph available through shaping substitutions, nor prove that a glyph is well drawn.</li>
<li><b>Glyph count vs cmap count:</b> total glyph count includes internal contextual forms, ligature outputs and alternates; cmap count measures characters directly mapped by Unicode. Do not compare these as one coverage score.</li>
<li><b>GSUB/GPOS:</b> GSUB replaces glyphs (for example, contextual Arabic forms and ligatures); GPOS positions glyphs and marks. Feature tags are useful evidence, not a complete font-quality metric.</li>
<li><b>Text identity:</b> rasm/orthography and riwayah belong to the source text/edition. A font name cannot establish that arbitrary text is Uthmani, Imla'i, Hafs or Warsh.</li>
<li><b>Page layout:</b> 15-line Madani, 15-/16-line Indo-Pak and similar formats require page/line metadata. Ordinary Unicode fonts do not store the full layout.</li>
<li><b>Fallback:</b> a browser may display missing characters from another font. Coverage results always refer to the selected font's own cmap.</li>
<li><b>unicode-range:</b> tells the browser which characters a font face may supply. It cannot add a glyph absent from the font.</li>
</ul></section>

<footer>Built from {len(records)} supplied TTF/OTF files. HTML specimens are live text, not images. Font files are included as received. Check each font's licence before redistributing or deploying it publicly. See README.md for sources and build instructions.</footer>
</main>
<script>
function filterRows(inputId, rowSelector, countId, noun) {{
  const input=document.getElementById(inputId); if(!input) return;
  input.addEventListener('input',()=>{{
    const q=input.value.trim().toLowerCase(); let n=0;
    document.querySelectorAll(rowSelector).forEach(el=>{{
      const value=(el.dataset.search || el.textContent).toLowerCase();
      const ok=!q || value.includes(q); el.style.display=ok?'':'none'; if(ok)n++;
    }});
    document.getElementById(countId).textContent=n+' '+noun;
  }});
}}
filterRows('inventorySearch','#fontInventoryTable tbody tr','inventoryCount','matching font files');
filterRows('fontSearch','.font-card','fontCount','matching font previews');
</script></body></html>'''

    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Fonts: {len(records)} total, {len(arabic_records)} Arabic-capable, {len(non_arabic_records)} no Arabic map")
    print(f"Full Al-Fatiha: {full_fatiha}; full six pause types: {full_waqf}; U+FDFA support: {saw_support}")
    print(f"Generated: {OUT_HTML} ({OUT_HTML.stat().st_size:,} bytes)")
    print(f"Generated: {OUT_JSON} ({OUT_JSON.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
