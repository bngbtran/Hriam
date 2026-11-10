"""Gộp A–Č và D–Y, chia theo nhóm 5 chữ cái (đúng thứ tự bảng chữ cái Êđê), và xuất bản tổng.

Đầu ra: data/dictionary/
    dictionary_full.xlsx, dictionary_full.json        # toàn bộ
    01_A-Ă-Â-B-Ƀ/ dictionary_01.json, dictionary_01.xlsx
    02_...                                            # mỗi folder 5 chữ cái

Chạy (sau khi đã chạy build_ac.py cho AC và DY):   python scripts/split_dict.py
Cần openpyxl nên KHÔNG dùng -I.
"""
import json
import os
import shutil
import sys
import unicodedata
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dict_xlsx import write_workbook  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'dictionary')
GROUP = 5


def nfc(s):
    return unicodedata.normalize('NFC', s)


def load(tag):
    p = os.path.join(DATA, 'dictionary', '_build', tag)
    d = json.load(open(os.path.join(p, f'dictionary_{tag}.json'), encoding='utf8'))
    d['corrections'] = json.load(open(os.path.join(p, 'corrections.json'), encoding='utf8'))
    return d


parts = [load('AC'), load('DY')]
base = parts[0]
alphabet = [[a['upper'], a['lower'], a['vietnamese_sound']] for a in base['alphabet']]
letters = [nfc(a[0]) for a in alphabet]            # 38 chữ, đúng thứ tự
entries = [e for d in parts for e in d['entries']]
corrections = [c for d in parts for c in d['corrections']]

# nhãn từ loại đầy đủ (cho sheet "Chữ viết tắt")
pos_full = dict(base['abbreviations'])
for d in parts:
    for e in d['entries']:
        for p in e['pos'] + [s['pos'] for s in e['senses'] if s['pos']]:
            pos_full.setdefault(p['code'], p['full'])
pos_full['hư từ'] = 'Hư từ (in nguyên chữ trong sách; không có trong bảng viết tắt)'
for c in ('ct', 'ht', 'bt', 'pt'):
    pos_full.setdefault(c, f'{c} – không có trong bảng viết tắt của sách; giữ nguyên như in')

by_letter = {L: [] for L in letters}
for e in entries:
    by_letter[nfc(e['letter'])].append(e)

# làm lại thư mục đầu ra (chỉ xoá những gì script này tạo)
if os.path.isdir(OUT):
    for name in os.listdir(OUT):
        p = os.path.join(OUT, name)
        if os.path.isdir(p) and name[:2].isdigit():
            shutil.rmtree(p)
        elif name == 'dictionary_full.json':
            os.remove(p)
os.makedirs(OUT, exist_ok=True)

groups = [letters[i:i + GROUP] for i in range(0, len(letters), GROUP)]
index = []
for gi, g in enumerate(groups, 1):
    ents = [e for L in g for e in by_letter[L]]
    name = f"{gi:02d}_{'-'.join(g)}"
    folder = os.path.join(OUT, name)
    os.makedirs(folder, exist_ok=True)
    pages = {e['pdf_page'] for e in ents}
    corr = [c for c in corrections if ents and min(pages) <= c['pdf_page'] <= max(pages)]
    meta = {
        'title': f'Từ điển Êđê – Việt, nhóm {gi}: {" ".join(g)}',
        'letters': g,
        'letters_without_entries': [L for L in g if not by_letter[L]],
        'entries_by_letter': {L: len(by_letter[L]) for L in g},
        'entry_count': len(ents),
        'example_count': sum(len(s['examples']) for e in ents for s in e['senses']),
        'pdf_pages': [min(pages), max(pages)] if ents else None,
        'generated': date.today().isoformat(),
    }
    json.dump({'meta': meta, 'entries': ents}, open(os.path.join(folder, f'dictionary_{gi:02d}.json'), 'w',
              encoding='utf8'), ensure_ascii=False, indent=2)
    write_workbook(os.path.join(folder, f'dictionary_{gi:02d}.xlsx'), ents, ' '.join(g), base['abbreviations'],
                   base['loan_sources'], alphabet, pos_full, corr)
    index.append((name, g, meta))

n_ex = sum(len(s['examples']) for e in entries for s in e['senses'])
full_meta = {
    'title': 'Từ điển Êđê – Việt (toàn bộ A → Y)',
    'source': 'data/PDF/TuDienEDe.pdf (bản scan), trang PDF 7–168 = trang sách 5–166',
    'entry_count': len(entries), 'example_count': n_ex,
    'entries_by_letter': {L: len(by_letter[L]) for L in letters},
    'groups': {n: g for n, g, _ in index},
    'generated': date.today().isoformat(),
    'caveat': ('Chưa được người bản ngữ rà soát. Phần A–Č đã đối chiếu từng dòng với ảnh scan; phần D–Y mới '
               'đối chiếu từng chữ ở một số trang (xem data/dictionary/README.md), còn lại chỉ quét tự động.'),
}
json.dump({'meta': full_meta, 'abbreviations': base['abbreviations'], 'loan_sources': base['loan_sources'],
           'alphabet': base['alphabet'], 'entries': entries},
          open(os.path.join(OUT, 'dictionary_full.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=2)
try:
    write_workbook(os.path.join(OUT, 'dictionary_full.xlsx'), entries, 'A–Y', base['abbreviations'],
                   base['loan_sources'], alphabet, pos_full, corrections)
except PermissionError:
    print('CẢNH BÁO: dictionary_full.xlsx đang mở trong Excel nên chưa ghi được; hãy đóng file rồi chạy lại.')

print('Tổng:', len(entries), 'mục |', n_ex, 'ví dụ')
for n, g, m in index:
    print(f"  {n:<24} {m['entry_count']:>5} mục  {m['example_count']:>5} ví dụ  trống: {m['letters_without_entries']}")
