#!/usr/bin/env python3
"""
font_inspect.py - inspect a font file completely.

    python font_inspect.py FONT all                       # everything below, in one report
    python font_inspect.py FONT info                      # names, licence, metrics, embedding rights, tables, variable axes
    python font_inspect.py FONT coverage                  # which Unicode blocks / scripts it covers (with %)
    python font_inspect.py FONT chars --block Arabic      # every character: code point, name, glyph name, advance
    python font_inspect.py FONT glyphs                    # glyph inventory: mapped vs unmapped (ligatures, alternates, ...)
    python font_inspect.py FONT features                  # OpenType GSUB/GPOS features by script and language
    python font_inspect.py FONT check --text "بِسْمِ"       # does the font support this text? (also --file)
    python font_inspect.py FONT unicode-range             # ready-to-paste CSS unicode-range + @font-face
    python font_inspect.py FONT subset --text-file t.txt --out small.ttf   # make a physical subset
    python font_inspect.py FONT report --html report.html [--pdf report.pdf]   # visual glyph chart

Works with .ttf .otf .woff .woff2 (woff2 needs `pip install brotli`) and .ttc (use --font-number N).
Requires: pip install fonttools      (optional: weasyprint for --pdf)
"""
import argparse
import base64
import collections
import html
import os
import re
import sys
import unicodedata

from fontTools import unicodedata as ftu
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.O_S_2f_2 import OS2_UNICODE_RANGES

# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
NAME_IDS = [
    (1, "Family"), (2, "Subfamily"), (4, "Full name"), (6, "PostScript name"), (3, "Unique ID"),
    (5, "Version"), (0, "Copyright"), (7, "Trademark"), (8, "Manufacturer"), (9, "Designer"),
    (10, "Description"), (11, "Vendor URL"), (12, "Designer URL"), (13, "License"),
    (14, "License URL"), (16, "Typographic family"), (17, "Typographic subfamily"),
]

FEATURE_INFO = {
    "ccmp": "glyph composition/decomposition (needed for stacked marks)", "locl": "localized forms",
    "isol": "isolated forms (joining scripts)", "init": "initial forms (joining scripts)", "medi": "medial forms (joining scripts)",
    "fina": "final forms (joining scripts)", "rlig": "required ligatures", "liga": "standard ligatures",
    "dlig": "discretionary ligatures", "clig": "contextual ligatures", "calt": "contextual alternates",
    "rclt": "required contextual alternates", "curs": "cursive attachment", "kern": "kerning",
    "dist": "distances (positioning)", "mark": "mark-to-base positioning", "mkmk": "mark-to-mark positioning",
    "abvm": "above-base mark positioning", "blwm": "below-base mark positioning",
    "abvs": "above-base substitutions", "blws": "below-base substitutions", "pres": "pre-base substitutions",
    "psts": "post-base substitutions", "pref": "pre-base forms", "blwf": "below-base forms",
    "pstf": "post-base forms", "half": "half forms", "rphf": "reph form", "akhn": "akhand",
    "nukt": "nukta forms", "vatu": "vattu variants", "cjct": "conjunct forms", "haln": "halant forms",
    "init ": "", "rtla": "right-to-left alternates", "rtlm": "right-to-left mirrored forms",
    "ltra": "left-to-right alternates", "ltrm": "left-to-right mirrored forms",
    "salt": "stylistic alternates", "swsh": "swash", "cswh": "contextual swash", "jalt": "justification alternates",
    "smcp": "small capitals", "c2sc": "caps to small caps", "case": "case-sensitive forms",
    "frac": "fractions", "numr": "numerators", "dnom": "denominators", "sups": "superscript", "subs": "subscript",
    "sinf": "scientific inferiors", "ordn": "ordinals", "zero": "slashed zero",
    "lnum": "lining figures", "onum": "oldstyle figures", "pnum": "proportional figures", "tnum": "tabular figures",
    "ss01": "", "aalt": "access all alternates", "ccmp ": "", "vert": "vertical writing", "vrt2": "vertical rotation",
    "mset": "mark positioning via substitution", "stch": "stretching glyph decomposition",
    "cv01": "", "hlig": "historical ligatures", "hist": "historical forms", "trak": "tracking",
}


def feature_desc(tag):
    if tag in FEATURE_INFO and FEATURE_INFO[tag]:
        return FEATURE_INFO[tag]
    if re.fullmatch(r"ss\d\d", tag):
        return f"stylistic set {int(tag[2:])}"
    if re.fullmatch(r"cv\d\d", tag):
        return f"character variant {int(tag[2:])}"
    return ""


GSUB_TYPES = {1: "single", 2: "multiple", 3: "alternate", 4: "ligature", 5: "context", 6: "chain-context",
              7: "extension", 8: "reverse-chain"}
GPOS_TYPES = {1: "single", 2: "pair/kern", 3: "cursive", 4: "mark-to-base", 5: "mark-to-ligature",
              6: "mark-to-mark", 7: "context", 8: "chain-context", 9: "extension"}

FSTYPE_BITS = [
    (0x0002, "Restricted licence: embedding NOT permitted"),
    (0x0004, "Preview & print embedding only (read-only documents)"),
    (0x0008, "Editable embedding"),
    (0x0100, "No subsetting allowed"),
    (0x0200, "Bitmap embedding only"),
]


def load(path, number=0):
    if not os.path.exists(path):
        sys.exit(f"error: font not found: {path}")
    try:
        return TTFont(path, fontNumber=number, lazy=True)
    except Exception as e:  # noqa
        sys.exit(f"error: cannot open font ({e}). For .woff2 install brotli: pip install brotli")


def nm(font, nid):
    n = font["name"].getDebugName(nid) if "name" in font else None
    return (n or "").replace("\r", " ").replace("\n", " ").strip()


def cp_fmt(cp):
    return f"U+{cp:04X}"


def char_name(cp):
    try:
        return unicodedata.name(chr(cp))
    except ValueError:
        return ""


def category(cp):
    return unicodedata.category(chr(cp))


def display(cp):
    """printable form of a character (marks get a dotted-circle base)."""
    c = chr(cp)
    cat = category(cp)
    if cat in ("Mn", "Me", "Mc"):
        return "\u25CC" + c
    if cat in ("Cc", "Cf", "Zs", "Zl", "Zp", "Cs", "Co", "Cn"):
        return " "
    return c


def best_cmap(font):
    cmap = font.getBestCmap() if "cmap" in font else None
    return cmap or {}


def compress_ranges(cps, gap=0):
    """sorted code points -> [(start, end)], merging neighbours whose gap <= `gap`."""
    cps = sorted(set(cps))
    if not cps:
        return []
    out, start, prev = [], cps[0], cps[0]
    for cp in cps[1:]:
        if cp - prev - 1 > gap:
            out.append((start, prev))
            start = cp
        prev = cp
    out.append((start, prev))
    return out


def ranges_to_css(ranges):
    return ", ".join(f"U+{a:04X}" if a == b else f"U+{a:04X}-{b:04X}" for a, b in ranges)


def parse_range_arg(s):
    """'U+0600-06FF,U+0750' or '0600-06FF' -> set of code points."""
    out = set()
    for part in re.split(r"[,\s]+", s.strip()):
        if not part:
            continue
        part = part.upper().replace("U+", "")
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a, 16), int(b, 16) + 1))
        else:
            out.add(int(part, 16))
    return out


def block_table():
    """[(start, end, name)] from fontTools' Unicode data."""
    starts, names = ftu.Blocks.RANGES, ftu.Blocks.VALUES
    rows = []
    for i, s in enumerate(starts):
        e = (starts[i + 1] - 1) if i + 1 < len(starts) else 0x10FFFF
        rows.append((s, e, names[i]))
    return rows


_assigned_cache = {}


def assigned_in(start, end):
    key = (start, end)
    if key not in _assigned_cache:
        if end - start > 70000:
            _assigned_cache[key] = end - start + 1
        else:
            _assigned_cache[key] = sum(1 for c in range(start, end + 1) if unicodedata.category(chr(c)) != "Cn")
    return _assigned_cache[key]


def read_text_arg(args):
    text = ""
    if getattr(args, "text", None):
        text += args.text
    if getattr(args, "text_file", None):
        with open(args.text_file, encoding="utf-8") as fh:
            text += fh.read()
    return text


def advance(font, glyph):
    try:
        return font["hmtx"][glyph][0]
    except Exception:  # noqa
        return None


def h(title):
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


# --------------------------------------------------------------------------
# info
# --------------------------------------------------------------------------
def cmd_info(font, path, args):
    h("FILE")
    kind = "TrueType outlines (glyf)" if "glyf" in font else ("CFF2 outlines" if "CFF2" in font else ("CFF / PostScript outlines" if "CFF " in font else "unknown outlines"))
    print(f"path        : {path}")
    print(f"size        : {os.path.getsize(path):,} bytes")
    print(f"container   : {font.flavor or 'plain sfnt (ttf/otf)'}")
    print(f"outlines    : {kind}")
    print(f"glyphs      : {font['maxp'].numGlyphs:,}")
    cm = best_cmap(font)
    print(f"characters  : {len(cm):,} code points in best cmap")
    subs = [(t.platformID, t.platEncID, t.format) for t in font["cmap"].tables] if "cmap" in font else []
    print("cmap tables : " + ", ".join(f"(platform {p}, enc {e}, format {f})" for p, e, f in subs))

    h("NAMES AND LICENCE")
    for nid, label in NAME_IDS:
        v = nm(font, nid)
        if v:
            print(f"{label:22s}: {v[:300]}")

    h("EMBEDDING RIGHTS (OS/2 fsType)")
    os2 = font["OS/2"] if "OS/2" in font else None
    if os2 is None:
        print("no OS/2 table")
    else:
        fs = os2.fsType
        print(f"fsType = {fs} (0x{fs:04X})")
        notes = [text for bit, text in FSTYPE_BITS if fs & bit]
        print("  " + ("; ".join(notes) if notes else "Installable embedding: no restrictions declared in the font flags"))
        print("  (fsType is only a technical flag. The licence text above is what legally counts.)")

    h("METRICS")
    head, hhea = font["head"], font["hhea"]
    print(f"unitsPerEm            : {head.unitsPerEm}")
    print(f"hhea ascent/descent   : {hhea.ascent} / {hhea.descent}   lineGap {hhea.lineGap}")
    if os2:
        print(f"typo ascender/descender: {os2.sTypoAscender} / {os2.sTypoDescender}   lineGap {os2.sTypoLineGap}")
        print(f"win ascent/descent    : {os2.usWinAscent} / {os2.usWinDescent}")
        if hasattr(os2, "sxHeight") and os2.version >= 2:
            xh = os2.sxHeight if os2.sxHeight > 0 else "n/a"
            ch = os2.sCapHeight if os2.sCapHeight > 0 else "n/a"
            print(f"x-height / cap-height : {xh} / {ch}")
        print(f"weight class / width  : {os2.usWeightClass} / {os2.usWidthClass}")
        sel = [n for bit, n in ((0, "italic"), (5, "bold"), (6, "regular"), (7, "USE_TYPO_METRICS")) if os2.fsSelection & (1 << bit)]
        print(f"fsSelection flags     : {', '.join(sel) or '-'}")
    if "post" in font:
        print(f"italic angle          : {font['post'].italicAngle}   fixed pitch: {bool(font['post'].isFixedPitch)}")
    if cm and 0x20 in cm:
        print(f"space advance         : {advance(font, cm[0x20])} units = {advance(font, cm[0x20]) / head.unitsPerEm:.3f} em")

    h("VARIABLE FONT AXES")
    if "fvar" in font:
        for ax in font["fvar"].axes:
            print(f"axis {ax.axisTag!r:7} {nm(font, ax.axisNameID) or '':14s} min {ax.minValue:g}  default {ax.defaultValue:g}  max {ax.maxValue:g}")
        for inst in font["fvar"].instances:
            coords = ", ".join(f"{k}={v:g}" for k, v in inst.coordinates.items())
            print(f"  instance: {nm(font, inst.subfamilyNameID) or '?':20s} {coords}")
    else:
        print("not a variable font (no fvar table)")

    h("COLOUR / BITMAP TABLES")
    found = [t for t in ("COLR", "CPAL", "SVG ", "sbix", "CBDT", "CBLC", "EBDT", "EBLC") if t in font]
    print(", ".join(found) if found else "none (monochrome outline font)")

    h("DECLARED UNICODE RANGES (OS/2 bits, what the font CLAIMS)")
    if os2:
        bits = sorted(os2.getUnicodeRanges())
        names = []
        for b in bits:
            if b < len(OS2_UNICODE_RANGES):
                n = " / ".join(dict.fromkeys(name for name, _ in OS2_UNICODE_RANGES[b]))
                if n not in names:
                    names.append(n)
        print(", ".join(names) or "none declared")
        print("  (compare with `coverage`, which counts what is actually in the cmap)")

    h("TABLES")
    tags = sorted(font.keys())
    try:
        sizes = {t: font.reader.tables[t].length for t in tags if t in font.reader.tables}
    except Exception:  # noqa
        sizes = {}
    print("  ".join(f"{t.strip()}" + (f"({sizes[t]:,})" if t in sizes else "") for t in tags if t != "GlyphOrder"))
    return 0


# --------------------------------------------------------------------------
# coverage
# --------------------------------------------------------------------------
def cmd_coverage(font, path, args):
    cm = best_cmap(font)
    if not cm:
        print("no usable cmap")
        return 1
    cps = sorted(cm)
    h(f"COVERAGE BY UNICODE BLOCK   ({len(cps):,} characters)")
    by_block = collections.defaultdict(list)
    blocks = block_table()
    import bisect
    starts = [b[0] for b in blocks]
    for cp in cps:
        i = bisect.bisect_right(starts, cp) - 1
        by_block[i].append(cp)
    print(f"{'Block':38s} {'range':>15s} {'in font':>8s} {'assigned':>9s} {'%':>6s}")
    for i in sorted(by_block):
        s, e, name = blocks[i]
        have = len(by_block[i])
        tot = assigned_in(s, e)
        pct = 100 * have / tot if tot else 0
        print(f"{name[:38]:38s} {cp_fmt(s) + '-' + f'{e:04X}':>15s} {have:8,d} {tot:9,d} {pct:5.0f}%")

    h("COVERAGE BY SCRIPT")
    sc = collections.Counter(ftu.script(chr(c)) for c in cps)
    for code, n in sc.most_common():
        print(f"{code:5s} {ftu.script_name(code):28s} {n:6,d}")

    h("BY GENERAL CATEGORY")
    cc = collections.Counter(category(c) for c in cps)
    labels = {"Lu": "uppercase letters", "Ll": "lowercase letters", "Lo": "other letters", "Lm": "modifier letters",
              "Mn": "non-spacing marks (harakat etc.)", "Mc": "spacing marks", "Me": "enclosing marks",
              "Nd": "decimal digits", "No": "other numbers", "Pc": "connector punct.", "Pd": "dashes", "Ps": "open punct.",
              "Pe": "close punct.", "Po": "other punct.", "Sm": "math symbols", "Sc": "currency", "Sk": "modifier symbols",
              "So": "other symbols", "Zs": "spaces", "Cf": "format controls (ZWJ, RLM...)", "Cc": "control codes",
              "Co": "PRIVATE USE (custom glyph codes)", "Cn": "unassigned", "Pi": "initial quotes", "Pf": "final quotes"}
    for k, n in cc.most_common():
        print(f"{k}  {labels.get(k, ''):38s} {n:6,d}")
    pua = sum(1 for c in cps if category(c) == "Co")
    if pua:
        print(f"\nNOTE: {pua:,} private-use code points. These fonts often only work with the publisher's own text data.")
    return 0


# --------------------------------------------------------------------------
# chars
# --------------------------------------------------------------------------
def cmd_chars(font, path, args):
    cm = best_cmap(font)
    cps = sorted(cm)
    if args.block:
        cps = [c for c in cps if args.block.lower() in ftu.block(chr(c)).lower()]
    if args.script:
        cps = [c for c in cps if ftu.script(chr(c)).lower() == args.script.lower()]
    if args.range:
        want = parse_range_arg(args.range)
        cps = [c for c in cps if c in want]
    if args.category:
        cps = [c for c in cps if category(c).startswith(args.category)]
    total = len(cps)
    if args.limit:
        cps = cps[: args.limit]
    if args.csv:
        print("codepoint,char,name,category,script,block,glyph,advance")
    else:
        print(f"{'code':8s} {'char':5s} {'cat':3s} {'adv':>5s}  {'glyph name':22s} name")
    for cp in cps:
        g = cm[cp]
        adv = advance(font, g)
        if args.csv:
            print(f'{cp_fmt(cp)},{display(cp).strip()},"{char_name(cp)}",{category(cp)},{ftu.script(chr(cp))},"{ftu.block(chr(cp))}",{g},{adv}')
        else:
            print(f"{cp_fmt(cp):8s} {display(cp):5s} {category(cp):3s} {str(adv):>5s}  {g:22s} {char_name(cp)}")
    if args.limit and total > args.limit:
        print(f"... {total - args.limit:,} more (raise --limit)")
    print(f"\n{total:,} character(s) matched", file=sys.stderr)
    return 0


# --------------------------------------------------------------------------
# glyphs
# --------------------------------------------------------------------------
def cmd_glyphs(font, path, args):
    order = font.getGlyphOrder()
    cm = best_cmap(font)
    inv = collections.defaultdict(list)
    for cp, g in cm.items():
        inv[g].append(cp)
    mapped = [g for g in order if g in inv]
    unmapped = [g for g in order if g not in inv]
    h("GLYPH INVENTORY")
    print(f"total glyphs        : {len(order):,}")
    print(f"reachable by a char : {len(mapped):,}   (have a cmap entry)")
    print(f"NOT in cmap         : {len(unmapped):,}   (ligatures, contextual/positional forms, marks variants, components)")
    gn_real = not all(re.fullmatch(r"glyph\d+|gid\d+", g) for g in order[1:50])
    if not gn_real:
        print("NOTE: glyph names are auto-generated (no post names stored), so classification by name is unavailable.")
    groups = collections.Counter()
    for g in unmapped:
        if "." in g:
            groups["." + g.split(".", 1)[1]] += 1
        elif g.startswith("uni") or g.startswith("u"):
            groups["(uniXXXX-named, unmapped)"] += 1
        elif "_" in g:
            groups["ligature-like (a_b)"] += 1
        else:
            groups["other"] += 1
    if groups:
        print("\nunmapped glyphs by name suffix/pattern:")
        for k, n in groups.most_common(25):
            print(f"  {k:32s} {n:6,d}")
    if unmapped:
        print("\nsample unmapped glyph names: " + ", ".join(unmapped[:14]) + (" ..." if len(unmapped) > 14 else ""))
    limit = None if args.all else args.limit
    listing = unmapped if args.unmapped else order
    gidx = {g: n for n, g in enumerate(order)}
    print(f"\n{'idx':>5s} {'glyph':26s} {'adv':>5s} {'lsb':>6s}  mapped from")
    shown = 0
    for g in listing:
        i = gidx[g]
        if limit and shown >= limit:
            print(f"... {len(listing) - shown:,} more glyphs (use --all or --limit N)")
            break
        adv = advance(font, g)
        lsb = font["hmtx"][g][1] if "hmtx" in font else ""
        src = " ".join(cp_fmt(c) for c in sorted(inv.get(g, []))[:4]) or "-"
        print(f"{i:5d} {g[:26]:26s} {str(adv):>5s} {str(lsb):>6s}  {src}")
        shown += 1
    return 0


# --------------------------------------------------------------------------
# features
# --------------------------------------------------------------------------
def lookup_type(table, idx, kind):
    lk = table.LookupList.Lookup[idx]
    t = lk.LookupType
    if t == (7 if kind == "GSUB" else 9):
        try:
            t = lk.SubTable[0].ExtSubTable.LookupType
        except Exception:  # noqa
            pass
    return (GSUB_TYPES if kind == "GSUB" else GPOS_TYPES).get(t, str(t))


def cmd_features(font, path, args):
    any_layout = False
    for kind in ("GSUB", "GPOS"):
        if kind not in font:
            continue
        any_layout = True
        table = font[kind].table
        h(f"{kind}: {'glyph substitution (shaping, ligatures, alternates)' if kind == 'GSUB' else 'glyph positioning (kerning, mark placement)'}")
        if not table.ScriptList:
            print("no scripts")
            continue
        feats = table.FeatureList.FeatureRecord
        print(f"lookups: {len(table.LookupList.Lookup)}   features: {len(feats)}   scripts: {len(table.ScriptList.ScriptRecord)}")
        signatures = {}
        for sr in table.ScriptList.ScriptRecord:
            tag = sr.ScriptTag
            langs = [("(default)", sr.Script.DefaultLangSys)] if sr.Script.DefaultLangSys else []
            langs += [(lr.LangSysTag, lr.LangSys) for lr in sr.Script.LangSysRecord]
            print(f"\n script {tag!r}: {len(langs)} language system(s)")
            if not langs:
                continue
            name, ls = langs[0]
            idxs = list(ls.FeatureIndex)
            sig = tuple(sorted((feats[i].FeatureTag, tuple(feats[i].Feature.LookupListIndex)) for i in idxs))
            if sig in signatures:
                print(f"   same features as script {signatures[sig]!r}")
                others = [n for n, _ in langs[1:]]
                if others:
                    print(f"   language systems: {', '.join(others)}")
                continue
            signatures[sig] = tag
            seen = set()
            for fi in idxs:
                fr = feats[fi]
                if fr.FeatureTag in seen:
                    continue
                seen.add(fr.FeatureTag)
                types = sorted({lookup_type(table, li, kind) for li in fr.Feature.LookupListIndex})
                label = ""
                fp = getattr(fr.Feature, "FeatureParams", None)
                if fp is not None and getattr(fp, "UINameID", None):
                    label = f'  "{nm(font, fp.UINameID)}"'
                print(f"   {fr.FeatureTag!r:7} {feature_desc(fr.FeatureTag):48s} {len(fr.Feature.LookupListIndex)} lookup(s) [{', '.join(types)}]{label}")
            others = [n for n, _ in langs[1:]]
            if others:
                print(f"   other language systems: {', '.join(others)}")
    if not any_layout:
        print("No GSUB/GPOS tables: this font has NO OpenType shaping. Arabic joining, Bangla conjuncts and mark")
        print("positioning will not work through the font itself.")
    return 0


# --------------------------------------------------------------------------
# check (text coverage + sanity)
# --------------------------------------------------------------------------
def health_warnings(font, cps_to_test=None, deep=True):
    cm = best_cmap(font)
    warns = []
    if 0x20 not in cm:
        warns.append("no glyph for SPACE (U+0020)")
    if 0xA0 not in cm:
        warns.append("no glyph for NO-BREAK SPACE (U+00A0), which Quranic verse text often uses before the verse number")
    cps = sorted(cps_to_test if cps_to_test is not None else cm)
    # zero advance on non-mark characters
    zero = [c for c in cps if c in cm and advance(font, cm[c]) == 0 and category(c) not in ("Mn", "Me", "Cf", "Cc", "Zs")]
    if zero:
        warns.append("mapped but ZERO advance width and not a combining mark (will be invisible/overlap): "
                     + ", ".join(cp_fmt(c) for c in zero[:12]) + (" ..." if len(zero) > 12 else ""))
    # blank outlines
    if deep:
        try:
            gs = font.getGlyphSet()
            blank = []
            for c in cps[:6000]:
                if c not in cm or category(c) in ("Zs", "Cf", "Cc", "Zl", "Zp"):
                    continue
                bp = BoundsPen(gs)
                gs[cm[c]].draw(bp)
                if bp.bounds is None:
                    blank.append(c)
            if blank:
                warns.append("mapped but BLANK outline (empty glyph): " + ", ".join(cp_fmt(c) for c in blank[:12]) + (" ..." if len(blank) > 12 else ""))
        except Exception:  # noqa
            pass
    return warns


def cmd_check(font, path, args):
    text = read_text_arg(args)
    if not text:
        sys.exit("error: give --text 'سلام' or --file FILE")
    cm = best_cmap(font)
    used = sorted({ord(c) for c in text if not c.isspace() or c in "\u00a0"})
    h(f"TEXT CHECK: {len(used)} distinct characters")
    missing, ok = [], []
    for cp in used:
        (ok if cp in cm and cm[cp] != ".notdef" else missing).append(cp)
    print(f"supported : {len(ok)}")
    print(f"MISSING   : {len(missing)}")
    for cp in missing:
        print(f"   {cp_fmt(cp)}  {display(cp)}  {char_name(cp)}   [{ftu.script(chr(cp))}, {ftu.block(chr(cp))}]")
    warns = health_warnings(font, ok)
    if warns:
        print("\nWARNINGS for characters in this text:")
        for w in warns:
            print("  -", w)
    if missing:
        print("\nWhat happens: the renderer silently switches to ANOTHER font for these characters.")
        print("Check the PDF with `pdffonts` to see which extra fonts were pulled in.")
    return 1 if (missing and args.fail) else 0


# --------------------------------------------------------------------------
# unicode-range
# --------------------------------------------------------------------------
def select_cps(font, args):
    cm = best_cmap(font)
    cps = set(cm)
    if getattr(args, "block", None):
        cps = {c for c in cps if args.block.lower() in ftu.block(chr(c)).lower()}
    if getattr(args, "script", None):
        cps = {c for c in cps if ftu.script(chr(c)).lower() == args.script.lower()}
    text = read_text_arg(args)
    if text:
        cps &= {ord(c) for c in text}
    if getattr(args, "exclude_pua", False):
        cps = {c for c in cps if category(c) != "Co"}
    if not getattr(args, "keep_controls", False):
        cps = {c for c in cps if category(c) != "Cc" and c not in (0xFEFF,)}
    cps.discard(0)
    return sorted(cps)


def cmd_unicode_range(font, path, args):
    cps = select_cps(font, args)
    if not cps:
        sys.exit("nothing selected (check --block/--script/--text filters)")
    rng = compress_ranges(cps, args.merge_gap)
    css = ranges_to_css(rng)
    h(f"UNICODE-RANGE   ({len(cps):,} code points -> {len(rng)} range(s), merge-gap={args.merge_gap})")
    if args.merge_gap:
        covered = sum(b - a + 1 for a, b in rng)
        print(f"merged ranges now claim {covered:,} code points ({covered - len(cps):,} that the font does NOT have).")
        print("That is harmless in browsers (they fall back for missing glyphs) but widens what this face is asked for.\n")
    print(css)
    fam = args.family or nm(font, 16) or nm(font, 1) or "MyFont"
    weight = ""
    if "OS/2" in font and font["OS/2"].usWeightClass not in (400, 0):
        weight = f"\n  font-weight: {font['OS/2'].usWeightClass};"
    print("\n--- paste into your CSS ---")
    print(f"""@font-face {{
  font-family: "{fam}";
  src: url("{args.src or os.path.basename(path)}");{weight}
  unicode-range: {css};
}}""")
    if args.per_block:
        h("PER BLOCK")
        blocks = collections.defaultdict(list)
        for c in cps:
            blocks[ftu.block(chr(c))].append(c)
        for b, cs in blocks.items():
            print(f"{b:38s} {ranges_to_css(compress_ranges(cs, args.merge_gap))}")
    print("\nIMPORTANT: browsers and Chromium-based tools (Paged.js, Puppeteer, Playwright) honour unicode-range.")
    print("WeasyPrint ignores it (tested: both faces are declared but only one gets used).")
    print("For WeasyPrint use a font-family fallback stack, or make a physical subset with:  subset --text-file ...")
    return 0


# --------------------------------------------------------------------------
# subset
# --------------------------------------------------------------------------
def cmd_subset(font, path, args):
    from fontTools import subset as ftsubset
    if not args.out:
        sys.exit("error: --out FILE is required")
    cps = select_cps(font, args)
    if args.unicodes:
        cps = sorted(parse_range_arg(args.unicodes))
    if not cps:
        sys.exit("nothing to subset: use --text/--text-file/--unicodes/--block/--script")
    uni = ",".join(f"{c:04X}" for c in cps)
    argv = [path, f"--unicodes={uni}", f"--output-file={args.out}", "--layout-features=*", "--name-IDs=*",
            "--notdef-outline", "--glyph-names", "--no-hinting" if args.no_hinting else "--hinting"]
    if args.flavor:
        argv.append(f"--flavor={args.flavor}")
    ftsubset.main(argv)
    print(f"wrote {args.out}: {os.path.getsize(args.out):,} bytes (from {os.path.getsize(path):,}), {len(cps):,} code points requested")
    print("layout features (init/medi/fina/ccmp/mark/mkmk...) were kept, so Arabic/Bangla shaping still works.")
    return 0


# --------------------------------------------------------------------------
# report (HTML / PDF visual chart)
# --------------------------------------------------------------------------
def cmd_report(font, path, args):
    if not (args.html or args.pdf):
        sys.exit("error: give --html FILE and/or --pdf FILE")
    cm = best_cmap(font)
    cps = sorted(cm)
    import bisect
    blocks = block_table()
    starts = [b[0] for b in blocks]
    groups = collections.OrderedDict()
    for cp in cps:
        groups.setdefault(bisect.bisect_right(starts, cp) - 1, []).append(cp)

    data = base64.b64encode(open(path, "rb").read()).decode()
    mime = {"woff2": "font/woff2", "woff": "font/woff"}.get(font.flavor or "", "font/ttf")
    fmt = {"woff2": "woff2", "woff": "woff"}.get(font.flavor or "", "truetype")
    title = nm(font, 4) or os.path.basename(path)
    out = [f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html.escape(title)} - glyph chart</title>
<style>
@font-face {{ font-family: "Inspected"; src: url(data:{mime};base64,{data}) format("{fmt}"); }}
@page {{ size: A4; margin: 12mm; @bottom-right {{ content: counter(page); font: 8pt sans-serif; color: #888; }} }}
body {{ font: 10pt/1.4 sans-serif; color: #222; }}
h1 {{ font-size: 18pt; margin: 0 0 2mm; }} h2 {{ font-size: 11pt; margin: 7mm 0 1mm; border-bottom: 1px solid #999; break-after: avoid; }}
.meta {{ color: #666; font-size: 8.5pt; margin-bottom: 3mm; }}
.grid {{ font-size: 0; }}
.cell {{ display: inline-block; vertical-align: top; width: 21mm; height: 24mm; border: 0.4pt solid #ddd; margin: 0 -0.4pt -0.4pt 0; text-align: center; overflow: hidden; }}
.cell .g {{ font: 26pt/1.5 "Inspected"; height: 13mm; }}
.cell .c {{ font: 6.5pt monospace; color: #555; }} .cell .n {{ font: 5.5pt monospace; color: #999; overflow: hidden; white-space: nowrap; }}
.note {{ color: #a60; font-size: 8pt; }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<div class="meta">{html.escape(nm(font, 5))} &middot; {font['maxp'].numGlyphs:,} glyphs &middot; {len(cps):,} characters &middot; {html.escape(nm(font, 13)[:160])}</div>"""]
    cap = args.max_per_block
    for i, items in groups.items():
        s, e, name = blocks[i]
        out.append(f"<h2>{html.escape(name)} <small>U+{s:04X}-{e:04X} &middot; {len(items):,} of {assigned_in(s, e):,}</small></h2><div class='grid'>")
        for cp in items[:cap]:
            out.append(f"<div class='cell'><div class='g' lang='und'>{html.escape(display(cp))}</div><div class='c'>U+{cp:04X}</div><div class='n'>{html.escape(cm[cp] if len(cm[cp]) <= 15 else cm[cp][:14] + '…')}</div></div>")
        out.append("</div>")
        if len(items) > cap:
            out.append(f"<div class='note'>... {len(items) - cap:,} more not drawn (raise --max-per-block)</div>")
    out.append("</body></html>")
    doc = "\n".join(out)
    if args.html:
        with open(args.html, "w", encoding="utf-8") as fh:
            fh.write(doc)
        print(f"wrote {args.html}  ({os.path.getsize(args.html):,} bytes; open it in a browser)")
    if args.pdf:
        try:
            from weasyprint import HTML
        except ImportError:
            sys.exit("error: --pdf needs WeasyPrint (pip install weasyprint)")
        HTML(string=doc).write_pdf(args.pdf)
        print(f"wrote {args.pdf}")
    return 0


# --------------------------------------------------------------------------
# all
# --------------------------------------------------------------------------
def cmd_all(font, path, args):
    cmd_info(font, path, args)
    cmd_coverage(font, path, args)
    h("HEALTH CHECKS")
    warns = health_warnings(font)
    cm = best_cmap(font)
    if any(0x0600 <= c <= 0x06FF for c in cm):
        if "GSUB" not in font or not any(sr.ScriptTag in ("arab",) for sr in font["GSUB"].table.ScriptList.ScriptRecord):
            warns.append("has Arabic letters but no 'arab' script in GSUB: joining/positional forms will not shape through this font")
    if any(0x0980 <= c <= 0x09FF for c in cm):
        if "GSUB" not in font or not any(sr.ScriptTag in ("bng2", "beng") for sr in font["GSUB"].table.ScriptList.ScriptRecord):
            warns.append("has Bengali letters but no 'bng2'/'beng' script in GSUB: conjuncts and vowel signs may not shape")
    for t in ("fpgm", "prep"):
        pass
    print("\n".join("  WARNING: " + w for w in warns) if warns else "  no problems found")
    args.all = False
    args.limit = 40
    cmd_glyphs(font, path, args)
    cmd_features(font, path, args)
    return 0


# --------------------------------------------------------------------------
def build_parser():
    ap = argparse.ArgumentParser(description="Inspect a font file", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    ap.add_argument("font")
    ap.add_argument("command", choices=["all", "info", "coverage", "chars", "glyphs", "features", "check",
                                        "unicode-range", "subset", "report"])
    ap.add_argument("--font-number", type=int, default=0, help="face index inside a .ttc collection")
    # shared selectors
    ap.add_argument("--block", help="Unicode block name (substring), e.g. Arabic, Bengali")
    ap.add_argument("--script", help="Unicode script code, e.g. Arab, Beng, Latn")
    ap.add_argument("--range", help="code point range, e.g. U+0600-06FF")
    ap.add_argument("--category", help="general category prefix, e.g. L, Mn, Nd")
    ap.add_argument("--text", help="text to test / restrict to")
    ap.add_argument("--text-file", "--file", dest="text_file", help="UTF-8 file with text to test / restrict to")
    ap.add_argument("--limit", type=int, default=0, help="max rows for chars/glyphs (0 = all for chars)")
    ap.add_argument("--all", action="store_true", help="glyphs: list every glyph")
    ap.add_argument("--unmapped", action="store_true", help="glyphs: list only glyphs with no character (ligatures, alternates)")
    ap.add_argument("--csv", action="store_true", help="chars: CSV output")
    ap.add_argument("--fail", action="store_true", help="check: exit code 1 if characters are missing (for scripts/CI)")
    # unicode-range / subset
    ap.add_argument("--merge-gap", type=int, default=0, help="unicode-range: merge ranges separated by <= N code points")
    ap.add_argument("--exclude-pua", action="store_true", help="drop private-use code points")
    ap.add_argument("--keep-controls", action="store_true")
    ap.add_argument("--per-block", action="store_true", help="unicode-range: also print ranges per block")
    ap.add_argument("--family", help="unicode-range: font-family name for the snippet")
    ap.add_argument("--src", help="unicode-range: url() for the snippet")
    ap.add_argument("--unicodes", help="subset: explicit code points, e.g. U+0020-007E,U+0600-06FF")
    ap.add_argument("--out", help="subset: output font file")
    ap.add_argument("--flavor", choices=["woff", "woff2"], help="subset: output container")
    ap.add_argument("--no-hinting", action="store_true")
    # report
    ap.add_argument("--html", help="report: write HTML chart")
    ap.add_argument("--pdf", help="report: write PDF chart (needs weasyprint)")
    ap.add_argument("--max-per-block", type=int, default=400)
    return ap


def main():
    args = build_parser().parse_args()
    font = load(args.font, args.font_number)
    handlers = {"all": cmd_all, "info": cmd_info, "coverage": cmd_coverage, "chars": cmd_chars, "glyphs": cmd_glyphs,
                "features": cmd_features, "check": cmd_check, "unicode-range": cmd_unicode_range,
                "subset": cmd_subset, "report": cmd_report}
    if args.command == "glyphs" and not args.limit and not args.all:
        args.limit = 60
    sys.exit(handlers[args.command](font, args.font, args) or 0)


if __name__ == "__main__":
    main()
