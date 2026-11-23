# Qur'anic Text & Font Analyzer

A reproducible Python utility that scans font files in the **same folder as the Python script**, inspects their metadata and Unicode/OpenType coverage, and analyzes any supplied Arabic-script text.

The font inventory is discovered every time the program runs. You do not need to edit a font list or update a manifest when adding/removing fonts.

## What's included

- 57 font binaries currently included in the project root: the previous 55 plus two files from the latest archive.
- `quran_font_analyzer.py`: the complete analyzer and report generator.
- `report-output/`: generated HTML, JSON, CSV and CSS files (recreated on each report run).
- `samples/`: example hadith text and a Uthmani Al-Fatihah sample.
- `reference_texts/`: folder for matched Uthmani, Imla'i and IndoPak reference passages.
- `tests/`: automated tests.
- `CLASSIFICATION-METHODOLOGY.md`: what can and cannot be inferred about text types.
- `FONT-LICENSE-NOTES.md`: notes about embedded font licensing metadata.

## Requirements

- Python 3.10+
- `fonttools[woff]`
- `brotli` (WOFF2 support)

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\\Scripts\\activate    # Windows PowerShell
python -m pip install -r requirements.txt
```

## 1. Generate the full report

Run from any working directory:

```bash
python /path/to/quran_text_font_analyzer/quran_font_analyzer.py
```

By default the script:

1. Scans font binaries placed directly beside `quran_font_analyzer.py`.
2. Uses `samples/hadith_quranohadith_original.txt` as the analysis text.
3. Rebuilds `report-output/`.

It scans `.ttf`, `.otf`, `.woff` and `.woff2` files. The scan is non-recursive by default.

### Add or remove fonts

Place a new font file directly in the project folder, beside `quran_font_analyzer.py`, and rerun the command. Remove a font file and rerun to remove it from the next report. No Python list, JSON manifest or configuration needs changing.

Example folder layout:

```text
quran_text_font_analyzer/
├── quran_font_analyzer.py
├── AdobeArabic.woff2
├── MyArabicFont.otf
├── AnotherFont.ttf
├── UthmanTN1.otf
├── fontawesome-webfont.woff2
├── samples/
├── reference_texts/
└── report-output/
```

To scan nested font folders too:

```bash
python quran_font_analyzer.py --recursive-fonts
```

To use a different folder:

```bash
python quran_font_analyzer.py --font-dir /path/to/font-folder
```

List what will be scanned:

```bash
python quran_font_analyzer.py --list-fonts
```

## 2. Analyze a text without generating the full font report

This mode prints text characteristics to the terminal. It does not scan fonts or create report files.

### As an option argument

```bash
python quran_font_analyzer.py --text 'اللَّهُمَّ اغْفِرْ لَنَا' --text-only
```

### As a positional argument

```bash
python quran_font_analyzer.py 'اللَّهُمَّ اغْفِرْ لَنَا' --text-only
```

### From a UTF-8 text file

```bash
python quran_font_analyzer.py --text-file passage.txt --text-only
```

### From standard input

```bash
cat passage.txt | python quran_font_analyzer.py --stdin --text-only
```

### Output as JSON

```bash
python quran_font_analyzer.py --text 'ك ک ي ی ہ' --text-only --format json
cat passage.txt | python quran_font_analyzer.py --stdin --text-only --format json
```

The text-only analysis reports:

- Character and distinct Unicode code-point counts.
- Unicode names and general categories for each character.
- Arabic-script, Latin, Bengali and other script counts.
- Perso-Arabic / Urdu-associated letters such as `ک`, `ہ`, `ۃ`, `ی`, `پ`, `چ`, `گ` and others.
- Side-by-side counts for Arabic `ك` versus Persian `ک`, Arabic `ي` versus Farsi `ی`, Arabic `ه` versus Urdu `ہ`, and Arabic `ة` versus Urdu `ۃ`.
- Arabic-Indic versus Persian-style digits.
- Arabic punctuation, Qur'anic signs, waqf marks, presentation forms and private-use characters.
- Diacritics, tatweel, zero-width joiner/non-joiner and Unicode normalization observations.
- An evidence-based text/orthography assessment.

The output describes code-point use. It does **not** infer the language merely from the presence of a few letters.

## 3. Generate a full report for your own text

Unlike text-only mode, these commands scan all font files and regenerate the full HTML/CSV/JSON/CSS report for that exact text.

```bash
python quran_font_analyzer.py --text-file my-hadith.txt --text-kind hadith
python quran_font_analyzer.py --text-file my-ayah.txt --text-kind quran
python quran_font_analyzer.py --text 'اللَّهُمَّ اغْفِرْ لَنَا' --label 'Dua sample'
cat my-ayah.txt | python quran_font_analyzer.py --stdin --text-kind quran
```

`--text-kind` accepts `auto`, `quran`, `hadith`, `arabic-prose` and `unknown`. It sets the context of the input; it does not claim that a text is Uthmani or Imla'i.

## 4. Distinguish Uthmani, Imla'i and IndoPak

The tool can observe signals, but **Unicode character clues alone cannot reliably certify an edition**.

For stronger identification, provide the same passage from a known edition in `reference_texts/`:

```text
reference_texts/
├── uthmani_2_255.txt
├── imlaei_2_255.txt
└── indopak_2_255.txt
```

Each reference file should contain the same passage and verse range as the supplied input. Filename prefixes determine the candidate type: `uthmani`, `imlaei`/`imlai`/`simple`, or `indopak`.

Then run:

```bash
python quran_font_analyzer.py --text-file my-ayah.txt --text-kind quran --reference-dir reference_texts
```

A near-exact normalized match is reported as a strong reference match. This is a similarity check, not scholarly authentication. Check the reference source and edition.

If the source already tells you its edition, you can record that explicitly:

```bash
python quran_font_analyzer.py --text-file my-ayah.txt --declared-layout uthmani
```

Accepted labels: `uthmani`, `imlaei`, `indopak`. This is recorded as source-declared, not inferred.

## 5. Generated files

The full report is written to `report-output/`:

| File | Purpose |
|---|---|
| `report.html` | Interactive report with detailed metadata for every detected font and live text specimens |
| `font_report.json` | Full machine-readable report, including all font metadata and cmap information |
| `text_analysis.json` | Text-only analysis as JSON |
| `font_inventory.csv` | One row per font with the key metadata and text-coverage results |
| `character_inventory.csv` | One row per character in the selected text |
| `font_unicode_ranges.css` | CSS `@font-face`/`unicode-range` declarations for detected fonts |

These files are overwritten on each full report run. Adding or removing a font automatically changes the next inventory and generated outputs.

## 6. Automated tests

```bash
python -m unittest discover -s tests -v
```

## Important interpretation rules

1. **Font metadata is not text metadata.** A font named Uthmani or Naskh does not prove that text rendered with it is Uthmani.
2. **Glyph count is not cmap count.** OpenType substitutions can access internal glyphs not mapped directly to Unicode.
3. **cmap coverage is not shaping quality.** GSUB/GPOS presence does not guarantee correct mark placement in every browser.
4. **Arabic script is not the same as Arabic language.** Perso-Arabic code points indicate encoded character choices; they do not prove the text is Urdu or Persian.
5. **IndoPak is not simply text containing Urdu letters.** It is a named Qur'anic text representation/edition convention. Compare the passage against a reference source.
6. **No Uthmani marker does not prove Imla'i.** Marks may have been stripped, the passage may be short, or the source may use another convention.
7. **Typeface and page layout differ.** Naskh/Nastaliq are typeface/script-style descriptions; 15-line/16-line page layouts need page and line positioning data.
8. **Font embedding flags are not a complete license assessment.** Read the embedded license and upstream terms before redistributing or web-hosting font files.

See `CLASSIFICATION-METHODOLOGY.md` for details.
