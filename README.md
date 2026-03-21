# AI Code Reviewer

Automatically reviews GitHub pull requests using a HuggingFace model and posts inline feedback as GitHub comments.

## Stack

- FastAPI — webhook server
- HuggingFace Inference API — code review model
- Supabase — database
- React — dashboard (coming soon)

## Setup

1. Copy `.env.example` to `.env` and fill in your keys
2. `cd backend && pip install -r requirements.txt`
3. `uvicorn main:app --reload`