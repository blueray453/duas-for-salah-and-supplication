from PIL import Image, ImageDraw, ImageFont, features
from pathlib import Path
import json, math

# Resolve all paths relative to this script, not the machine that created it.
SCRIPT_DIR = Path(__file__).resolve().parent


def find_project_root(start: Path) -> Path:
    candidates = [start, *list(start.parents)[:4]]
    for candidate in candidates:
        if (candidate / 'font_audit.json').is_file():
            return candidate
    raise SystemExit(
        'Could not find font_audit.json. Put render_specimens.py in the project '
        'root or in its fonts/ subfolder, and keep font_audit.json in the project root.'
    )


ROOT = find_project_root(SCRIPT_DIR)
_audit_preview = json.loads((ROOT / 'font_audit.json').read_text(encoding='utf-8'))
_expected_font_names = [item['filename'] for item in _audit_preview.get('fonts', [])]
_font_dir_candidates = [SCRIPT_DIR, ROOT, ROOT / 'fonts']
FONT_DIR = max(
    _font_dir_candidates,
    key=lambda folder: sum((folder / name).is_file() for name in _expected_font_names),
)


def font_path_for(font_record):
    filename = font_record['filename']
    path = FONT_DIR / filename
    if not path.is_file():
        raise SystemExit(
            f'Missing font file: {filename}\n'
            f'Looked in: {FONT_DIR}\n'
            'Keep the supplied font binaries together in the fonts directory.'
        )
    return path


# Create output beside this script. No /mnt/data path is used.
OUT = SCRIPT_DIR / 'quran_font_specimen_images'
OUT.mkdir(parents=True, exist_ok=True)
INDIV = OUT / 'individual'
INDIV.mkdir(parents=True, exist_ok=True)


def ui_font(size, bold=False):
    candidates = [
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
        Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


if not features.check('raqm'):
    raise SystemExit('Pillow was installed without libraqm. Reinstall Pillow with RAQM support for Arabic shaping.')

audit = _audit_preview
fonts = [f for f in audit['fonts'] if f.get('arabic_count', 0) > 0]

# Verified verse excerpts already included in the project source, preserving their source text.
examples = [
    ('36:76 · Compulsory pause · U+06D8', 'فَلَا يَحْزُنكَ قَوْلُهُمْ ۘ إِنَّا نَعْلَمُ مَا يُسِرُّونَ وَمَا يُعْلِنُونَ'),
    ('16:57 · Impermissible pause · U+06D9', 'وَيَجْعَلُونَ لِلَّـهِ الْبَنَاتِ سُبْحَانَهُ ۙ وَلَهُم مَّا يَشْتَهُونَ'),
    ('2:45 · Permissible pause · U+06DA', 'وَاسْتَعِينُوا بِالصَّبْرِ وَالصَّلَاةِ ۚ وَإِنَّهَا لَكَبِيرَةٌ إِلَّا عَلَى الْخَاشِعِينَ'),
    ('16:17 · Pause preferred · U+06D7', 'أَفَمَن يَخْلُقُ كَمَن لَّا يَخْلُقُ ۗ أَفَلَا تَذَكَّرُونَ'),
    ('16:21 · Continuation preferred · U+06D6', 'أَمْوَاتٌ غَيْرُ أَحْيَاءٍ ۖ وَمَا يَشْعُرُونَ أَيَّانَ يُبْعَثُونَ'),
    ('2:2 · Interchangeable pause pair · U+06DB', 'ذَٰلِكَ الْكِتَابُ لَا رَيْبَ ۛ فِيهِ ۛ هُدًى لِّلْمُتَّقِينَ'),
    ('18:1 · Hafs Saktah · U+06DC', 'عِوَجَاۜ'),
]

# All signs displayed together as a glyph stress line. Explicitly marked as synthetic, not Qur'anic text.
fixture_label = 'Glyph stress line · typography test only (not Qur’anic wording)'
fixture = 'بَابٌۖ  بَابٌۗ  بَابٌۘ  بَابٌۙ  بَابٌۚ  بَابٌۛ  بَابٌۜ'
honorific_label = 'Honorific test · U+FDFA'
honorific = 'رَسُولُ اللَّهِ ﷺ'

# Use the font binary alone. Pillow/RAQM does not perform browser/OS font-family fallback.
FONT_SIZE = 34
SMALL_SIZE = 18
LABEL_SIZE = 18
BG = (250, 248, 242)
CARD = (255, 255, 252)
INK = (30, 32, 35)
SUB = (92, 94, 99)
LINE = (222, 220, 212)
GOOD = (30, 112, 75)
WARN = (160, 95, 20)
BAD = (160, 55, 55)


def safe_font(path, size):
    return ImageFont.truetype(str(path), size=size, layout_engine=ImageFont.Layout.RAQM)


def cp_missing(font_path, cps):
    # cmap coverage from project audit, independent of rendering fallback
    t = next(x for x in fonts if x['filename'] == font_path.name)
    have = set()
    # Recover exact cmap from JSON ranges.
    for a,b in t.get('ranges', []):
        have.update(range(a,b+1))
    return [cp for cp in cps if cp not in have]

waqf_cps = audit['madani_waqf_codepoints']
saktah_cp = audit['saktah_codepoints'][0]
honorific_cp = audit['honorific_codepoint']

# Render each font in an individual high-resolution specimen image.
records=[]
for f in fonts:
    path = font_path_for(f)
    font = safe_font(path, FONT_SIZE)
    font_small = safe_font(path, SMALL_SIZE)
    label_font = ui_font(LABEL_SIZE)
    title_font = ui_font(28, bold=True)
    meta_font = ui_font(18)
    body_font = ui_font(17)

    missing_waqf = cp_missing(path, waqf_cps)
    has_saktah = f.get('saktah', False)
    has_honorific = f.get('saw', False)

    W, H = 1840, 1040
    im = Image.new('RGB', (W,H), BG)
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((26,26,W-26,H-26), radius=24, fill=CARD, outline=LINE, width=2)

    title = f['filename']
    d.text((62,54), title, font=title_font, fill=INK)
    status = f"Madinah pause marks: {6-len(missing_waqf)}/6     Saktah U+06DC: {'yes' if has_saktah else 'no'}     Honorific U+FDFA: {'yes' if has_honorific else 'no'}     Al-Fatiha fixture: {f['fatiha_have']}/31"
    d.text((62,105), status, font=meta_font, fill=GOOD if not missing_waqf else WARN)
    if missing_waqf:
        miss_txt = 'Not mapped in this font: ' + ', '.join(f'U+{c:04X}' for c in missing_waqf)
        d.text((62,134), miss_txt, font=meta_font, fill=BAD)
    else:
        d.text((62,134), 'All six pause signs are mapped by this font.', font=meta_font, fill=GOOD)

    y=188
    d.line((62,165,W-62,165), fill=LINE, width=2)
    line_gap=77
    for caption, arabic in examples:
        d.text((62,y), caption, font=label_font, fill=SUB)
        # Render a single explicit font, no font-family fallback. Clip to fixed content area only.
        # Decrease size only if string is too wide, without changing font family.
        fs=FONT_SIZE
        rf=font
        bbox=d.textbbox((0,0), arabic, font=rf, direction='rtl', language='ar', anchor='ra')
        max_width=W-160
        while (bbox[2]-bbox[0]) > max_width and fs>24:
            fs-=1
            rf=safe_font(path, fs)
            bbox=d.textbbox((0,0), arabic, font=rf, direction='rtl', language='ar', anchor='ra')
        d.text((W-72,y+30), arabic, font=rf, fill=INK, direction='rtl', language='ar', anchor='ra')
        y += line_gap

    d.line((62,y+2,W-62,y+2), fill=LINE, width=2)
    y += 20
    d.text((62,y), fixture_label, font=label_font, fill=SUB)
    d.text((W-72,y+40), fixture, font=font, fill=INK, direction='rtl', language='ar', anchor='ra')
    y += 88
    d.text((62,y), honorific_label, font=label_font, fill=SUB)
    d.text((W-72,y+36), honorific, font=font, fill=INK, direction='rtl', language='ar', anchor='ra')
    d.text((62,H-66), 'Rendered from this exact font file only · no system-font fallback · excerpts sourced from project samples', font=body_font, fill=SUB)

    out_path=INDIV/(path.stem.replace(' ','_')+'.png')
    im.save(out_path, optimize=True)
    records.append({'font':f, 'path':out_path, 'missing':missing_waqf})

# Sort for comparison: full six-sign fonts first; partials last.
records.sort(key=lambda r: (len(r['missing'])>0, r['font']['filename'].lower()))

# Create separate contact sheets: fully covered pause repertoire first, partial fonts separately.
PANEL_W, PANEL_H = 1840, 1040
MARGIN, GAP = 40, 32
full_records = [r for r in records if not r['missing']]
partial_records = [r for r in records if r['missing']]

def make_sheets(group, prefix):
    if not group:
        return
    for page in range(math.ceil(len(group)/4)):
        subset=group[page*4:(page+1)*4]
        cols, rows = 2, 2
        W = MARGIN*2 + cols*PANEL_W + (cols-1)*GAP
        H = MARGIN*2 + rows*PANEL_H + (rows-1)*GAP
        sheet=Image.new('RGB',(W,H),BG)
        for i, rec in enumerate(subset):
            src=Image.open(rec['path']).convert('RGB')
            x=MARGIN+(i%cols)*(PANEL_W+GAP)
            y=MARGIN+(i//cols)*(PANEL_H+GAP)
            sheet.paste(src,(x,y))
        out=OUT/f'{prefix}_page_{page+1}.png'
        sheet.save(out,optimize=True)

make_sheets(full_records, 'full_pause_support')
make_sheets(partial_records, 'partial_pause_support')

# Also create one compact glyph-only chart to compare the seven pause/Saktah glyphs in all fonts.
font_names = [r['font']['filename'] for r in records]
row_h=88
W=2300
H=180+len(records)*row_h
chart=Image.new('RGB',(W,H),BG)
d=ImageDraw.Draw(chart)
title_font=ui_font(32, bold=True)
name_font=ui_font(18)
small=ui_font(16)
d.text((40,30),'Qur’anic pause-sign glyph comparison',font=title_font,fill=INK)
d.text((40,82),'Each glyph is rendered from the named font binary only; missing glyphs appear as that font’s .notdef box.',font=small,fill=SUB)
headers=['U+06D6','U+06D7','U+06D8','U+06D9','U+06DA','U+06DB','U+06DC']
colx=[1120,1280,1440,1600,1760,1920,2080]
for x,h in zip(colx,headers): d.text((x,130),h,font=small,fill=SUB,anchor='mm')
for idx, rec in enumerate(records):
    y=180+idx*row_h
    if idx%2==0: d.rectangle((30,y,W-30,y+row_h),fill=(255,255,252))
    d.text((48,y+row_h//2),rec['font']['filename'],font=name_font,fill=INK,anchor='lm')
    fpath=font_path_for(rec['font'])
    glyph_font=safe_font(fpath,34)
    glyphs=['بَابٌۖ','بَابٌۗ','بَابٌۘ','بَابٌۙ','بَابٌۚ','بَابٌۛ','بَابٌۜ']
    for x,g in zip(colx,glyphs):
        d.text((x,y+row_h//2),g,font=glyph_font,fill=INK,direction='rtl',language='ar',anchor='mm')
    d.line((30,y+row_h,W-30,y+row_h),fill=LINE,width=1)
chart_path=OUT/'pause_glyphs_all_arabic_fonts.png'
chart.save(chart_path,optimize=True)

# Create manifest and explanatory README.
manifest=[]
for r in records:
    f=r['font']
    manifest.append({
        'filename':f['filename'], 'image':str(r['path'].relative_to(OUT)),
        'madinah_pause_mapped':6-len(r['missing']), 'missing_pause_codepoints':[f'U+{c:04X}' for c in r['missing']],
        'saktah':bool(f.get('saktah')), 'saw':bool(f.get('saw')),
        'note':'Rendered using this font file only. Missing glyphs are not supplied by system fonts.'
    })
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'README.txt').write_text('''Qur’anic font specimen images\n\nThese PNG images are rendered directly from the exact font files supplied in the original project, using Pillow with RAQM Arabic shaping. Each specimen uses a single explicit font binary. No browser or operating-system font-family fallback is used.\n\nFiles:\n- font_comparison_page_1.png ... : detailed comparison pages (four fonts per page)\n- pause_glyphs_all_arabic_fonts.png : seven pause/Saktah glyph strip per Arabic-capable font\n- individual/ : full-size image per Arabic-capable font\n- manifest.json : coverage and image manifest\n\nThe seven sample lines are actual verse excerpts already stored in the project’s samples/madinah_pause_examples.txt: six Madinah pause-mark classes and one Hafs Saktah example. The repeated-word line is a synthetic typography test only, not Qur’anic wording. The final Arabic line tests the ﷺ honorific (U+FDFA).\n\nImportant: if a font does not map a particular pause sign, the image shows that font’s missing-glyph replacement rather than borrowing the symbol from another font. This is deliberate: it prevents fallback from hiding font deficiencies. The coverage status is printed in each specimen card.\n\nThe images are a fixed visual record; they do not replace live HTML text for browser testing, accessibility, search, selection, or responsive layout.\n''',encoding='utf-8')

# Report where the images were written. No script copy or ZIP is created.

print('fonts',len(fonts),'images',len(records),'waqf_complete',sum(not r['missing'] for r in records))
for p in sorted(OUT.glob('*.png')):
    print(p.name,p.stat().st_size)
print('output_dir', OUT)
