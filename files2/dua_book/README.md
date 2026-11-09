# Dua Book Builder (WeasyPrint)

Builds a PDF with a cover, table of contents (real page numbers), running header/footer,
page-number badges and a right-to-left **word-by-word grid** (Arabic on top, meaning below).
Content lives in `data/book.json`; layout lives in `templates/`.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python build.py                      # -> output/book.pdf
```

WeasyPrint needs the Pango library:
* Linux: usually present. Otherwise `sudo apt install libpango-1.0-0 libpangoft2-1.0-0`
* macOS: `brew install pango`
* Windows: follow https://doc.courtbouillon.org/weasyprint/stable/first_steps.html (WSL is the easiest route)

All fonts are bundled in `fonts/`, so nothing needs installing system-wide.

## Options

| Command | What it does |
|---|---|
| `python build.py --grid inline` | Use the inline-block word grid instead of flexbox (same look, most predictable) |
| `python build.py --lang en` | English only (hides Bangla). Default comes from `"languages"` in the JSON |
| `python build.py --data my.json --out my.pdf` | Use another data file / output path |
| `python build.py --keep-html` | Also save `output/book.html` so you can open it in a browser and inspect |

## Data format (`data/book.json`)

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

* List `words` in **reading order** (first word first). The grid places the first word on the right.
* `lines` lets you alternate: word grid, translation, word grid, translation...
* Each dua starts on a new page and is numbered `1.1`, `1.2`, ... automatically.
* Add a language by adding its key (for example `"ur"`) to words/translations and to `"languages"`,
  then add a font and a `.tr-ur` / `.g-ur` rule in `templates/style.css`.

## Customising the look

* `templates/style.css`: colours are the four variables at the top (`--ink`, `--accent`, `--line`, `--tint`).
* `assets/logo.svg`: replace with your own logo (used on the cover and in the footer).
* The cover artwork is a simple placeholder SVG inside `templates/book.html`. Replace it with your own artwork.

## Important: the sample data

`data/book.json` is **sample data to test the layout only**. Verify every Arabic text, word gloss,
translation and reference against a trusted source (and have a knowledgeable person proofread)
before publishing anything.

## Fonts (all open licence)

Amiri, Poppins, Noto Serif and Noto Sans Bengali (SIL Open Font License), bundled in `fonts/`.
