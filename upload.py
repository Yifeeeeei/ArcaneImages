import os
import shutil
import json
from tqdm import tqdm

BATCH_SIZE = 40


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


if __name__ == "__main__":

    commit_single_file("update.txt")
    commit_single_file("update.json")

    if not os.path.exists("output"):
        print("output directory does not exist!")
        exit(-1)
    all_files = get_all_files_in_dir_recursively("output")
    commit_and_push(all_files)
    print("All files uploaded successfully!")
