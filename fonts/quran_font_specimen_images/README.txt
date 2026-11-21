Qur’anic font specimen images

These PNG images are rendered directly from the exact font files supplied in the original project, using Pillow with RAQM Arabic shaping. Each specimen uses a single explicit font binary. No browser or operating-system font-family fallback is used.

Files:
- font_comparison_page_1.png ... : detailed comparison pages (four fonts per page)
- pause_glyphs_all_arabic_fonts.png : seven pause/Saktah glyph strip per Arabic-capable font
- individual/ : full-size image per Arabic-capable font
- manifest.json : coverage and image manifest

The seven sample lines are actual verse excerpts already stored in the project’s samples/madinah_pause_examples.txt: six Madinah pause-mark classes and one Hafs Saktah example. The repeated-word line is a synthetic typography test only, not Qur’anic wording. The final Arabic line tests the ﷺ honorific (U+FDFA).

Important: if a font does not map a particular pause sign, the image shows that font’s missing-glyph replacement rather than borrowing the symbol from another font. This is deliberate: it prevents fallback from hiding font deficiencies. The coverage status is printed in each specimen card.

The images are a fixed visual record; they do not replace live HTML text for browser testing, accessibility, search, selection, or responsive layout.
