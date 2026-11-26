#!/usr/bin/env python3
"""
adoc_to_json.py - convert duas.adoc into data/book.json (the format build.py reads).

    python adoc_to_json.py duas.adoc                       # -> data/duas.json
    python adoc_to_json.py duas.adoc --out data/book.json
    python adoc_to_json.py duas.adoc --translation-source machine
    python adoc_to_json.py duas.adoc --title "My Dua Book" --org "My Org"

Then build the PDF:
    python build.py --data data/duas.json
"""
import argparse
import json
import re
import unicodedata
from pathlib import Path

ROLE_RE = re.compile(r"^\[\.([\w-]+)\]$")
HEADING_RE = re.compile(r"^(={2,4})\s+(.*\S)\s*$")
QURAN_REF_RE = re.compile(r"^Quran\s+(\d+):(\d+)(?:-(\d+))?\s*$")
DASH_SPLIT_RE = re.compile(r"\s[–-]\s")
TRANSLIT_IN_WORD_RE = re.compile(r"^(.*?)\s*\(([^()]*)\)\s*$")
BENGALI_RE = re.compile(r"[\u0980-\u09FF]")

FIELD_MAP = {
    "arabic-text": "arabic",
    "word-by-word": "word_by_word",
    "transliteration": "transliteration",
    "translation-bangla": "bn",
    "translation-english": "en",
    "translation-computer-generated-bangla": "bn_machine",
    "translation-computer-generated-english": "en_machine",
}


# --------------------------------------------------------------------------- parsing
def new_entry(section, subsection, subsubsection):
    return {"section": section, "subsection": subsection, "subsubsection": subsubsection,
            "references": [], "labels": [], "notes": [], "arabic": "",
            "word_groups": [],            # list of lists of {ar,bn,en}; blank line = new group
            "transliteration": "",
            "bn": "", "en": "", "bn_machine": "", "en_machine": ""}


def read_block(lines, i):
    n = len(lines)
    while i < n and not lines[i].strip():
        i += 1
    if i < n and lines[i].strip() == "--":
        i += 1
        out = []
        while i < n and lines[i].strip() != "--":
            out.append(lines[i].rstrip())
            i += 1
        return out, i + 1
    out = []
    while i < n and lines[i].strip():
        if ROLE_RE.match(lines[i].strip()) or HEADING_RE.match(lines[i]):
            break
        out.append(lines[i].rstrip())
        i += 1
    return out, i


def parse_word_line(line):
    parts = DASH_SPLIT_RE.split(line.strip(), maxsplit=2)
    ar = parts[0].strip()
    m = TRANSLIT_IN_WORD_RE.match(ar)
    if m:
        ar = m.group(1).strip()
    word = {"ar": ar}
    if len(parts) > 1 and parts[1].strip():
        word["bn"] = parts[1].strip()
    if len(parts) > 2 and parts[2].strip():
        word["en"] = parts[2].strip()
    return word


def parse_word_groups(block):
    groups, cur = [], []
    for ln in block:
        if not ln.strip():
            if cur:
                groups.append(cur)
                cur = []
            continue
        cur.append(parse_word_line(ln))
    if cur:
        groups.append(cur)
    return groups


def has_content(e):
    return any(e[k] for k in ("arabic", "word_groups", "transliteration",
                              "bn", "en", "bn_machine", "en_machine"))


def parse_adoc(path):
    lines = Path(path).read_text(encoding="utf-8").split("\n")
    entries, entry = [], None
    section = subsection = subsubsection = None
    book_title = None
    i, n = 0, len(lines)
    while i < n:
        raw, s = lines[i], lines[i].strip()
        if not s or s == "--" or s == "&&&&" or s.startswith(":") or s.startswith("//"):
            i += 1
            continue
        if s.startswith("= ") and not s.startswith("=="):
            book_title = s[2:].strip()
            i += 1
            continue
        h = HEADING_RE.match(raw)
        if h:
            level, title = len(h.group(1)), h.group(2)
            if level == 2:
                section, subsection, subsubsection = title, None, None
            elif level == 3:
                subsection, subsubsection = title, None
            else:
                subsubsection = title
            entry = None
            i += 1
            continue
        m = ROLE_RE.match(s)
        if m:
            role = m.group(1)
            block, i = read_block(lines, i + 1)
            if role == "reference":
                if entry is None or has_content(entry):
                    entry = new_entry(section, subsection, subsubsection)
                    entries.append(entry)
                for ln in block:
                    t = ln.strip()
                    if not t:
                        continue
                    if t.startswith("NOTE:"):
                        entry["notes"].append(t[5:].strip())
                    elif t.startswith(".") and not t.startswith(". "):
                        entry["labels"].append(t[1:].strip())
                    else:
                        entry["references"].append(t)
            elif role in FIELD_MAP and entry is not None:
                field = FIELD_MAP[role]
                content = []
                for b in block:
                    if b.strip().startswith("NOTE:"):
                        entry["notes"].append(b.strip()[5:].strip())
                    else:
                        content.append(b)
                if field == "word_by_word":
                    entry["word_groups"].extend(parse_word_groups(content))
                else:
                    text = "\n".join(b for b in content if b.strip()).strip()
                    entry[field] = (entry[field] + "\n" + text).strip() if entry[field] else text
            continue
        if s.startswith("NOTE:") and entry is not None:
            entry["notes"].append(s[5:].strip())
        i += 1
    return book_title, entries


# --------------------------------------------------------------------------- conversion
def arabic_words(text):
    """Split plain Arabic text into word cells; lone waqf/pause marks stay with the previous word."""
    words = []
    for tok in text.split():
        if words and not any(unicodedata.category(c).startswith("L") for c in tok):
            words[-1]["ar"] += " " + tok
        else:
            words.append({"ar": tok})
    return words


def split_by_language(texts):
    """Distribute intro texts into {'bn': ..., 'en': ...} by script."""
    out = {}
    for t in texts:
        if not t:
            continue
        lang = "bn" if BENGALI_RE.search(t) else "en"
        out.setdefault(lang, []).append(t)
    return {k: " | ".join(v) for k, v in out.items()}


def pick(entry, lang, source):
    human, machine = entry[lang], entry[lang + "_machine"]
    if source == "human":
        return human
    if source == "machine":
        return machine or human
    return human or machine          # auto


def build_lines(e, source):
    tr = {lang: pick(e, lang, source) for lang in ("en", "bn")}
    tr = {k: v for k, v in tr.items() if v}

    if e["word_groups"]:
        lines = [{"words": g, "translation": {}} for g in e["word_groups"]]
    elif e["arabic"]:
        lines = [{"words": arabic_words(row), "translation": {}}
                 for row in e["arabic"].split("\n") if row.strip()]
    else:
        lines = []
    if lines:
        lines[-1]["translation"] = tr      # translation sits under the last line
    return lines


def format_reference(e):
    parts = []
    for r in e["references"]:
        m = QURAN_REF_RE.match(r)
        parts.append(r if not m else r)
    return "; ".join(parts)


def convert(entries, source):
    duas, skipped = [], 0
    counts = {}
    for e in entries:
        lines = build_lines(e, source)
        if not lines:
            skipped += 1
            continue
        base = ": ".join(x for x in (e["section"], e["subsection"], e["subsubsection"]) if x)
        counts[base] = counts.get(base, 0) + 1
        dua = {
            "title": f"{base} ({counts[base]})",
            "section": e["section"],
            "subsection": e["subsection"],
            "lines": lines,
            "reference": format_reference(e),
        }
        intro = split_by_language(e["labels"] + e["notes"])
        if intro:
            dua["intro"] = intro
        if e["transliteration"]:
            dua["transliteration"] = e["transliteration"]
        duas.append(dua)
    # drop "(1)" where a heading has only one dua
    for d in duas:
        base = d["title"].rsplit(" (", 1)[0]
        if counts[base] == 1:
            d["title"] = base
    return duas, skipped


def main():
    ap = argparse.ArgumentParser(description="Convert duas.adoc to book.json for build.py")
    ap.add_argument("adoc", help="input .adoc file")
    ap.add_argument("--out", default="data/duas.json", help="output JSON (default data/duas.json)")
    ap.add_argument("--translation-source", choices=["auto", "human", "machine"], default="auto",
                    help="auto = original translation, fall back to computer-generated (default); "
                         "human = original only; machine = computer-generated first")
    ap.add_argument("--title")
    ap.add_argument("--subtitle", default="Word by Word")
    ap.add_argument("--tagline", default="Supplication from Quran and Authentic Hadith")
    ap.add_argument("--running-title")
    ap.add_argument("--org", default="Your Organisation")
    args = ap.parse_args()

    book_title, entries = parse_adoc(args.adoc)
    duas, skipped = convert(entries, args.translation_source)
    title = args.title or book_title or "Dua Book"

    data = {
        "meta": {"title": title, "subtitle": args.subtitle, "tagline": args.tagline,
                 "running_title": args.running_title or title, "org": args.org, "lang": "en"},
        "languages": ["en", "bn"],
        "duas": duas,
        "about": {
            "heading": f"About {args.org}",
            "text": "Replace this text with a short description of your organisation.",
            "links": [{"label": "Website", "url": "https://example.org"}],
            "footer_note": "FOR FREE DISTRIBUTION ONLY | NOT FOR SALE",
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    words = sum(len(l["words"]) for d in duas for l in d["lines"])
    print(f"wrote {out}: {len(duas)} duas, {words} word cells"
          + (f" ({skipped} entries skipped: no Arabic text)" if skipped else ""))


if __name__ == "__main__":
    main()
