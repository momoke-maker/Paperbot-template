"""On-request episodes: the listener sends the bot a PDF or a link -> Gemini writes the script -> audio.

Triggered by the Google Apps Script relay (relay/apps_script.gs) via repository_dispatch
(event_type "telegram", the Telegram message in client_payload.message). For a manual test, run the
workflow with a message JSON as input.
"""
import base64, datetime, json, os, re, sys, time, zoneinfo
import requests

import make_episode as me

UA = {"User-Agent": "Mozilla/5.0 (paperbot; personal use)"}
MAX_PDF_BYTES = 18 * 1024 * 1024   # Gemini accepts up to ~20 MB of inline data per request
WRITER_BUDGET_SEC = 20 * 60        # total time for writing the script, across models and retries
SKIP_MODELS = ("tts", "image", "live", "embed", "audio", "lite", "nano", "gemma", "robotics", "computer")


def reply(chat_id, text, reply_to=None):
    data = {"chat_id": chat_id, "text": text}
    if reply_to:
        data["reply_to_message_id"] = reply_to
    requests.post(me.telegram("sendMessage"), data=data, timeout=60)


# ---------------- getting the PDF ----------------
def download(url, **kw):
    """Return (content, content_type), refusing anything larger than MAX_PDF_BYTES."""
    with requests.get(url, timeout=60, stream=True, **kw) as r:
        if not r.ok:
            return b"", ""
        data = b""
        for block in r.iter_content(1 << 16):
            data += block
            if len(data) > MAX_PDF_BYTES:
                raise ValueError("הקובץ גדול מדי (מעל 18MB)")
        return data, r.headers.get("content-type", "")


def fetch_pdf(url):
    """Return (pdf_bytes or None, html_text)."""
    data, ctype = download(url, headers=UA, allow_redirects=True)
    if data[:5] == b"%PDF-":
        return data, ""
    return None, data.decode("utf-8", "ignore") if "html" in ctype else ""


def pdf_from_telegram(doc):
    if doc.get("file_size", 0) > MAX_PDF_BYTES:
        raise ValueError("הקובץ גדול מדי (מעל 18MB)")
    info = requests.post(me.telegram("getFile"), data={"file_id": doc["file_id"]}, timeout=60).json()
    if not info.get("ok"):
        raise RuntimeError("לא הצלחתי להוריד את הקובץ מטלגרם")
    token = me.secret("TELEGRAM_BOT_TOKEN")
    data, _ = download(f"https://api.telegram.org/file/bot{token}/{info['result']['file_path']}")
    if data[:5] != b"%PDF-":
        raise RuntimeError("הקובץ לא נראה כמו PDF תקין")
    return data


def pdf_from_url(url):
    """Try the link itself, the publisher's citation_pdf_url, then an open-access copy via OpenAlex."""
    m = re.search(r"arxiv\.org/abs/([\w.\-/]+)", url)
    if m:
        url = f"https://arxiv.org/pdf/{m.group(1)}"
    pdf, html = fetch_pdf(url)
    if pdf:
        return pdf
    m = re.search(r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)', html, re.I)
    if m:
        pdf, _ = fetch_pdf(m.group(1))
        if pdf:
            return pdf
    doi = re.search(r"10\.\d{4,9}/[^\s\"'<>?#]+", url)
    doi = doi.group(0) if doi else (re.search(r'citation_doi["\'][^>]+content=["\'](10\.[^"\']+)', html, re.I) or [None, None])[1]
    if not doi:
        return None
    try:
        work = requests.get(f"https://api.openalex.org/works/doi:{doi.rstrip('.')}", timeout=30).json()
    except Exception as e:
        print("openalex:", e)
        return None
    candidates = [(work.get("best_oa_location") or {}).get("pdf_url"), (work.get("open_access") or {}).get("oa_url")]
    candidates += [loc.get("pdf_url") for loc in work.get("locations", []) if loc.get("is_oa")]
    for c in filter(None, candidates):
        pdf, _ = fetch_pdf(c)
        if pdf:
            return pdf
    return None


# ---------------- Gemini writes the script ----------------
def writer_models():
    ranked = []
    for m in me.gemini_models():
        name = m["name"].split("/")[-1]
        if "generateContent" not in m.get("supportedGenerationMethods", []) or any(x in name for x in SKIP_MODELS):
            continue
        if "pro" in name or "flash" in name:
            version = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
            ranked.append((float(version.group(1)) if version else 0, "pro" in name,
                           "preview" not in name and "exp" not in name, name))
    return [r[3] for r in sorted(ranked, reverse=True)] or ["gemini-2.5-pro", "gemini-2.5-flash"]


def write_script(pdf, note=""):
    guide = "\n\n".join(open(os.path.join(me.ROOT, "config", f), encoding="utf-8").read()
                        for f in ("episode_guidelines.md", "listener.md"))
    prompt = (guide + "\n\n---\nTASK: Write the episode for the attached paper, following the guidelines exactly. "
              'Return ONLY a JSON object: {"meta": {...meta.json fields...}, "lines": [{"s": "A"|"B", "text": "..."}]}. '
              'Set meta.source to "request".' + (f"\nThe listener's note with the request: {note}" if note else ""))
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(pdf).decode()}},
                                    {"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}}
    deadline, last = time.time() + WRITER_BUDGET_SEC, "no model available"
    for model in writer_models()[:4]:
        for attempt in range(3):
            if time.time() > deadline:
                raise RuntimeError(f"writing took too long ({last})")
            r = requests.post(f"{me.GEMINI}/models/{model}:generateContent", headers=me.gemini_headers(),
                              json=body, timeout=max(60, int(deadline - time.time())))
            if r.ok:
                try:
                    parts = r.json()["candidates"][0]["content"]["parts"]
                    txt = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                    data = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
                    assert len(data["lines"]) >= 20 and data["meta"].get("title")
                    assert all(l.get("s") in ("A", "B") and l.get("text") for l in data["lines"])
                    print("script written by", model, "lines:", len(data["lines"]))
                    return data, model
                except Exception as e:
                    last = f"{model}: unusable output ({e})"
                    break
            last = f"{model}: HTTP {r.status_code} {r.text[:200]}"
            if r.status_code not in (429, 500, 503):
                break
            time.sleep(min(me.retry_wait(r, attempt), max(0, deadline - time.time())))
        print("writer failed:", last)
    raise RuntimeError(last)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower())[:40].strip("-") or "paper"


# ---------------- main ----------------
def handle(msg):
    cid = str(msg["chat"]["id"])
    if not os.path.exists(me.CHAT_ID_FILE) or cid != me.chat_id():
        print("ignoring message from an unknown chat")
        return
    mid = msg.get("message_id")
    text = msg.get("text") or msg.get("caption") or ""
    doc = msg.get("document") or {}
    urls = re.findall(r"https?://\S+", text)
    if doc.get("mime_type") == "application/pdf" or doc.get("file_name", "").lower().endswith(".pdf"):
        reply(cid, "📥 קיבלתי את המאמר! הפרק יגיע בעוד 5–10 דקות.", mid)
        pdf = pdf_from_telegram(doc)
    elif urls and not msg.get("reply_to_message"):
        reply(cid, "🔗 קיבלתי את הקישור, בודק אם יש גישה ל-PDF המלא...", mid)
        pdf = pdf_from_url(urls[0])
        if not pdf:
            reply(cid, "🔒 לא הצלחתי להגיע ל-PDF המלא (כנראה מאמר בתשלום). אפשר להוריד אותו דרך האוניברסיטה "
                       "ולשלוח לי את הקובץ עצמו.", mid)
            return
    else:
        return  # a note: nothing to do
    data, model = write_script(pdf, re.sub(r"https?://\S+", "", text).strip())
    day = datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Jerusalem")).strftime("%Y-%m-%d")
    ep = os.path.join(me.ROOT, "episodes", f"{day}-req-{slug(data['meta']['title'])}")
    os.makedirs(ep, exist_ok=True)
    with open(os.path.join(ep, "source.pdf"), "wb") as fh:
        fh.write(pdf)
    me.write_json(os.path.join(ep, "meta.json"), {**data["meta"], "source": "request", "script_model": model})
    me.write_json(os.path.join(ep, "script.json"), {"speakers": me.DEFAULT_SPEAKERS, "lines": data["lines"]})
    status = me.process(ep)
    if status.get("telegram") != "sent":
        raise RuntimeError(status.get("error", "sending failed")[-300:])


def main():
    raw = os.environ.get("TG_MESSAGE_JSON", "").strip()
    if not raw and os.environ.get("GITHUB_EVENT_PATH"):
        with open(os.environ["GITHUB_EVENT_PATH"]) as fh:
            raw = json.dumps((json.load(fh).get("client_payload") or {}).get("message") or {})
    msg = json.loads(raw or "{}")
    if not msg.get("chat"):
        print("no message")
        return
    try:
        handle(msg)
    except Exception as e:
        print(me.redact(e))
        reply(str(msg["chat"]["id"]), f"😕 משהו השתבש ביצירת הפרק: {me.redact(e)[:300]}", msg.get("message_id"))
        sys.exit(1)


if __name__ == "__main__":
    main()
