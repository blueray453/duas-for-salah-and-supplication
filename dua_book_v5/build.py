#!/usr/bin/env python3
"""
build.py - render a book (JSON or Markdown) into a PDF with WeasyPrint.

    python build.py                              # data/book.json -> output/book.pdf
    python build.py --data data/book.md          # Markdown input (detected by extension)
    python build.py --style bw                   # black & white print version -> output/book-bw.pdf
    python build.py --style both                 # colour AND black & white PDFs in one go
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
ASSETS = ROOT / "assets"

STYLES = {
    # name: (extra stylesheet or None, logo file, default output filename)
    "color": (None, "logo.svg", "book.pdf"),
    "bw":    ("style-bw.css", "logo-bw.svg", "book-bw.pdf"),
}


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


def output_path(out_arg, style, multiple):
    """Work out where a given style's PDF goes."""
    default_name = STYLES[style][2]
    if not out_arg:
        return ROOT / "output" / default_name
    out = Path(out_arg)
    if multiple and style == "bw":          # --style both with --out x.pdf -> x.pdf + x-bw.pdf
        return out.with_name(out.stem + "-bw" + (out.suffix or ".pdf"))
    return out


def build_one(data, languages, grid, style, out, keep_html):
    extra_css, logo_file, _ = STYLES[style]

    logo = ASSETS / logo_file
    if not logo.exists():                    # user removed the bw logo? fall back to the colour one
        print(f"warning: assets/{logo_file} not found, using assets/logo.svg")
        logo = ASSETS / "logo.svg"

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("book.html").render(
        meta=data["meta"],
        duas=data["duas"],
        about=data.get("about"),
        languages=languages,
        grid_class=f"grid-{grid}",
        style_name=style,
        extra_css=extra_css,   # linked AFTER style.css so it wins the cascade
        logo=f"../assets/{logo.name}",
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    if keep_html:
        out.with_suffix(".html").write_text(html, encoding="utf-8")

    # base_url = templates/ so "style.css" and "../fonts/..." resolve correctly
    HTML(string=html, base_url=str(TEMPLATES) + "/").write_pdf(
        str(out), font_config=FontConfiguration()
    )
    print(f"wrote {out}  (style={style}, grid={grid}, languages={languages})")


def main():
    ap = argparse.ArgumentParser(description="Build the dua book PDF")
    ap.add_argument("--data", default=str(ROOT / "data" / "book.json"),
                    help="book data: .json or .md (default: data/book.json)")
    ap.add_argument("--out", help="output PDF (default: output/book.pdf, or output/book-bw.pdf for --style bw)")
    ap.add_argument("--style", choices=["color", "bw", "both"], default="color",
                    help="color (default), bw = black & white print version, both = build both")
    ap.add_argument("--to-json", metavar="FILE",
                    help="also write the loaded data as JSON (handy to convert Markdown -> JSON)")
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

    styles = ["color", "bw"] if args.style == "both" else [args.style]
    for style in styles:
        out = output_path(args.out, style, multiple=len(styles) > 1)
        build_one(data, languages, args.grid, style, out, args.keep_html)


if __name__ == "__main__":
    main()
