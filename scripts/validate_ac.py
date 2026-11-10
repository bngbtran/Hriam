"""Kiểm tra chính tả tự động cho bản chép A–Č (sau khi đã đối chiếu thủ công với ảnh scan).

Ba lớp kiểm tra, đều chỉ để KHOANH VÙNG chỗ cần soi lại, không tự sửa:
 1. Ký tự lạ: mọi ký tự Êđê ngoài bảng chữ cái của sách.
 2. Dấu phụ dễ nhầm (ŏ/ơ̆/ô̆, ĕ/ê̆/ê, ŭ/ư̆): từ chưa gặp trong ngữ liệu Kinh Thánh Êđê nhưng biến thể của nó thì có.
 3. Âm tiết tiếng Việt chưa gặp trong ngữ liệu Kinh Thánh tiếng Việt (bắt lỗi gõ sai dấu/chữ).

Chạy:  python -I scripts/validate_ac.py
"""
import collections
import json
import os
import re
import sys
import unicodedata

for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = os.environ.get('DICT_TAG', 'AC')
SHARED = os.path.join(ROOT, 'data', 'dictionary', 'reference')
D = os.path.join(ROOT, 'data', 'dictionary', '_build', TAG)


LET = r"(?:[^\W\d_]|[̀-ͯ])"          # chữ cái, kể cả dấu phụ rời (ê̆, ơ̆ ...)
TOK = re.compile(LET + "+(?:[-'’]" + LET + "+)*")


def nfc(s):
    return unicodedata.normalize('NFC', s)


def nfd(s):
    return unicodedata.normalize('NFD', s)


entries = json.load(open(os.path.join(D, '_parsed.json'), encoding='utf8'))

# ---- ngữ liệu tham chiếu
def corpus_tokens(path):
    c = collections.Counter()
    for ln in open(path, encoding='utf8'):
        t = nfc(json.loads(ln)['text']).lower()
        c.update(TOK.findall(t))
    return c

ede_c = corpus_tokens(os.path.join(ROOT, 'data', 'interim', 'ede.jsonl'))
vi_c = corpus_tokens(os.path.join(ROOT, 'data', 'interim', 'vi.jsonl'))
vi_syll = set()
for w in vi_c:
    vi_syll.update(TOK.findall(w))

# ---- 1. ký tự Êđê hợp lệ
alpha = json.load(open(os.path.join(SHARED, 'alphabet.json'), encoding='utf8'))['letters']
ALLOWED = set()
for up, lo, _ in alpha:
    ALLOWED.update(nfd(up)); ALLOWED.update(nfd(lo))
ALLOWED.update(" -'’,.()/?!…;:")
ALLOWED.update('ƀɓ')  # chấp nhận ƀ (U+0180) – ta chuẩn hóa về Ƀ/ƀ
ALLOWED.update(nfd('Ƀƀ'))


# từ tiếng Việt/tên riêng xuất hiện trong câu Êđê của sách (không thuộc bảng chữ cái Êđê)
VI_IN_EDE = {'việt', 'nam', 'hồ', 'dak', 'lak', 'yuăn'}


def ede_chars_bad(text):
    keep = ''.join(w for w in TOK.findall(nfc(text)) if w.lower() not in VI_IN_EDE)
    return sorted({ch for ch in nfd(keep) if ch not in ALLOWED and not ch.isdigit()})


SWAP = [('ơ̆', 'ŏ'), ('ŏ', 'ơ̆'), ('ô̆', 'ŏ'), ('ŏ', 'ô̆'), ('ê̆', 'ĕ'), ('ĕ', 'ê̆'), ('ê̆', 'ê'),
        ('ê', 'ê̆'), ('ĕ', 'ê'), ('ê', 'ĕ'), ('ư̆', 'ŭ'), ('ŭ', 'ư̆'), ('ô̆', 'ô'), ('ô', 'ô̆')]


def variants(w):
    out = set()
    for a, b in SWAP:
        a, b = nfc(a), nfc(b)
        if a in w:
            out.add(w.replace(a, b))
    return out


report = {'ede_char_issues': [], 'diacritic_conflicts': [], 'ede_rare': [], 'vi_unknown_syllables': []}
seen_conf = set()
ede_forms = collections.defaultdict(list)   # token -> [(id, vị trí)]

for e in entries:
    texts = [('headword', e['headword'])]
    for s in e['senses']:
        for ex in s['examples']:
            texts.append(('example', ex['ede']))
    for where, t in texts:
        bad = ede_chars_bad(t)
        if bad:
            report['ede_char_issues'].append({'id': e['id'], 'headword': e['headword'], 'where': where,
                                              'text': t, 'chars': bad})
        for tok in TOK.findall(nfc(t).lower()):
            ede_forms[tok].append((e['id'], e['headword'], where))

for tok, locs in sorted(ede_forms.items()):
    n = ede_c.get(tok, 0)
    vs = [(v, ede_c.get(v, 0)) for v in variants(tok) if ede_c.get(v, 0) > 0]
    if n == 0 and vs and tok not in seen_conf:
        seen_conf.add(tok)
        report['diacritic_conflicts'].append({'token': tok, 'bible_count': 0,
                                              'bible_variants': sorted(vs, key=lambda x: -x[1]),
                                              'where': [f'{a} {b} [{c}]' for a, b, c in locs[:3]]})
    elif n == 0 and any(ch in nfd(tok) for ch in '̛̆̌̂') :
        report['ede_rare'].append({'token': tok, 'where': [f'{a} {b} [{c}]' for a, b, c in locs[:2]]})

# ---- 3. tiếng Việt
vi_seen = collections.defaultdict(list)
for e in entries:
    for s in e['senses']:
        parts = [s['gloss']] + [ex['vi'] for ex in s['examples']]
        for p in parts:
            for syl in TOK.findall(nfc(p).lower()):
                if syl not in vi_syll:
                    vi_seen[syl].append(f"{e['id']} {e['headword']}")
for syl, locs in sorted(vi_seen.items()):
    report['vi_unknown_syllables'].append({'syllable': syl, 'where': locs[:3], 'count': len(locs)})

json.dump(report, open(os.path.join(D, 'validation_report.json'), 'w', encoding='utf8'),
          ensure_ascii=False, indent=1)
print('Ký tự Êđê lạ        :', len(report['ede_char_issues']))
print('Xung đột dấu phụ    :', len(report['diacritic_conflicts']))
print('Từ Êđê lạ (có dấu)  :', len(report['ede_rare']))
print('Âm tiết Việt lạ     :', len(report['vi_unknown_syllables']))
