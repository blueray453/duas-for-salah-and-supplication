# Qur'anic Text & Font Analyzer

A reproducible Python tool that scans font binaries beside the script, extracts font metadata and Unicode/OpenType coverage, and analyzes an input Arabic-script text across separate dimensions:

1. **Orthography / text representation** — Uthmani, Imla'i/Simple, IndoPak, or inconclusive.
2. **Riwayah** — Hafs, Warsh, Qalun, etc., only when declared or matched to a labelled reference.
3. **Script tradition** — Madani/Uthmani, IndoPak, Maghribi, etc., only when supported by metadata.
4. **Typeface** — Naskh, Nastaleeq, Kufi, etc.; a font property, not a text property.
5. **Digital encoding model** — ordinary Unicode, QPC glyph code V1/V2, IndoPak Unicode rendering, or unknown.
6. **Mushaf page layout** — page edition, line count and Mushaf ID; requires source/page metadata.

The analyzer deliberately does **not** infer all six dimensions from a handful of Unicode characters. It uses source declarations, local same-passage reference files, Quran Foundation field names and selected Mushaf metadata. Heuristic character observations are labelled as observations, not certifications.

## Project contents

- 57 supplied font binaries in the project root (including the additional QPC/IndoPak/Adobe Arabic/FontAwesome files from earlier iterations).
- `quran_font_analyzer.py` — all inspection, text analysis and report generation.
- `report-output/` — generated HTML, JSON, CSV and CSS output.
- `samples/` — example hadith text and Uthmani Al-Fatihah sample.
- `reference_texts/` — optional same-passage source references and manifest.
- `tests/` — automated regression tests.
- `CLASSIFICATION-METHODOLOGY.md` — classification boundaries and examples.
- `SOURCE-REFERENCES.md` — technical sources.
- `FONT-LICENSE-NOTES.md` — embedded licence metadata notes.

## Requirements and installation

- Python 3.10+
- `fonttools[woff]`
- `brotli` for WOFF2 support

```bash
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\\Scripts\\activate    # Windows PowerShell
python -m pip install -r requirements.txt
```

## 1. Generate the full report

```bash
python quran_font_analyzer.py
```

By default the program:

1. Scans `.ttf`, `.otf`, `.woff` and `.woff2` files directly beside the script.
2. Uses `samples/hadith_quranohadith_original.txt` as the input text.
3. Regenerates `report-output/`.

The font list is discovered at runtime. Add/remove a font in the project root and rerun; no source-code list or manifest update is needed.

Scan nested folders too:

```bash
python quran_font_analyzer.py --recursive-fonts
```

Use another font folder:

```bash
python quran_font_analyzer.py --font-dir /path/to/fonts
```

List discovered fonts:

```bash
python quran_font_analyzer.py --list-fonts
```

## 2. Analyze a text without scanning fonts or generating files

Positional argument:

```bash
python quran_font_analyzer.py 'ك ک ي ی ه ہ' --text-only
```

Option argument:

```bash
python quran_font_analyzer.py --text 'اللَّهُمَّ اغْفِرْ لَنَا' --text-only
```

UTF-8 file:

```bash
python quran_font_analyzer.py --text-file passage.txt --text-only
```

Standard input:

```bash
cat passage.txt | python quran_font_analyzer.py --stdin --text-only
```

JSON output:

```bash
python quran_font_analyzer.py --text 'ك ک ي ی' --text-only --format json
```

Text-only mode reports character counts, Unicode names/code points, Arabic/Perso-Arabic distinctions, digits, punctuation, diacritics, Qur'anic marks, private-use and presentation-form characters, normalization and the separate dimension assessments. It does not scan the font files.

## 3. Generate a full font report for another text

```bash
python quran_font_analyzer.py --text-file my-hadith.txt --text-kind hadith
python quran_font_analyzer.py --text-file my-ayah.txt --text-kind quran
python quran_font_analyzer.py --text 'اللَّهُمَّ اغْفِرْ لَنَا' --label 'Dua sample'
cat my-ayah.txt | python quran_font_analyzer.py --stdin --text-kind quran
```

`--text-kind` accepts `auto`, `quran`, `hadith`, `arabic-prose` and `unknown`. It sets the analysis context; it does not determine the orthography.

## 4. Multi-dimensional text classification

The report presents each dimension separately. Example source-declared metadata:

```bash
python quran_font_analyzer.py \
  --text-file ayah.txt --text-kind quran \
  --declared-orthography uthmani \
  --declared-riwayah hafs \
  --declared-script-tradition madani \
  --declared-typeface naskh \
  --encoding-model unicode-text \
  --page-layout 'Madani 15-line' \
  --line-count 15 --page-count 604
```

Available declaration options:

| Option | Values / use |
|---|---|
| `--declared-orthography` | `uthmani`, `imlaei`, `indopak` |
| `--declared-layout` | Backward-compatible alias for `--declared-orthography` |
| `--declared-riwayah` | `hafs`, `warsh`, `qalun`, `shuabah`, `duri`, `other` |
| `--declared-script-tradition` | `madani`, `indopak`, `maghribi`, `qpc-nastaleeq`, `other` |
| `--declared-typeface` | `naskh`, `nastaleeq`, `kufi`, `maghribi`, `thuluth`, `ruqah`, `other` |
| `--encoding-model` | `unicode-text`, `unicode-indopak-nastaleeq`, `qpc-glyph-v1`, `qpc-glyph-v2`, `digital-khatt-v1`, `digital-khatt-v2`, `digital-khatt-indopak`, `unknown` |
| `--qf-field` | A documented Quran Foundation field; fills only dimensions documented for that field (see below) |
| `--mushaf-id` | Quran Foundation Pages Lookup ID (see table below) |
| `--page-layout` | Free-text source description, e.g. `IndoPak 16-line` |
| `--line-count` | Known lines per page |
| `--page-count` | Known page count |
| `--font-for-text` | Exact font filename or embedded family name to attach as typography context in a full report |

A declaration is reported as **source-declared**, not inferred. The analyzer does not infer Hafs/Warsh from generic diacritics, does not equate IndoPak with Urdu-associated Unicode letters, and cannot derive a 15-/16-line printed page from a continuous paragraph.

## 5. Quran Foundation (QUL/QF) text fields and digital formats

The analyzer records the meaning/rendering notes for these documented field names:

| Field | Analyzer interpretation |
|---|---|
| `text_uthmani` | Uthmani text |
| `text_uthmani_simple` | Simplified representation of Uthmani text |
| `text_uthmani_tajweed` | Uthmani Tajweed text |
| `text_imlaei` | Imla'i/Simple text |
| `text_imlaei_simple` | Imla'i/Simple variant |
| `text_indopak_nastaleeq` | IndoPak Nastaleeq Unicode; use the compatible font |
| `text_indopak` | Deprecated IndoPak field, retained for compatibility |
| `text_qpc_hafs` | QPC Hafs Unicode text |
| `qpc_uthmani_hafs` | Deprecated alias for `text_qpc_hafs` |
| `text_qpc_nastaleeq` | QPC Nastaleeq representation; verify its compatible rendering font |
| `text_qpc_nastaleeq_hafs` | QPC Nastaleeq Hafs representation |
| `code_v1` / `code_v2` | QPC glyph-code data, not ordinary Unicode verse text |

The QF field reference identifies `text_indopak_nastaleeq` as the current IndoPak Nastaleeq text field and marks `text_indopak` as deprecated. It also lists `text_qpc_nastaleeq`, `text_qpc_nastaleeq_hafs`, and the deprecated `qpc_uthmani_hafs` alias. The font-rendering guide warns that the IndoPak Nastaleeq text must be rendered with its compatible font, otherwise waqf signs and verse-end markers may not render correctly.

### Use a Quran Foundation field directly

When you know the name of the field from which your text came, pass it to `--qf-field`. The analyzer then applies only the metadata documented for that field; unknown dimensions remain inconclusive.

```bash
# Unicode Uthmani text field
python quran_font_analyzer.py --text-file ayah.txt --text-kind quran --qf-field text_uthmani

# IndoPak Nastaleeq field (marks typeface and compatible-font requirement)
python quran_font_analyzer.py --text-file ayah.txt --text-kind quran --qf-field text_indopak_nastaleeq

# QPC glyph-code data (identifies the encoding model, not a font-independent text string)
python quran_font_analyzer.py --text-file qpc_words.txt --text-kind quran --qf-field code_v2 --mushaf-id 1
```

`--qf-field` is source metadata, not an automatic text detector. Do not use it unless the input actually came from that field. `--qf-field` cannot be combined with `--text-kind hadith` or `arabic-prose`.

Digital Khatt variants are not assigned merely from Unicode characters. If your source identifies the specific variant, record it explicitly with `--encoding-model digital-khatt-v1`, `digital-khatt-v2`, or `digital-khatt-indopak`.

## 6. Quran Foundation Mushaf IDs in the analyzer

The built-in catalogue follows the Pages Lookup API guide checked on 2026-11-23:

| ID | Name | Pages | Lines | Notes |
|---:|---|---:|---:|---|
| 1 | QCF V2 | 604 | — | QPC glyph V2 workflow |
| 2 | QCF V1 | 604 | — | QPC glyph V1 workflow |
| 3 | IndoPak | 604 | — | IndoPak script resource |
| 4 | Uthmani Hafs | 604 | — | Uthmani/Hafs resource |
| 5 | KFGQPC Hafs | 604 | — | King Fahd Complex Hafs resource |
| 6 | IndoPak 15-line | 610 | 15 | South Asian 15-line Mushaf |
| 7 | IndoPak 16-line | 548 | 16 | South Asian 16-line Mushaf |
| 11 | Tajweed | 604 | — | Tajweed resource; verify actual text field/riwayah |
| 19 | QCF Tajweed V4 | 604 | — | QCF Tajweed V4 resource |

The ID map is included in `font_report.json` and the HTML report. Confirm IDs against the current API documentation before relying on them in a production integration.

Example:

```bash
python quran_font_analyzer.py --text-file ayah.txt --text-kind quran --mushaf-id 7
```

This records the IndoPak 16-line Mushaf metadata. It does not prove that arbitrary supplied text was copied from that edition; it is metadata supplied by the user.

## 7. Same-passage reference matching (recommended for identification)

Character signals alone cannot reliably distinguish Uthmani, Imla'i and IndoPak. For stronger comparison, place a text file for the **same passage** in `reference_texts/` and describe it with a manifest.

Create `reference_texts/manifest.json` using this structure:

```json
{
  "references": [
    {
      "file": "uthmani_hafs_madani_15_lines.txt",
      "orthography": "Uthmani",
      "riwayah": "Hafs",
      "script_tradition": "Madani / Uthmani",
      "typography": "Naskh",
      "encoding_model": "Unicode text",
      "page_layout": "Madani 15-line",
      "line_count": 15,
      "page_count": 604,
      "mushaf_id": 5,
      "qf_field": "text_uthmani",
      "source": "Name of source/edition",
      "source_url": "https://example.org/edition"
    }
  ]
}
```

Use `reference_texts/manifest.example.json` as a template. Only use `source`/`source_url` values that you have verified. Each referenced `.txt` file must contain the matching passage. A strong exact/subsequence match can identify the dimensions listed in the manifest. A fuzzy or base-letter-only similarity is shown as diagnostic evidence, not as a definitive classification.

Filename conventions are also supported when no manifest entry exists. Examples:

- `uthmani_hafs_madani.txt`
- `imlaei_hafs.txt`
- `indopak_hafs_nastaleeq_16_lines.txt`
- `qpc_glyph_v2_hafs.txt`

The manifest is preferable because it can explicitly describe all the dimensions without relying on filename tokens.

Run:

```bash
python quran_font_analyzer.py \
  --text-file my-ayah.txt --text-kind quran \
  --reference-dir reference_texts
```

This is a text similarity comparison, not scholarly authentication. Check the provenance, edition and verse range of each reference.

## 8. Font typography metadata

Each font record includes its embedded family/style names, designer, manufacturer, copyright and licence strings (when present), weight/width, glyph count, cmap mappings, Unicode blocks, metrics, embedding flags, GSUB/GPOS tags, variable axes, table inventory, CSS `unicode-range` and text coverage.

The report additionally extracts filename/name-table indicators for typography labels (Naskh, Nastaleeq, Kufi, etc.), named products (QPC/KFGQPC, Digital Khatt, IndoPak, etc.) and recitation strings (Hafs/Warsh/Qalun) when present. These are metadata hints about the font product, **not proof about a text rendered using it**.

To attach a font to the text report:

```bash
python quran_font_analyzer.py --text-file my-ayah.txt --text-kind quran --font-for-text 'KFGQPC Uthman Taha Naskh Regular.ttf'
```

## 9. Generated files

The full report is written to `report-output/`:

| File | Purpose |
|---|---|
| `report.html` | Interactive report with all text dimensions, reference comparisons, font overview and per-font detail cards |
| `font_report.json` | Full machine-readable report, font inventory, QUL field map and Mushaf ID catalogue |
| `text_analysis.json` | Text characteristics and multi-dimensional classification |
| `font_inventory.csv` | One row per font, with metadata and typography-name indicators |
| `character_inventory.csv` | One row per character in the selected text |
| `font_unicode_ranges.css` | CSS `@font-face`/`unicode-range` declarations |

These files are overwritten on each full report run. Adding/removing font binaries changes the next font inventory and text-coverage results.

## 10. Automated tests

```bash
python -m unittest discover -s tests -v
```

## Interpretation boundaries

- Font metadata is not text metadata.
- Glyph count is not cmap count; OpenType substitutions can use internal glyphs that are not directly mapped to Unicode.
- cmap coverage is not shaping quality; GSUB/GPOS feature presence does not guarantee browser rendering quality.
- Arabic-script code points are not language detection.
- IndoPak is not simply text containing Urdu/Persian characters.
- Absence of Uthmani-associated code points does not prove Imla'i.
- Typeface is separate from orthography and script tradition.
- Page line-count/pagination needs a Mushaf ID or page/word position metadata.
- Font embedding flags are not a complete licence assessment; read the upstream licence before redistribution or web hosting.

See `CLASSIFICATION-METHODOLOGY.md` for detail.
