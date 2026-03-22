import os
from github import Github
from dotenv import load_dotenv

load_dotenv()

github_client = Github(os.environ.get("GITHUB_ACCESS_TOKEN"))


def post_review_comments(repo_full_name, pr_number, comments, summary, check_status):
    repo = github_client.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)
    commit = repo.get_commit(pr.head.sha)

    review_comments = []
    for comment in comments:
        file_path = comment.get("file")
        line = comment.get("line")
        message = comment.get("message", "")
        severity = comment.get("severity", "suggestion")
        suggestion = comment.get("suggestion")

        if not file_path or not line:
            continue

        severity_label = {
            "critical": "🔴 Critical",
            "warning": "🟡 Warning",
            "suggestion": "🟢 Suggestion"
        }.get(severity, "💬 Note")

        body = f"**{severity_label}**\n\n{message}"

        if suggestion:
            body += f"\n\n**Suggested fix:**\n```\n{suggestion}\n```"

        try:
            review_comments.append({
                "path": file_path,
                "line": int(line),
                "body": body
            })
        except Exception:
            continue

    status_emoji = "✅" if check_status == "passed" else "❌"
    review_body = f"{status_emoji} **AI Code Review Complete**\n\n{summary}"

    if not review_comments:
        review_body += "\n\nNo specific line issues found."

    try:
        if review_comments:
            pr.create_review(
                commit=commit,
                body=review_body,
                event="COMMENT",
                comments=[
                    {
                        "path": c["path"],
                        "line": c["line"],
                        "body": c["body"]
                    }
                    for c in review_comments
                ]
            )
        else:
            pr.create_issue_comment(review_body)
    except Exception as e:
        pr.create_issue_comment(
            f"{review_body}\n\n*(Could not post inline comments: {str(e)})*"
        )
