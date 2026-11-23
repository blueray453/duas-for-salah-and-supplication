# Source references

The analyzer itself runs offline. It does not download Quran text or call Quran Foundation APIs. The links below document the model used in the report and were checked on 2026-11-23.

1. **Tanzil — Quran Text Types**  
   https://tanzil.net/docs/quran_text_types  
   Describes Uthmani and Simple/Imla'ei as separate Qur'an text formats.

2. **Quran Foundation — Field Reference**  
   https://api-docs.quran.foundation/docs/api/field-reference/  
   Lists verse/word fields including `text_uthmani`, `text_uthmani_simple`, `text_imlaei`, `text_imlaei_simple`, `text_indopak_nastaleeq`, `text_qpc_hafs`, `text_qpc_nastaleeq`, `text_qpc_nastaleeq_hafs`, the deprecated `qpc_uthmani_hafs` alias, and the deprecated `text_indopak` field.

3. **Quran Foundation — Font Rendering**  
   https://api-docs.quran.foundation/docs/tutorials/fonts/font-rendering/  
   Explains QPC glyph-code rendering, Unicode font rendering and the compatible font requirement for `text_indopak_nastaleeq`. Also documents word character types such as `word`, `end`, `pause`, `sajdah` and `rub-el-hizb`.

4. **Quran Foundation — Page Layout API Guide**  
   https://api-docs.quran.foundation/docs/tutorials/fonts/page-layout/  
   Documents Mushaf ID examples including QCF V1/V2, IndoPak, Uthmani Hafs, KFGQPC Hafs, IndoPak 15-line and 16-line, Tajweed and QCF Tajweed V4. It also explains page/line position data.

5. **Quran Foundation — FAQ / Content Sync**  
   https://api-docs.quran.foundation/docs/tutorials/faq/  
   Describes `quran_core` fields and the compatibility requirements of the IndoPak Nastaleeq rendering font.

6. **Unicode — Arabic Names List**  
   https://www.unicode.org/Public/UCD/latest/ucd/NamesList.txt  
   Reference for code point names and Arabic-script character identities.

## Implementation boundary

- The field names and Mushaf ID catalogue are source-documentation references, not a runtime API guarantee. Recheck the API docs/version before an integration.
- Local reference matching compares text sequences. It does not validate a reference's authority or edition.
- Font metadata comes directly from supplied font binaries. Filename/name-table typography labels are not visual proofs.
- A text's orthography, riwayah, script tradition, font style, encoding model and page layout are separate properties.
