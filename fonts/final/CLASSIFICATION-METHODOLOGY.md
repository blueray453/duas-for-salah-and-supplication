# Text classification: what can and cannot be inferred

The analyzer intentionally does not equate a Unicode character profile with a complete orthographic edition label.

## 1. What the script can identify directly

It can report the actual Unicode code points used in a sample, their Unicode names, counts, and associated script blocks. For this project it highlights code points often associated with Perso-Arabic/Urdu/Persian writing, such as:

- U+06A9 KEHEH (`ک`)
- U+06CC FARSI YEH (`ی`)
- U+06C1 HEH GOAL (`ہ`)
- U+06C3 TEH MARBUTA GOAL (`ۃ`)
- U+06F0–U+06F9 EXTENDED ARABIC-INDIC DIGITS (`۰`–`۹`)
- U+06D4 ARABIC FULL STOP (`۔`)

These observations describe encoded characters. They do not by themselves identify the language: Arabic prose may have been copied from a site using extended Perso-Arabic spellings, and individual characters such as Farsi Yeh can occur in several languages/contexts. The report therefore says “Perso-Arabic / Urdu-associated code points” rather than “this is Urdu”.

The script also identifies selected Qur'anic marks, pause symbols, and Uthmani-associated code points. These are clues, not proof of a particular Mushaf edition.

## 2. What needs a source/reference comparison

The labels Uthmani, Imla'i/Simple and IndoPak identify different Qur'anic text representations. Quran Foundation exposes them as separate text fields (`text_uthmani`, `text_imlaei`, `text_indopak_nastaleeq`), which is evidence that they should not be reduced to one font or one Unicode-block test.

For a text to be identified against those labels, provide the same passage in a known edition:

- `uthmani*.txt`
- `imlaei*.txt`, `imlai*.txt`, or `simple*.txt`
- `indopak*.txt`

The analyzer compares the input to each matching file after NFC normalisation and removal of whitespace/tatweel. A near-exact sequence match is reported as a strong match. This is an engineering comparison, not a scholarly certification; verify the provenance, recitation and edition of the reference text.

Alternatively, use `--declared-layout` when the source itself already tells you which text edition it is. The report clearly labels this as source-declared rather than inferred.

## 3. Why character heuristics are not enough

- A text can omit Uthmani-specific signs because it is a clean/simple form, because diacritics were removed, or because it is only a short fragment. Absence does not prove Imla'i.
- IndoPak Quran text is not synonymous with text that merely contains Urdu letters. It has a separately defined text representation and rendering requirements.
- A font called “Uthmanic” or “IndoPak” describes a font/product. It does not establish how a text was sourced or encoded.
- Naskh and Nastaliq are visual typeface/calligraphic styles, not orthography labels.
- A 15-line/16-line printed Mushaf layout requires page boundaries and word/line placement data, not just the text string.

## 4. Hadith prose

Uthmani and Imla'i are relevant when comparing Qur'anic text representations. For a hadith or dua, the analyzer reports Arabic/Perso-Arabic encoding features and font coverage, but marks the Qur'anic edition classification as not applicable unless the user explicitly supplies source metadata.
