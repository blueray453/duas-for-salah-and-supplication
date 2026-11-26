#!/usr/bin/env python3
"""
adoc_to_json.py - convert duas.adoc into the JSON that build.py reads.

    python adoc_to_json.py duas.adoc                    # -> data/duas.json
    python adoc_to_json.py duas.adoc --out data/book.json
    python adoc_to_json.py duas.adoc --translation-source machine

Then:  python build.py --data data/duas.json
"""
import argparse
import json
import re
import unicodedata
from collections import OrderedDict
from pathlib import Path

ROLE_RE = re.compile(r"^\[\.([\w-]+)\]$")
HEADING_RE = re.compile(r"^(={2,4})\s+(.*\S)\s*$")
QURAN_REF_RE = re.compile(r"^Quran\s+(\d+:\d+(?:-\d+)?)\s*$")
SEP_RE = re.compile(r"\s+[–—-]\s+")                 # en dash, em dash or hyphen, spaced
TRANSLIT_RE = re.compile(r"^(.*?)\s*\(([^()]*[A-Za-zāīūḥṣḍṭẓ][^()]*)\)\s*$")
BENGALI_RE = re.compile(r"[\u0980-\u09FF]")
URL_RE = re.compile(r"https?://[^\s<>\"]+")

# Same list as abbreviation-replacer.js
SOURCES = OrderedDict([
    ("AAM", "Al-Adab Al-Mufrad"),
    ("BM", "Bulugh al-Maram"),
    ("HM", "Hisn al-Muslim"),
    ("JT", "Jami` at-Tirmidhi"),
    ("MA", "Musnad Ahmad"),
    ("MAM", "Mishkat al-Masabih"),
    ("RAS", "Riyad as-Salihin"),
    ("SAB", "Sahih al-Bukhari"),
    ("SAN", "Sunan an-Nasa'i"),
    ("SD", "Sunan Abi Dawud"),
    ("SIM", "Sunan Ibn Majah"),
    ("SM", "Sahih Muslim"),
])
SUFFIXES = {"T": "Tahajjud", "N": "Nafl Prayer"}
ABBR_ALT = "|".join(sorted(SOURCES, key=len, reverse=True))
ABBR_FULL_RE = re.compile(rf"^({ABBR_ALT})\s+(\S+?)(?:\s*\(([TN])\))?$")
ABBR_LEAD_RE = re.compile(rf"^({ABBR_ALT})\s+(.*)$")
NAME_TO_ABBR = {v: k for k, v in SOURCES.items()}
NAME_NUM_RE = re.compile(r"^(.+?)\s+(\d+[a-z]?)$")

FIELD_MAP = {
    "arabic-text": "arabic",
    "word-by-word": "word_by_word",
    "transliteration": "transliteration",
    "translation-bangla": "bn",
    "translation-english": "en",
    "translation-computer-generated-bangla": "bn_machine",
    "translation-computer-generated-english": "en_machine",
}


# --------------------------------------------------------------------------- helpers
def lang_of(text):
    return "bn" if BENGALI_RE.search(text) else "en"


def extract_urls(text):
    """Return (text_without_urls, [urls])."""
    urls = [u.rstrip(".,;:)”’'") for u in URL_RE.findall(text)]
    rest = URL_RE.sub("", text)
    rest = re.sub(r"\s{2,}", " ", rest).strip(" \t-–|:;,")
    return rest, urls


def new_entry(section, subsection, subsubsection):
    return {"section": section, "subsection": subsection, "subsubsection": subsubsection,
            "references": [], "labels": [], "notes": [], "heading_notes": [],
            "arabic": "", "word_groups": [], "transliteration": "",
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


# --------------------------------------------------------------------------- word-by-word
def parse_word_line(line):
    """'ar – bn – en'  or  'ar (translit) – bn'  ->  dict(ar, [tr], [bn], [en])."""
    parts = SEP_RE.split(line.strip(), maxsplit=2)
    ar = parts[0].strip()
    word = {}
    m = TRANSLIT_RE.match(ar)
    if m:
        ar = m.group(1).strip()
        word["tr"] = m.group(2).strip()
    word = {"ar": ar, **word}
    if len(parts) > 1 and parts[1].strip():
        word["bn"] = parts[1].strip()
    if len(parts) > 2 and parts[2].strip():
        word["en"] = parts[2].strip()
    return word


def group_to_lines(rows):
    """One blank-line-separated group of rows -> list of grid lines.

    Two layouts exist in the source:
      * every row is a word/phrase with its own English   -> one grid line
      * single words (with transliteration, Bangla only) followed by a *phrase row*
        that carries the English meaning of those words    -> grid + phrase meaning
    """
    lines, plain, pending = [], [], []

    def flush_plain():
        nonlocal plain
        if plain:
            lines.append({"words": plain, "translation": {}})
            plain = []

    for w in rows:
        if "en" not in w and "tr" in w:             # single word waiting for its phrase row
            pending.append(w)
        elif pending and "en" in w:                  # phrase row closes the pending words
            flush_plain()
            phrase = {k: w[k] for k in ("bn", "en") if k in w}
            lines.append({"words": pending, "phrase": phrase, "translation": {}})
            pending = []
        else:
            if pending:                              # pending words that never got a phrase row
                plain.extend(pending)
                pending = []
            plain.append(w)
    plain.extend(pending)
    flush_plain()
    return lines


# --------------------------------------------------------------------------- parsing
def parse_adoc(path):
    lines = Path(path).read_text(encoding="utf-8").split("\n")
    entries, entry = [], None
    section = subsection = subsubsection = None
    book_title = None
    heading_level = 2
    pending_heading_notes = []
    i, n = 0, len(lines)

    def has_content(e):
        return any(e[k] for k in ("arabic", "word_groups", "transliteration",
                                  "bn", "en", "bn_machine", "en_machine"))

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
            level, title = len(h.group(1)) - 1, h.group(2)       # == -> 1, === -> 2, ==== -> 3
            if level == 1:
                section, subsection, subsubsection = title, None, None
            elif level == 2:
                subsection, subsubsection = title, None
            else:
                subsubsection = title
            heading_level = level
            entry = None
            pending_heading_notes = []
            i += 1
            continue
        m = ROLE_RE.match(s)
        if m:
            role = m.group(1)
            block, i = read_block(lines, i + 1)
            if role == "reference":
                if entry is None or has_content(entry):
                    entry = new_entry(section, subsection, subsubsection)
                    entry["heading_notes"] = pending_heading_notes
                    pending_heading_notes = []
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
                    group = []
                    for b in content:
                        if b.strip():
                            group.append(parse_word_line(b))
                        elif group:
                            entry["word_groups"].append(group)
                            group = []
                    if group:
                        entry["word_groups"].append(group)
                else:
                    text = "\n".join(b for b in content if b.strip()).strip()
                    entry[field] = (entry[field] + "\n" + text).strip() if entry[field] else text
            continue
        if s.startswith("NOTE:"):
            note = s[5:].strip()
            if entry is not None:
                entry["notes"].append(note)
            else:                                  # note under a heading, before its first dua
                pending_heading_notes.append({"level": heading_level, "text": note})
        i += 1
    return book_title, entries


# --------------------------------------------------------------------------- references
def build_reference(e):
    """Turn raw reference/label/note lines into a structured reference block."""
    sources = OrderedDict()       # abbr or 'Quran' -> {"name", "abbr", "numbers"}
    other, comments, links = [], [], []

    def add_source(key, name, number):
        s = sources.setdefault(key, {"name": name, "abbr": key, "numbers": []})
        if number not in s["numbers"]:
            s["numbers"].append(number)

    for raw in e["references"]:
        text, urls = extract_urls(raw)
        links.extend(urls)
        if not text:
            continue
        mq = QURAN_REF_RE.match(text)
        ma = ABBR_FULL_RE.match(text)
        if mq:
            add_source("Quran", "Quran", mq.group(1))
        elif ma:
            number = ma.group(2) + (f" ({SUFFIXES[ma.group(3)]})" if ma.group(3) else "")
            add_source(ma.group(1), SOURCES[ma.group(1)], number)
        elif NAME_NUM_RE.match(text) and NAME_NUM_RE.match(text).group(1) in NAME_TO_ABBR:
            nm = NAME_NUM_RE.match(text)               # full book name + number, e.g. "Musnad Ahmad 23355"
            add_source(NAME_TO_ABBR[nm.group(1)], nm.group(1), nm.group(2))
        else:
            ml = ABBR_LEAD_RE.match(text)
            if ml:                                     # abbreviation followed by free text
                text = f"{SOURCES[ml.group(1)]} {ml.group(2)}"
            text = re.sub(r"\((T|N)\)", lambda m: f"({SUFFIXES[m.group(1)]})", text)
            if len(text) > 90 or (len(text) > 50 and text.endswith(".")):
                comments.append({"text": text, "lang": lang_of(text)})
            else:
                other.append(text)

    labels = []
    for lab in e["labels"]:
        text, urls = extract_urls(lab)
        links.extend(urls)
        if text:
            labels.append({"text": text, "lang": lang_of(text)})

    notes = {}
    for note in e["notes"]:
        text, urls = extract_urls(note)
        links.extend(urls)
        if text:
            notes.setdefault(lang_of(text), []).append(text)

    seen, uniq_links = set(), []
    for u in links:
        if u not in seen:
            seen.add(u)
            uniq_links.append(u)

    ref = {"labels": labels, "sources": list(sources.values()), "other": other,
           "comments": comments, "links": uniq_links}
    ref = {k: v for k, v in ref.items() if v}
    return ref, notes


# --------------------------------------------------------------------------- conversion
def pick(entry, lang, source):
    human, machine = entry[lang], entry[lang + "_machine"]
    if source == "human":
        return human
    if source == "machine":
        return machine or human
    return human or machine


def build_lines(e, source):
    tr = {lang: pick(e, lang, source) for lang in ("en", "bn")}
    tr = {k: v for k, v in tr.items() if v}

    lines = []
    if e["word_groups"]:
        for g in e["word_groups"]:
            lines.extend(group_to_lines(g))
    elif e["arabic"]:
        lines = [{"text": row.strip(), "translation": {}}
                 for row in e["arabic"].split("\n") if row.strip()]
    if lines:
        lines[-1]["translation"] = tr
    return lines


def convert(entries, source):
    duas, skipped = [], 0
    for e in entries:
        lines = build_lines(e, source)
        if not lines:
            skipped += 1
            continue
        ref, notes = build_reference(e)
        quran_only = bool(ref.get("sources")) and all(s["abbr"] == "Quran" for s in ref["sources"]) \
            and not ref.get("other")
        dua = {"section": e["section"], "subsection": e["subsection"],
               "subsubsection": e["subsubsection"],
               "source_type": "quran" if quran_only else "hadith"}
        if e["heading_notes"]:
            dua["heading_notes"] = [{"level": h["level"], "text": extract_urls(h["text"])[0],
                                     "lang": lang_of(h["text"])} for h in e["heading_notes"]]
            for h in e["heading_notes"]:                      # keep their links with the dua
                ref.setdefault("links", []).extend(u for u in extract_urls(h["text"])[1]
                                                   if u not in ref.get("links", []))
        if notes:
            dua["intro"] = notes
        dua["lines"] = lines
        if e["transliteration"]:
            dua["transliteration"] = e["transliteration"]
        if ref:
            dua["reference"] = ref
        duas.append(dua)
    return duas, skipped


def main():
    ap = argparse.ArgumentParser(description="Convert duas.adoc to JSON for build.py")
    ap.add_argument("adoc", help="input .adoc file")
    ap.add_argument("--out", default="data/duas.json", help="output JSON (default data/duas.json)")
    ap.add_argument("--translation-source", choices=["auto", "human", "machine"], default="auto",
                    help="auto = original translation, fall back to computer-generated (default); "
                         "human = original only; machine = computer-generated first")
    ap.add_argument("--title")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--tagline", default="Work in progress")
    ap.add_argument("--org", default="github.com/blueray453/duas-for-salah-and-supplication",
                    help="footer text on every page")
    args = ap.parse_args()

    book_title, entries = parse_adoc(args.adoc)
    duas, skipped = convert(entries, args.translation_source)
    title = args.title or book_title or "Dua Book"

    data = {
        "meta": {"title": title, "subtitle": args.subtitle, "tagline": args.tagline,
                 "running_title": title, "org": args.org, "lang": "en"},
        "languages": ["en", "bn"],
        "sources": SOURCES,
        "duas": duas,
        "about": {
            "heading": "About this book",
            "text": ("This is a work in progress. Disclaimer: I am not an Islamic scholar. "
                     "If you find any mistakes in the book, or want to include a dua that is "
                     "not mentioned here, please open an issue at:"),
            "links": [{"label": "GitHub",
                       "url": "https://github.com/blueray453/duas-for-salah-and-supplication"}],
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    words = sum(len(l.get("words", [])) for d in duas for l in d["lines"])
    print(f"wrote {out}: {len(duas)} duas, {words} word cells"
          + (f" ({skipped} entries skipped: no Arabic text)" if skipped else ""))


if __name__ == "__main__":
    main()
