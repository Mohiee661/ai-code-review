from fastapi import FastAPI
from webhook import router as webhook_router
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Code Reviewer")

app.include_router(webhook_router)

@app.get("/health")
def health():
    return {"status": "ok"}
