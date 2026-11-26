"""
md_parser.py - turn a semi-structured Markdown file into the same dict that
data/book.json holds, so build.py can use either format.

Convention (see README.md for the full description):

    ---                                  front matter: title, subtitle, tagline,
    title: My Book                        org, running_title, lang, languages: [en, bn]
    languages: [en, bn]
    ---

    ## Dua title                         one dua = one "##" section (own page, numbered 1.1, 1.2 ...)

    > Intro note text                    blockquote = intro box. "bn: ..." lines add other languages
    > bn: Bangla intro

    | Arabic | words | here |           first table row = Arabic words, in READING ORDER
    |---|---|---|
    | English | gloss | row |           following rows = glosses, in the order of `languages`
    | Bangla | gloss | row |

    en: Translation of that line         translation lines belong to the table above them
    bn: Bangla translation

    ref: Sunan at-Tirmidhi 3391          reference (optional)

    # About Your Organisation            a single "#" heading starts the About page
    Some paragraph text.
    - Website: https://example.org       list items "Label: url" become links
    note: FOR FREE DISTRIBUTION ONLY     "note:" becomes the footer note
"""
import re
import sys
import json
from pathlib import Path

LANG_LINE = re.compile(r"^([A-Za-z]{2,3}):\s*(.*)$")
SEPARATOR_ROW = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")


class MarkdownBookError(Exception):
    pass


# ----------------------------------------------------------------- helpers
def _parse_front_matter(lines):
    """Return (dict, index_of_first_body_line)."""
    if not lines or lines[0].strip() != "---":
        return {}, 0
    meta = {}
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return meta, i + 1
        if ":" not in lines[i]:
            continue
        key, _, value = lines[i].partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = value.strip("'\"")
    raise MarkdownBookError("Front matter started with '---' but was never closed.")


def _split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _is_table_line(line):
    return line.lstrip().startswith("|")


# ----------------------------------------------------------------- main
def parse_markdown(text, source="<markdown>"):
    warnings = []
    text = text.replace("\r\n", "\n")
    # drop <!-- comments -->, keeping line breaks so warning line numbers stay right
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    lines = text.split("\n")
    fm, start = _parse_front_matter(lines)

    languages = fm.get("languages", ["en"])
    if isinstance(languages, str):
        languages = [languages]
    known = set(languages) | {"en"}

    title = fm.get("title", "Untitled")
    meta = {
        "title": title,
        "subtitle": fm.get("subtitle", ""),
        "tagline": fm.get("tagline", ""),
        "running_title": fm.get("running_title", title),
        "org": fm.get("org", ""),
        "lang": fm.get("lang", "en"),
    }

    duas, about = [], None
    cur = None            # current dua dict
    cur_line = None       # most recent {"words", "translation"} in the current dua
    in_about = False
    quote_buf = []        # pending blockquote lines
    table_buf = []        # pending table lines
    table_start = 0

    def where(n):
        return f"{Path(source).name}:{n}"

    def flush_quote(n):
        nonlocal quote_buf
        if not quote_buf:
            return
        if cur is None:
            warnings.append(f"{where(n)}: blockquote before any '##' section was ignored")
        else:
            intro = cur.setdefault("intro", {})
            plain = []
            for q in quote_buf:
                m = LANG_LINE.match(q)
                if m and m.group(1).lower() in known and m.group(1).lower() != "ref":
                    intro[m.group(1).lower()] = m.group(2).strip()
                elif q.strip():
                    plain.append(q.strip())
            if plain:
                intro["en"] = (" ".join(plain) + " " + intro.get("en", "")).strip()
        quote_buf = []

    def flush_table(n):
        nonlocal table_buf, cur_line
        if not table_buf:
            return
        rows = [_split_row(l) for l in table_buf if not SEPARATOR_ROW.match(l.strip())]
        table_buf = []
        if cur is None:
            warnings.append(f"{where(table_start)}: table before any '##' section was ignored")
            return
        if not rows:
            return
        arabic = rows[0]
        gloss_rows = rows[1:]
        if len(gloss_rows) > len(languages):
            warnings.append(
                f"{where(table_start)} [{cur['title']}]: {len(gloss_rows)} gloss rows but only "
                f"{len(languages)} language(s) declared ({', '.join(languages)}); extra rows ignored")
        words = [{"ar": a} for a in arabic]
        for lang, row in zip(languages, gloss_rows):
            if len(row) != len(arabic):
                warnings.append(
                    f"{where(table_start)} [{cur['title']}]: '{lang}' row has {len(row)} cells but the "
                    f"Arabic row has {len(arabic)} - padded/trimmed, please check alignment")
            for i, w in enumerate(words):
                value = row[i] if i < len(row) else ""
                if value:
                    w[lang] = value
        cur_line = {"words": words, "translation": {}}
        cur["lines"].append(cur_line)

    for n in range(start, len(lines)):
        raw = lines[n]
        s = raw.strip()
        lineno = n + 1

        # --- table accumulation
        if _is_table_line(raw):
            flush_quote(lineno)
            if not table_buf:
                table_start = lineno
            table_buf.append(raw)
            continue
        elif table_buf:
            flush_table(lineno)

        # --- blockquote accumulation
        if s.startswith(">"):
            quote_buf.append(s[1:].strip())
            continue
        elif quote_buf:
            flush_quote(lineno)

        if not s:
            continue

        # --- headings
        if s.startswith("## "):
            in_about = False
            cur = {"title": s[3:].strip(), "lines": []}
            cur_line = None
            duas.append(cur)
            continue
        if s.startswith("# "):
            in_about = True
            cur, cur_line = None, None
            about = {"heading": s[2:].strip(), "text": "", "links": [], "footer_note": ""}
            continue

        # --- About page content
        if in_about:
            if s.startswith(("- ", "* ")):
                label, sep, url = s[2:].partition(": ")
                if sep:
                    about["links"].append({"label": label.strip(), "url": url.strip()})
                else:
                    warnings.append(f"{where(lineno)}: about link needs 'Label: url' - ignored")
            elif s.lower().startswith("note:"):
                about["footer_note"] = s[5:].strip()
            else:
                about["text"] = (about["text"] + " " + s).strip()
            continue

        if cur is None:
            warnings.append(f"{where(lineno)}: text before the first '##' section was ignored: {s[:40]!r}")
            continue

        # --- ref / translations
        if s.lower().startswith("ref:"):
            ref = s[4:].strip()
            cur["reference"] = (cur["reference"] + "; " + ref) if cur.get("reference") else ref
            continue
        m = LANG_LINE.match(s)
        if m and m.group(1).lower() in known:
            if cur_line is None:
                warnings.append(f"{where(lineno)} [{cur['title']}]: translation before any table - ignored")
            else:
                cur_line["translation"][m.group(1).lower()] = m.group(2).strip()
            continue

        warnings.append(f"{where(lineno)} [{cur['title']}]: line not understood, ignored: {s[:50]!r}")

    flush_table(len(lines))
    flush_quote(len(lines))

    if not duas:
        raise MarkdownBookError("No '## ' sections found - nothing to build.")
    for d in duas:
        if not d["lines"]:
            warnings.append(f"[{d['title']}]: section has no word table")

    data = {"meta": meta, "languages": languages, "duas": duas}
    if about:
        data["about"] = {k: v for k, v in about.items() if v or k == "links"}
    return data, warnings


def load_markdown(path):
    data, warnings = parse_markdown(Path(path).read_text(encoding="utf-8"), source=str(path))
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    return data


if __name__ == "__main__":     # python md_parser.py book.md  -> prints JSON
    if len(sys.argv) != 2:
        sys.exit("usage: python md_parser.py book.md")
    print(json.dumps(load_markdown(sys.argv[1]), ensure_ascii=False, indent=2))
