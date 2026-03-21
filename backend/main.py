import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from webhook import router as webhook_router
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Code Reviewer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(webhook_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/reviews/{repo_owner}/{repo_name}")
def get_reviews(repo_owner: str, repo_name: str):
    from database import get_reviews_by_repo
    repo_full_name = f"{repo_owner}/{repo_name}"
    return get_reviews_by_repo(repo_full_name)
