"""Render episodes/<id>/script.json to episode.mp3 and send it to Telegram.

Runs in GitHub Actions (secrets: GEMINI_API_KEY, TELEGRAM_BOT_TOKEN). Handles every episode folder
that has a script.json and hasn't been delivered yet (at most MAX_ATTEMPTS tries per episode).
Voices: Gemini multi-speaker TTS, with the free edge-tts voices as a fallback. Language (Hebrew or
English) comes from config/listener.md.
"""
import asyncio, base64, glob, json, os, re, subprocess, sys, tempfile, time, traceback
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAT_ID_FILE = os.path.join(ROOT, "config", "chat_id.txt")
GEMINI = "https://generativelanguage.googleapis.com/v1beta"
FALLBACK_TTS_MODELS = ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"]
CHUNK_CHARS = 3500          # text per TTS request
SR = 24000                  # Gemini returns 24 kHz 16-bit mono PCM
GEMINI_BUDGET_SEC = 15 * 60  # after this, switch to edge-tts so the job never hits its timeout
MAX_ATTEMPTS = 2            # an episode that failed this many times is skipped (no endless retries)
LISTENER_FILE = os.path.join(ROOT, "config", "listener.md")
VOICES = {  # two hosts per language; Gemini voices are multilingual, edge-tts voices are per language
    "he": {"A": {"label": "Maya", "gemini_voice": "Kore", "edge_voice": "he-IL-HilaNeural"},
           "B": {"label": "Daniel", "gemini_voice": "Puck", "edge_voice": "he-IL-AvriNeural"}},
    "en": {"A": {"label": "Maya", "gemini_voice": "Kore", "edge_voice": "en-US-AriaNeural"},
           "B": {"label": "Daniel", "gemini_voice": "Puck", "edge_voice": "en-US-GuyNeural"}},
}
STYLES = {
    "he": "Read the following two-host podcast conversation aloud in natural, fluent Israeli Hebrew. ",
    "en": "Read the following two-host podcast conversation aloud in natural, fluent English. ",
}
STYLE_TAIL = ("Warm, calm, conversational tone, like two researchers talking over morning coffee; "
              "clear pronunciation of technical terms. Do not add or skip words.\n\n")


# ---------------- helpers ----------------
def language():
    """Episode language from config/listener.md ("- language: he" or "- language: en"); Hebrew by default."""
    if os.path.exists(LISTENER_FILE):
        with open(LISTENER_FILE, encoding="utf-8") as fh:
            m = re.search(r"^\W*language:\s*(he|en)\b", fh.read(), re.M | re.I)
            if m:
                return m.group(1).lower()
    return "he"


def default_speakers():
    return VOICES[language()]


def log(*a):
    print(*a, flush=True)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def secret(name):
    return os.environ.get(name, "").strip()


def redact(text):
    """Remove secrets from text that may end up in logs, committed files or Telegram messages."""
    text = str(text)
    for name in ("GEMINI_API_KEY", "TELEGRAM_BOT_TOKEN"):
        if secret(name):
            text = text.replace(secret(name), "***")
    return text


# ---------------- Gemini ----------------
def gemini_headers():
    # key in a header, not the URL, so it never appears in error messages
    return {"x-goog-api-key": secret("GEMINI_API_KEY")}


def gemini_models():
    r = requests.get(f"{GEMINI}/models", headers=gemini_headers(), params={"pageSize": 200}, timeout=30)
    r.raise_for_status()
    return r.json().get("models", [])


def retry_wait(r, attempt):
    m = re.search(r'"retryDelay":\s*"(\d+)', r.text)
    return int(m.group(1)) + 3 if m else 20 * (attempt + 1)


def tts_models():
    try:
        names = [m["name"].split("/")[-1] for m in gemini_models() if "tts" in m["name"].lower()]
        names.sort(key=lambda n: ("flash" not in n, "lite" in n, "preview" in n, n))
        return names or FALLBACK_TTS_MODELS
    except Exception as e:
        log("model list failed:", redact(e))
        return FALLBACK_TTS_MODELS


def chunks(lines, limit=CHUNK_CHARS):
    cur, size = [], 0
    for ln in lines:
        if cur and size + len(ln["text"]) > limit:
            yield cur
            cur, size = [], 0
        cur.append(ln)
        size += len(ln["text"])
    if cur:
        yield cur


def tts_request(model, speakers, chunk, per_part):
    if per_part:  # newer TTS models: one text part per line, tagged with its speaker
        parts = [{"text": l["text"], "speechMetadata": {"speaker": speakers[l["s"]]["label"]}} for l in chunk]
    else:
        convo = "\n".join(f'{speakers[l["s"]]["label"]}: {l["text"]}' for l in chunk)
        parts = [{"text": STYLES[language()] + STYLE_TAIL + convo}]
    voices = [{"speaker": s["label"], "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": s["gemini_voice"]}}}
              for s in speakers.values()]
    return {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"multiSpeakerVoiceConfig": {"speakerVoiceConfigs": voices}}}}


def gemini_chunk(model, speakers, chunk, deadline):
    per_part = False
    for attempt in range(8):
        r = requests.post(f"{GEMINI}/models/{model}:generateContent", headers=gemini_headers(),
                          json=tts_request(model, speakers, chunk, per_part), timeout=300)
        if r.ok:
            parts = r.json()["candidates"][0]["content"]["parts"]
            return base64.b64decode(next(p["inlineData"]["data"] for p in parts if "inlineData" in p))
        if r.status_code == 400 and "speech_metadata" in r.text and not per_part:
            per_part = True
            continue
        if r.status_code in (429, 500, 503):
            wait = retry_wait(r, attempt)
            if time.time() + wait > deadline:  # e.g. daily quota exhausted: don't wait, fall back
                raise RuntimeError(f"{model}: HTTP {r.status_code}, would wait {wait}s past the time budget")
            log(f"  {model}: HTTP {r.status_code}, retry in {wait}s")
            time.sleep(wait)
            continue
        raise RuntimeError(f"{model}: HTTP {r.status_code} {r.text[:300]}")
    raise RuntimeError(f"{model}: gave up after retries")


def tts_gemini(script, out_wav, status):
    if not secret("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY missing")
    deadline = time.time() + GEMINI_BUDGET_SEC
    pause = b"\x00\x00" * int(SR * 0.4)
    last = None
    for model in tts_models()[:3]:
        try:
            pcm = b""
            for i, ch in enumerate(chunks(script["lines"])):
                log(f"  {model} chunk {i + 1}")
                pcm += gemini_chunk(model, script["speakers"], ch, deadline) + pause
            raw = out_wav + ".pcm"
            with open(raw, "wb") as fh:
                fh.write(pcm)
            run(["ffmpeg", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", raw, out_wav])
            os.remove(raw)
            status["voice"] = model
            return
        except Exception as e:
            last = e
            log("  model failed:", redact(e))
            if time.time() > deadline:
                break
    raise RuntimeError(f"Gemini TTS failed: {last}")


# ---------------- edge-tts fallback ----------------
def tts_edge(script, out_wav, status):
    import edge_tts

    async def render(tmp):
        files = []
        for i, ln in enumerate(script["lines"]):
            f = os.path.join(tmp, f"{i:04d}.mp3")
            await edge_tts.Communicate(ln["text"], script["speakers"][ln["s"]]["edge_voice"], rate="+5%").save(f)
            files.append(f)
        return files

    with tempfile.TemporaryDirectory() as tmp:
        files = asyncio.run(render(tmp))
        silence = os.path.join(tmp, "silence.mp3")
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", "0.35", silence])
        playlist = os.path.join(tmp, "list.txt")
        with open(playlist, "w") as fh:
            fh.writelines(f"file '{f}'\nfile '{silence}'\n" for f in files)
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", playlist, "-ar", str(SR), "-ac", "1", out_wav])
    status["voice"] = "edge-tts"


# ---------------- Telegram ----------------
def telegram(method):
    return f"https://api.telegram.org/bot{secret('TELEGRAM_BOT_TOKEN')}/{method}"


def chat_id():
    """The listener's chat id; discovered once from the /start message and saved to the repo."""
    if os.path.exists(CHAT_ID_FILE):
        with open(CHAT_ID_FILE) as fh:
            return fh.read().strip()
    updates = requests.get(telegram("getUpdates"), timeout=30).json().get("result", [])
    for u in reversed(updates):
        msg = u.get("message") or {}
        if msg.get("chat", {}).get("type") == "private":
            cid = str(msg["chat"]["id"])
            with open(CHAT_ID_FILE, "w") as fh:
                fh.write(cid + "\n")
            return cid
    raise RuntimeError("No chat found - send /start to the bot first")


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def short_title(meta):  # "title_he"/"summary_he": field names used by episodes made before Nov 2026
    return meta.get("title_short") or meta.get("title_he") or meta.get("title") or "Paperbot"


def caption(meta, limit=1024):
    """HTML caption that always fits Telegram's limit without cutting a tag in half."""
    title = short_title(meta)
    head = [f"<b>{esc(title)}</b>"]
    if meta.get("title") and meta["title"] != title:
        head.append(esc(meta["title"]))
    source = " · ".join(str(x) for x in (meta.get("authors"), meta.get("journal"), meta.get("year")) if x)
    if source:
        head.append(f"<i>{esc(source)}</i>")
    text = "\n".join(head)[:limit]
    link = f"\n\n{esc(meta['link'])}" if meta.get("link") else ""
    summary = meta.get("summary") or meta.get("summary_he") or ""
    while summary and len(text) + len(link) + len(esc(summary)) + 2 > limit:
        summary = summary[:-20].rstrip() + "…" if len(summary) > 21 else ""
    if summary:
        text += "\n\n" + esc(summary)
    return text + link if len(text) + len(link) <= limit else text


def send(meta, mp3, duration):
    cap = caption(meta)
    data = {"chat_id": chat_id(), "caption": cap, "parse_mode": "HTML",
            "title": short_title(meta)[:60],
            "performer": "Paperbot", "duration": int(duration)}
    for attempt in range(2):
        with open(mp3, "rb") as fh:
            r = requests.post(telegram("sendAudio"), data=data, timeout=300,
                              files={"audio": (os.path.basename(mp3), fh, "audio/mpeg")})
        if r.ok and r.json().get("ok"):
            return
        # e.g. a caption Telegram can't parse: retry once as plain text
        data.pop("parse_mode", None)
        data["caption"] = re.sub(r"<[^>]+>", "", cap).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    raise RuntimeError(f"Telegram: {r.status_code} {r.text[:300]}")


# ---------------- main ----------------
def duration_of(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout
    return float(out.strip() or 0)


def previous_status(ep_dir):
    path = os.path.join(ep_dir, "status.json")
    return read_json(path) if os.path.exists(path) else {}


def is_done(ep_dir):
    st = previous_status(ep_dir)
    has_mp3 = os.path.exists(os.path.join(ep_dir, "episode.mp3"))
    return st.get("telegram") == "sent" or (has_mp3 and not st)


def process(ep_dir):
    """Render one episode folder and send it. Returns the status dict (also saved as status.json)."""
    status = {"episode": os.path.basename(ep_dir), "attempts": previous_status(ep_dir).get("attempts", 0) + 1,
              "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        script = read_json(os.path.join(ep_dir, "script.json"))
        script.setdefault("speakers", default_speakers())
        meta = read_json(os.path.join(ep_dir, "meta.json"))
        wav, mp3 = os.path.join(ep_dir, "episode.wav"), os.path.join(ep_dir, "episode.mp3")
        if not os.path.exists(mp3):  # rendered on an earlier attempt -> only (re)send
            try:
                tts_gemini(script, wav, status)
            except Exception as e:
                status["gemini_error"] = redact(e)[:300]
                log("Gemini failed, using edge-tts:", status["gemini_error"])
                tts_edge(script, wav, status)
            run(["ffmpeg", "-y", "-i", wav, "-ac", "1", "-b:a", "64k",
                 "-metadata", f"title={short_title(meta)}", mp3])
            os.remove(wav)
        status["duration_sec"] = round(duration_of(mp3))
        send(meta, mp3, status["duration_sec"])
        status["telegram"] = "sent"
    except Exception:
        status["error"] = redact(traceback.format_exc())[-1500:]
        log(status["error"])
    write_json(os.path.join(ep_dir, "status.json"), status)
    return status


def main():
    todo = []
    for path in sorted(glob.glob(os.path.join(ROOT, "episodes", "*", "script.json"))):
        ep = os.path.dirname(path)
        if is_done(ep):
            continue
        if previous_status(ep).get("attempts", 0) >= MAX_ATTEMPTS:
            log("skipping (failed too often):", os.path.basename(ep))
            continue
        todo.append(ep)
    log("episodes to make:", [os.path.basename(t) for t in todo])
    results = [process(ep) for ep in todo]
    sys.exit(0 if all(r.get("telegram") == "sent" for r in results) else 1)


if __name__ == "__main__":
    main()
