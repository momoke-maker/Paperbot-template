# Paperbot — a daily research-paper podcast in Hebrew, delivered privately on Telegram

Every morning the listener (see config/listener.md) gets ONE research paper as a detailed two-host
Hebrew audio episode (12–16 min) in their private Telegram bot. They can also send the bot a PDF or a
link at any time and get an episode on demand.

## How it works
- **Daily (Claude scheduled task, morning):** pick a paper per config/topics.md (journal tiers, topic
  rotation, no repeats) via Undermind → read the full text → write the script per
  config/episode_guidelines.md + config/listener.md → commit `episodes/<YYYY-MM-DD>/script.json` +
  `meta.json` → push. The prompt for the task is in DAILY_TASK_PROMPT.md.
- **.github/workflows/episode.yml** (on push of episodes/**/script.json, or run manually): Gemini TTS
  (multi-speaker; edge-tts fallback) → episode.mp3 committed → sent to Telegram with a caption.
  Processes every episode folder that has no episode.mp3 yet.
- **On request:** Google Apps Script (relay/apps_script.gs, on the listener's Google account) checks the
  bot every minute; a PDF or a link (not a reply) triggers `repository_dispatch: telegram` →
  request.yml → scripts/inbox.py: Gemini reads the PDF and writes the script → same TTS → Telegram.
- Replies to episode messages in Telegram are the listener's notes; the pipeline ignores them.

## Secrets (GitHub → Settings → Secrets and variables → Actions)
GEMINI_API_KEY, TELEGRAM_BOT_TOKEN. The chat id is discovered automatically and saved to config/chat_id.txt.

## Rules
- Episodes only from the paper's full text, never from the abstract alone. Never invent numbers or details.
- Never repeat a paper (check episodes/*/meta.json); avoid papers in config/library.md.
- Never automate logins to university/library accounts. Paywalled papers: the listener downloads the
  PDF themselves and sends it to the bot.
- Claude's cloud sandbox usually can't reach Google/Telegram APIs directly; the GitHub API works.
  All calls to Gemini and Telegram happen inside GitHub Actions.
