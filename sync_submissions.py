import os
import re
import json
import requests
from pathlib import Path
from bs4 import BeautifulSoup

CF_USERNAME = os.environ.get("CF_USERNAME", "writeAhead")
LC_USERNAME = os.environ.get("LC_USERNAME", "writeAhead")

LANG_MAP = {
    "cpp": "cpp", "c++": "cpp", "gnu c++": "cpp", "gnu c++17": "cpp", "gnu c++20": "cpp", "gnu c++23": "cpp",
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
# 1. CODEFORCES SYNC
# -------------------------------------------------------------------
def sync_codeforces():
    print(f"--- Fetching Codeforces submissions for {CF_USERNAME} ---")
    url = f"https://codeforces.com/api/user.status?handle={CF_USERNAME}&from=1&count=20"
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    try:
        res = session.get(url, timeout=15)
        data = res.json()
        if data.get("status") != "OK":
            print(f"Codeforces API error: {data.get('comment')}")
            return
    except Exception as e:
        print(f"Failed to query Codeforces API: {e}")
        return

    accepted_subs = [s for s in data.get("result", []) if s.get("verdict") == "OK"]
    print(f"[Codeforces] Found {len(accepted_subs)} accepted submissions.")

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

        # Clean existing directory if it only contains old placeholder txt file
        old_txt = target_dir / "solution.txt"
        if old_txt.exists() and ext != "txt":
            old_txt.unlink()

        code_content = ""
        sub_url = f"https://codeforces.com/contest/{contest_id}/submission/{sub_id}"
        
        try:
            page_res = session.get(sub_url, timeout=15)
            if page_res.status_code == 200:
                soup = BeautifulSoup(page_res.text, "html.parser")
                source_elem = soup.find("pre", id="program-source-code")
                if source_elem:
                    code_content = source_elem.get_text()
        except Exception as err:
            print(f"Could not scrape code for CF submission {sub_id}: {err}")

        target_dir.mkdir(parents=True, exist_ok=True)

        # Write README
        problem_url = f"https://codeforces.com/problemset/problem/{contest_id}/{index}"
        readme_file = target_dir / "README.md"
        readme_content = f"# {contest_id}{index} - {name}\n\n" \
                         f"- **Problem Link:** [{problem_url}]({problem_url})\n" \
                         f"- **Language:** {lang}\n" \
                         f"- **Submission ID:** {sub_id}\n"
        readme_file.write_text(readme_content, encoding="utf-8")

        # Fallback if page scrape was blocked by Cloudflare
        if not code_content.strip():
            code_content = f"// Problem: {name} ({contest_id}{index})\n" \
                           f"// Language: {lang}\n" \
                           f"// Submission Link: {sub_url}\n"

        solution_file.write_text(code_content, encoding="utf-8")
        print(f"[Codeforces] Synced: {folder_name}")


# -------------------------------------------------------------------
# 2. LEETCODE SYNC
# -------------------------------------------------------------------
def sync_leetcode():
    print(f"--- Fetching LeetCode submissions for {LC_USERNAME} ---")
    
    # Official LeetCode GraphQL public endpoint
    url = "https://leetcode.com/graphql"
    query = """
    query recentAcSubmissions($username: String!, $limit: Int!) {
      recentAcSubmissionList(username: $username, limit: $limit) {
        id
        title
        titleSlug
        timestamp
      }
    }
    """
    payload = {
        "query": query,
        "variables": {"username": LC_USERNAME, "limit": 20}
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://leetcode.com"
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        data = res.json()
        ac_list = data.get("data", {}).get("recentAcSubmissionList", [])
    except Exception as e:
        print(f"Failed to query LeetCode GraphQL: {e}")
        return

    if not ac_list:
        print("No recent accepted submissions found for LeetCode.")
        return

    print(f"[LeetCode] Found {len(ac_list)} recent accepted submissions.")

    for sub in ac_list:
        title = sub.get("title")
        slug = sub.get("titleSlug")
        sub_id = sub.get("id")

        if not slug:
            continue

        folder_name = clean_slug(slug)
        target_dir = Path("LeetCode") / folder_name
        
        # Check if already fully populated
        readme_file = target_dir / "README.md"
        if readme_file.exists():
            continue

        target_dir.mkdir(parents=True, exist_ok=True)

        problem_url = f"https://leetcode.com/problems/{slug}/"
        readme_content = f"# {title}\n\n" \
                         f"- **Problem Link:** [{problem_url}]({problem_url})\n" \
                         f"- **Status:** Accepted\n" \
                         f"- **Submission ID:** {sub_id}\n"
        readme_file.write_text(readme_content, encoding="utf-8")

        # Secondary fetch via public endpoint for code body
        code_str = ""
        try:
            code_res = requests.get(f"https://alfa-leetcode-api.onrender.com/submissionId/{sub_id}", timeout=10)
            if code_res.status_code == 200:
                code_data = code_res.json()
                code_str = code_data.get("code", "")
                lang = code_data.get("lang", "txt")
                ext = get_file_extension(lang)
            else:
                ext = "py"
        except Exception:
            ext = "py"

        solution_file = target_dir / f"solution.{ext}"

        if not code_str.strip():
            code_str = f"# Solution for LeetCode problem: {title}\n" \
                       f"# Problem Link: {problem_url}\n" \
                       f"# Note: Full automated source code retrieval for LeetCode requires session authentication.\n"

        solution_file.write_text(code_str, encoding="utf-8")
        print(f"[LeetCode] Synced: {folder_name}")


if __name__ == "__main__":
    sync_codeforces()
    sync_leetcode()