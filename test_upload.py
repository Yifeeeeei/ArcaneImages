import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("asset_upload", Path(__file__).with_name("upload.py"))
upload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upload)


class UpdateTests(unittest.TestCase):
    def test_real_extensions_unicode_and_local_only(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); source = base / "source"; dest = base / "images"
            card = source / "output" / "基础包" / "1011001.jpg"
            art = source / "drawings" / "基础包" / "基础包-伙伴" / "1011001.webp"
            card.parent.mkdir(parents=True); art.parent.mkdir(parents=True); dest.mkdir()
            card.write_bytes(b"card"); art.write_bytes(b"original")
            (art.parent / "helper.py").write_text("do not copy")
            with patch.object(upload, "ARCANE_GO_DIR", source), patch.object(upload, "REPO_DIR", dest), patch.object(upload, "get_changed_output_files", return_value=["drawings/基础包/基础包-伙伴/1011001.webp"]), patch.object(upload, "run_git", side_effect=AssertionError("local mode must not mutate Git")):
                upload.main(["--local-only"])
                self.assertEqual((dest / art.relative_to(source)).read_bytes(), b"original")
                self.assertEqual((dest / card.relative_to(source)).read_bytes(), b"card")
                self.assertFalse((dest / art.relative_to(source).parent / "helper.py").exists())
                self.assertEqual(upload.artwork_index([art], source / "drawings")["images"]["1011001"], "drawings/基础包/基础包-伙伴/1011001.webp")
                self.assertFalse((dest / "new_output").exists())
                stamp = (dest / art.relative_to(source)).stat().st_mtime_ns
                upload.main(["--local-only"])
                self.assertEqual((dest / art.relative_to(source)).stat().st_mtime_ns, stamp)

    def test_dry_run_does_not_write_and_duplicate_ids_fail_before_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"; dest = Path(temp) / "dest"
            (source / "output").mkdir(parents=True); (source / "drawings").mkdir()
            (source / "output/1011001.jpg").write_bytes(b"card")
            (source / "drawings/1011001.png").write_bytes(b"art")
            with patch.object(upload, "ARCANE_GO_DIR", source), patch.object(upload, "REPO_DIR", dest):
                upload.main(["--dry-run"])
                self.assertFalse(dest.exists())
                (source / "drawings/1011001.webp").write_bytes(b"duplicate")
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    upload.main(["--local-only"])
                self.assertFalse(dest.exists())

    def test_numeric_updates_include_artwork_but_not_manifest(self):
        self.assertEqual(upload.filter_card_ids(["drawings/a/1011001.webp", "output/a/1011001.jpg", "drawings/b/4111001.png", "drawings/index.json"]), [1011001, 4111001])


if __name__ == "__main__":
    unittest.main()
