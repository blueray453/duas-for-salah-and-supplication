# Classification methodology (v1.2)

The analyzer treats the following as independent dimensions. A label in one dimension must not be copied into another.

| Dimension | Examples | How the analyzer determines it |
|---|---|---|
| Orthography / text representation | Uthmani, Imla'i/Simple, IndoPak | Source declaration or strong same-passage reference match; character signals are only clues |
| Riwayah | Hafs, Warsh, Qalun, Shu'bah, Al-Duri | Source declaration or reference metadata; not inferred from generic diacritics |
| Script tradition | Madani/Uthmani, IndoPak, Maghribi, QPC Nastaleeq | Source/edition reference or explicit source metadata; Perso-Arabic letters alone do not prove IndoPak |
| Typeface / calligraphic style | Naskh, Nastaleeq, Kufi, Thuluth, Maghribi | Embedded font names/filename indicators or user-supplied typeface metadata; not a text property |
| Digital encoding model | Unicode text, IndoPak Unicode, QPC glyph code V1/V2 | Source field/metadata, explicit command option, or a cautious private-use code-point signal |
| Mushaf page layout | QCF V1/V2, Madani, IndoPak 15-line/16-line | Mushaf ID or source-supplied page/line data; cannot be inferred from prose alone |

## 1. Direct Unicode observations

The analyzer reports actual code points, names, counts and selected pairs such as:

- Arabic Kaf `ك` U+0643 vs Persian/Urdu Keheh `ک` U+06A9.
- Arabic Yeh `ي` U+064A vs Farsi Yeh `ی` U+06CC.
- Arabic Heh `ه` U+0647 vs Urdu Heh Goal `ہ` U+06C1.
- Arabic Teh Marbuta `ة` U+0629 vs Urdu Teh Marbuta Goal `ۃ` U+06C3.

These are character-encoding observations. They do not establish a text's language, geographic origin or Qur'anic edition. For example, Arabic prose copied from a South Asian website may use Urdu-associated code points while the language remains Arabic.

The script also reports Arabic/Persian digits, Arabic punctuation, combining marks, Qur'anic/waqf annotations, presentation forms, private-use characters, tatweel, ZWJ/ZWNJ and Unicode normalization changes.

## 2. Orthography / text representation

Tanzil documents two general Qur'an text formats: Uthmani and Simple (also called Imla'ei). Quran Foundation separately exposes fields including `text_uthmani`, `text_uthmani_simple`, `text_imlaei`, `text_imlaei_simple`, `text_indopak_nastaleeq`, `text_qpc_hafs`, `text_qpc_nastaleeq`, `text_qpc_nastaleeq_hafs`, and deprecated aliases.

The tool does not infer Imla'i merely because it did not find an Uthmani-associated code point. Mark stripping, text normalization, a short excerpt or an alternate representation can remove the expected signal.

## 3. Reference matching

Place same-passage UTF-8 files in `reference_texts/`. `manifest.json` can record all the dimensions and source provenance. Filename-based metadata parsing is a fallback only.

Recommended manifest fields:

- `file`
- `orthography`
- `riwayah`
- `script_tradition`
- `typography`
- `encoding_model`
- `page_layout`
- `mushaf_id`
- `line_count`
- `page_count`
- `qf_field`
- `source`, `source_url`

The strict comparison applies NFC, removes whitespace and tatweel, and preserves diacritics, annotation characters, punctuation and letter variants. Exact input/reference equality and exact substring matches are strong matches. Fuzzy sequence matching is shown but only accepted as strong under a very high similarity and comparable-length condition. A base-letter-only similarity is diagnostic and never triggers a classification.

A match indicates similarity to the supplied local reference. It does not authenticate the reference's publisher, edition, riwayah or scholarly accuracy. Verify the file provenance independently.

## 4. Riwayah

Hafs, Warsh, Qalun and other riwayat describe transmission/recitation. Some variants have different readings and textual indications, but a general Unicode sample cannot establish which transmission it represents. The analyzer therefore requires source-declared data or a strong match to a labelled reference for automatic reporting.

## 5. Script tradition versus typography

Madani, IndoPak and Maghribi are script/edition traditions. Naskh, Nastaleeq, Kufi, Thuluth and similar labels describe typeface/calligraphic style. A Nastaleeq font does not turn an arbitrary text into an IndoPak Qur'an edition. A font whose name includes “Uthmani” does not prove the supplied text uses Uthmani orthography.

Per-font typography/product labels are taken only from filename and embedded OpenType name strings. The report describes them as metadata indicators. Actual visual classification should include rendering and visual review.

## 6. Unicode text versus QPC glyph codes

Quran Foundation distinguishes Unicode text fields from QPC glyph-code fields such as `code_v1` and `code_v2`. Glyph-code content is not an ordinary Unicode verse string; it must be interpreted with its corresponding code/font system. Private-use characters in an input are a warning signal for a custom mapping, but they do not identify which mapping without the relevant source metadata.

The field map also records that `text_indopak_nastaleeq` must be rendered with a compatible IndoPak Nastaleeq font. The Quran Foundation font-rendering guide warns that generic fonts may not correctly render the IndoPak waqf and verse-end markers.

## 7. Mushaf IDs and page layout

The built-in Mushaf ID catalogue reflects the Quran Foundation Pages Lookup API guide checked on 2026-11-23. In particular, IDs 6 and 7 are IndoPak 15-line and 16-line resources. Other IDs identify QCF V1/V2, IndoPak, Uthmani Hafs, KFGQPC Hafs and Tajweed resources.

Page/line layout is not encoded in a continuous Arabic paragraph. Use a Mushaf ID, line count/page count, or word-level page and line positions. The static catalogue is a convenience map; confirm it against the API documentation in the application version being integrated.

## 8. Hadith and Arabic prose

Uthmani/Imla'i/IndoPak are Qur'anic text/edition labels. For hadith and ordinary Arabic prose, the analyzer marks Qur'anic orthography/riwayah/script-tradition as not applicable unless source metadata is explicitly supplied. It still reports Perso-Arabic-associated character choices, punctuation, diacritics and font coverage.

## 9. Font metadata is not rendered-font proof

The selected font's name-table metadata may identify a family/style, but browser fallback may display missing characters from another font. `--font-for-text` associates a specific font file with the report; it does not prove the browser used that font for every glyph. Verify rendering in-browser with fallback controlled, especially for Arabic combining marks and Quranic annotations.


## Quran Foundation source-field declarations

`--qf-field` records the exact Quran Foundation field used for the text. It is not a heuristic. The analyzer maps documented fields such as `text_uthmani`, `text_imlaei`, `text_indopak_nastaleeq`, `text_qpc_hafs`, `text_qpc_nastaleeq`, `text_qpc_nastaleeq_hafs`, `code_v1` and `code_v2` to only the dimensions supported by the field documentation. Dimensions not implied by that field remain unknown.

For example, `text_indopak_nastaleeq` supports an IndoPak orthography/script-tradition label and Nastaleeq typography; `code_v2` identifies the QPC glyph-code V2 encoding model but does not, by itself, prove a riwayah or typeface. The field reference and font-rendering guide should be checked when upstream API definitions change.

Digital Khatt V1/V2/IndoPak are recorded as source-declared encoding/rendering models when supplied explicitly. Their presence cannot be detected from ordinary Unicode text alone.
