// ==UserScript==
// @name         LeetCode -> GitHub Auto Sync
// @namespace    sai-leetcode-sync
// @version      1.0
// @description  Fires a GitHub repository_dispatch event the instant a LeetCode submission is Accepted. Skips contest problems.
// @match        https://leetcode.com/problems/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  // ---------- CONFIG: edit these three before using ----------
  const CONFIG = {
    GITHUB_OWNER: "your-github-username",
    GITHUB_REPO: "your-repo-name",
    GITHUB_TOKEN: "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", // fine-grained PAT, "Contents" + "Actions" write scope on this repo only
  };
  // -------------------------------------------------------------

  // Skip entirely on contest URLs (never send contest solutions)
  if (window.location.pathname.startsWith("/contest/")) {
    return;
  }

  // Map LeetCode's submission body -> submission id, so that when the
  // "check" polling endpoint reports Accepted, we already have the code.
  const pendingCode = new Map(); // submissionId (string) -> { code, lang }

  const LANG_EXT = {
    python3: "py", python: "py", java: "java", cpp: "cpp", c: "c",
    javascript: "js", typescript: "ts", golang: "go", kotlin: "kt",
    swift: "swift", rust: "rs", csharp: "cs",
  };

  function getSlugFromUrl() {
    const m = window.location.pathname.match(/\/problems\/([^/]+)/);
    return m ? m[1] : null;
  }

  async function getQuestionMeta(slug) {
    const query = `
      query questionData($titleSlug: String!) {
        question(titleSlug: $titleSlug) {
          title
          difficulty
          content
          topicTags { name }
        }
      }`;
    const res = await fetch("https://leetcode.com/graphql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ query, variables: { titleSlug: slug } }),
    });
    const data = await res.json();
    return data.data.question;
  }

  function stripHtml(html) {
    const div = document.createElement("div");
    div.innerHTML = html || "";
    return (div.textContent || "").replace(/\s+/g, " ").trim();
  }

  async function dispatchToGithub(payload) {
    const url = `https://api.github.com/repos/${CONFIG.GITHUB_OWNER}/${CONFIG.GITHUB_REPO}/dispatches`;
    try {
      await fetch(url, {
        method: "POST",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${CONFIG.GITHUB_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          event_type: "leetcode_submission",
          client_payload: payload,
        }),
      });
      console.log("[LC-Sync] Dispatched:", payload.title);
    } catch (e) {
      console.error("[LC-Sync] Dispatch failed:", e);
    }
  }

  async function handleAccepted(submissionId) {
    const cached = pendingCode.get(submissionId);
    if (!cached) return; // we didn't capture the submit body, bail quietly

    const slug = getSlugFromUrl();
    if (!slug) return;

    const q = await getQuestionMeta(slug);
    const ext = LANG_EXT[cached.lang.toLowerCase().replace(/\s/g, "")] || "txt";

    const payload = {
      slug,
      title: q.title,
      difficulty: q.difficulty,
      topic_tags: q.topicTags.map((t) => t.name).join(", "),
      lang: cached.lang,
      ext,
      code: cached.code,
      problem_content: stripHtml(q.content).slice(0, 1500),
      problem_url: `https://leetcode.com/problems/${slug}/`,
      timestamp: Math.floor(Date.now() / 1000),
    };

    dispatchToGithub(payload);
    pendingCode.delete(submissionId);
  }

  // ---- Monkey-patch fetch to observe LeetCode's own network calls ----
  const originalFetch = window.fetch;
  window.fetch = async function (...args) {
    const [resource, options] = args;
    const url = typeof resource === "string" ? resource : resource.url;

    // Capture the outgoing submit request (contains the code you typed)
    if (url && url.includes("/submit/") && options && options.method === "POST") {
      try {
        const body = JSON.parse(options.body);
        const response = await originalFetch.apply(this, args);
        const clone = response.clone();
        clone.json().then((data) => {
          if (data && data.submission_id) {
            pendingCode.set(String(data.submission_id), {
              code: body.typed_code,
              lang: body.lang,
            });
          }
        }).catch(() => {});
        return response;
      } catch (e) {
        return originalFetch.apply(this, args);
      }
    }

    // Watch the polling "check" endpoint for Accepted verdicts
    if (url && url.includes("/submissions/detail/") && url.includes("/check/")) {
      const response = await originalFetch.apply(this, args);
      response.clone().json().then((data) => {
        if (data && data.state === "SUCCESS" && data.status_msg === "Accepted") {
          const idMatch = url.match(/\/detail\/(\d+)\/check\//);
          if (idMatch) handleAccepted(idMatch[1]);
        }
      }).catch(() => {});
      return response;
    }

    return originalFetch.apply(this, args);
  };
})();
