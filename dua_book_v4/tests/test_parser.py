"""Run:  python tests/test_parser.py
Checks that data/book.md parses to exactly the same data as data/book.json."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from md_parser import parse_markdown  # noqa: E402

md, warnings = parse_markdown((ROOT / "data" / "book.md").read_text(encoding="utf-8"), "book.md")
js = json.loads((ROOT / "data" / "book.json").read_text(encoding="utf-8"))
js.pop("_note", None)

assert not warnings, f"unexpected warnings: {warnings}"
assert md["meta"] == js["meta"], "meta differs"
assert md["languages"] == js["languages"], "languages differ"
assert md["duas"] == js["duas"], "duas differ"
assert md["about"] == js["about"], "about differs"

bad, w = parse_markdown("---\ntitle: t\nlanguages: [en, bn]\n---\n## A\n| x | y |\n|---|---|\n| one |\n")
assert any("padded/trimmed" in m for m in w), "misaligned table should warn"
print("all parser tests passed")
