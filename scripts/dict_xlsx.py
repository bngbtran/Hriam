"""Ghi sổ Excel cho từ điển Êđê – Việt (dùng chung cho từng phần và cho bản tổng)."""
import unicodedata
from collections import Counter

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HDR = PatternFill('solid', fgColor='1F4E78')
HF = Font(name='Times New Roman', bold=True, color='FFFFFF', size=11)
BF = Font(name='Times New Roman', size=11)
BOLD = Font(name='Times New Roman', size=11, bold=True)
thin = Side(style='thin', color='BFBFBF')
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
WRAP = Alignment(wrap_text=True, vertical='top')
BAND = PatternFill('solid', fgColor='F2F7FC')


def nfc(x):
    return unicodedata.normalize('NFC', x)


def sheet(ws, headers, rows, widths):
    ws.append(headers)
    for r in rows:
        ws.append(r)
    for c in range(1, len(headers) + 1):
        cell = ws.cell(1, c)
        cell.fill, cell.font, cell.border = HDR, HF, BORDER
        cell.alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
        ws.column_dimensions[get_column_letter(c)].width = widths[c - 1]
    for ri, row in enumerate(ws.iter_rows(min_row=2), 2):
        for cell in row:
            cell.font, cell.alignment, cell.border = BF, WRAP, BORDER
            if ri % 2 == 1:
                cell.fill = BAND
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    ws.row_dimensions[1].height = 32


def gloss_text(e):
    if len(e['senses']) == 1 and not e['senses'][0]['label']:
        return e['senses'][0]['gloss_vi']
    return '\n'.join(f"{s['label']} " + (f"({s['pos']['code']}) " if s['pos'] else '') + s['gloss_vi']
                     for s in e['senses'])


def example_text(e, which):
    lines = []
    for s in e['senses']:
        for x in s['examples']:
            lines.append((f"{s['label']} " if len(e['senses']) > 1 and s['label'] else '') + x[which])
    return '\n'.join(lines)


def write_workbook(path, entries, scope, abbreviations, loan_sources, alphabet_rows, pos_full,
                   corrections):
    """entries: danh sách mục (dạng JSON); alphabet_rows: [[Hoa, thường, âm VN], ...]."""
    wb = Workbook()
    HEAD = ['ID', 'Chữ cái', 'Từ Êđê', 'Biến thể', 'Từ loại (viết tắt)', 'Từ loại (đầy đủ)',
            'Nguồn gốc từ vay mượn', 'Số nghĩa', 'Nghĩa tiếng Việt', 'Ví dụ Êđê', 'Ví dụ dịch tiếng Việt',
            'Trang sách', 'Trang PDF', 'Ghi chú']
    WID = [9, 8, 24, 14, 12, 34, 20, 8, 42, 46, 46, 9, 9, 44]

    def main_rows(es):
        out = []
        for e in es:
            out.append([
                e['id'], e['letter'], e['headword'], ', '.join(e['variants']),
                ', '.join(p['code'] for p in e['pos']) or ', '.join(
                    sorted({s['pos']['code'] for s in e['senses'] if s['pos']})),
                '; '.join(p['full'] for p in e['pos']) or '; '.join(
                    sorted({s['pos']['full'] for s in e['senses'] if s['pos']})),
                (f"{e['loan_source']['code']} – {e['loan_source']['full']}" if e['loan_source'] else ''),
                len(e['senses']), gloss_text(e), example_text(e, 'ede'), example_text(e, 'vi'),
                e['book_page'], e['pdf_page'], ' '.join(e['notes'])])
        return out

    def fill_main(w, es):
        sheet(w, HEAD, main_rows(es), WID)
        for r in range(2, w.max_row + 1):
            w.cell(r, 3).font = BOLD

    ws = wb.active
    ws.title = f'Từ điển {scope}'[:31]
    fill_main(ws, entries)

    # thống kê + một sheet riêng cho từng chữ cái (theo thứ tự bảng chữ cái)
    order = [nfc(r[0]) for r in alphabet_rows]
    by_letter = {}
    for e in entries:
        by_letter.setdefault(nfc(e['letter']), []).append(e)
    stat = wb.create_sheet('Thống kê theo chữ')
    rows = []
    for L in order:
        es = by_letter.get(L, [])
        rows.append([L, len(es), sum(len(s['examples']) for e in es for s in e['senses']),
                     es[0]['book_page'] if es else '', es[-1]['book_page'] if es else ''])
    rows.append(['Tổng', len(entries), sum(r[2] for r in rows), '', ''])
    sheet(stat, ['Chữ cái', 'Số mục', 'Số ví dụ', 'Từ trang sách', 'Đến trang sách'], rows, [12, 10, 10, 14, 14])
    for L in order:
        if L in by_letter:
            wl = wb.create_sheet(f'Chữ {L}')
            fill_main(wl, by_letter[L])

    ws2 = wb.create_sheet('Từng nghĩa')
    rows = []
    for e in entries:
        for s in e['senses']:
            p = s['pos'] or (e['pos'][0] if len(e['pos']) == 1 else None)
            rows.append([e['id'], e['headword'], s['index'], s['label'],
                         p['code'] if p else (', '.join(x['code'] for x in e['pos'])),
                         p['full'] if p else '; '.join(x['full'] for x in e['pos']),
                         s['gloss_vi'], len(s['examples'])])
    sheet(ws2, ['ID', 'Từ Êđê', 'Nghĩa số', 'Nhãn trong sách', 'Từ loại', 'Từ loại (đầy đủ)',
                'Nghĩa tiếng Việt', 'Số ví dụ'], rows, [9, 26, 9, 12, 10, 40, 50, 9])

    ws3 = wb.create_sheet('Ví dụ (song ngữ)')
    rows, k = [], 0
    for e in entries:
        for s in e['senses']:
            for x in s['examples']:
                k += 1
                rows.append([k, e['id'], e['headword'], s['label'], x['ede'], x['vi']])
    sheet(ws3, ['STT', 'ID', 'Từ đầu mục', 'Nghĩa', 'Câu/cụm Êđê', 'Dịch tiếng Việt'], rows,
          [7, 9, 24, 8, 52, 52])

    ws4 = wb.create_sheet('Chữ viết tắt')
    cnt = Counter(p['code'] for e in entries for p in e['pos'])
    cnt.update(s['pos']['code'] for e in entries for s in e['senses'] if s['pos'])
    rows = [[c, pos_full.get(c, full), cnt.get(c, 0) or '', 'Từ loại/ký hiệu trong bảng viết tắt của sách']
            for c, full in abbreviations.items()]
    rows += [[c, v, '', 'Nguồn gốc từ vay mượn'] for c, v in loan_sources.items()]
    rows += [['phó từ', 'In nguyên chữ trong sách – quy về pht (Phụ từ)', '', 'Dạng in đầy đủ'],
             ['hư từ', pos_full['hư từ'], cnt.get('hư từ', 0), 'Dạng in đầy đủ']]
    for c in ('ct', 'ht', 'bt', 'pt'):
        rows.append([c, pos_full[c], cnt.get(c, 0), 'Không có trong bảng viết tắt'])
    sheet(ws4, ['Ký hiệu', 'Nghĩa đầy đủ', f'Số lần dùng ({scope})', 'Ghi chú'], rows, [12, 70, 16, 40])

    ws5 = wb.create_sheet('Bảng chữ cái Êđê')
    sheet(ws5, ['Chữ hoa', 'Chữ thường', 'Âm tiếng Việt tương ứng'], alphabet_rows, [12, 12, 50])
    for r in range(2, ws5.max_row + 1):
        for c in (1, 2):
            ws5.cell(r, c).font = Font(name='Times New Roman', size=13, bold=True)

    ws6 = wb.create_sheet('Sửa lỗi OCR')
    rows = [[c['pdf_page'], c['book_page'], c['headword'], c['old'], c['new']] for c in corrections]
    sheet(ws6, ['Trang PDF', 'Trang sách', 'Mục', 'Bản chép tay cũ', 'Đã sửa thành'], rows,
          [10, 10, 26, 40, 40])

    ws7 = wb.create_sheet('Ghi chú nguồn')
    rows = [[e['id'], e['headword'], ' '.join(e['notes']), e['source_line']] for e in entries if e['notes']
            and not all(n == 'Sách không ghi từ loại cho mục này.' for n in e['notes'])]
    sheet(ws7, ['ID', 'Mục', 'Ghi chú', 'Dòng gốc sau đối chiếu'], rows, [9, 24, 60, 80])

    wb.save(path)
    return cnt
