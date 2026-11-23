# Font licensing notes

The font binaries in this project were supplied for local analysis. Their presence in this project does not grant a license to redistribute, re-host, subset, modify, or commercially use them.

The analyzer extracts embedded name-table copyright and license fields, license URLs, and `OS/2.fsType` embedding flags when present. These are informational metadata, not a legal determination. Missing metadata does not mean that a font is public domain or freely redistributable.

## Newly added archive fonts

### `UthmanTN1.otf`

The embedded font metadata identifies:

- Family: KFGQPC Uthman Taha Naskh
- Style: Regular
- Version: 0.10
- Designer: Ashfaq Ahmad Niazi
- Manufacturer: IT Department
- Vendor URL: `http://fonts.qurancomplex.gov.sa`

The font embeds an Electronic End-User License Agreement attributed to King Fahd Glorious Quran Printing Complex. It states that use, copying and distribution are permitted free of cost subject to the agreement, and prohibits modification, alteration, reverse engineering and related activities. Read the complete embedded `name` table license text in the generated HTML/JSON before redistributing this file.

### `fontawesome-webfont.woff2`

The embedded metadata identifies FontAwesome Regular, version 4.6.3, designer Dave Gandy, manufacturer Fort Awesome, with license URL `http://fontawesome.io/license/`. This font is an icon font and has no Arabic-block cmap coverage in the supplied binary. Consult the license applicable to this exact Font Awesome version before redistribution.

## Previously supplied reference font

### `font-arabic2.woff2`

The embedded metadata identifies Adobe Arabic Regular. Consult Adobe's current font licensing terms: https://www.adobe.com/type/legal.html. A copy served from a public CDN does not itself establish permission to redistribute or self-host the font.

## General guidance

Before public deployment or sharing font binaries, check each font's official upstream source and license. The metadata report includes the fields the font embeds, but cannot establish the legal status of a font where those fields are incomplete or ambiguous.
