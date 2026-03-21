import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")
supabase: Client = create_client(url, key)


def insert_pull_request(pr_number, repo, author, title, base_branch):
    data = {
        "github_pr_number": pr_number,
        "repo_full_name": repo,
        "author": author,
        "title": title,
        "base_branch": base_branch,
        "status": "open"
    }
    result = supabase.table("pull_requests").insert(data).execute()
    return result.data[0]


def insert_review(pr_id, commit_sha, score, summary, check_status, llm_model):
    data = {
        "pr_id": pr_id,
        "commit_sha": commit_sha,
        "score": score,
        "summary": summary,
        "check_status": check_status,
        "llm_model": llm_model
    }
    result = supabase.table("reviews").insert(data).execute()
    return result.data[0]


def insert_comment(review_id, file_path, line_number, severity, category, message, suggestion=None):
    data = {
        "review_id": review_id,
        "file_path": file_path,
        "line_number": line_number,
        "severity": severity,
        "category": category,
        "message": message,
        "suggestion": suggestion,
        "resolved": False
    }
    result = supabase.table("comments").insert(data).execute()
    return result.data[0]


def insert_file_reviewed(review_id, file_path, additions, deletions, issues_found):
    data = {
        "review_id": review_id,
        "file_path": file_path,
        "additions": additions,
        "deletions": deletions,
        "issues_found": issues_found
    }
    result = supabase.table("files_reviewed").insert(data).execute()
    return result.data[0]


def get_reviews_by_repo(repo):
    result = supabase.table("pull_requests")\
        .select("*, reviews(*)")\
        .eq("repo_full_name", repo)\
        .execute()
    return result.data


def mark_comment_resolved(comment_id):
    result = supabase.table("comments")\
        .update({"resolved": True})\
        .eq("id", comment_id)\
        .execute()
    return result.data
