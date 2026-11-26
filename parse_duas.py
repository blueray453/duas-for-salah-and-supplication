#!/usr/bin/env python3
"""
Parse duas.adoc into a structured dataset.

Outputs (in the output directory):
  duas.json        - nested records, one per dua entry (word-by-word kept as a list)
  duas.jsonl       - same records, one JSON object per line
  duas.csv         - flat table, one row per dua (lists are JSON-encoded / " | " joined)
  duas_words.csv   - one row per word-by-word item, linked to dua_id

Usage:
  python parse_duas.py duas.adoc [output_dir]
"""
import csv
import json
import re
import sys
from pathlib import Path

ROLE_RE = re.compile(r"^\[\.([\w-]+)\]$")
HEADING_RE = re.compile(r"^(={2,4})\s+(.*\S)\s*$")
QURAN_REF_RE = re.compile(r"^Quran\s+(\d+):(\d+)(?:-(\d+))?\s*$")
DASH_SPLIT_RE = re.compile(r"\s[–-]\s")  # en-dash or hyphen surrounded by spaces
TRANSLIT_IN_WORD_RE = re.compile(r"^(.*?)\s*\(([^()]*)\)\s*$")

# role tag -> field name in the record
FIELD_MAP = {
    "arabic-text": "arabic",
    "word-by-word": "word_by_word",
    "transliteration": "transliteration",
    "translation-bangla": "translation_bangla",
    "translation-english": "translation_english",
    "translation-computer-generated-bangla": "translation_bangla_machine",
    "translation-computer-generated-english": "translation_english_machine",
}


def new_entry(section, subsection, subsubsection):
    return {
        "section": section,
        "subsection": subsection,
        "subsubsection": subsubsection,
        "references": [],        # raw reference strings (Quran / hadith codes)
        "labels": [],            # ".Title" lines inside reference block (grading, context, ...)
        "notes": [],             # NOTE: lines
        "arabic": "",
        "word_by_word": [],
        "transliteration": "",
        "translation_bangla": "",
        "translation_english": "",
        "translation_bangla_machine": "",
        "translation_english_machine": "",
    }


def read_block(lines, i):
    """Read a content block starting at line i (the line after the role tag).

    Supports both forms used in the file:
        --
        text...
        --
    and a bare paragraph that runs until the next blank line.
    Returns (list_of_lines, next_index).
    """
    n = len(lines)
    while i < n and not lines[i].strip():
        i += 1
    if i < n and lines[i].strip() == "--":
        i += 1
        out = []
        while i < n and lines[i].strip() != "--":
            out.append(lines[i].rstrip())
            i += 1
        return out, i + 1  # skip closing --
    out = []
    while i < n and lines[i].strip():
        if ROLE_RE.match(lines[i].strip()) or HEADING_RE.match(lines[i]):
            break
        out.append(lines[i].rstrip())
        i += 1
    return out, i


def parse_word_line(line):
    """'arabic – bangla – english' (optionally 'arabic (translit) – bangla')."""
    parts = DASH_SPLIT_RE.split(line.strip(), maxsplit=2)
    ar = parts[0].strip()
    translit = ""
    m = TRANSLIT_IN_WORD_RE.match(ar)
    if m:
        ar, translit = m.group(1).strip(), m.group(2).strip()
    return {
        "arabic": ar,
        "transliteration": translit,
        "bangla": parts[1].strip() if len(parts) > 1 else "",
        "english": parts[2].strip() if len(parts) > 2 else "",
    }


def parse_reference_block(lines, entry):
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("NOTE:"):
            entry["notes"].append(s[5:].strip())
        elif s.startswith(".") and not s.startswith(". "):
            entry["labels"].append(s[1:].strip())
        else:
            entry["references"].append(s)


def parse(path):
    lines = Path(path).read_text(encoding="utf-8").split("\n")
    entries = []
    section = subsection = subsubsection = None
    section_notes = {}           # heading -> notes that appear before the first entry
    entry = None
    i, n = 0, len(lines)

    def has_content(e):
        return any(e[k] for k in ("arabic", "word_by_word", "transliteration",
                                  "translation_bangla", "translation_english",
                                  "translation_bangla_machine",
                                  "translation_english_machine"))

    while i < n:
        raw = lines[i]
        s = raw.strip()

        if not s or s == "--" or s == "&&&&" or s.startswith(":") or s.startswith("//"):
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
                # start a new entry unless the current one has no content yet
                if entry is None or has_content(entry):
                    entry = new_entry(section, subsection, subsubsection)
                    entries.append(entry)
                parse_reference_block(block, entry)
            elif role in FIELD_MAP and entry is not None:
                field = FIELD_MAP[role]
                # NOTE lines can sneak into content blocks; split them out
                content = []
                for b in block:
                    if b.strip().startswith("NOTE:"):
                        entry["notes"].append(b.strip()[5:].strip())
                    else:
                        content.append(b)
                if field == "word_by_word":
                    entry[field].extend(parse_word_line(b) for b in content if b.strip())
                else:
                    text = "\n".join(b for b in content if b.strip()).strip()
                    entry[field] = (entry[field] + "\n" + text).strip() if entry[field] else text
            continue

        if s.startswith("NOTE:"):
            note = s[5:].strip()
            if entry is not None:
                entry["notes"].append(note)
            else:
                key = " / ".join(x for x in (section, subsection, subsubsection) if x)
                section_notes.setdefault(key, []).append(note)
            i += 1
            continue

        i += 1  # anything else is ignored

    return entries, section_notes


def enrich(entries):
    for idx, e in enumerate(entries, 1):
        e["id"] = idx
        quran = []
        for r in e["references"]:
            m = QURAN_REF_RE.match(r)
            if m:
                quran.append({
                    "surah": int(m.group(1)),
                    "ayah_start": int(m.group(2)),
                    "ayah_end": int(m.group(3) or m.group(2)),
                })
        e["quran_refs"] = quran
        e["source_type"] = "quran" if quran and len(quran) == len(e["references"]) else (
            "hadith" if e["references"] else "unknown")
        e["word_count"] = len(e["word_by_word"])
    # put id first
    return [{"id": e["id"], **{k: v for k, v in e.items() if k != "id"}} for e in entries]


def write_outputs(entries, section_notes, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "duas.json").write_text(
        json.dumps({"section_notes": section_notes, "duas": entries},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    with open(out / "duas.jsonl", "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    cols = ["id", "section", "subsection", "subsubsection", "source_type",
            "references", "labels", "notes", "arabic", "transliteration",
            "translation_bangla", "translation_english",
            "translation_bangla_machine", "translation_english_machine",
            "word_count", "quran_refs"]
    with open(out / "duas.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for e in entries:
            row = dict(e)
            row["references"] = " | ".join(e["references"])
            row["labels"] = " | ".join(e["labels"])
            row["notes"] = " | ".join(e["notes"])
            row["quran_refs"] = json.dumps(e["quran_refs"], ensure_ascii=False) if e["quran_refs"] else ""
            w.writerow({c: row.get(c, "") for c in cols})

    with open(out / "duas_words.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dua_id", "position", "arabic", "transliteration", "bangla", "english"])
        for e in entries:
            for pos, wd in enumerate(e["word_by_word"], 1):
                w.writerow([e["id"], pos, wd["arabic"], wd["transliteration"],
                            wd["bangla"], wd["english"]])


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "duas.adoc"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    entries, section_notes = parse(src)
    entries = enrich(entries)
    write_outputs(entries, section_notes, out_dir)
    print(f"Parsed {len(entries)} duas, "
          f"{sum(e['word_count'] for e in entries)} word-by-word rows -> {out_dir}")


if __name__ == "__main__":
    main()
