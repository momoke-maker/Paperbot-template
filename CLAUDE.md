# Paperbot — a daily research-paper podcast, delivered privately on Telegram

Every morning the listener (see config/listener.md) gets ONE research paper as a detailed two-host
audio episode (12–16 min, Hebrew or English) in their private Telegram bot. They can also send the bot
a PDF or a link at any time and get an episode on demand.

## Setting it up for a new user (when config/listener.md still contains <<placeholders>>)

You are the setup guide. Do everything you can yourself; ask the user only for what needs their own
accounts or keys. Talk in the user's language, one step at a time, short and friendly, and confirm each
step works before moving on. Never ask the user to paste a key, token or password into the chat —
keys go only into GitHub Secrets and Google Apps Script properties, which the user fills in.

What only the user can do (guide them; exact clicks are in README.md):
1. Create their private copy of this repo ("Use this template", Private).
2. Connect GitHub and Undermind to Claude (Claude settings → Connectors).
3. Create a Telegram bot with @BotFather and send it `/start`.
4. Create a Gemini API key at aistudio.google.com/apikey.
5. Add the GitHub secrets GEMINI_API_KEY and TELEGRAM_BOT_TOKEN (repo Settings → Secrets → Actions).
6. Sign up to Undermind with their university email (at Reichman this gives free Pro access).
7. The Google Apps Script relay (step C below): paste the code, add 3 properties, run `setup`.

What you do yourself, in this order:
A. **Profile.** Ask: episodes in Hebrew or English? Their name (spelling as it should be spoken, and
   how to address them: female/male), role, field, and their own research; topics that interest them.
   Offer to use a CV, research proposal or paper list they attach. Fill config/listener.md (keep the
   `- language: he|en` line machine-readable) and config/topics.md. Review the journal tiers in
   topics.md for their field and propose changes. Optionally fill config/library.md with papers they
   already know. Commit and push.
B. **Test episode.** After their secrets are set and they sent `/start`: write a 3–4 line test episode
   in their language to `episodes/0000-test/` (script.json with just "lines", meta.json with title,
   title_short, summary) and push. That runs the "Make episode" workflow. Poll
   `https://api.github.com/repos/<owner>/<repo>/actions/runs?per_page=1` until it completes, then pull
   and check `episodes/0000-test/status.json` and that `config/chat_id.txt` now exists. On failure,
   read the job logs and fix or explain.
C. **Relay.** Set `const REPO` in relay/apps_script.gs to their `<owner>/<repo>` and push, so the file
   they copy is ready. Then guide them: a fine-grained GitHub token (only this repo, Contents: Read and
   write) → script.google.com → new project → paste the file (GitHub's "Copy raw file" button avoids
   cut-off pastes) → Script properties TELEGRAM_BOT_TOKEN, GH_TOKEN, CHAT_ID (tell them the CHAT_ID
   value from config/chat_id.txt) → run `setup` → approve the permissions (the "unverified app"
   warning is normal for a script they own). Test: they send the bot a PDF; you watch for the
   "Episode on request" run.
D. **Undermind workspace.** With the Undermind tools: create a workspace named "Paperbot" and note
   its id.
E. **Daily task.** Fill DAILY_TASK_PROMPT.md's placeholders (repo, workspace id) and create a
   scheduled task with your scheduling tool: daily at 07:13 in their time zone (ask if unsure), with
   the filled prompt. Tell them the first episode arrives the next morning, around 07:30–07:45.
F. Wrap up: a short summary of what was set up, and how to use it (PDF/link → episode; reply to an
   episode message to keep notes; ask Claude to change the style in config/episode_guidelines.md).

## How it works
- **Daily (Claude scheduled task):** pick a paper per config/topics.md (journal tiers, topic rotation,
  no repeats) via Undermind → read the full text → write the script per config/episode_guidelines.md
  + config/listener.md → commit `episodes/<YYYY-MM-DD>/script.json` + `meta.json` → push.
- **.github/workflows/episode.yml** (on push of episodes/**/script.json, or run manually): Gemini TTS
  (multi-speaker; edge-tts fallback) → episode.mp3 committed → sent to Telegram with a caption.
- **On request:** the Apps Script relay checks the bot every minute; a PDF or a link (not a reply)
  triggers `repository_dispatch: telegram` → request.yml → scripts/inbox.py: Gemini reads the PDF and
  writes the script → same TTS → Telegram.
- Replies to episode messages in Telegram are the listener's notes; the pipeline ignores them.

## Rules
- Episodes only from the paper's full text, never from the abstract alone. Never invent numbers or details.
- Never repeat a paper (check episodes/*/meta.json); avoid papers in config/library.md.
- Never automate logins to university/library accounts. Paywalled papers: the listener downloads the
  PDF themselves and sends it to the bot.
- Claude's cloud sandbox usually can't reach Google/Telegram APIs directly; the GitHub API works.
  All calls to Gemini and Telegram happen inside GitHub Actions.
