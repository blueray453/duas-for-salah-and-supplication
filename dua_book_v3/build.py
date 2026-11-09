#!/usr/bin/env python3
"""
build.py - render a book (JSON or Markdown) into a PDF with WeasyPrint.

    python build.py                              # data/book.json -> output/book.pdf
    python build.py --data data/book.md          # Markdown input (detected by extension)
    python build.py --data data/book.md --to-json data/converted.json   # also export JSON
    python build.py --grid inline                # use the inline-block word grid
    python build.py --lang en                    # English only (hide Bangla)
    python build.py --data my.md --out my.pdf
    python build.py --keep-html                  # also save the intermediate HTML (debugging)
"""
import argparse
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

from md_parser import load_markdown, MarkdownBookError

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"


def load_data(path):
    """Load book data from .json or .md (anything else is an error)."""
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"error: data file not found: {p}")
    suffix = p.suffix.lower()
    if suffix == ".json":
        return json.loads(p.read_text(encoding="utf-8"))
    if suffix in (".md", ".markdown"):
        try:
            return load_markdown(p)
        except MarkdownBookError as e:
            raise SystemExit(f"error: {e}")
    raise SystemExit(f"error: unsupported data format '{suffix}' (use .json or .md)")


def main():
    ap = argparse.ArgumentParser(description="Build the dua book PDF")
    ap.add_argument("--data", default=str(ROOT / "data" / "book.json"),
                    help="book data: .json or .md (default: data/book.json)")
    ap.add_argument("--to-json", metavar="FILE",
                    help="also write the loaded data as JSON (handy to convert Markdown -> JSON)")
    ap.add_argument("--out", default=str(ROOT / "output" / "book.pdf"))
    ap.add_argument("--grid", choices=["flex", "inline"], default="flex",
                    help="word-grid layout: flex (default) or inline (fallback)")
    ap.add_argument("--lang", help="comma-separated translation languages, e.g. en or en,bn "
                                   "(default: the 'languages' list in the data file)")
    ap.add_argument("--keep-html", action="store_true")
    args = ap.parse_args()

    data = load_data(args.data)
    if args.to_json:
        Path(args.to_json).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.to_json}")
    languages = args.lang.split(",") if args.lang else data.get("languages", ["en"])

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("book.html").render(
        meta=data["meta"],
        duas=data["duas"],
        about=data.get("about"),
        languages=languages,
        grid_class=f"grid-{args.grid}",
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.keep_html:
        (out.with_suffix(".html")).write_text(html, encoding="utf-8")

    # base_url = templates/ so "style.css" and "../fonts/..." resolve correctly
    HTML(string=html, base_url=str(TEMPLATES) + "/").write_pdf(
        str(out), font_config=FontConfiguration()
    )
    print(f"wrote {out}  (grid={args.grid}, languages={languages})")


if __name__ == "__main__":
    main()
