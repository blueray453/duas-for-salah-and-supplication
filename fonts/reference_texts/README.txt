Add UTF-8 text files here. Each file should contain the same passage/range as the input being analyzed.

Recommended: create manifest.json with a "references" list. Each object can include:
  file, orthography, riwayah, script_tradition, typography, encoding_model,
  page_layout, mushaf_id, line_count, page_count, qf_field, source, source_url.

See manifest.example.json for a template. Use only source/edition metadata that you have verified.

Filename fallback conventions include:
  uthmani_hafs_madani.txt
  imlaei_hafs.txt
  indopak_hafs_nastaleeq_16_lines.txt
  qpc_glyph_v2_hafs.txt

The analyzer compares the actual text sequence, preserving diacritics, annotations and edition-specific character distinctions. A matching reference must be the same passage. Similarity is not scholarly authentication.
