import os
import shutil
import json
from tqdm import tqdm
import subprocess

BATCH_SIZE = 40


def get_latest_commit():
    # Run the git log command to get the latest commit hash
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE, text=True
    )

    # Strip any trailing newline or spaces
    latest_commit = result.stdout.strip()
    return latest_commit


def get_modified_and_added_files(commit1, commit2):
    # Run the git diff command with --diff-filter=AM to ignore deleted files
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=AM", commit1, commit2],
        stdout=subprocess.PIPE,
        text=True,
    )

    # Split the result by newline to get individual file names
    files = result.stdout.splitlines()
    return files


def get_all_files_in_dir_recursively(dirname):
    all_files = []
    for root, dirs, files in os.walk(dirname):
        for file in files:
            all_files.append(os.path.join(root, file))
    return all_files


def commit_and_push(all_files):
    batch_num = len(all_files) // BATCH_SIZE
    if len(all_files) % BATCH_SIZE != 0:
        batch_num += 1

    for batch_idx in tqdm(range(batch_num)):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min((batch_idx + 1) * BATCH_SIZE, len(all_files))
        batch_files = all_files[start_idx:end_idx]

        cmd_add = "git add " + " ".join(batch_files)
        os.system(cmd_add)
        cmt_commit = (
            'git commit -m "upload batch '
            + str(batch_idx + 1)
            + " of "
            + str(batch_num)
            + '"'
        )
        os.system(cmt_commit)
        os.system("git push")


def commit_single_file(file_path):
    if not os.path.exists(file_path):
        print(file_path + " does not exist!")
        exit(-1)
    os.system("git add " + file_path)
    os.system('git commit -m "upload ' + file_path + '"')
    os.system("git push")
    print(file_path + " uploaded successfully!")


def filter_card_only(files):
    card_numbers = []
    for file in files:
        number_str = file.split("/")[-1].split(".")[0]
        # see if it can be converted to an integer
        number = None
        try:
            number = int(number_str)
            card_numbers.append(number)
        except:
            continue
    return card_numbers


if __name__ == "__main__":
    last_commit_hash = get_latest_commit()

    commit_single_file("update.txt")
    if not os.path.exists("output"):
        print("output directory does not exist!")
        exit(-1)
    all_files = get_all_files_in_dir_recursively("output")
    commit_and_push(all_files)
    print("All files uploaded successfully!")

    now_commit_hash = get_latest_commit()
    modified_files = get_modified_and_added_files(last_commit_hash, now_commit_hash)

    modified_cards = filter_card_only(modified_files)
    print("Modified cards: ", modified_cards)

    with open("update.json", "w") as f:
        json.dump(modified_cards, f)
    commit_single_file("update.json")
    print("upload completed")
