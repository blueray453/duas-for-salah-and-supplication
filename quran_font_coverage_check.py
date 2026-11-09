from fontTools.ttLib import TTFont
from PIL import ImageFont, features
from pathlib import Path

UTHMANI = [
"بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
"الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ",
"الرَّحْمَٰنِ الرَّحِيمِ",
"مَالِكِ يَوْمِ الدِّينِ",
"إِيَّاكَ نَعْبُدُ وَإِيَّاكَ نَسْتَعِينُ",
"اهْدِنَا الصِّرَاطَ الْمُسْتَقِيمَ",
"صِرَاطَ الَّذِينَ أَنْعَمْتَ عَلَيْهِمْ غَيْرِ الْمَغْضُوبِ عَلَيْهِمْ وَلَا الضَّالِّينَ",
]
INDOPAK = [
"بِسۡمِ اللّٰهِ الرَّحۡمٰنِ الرَّحِيۡمِ",
"اَلۡحَمۡدُ لِلّٰهِ رَبِّ الۡعٰلَمِيۡنَۙ",
"الرَّحۡمٰنِ الرَّحِيۡمِۙ",
"مٰلِكِ يَوۡمِ الدِّيۡنِؕ",
"اِيَّاكَ نَعۡبُدُ وَاِيَّاكَ نَسۡتَعِيۡنُؕ",
"اِهۡدِنَا الصِّرَاطَ الۡمُسۡتَقِيۡمَۙ",
"صِرَاطَ الَّذِيۡنَ اَنۡعَمۡتَ عَلَيۡهِمۡ ۙ غَيۡرِ الْمَغۡضُوۡبِ عَلَيۡهِمۡ وَلَا الضَّآلِّيۡنَ",
]
fonts = {
'Amiri': '/usr/share/fonts/opentype/fonts-hosny-amiri/Amiri-Regular.ttf',
'Amiri Quran': '/usr/share/fonts/opentype/fonts-hosny-amiri/AmiriQuran.ttf',
'Amiri Quran Colored': '/usr/share/fonts/opentype/fonts-hosny-amiri/AmiriQuranColored.ttf',
'Noto Naskh Arabic': '/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf',
'Noto Nastaliq Urdu': '/usr/share/fonts/truetype/noto/NotoNastaliqUrdu-Bold.ttf',
'Noto Kufi Arabic': '/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf',
}

def chars(lines): return sorted({c for line in lines for c in line if not c.isspace()})
for script, lines in [('UTHMANI', UTHMANI), ('INDOPAK', INDOPAK)]:
    cs=chars(lines)
    print(f'==== {script}; {len(cs)} distinct non-space characters; RAQM={features.check("raqm")}')
    for name,path in fonts.items():
        ft=TTFont(path)
        cmap=ft.getBestCmap()
        missing=[c for c in cs if ord(c) not in cmap]
        tables=ft.keys()
        upm=ft['head'].unitsPerEm
        space_glyph=cmap.get(0x20)
        adv=ft['hmtx'][space_glyph][0]/upm if space_glyph and space_glyph in ft['hmtx'].metrics else None
        colors=[t for t in ('COLR','CPAL','SVG ') if t in tables]
        print(f'  {name:22s} missing {len(missing):2d}:', ' '.join(f'U+{ord(c):04X}' for c in missing) or '-', f'space={adv:.3f}em' if adv is not None else 'space=n/a', f'color_tables={colors}')
print('--- required marker checks ---')
for name,path in fonts.items():
    cm=TTFont(path).getBestCmap()
    print(f'{name:22s}', {h:(ord(c) in cm) for h,c in [('06DD','\u06DD'),('FD3E','\uFD3E'),('FD3F','\uFD3F'),('0661','\u0661'),('06F1','\u06F1')]})
