/* Hriăm — dịch Việt ↔ Ê Đê chạy hoàn toàn trên trình duyệt.
   Dữ liệu: data/dictionary.json và data/pairs.json (tạo bằng scripts/export_web_data.py). */
"use strict";

const MAX_PHRASE = 5;
const LANG = { vi: "Tiếng Việt", ede: "Tiếng Ê Đê" };
const DIRS = { vi2ede: ["vi", "ede"], ede2vi: ["ede", "vi"] };
const CLASSIFIERS = ["cái", "con", "cây", "quả", "trái", "sự", "việc", "người", "bộ", "chiếc"];
const EDE_KEYS = ["ă", "â", "ĕ", "ê", "ê̆", "ĭ", "ŏ", "ô", "ô̆", "ơ", "ơ̆", "ŭ", "ư", "ư̆", "ƀ", "č", "đ", "ñ", "Ƀ", "Č", "Đ", "Ñ"];
const SAMPLES = {
  vi2ede: ["Đen như quạ", "Tôi muốn ăn cơm", "Con chó cắn con gà", "Nhà anh ở đâu?"],
  ede2vi: ["Jŭ msĕ si ak", "Dhŏng khăt", "Ƀŏng boh kroh", "Ti anôk sang ih?"],
};

/* ---------- Xử lý chữ ---------- */
const WORD_RE = /\p{L}[\p{L}\p{M}']*/gu;
const nfc = (s) => s.normalize("NFC");
const words = (s) => (nfc(s).match(WORD_RE) || []).map((w) => w.toLowerCase());
const stripParens = (s) => s.replace(/\s*\([^)]*\)/g, "").trim();
/** Bỏ dấu để tra được cả khi gõ thiếu dấu: "dhong" khớp "Dhŏng". */
const fold = (s) => s.toLowerCase().normalize("NFD").replace(/đ/g, "d").replace(/ƀ/g, "b")
  .replace(/\p{M}/gu, "").normalize("NFC");

function viPhrases(gloss) {
  const out = [];
  for (const part of stripParens(gloss).split(/[,;.]/)) {
    const phrase = words(part).join(" ");
    if (!phrase) continue;
    out.push(phrase);
    for (const c of CLASSIFIERS) if (phrase.startsWith(c + " ")) out.push(phrase.slice(c.length + 1));
  }
  return out;
}

/* ---------- Từ điển ---------- */
class Dictionary {
  constructor(entries) {
    this.entries = entries;
    this.ede = new Map(); this.edeFolded = new Map(); this.vi = new Map();
    const add = (map, key, value) => { if (!map.has(key)) map.set(key, []); map.get(key).push(value); };
    entries.forEach((e, i) => {
      const forms = (e.v.length ? e.v : [e.h]).map(stripParens).concat(e.a);
      for (const form of forms) {
        const key = words(form).join(" ");
        if (key) { add(this.ede, key, i); add(this.edeFolded, fold(key), i); }
      }
      e.s.forEach((sense, rank) => viPhrases(sense[1]).forEach((p, j) => add(this.vi, p, [i, rank + j])));
    });
    for (const [key, list] of this.vi) {
      const best = new Map();
      for (const [i, r] of list) if (!best.has(i) || r < best.get(i)) best.set(i, r);
      this.vi.set(key, [...best].sort((a, b) => a[1] - b[1] || entries[a[0]].h.length - entries[b[0]].h.length).map((x) => x[0]));
    }
  }

  lookup(tokens, lang) {
    const key = tokens.join(" ");
    if (lang === "ede") {
      if (this.ede.has(key)) return [this.ede.get(key), true];
      return [this.edeFolded.get(fold(key)) || [], false];
    }
    return [this.vi.get(key) || [], true];
  }

  /** Ghép theo cụm dài nhất khớp từ điển, từ trái sang phải. */
  segment(text, lang) {
    const tokens = words(text), out = [];
    let i = 0;
    while (i < tokens.length) {
      // "con dao": "con" chỉ là từ chỉ loại, tránh dịch thành "Anak" (con cái).
      if (lang === "vi" && CLASSIFIERS.includes(tokens[i]) && i + 1 < tokens.length
          && this.lookup(tokens.slice(i + 1, i + 2), lang)[0].length
          && !this.lookup(tokens.slice(i, i + 2), lang)[0].length) {
        out.push({ text: tokens[i], entries: [], exact: true, classifier: true });
        i += 1;
        continue;
      }
      let matched = false;
      for (let size = Math.min(MAX_PHRASE, tokens.length - i); size > 0; size--) {
        const [found, exact] = this.lookup(tokens.slice(i, i + size), lang);
        if (found.length) {
          out.push({ text: tokens.slice(i, i + size).join(" "), entries: found.slice(0, 6), exact });
          i += size; matched = true; break;
        }
      }
      if (!matched) { out.push({ text: tokens[i], entries: [], exact: false }); i += 1; }
    }
    return out;
  }

  short(index, lang) {
    const e = this.entries[index];
    if (lang === "ede") return e.s.length ? stripParens(e.s[0][1]).split(/[,;]/)[0].trim() : "";
    return e.v.length ? e.v[0] : stripParens(e.h);
  }

  search(query, limit = 24) {
    const q = words(query).join(" ");
    if (!q) return [];
    const fq = fold(q), hits = [];
    const wordRe = new RegExp(`(^|\\s)${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(\\s|$)`);
    this.entries.forEach((e, i) => {
      const head = words(stripParens(e.h)).join(" ");
      let rank;
      if (head === q) rank = 0;
      else if (e.s.some((s) => viPhrases(s[1]).includes(q))) rank = 1;
      else if (fold(head) === fq) rank = 2;
      else if (head.startsWith(q) || fold(head).startsWith(fq)) rank = 3;
      else if (e.s.some((s) => wordRe.test(words(s[1]).join(" ")))) rank = 4;
      else return;
      hits.push([rank, head.length, i]);
    });
    return hits.sort((a, b) => a[0] - b[0] || a[1] - b[1]).slice(0, limit).map((h) => h[2]);
  }
}

/* ---------- Tìm câu tương tự: TF-IDF trên n-gram 3 ký tự ---------- */
class SentenceIndex {
  static grams(text, lang) {
    const counts = new Map();
    const tokens = lang === "ede" ? (fold(text).match(/\p{L}+/gu) || []) : words(text);
    for (const w of tokens) {
      const padded = ` ${w} `;
      for (let i = 0; i + 3 <= padded.length; i++) {
        const g = padded.slice(i, i + 3);
        counts.set(g, (counts.get(g) || 0) + 1);
      }
    }
    return counts;
  }

  /** Dựng chỉ mục theo từng phần, nhường trình duyệt giữa các phần để trang không bị đơ. */
  static async build(texts, lang) {
    const self = new SentenceIndex();
    const docs = new Array(texts.length), df = new Map();
    for (let start = 0; start < texts.length; start += 3000) {
      for (let d = start; d < Math.min(start + 3000, texts.length); d++) {
        docs[d] = SentenceIndex.grams(texts[d], lang);
        for (const g of docs[d].keys()) df.set(g, (df.get(g) || 0) + 1);
      }
      await new Promise((r) => setTimeout(r));
    }
    const n = texts.length;
    self.n = n;
    self.idf = new Map();
    for (const [g, c] of df) self.idf.set(g, Math.log((1 + n) / (1 + c)) + 1);
    const postings = new Map();
    self.norm = new Float32Array(n);
    for (let d = 0; d < n; d++) {
      let sum = 0;
      for (const [g, tf] of docs[d]) {
        const w = (1 + Math.log(tf)) * self.idf.get(g);
        sum += w * w;
        let p = postings.get(g);
        if (!p) postings.set(g, (p = { ids: [], ws: [] }));
        p.ids.push(d); p.ws.push(w);
      }
      self.norm[d] = Math.sqrt(sum) || 1;
      docs[d] = null;
      if (d % 5000 === 4999) await new Promise((r) => setTimeout(r));
    }
    self.postings = new Map();
    for (const [g, p] of postings) self.postings.set(g, [Int32Array.from(p.ids), Float32Array.from(p.ws)]);
    return self;
  }

  search(text, lang, k = 6, threshold = 0.12) {
    const scores = new Float32Array(this.n);
    let qnorm = 0;
    for (const [g, tf] of SentenceIndex.grams(text, lang)) {
      const idf = this.idf.get(g);
      if (!idf) continue;
      const wq = (1 + Math.log(tf)) * idf;
      qnorm += wq * wq;
      const [ids, ws] = this.postings.get(g);
      for (let j = 0; j < ids.length; j++) scores[ids[j]] += wq * ws[j];
    }
    qnorm = Math.sqrt(qnorm) || 1;
    const top = [];
    for (let d = 0; d < this.n; d++) {
      if (!scores[d]) continue;
      const s = scores[d] / (qnorm * this.norm[d]);
      if (s < threshold) continue;
      if (top.length < k) { top.push([s, d]); top.sort((a, b) => b[0] - a[0]); }
      else if (s > top[k - 1][0]) { top[k - 1] = [s, d]; top.sort((a, b) => b[0] - a[0]); }
    }
    return top;
  }
}

/* ---------- Trạng thái và tải dữ liệu ---------- */
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n) => n.toLocaleString("vi-VN");
/** Trạng thái trống dùng một hoạ tiết đơn lẻ của bộ nhận diện (assets/brand/icon-*.svg). */
const emptyState = (motif, text) =>
  `<p class="empty-state"><img src="assets/brand/icon-${motif}.svg" alt="" width="44" height="36">${esc(text)}</p>`;
const state = { dict: null, pairs: null, sources: [], index: {}, building: {}, direction: "vi2ede" };
try { state.direction = localStorage.getItem("hriam.direction") || "vi2ede"; } catch (e) { /* trình duyệt chặn bộ nhớ */ }
if (!DIRS[state.direction]) state.direction = "vi2ede";

async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

function indexFor(lang) {
  if (!state.pairs) return Promise.resolve(null);
  if (!state.building[lang]) {
    state.building[lang] = SentenceIndex.build(state.pairs.map((r) => (lang === "ede" ? r[0] : r[1])), lang)
      .then((idx) => (state.index[lang] = idx));
  }
  return state.building[lang];
}

/* ---------- Dịch ---------- */
let timer = null, seq = 0;

function onInput(now = false) {
  $("count").textContent = `${$("input").value.length}/2000`;
  clearTimeout(timer);
  timer = setTimeout(translate, now ? 0 : 350);
}

async function translate() {
  const text = nfc($("input").value.trim());
  if (!text) return reset();
  if (!state.dict) { $("timing").innerHTML = '<span class="spin"></span> Đang tải từ điển…'; return; }
  const mine = ++seq, started = performance.now();
  const [src, tgt] = DIRS[state.direction];

  const gloss = [], cardIds = [];
  for (const seg of state.dict.segment(text, src)) {
    const options = [];
    for (const i of seg.entries) {
      const value = state.dict.short(i, src);
      if (value && !options.some((o) => o.toLowerCase() === value.toLowerCase())) options.push(value);
      if (!cardIds.includes(i) && cardIds.length < 12) cardIds.push(i);
    }
    gloss.push({ source: seg.text, options: options.slice(0, 4), exact: seg.exact, classifier: !!seg.classifier });
  }
  let draft = gloss.filter((g) => !g.classifier)
    .map((g) => (g.options.length ? g.options[0].toLowerCase() : `[${g.source}]`)).join(" ");
  draft = draft.charAt(0).toUpperCase() + draft.slice(1);

  renderDraft(draft);
  renderGloss(gloss);
  $("cards").innerHTML = cardIds.length ? cardIds.map(card).join("") : '<span class="empty">Không có mục từ nào khớp.</span>';

  if (!state.index[src]) $("pairs").innerHTML = '<span class="empty"><span class="spin"></span> Đang chuẩn bị kho câu, lần đầu mất vài giây…</span>';
  const index = await indexFor(src);
  if (mine !== seq) return;
  const hits = index ? index.search(text, src) : [];
  renderPairs(hits.map(([score, d]) => ({ score, row: state.pairs[d] })), src, tgt, text);
  $("timing").textContent = `${Math.round(performance.now() - started)} ms`;
}

function renderDraft(draft) {
  const out = $("output");
  out.className = "result";
  out.textContent = draft;
  $("kind").textContent = "Ghép nghĩa từng từ";
  $("note").hidden = false;
  $("note").textContent = "Bản ghép nghĩa theo từ điển, chưa theo ngữ pháp Ê Đê. Hãy đối chiếu với các câu tương tự bên dưới.";
  $("copy").disabled = false;
}

function renderGloss(gloss) {
  $("gloss").innerHTML = gloss.length ? gloss.map((g) => {
    const cls = g.classifier ? "tok cls" : !g.options.length ? "tok miss" : !g.exact ? "tok fuzzy" : "tok";
    const main = g.classifier ? "(từ chỉ loại)" : g.options[0] || "—";
    const alt = g.options.slice(1).join(" · ");
    return `<div class="${cls}"><b>${esc(g.source)}</b><i>${esc(main)}</i>${alt ? `<div class="alt">${esc(alt)}</div>` : ""}</div>`;
  }).join("") : '<span class="empty">Không có từ nào.</span>';
}

function renderPairs(items, src, tgt, text) {
  const col = { ede: 0, vi: 1 };
  const same = (a) => fold(a).replace(/[^\p{L}\s]/gu, "").trim() === fold(text).replace(/[^\p{L}\s]/gu, "").trim();
  $("pairs").innerHTML = items.length ? items.map(({ score, row }) => {
    const source = state.sources[row[2]] || "";
    return `<div class="pair${same(row[col[src]]) ? " exact" : ""}">
      <div><span class="lang">${LANG[src]}</span>${esc(row[col[src]])}</div>
      <div><span class="lang">${LANG[tgt]}</span>${esc(row[col[tgt]])}</div>
      <div class="meta">${esc(source)}${row[3] ? " · " + esc(row[3]) : ""}
        <div class="bar" title="Độ giống ${Math.round(score * 100)}%"><div style="width:${Math.round(Math.min(1, score) * 100)}%"></div></div></div>
    </div>`;
  }).join("") : emptyState("rua", state.pairs ? "Không tìm thấy câu tương tự." : "Kho câu chưa tải xong.");
}

function card(i) {
  const e = state.dict.entries[i];
  return `<article class="card">
    <h3>${esc(e.h)}</h3>
    <div class="pos">${esc(e.p.join(", "))}${e.pg ? `${e.p.length ? " · " : ""}trang ${e.pg}` : ""}</div>
    <ol>${e.s.map(([, gloss, pos, examples]) => `<li>${pos ? `<span class="pos">${esc(pos)}.</span> ` : ""}${esc(gloss)}
      ${examples.slice(0, 4).map(([ede, vi]) => `<div class="ex"><em>${esc(ede)}</em>: ${esc(vi)}</div>`).join("")}</li>`).join("")}</ol>
  </article>`;
}

function reset() {
  seq++;
  $("output").className = "result placeholder";
  $("output").textContent = "Bản dịch sẽ hiện ở đây.";
  $("note").hidden = true; $("kind").textContent = ""; $("timing").textContent = ""; $("copy").disabled = true;
  $("gloss").innerHTML = emptyState("chuon-chuon", "Nhập một câu để bắt đầu.");
  for (const id of ["pairs", "cards"]) $(id).innerHTML = '<span class="empty">Chưa có.</span>';
}

/* ---------- Giao diện ---------- */
function renderDirection() {
  const [src, tgt] = DIRS[state.direction];
  $("srcName").textContent = LANG[src];
  $("tgtName").textContent = LANG[tgt];
  setKeyboard(src === "ede");
  $("samples").innerHTML = "<span>Thử</span>" +
    SAMPLES[state.direction].map((s) => `<button type="button">${esc(s)}</button>`).join("");
  $("samples").querySelectorAll("button").forEach((b) => (b.onclick = () => { $("input").value = b.textContent; onInput(true); }));
}

function setKeyboard(open) {
  $("keys").hidden = !open;
  $("kbd").setAttribute("aria-expanded", String(open));
  $("kbd").textContent = open ? "Ẩn bàn phím" : "Bàn phím Ê Đê";
}

function insertKey(ch) {
  const t = $("input"), a = t.selectionStart, b = t.selectionEnd;
  t.value = t.value.slice(0, a) + ch + t.value.slice(b);
  t.selectionStart = t.selectionEnd = a + ch.length;
  t.focus();
  onInput();
}

let lookupTimer = null;
function runLookup() {
  const q = $("q").value;
  if (!state.dict || !q.trim()) { $("lookup").innerHTML = ""; return; }
  const ids = state.dict.search(q);
  $("lookup").innerHTML = ids.length ? ids.map(card).join("") : emptyState("than-lan", "Không tìm thấy mục từ nào. Thử gõ không dấu hoặc gõ nghĩa tiếng Việt.");
}

$("keys").innerHTML = EDE_KEYS.map((k) => `<button type="button">${k}</button>`).join("");
$("keys").querySelectorAll("button").forEach((b) => (b.onclick = () => insertKey(b.textContent)));
$("input").addEventListener("input", () => onInput());
$("input").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); onInput(true); } });
$("kbd").onclick = () => setKeyboard($("keys").hidden);
$("clear").onclick = () => { $("input").value = ""; onInput(true); $("input").focus(); };
$("copy").onclick = async () => {
  try { await navigator.clipboard.writeText($("output").textContent); $("timing").textContent = "Đã chép"; }
  catch (e) { $("timing").textContent = "Không chép được"; }
};
$("swap").onclick = () => {
  state.direction = state.direction === "vi2ede" ? "ede2vi" : "vi2ede";
  try { localStorage.setItem("hriam.direction", state.direction); } catch (e) { /* bỏ qua */ }
  renderDirection();
  onInput(true);
};
$("q").addEventListener("input", () => { clearTimeout(lookupTimer); lookupTimer = setTimeout(runLookup, 200); });

// Link chia sẻ được: ?dir=ede2vi&text=Jŭ msĕ si ak
const params = new URLSearchParams(location.search);
if (DIRS[params.get("dir")]) state.direction = params.get("dir");
if (params.get("text")) { $("input").value = params.get("text").slice(0, 2000); $("count").textContent = `${$("input").value.length}/2000`; }
if (params.get("q")) $("q").value = params.get("q").slice(0, 100);

renderDirection();
loadJSON("data/dictionary.json").then((data) => {
  state.dict = new Dictionary(data.entries);
  $("factEntries").textContent = fmt(data.entries.length);
  if ($("input").value.trim()) onInput(true);
  if ($("q").value.trim()) runLookup();
}).catch((err) => {
  $("lead").textContent = `Không tải được từ điển (${err.message}). Hãy mở trang qua một web server, không mở trực tiếp file.`;
});
loadJSON("data/pairs.json").then((data) => {
  state.pairs = data.rows;
  state.sources = data.sources;
  $("factPairs").textContent = fmt(data.rows.length);
  $("lead").textContent = `Tra ${$("factEntries").textContent} mục từ và tìm trong ${fmt(data.rows.length)} cặp câu song ngữ, ngay trên trình duyệt của bạn.`;
  indexFor(DIRS[state.direction][0]);
  if ($("input").value.trim()) onInput(true);
}).catch(() => { /* web vẫn tra từ được khi thiếu kho câu */ });
