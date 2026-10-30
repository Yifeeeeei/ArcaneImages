import json
import os
from pathlib import Path
import shutil
import subprocess

from tqdm import tqdm


BATCH_SIZE = 40
REPO_DIR = Path(__file__).resolve().parent
ARCANE_GO_DIR = Path(
    os.environ.get("ARCANE_GO_REPO", REPO_DIR.parent / "arcane_go")
).resolve()
OUTPUT_MAPPINGS = (
    (ARCANE_GO_DIR / "output", REPO_DIR / "output"),
    (ARCANE_GO_DIR / "new_output", REPO_DIR / "new_output"),
)


def run_git(*args, capture_output=False, check=True):
    return subprocess.run(
        ["git", *args],
        cwd=REPO_DIR,
        check=check,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE if capture_output else None,
    )


def get_latest_commit():
    return run_git("rev-parse", "HEAD", capture_output=True).stdout.strip()


def get_modified_and_added_files(commit1, commit2):
    result = run_git(
        "diff",
        "--name-only",
        "--diff-filter=AM",
        commit1,
        commit2,
        capture_output=True,
    )
    return result.stdout.splitlines()


def sync_tree(source, destination):
    if not source.is_dir():
        raise FileNotFoundError(f"generated output directory does not exist: {source}")

    copied = 0
    for source_file in source.rglob("*"):
        if not source_file.is_file():
            continue
        relative_path = source_file.relative_to(source)
        destination_file = destination / relative_path
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination_file)
        copied += 1
    print(f"Synced {copied} files: {source} -> {destination}")


def sync_generated_outputs():
    for source, destination in OUTPUT_MAPPINGS:
        sync_tree(source, destination)


def get_changed_output_files():
    result = run_git(
        "-c",
        "core.quotepath=false",
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        "output",
        "new_output",
        capture_output=True,
    )
    files = []
    for line in result.stdout.splitlines():
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path.strip('"'))
    return files


def commit_and_push(files):
    batches = [files[index : index + BATCH_SIZE] for index in range(0, len(files), BATCH_SIZE)]
    if not batches:
        print("No generated card files changed.")
        return

    for batch_index, batch_files in enumerate(tqdm(batches), start=1):
        run_git("add", "--", *batch_files)
        run_git("commit", "-m", f"upload batch {batch_index} of {len(batches)}")
        run_git("push")


def commit_single_file(file_path):
    path = REPO_DIR / file_path
    if not path.exists():
        raise FileNotFoundError(f"{file_path} does not exist")

    run_git("add", "--", file_path)
    staged = run_git(
        "diff", "--cached", "--quiet", "--", file_path, check=False
    )
    if staged.returncode == 0:
        print(f"{file_path} has no changes.")
        return
    run_git("commit", "-m", f"upload {file_path}")
    run_git("push")
    print(f"{file_path} uploaded successfully!")


def filter_card_ids(files, new_schema=False):
    card_ids = []
    prefix = "new_output/" if new_schema else "output/"
    for file_path in files:
        normalized = file_path.replace("\\", "/")
        if not normalized.startswith(prefix):
            continue
        card_id = Path(normalized).stem
        if new_schema:
            if card_id and not card_id.isdigit():
                card_ids.append(card_id)
        elif card_id.isdigit():
            card_ids.append(int(card_id))
    return sorted(set(card_ids))


def write_update_file(file_path, card_ids):
    with (REPO_DIR / file_path).open("w", encoding="utf-8") as file:
        json.dump(card_ids, file, ensure_ascii=False)
        file.write("\n")
    commit_single_file(file_path)


def main():
    os.chdir(REPO_DIR)
    last_commit_hash = get_latest_commit()

    sync_generated_outputs()
    commit_single_file("update.txt")
    commit_and_push(get_changed_output_files())

    now_commit_hash = get_latest_commit()
    modified_files = get_modified_and_added_files(last_commit_hash, now_commit_hash)
    modified_cards = filter_card_ids(modified_files)
    modified_new_cards = filter_card_ids(modified_files, new_schema=True)
    print("Modified legacy cards:", modified_cards)
    print("Modified redesigned cards:", modified_new_cards)

    write_update_file("update.json", modified_cards)
    write_update_file("new_update.json", modified_new_cards)
    print("upload completed")


if __name__ == "__main__":
    main()
