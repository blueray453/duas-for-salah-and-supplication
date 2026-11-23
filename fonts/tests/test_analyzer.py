from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "quran_font_analyzer.py"
SPEC = importlib.util.spec_from_file_location("quran_font_analyzer", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class AnalyzerTests(unittest.TestCase):
    def make_args(self, **overrides):
        values = dict(
            text_kind="hadith",
            label="test hadith",
            declared_layout=None,
            reference_dir=ROOT / "reference_texts",
        )
        values.update(overrides)
        return Namespace(**values)

    def test_hadith_detects_perso_arabic_codepoints(self):
        text = (ROOT / "samples" / "hadith_quranohadith_original.txt").read_text(encoding="utf-8")
        result = module.analyze_text(text, self.make_args())
        found = set(result["unique_perso_arabic_codepoints"])
        self.assertTrue({"U+06A9", "U+06C1", "U+06C3", "U+06CC", "U+06D4", "U+06F4"}.issubset(found))
        self.assertEqual(result["layout_analysis"]["status"], "Arabic prose / hadith sample")
        self.assertTrue(result["encoding_observations"]["has_perso_arabic_associated_characters"])

    def test_text_encoding_observations_compare_arabic_and_perso_forms(self):
        text = "ك ک ي ی ه ہ ة ۃ ١ ۱"
        result = module.analyze_text(text, self.make_args())
        pairs = result["encoding_observations"]["arabic_vs_perso_character_pairs"]
        self.assertEqual(pairs["kaf"]["Arabic_Kaf_U+0643_count"], 1)
        self.assertEqual(pairs["kaf"]["Persian_Keheh_U+06A9_count"], 1)
        self.assertEqual(result["encoding_observations"]["digit_counts"]["arabic_indic_digits"], 1)
        self.assertEqual(result["encoding_observations"]["digit_counts"]["extended_arabic_indic_persian_style_digits"], 1)

    def test_no_automatic_uthmani_or_imlaei_claim_without_reference(self):
        text = (ROOT / "samples" / "al_fatihah_uthmani.txt").read_text(encoding="utf-8")
        result = module.analyze_text(text, self.make_args(text_kind="quran", label="Al-Fatihah"))
        self.assertEqual(result["layout_analysis"]["status"], "Heuristic evidence only")
        self.assertIn("U+0671", result["layout_analysis"]["signals"]["uthmani_associated_codepoints"])

    def test_exact_reference_comparison_classifies_reference_label(self):
        text = (ROOT / "samples" / "al_fatihah_uthmani.txt").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp)
            (ref_dir / "uthmani_alfatihah.txt").write_text(text, encoding="utf-8")
            result = module.analyze_text(text, self.make_args(text_kind="quran", label="Al-Fatihah", reference_dir=ref_dir))
        self.assertEqual(result["layout_analysis"]["classification"], "Uthmani")
        self.assertEqual(result["layout_analysis"]["status"], "Strong reference-text match")

    def test_declared_layout_is_recorded_as_declared(self):
        result = module.analyze_text("بِسْمِ اللَّهِ", self.make_args(declared_layout="imlaei"))
        self.assertEqual(result["layout_analysis"]["classification"], "Imla'i / Simple")
        self.assertEqual(result["layout_analysis"]["status"], "Source-declared classification")

    def test_axis_dimensions_are_separate_and_declared(self):
        result = module.analyze_text(
            "بِسْمِ اللَّهِ",
            self.make_args(
                text_kind="quran",
                declared_orthography="uthmani",
                declared_riwayah="hafs",
                declared_script_tradition="madani",
                declared_typeface="naskh",
                encoding_model="unicode-text",
                page_layout="Madani 15-line",
            ),
        )
        dims = result["layout_analysis"]["dimensions"]
        self.assertEqual(dims["orthography"]["value"], "Uthmani")
        self.assertEqual(dims["riwayah"]["value"], "Hafs")
        self.assertEqual(dims["script_tradition"]["value"], "Madani")
        self.assertEqual(dims["typography"]["value"], "Naskh")
        self.assertEqual(dims["encoding_model"]["value"], "Unicode text")
        self.assertEqual(dims["page_layout"]["value"], "Madani 15-line")

    def test_reference_manifest_supplies_multiple_dimensions(self):
        text = (ROOT / "samples" / "al_fatihah_uthmani.txt").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            ref_dir = Path(tmp)
            (ref_dir / "passage.txt").write_text(text, encoding="utf-8")
            manifest = {
                "references": [{
                    "file": "passage.txt", "orthography": "Uthmani",
                    "riwayah": "Hafs", "script_tradition": "Madani / Uthmani",
                    "typography": "Naskh", "encoding_model": "Unicode text",
                    "page_layout": "Madani 15-line", "line_count": 15,
                    "mushaf_id": 5, "qf_field": "text_uthmani",
                    "source": "test reference fixture"
                }]
            }
            (ref_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = module.analyze_text(text, self.make_args(text_kind="quran", reference_dir=ref_dir))
        dims = result["layout_analysis"]["dimensions"]
        self.assertEqual(dims["orthography"]["value"], "Uthmani")
        self.assertEqual(dims["riwayah"]["value"], "Hafs")
        self.assertEqual(dims["typography"]["value"], "Naskh")
        self.assertEqual(dims["page_layout"]["value"], "Madani 15-line")

    def test_reference_filename_parses_indopak_nastaleeq_and_lines(self):
        metadata = module.parse_reference_filename(Path("indopak_hafs_nastaleeq_16_lines.txt"))
        self.assertEqual(metadata["orthography"], "IndoPak")
        self.assertEqual(metadata["riwayah"], "Hafs")
        self.assertEqual(metadata["typography"], "Nastaleeq")
        self.assertEqual(metadata["line_count"], 16)

    def test_mushaf_id_7_provides_indopak_16_line_layout(self):
        result = module.analyze_text("بِسْمِ اللَّهِ", self.make_args(text_kind="quran", mushaf_id=7))
        layout = result["layout_analysis"]
        self.assertEqual(layout["dimensions"]["orthography"]["value"], "IndoPak")
        self.assertIn("16 lines", layout["dimensions"]["page_layout"]["value"])

    def test_mushaf_id_records_page_count_from_catalog(self):
        result = module.analyze_text("بِسْمِ اللَّهِ", self.make_args(text_kind="quran", mushaf_id=7))
        self.assertEqual(result["layout_analysis"]["mushaf_metadata"]["page_count"], 548)

    def test_qf_qpc_nastaleeq_field_records_nastaleeq_without_claiming_indopak(self):
        result = module.analyze_text(
            "بِسْمِ اللَّهِ",
            self.make_args(text_kind="quran", qf_field="text_qpc_nastaleeq"),
        )
        dims = result["layout_analysis"]["dimensions"]
        self.assertEqual(dims["typography"]["value"], "Nastaleeq")
        self.assertEqual(dims["script_tradition"]["value"], "QPC Nastaleeq representation")
        self.assertNotEqual(dims["script_tradition"]["value"], "IndoPak")

    def test_qf_field_indopak_nastaleeq_supplies_separate_dimensions(self):
        result = module.analyze_text(
            "بِسْمِ اللَّهِ",
            self.make_args(text_kind="quran", qf_field="text_indopak_nastaleeq"),
        )
        layout = result["layout_analysis"]
        dims = layout["dimensions"]
        self.assertEqual(dims["orthography"]["value"], "IndoPak")
        self.assertEqual(dims["script_tradition"]["value"], "IndoPak")
        self.assertEqual(dims["typography"]["value"], "Nastaleeq")
        self.assertEqual(dims["orthography"]["status"], "Source-field declared")
        self.assertEqual(layout["qf_field"], "text_indopak_nastaleeq")

    def test_qf_field_qpc_hafs_declares_hafs_but_not_page_layout(self):
        result = module.analyze_text(
            "بِسْمِ اللَّهِ",
            self.make_args(text_kind="quran", qf_field="text_qpc_hafs"),
        )
        dims = result["layout_analysis"]["dimensions"]
        self.assertEqual(dims["orthography"]["value"], "Uthmani")
        self.assertEqual(dims["riwayah"]["value"], "Hafs")
        self.assertEqual(dims["script_tradition"]["value"], "QPC / Madani")
        self.assertEqual(dims["page_layout"]["status"], "Not inferable from text alone")

    def test_qf_glyph_code_field_does_not_invent_orthography(self):
        result = module.analyze_text(
            "بِسْمِ اللَّهِ",
            self.make_args(text_kind="quran", qf_field="code_v2"),
        )
        dims = result["layout_analysis"]["dimensions"]
        self.assertEqual(dims["encoding_model"]["value"], "QPC glyph code V2 (not ordinary Unicode verse text)")
        self.assertEqual(dims["orthography"]["status"], "Not inferable from text alone")

    def test_adobe_arabic_maps_hadith_text(self):
        text = (ROOT / "samples" / "hadith_quranohadith_original.txt").read_text(encoding="utf-8")
        cps = {ord(ch) for ch in text if not ch.isspace()}
        record = module.inspect_font(ROOT / "font-arabic2.woff2", cps)
        self.assertIsNone(record.get("error"))
        self.assertIn("Adobe Arabic", record["family"])
        self.assertEqual(record["text_coverage"]["mapped"], len(cps))

    def test_current_folder_font_discovery_includes_new_archive_fonts(self):
        found = {p.name for p in module.find_font_files(ROOT)}
        self.assertIn("UthmanTN1.otf", found)
        self.assertIn("fontawesome-webfont.woff2", found)
        self.assertIn("font-arabic2.woff2", found)
        self.assertGreaterEqual(len(found), 57)

    def test_font_discovery_tracks_additions_and_removals(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            direct_font = folder / "added.ttf"
            nested_dir = folder / "nested"
            nested_dir.mkdir()
            nested_font = nested_dir / "nested.otf"
            direct_font.write_bytes(b"test")
            nested_font.write_bytes(b"test")
            self.assertEqual([p.name for p in module.find_font_files(folder)], ["added.ttf"])
            self.assertEqual(len(module.find_font_files(folder, recursive=True)), 2)
            direct_font.unlink()
            self.assertEqual(module.find_font_files(folder), [])

    def test_positional_text_only_cli(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "ك ی ہ", "--text-only"],
            text=True, capture_output=True, check=True,
        )
        self.assertIn("TEXT CHARACTERISTICS", result.stdout)
        self.assertIn("Perso-Arabic-associated characters present: True", result.stdout)

    def test_stdin_json_cli(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--stdin", "--text-only", "--format", "json"],
            input="ك ی ہ", text=True, capture_output=True, check=True,
        )
        parsed = json.loads(result.stdout)
        self.assertTrue(parsed["encoding_observations"]["has_perso_arabic_associated_characters"])

    def test_qf_field_cli_reports_indopak_nastaleeq(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--text", "بِسْمِ اللَّهِ", "--text-kind", "quran", "--qf-field", "text_indopak_nastaleeq", "--text-only", "--format", "json"],
            text=True, capture_output=True, check=True,
        )
        parsed = json.loads(result.stdout)
        dimensions = parsed["layout_analysis"]["dimensions"]
        self.assertEqual(dimensions["typography"]["value"], "Nastaleeq")
        self.assertEqual(dimensions["orthography"]["status"], "Source-field declared")

    def test_text_file_text_only_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            text_file = Path(tmp) / "sample.txt"
            text_file.write_text("ك ک ي ی", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--text-file", str(text_file), "--text-only"],
                text=True, capture_output=True, check=True,
            )
        self.assertIn("Perso-Arabic-associated characters present: True", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
