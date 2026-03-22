import os
import re
import json
import requests
from dotenv import load_dotenv

load_dotenv()

HF_API_TOKEN = os.environ.get("HUGGINGFACE_API_TOKEN")
HF_MODEL = "mistralai/Mistral-7B-Instruct-v0.2"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

HEADERS = {
    "Authorization": f"Bearer {HF_API_TOKEN}",
    "Content-Type": "application/json"
}


def build_prompt(formatted_diff):
    return f"""<s>[INST] You are a senior software engineer performing a code review.

Analyze the following code changes and identify ALL issues including security vulnerabilities, bugs, hardcoded secrets, SQL injection, and bad practices.

Return ONLY a valid JSON array. No explanation, no markdown, no extra text.

Each object in the array must have exactly these fields:
- "file": filename string
- "line": line number integer
- "severity": one of "critical", "warning", "suggestion"
- "category": one of "security", "bug", "style", "performance"
- "message": explanation string
- "suggestion": fixed code string or null

If no issues found return empty array [].

Code changes to review:
{formatted_diff}
[/INST]"""


def call_hf_model(prompt):
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 1000,
            "temperature": 0.1,
            "return_full_text": False,
            "stop": ["</s>"]
        }
    }

    try:
        response = requests.post(
            HF_API_URL,
            headers=HEADERS,
            json=payload,
            timeout=120
        )

        if response.status_code == 503:
            return None, "model_loading"

        if response.status_code == 429:
            return None, "rate_limited"

        if response.status_code != 200:
            return None, f"api_error_{response.status_code}"

        result = response.json()

        if isinstance(result, list) and len(result) > 0:
            return result[0].get("generated_text", ""), None

        return None, "empty_response"

    except requests.exceptions.Timeout:
        return None, "timeout"

    except Exception as e:
        return None, str(e)


def parse_model_response(raw_text):
    if not raw_text:
        return []

    try:
        match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return parsed
    except json.JSONDecodeError:
        pass

    return []


def calculate_score(comments):
    if not comments:
        return 100

    score = 100
    deductions = {
        "critical": 20,
        "warning": 8,
        "suggestion": 2
    }

    for comment in comments:
        severity = comment.get("severity", "suggestion")
        score -= deductions.get(severity, 2)

    return max(0, score)


def get_check_status(comments):
    for comment in comments:
        if comment.get("severity") == "critical":
            return "failed"
    return "passed"


def get_summary(comments, score):
    if not comments:
        return f"No issues found. Score: {score}/100."

    critical = len([c for c in comments if c.get("severity") == "critical"])
    warnings = len([c for c in comments if c.get("severity") == "warning"])
    suggestions = len([c for c in comments if c.get("severity") == "suggestion"])

    parts = []
    if critical:
        parts.append(f"{critical} critical")
    if warnings:
        parts.append(f"{warnings} warning(s)")
    if suggestions:
        parts.append(f"{suggestions} suggestion(s)")

    return f"{', '.join(parts)} found. Score: {score}/100."


def review_diff(formatted_diff):
    if not formatted_diff or not formatted_diff.strip():
        return {
            "status": "success",
            "comments": [],
            "score": 100,
            "check_status": "passed",
            "summary": "No changes to review."
        }

    prompt = build_prompt(formatted_diff)
    raw_text, error = call_hf_model(prompt)

    if error == "model_loading":
        return {
            "status": "model_loading",
            "message": "Model is warming up, retry in 30 seconds",
            "comments": [],
            "score": None,
            "check_status": "pending",
            "summary": "Model loading."
        }

    if error == "rate_limited":
        return {
            "status": "rate_limited",
            "message": "Rate limit hit, retry shortly",
            "comments": [],
            "score": None,
            "check_status": "pending",
            "summary": "Rate limited."
        }

    if error:
        return {
            "status": "error",
            "message": error,
            "comments": [],
            "score": None,
            "check_status": "pending",
            "summary": "Review failed."
        }

    comments = parse_model_response(raw_text)
    score = calculate_score(comments)
    check_status = get_check_status(comments)
    summary = get_summary(comments, score)

    return {
        "status": "success",
        "comments": comments,
        "score": score,
        "check_status": check_status,
        "summary": summary
    }
