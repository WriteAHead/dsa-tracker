import os
import re
import json
import requests
from pathlib import Path
from bs4 import BeautifulSoup

CF_USERNAME = os.environ.get("CF_USERNAME", "writeAhead")
LC_USERNAME = os.environ.get("LC_USERNAME", "writeAhead")

LANG_MAP = {
    "cpp": "cpp", "c++": "cpp", "gnu c++": "cpp", "gnu c++17": "cpp", "gnu c++20": "cpp",
    "python": "py", "python3": "py", "py": "py", "pypy3": "py",
    "java": "java", "javascript": "js", "typescript": "ts",
    "c": "c", "c#": "cs", "csharp": "cs", "go": "go", "golang": "go",
    "rust": "rs", "kotlin": "kt", "swift": "swift"
}

def clean_slug(text: str) -> str:
    return re.sub(r"[^\w\-]", "_", text).strip("_")

def get_file_extension(language_str: str) -> str:
    lang_lower = language_str.lower()
    for key, ext in LANG_MAP.items():
        if key in lang_lower:
            return ext
    return "txt"

# -------------------------------------------------------------------
# CODEFORCES SYNC (Fetches full source code via web scraping)
# -------------------------------------------------------------------
def sync_codeforces():
    print(f"--- Fetching Codeforces submissions for {CF_USERNAME} ---")
    url = f"https://codeforces.com/api/user.status?handle={CF_USERNAME}&from=1&count=20"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        res = requests.get(url, headers=headers, timeout=15)
        data = res.json()
        if data.get("status") != "OK":
            print(f"Codeforces API error: {data.get('comment')}")
            return
    except Exception as e:
        print(f"Failed to query Codeforces: {e}")
        return

    accepted_subs = [s for s in data.get("result", []) if s.get("verdict") == "OK"]

    for sub in accepted_subs:
        problem = sub.get("problem", {})
        contest_id = problem.get("contestId")
        index = problem.get("index")
        name = problem.get("name", "Unknown")
        lang = sub.get("programmingLanguage", "")
        sub_id = sub.get("id")

        if not contest_id or not index or not sub_id:
            continue

        folder_name = clean_slug(f"{contest_id}{index}_{name}")
        target_dir = Path("Codeforces") / folder_name
        ext = get_file_extension(lang)
        solution_file = target_dir / f"solution.{ext}"

        if solution_file.exists():
            continue

        # Fetch actual code string from CF submission page
        sub_url = f"https://codeforces.com/contest/{contest_id}/submission/{sub_id}"
        code_content = ""
        try:
            page_res = requests.get(sub_url, headers=headers, timeout=15)
            soup = BeautifulSoup(page_res.text, "html.parser")
            source_elem = soup.find("pre", id="program-source-code")
            if source_elem:
                code_content = source_elem.get_text()
        except Exception as err:
            print(f"Could not scrape code for CF sub {sub_id}: {err}")

        target_dir.mkdir(parents=True, exist_ok=True)

        # Write README
        problem_url = f"https://codeforces.com/problemset/problem/{contest_id}/{index}"
        readme_file = target_dir / "README.md"
        readme_content = f"# {contest_id}{index} - {name}\n\n" \
                         f"- **Problem URL:** [{problem_url}]({problem_url})\n" \
                         f"- **Language:** {lang}\n" \
                         f"- **Submission ID:** {sub_id}\n"
        readme_file.write_text(readme_content, encoding="utf-8")

        # Write actual code
        if not code_content:
            code_content = f"// Codeforces Submission ID: {sub_id}\n// Code scraping restricted or submission page unavailable."

        solution_file.write_text(code_content, encoding="utf-8")
        print(f"[Codeforces] Synced code for: {folder_name}")

# -------------------------------------------------------------------
# LEETCODE SYNC (Fetches recent AC problem links & code snippets)
# -------------------------------------------------------------------
def sync_leetcode():
    print(f"--- Fetching LeetCode submissions for {LC_USERNAME} ---")
    url = f"https://alfa-leetcode-api.onrender.com/acSubmission?username={LC_USERNAME}&limit=10"

    try:
        res = requests.get(url, timeout=15)
        data = res.json()
        ac_list = data.get("submission", []) if isinstance(data, dict) else []
    except Exception as e:
        print(f"Failed to fetch LeetCode data: {e}")
        return

    if not ac_list:
        print("No recent accepted submissions found for LeetCode.")
        return

    for sub in ac_list:
        title = sub.get("title")
        slug = sub.get("titleSlug")
        lang = sub.get("lang", "txt")
        code = sub.get("code", "")

        if not slug:
            continue

        folder_name = clean_slug(slug)
        target_dir = Path("LeetCode") / folder_name
        ext = get_file_extension(lang)
        solution_file = target_dir / f"solution.{ext}"

        if solution_file.exists():
            continue

        target_dir.mkdir(parents=True, exist_ok=True)

        problem_url = f"https://leetcode.com/problems/{slug}/"
        readme_file = target_dir / "README.md"
        readme_content = f"# {title}\n\n" \
                         f"- **Problem Link:** [{problem_url}]({problem_url})\n" \
                         f"- **Language:** {lang}\n"
        readme_file.write_text(readme_content, encoding="utf-8")

        if not code:
            code = f"# LeetCode Submission - {title}\n# Link: {problem_url}\n"

        solution_file.write_text(code, encoding="utf-8")
        print(f"[LeetCode] Synced code for: {folder_name}")

if __name__ == "__main__":
    sync_codeforces()
    sync_leetcode()