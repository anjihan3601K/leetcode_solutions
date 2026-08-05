# Setup

## 1. Create the GitHub repo
Create a new repo (e.g. `leetcode-solutions`). Push these files (`.github/workflows/`, `scripts/`, `requirements.txt`) to it.

## 2. Add the Groq secret
Repo → Settings → Secrets and variables → Actions → New repository secret
- Name: `GROQ_API_KEY`
- Value: your Groq API key

## 3. Create a GitHub Personal Access Token (for the userscript)
GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token
- Repository access: **Only select repositories** → your leetcode-solutions repo
- Permissions: **Contents: Read and write**, **Actions: Read and write**
- Copy the token (starts with `github_pat_...`) — you won't see it again

## 4. Install Tampermonkey
- Chrome/Edge: search "Tampermonkey" in the Web Store → Add to Chrome
- Firefox: search in Firefox Add-ons

## 5. Add the userscript
- Click the Tampermonkey icon → Create a new script
- Delete the placeholder content, paste in `userscript/leetcode-to-github.user.js`
- Edit the `CONFIG` block at the top:
  ```js
  const CONFIG = {
    GITHUB_OWNER: "your-github-username",
    GITHUB_REPO: "leetcode-solutions",
    GITHUB_TOKEN: "github_pat_xxxxxxxxxxxxxxxxxxxxxxx",
  };
  ```
- Save (Ctrl+S)

## 6. Test it
- Go to any LeetCode problem, solve it, submit until Accepted
- Open the browser console (F12) — you should see `[LC-Sync] Dispatched: <problem title>`
- Check your repo's Actions tab — a "LeetCode Submission Sync" run should appear within a few seconds
- Once it finishes, check `problems/<difficulty>/<slug>/` in your repo

## Notes
- Contest problems (`leetcode.com/contest/...`) are intentionally skipped — never auto-committed.
- Solving the same problem again later adds a new file under `attempts/` and a new entry in that problem's README — nothing gets overwritten.
- If the userscript ever stops firing, check the browser console for errors first (F12 on a LeetCode problem page) — LeetCode occasionally tweaks their internal API paths, which would need a small script update.
- The GitHub PAT lives only in your local Tampermonkey script (client-side), scoped to just this one repo — nobody else sees it.
