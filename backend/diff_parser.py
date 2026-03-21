import os
from github import Github
from dotenv import load_dotenv

load_dotenv()

github_client = Github(os.environ.get("GITHUB_ACCESS_TOKEN"))


def get_pr_diff(repo_full_name, pr_number):
    repo = github_client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    files = []

    for file in pr.get_files():
        if file.patch is None:
            continue

        lines = file.patch.split("\n")
        chunks = []
        current_line = 0

        for line in lines:
            if line.startswith("@@"):
                parts = line.split("+")
                if len(parts) > 1:
                    current_line = int(parts[1].split(",")[0].strip().split(" ")[0])
            elif line.startswith("+") and not line.startswith("+++"):
                chunks.append({
                    "type": "add",
                    "line_number": current_line,
                    "content": line[1:]
                })
                current_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                chunks.append({
                    "type": "delete",
                    "line_number": current_line,
                    "content": line[1:]
                })
            else:
                chunks.append({
                    "type": "context",
                    "line_number": current_line,
                    "content": line
                })
                current_line += 1

        files.append({
            "filename": file.filename,
            "status": file.status,
            "additions": file.additions,
            "deletions": file.deletions,
            "chunks": chunks,
            "raw_patch": file.patch
        })

    return {
        "pr_number": pr_number,
        "title": pr.title,
        "author": pr.user.login,
        "base_branch": pr.base.ref,
        "commit_sha": pr.head.sha,
        "files": files
    }


def format_diff_for_model(files):
    formatted = []

    for file in files:
        if not file["chunks"]:
            continue

        block = f"File: {file['filename']}\n"
        block += f"Status: {file['status']} (+{file['additions']} -{file['deletions']})\n"
        block += "Changes:\n"

        for chunk in file["chunks"]:
            if chunk["type"] == "add":
                block += f"+ (line {chunk['line_number']}) {chunk['content']}\n"
            elif chunk["type"] == "delete":
                block += f"- {chunk['content']}\n"
            else:
                block += f"  {chunk['content']}\n"

        formatted.append(block)

    return "\n---\n".join(formatted)
