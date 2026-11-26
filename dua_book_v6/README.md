# Dua Book Builder (WeasyPrint)

Builds a PDF with a cover, table of contents (real page numbers), running header/footer,
page-number badges and a right-to-left **word-by-word grid** (Arabic on top, meaning below).

Content comes from **JSON or Markdown** (your choice, same result). Layout lives in `templates/`.

```
data/book.json ─┐
                ├─►  build.py  ─►  output/book.pdf
data/book.md  ──┘      (md_parser.py reads Markdown)
```

## Run it

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python build.py                          # JSON (default)  -> output/book.pdf
python build.py --data data/book.md      # Markdown        -> output/book.pdf
python build.py --style bw               # black & white   -> output/book-bw.pdf
python build.py --style both             # colour + B&W in one go
```

WeasyPrint needs the Pango library:
* Linux: usually present. Otherwise `sudo apt install libpango-1.0-0 libpangoft2-1.0-0`
* macOS: `brew install pango`
* Windows: see https://doc.courtbouillon.org/weasyprint/stable/first_steps.html (WSL is the easiest route)

All fonts are bundled in `fonts/`; nothing needs installing system-wide.

## From `duas.adoc` to PDF

```bash
python adoc_to_json.py data/duas.adoc --out data/duas.json    # 1. adoc -> JSON
python build.py --data data/duas.json                         # 2. JSON -> output/book.pdf
python build.py --data data/duas.json --style both            #    colour + black & white
```

What the converter and template do with your adoc:

* **Contents page** lists every section (`==`), sub-section (`===`) and sub-sub-section (`====`) with page numbers.
  Sections become numbered chapters (1, 2, 3 ...), duas are numbered 4.1, 4.2 ... inside their chapter,
  and the running header shows the current chapter name.
* **References** are expanded with the same abbreviation list as `abbreviation-replacer.js`
  (`SAB 744` -> *Sahih al-Bukhari 744*, `(T)` -> *(Tahajjud)*, `(N)` -> *(Nafl Prayer)*) and grouped per book.
  The `.Title` lines (context, grading) are shown above the sources, long commentary below them in small
  type, and URLs as a list of links. To change the list, edit `SOURCES` in `adoc_to_json.py`.
* **Word-by-word**: rows that carry a transliteration `ar (translit) - bn` are shown as single words with the
  transliteration under the Arabic; the phrase row that follows them (`ar - bn - en`) is shown as the
  meaning of that phrase under the grid. Separators `-`, en dash and em dash are all understood.
* Duas without word-by-word data show the plain Arabic text (Quran verses use the Amiri Quran font).
* `NOTE:` lines under a heading become a note box under that heading; other `NOTE:` lines go above the dua.
* `--layout page` puts every dua on its own page instead of letting them flow inside a chapter.
* `cover.jpg` in `assets/` is used as the full-bleed cover of the colour book; the black & white book
  uses the line-art cover so it prints cleanly.

## Options

| Command | What it does |
|---|---|
| `--data FILE` | Input file. `.json` or `.md`, detected by extension |
| `--out FILE` | Output PDF path (default `output/book.pdf`, or `output/book-bw.pdf` for `--style bw`) |
| `--style color\|bw\|both` | `color` (default), `bw` = black & white print version, `both` = build both. With `both --out x.pdf` you get `x.pdf` and `x-bw.pdf` |
| `--to-json FILE` | Also save the loaded data as JSON (convert Markdown to JSON) |
| `--grid inline` | Use the inline-block word grid instead of flexbox (same look, most predictable) |
| `--lang en` | Show only these translation languages, e.g. `en` or `en,bn` |
| `--layout flow\|page` | `flow` (default): duas follow each other inside a chapter. `page`: one dua per page |
| `--keep-html` | Also save the intermediate HTML next to the PDF (debugging only) |

## Markdown format

```markdown
---
title: Dua in the Morning & Evening
subtitle: Word by Word
tagline: Supplication from Quran and Authentic Hadith
org: Your Organisation
languages: [en, bn]
---

## Bismillah

> Intro text shown in a note box.
> bn: Bangla version of the intro.

| بِسْمِ | ٱللَّهِ | ٱلرَّحْمَـٰنِ | ٱلرَّحِيمِ |
|---|---|---|---|
| In the name | of Allah | the Most Gracious | the Most Merciful |
| নামে | আল্লাহর | পরম করুণাময় | অসীম দয়ালু |

en: Translation of the line above.
bn: Bangla translation.

ref: Quran 1:1

# About Your Organisation
Paragraph text.
- Website: https://example.org
note: FOR FREE DISTRIBUTION ONLY | NOT FOR SALE
```

| In Markdown | Becomes |
|---|---|
| Front matter between `---` lines | Book metadata: `title`, `subtitle`, `tagline`, `running_title`, `org`, `lang`, `languages` |
| `## Heading` | One dua: its own page, auto-numbered 1.1, 1.2, ... |
| `>` lines | Intro note box. `bn:` (any declared language) lines inside add other languages |
| A table | One word grid. **Row 1 = Arabic words** (reading order), **next rows = glosses**, in the order of `languages` |
| `en:` / `bn:` lines after a table | Translation of the table above them |
| `ref:` | Reference line |
| `# Heading` (single `#`) | The About page. `- Label: url` lines become links, `note:` is the footer note |
| `<!-- comment -->` | Ignored |

Rules and tips:
* **Column order is reading order.** First column = first word. Some editors display Arabic cells
  right to left, which can look reversed; the PDF preview is the real check.
* A dua can have several table + translation blocks one after another.
* Every gloss row needs the **same number of cells** as the Arabic row. If not, you get a
  warning with the file and line number, and the row is padded or trimmed.
* Warnings are printed for anything the parser ignores (stray text, translation before a table,
  empty sections, ...). Fatal problems (unclosed front matter, no `##` sections) stop the build.
* Don't put a `|` character inside a table cell.

## JSON format (`data/book.json`)

```json
{
  "meta":      { "title": "...", "subtitle": "...", "tagline": "...",
                 "running_title": "header text", "org": "footer text", "lang": "en" },
  "languages": ["en", "bn"],
  "duas": [
    {
      "title": "Morning Dua",
      "intro": { "en": "optional note box", "bn": "..." },
      "lines": [
        {
          "words": [ { "ar": "ٱللَّهُمَّ", "en": "O Allah", "bn": "হে আল্লাহ" } ],
          "translation": { "en": "full translation of this line", "bn": "..." }
        }
      ],
      "reference": "Sunan at-Tirmidhi 3391"
    }
  ],
  "about": { "heading": "...", "text": "...", "links": [ { "label": "Website", "url": "https://..." } ],
             "footer_note": "..." }
}
```

Add another language (for example `"ur"`) by adding its key to the words/translations and to
`"languages"`, then add a font and `.tr-ur` / `.g-ur` rules in `templates/style.css`.
In Markdown, add it to `languages: [...]` and add one gloss row per language.

## Black & white print style

`python build.py --style bw` makes a version designed for mono printers, not just a greyscale
conversion of the colour one:

* pure black text on white paper (no brown, no tints)
* no tinted fills: note boxes are outlined with a thick left bar, because light fills print as dirty halftone dots
* solid black hairlines instead of light-grey ones, which break up when printed
* outlined page-number badges instead of solid blocks, and a line-art cover instead of a full-page
  gradient. In the sample this cut total ink use by about 60%, almost all of it from the cover.
* uses `assets/logo-bw.svg` (a black version of the logo) in the footer and on the cover

Tips: it's still a vector PDF, so print at **100% / Actual size**; choose the printer's greyscale or
black-only mode if you want to be sure no colour toner is used. Replace **both** `assets/logo.svg`
and `assets/logo-bw.svg` with your own logo. The B&W rules live in `templates/style-bw.css`
(it is loaded after `style.css`, so anything in it overrides the colour style).

## Customising the look

* `templates/style.css`: the palette is sampled from `assets/cover.jpg` and lives in the variables at the
  top (`--ink`, `--accent`, `--leaf`, `--sage`, `--line`, `--tint`, `--paper`).
* `assets/logo.svg` and `assets/logo-bw.svg`: replace with your own logo (colour and black versions).
* The cover artwork is a placeholder SVG inside `templates/book.html`. Replace it with your own.

## Project layout

```
build.py            entry point (loads JSON or Markdown, renders, writes the PDF)
md_parser.py        Markdown -> data converter
data/book.json      sample data (JSON)
data/book.md        the same sample data (Markdown)
templates/          book.html (Jinja2 structure), style.css (colour look), style-bw.css (B&W overrides)
fonts/ assets/      bundled fonts and the logo
tests/              python tests/test_parser.py  (checks book.md == book.json)
output/             generated PDFs go here
```

### Extra JSON fields used by the adoc data

`section`, `subsection`, `subsubsection` on a dua (chapter structure), `source_type` (`quran` / `hadith`),
`heading_notes`, `transliteration`; on a line: `text` (plain Arabic instead of a word grid) and `phrase`
(`{"en": ..., "bn": ...}` meaning of the words above it); on a word: `tr` (transliteration);
and `reference` as an object:

```json
"reference": {
  "labels":   [{"text": "Weak", "lang": "en"}],
  "sources":  [{"name": "Sahih al-Bukhari", "abbr": "SAB", "numbers": ["7499", "1120"]}],
  "other":    ["Muwatta Malik Book 51, Hadith 1743 (No Grade)"],
  "comments": [{"text": "...", "lang": "en"}],
  "links":    ["https://..."]
}
```

A plain string `"reference": "Quran 1:1"` still works (used by the Markdown samples).

## Important: the sample data

The sample duas are **layout samples only**. Verify every Arabic text, word gloss, translation and
reference against a trusted source (and have a knowledgeable person proofread) before publishing.

## Fonts (all open licence)

Amiri, Poppins, Noto Serif and Noto Sans Bengali (SIL Open Font License), bundled in `fonts/`.
