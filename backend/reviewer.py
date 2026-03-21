import os
import re
import json
import requests
from dotenv import load_dotenv

load_dotenv()

HF_API_TOKEN = os.environ.get("HUGGINGFACE_API_TOKEN")
HF_MODEL = "bigcode/starcoder2-3b"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

HEADERS = {
    "Authorization": f"Bearer {HF_API_TOKEN}",
    "Content-Type": "application/json"
}


def build_prompt(formatted_diff):
    return f"""<review>
You are a senior software engineer doing a code review.
Analyze the following code changes and return a JSON array of issues found.

Each issue must have these fields:
- file: filename as a string
- line: line number as an integer
- severity: exactly one of "critical", "warning", "suggestion"
- category: exactly one of "security", "bug", "style", "performance"
- message: short clear explanation of the issue
- suggestion: fixed code as a string, or null if no fix needed

Rules:
- Only return a raw JSON array
- No markdown, no explanation, no extra text
- If no issues found return an empty array []

Code changes:
{formatted_diff}
</review>
JSON:"""


def call_hf_model(prompt):
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 800,
            "temperature": 0.1,
            "return_full_text": False,
            "stop": ["</s>", "<|endoftext|>"]
        }
    }

    try:
        response = requests.post(
            HF_API_URL,
            headers=HEADERS,
            json=payload,
            timeout=60
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
        match = re.search(r'\[.*?\]', raw_text, re.DOTALL)
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
            "message": "Model is warming up, please retry in 20 seconds",
            "comments": [],
            "score": None,
            "check_status": "pending",
            "summary": "Model loading."
        }

    if error == "rate_limited":
        return {
            "status": "rate_limited",
            "message": "HuggingFace rate limit hit, please retry shortly",
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
