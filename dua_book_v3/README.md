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
```

WeasyPrint needs the Pango library:
* Linux: usually present. Otherwise `sudo apt install libpango-1.0-0 libpangoft2-1.0-0`
* macOS: `brew install pango`
* Windows: see https://doc.courtbouillon.org/weasyprint/stable/first_steps.html (WSL is the easiest route)

All fonts are bundled in `fonts/`; nothing needs installing system-wide.

## Options

| Command | What it does |
|---|---|
| `--data FILE` | Input file. `.json` or `.md`, detected by extension |
| `--out FILE` | Output PDF path (default `output/book.pdf`) |
| `--to-json FILE` | Also save the loaded data as JSON (convert Markdown to JSON) |
| `--grid inline` | Use the inline-block word grid instead of flexbox (same look, most predictable) |
| `--lang en` | Show only these translation languages, e.g. `en` or `en,bn` |
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

## Customising the look

* `templates/style.css`: colours are the four variables at the top (`--ink`, `--accent`, `--line`, `--tint`).
* `assets/logo.svg`: replace with your own logo (cover and footer).
* The cover artwork is a placeholder SVG inside `templates/book.html`. Replace it with your own.

## Project layout

```
build.py            entry point (loads JSON or Markdown, renders, writes the PDF)
md_parser.py        Markdown -> data converter
data/book.json      sample data (JSON)
data/book.md        the same sample data (Markdown)
templates/          book.html (Jinja2 structure) + style.css (look)
fonts/ assets/      bundled fonts and the logo
tests/              python tests/test_parser.py  (checks book.md == book.json)
output/             generated PDFs go here
```

## Important: the sample data

The sample duas are **layout samples only**. Verify every Arabic text, word gloss, translation and
reference against a trusted source (and have a knowledgeable person proofread) before publishing.

## Fonts (all open licence)

Amiri, Poppins, Noto Serif and Noto Sans Bengali (SIL Open Font License), bundled in `fonts/`.
