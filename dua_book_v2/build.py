#!/usr/bin/env python3
"""
build.py - render data/book.json into a PDF with WeasyPrint.

    python build.py                          # uses data/book.json -> output/book.pdf
    python build.py --grid inline            # use the inline-block word grid
    python build.py --lang en                # English only (hide Bangla)
    python build.py --data my.json --out my.pdf
    python build.py --keep-html              # also save output/book.html for debugging
"""
import argparse
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"


def main():
    ap = argparse.ArgumentParser(description="Build the dua book PDF")
    ap.add_argument("--data", default=str(ROOT / "data" / "book.json"))
    ap.add_argument("--out", default=str(ROOT / "output" / "book.pdf"))
    ap.add_argument("--grid", choices=["flex", "inline"], default="flex",
                    help="word-grid layout: flex (default) or inline (fallback)")
    ap.add_argument("--lang", help="comma-separated translation languages, e.g. en or en,bn "
                                   "(default: the 'languages' list in the data file)")
    ap.add_argument("--keep-html", action="store_true")
    args = ap.parse_args()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
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
