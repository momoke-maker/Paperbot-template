// Google Apps Script relay: Telegram bot -> GitHub "Episode on request" workflow.
// Runs on your own Google account, once a minute (free). Only a PDF, or a link that is not a
// reply, from your chat starts a run. Everything else (notes, replies) is ignored.
//
// Script properties (Project Settings -> Script properties):
//   TELEGRAM_BOT_TOKEN, GH_TOKEN (fine-grained, your repo only, Contents: read & write), CHAT_ID
// First time: choose the function "setup" and press Run.

const REPO = 'YOUR-GITHUB-USERNAME/YOUR-REPO-NAME'; // <-- change this

function checkTelegram() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    const p = PropertiesService.getScriptProperties();
    const token = p.getProperty('TELEGRAM_BOT_TOKEN');
    const gh = p.getProperty('GH_TOKEN');
    const chat = String(p.getProperty('CHAT_ID'));
    const offset = Number(p.getProperty('OFFSET') || 0);

    const url = 'https://api.telegram.org/bot' + token + '/getUpdates?timeout=0&offset=' + offset;
    const res = JSON.parse(UrlFetchApp.fetch(url, { muteHttpExceptions: true }).getContentText());
    if (!res.ok || !res.result.length) return;

    let next = offset;
    res.result.forEach(function (u) {
      next = u.update_id + 1;
      const m = u.message;
      if (!m || String(m.chat.id) !== chat) return;
      const doc = m.document;
      const isPdf = doc && (doc.mime_type === 'application/pdf' || /\.pdf$/i.test(doc.file_name || ''));
      const text = m.text || m.caption || '';
      const hasLink = /https?:\/\/\S+/.test(text) && !m.reply_to_message;
      if (!isPdf && !hasLink) return; // a note - nothing to do

      UrlFetchApp.fetch('https://api.github.com/repos/' + REPO + '/dispatches', {
        method: 'post',
        contentType: 'application/json',
        headers: { Authorization: 'Bearer ' + gh, Accept: 'application/vnd.github+json' },
        payload: JSON.stringify({ event_type: 'telegram', client_payload: { message: m } }),
        muteHttpExceptions: true,
      });
    });
    p.setProperty('OFFSET', String(next));
  } finally {
    lock.releaseLock();
  }
}

function setup() {
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('checkTelegram').timeBased().everyMinutes(1).create();
  checkTelegram();
}
