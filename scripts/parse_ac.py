"""Phân tích bản chép đã đối chiếu (data/verified/AC/p*.txt) thành JSON có cấu trúc.

Chạy:  python -I scripts/parse_ac.py   (DICT_TAG=DY cho phần D–Y)
Đầu ra: data/dictionary/_build/<TAG>/_parsed.json
"""
import glob
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = os.environ.get('DICT_TAG', 'AC')          # AC = A–Č, DY = D–Y
SRC = os.path.join(ROOT, 'data', 'verified', TAG)
SHARED = os.path.join(ROOT, 'data', 'dictionary', 'reference')   # bảng viết tắt + bảng chữ cái dùng chung
OUT = os.path.join(ROOT, 'data', 'dictionary', '_build', TAG)
os.makedirs(OUT, exist_ok=True)

ABBR = json.load(open(os.path.join(SHARED, 'abbreviations.json'), encoding='utf8'))
POS_CODES = ABBR['abbreviations']
LOANS = ABBR['loan_sources']
SPELLED = ABBR['spelled_out_in_text']
EXTRA_POS = {'ct', 'ht', 'bt', 'pt'}   # in trong sách nhưng không có trong bảng viết tắt
ALIAS_POS = {'trtừ': 'trt'}            # 'trtừ' = trợ từ, viết dính liền
LOAN_MARKERS = set(LOANS)              # Anh, Pr, Yu, La, Trg
LOAN_ALIAS = {'yu': 'Yu', 'anh': 'Anh', 'pr': 'Pr', 'la': 'La', 'trg': 'Trg',
              'yuăn': 'Yu', 'prăng': 'Pr'}   # sách có lúc in nguyên chữ


for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding='utf-8')


def nfc(s):
    return unicodedata.normalize('NFC', s)


def pos_of(token):
    """'dt' / 'phó từ' ... -> mã chuẩn hoặc None."""
    t = token.strip().lower()
    t = ALIAS_POS.get(t, t)
    if t in POS_CODES or t in EXTRA_POS:
        return t
    if t in SPELLED:
        return SPELLED[t] or t
    return None


GROUP = re.compile(r'\(([^()]*)\)')


def split_head(head):
    """Tách 'Ƀruêh (dt) (Anh)' -> (từ, [pos], loan, [biến thể trong ngoặc])."""
    pos, loan, alts = [], None, []
    # bóc các nhóm ngoặc ở cuối
    while True:
        m = re.search(r'\s*\(([^()]*)\)\s*$', head)
        if not m:
            break
        inner = m.group(1).strip()
        p = pos_of(inner)
        if p:
            pos.insert(0, p)
        elif inner.lower() in LOAN_ALIAS:
            loan = LOAN_ALIAS[inner.lower()]
        else:
            break
        head = head[:m.start()]
    return head.strip(), pos, loan


ROMAN = re.compile(r'(?:(?<=^)|(?<=\s))(III|II|I|IV)\.\s*')
NUM = re.compile(r'(?:(?<=^)|(?<=[\s.;:)]))(\d{1,2})\.\s*(?=\S)')


def split_senses(body):
    """body -> [(roman, number, text)]"""
    # tách khối La Mã
    marks = [(m.start(), m.end(), m.group(1)) for m in ROMAN.finditer(body)]
    blocks = []
    if marks and marks[0][0] <= 1:
        for i, (s, e, r) in enumerate(marks):
            end = marks[i + 1][0] if i + 1 < len(marks) else len(body)
            blocks.append((r, body[e:end].strip()))
    else:
        blocks.append((None, body.strip()))
    out = []
    for roman, text in blocks:
        # tách số thứ tự 1. 2. 3. theo đúng thứ tự tăng dần
        cands = [(m.start(), m.end(), int(m.group(1))) for m in NUM.finditer(text)]
        picked, expect = [], None
        for s, e, n in cands:
            if expect is None:
                if n in (1, 2) and s <= 12:   # khối bắt đầu bằng số (khối II của 'Ƀơ̆ng' bắt đầu từ 2)
                    picked.append((s, e, n)); expect = n + 1
            elif n == expect:
                picked.append((s, e, n)); expect = n + 1
        if not picked:
            out.append((roman, None, text))
            continue
        pre = text[:picked[0][0]].strip()
        if pre:
            out.append((roman, None, pre))
        for i, (s, e, n) in enumerate(picked):
            end = picked[i + 1][0] if i + 1 < len(picked) else len(text)
            out.append((roman, n, text[e:end].strip()))
    return out


def split_gloss_examples(text):
    """'Gloss. Ede: Vi; Ede: Vi.' -> (gloss, [{ede, vi}])"""
    text = text.strip()
    # che dấu ':' nằm trong ngoặc đơn (vd. "(từ dùng đếm số người: Đứa, người)")
    text = re.sub(r'\([^()]*\)', lambda m: m.group(0).replace(':', ''), text)
    chunks = [c.strip() for c in re.split(r';\s+|\.\s+(?=[^\s])', text) if c.strip()]
    # tách lại: chia theo '; ' và '. '
    gloss_parts, examples = [], []
    for c in chunks:
        if ':' in c:
            left, right = c.split(':', 1)
            if left.strip() and right.strip():
                examples.append({'ede': left.strip().rstrip('.'), 'vi': right.strip().rstrip('.').strip()})
                continue
        if examples and not gloss_parts:
            gloss_parts.append(c)
        elif examples:
            # đoạn không có ':' sau ví dụ -> nối vào bản dịch trước (câu dịch bị tách bởi dấu chấm)
            examples[-1]['vi'] += '. ' + c.rstrip('.')
        else:
            gloss_parts.append(c)
    gloss = '. '.join(p.rstrip('.').strip() for p in gloss_parts).strip()
    gloss = gloss.replace('', ':')
    for e in examples:
        e['ede'] = e['ede'].replace('', ':')
        e['vi'] = e['vi'].replace('', ':')
    return gloss, examples


LEAD_POS = re.compile(r'^\(([^()]*)\)\s*\.?\s*')


def parse_line(head, body, page):
    word, pos, loan = split_head(head)
    entry = {'headword': nfc(word), 'pos': pos, 'loan': loan, 'senses': [], 'page': page}
    body = body.strip()
    senses = []
    for roman, num, text in split_senses(body):
        spos = None
        m = LEAD_POS.match(text)
        while m:
            inner = m.group(1).strip()
            p = pos_of(inner)
            if p:
                spos = p
                text = text[m.end():]
                m = LEAD_POS.match(text)
            elif inner.lower().startswith('đại từ'):
                spos = 'đt'
                text = text[m.end():]
                m = LEAD_POS.match(text)
            else:
                break
        gloss, exs = split_gloss_examples(text)
        senses.append({'roman': roman, 'number': num, 'pos': spos, 'gloss': nfc(gloss),
                       'examples': [{'ede': nfc(e['ede']), 'vi': nfc(e['vi'])} for e in exs]})
    # mục chỉ có "I.(đgt)" rồi mới tới "1. ... 2. ...": chuyển từ loại xuống các nghĩa cùng khối
    clean = []
    for i, sn in enumerate(senses):
        if sn['pos'] and not sn['gloss'] and not sn['examples']:
            for nx in senses[i + 1:]:
                if nx['roman'] != sn['roman']:
                    break
                if not nx['pos']:
                    nx['pos'] = sn['pos']
            continue
        clean.append(sn)
    entry['senses'] = clean
    entry['variants'] = [v.strip() for v in entry['headword'].split(',') if v.strip()] if ',' in entry['headword'] else []
    return entry


def main():
    lines = []  # (page, text)
    for f in sorted(glob.glob(os.path.join(SRC, 'p*.txt'))):
        page = int(re.search(r'p(\d+)\.txt', f).group(1))
        for ln in open(f, encoding='utf8').read().splitlines():
            if ln.strip():
                lines.append((page, nfc(ln.rstrip())))
    # ghép dòng tiếp nối ('| ...')
    entries_raw = []
    for page, ln in lines:
        if ln.startswith('|'):
            entries_raw[-1][2] = (entries_raw[-1][2] + ' ' + ln[1:].strip()).strip()
            entries_raw[-1][3].append(page)
            continue
        if '|' not in ln:
            print('DÒNG KHÔNG CÓ |:', page, ln, file=sys.stderr)
            continue
        head, body = ln.split('|', 1)
        entries_raw.append([page, head.strip(), body.strip(), [page]])
    entries = []
    for page, head, body, pages in entries_raw:
        e = parse_line(head, body, page)
        e['pages'] = sorted(set(pages))
        e['raw'] = f'{head} | {body}'
        entries.append(e)
    # đánh số, chữ cái
    for i, e in enumerate(entries, 1):
        e['id'] = f'{TAG}{i:04d}'
        e['letter'] = nfc(e['headword'][0].upper())
    json.dump(entries, open(os.path.join(OUT, '_parsed.json'), 'w', encoding='utf8'),
              ensure_ascii=False, indent=1)
    print(len(entries), 'mục')


if __name__ == '__main__':
    main()
