"""On-demand episodes: The listener sends the bot a PDF or a link -> Gemini writes the script -> audio -> Telegram.

Triggered by the Cloudflare relay via repository_dispatch (event_type "telegram"), with the Telegram
message in client_payload.message. Run manually with TG_MESSAGE_JSON to test.
"""
import base64, datetime, json, os, re, sys, time, traceback
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_episode as me

ROOT = me.ROOT
GEMINI = me.GEMINI
UA = {"User-Agent": "Mozilla/5.0 (paperbot; personal use)"}


def tg(method, **data):
    token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    return requests.post(f"https://api.telegram.org/bot{token}/{method}", data=data, timeout=60).json()


def reply(chat_id, text, reply_to=None):
    kw = {"chat_id": chat_id, "text": text}
    if reply_to:
        kw["reply_to_message_id"] = reply_to
    tg("sendMessage", **kw)


# ---------------- getting the PDF ----------------
def pdf_from_telegram(doc):
    token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    info = tg("getFile", file_id=doc["file_id"])
    if not info.get("ok"):
        raise RuntimeError("לא הצלחתי להוריד את הקובץ מטלגרם (אולי הוא גדול מ-20MB)")
    path = info["result"]["file_path"]
    return requests.get(f"https://api.telegram.org/file/bot{token}/{path}", timeout=120).content


def fetch_pdf(url):
    r = requests.get(url, headers=UA, timeout=60, allow_redirects=True)
    if r.ok and (r.content[:5] == b"%PDF-" or "pdf" in r.headers.get("content-type", "")):
        return r.content, None
    html = r.text if r.ok else ""
    return None, html


def pdf_from_url(url):
    m = re.search(r"arxiv\.org/abs/([\w.\-/]+)", url)
    if m:
        url = f"https://arxiv.org/pdf/{m.group(1)}"
    pdf, html = fetch_pdf(url)
    if pdf:
        return pdf
    # publisher page that exposes a PDF link
    m = re.search(r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)', html or "", re.I)
    if m:
        pdf, _ = fetch_pdf(m.group(1))
        if pdf:
            return pdf
    # open-access copy via OpenAlex
    doi = re.search(r"10\.\d{4,9}/[^\s\"'<>?#]+", url) or re.search(
        r'citation_doi["\'][^>]+content=["\'](10\.[^"\']+)', html or "", re.I)
    if doi:
        d = doi.group(1) if doi.lastindex else doi.group(0)
        try:
            w = requests.get(f"https://api.openalex.org/works/doi:{d.rstrip('.')}", timeout=30).json()
            cands = [(w.get("best_oa_location") or {}).get("pdf_url"), (w.get("open_access") or {}).get("oa_url")]
            cands += [l.get("pdf_url") for l in w.get("locations", []) if l.get("is_oa")]
            for c in filter(None, cands):
                pdf, _ = fetch_pdf(c)
                if pdf:
                    return pdf
        except Exception as e:
            print("openalex:", e)
    return None


# ---------------- Gemini writes the script ----------------
def writer_models(key):
    r = requests.get(f"{GEMINI}/models", params={"key": key, "pageSize": 200}, timeout=30).json()
    out = []
    for m in r.get("models", []):
        n = m["name"].split("/")[-1]
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        if any(x in n for x in ["tts", "image", "live", "embed", "audio", "lite", "nano", "gemma", "robotics", "computer"]):
            continue
        if "pro" not in n and "flash" not in n:
            continue
        ver = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
        out.append((float(ver.group(1)) if ver else 0, "pro" in n, "preview" not in n and "exp" not in n, n))
    out.sort(reverse=True)
    names = [o[3] for o in out]
    return names or ["gemini-2.5-pro", "gemini-2.5-flash"]


def write_script(pdf, note=""):
    key = os.environ["GEMINI_API_KEY"].strip()
    guide = open(os.path.join(ROOT, "config", "episode_guidelines.md"), encoding="utf-8").read()
    guide += "\n\n" + open(os.path.join(ROOT, "config", "listener.md"), encoding="utf-8").read()
    prompt = (guide + "\n\n---\nTASK: Write the episode for the attached paper, following the guidelines exactly. "
              "Return ONLY a JSON object: {\"meta\": {...meta.json fields...}, \"lines\": [{\"s\": \"A\"|\"B\", \"text\": \"...\"}]}. "
              "Set meta.source to \"request\"." + (f"\nThe listener's note with the request: {note}" if note else ""))
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "application/pdf",
                                                     "data": base64.b64encode(pdf).decode()}},
                                    {"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}}
    last = None
    for model in writer_models(key)[:4]:
        for attempt in range(3):
            r = requests.post(f"{GEMINI}/models/{model}:generateContent", params={"key": key}, json=body, timeout=600)
            if r.status_code == 200:
                try:
                    txt = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"]
                                  if not p.get("thought"))
                    data = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
                    assert len(data["lines"]) >= 20 and data["meta"].get("title")
                    print("script written by", model, "lines:", len(data["lines"]))
                    return data, model
                except Exception as e:
                    last = f"{model}: bad output {e}"
                    break
            last = f"{model}: HTTP {r.status_code} {r.text[:200]}"
            if r.status_code in (429, 500, 503):
                time.sleep(30 * (attempt + 1))
                continue
            break
        print("writer failed:", last)
    raise RuntimeError(last)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower())[:40].strip("-") or "paper"


# ---------------- main ----------------
def handle(msg):
    cid = str(msg["chat"]["id"])
    allowed = open(me.CHAT_ID_FILE).read().strip() if os.path.exists(me.CHAT_ID_FILE) else cid
    if cid != allowed:
        print("ignoring message from another chat")
        return
    mid = msg["message_id"]
    text = msg.get("text") or msg.get("caption") or ""
    doc = msg.get("document")
    urls = re.findall(r"https?://\S+", text)
    if msg.get("repo_pdf"):
        pdf = open(os.path.join(ROOT, msg["repo_pdf"]), "rb").read()
        reply(cid, "📥 קיבלתי את המאמר! מכינה פרק, זה ייקח בערך 5–10 דקות.")
    elif doc and (doc.get("mime_type") == "application/pdf" or doc.get("file_name", "").lower().endswith(".pdf")):
        reply(cid, "📥 קיבלתי את המאמר! מכינה פרק, זה ייקח בערך 5–10 דקות.", mid)
        pdf = pdf_from_telegram(doc)
    elif urls and not msg.get("reply_to_message"):
        reply(cid, "🔗 קיבלתי את הקישור, בודקת אם יש גישה ל-PDF...", mid)
        pdf = pdf_from_url(urls[0])
        if not pdf:
            reply(cid, "🔒 לא הצלחתי להגיע ל-PDF המלא (כנראה מאמר בתשלום). אפשר להוריד אותו דרך האוניברסיטה ולשלוח לי את הקובץ עצמו.", mid)
            return
    else:
        return  # notes etc. - nothing to do
    note = re.sub(r"https?://\S+", "", text).strip()
    data, model = write_script(pdf, note)
    day = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2))).strftime("%Y-%m-%d")
    ep = os.path.join(ROOT, "episodes", f"{day}-req-{slug(data['meta']['title'])}{msg.get('suffix', '')}")
    os.makedirs(ep, exist_ok=True)
    open(os.path.join(ep, "source.pdf"), "wb").write(pdf)
    meta = data["meta"]
    meta["source"], meta["script_model"] = "request", model
    json.dump(meta, open(os.path.join(ep, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump({"speakers": me.DEFAULT_SPEAKERS, "lines": data["lines"]},
              open(os.path.join(ep, "script.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    st = me.process(ep)
    if st.get("telegram") != "sent":
        raise RuntimeError(st.get("telegram"))


def main():
    raw = os.environ.get("TG_MESSAGE_JSON", "").strip()
    if not raw and os.environ.get("GITHUB_EVENT_PATH"):
        ev = json.load(open(os.environ["GITHUB_EVENT_PATH"]))
        raw = json.dumps((ev.get("client_payload") or {}).get("message") or {})
    msg = json.loads(raw or "{}")
    if not msg:
        print("no message")
        return
    try:
        handle(msg)
    except Exception as e:
        traceback.print_exc()
        reply(str(msg["chat"]["id"]), f"😕 משהו השתבש ביצירת הפרק: {str(e)[:300]}", msg.get("message_id"))
        sys.exit(1)


if __name__ == "__main__":
    main()
