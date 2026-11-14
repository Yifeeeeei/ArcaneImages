"""Sync rendered cards and original artwork from arcane_go.

The default keeps the existing upload/commit/push workflow. Use --local-only
for local review, or --dry-run to inspect the copy plan without changing files.
Original image bytes and directory names are preserved. No redesigned output
is copied by this script.
"""

import argparse
import filecmp
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


BATCH_SIZE = 40
REPO_DIR = Path(__file__).resolve().parent
ARCANE_GO_DIR = Path(os.environ.get("ARCANE_GO_REPO", REPO_DIR.parent / "arcane_go")).resolve()
IMAGE_EXTENSIONS = frozenset((".jpg", ".jpeg", ".png", ".webp", ".avif"))
ASSET_ROOTS = ("output", "drawings")


def run_git(*args, capture_output=False, check=True):
    return subprocess.run(
        ["git", *args], cwd=REPO_DIR, check=check, text=True, encoding="utf-8",
        stdout=subprocess.PIPE if capture_output else None,
    )


def source_files(source, images_only=False):
    if not source.is_dir():
        raise FileNotFoundError(f"source directory does not exist: {source}")
    return sorted(
        (p for p in source.rglob("*") if p.is_file()
         and not p.is_symlink()
         and (not images_only or p.suffix.lower() in IMAGE_EXTENSIONS)),
        key=lambda p: p.relative_to(source).as_posix(),
    )


def artwork_index(files, source):
    images = {}
    for path in files:
        if not re.fullmatch(r"\d{7}", path.stem):
            continue
        relative = "drawings/" + path.relative_to(source).as_posix()
        if path.stem in images:
            raise ValueError(f"duplicate artwork for {path.stem}: {images[path.stem]} / {relative}")
        images[path.stem] = relative
    return {"version": 1, "images": dict(sorted(images.items()))}


def sync_tree(source, destination, files, dry_run=False):
    copied = 0
    unchanged = 0
    for source_file in files:
        destination_file = destination / source_file.relative_to(source)
        if destination_file.is_file() and filecmp.cmp(source_file, destination_file, shallow=False):
            unchanged += 1
            continue
        if not dry_run:
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination_file)
        copied += 1
    print(f"{'Would sync' if dry_run else 'Synced'} {source.name}: {copied} copied, {unchanged} unchanged")
    return copied, unchanged


def write_json(path, data, dry_run=False):
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return True


def sync_generated_outputs(dry_run=False):
    output = ARCANE_GO_DIR / "output"
    drawings = ARCANE_GO_DIR / "drawings"
    # Inventory and validate both sources before the first write.
    rendered_files = source_files(output)
    drawing_files = source_files(drawings, images_only=True)
    if not rendered_files or not drawing_files:
        raise ValueError("source output and drawings must both contain files")
    index = artwork_index(drawing_files, drawings)
    if not index["images"]:
        raise ValueError("no seven-digit original artwork IDs were found")
    sync_tree(output, REPO_DIR / "output", rendered_files, dry_run)
    sync_tree(drawings, REPO_DIR / "drawings", drawing_files, dry_run)
    write_json(REPO_DIR / "drawings" / "index.json", index, dry_run)
    print(f"Original artwork index: {len(index['images'])} cards")
    return index


def get_changed_output_files():
    result = run_git(
        "-c", "status.renames=false", "status", "--porcelain=v1", "-z",
        "--untracked-files=all", "--", *ASSET_ROOTS, capture_output=True,
    )
    # NUL-delimited paths preserve spaces, Unicode and quotes.
    return [entry[3:] for entry in result.stdout.split("\0") if entry]


def filter_card_ids(files):
    ids = set()
    for file_path in files:
        path = Path(file_path.replace("\\", "/"))
        if path.parts and path.parts[0] in ASSET_ROOTS and re.fullmatch(r"\d{7}", path.stem):
            ids.add(int(path.stem))
    return sorted(ids)


def commit_and_push(files):
    batches = [files[i:i + BATCH_SIZE] for i in range(0, len(files), BATCH_SIZE)]
    for number, batch in enumerate(batches, 1):
        run_git("add", "--", *batch)
        run_git("commit", "-m", f"upload assets batch {number} of {len(batches)}")
        run_git("push")
    if not batches:
        print("No card or artwork files changed.")


def commit_single_file(file_path):
    if not (REPO_DIR / file_path).exists():
        raise FileNotFoundError(file_path)
    run_git("add", "--", file_path)
    if run_git("diff", "--cached", "--quiet", "--", file_path, check=False).returncode == 0:
        return
    run_git("commit", "-m", f"upload {file_path}")
    run_git("push")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-only", action="store_true", help="sync files without staging, commits or pushes")
    parser.add_argument("--dry-run", action="store_true", help="show the sync plan without writing or publishing")
    args = parser.parse_args(argv)
    if args.dry_run:
        sync_generated_outputs(dry_run=True)
        print("Dry run complete; no files or Git state changed.")
        return
    if not args.local_only and run_git("diff", "--cached", "--quiet", check=False).returncode != 0:
        raise RuntimeError("the index already contains staged changes; handle them before publishing")
    sync_generated_outputs()
    changed = get_changed_output_files()
    card_ids = filter_card_ids(changed)
    write_json(REPO_DIR / "update.json", card_ids)
    if args.local_only:
        print(f"Local sync complete: {len(card_ids)} changed card IDs; no staging, commits or pushes.")
        return
    commit_single_file("update.txt")
    commit_and_push(changed)
    commit_single_file("update.json")
    print("Upload complete.")


if __name__ == "__main__":
    main()
