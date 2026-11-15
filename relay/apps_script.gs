// Paperbot relay (Google Apps Script, runs on your own Google account, free).
// Every minute it asks Telegram for new messages to the bot. A PDF, or a link that is not a reply,
// from your chat starts the "Episode on request" GitHub workflow. Everything else (notes) is ignored.
//
// Script properties (Project Settings -> Script properties):
//   TELEGRAM_BOT_TOKEN, GH_TOKEN (fine-grained token, only your repo, Contents: read & write), CHAT_ID
// First time: choose the function "setup" and press Run.

const REPO = 'YOUR-GITHUB-USERNAME/YOUR-REPO-NAME'; // <-- change this

function checkTelegram() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return; // the previous run is still working
  try {
    const props = PropertiesService.getScriptProperties();
    const token = props.getProperty('TELEGRAM_BOT_TOKEN');
    const chat = String(props.getProperty('CHAT_ID'));
    const offset = Number(props.getProperty('OFFSET') || 0);

    const res = JSON.parse(UrlFetchApp.fetch(
      'https://api.telegram.org/bot' + token + '/getUpdates?timeout=0&offset=' + offset,
      { muteHttpExceptions: true }).getContentText());
    if (!res.ok) return;

    res.result.forEach(function (update) {
      // remember progress per message, so a failure never makes a message run twice
      props.setProperty('OFFSET', String(update.update_id + 1));
      const msg = update.message;
      if (!msg || String(msg.chat.id) !== chat || !wantsEpisode(msg)) return;
      const code = startEpisode(props.getProperty('GH_TOKEN'), msg);
      if (code !== 204) {
        notify(token, chat, '⚠️ לא הצלחתי להפעיל את יצירת הפרק (GitHub החזיר ' + code + '). ' +
          'אם עברה שנה מההקמה, כנראה שפג תוקף ה-GH_TOKEN וצריך ליצור חדש (README, שלב 9).');
      }
    });
  } finally {
    lock.releaseLock();
  }
}

function wantsEpisode(msg) {
  const doc = msg.document;
  const isPdf = doc && (doc.mime_type === 'application/pdf' || /\.pdf$/i.test(doc.file_name || ''));
  const text = msg.text || msg.caption || '';
  const isLink = /https?:\/\/\S+/.test(text) && !msg.reply_to_message;
  return Boolean(isPdf || isLink);
}

function startEpisode(ghToken, msg) {
  return UrlFetchApp.fetch('https://api.github.com/repos/' + REPO + '/dispatches', {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + ghToken, Accept: 'application/vnd.github+json' },
    payload: JSON.stringify({ event_type: 'telegram', client_payload: { message: msg } }),
    muteHttpExceptions: true,
  }).getResponseCode();
}

function notify(token, chat, text) {
  UrlFetchApp.fetch('https://api.telegram.org/bot' + token + '/sendMessage', {
    method: 'post', payload: { chat_id: chat, text: text }, muteHttpExceptions: true,
  });
}

function setup() {
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('checkTelegram').timeBased().everyMinutes(1).create();
  checkTelegram();
}
