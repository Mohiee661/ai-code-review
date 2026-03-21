import os
import re
import json
import requests
from dotenv import load_dotenv

load_dotenv()

HF_API_TOKEN = os.environ.get("HUGGINGFACE_API_TOKEN")
HF_MODEL = "microsoft/codereviewer"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

HEADERS = {
    "Authorization": f"Bearer {HF_API_TOKEN}",
    "Content-Type": "application/json"
}


def build_prompt(formatted_diff):
    return f"""You are an expert code reviewer. Review the following code changes and identify issues.

For each issue found, return a JSON array with objects containing these exact fields:
- file: the filename
- line: the line number (integer)
- severity: one of "critical", "warning", "suggestion"
- category: one of "security", "bug", "style", "performance"
- message: clear explanation of the issue
- suggestion: the corrected code (or null if no fix needed)

Code changes to review:
{formatted_diff}

Return only a valid JSON array. No explanation, no markdown, no extra text. Just the JSON array.
"""


def call_hf_model(prompt):
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 1000,
            "temperature": 0.2,
            "return_full_text": False
        }
    }

    response = requests.post(HF_API_URL, headers=HEADERS, json=payload)

    if response.status_code == 503:
        return None, "model_loading"

    if response.status_code != 200:
        return None, f"api_error_{response.status_code}"

    result = response.json()

    if isinstance(result, list) and len(result) > 0:
        return result[0].get("generated_text", ""), None

    return None, "empty_response"


def parse_model_response(raw_text):
    if not raw_text:
        return []

    try:
        match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError:
        pass

    return []


def calculate_score(comments):
    if not comments:
        return 100

    score = 100
    for comment in comments:
        severity = comment.get("severity", "")
        if severity == "critical":
            score -= 20
        elif severity == "warning":
            score -= 8
        elif severity == "suggestion":
            score -= 2

    return max(0, score)


def get_check_status(comments):
    for comment in comments:
        if comment.get("severity") == "critical":
            return "failed"
    return "passed"


def review_diff(formatted_diff):
    prompt = build_prompt(formatted_diff)
    raw_text, error = call_hf_model(prompt)

    if error == "model_loading":
        return {
            "status": "model_loading",
            "message": "Model is warming up, retry in 20 seconds",
            "comments": [],
            "score": None,
            "check_status": "pending"
        }

    if error:
        return {
            "status": "error",
            "message": error,
            "comments": [],
            "score": None,
            "check_status": "pending"
        }

    comments = parse_model_response(raw_text)
    score = calculate_score(comments)
    check_status = get_check_status(comments)

    return {
        "status": "success",
        "comments": comments,
        "score": score,
        "check_status": check_status,
        "summary": f"{len(comments)} issue(s) found. Score: {score}/100."
    }
