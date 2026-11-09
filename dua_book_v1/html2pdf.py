#!/usr/bin/env python3
"""
html2pdf.py - Convert an HTML file into a polished PDF with:
  cover page, table of contents (with page numbers), running header/footer,
  page numbers, and English + Arabic (RTL) + Bangla text support.

Usage:
  python html2pdf.py input.html output.pdf \
      --title "My Report" --subtitle "Annual Overview" \
      --author "Your Name" --date "9 November 2026" --accent "#0f4c81"

Requires:  pip install weasyprint beautifulsoup4
Fonts:     Noto Sans, Noto Sans Bengali, Noto Naskh Arabic (installed system-wide)
           Ubuntu/Debian:  sudo apt install fonts-noto-core
           macOS:          brew install --cask font-noto-sans font-noto-sans-bengali font-noto-naskh-arabic
           Windows:        install the .ttf files from fonts.google.com/noto
"""
import argparse
import datetime
import html
import re
from pathlib import Path

from bs4 import BeautifulSoup
from weasyprint import HTML, CSS

# ----------------------------------------------------------------------------
# 1. CSS template. Font stacks: the browser/WeasyPrint picks the first font that
#    HAS the glyph, so listing Latin -> Bengali -> Arabic gives per-character
#    fallback inside a single paragraph (mixed-script text just works).
# ----------------------------------------------------------------------------
CSS_TEMPLATE = """
@page {
  size: %(page_size)s;
  margin: 25mm 22mm 25mm 22mm;
}

/* ---- Cover: no header/footer, full-bleed colour ---- */
@page cover {
  margin: 0;
  @top-left     { content: none; }
  @bottom-center{ content: none; }
}

/* ---- TOC: roman numerals, restart at i ---- */
@page :nth(1 of toc)  { counter-reset: page 1; }
@page :nth(1 of main) { counter-reset: page 1; }   /* body restarts at 1 */
@page toc {
  @top-left   { content: string(doctitle); font-size: 9pt; color: #888; }
  @bottom-center { content: counter(page, lower-roman); font-size: 9pt; color: #555; }
}

/* ---- Main content: arabic numerals starting at 1 ---- */
@page main {
  @top-left   { content: string(doctitle); font-size: 9pt; color: #888;
                border-bottom: 0.5pt solid #ddd; padding-bottom: 3mm; width: 100%%; }
  @top-right  { content: string(chapter); font-size: 9pt; color: %(accent)s;
                border-bottom: 0.5pt solid #ddd; padding-bottom: 3mm; }
  @bottom-center { content: "— " counter(page) " —"; font-size: 9.5pt; color: #555; }
}

html {
  font-family: "Noto Sans", "Noto Sans Bengali", "Noto Naskh Arabic", sans-serif;
  font-size: 10.5pt;
  line-height: 1.65;
  color: #222;
}

/* Each block decides its own direction from its first strong character,
   so Arabic paragraphs flow right-to-left automatically.            */
p, li, h1, h2, h3, h4, td, th, blockquote, figcaption {
  unicode-bidi: plaintext;
  text-align: start;
}
[dir="rtl"], :lang(ar) { font-family: "Noto Naskh Arabic", "Noto Sans", "Noto Sans Bengali", serif; }
:lang(bn)              { font-family: "Noto Sans Bengali", "Noto Sans", "Noto Naskh Arabic", sans-serif; line-height: 1.8; }
/* Arabic script needs a bit more line height for diacritics */
[dir="rtl"] { line-height: 2; font-size: 11.5pt; }

/* ---------------- Cover ---------------- */
.cover {
  page: cover;
  height: 297mm;               /* A4; adjusted for Letter below if needed */
  box-sizing: border-box;
  padding: 0 28mm;
  background: linear-gradient(160deg, %(accent)s 0%%, %(accent_dark)s 100%%);
  color: #fff;
  display: flex; flex-direction: column; justify-content: center;
  page-break-after: always;
}
.cover .bar   { width: 28mm; height: 2.2mm; background: %(gold)s; margin-bottom: 14mm; }
.cover h1     { font-size: 34pt; line-height: 1.25; margin: 0 0 6mm; font-weight: 700;
                string-set: doctitle content(); bookmark-level: none; }
.cover .subtitle { font-size: 15pt; font-weight: 300; opacity: .92; margin-bottom: 40mm; }
.cover .meta  { font-size: 11pt; opacity: .85; border-top: 0.5pt solid rgba(255,255,255,.4);
                padding-top: 6mm; }

/* ---------------- TOC ---------------- */
.toc { page: toc; page-break-after: always; }
.toc h2.toc-title { font-size: 22pt; color: %(accent)s; margin: 0 0 10mm;
                    border-bottom: 2pt solid %(gold)s; padding-bottom: 3mm; bookmark-level: 1; }
.toc ul  { list-style: none; margin: 0; padding: 0; }
.toc li  { margin: 0; }
.toc a   { color: inherit; text-decoration: none; display: block; }
.toc a::after { content: leader('.') target-counter(attr(href), page); color: #555; }
.toc .l1 { margin-top: 4mm; font-weight: 600; font-size: 11.5pt; }
.toc .l2 { padding-inline-start: 8mm; font-size: 10.5pt; }
.toc .l3 { padding-inline-start: 16mm; font-size: 9.5pt; color: #555; }

/* ---------------- Body ---------------- */
.content { page: main; }
.content h1 {
  string-set: chapter content();
  break-before: page; font-size: 22pt; color: %(accent)s;
  margin: 0 0 8mm; padding-bottom: 3mm; border-bottom: 2pt solid %(gold)s;
  bookmark-level: 1; bookmark-label: content();
}
.content h1:first-child { break-before: avoid; }
.content h2 { font-size: 15pt; color: %(accent_dark)s; margin: 9mm 0 3mm; bookmark-level: 2; break-after: avoid; }
.content h3 { font-size: 12pt; color: #333;            margin: 6mm 0 2mm; bookmark-level: 3; break-after: avoid; }
.content p  { margin: 0 0 3.2mm; orphans: 3; widows: 3; }
.content a  { color: %(accent)s; }
.content img{ max-width: 100%%; height: auto; }
.content blockquote {
  margin: 4mm 0; padding: 3mm 5mm; background: #f4f7fb;
  border-inline-start: 1.2mm solid %(accent)s; color: #444;
  break-inside: avoid;
}
.content table { width: 100%%; border-collapse: collapse; margin: 4mm 0; font-size: 9.5pt; }
.content th    { background: %(accent)s; color: #fff; padding: 2.2mm 3mm; text-align: start; }
.content td    { padding: 2mm 3mm; border-bottom: 0.4pt solid #ddd; }
.content tr:nth-child(even) td { background: #f8f9fb; }
.content tr    { break-inside: avoid; }
.content pre, .content code {
  font-family: "DejaVu Sans Mono", monospace; font-size: 9pt; background: #f1f3f5;
}
.content pre   { padding: 3mm; border-radius: 1.5mm; white-space: pre-wrap; break-inside: avoid; }
.content code  { padding: 0 1mm; border-radius: 1mm; }
.content ul, .content ol { padding-inline-start: 7mm; margin: 0 0 3.2mm; }
"""


def darken(hex_color: str, factor: float = 0.55) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % (int(r * factor), int(g * factor), int(b * factor))


# ----------------------------------------------------------------------------
# 2. Parse the source HTML, give every heading a stable id, build the TOC.
# ----------------------------------------------------------------------------
def build_document(src_html: str, args) -> str:
    soup = BeautifulSoup(src_html, "html.parser")

    # Title: CLI flag > <title> > first <h1> > filename
    title = args.title
    if not title:
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text(" ", strip=True)
        else:
            title = Path(args.input).stem

    body = soup.body or soup
    if not args.keep_styles:
        for tag in body.find_all(["style", "script", "link"]):
            tag.decompose()

    # Headings -> ids + TOC entries
    entries = []
    max_level = args.toc_depth
    for n, h in enumerate(body.find_all(re.compile(r"^h[1-6]$")), start=1):
        level = int(h.name[1])
        if level > max_level:
            continue
        hid = h.get("id") or f"sec-{n}"
        h["id"] = hid
        entries.append((level, hid, h.get_text(" ", strip=True)))

    toc_html = "".join(
        f'<li class="l{lvl}"><a href="#{hid}">{html.escape(text)}</a></li>'
        for lvl, hid, text in entries
    )

    inner = body.decode_contents()
    date = args.date or datetime.date.today().strftime("%d %B %Y")
    meta = " &nbsp;•&nbsp; ".join(
        html.escape(x) for x in (args.author, date) if x
    )
    subtitle = f'<div class="subtitle">{html.escape(args.subtitle)}</div>' if args.subtitle else ""

    return f"""<!DOCTYPE html>
<html lang="{args.lang}"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<meta name="author" content="{html.escape(args.author or '')}"></head>
<body>
  <section class="cover">
    <div class="bar"></div>
    <h1>{html.escape(title)}</h1>
    {subtitle}
    <div class="meta">{meta}</div>
  </section>

  <section class="toc">
    <h2 class="toc-title">Contents</h2>
    <ul>{toc_html}</ul>
  </section>

  <main class="content">{inner}</main>
</body></html>"""


def main():
    ap = argparse.ArgumentParser(description="HTML -> polished PDF (cover, TOC, page numbers, EN/AR/BN)")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--title");  ap.add_argument("--subtitle")
    ap.add_argument("--author", default=""); ap.add_argument("--date")
    ap.add_argument("--accent", default="#0f4c81", help="brand colour (hex)")
    ap.add_argument("--page-size", default="A4", help="A4, Letter, ...")
    ap.add_argument("--toc-depth", type=int, default=2, help="deepest heading level in TOC (1-6)")
    ap.add_argument("--lang", default="en", help="default document language code")
    ap.add_argument("--keep-styles", action="store_true", help="keep <style> tags from source HTML")
    args = ap.parse_args()

    src_path = Path(args.input)
    src = src_path.read_text(encoding="utf-8")
    doc = build_document(src, args)

    css = CSS_TEMPLATE % dict(
        page_size=args.page_size,
        accent=args.accent,
        accent_dark=darken(args.accent),
        gold="#c9a227",
    )
    # base_url lets relative <img src="..."> in your HTML resolve correctly
    HTML(string=doc, base_url=str(src_path.resolve().parent)).write_pdf(
        args.output, stylesheets=[CSS(string=css)]
    )
    print(f"✓ wrote {args.output}")


if __name__ == "__main__":
    main()
