import os
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException
from dotenv import load_dotenv
from diff_parser import get_pr_diff, format_diff_for_model
from reviewer import review_diff
from database import (
    insert_pull_request,
    insert_review,
    insert_comment,
    insert_file_reviewed
)
from github_comments import post_review_comments

load_dotenv()

router = APIRouter()
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET")


def verify_signature(payload: bytes, signature: str) -> bool:
    if not signature:
        return False
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def webhook(request: Request):
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(payload_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event = request.headers.get("X-GitHub-Event", "")

    if event != "pull_request":
        return {"message": "ignored"}

    action = payload.get("action", "")
    if action not in ["opened", "synchronize"]:
        return {"message": "ignored"}

    pr_data = payload["pull_request"]
    repo_full_name = payload["repository"]["full_name"]
    pr_number = pr_data["number"]
    author = pr_data["user"]["login"]
    title = pr_data["title"]
    base_branch = pr_data["base"]["ref"]

    pr_record = insert_pull_request(
        pr_number=pr_number,
        repo=repo_full_name,
        author=author,
        title=title,
        base_branch=base_branch
    )

    diff_data = get_pr_diff(repo_full_name, pr_number)
    formatted_diff = format_diff_for_model(diff_data["files"])
    review_result = review_diff(formatted_diff)

    review_record = insert_review(
        pr_id=pr_record["id"],
        commit_sha=diff_data["commit_sha"],
        score=review_result["score"],
        summary=review_result["summary"],
        check_status=review_result["check_status"],
        llm_model="microsoft/codereviewer"
    )

    for file in diff_data["files"]:
        insert_file_reviewed(
            review_id=review_record["id"],
            file_path=file["filename"],
            additions=file["additions"],
            deletions=file["deletions"],
            issues_found=len([
                c for c in review_result["comments"]
                if c.get("file") == file["filename"]
            ])
        )

    for comment in review_result["comments"]:
        insert_comment(
            review_id=review_record["id"],
            file_path=comment.get("file", "unknown"),
            line_number=comment.get("line", 0),
            severity=comment.get("severity", "suggestion"),
            category=comment.get("category", "style"),
            message=comment.get("message", ""),
            suggestion=comment.get("suggestion", None)
        )

    post_review_comments(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        comments=review_result["comments"],
        summary=review_result["summary"],
        check_status=review_result["check_status"]
    )

    return {
        "message": "review complete",
        "pr": pr_number,
        "score": review_result["score"],
        "issues": len(review_result["comments"]),
        "check_status": review_result["check_status"]
    }
