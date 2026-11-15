"""Turn episodes/<id>/script.json into episode.mp3 and send it to Telegram.

Runs inside GitHub Actions. Secrets come from env:
  GEMINI_API_KEY, TELEGRAM_BOT_TOKEN
Processes every episode folder that has script.json but no episode.mp3.
"""
import asyncio, base64, glob, json, os, subprocess, sys, tempfile, time, traceback
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAT_ID_FILE = os.path.join(ROOT, "config", "chat_id.txt")
GEMINI = "https://generativelanguage.googleapis.com/v1beta"
FALLBACK_MODELS = ["gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"]
CHUNK_CHARS = 3500
SR = 24000
DEFAULT_SPEAKERS = {
    "A": {"label": "Maya", "gemini_voice": "Kore", "edge_voice": "he-IL-HilaNeural"},
    "B": {"label": "Daniel", "gemini_voice": "Puck", "edge_voice": "he-IL-AvriNeural"},
}

STYLE = (
    "Read the following two-host podcast conversation aloud in natural, fluent Israeli Hebrew. "
    "Warm, curious, conversational tone, like two researchers chatting over morning coffee; "
    "clear pronunciation of English technical terms. Do not add or skip words.\n\n"
)


def log(*a):
    print(*a, flush=True)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


# ---------------- Gemini TTS ----------------
def gemini_models(key):
    try:
        r = requests.get(f"{GEMINI}/models", params={"key": key, "pageSize": 200}, timeout=30)
        r.raise_for_status()
        names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                 if "tts" in m["name"].lower()]
        names.sort(key=lambda n: ("flash" not in n, "lite" in n, "preview" in n, n))
        if names:
            return names
    except Exception as e:
        log("model list failed:", e)
    return FALLBACK_MODELS


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


def gemini_chunk(key, model, speakers, chunk, per_part=False):
    if per_part:
        # newer TTS models: one text part per line, tagged with its speaker
        contents = [{"parts": [{"text": l["text"], "speechMetadata": {"speaker": speakers[l["s"]]["label"]}}
                               for l in chunk]}]
    else:
        convo = "\n".join(f'{speakers[l["s"]]["label"]}: {l["text"]}' for l in chunk)
        contents = [{"parts": [{"text": STYLE + convo}]}]
    body = {
        "contents": contents,
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"multiSpeakerVoiceConfig": {"speakerVoiceConfigs": [
                {"speaker": s["label"],
                 "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": s["gemini_voice"]}}}
                for s in speakers.values()]}},
        },
    }
    for attempt in range(8):
        r = requests.post(f"{GEMINI}/models/{model}:generateContent",
                          params={"key": key}, json=body, timeout=300)
        if r.status_code == 200:
            parts = r.json()["candidates"][0]["content"]["parts"]
            data = next(p["inlineData"]["data"] for p in parts if "inlineData" in p)
            return base64.b64decode(data)
        if r.status_code == 400 and "speech_metadata" in r.text and not per_part:
            return gemini_chunk(key, model, speakers, chunk, per_part=True)
        if r.status_code in (429, 500, 503):
            import re as _re
            m = _re.search(r'"retryDelay":\s*"(\d+)', r.text)
            wait = int(m.group(1)) + 3 if m else 20 * (attempt + 1)
            if wait > 180:
                # quota exhausted (e.g. daily limit): don't sleep past the job timeout,
                # move on to the next model / edge-tts fallback
                raise RuntimeError(f"{model}: HTTP {r.status_code}, retryDelay {wait}s too long")
            log(f"  {model}: HTTP {r.status_code}, retry in {wait}s")
            time.sleep(wait)
            continue
        raise RuntimeError(f"{model}: HTTP {r.status_code} {r.text[:300]}")
    raise RuntimeError(f"{model}: gave up after retries")


def tts_gemini(script, out_wav, status):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing")
    models = gemini_models(key)
    status["gemini_models_seen"] = models[:6]
    last = None
    for model in models[:3]:
        try:
            pcm = b""
            pause = b"\x00\x00" * int(SR * 0.4)
            for i, ch in enumerate(chunks(script["lines"])):
                log(f"  gemini {model} chunk {i+1}")
                pcm += gemini_chunk(key, model, script["speakers"], ch) + pause
                time.sleep(4)
            raw = out_wav + ".pcm"
            open(raw, "wb").write(pcm)
            run(["ffmpeg", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", raw, out_wav])
            status["model"] = model
            return
        except Exception as e:
            last = e
            log("  model failed:", e)
    raise RuntimeError(f"all Gemini models failed: {last}")


# ---------------- edge-tts fallback ----------------
def tts_edge(script, out_wav, status):
    import edge_tts

    async def go(tmp):
        files = []
        for i, ln in enumerate(script["lines"]):
            f = os.path.join(tmp, f"{i:04d}.mp3")
            await edge_tts.Communicate(ln["text"], script["speakers"][ln["s"]]["edge_voice"],
                                       rate="+5%").save(f)
            files.append(f)
        return files

    with tempfile.TemporaryDirectory() as tmp:
        files = asyncio.run(go(tmp))
        sil = os.path.join(tmp, "sil.mp3")
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", "0.35", sil])
        lst = os.path.join(tmp, "list.txt")
        with open(lst, "w") as fh:
            for f in files:
                fh.write(f"file '{f}'\nfile '{sil}'\n")
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-ar", str(SR), "-ac", "1", out_wav])
    status["model"] = "edge-tts"


# ---------------- Telegram ----------------
def chat_id(token):
    if os.path.exists(CHAT_ID_FILE):
        return open(CHAT_ID_FILE).read().strip()
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30).json()
    for u in reversed(r.get("result", [])):
        msg = u.get("message") or u.get("edited_message")
        if msg and msg["chat"]["type"] == "private":
            cid = str(msg["chat"]["id"])
            os.makedirs(os.path.dirname(CHAT_ID_FILE), exist_ok=True)
            open(CHAT_ID_FILE, "w").write(cid + "\n")
            return cid
    raise RuntimeError("No chat found - send /start to the bot first")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send(meta, mp3, duration):
    token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    cid = chat_id(token)
    cap = [f"<b>{esc(meta.get('title_he') or meta['title'])}</b>"]
    if meta.get("title_he"):
        cap.append(esc(meta["title"]))
    src = " · ".join(x for x in [meta.get("authors"), meta.get("journal"), str(meta.get("year", ""))] if x)
    if src:
        cap.append(f"<i>{esc(src)}</i>")
    if meta.get("summary_he"):
        cap.append("\n" + esc(meta["summary_he"]))
    if meta.get("link"):
        cap.append(f"\n{esc(meta['link'])}")
    caption = "\n".join(cap)[:1020]
    with open(mp3, "rb") as fh:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendAudio",
                          data={"chat_id": cid, "caption": caption, "parse_mode": "HTML",
                                "title": (meta.get("title_he") or meta["title"])[:60],
                                "performer": "Paperbot", "duration": int(duration)},
                          files={"audio": (os.path.basename(mp3), fh, "audio/mpeg")}, timeout=300)
    if not r.ok or not r.json().get("ok"):
        raise RuntimeError(f"Telegram: {r.status_code} {r.text[:300]}")


def duration_of(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return float(out.strip() or 0)


def process(ep_dir):
    status = {"episode": os.path.basename(ep_dir), "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    script = json.load(open(os.path.join(ep_dir, "script.json"), encoding="utf-8"))
    meta = json.load(open(os.path.join(ep_dir, "meta.json"), encoding="utf-8"))
    wav = os.path.join(ep_dir, "episode.wav")
    mp3 = os.path.join(ep_dir, "episode.mp3")
    engine_pref = script.get("engine", "gemini")
    try:
        if engine_pref == "edge":
            raise RuntimeError("edge requested")
        tts_gemini(script, wav, status)
        status["engine"] = "gemini"
    except Exception as e:
        status["gemini_error"] = str(e)[:500]
        log("Gemini failed -> edge-tts:", e)
        tts_edge(script, wav, status)
        status["engine"] = "edge-tts"
    run(["ffmpeg", "-y", "-i", wav, "-ac", "1", "-b:a", "64k",
         "-metadata", f"title={meta.get('title_he') or meta['title']}", mp3])
    os.remove(wav)
    status["duration_sec"] = round(duration_of(mp3))
    try:
        send(meta, mp3, status["duration_sec"])
        status["telegram"] = "sent"
    except Exception as e:
        status["telegram"] = f"error: {e}"[:500]
    json.dump(status, open(os.path.join(ep_dir, "status.json"), "w"), ensure_ascii=False, indent=2)
    log(json.dumps(status, ensure_ascii=False))
    return status


def main():
    todo = [os.path.dirname(p) for p in sorted(glob.glob(os.path.join(ROOT, "episodes", "*", "script.json")))
            if not os.path.exists(os.path.join(os.path.dirname(p), "episode.mp3"))]
    log("episodes to make:", [os.path.basename(t) for t in todo])
    failed = False
    for ep in todo:
        try:
            st = process(ep)
            failed |= st.get("telegram") != "sent"
        except Exception:
            failed = True
            err = traceback.format_exc()
            log(err)
            json.dump({"episode": os.path.basename(ep), "error": err[-1500:]},
                      open(os.path.join(ep, "status.json"), "w"), ensure_ascii=False, indent=2)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
