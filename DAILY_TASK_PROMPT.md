# The prompt for the daily Claude scheduled task

Before using it, replace the two placeholders:
- `<<OWNER/REPO>>` — your GitHub repo, e.g. `noa-cohen/paperbot`
- `<<UNDERMIND_WORKSPACE_ID>>` — the id of your Undermind workspace (see README, step 7)

Copy everything below the line.

---

You produce today's episode of my private daily paper podcast (Hebrew audio review of ONE research paper). Work fully autonomously; nobody will answer questions.

1. Repo: attach GitHub repo <<OWNER/REPO>> with PUSH access (add_repo tool, access "push") and clone it. Read CLAUDE.md, config/listener.md, config/topics.md, config/episode_guidelines.md, config/library.md, config/wishlist.md, and the meta.json of all existing episodes (to avoid repeats and to rotate topics).

2. Pick the paper with Undermind (call get_orientation first). Workspace: <<UNDERMIND_WORKSPACE_ID>>. Follow config/topics.md exactly: strict journal-tier priority (search tier 1 journals first with journal_contains, go down a tier only if there is no suitable paper), topic rotation, mostly recent papers with about one classic a week. Use search_papers with has_pdf=true. The paper MUST have a readable full-text PDF. If the ideal pick is paywalled, add it (title + DOI) to config/wishlist.md and choose another.
   If Undermind is not connected, use web search to find an open-access paper that follows the same rules, and read its full text with WebFetch.

3. Read the full paper (Undermind read_pdfs). Ask detailed questions so you have everything the guidelines require: the theory and prior work the paper builds on, hypotheses, each study's sample, design, exact manipulations, every measure, procedure, preregistration, all key results with numbers, the authors' interpretation of each result, the discussion (conclusions, implications, additional and null findings) and limitations. Use several read_pdfs calls if needed. Never invent details.

4. Write the episode in Hebrew exactly per config/episode_guidelines.md, for the listener described in config/listener.md. Save:
   - episodes/<today's date YYYY-MM-DD, Israel time>/script.json with {"speakers": DEFAULT_SPEAKERS from scripts/make_episode.py, "lines": [...]}
   - episodes/<same>/meta.json (fields per the guidelines, source "daily").
   Validate the JSON (python json.load) and check the word count.

5. Commit and push to main. The push triggers the "Make episode" GitHub Action, which makes the audio and sends it to Telegram.

6. Verify: poll the GitHub API (https://api.github.com/repos/<<OWNER/REPO>>/actions/runs?per_page=1 via curl) until the run completes (~5-15 min). Then git pull and read episodes/<date>/status.json. If it failed, read the job logs (actions/jobs/<id>/logs), fix the cause if it is in the script/meta, and push again. Finish with a 2-line summary: which paper, and whether it was delivered.
