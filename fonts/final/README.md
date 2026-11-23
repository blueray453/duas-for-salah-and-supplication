# Qur'anic Text & Font Analyzer

A reproducible Python project for inspecting Arabic/Qur'anic font files and examining a supplied Arabic text's Unicode character repertoire. The Python program generates the HTML report, JSON data, CSV character inventory and CSS `unicode-range` file.

## What it analyzes

### Every font file (`fonts/`)

For each TTF, OTF, WOFF or WOFF2 file, the report extracts the available:

- Font identity: family, subfamily, full name, PostScript name, version and unique ID.
- Attribution: copyright, designer, manufacturer, trademark, description, vendor/designer URLs and embedded license text/URL when present.
- Glyph count and Unicode cmap count (these are different measurements).
- Unicode code-point coverage grouped by script/block, including Arabic, Bengali, Latin, Arabic presentation forms and Private Use Area.
- OpenType GSUB and GPOS feature tags, GDEF presence, legacy kern table, color-font tables and variable-font axes.
- Metrics: units per em, font bounding box, weight/width class, OS/2 and hhea ascender/descender values, italic angle, underline metrics and vendor ID.
- `fsType` embedding-permission flags when present.
- SHA-256 hash and direct cmap coverage for the selected text.
- CSS `unicode-range` generated from the actual font cmap.

All metadata is reported as embedded in each binary. Missing metadata is shown as blank; it is not guessed.

### A selected text

The text analyser reports:

- Every distinct non-whitespace Unicode code point, Unicode name, category, frequency and code-point value.
- Perso-Arabic / Urdu-associated forms such as Keheh, Farsi Yeh, Heh Goal, Teh Marbuta Goal and extended Arabic-Indic digits.
- Arabic-Indic digits, Qur'anic annotation signs, Uthmani-associated characters and pause marks.
- NFC/NFKC normalisation observations, combining-mark count and tatweel.
- Whether each font maps every character used in the selected text.

The Perso-Arabic indicators describe code-point usage. They do **not** by themselves prove that the language is Urdu or Persian.

## Can it classify a text as Uthmani, Imla'i or IndoPak?

It deliberately separates a **signal-based assessment** from a **verified classification**.

- Uthmani and Imla'i/Simple are Qur'anic orthography/text-edition labels. Tanzil describes Uthmani and Simple (Imla'i) as separate text types.
- Quran Foundation exposes different data fields for `text_uthmani`, `text_imlaei` and `text_indopak_nastaleeq`. It also explains that IndoPak text needs a compatible font.
- Uthmani-associated code points, superscript marks or waqf symbols are useful clues, but their presence/absence does not certify an edition.
- IndoPak is not simply “Arabic text with Urdu letters”, and it is not synonymous with a Nastaliq typeface.
- A printed page layout such as Madani 15-line or IndoPak 16-line needs actual page/line/word-position information. It cannot be inferred from an unbroken paragraph.

For a confident comparison, supply the **same passage** from a known edition as a reference text. The script compares NFC-normalised character sequences after removing whitespace and tatweel. A near-exact match is reported as a strong reference match. You can also use `--declared-layout` to record an edition label already known from the source; this is explicitly marked as source-declared, not inferred.

## Install

Python 3.10 or later is recommended.

```bash
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\\Scripts\\activate    # Windows PowerShell
python -m pip install -r requirements.txt
```

`fontTools` reads TTF/OTF metadata and cmap tables. `brotli` enables WOFF2 decoding.

## Run the default analysis

From the project directory:

```bash
python quran_font_analyzer.py
```

This uses `samples/hadith_quranohadith_original.txt` and scans all font files in `fonts/`. It generates:

```text
report-output/
├── report.html
├── font_report.json
├── text_analysis.json
├── character_inventory.csv
└── font_unicode_ranges.css
```

Open `report-output/report.html` in a browser. The relative font paths allow the report's font specimens to load from `../fonts/`.

## Analyze another text

```bash
python quran_font_analyzer.py --text-file /path/to/my-arabic-text.txt
```

Or pass a short sample directly:

```bash
python quran_font_analyzer.py --text "اللَّهُمَّ اغْفِرْ لَنَا" --label "Dua sample"
```

For a known hadith, specify its genre so it is not presented as a Qur'anic edition:

```bash
python quran_font_analyzer.py --text-file my_hadith.txt --text-kind hadith
```

For a known Qur'anic excerpt, use:

```bash
python quran_font_analyzer.py --text-file my_ayah.txt --text-kind quran
```

The `quran` flag says what kind of source the user supplied; it does not assert Uthmani/Imla'i/IndoPak.

## Compare with known source text

Put matching reference files in `reference_texts/`:

```text
reference_texts/
├── uthmani_reference.txt
├── imlaei_reference.txt
└── indopak_reference.txt
```

Only `.txt` files with these filename prefixes are loaded. Each file should contain the same verse or passage as the input text, from the named edition. Then run:

```bash
python quran_font_analyzer.py --text-file my_ayah.txt --text-kind quran --reference-dir reference_texts
```

The report shows similarity scores. A 98.5% or higher normalized sequence similarity is labeled a strong reference match. This is a practical comparison threshold, not a scholarly standard. Check source provenance and the exact edition.

To record a known classification from source metadata instead:

```bash
python quran_font_analyzer.py --text-file my_ayah.txt --declared-layout uthmani
# accepted: uthmani, imlaei, indopak
```

## Other options

```bash
python quran_font_analyzer.py --help
python quran_font_analyzer.py --font-dir ./fonts --output-dir ./my-report
```

Fonts can be placed in any chosen `--font-dir`; the report generator computes paths relative to the output folder.

## Important interpretation rules

1. **Font metadata is not text metadata.** A file named Uthmanic/Hafs may be a Qur'anic typeface, but that does not prove arbitrary text rendered in it is Uthmani/Hafs.
2. **Glyph count is not cmap count.** OpenType substitutions can access internal glyphs that do not have direct Unicode mappings.
3. **cmap coverage is not shaping quality.** GSUB/GPOS feature presence is useful metadata, but it does not prove all mark combinations render correctly in every browser.
4. **Arabic script is not a language.** Perso-Arabic code points can occur in Arabic prose copied from a source that uses those characters; this does not make the passage linguistically Urdu.
5. **No Uthmani marker does not prove Imla'i.** Marks may have been stripped, the sample may be short, or the text may be a prose excerpt.
6. **Page layout is separate.** 15-line/16-line page pagination needs a Mushaf edition's page and line mapping.

## Project layout

```text
quran_text_font_analyzer/
├── quran_font_analyzer.py
├── requirements.txt
├── README.md
├── SOURCE-REFERENCES.md
├── fonts/                    # Original font set + Adobe Arabic WOFF2 reference
├── samples/
├── reference_texts/          # Add matched edition passages here
└── report-output/            # Generated outputs
```

## Licensing

The font binaries are supplied as audit inputs. Their presence in this local project does not grant redistribution or web-hosting rights. Check each embedded license note and the font's upstream license before redistribution or production deployment.

For the distinction between direct code-point observations and Qur'anic edition classification, see `CLASSIFICATION-METHODOLOGY.md`.
