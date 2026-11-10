"""Dựng bộ dữ liệu cuối của Từ điển Êđê – Việt: JSON + Excel.

Chạy lần lượt (DICT_TAG=AC cho A–Č, mặc định; DICT_TAG=DY cho D–Y):
    python -I scripts/parse_ac.py       # data/verified/<TAG>/*.txt -> _parsed.json
    python -I scripts/validate_ac.py    # kiểm tra chính tả -> validation_report.json
    python scripts/build_ac.py          # -> dictionary_<TAG>.json, dictionary_<TAG>.xlsx (cần openpyxl: KHÔNG dùng -I)
"""
import difflib
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dict_xlsx import write_workbook  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = os.environ.get('DICT_TAG', 'AC')
SHARED = os.path.join(ROOT, 'data', 'dictionary', 'reference')   # bảng viết tắt + bảng chữ cái dùng chung
D = os.path.join(ROOT, 'data', 'dictionary', '_build', TAG)
RAW = os.path.join(ROOT, 'data', 'raw', 'dict_transcribed')
VER = os.path.join(ROOT, 'data', 'verified', TAG)
SCOPE = {'AC': 'A–Č', 'DY': 'D–Y'}[TAG]
PDF_PAGES = {'AC': 'trang PDF 7–26 = trang sách 5–24', 'DY': 'trang PDF 27–168'}[TAG]


def nfc(s):
    return unicodedata.normalize('NFC', s)


def tidy(s):
    """Chuẩn hóa khoảng trắng/dấu câu (không đụng vào chữ)."""
    s = nfc(s)
    s = re.sub(r'\(\s+', '(', s)
    s = re.sub(r'\s+\)', ')', s)
    s = re.sub(r'\s+([.,;:])', r'\1', s)
    s = re.sub(r'\s{2,}', ' ', s)
    return s.strip()


AB = json.load(open(os.path.join(SHARED, 'abbreviations.json'), encoding='utf8'))
ALPHA = json.load(open(os.path.join(SHARED, 'alphabet.json'), encoding='utf8'))
PARSED = json.load(open(os.path.join(D, '_parsed.json'), encoding='utf8'))
REPORT = json.load(open(os.path.join(D, 'validation_report.json'), encoding='utf8'))

def nfd(s):
    return unicodedata.normalize('NFD', s)


_LETTERS = sorted((nfd(x[0]).upper() for x in ALPHA['letters']), key=len, reverse=True)
_BACK = {nfd(x[0]).upper(): nfc(x[0]) for x in ALPHA['letters']}


def letter_of(headword):
    """Chữ cái (theo bảng chữ cái Êđê) mà mục từ thuộc về; khớp dài nhất, gồm Ê̆, Ô̆, Ơ̆, Ư̆."""
    h = nfd(headword).lstrip("'’ ").upper()
    for L in _LETTERS:
        if h.startswith(L):
            return _BACK[L]
    return nfc(headword[:1].upper())


POS_FULL = dict(AB['abbreviations'])
POS_FULL['hư từ'] = 'Hư từ (in nguyên chữ trong sách; không có trong bảng viết tắt)'
POS_FULL['ct'] = ("ct – KHÔNG có trong bảng viết tắt của sách; các mục này là từ cảm thán "
                  "nên nhiều khả năng là 'tht' (Thán từ)")
for _c in ('ht', 'bt', 'pt'):
    POS_FULL[_c] = (f"{_c} – KHÔNG có trong bảng viết tắt của sách; sách in như vậy, giữ nguyên "
                    "(chưa rõ nghĩa chính xác)")
UNLISTED = {'ct', 'ht', 'bt', 'pt'}
LOAN_FULL = AB['loan_sources']

# Ghi chú theo từ đầu mục: chỗ sách in chưa nhất quán / nghi lỗi in. Không tự ý sửa nghĩa, chỉ báo.
NOTES = {
    'Buôr': "Sách ghi (đt) = đại từ nhưng nghĩa 'Hạch' là danh từ; nghi lỗi in của (dt).",
    'Čuê': "Sách ghi (đt) = đại từ nhưng nghĩa 'Lối mòn… nối (dây)' không phải đại từ; nghi lỗi in của (dt).",
    'Čhưn ênguê': "Bản in thiếu dấu '(' ở '(đt)'; từ loại đt (đại từ) cũng đáng ngờ.",
    'Ƀaih': "Sách ghi (ct) – không có trong bảng viết tắt; nhiều khả năng là tht (thán từ).",
    'Ƀaih haih': "Sách ghi (ct) – không có trong bảng viết tắt; nhiều khả năng là tht (thán từ).",
    'Anôk dôk': "Sách in 'chổ ở'; đã sửa thành 'chỗ ở' cho đúng chính tả tiếng Việt.",
    'Ƀap': "Sách thiếu dấu ':' trước 'Ví xách tay'; đã bổ sung.",
    'Čar': "Sách thiếu dấu '.' sau 'Tỉnh'; đã bổ sung để tách nghĩa và ví dụ.",
    'Čê̆č': "Sách in 'Giằm'; đã ghi 'Giầm' (đúng chính tả: giầm = ngâm).",
    'Čhŭñ': "Sách dùng ';' thay cho ':' sau ví dụ; đã đổi thành ':'.",
    'Čô': "Sách dùng ';' thay cho ':' ở 'Sa čô anak; Một đứa con'; đã đổi thành ':'.",
    'Čŭt': "Sách thiếu dấu '.' sau '(chỉ dùng cho mặc quần)'; đã bổ sung.",
    'Čuăn': "Sách in 'Qui định' (cách viết cũ của 'quy định'); giữ nguyên như sách.",
    'Bhiăn': "Sách ghi nguyên chữ (phó từ) thay vì viết tắt; quy về pht (Phụ từ).",
    # ---- D–Y
    'Mrai': "Sách in 'Aó đứt chỉ' (lỗi in của 'Áo'); giữ nguyên như sách.",
    'Mtah': "Sách in 'Qủa xanh', 'Aó màu xanh' (lỗi in của 'Quả', 'Áo'); giữ nguyên như sách.",
    'Kyâo yuôm': "Sách in 'gỗ qúy' ở ví dụ (lỗi in của 'quý'); giữ nguyên như sách.",
    'Mbliư̆ mlih': "Sách in 'Qúa trình' (lỗi in của 'Quá'); giữ nguyên như sách.",
    'Mgao': "Sách in 'Qúa trớn' (lỗi in của 'Quá'); giữ nguyên như sách.",
    'Djuh': "Sách ghi (đt) = đại từ nhưng nghĩa 'Củi' là danh từ; nghi lỗi in của (dt).",
    'Êhưng': "Bản in thiếu dấu '(' ở '(tt)'; đã bổ sung.",
    'Ênai': "Bản in thiếu dấu '(' ở '(đt)'; đã bổ sung. Nghĩa 'Tiếng' là danh từ nên (đt) đáng ngờ.",
    'Hwak': "Sách in 'Hwak (đgt). Nh. Êwak' (nh = như, tức đồng nghĩa với Êwak); đã chuyển 'Nh. Êwak' vào phần nghĩa.",
    'Ksĭng': "Sách ghi '(trtừ)' dính liền; quy về trt (Trợ từ).",
    'Mpliê': "Bản chép tay cũ ghi 'Bửa'; ảnh scan in 'Bừa'; đã sửa.",
}


def pos_obj(code):
    return {'code': code, 'full': POS_FULL.get(code, code)}


def sense_label(s):
    parts = []
    if s['roman']:
        parts.append(s['roman'] + '.')
    if s['number']:
        parts.append(f"{s['number']}.")
    return ' '.join(parts)


# ---------------- bảng sửa lỗi so với bản chép tay ban đầu
def tok(s):
    return re.findall(r'\S+', nfc(s))


corrections = []
for fn in sorted(os.listdir(VER)):
    a = open(os.path.join(RAW, fn), encoding='utf8').read().splitlines()
    b = open(os.path.join(VER, fn), encoding='utf8').read().splitlines()
    page = int(re.search(r'p(\d+)', fn).group(1))
    for old, new in zip(a, b):
        if nfc(old) == nfc(new):
            continue
        sm = difflib.SequenceMatcher(None, tok(old), tok(new), autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == 'equal':
                continue
            corrections.append({'pdf_page': page, 'book_page': page - 2,
                                'headword': nfc(old.split('|')[0].strip()) or '(dòng nối tiếp của mục trước)',
                                'old': ' '.join(tok(old)[i1:i2]), 'new': ' '.join(tok(new)[j1:j2])})

# ---------------- dựng entries
entries = []
for e in PARSED:
    hw = tidy(e['headword'])
    senses = []
    for i, s in enumerate(e['senses'], 1):
        senses.append({
            'index': i,
            'label': sense_label(s),
            'pos': pos_obj(s['pos']) if s['pos'] else None,
            'gloss_vi': tidy(s['gloss']),
            'examples': [{'ede': tidy(x['ede']), 'vi': tidy(x['vi'])} for x in s['examples']],
        })
    notes = []
    key = hw
    if key in NOTES:
        notes.append(NOTES[key])
    if 'phó từ' in e['raw'].split('|')[0]:
        notes.append(NOTES['Bhiăn'])
    used = set(e['pos']) | {s['pos'] for s in e['senses'] if s['pos']}
    for u in sorted(used & UNLISTED - {'ct'}):
        notes.append(f"Sách ghi ({u}) – không có trong bảng viết tắt; giữ nguyên như in.")
    if not e['pos'] and not any(s['pos'] for s in e['senses']):
        notes.append('Sách không ghi từ loại cho mục này.')
    _m = re.match(r'^(.*?)\s*\(([^()]+)\)$', hw)
    alt = [tidy(_m.group(2))] if _m else []
    entries.append({
        'id': e['id'],
        'letter': letter_of(hw),
        'headword': hw,
        'variants': [tidy(v) for v in e['variants']],
        'alt_forms': alt,
        'pos': [pos_obj(p) for p in e['pos']],
        'loan_source': ({'code': e['loan'], 'full': LOAN_FULL[e['loan']]} if e['loan'] else None),
        'senses': senses,
        'book_page': e['pages'][0] - 2,
        'pdf_page': e['pages'][0],
        'notes': notes,
        'source_line': tidy(e['raw']),
    })

SCOPE_TEXT = {
    'AC': ("Các mục bắt đầu bằng A, Ă, B, Ƀ, Č. Bảng chữ cái Êđê không có chữ 'C' riêng: "
           "âm 'ch' được viết là Č, nên phần 'A → C' kết thúc ở Č (trước chữ D)."),
    'DY': "Các mục từ chữ D đến hết chữ Y (D, Dh, Dj, Dl, Đ, E, Ê, G, H, I, J, K, L, M, N, Ñ, O, Ô, Ơ, P, R, S, T, U, Ư, W, Y…).",
}[TAG]
METHOD = {
    'AC': [
        'Bản chép tay có sẵn trong repo được đối chiếu lại từng dòng với ảnh scan (phóng 3,4×; dấu phụ khó phân biệt phóng 9–16×).',
        'Sửa các lỗi hệ thống: ŏ bị chép thành ơ̆ (hŏng, prŏng, ayŏng, jŏng, ƀŏng…), Alĕ bị chép thành Alê̆, m’ô̆ bị chép thành m’ŏ…',
        'Quét tự động ký tự lạ, dấu phụ dễ nhầm (so với ngữ liệu Kinh Thánh Êđê) và âm tiết tiếng Việt lạ (so với ngữ liệu Kinh Thánh tiếng Việt).',
        'Giữ nguyên chính tả của sách (kể cả ê̆, ô̆, ơ̆ khác với Kinh Thánh 2015); chỉ sửa lỗi chép và lỗi in rõ ràng, mọi chỗ sửa nằm trong sheet “Sửa lỗi OCR” và trường notes.',
    ],
    'DY': [
        'Bản chép tay có sẵn trong repo được sửa lỗi hệ thống ŏ bị chép thành ơ̆ (đã xác nhận bằng ảnh phóng lớn ở nhiều trang; mục “Ơ̆” ở trang PDF 121 có râu thật nên giữ nguyên).',
        'Đối chiếu từng chữ với ảnh scan (toàn trang) ở các trang PDF 27–31, 59, 75, 110, 140, 152; đối chiếu một phần (các dòng nghi vấn) ở trang 34, 82, 107, 121. Các trang còn lại (khoảng 125 trang) chỉ được kiểm tra bằng bộ quét tự động, chưa đối chiếu từng chữ.',
        'Quét tự động ký tự lạ, dấu phụ dễ nhầm (so với ngữ liệu Kinh Thánh Êđê) và âm tiết tiếng Việt lạ (so với ngữ liệu Kinh Thánh tiếng Việt); các nghi vấn được mở ảnh scan để xác nhận.',
        'Giữ nguyên chính tả của sách (kể cả ê̆, ô̆, ư̆ khác với Kinh Thánh 2015); chỉ sửa lỗi chép và lỗi in rõ ràng, mọi chỗ sửa nằm trong sheet “Sửa lỗi OCR” và trường notes.',
    ],
}
n_examples = sum(len(s['examples']) for e in entries for s in e['senses'])
letters = Counter(e['letter'] for e in entries)
meta = {
    'title': f'Từ điển Êđê – Việt (phần {SCOPE})',
    'source': f'data/PDF/TuDienEDe.pdf (bản scan), {PDF_PAGES}',
    'scope': SCOPE_TEXT,
    'generated': date.today().isoformat(),
    'entry_count': len(entries),
    'example_count': n_examples,
    'entries_by_letter': dict(letters),
    'method': METHOD[TAG],
    'caveat': ('Chưa được người bản ngữ rà soát. Các nhãn từ loại in lạ được giữ nguyên và ghi chú trong trường notes.'
               + (' Phần D–Y chưa được đối chiếu từng chữ với toàn bộ ảnh scan: có thể còn sót lỗi dấu phụ (ê̆/ĕ, ô̆/ŏ, ư̆/ŭ) và lỗi thanh điệu tiếng Việt.' if TAG == 'DY' else '')),
}
out = {'meta': meta, 'abbreviations': AB['abbreviations'], 'loan_sources': AB['loan_sources'],
       'alphabet': [{'upper': u, 'lower': l, 'vietnamese_sound': v} for u, l, v in ALPHA['letters']],
       'entries': entries}
json.dump(out, open(os.path.join(D, f'dictionary_{TAG}.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=2)

# ---------------- Excel
xl = os.path.join(D, f'dictionary_{TAG}.xlsx')
cnt = write_workbook(xl, entries, SCOPE, AB['abbreviations'], LOAN_FULL, ALPHA['letters'], POS_FULL, corrections)
json.dump(corrections, open(os.path.join(D, 'corrections.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)

# ---------------- báo cáo ngắn
print('Mục:', len(entries), '| ví dụ:', n_examples, '| theo chữ:', dict(letters))
print('Số chỗ sửa so với bản chép tay cũ:', len(corrections))
print('Từ loại:', dict(cnt))
print('Có ghi chú:', sum(1 for e in entries if e['notes']))
print('Đã ghi:', xl)
