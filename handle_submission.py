"""
handle_submission.py

Triggered once per Accepted LeetCode submission via a GitHub repository_dispatch
event (see .github/workflows/leetcode-submission.yml). The full payload (code,
title, difficulty, etc.) arrives already-assembled from the browser userscript
in the PAYLOAD env var as JSON.

Key behavior: solving the same problem again later does NOT overwrite the
previous solution. Each accepted submission is written as its own dated file
under problems/<difficulty>/<slug>/attempts/, and the per-problem README lists
every attempt chronologically.
"""

import os
import json
import time
import pathlib
import requests

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROBLEMS_DIR = REPO_ROOT / "problems"
README_FILE = REPO_ROOT / "README.md"

STATS_START = "<!-- STATS:START -->"
STATS_END = "<!-- STATS:END -->"


def generate_explanation(title, problem_text, code, lang):
    api_key = os.environ["GROQ_API_KEY"]
    prompt = f"""You are summarizing a LeetCode solution for a GitHub README.

Problem: {title}
Problem statement (trimmed): {problem_text[:1200]}

Solution code ({lang}):
{code[:3000]}

Write ONLY a 4-5 step explanation of the approach/algorithm used, as a
numbered markdown list. Be concise and technical (data structures used,
key insight, complexity). No preamble, no code repeated, no closing remarks.
"""
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 400,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def load_meta(folder):
    meta_file = folder / "meta.json"
    if meta_file.exists():
        return json.loads(meta_file.read_text())
    return {"title": "", "difficulty": "", "topic_tags": "", "problem_url": "", "attempts": []}


def save_meta(folder, meta):
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))


def render_problem_readme(folder, meta):
    attempts = sorted(meta["attempts"], key=lambda a: a["timestamp"], reverse=True)
    body = f"""# {meta['title']}

**Difficulty:** {meta['difficulty']}
**Tags:** {meta['topic_tags']}
**Problem:** {meta['problem_url']}

## Attempts ({len(attempts)})

"""
    for i, a in enumerate(attempts):
        date = time.strftime("%Y-%m-%d %H:%M", time.localtime(a["timestamp"]))
        body += f"### Attempt {len(attempts) - i} — {date} ({a['lang']})\n\n"
        body += f"Code: [`attempts/{a['file']}`](attempts/{a['file']})\n\n"
        body += f"{a['explanation']}\n\n---\n\n"

    (folder / "README.md").write_text(body)


def update_root_readme():
    if not README_FILE.exists():
        README_FILE.write_text(
            "# LeetCode Solutions\n\nAuto-synced the instant a submission is Accepted.\n\n"
            f"{STATS_START}\n{STATS_END}\n"
        )

    content = README_FILE.read_text()

    rows = []
    total_attempts = 0
    by_diff = {}
    if PROBLEMS_DIR.exists():
        for diff_dir in sorted(PROBLEMS_DIR.iterdir()):
            if not diff_dir.is_dir():
                continue
            for prob_dir in sorted(diff_dir.iterdir()):
                meta_file = prob_dir / "meta.json"
                if not meta_file.exists():
                    continue
                meta = json.loads(meta_file.read_text())
                n_attempts = len(meta["attempts"])
                total_attempts += n_attempts
                by_diff[meta["difficulty"]] = by_diff.get(meta["difficulty"], 0) + 1
                last_ts = max(a["timestamp"] for a in meta["attempts"])
                last_date = time.strftime("%Y-%m-%d", time.localtime(last_ts))
                rows.append((last_ts, meta["title"], meta["difficulty"], n_attempts, last_date, prob_dir))

    rows.sort(reverse=True)

    table = "| Problem | Difficulty | Attempts | Last Solved |\n|---|---|---|---|\n"
    for _, title, difficulty, n_attempts, last_date, prob_dir in rows:
        rel = prob_dir.relative_to(REPO_ROOT)
        table += f"| [{title}]({rel}) | {difficulty} | {n_attempts} | {last_date} |\n"

    summary = f"**Total problems:** {len(rows)}  \n**Total submissions synced:** {total_attempts}  \n" + \
        "  \n".join(f"- {k}: {v}" for k, v in sorted(by_diff.items()))

    stats_block = f"{STATS_START}\n{summary}\n\n{table}\n{STATS_END}"

    import re
    new_content = re.sub(f"{STATS_START}.*?{STATS_END}", stats_block, content, flags=re.DOTALL)
    README_FILE.write_text(new_content)


def main():
    payload = json.loads(os.environ["PAYLOAD"])

    slug = payload["slug"]
    difficulty = payload["difficulty"]
    folder = PROBLEMS_DIR / difficulty.lower() / slug
    attempts_dir = folder / "attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)

    ts = int(payload["timestamp"])
    date_str = time.strftime("%Y-%m-%d_%H%M", time.localtime(ts))
    filename = f"{date_str}.{payload['ext']}"
    (attempts_dir / filename).write_text(payload["code"])

    explanation = generate_explanation(
        payload["title"], payload.get("problem_content", ""), payload["code"], payload["lang"]
    )

    meta = load_meta(folder)
    meta["title"] = payload["title"]
    meta["difficulty"] = difficulty
    meta["topic_tags"] = payload.get("topic_tags", "")
    meta["problem_url"] = payload.get("problem_url", "")
    meta["attempts"].append({
        "file": filename,
        "lang": payload["lang"],
        "timestamp": ts,
        "explanation": explanation,
    })
    save_meta(folder, meta)
    render_problem_readme(folder, meta)
    update_root_readme()

    print(f"Synced attempt #{len(meta['attempts'])} for {payload['title']}")


if __name__ == "__main__":
    main()
