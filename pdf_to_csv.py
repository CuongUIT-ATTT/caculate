import csv
import re
from typing import Optional, List, Dict
from datetime import datetime


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _parse_amount(cell: str) -> Optional[float]:
    if cell is None:
        return None
    s = str(cell).strip()
    if s == "":
        return None
    neg = False
    # Parentheses indicate negative
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    # Normalize thousand/decimal separators
    s = s.replace("\xa0", " ").replace(" ", "")
    # Remove currency symbols
    s = re.sub(r"[^0-9.,-]", "", s)
    # If both . and , exist, decide by last separator as decimal
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        # If only comma exists and seems decimal
        if "," in s and s.count(",") == 1 and len(s.split(",")[-1]) in (2,3):
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    try:
        val = float(s)
        return -val if neg else val
    except Exception:
        return None


def extract_tables_to_csv(pdf_path: str, out_csv_path: str, table_settings: Optional[dict] = None) -> None:
    """
    Raw extraction: dump all tables across pages to CSV without schema mapping.
    """
    try:
        import pdfplumber
    except Exception as e:
        raise RuntimeError("pdfplumber is required for PDF to CSV conversion.") from e

    rows: List[List[str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            try:
                tables = (page.extract_tables() or []) if not table_settings else [page.extract_table(table_settings)]
            except Exception:
                tables = []
            for table in tables:
                if not table:
                    continue
                for row in table:
                    rows.append([str(cell).strip() if cell is not None else '' for cell in row])
                rows.append([])
            rows.append([])

    with open(out_csv_path, 'w', encoding='utf-8', newline='') as fo:
        w = csv.writer(fo)
        for r in rows:
            w.writerow(r)


def extract_tables_to_structured_csv(pdf_path: str, out_csv_path: str) -> None:
    """
    Extract tables and map columns to the working CSV schema:
    headers: Date, Category name, Note, Amount

    Heuristics:
    - Detect header row by first non-empty row; normalize header names.
    - Map synonyms for date/note/category/amount; or infer amount via debit/credit.
    - Parse amounts, parentheses negative; compute Amount = Credit - Debit if both exist.
    - If category missing, leave empty; note aggregates text columns.
    - Skip repeated header rows across pages.
    """
    try:
        import pdfplumber
    except Exception as e:
        raise RuntimeError("pdfplumber is required for PDF to CSV conversion.") from e

    synonym_map = {
        'date': {'date', 'ngày', 'transaction date', 'posting date', 'tanggal'},
        'note': {'note', 'description', 'ghi chú', 'memo', 'content', 'details'},
        'category': {'category', 'danh mục', 'loại', 'type'},
        'amount': {'amount', 'số tiền', 'giá trị', 'value', 'số tiền (vnd)'},
        'debit': {'debit', 'chi', 'nợ', 'dr', 'withdrawal'},
        'credit': {'credit', 'thu', 'có', 'cr', 'deposit'},
    }

    def classify_headers(headers: List[str]) -> Dict[str, int]:
        hnorm = [_norm(h) for h in headers]
        idxs: Dict[str, int] = {}
        for i, h in enumerate(hnorm):
            for key, syns in synonym_map.items():
                if h in syns and key not in idxs:
                    idxs[key] = i
        # Sometimes numbers columns are named like "Số tiền(+/-)"; try loose matching
        for i, h in enumerate(hnorm):
            if 'amount' in h or 'số tiền' in h:
                idxs.setdefault('amount', i)
            if 'debit' in h or 'nợ' in h or 'chi' in h:
                idxs.setdefault('debit', i)
            if 'credit' in h or 'có' in h or 'thu' in h:
                idxs.setdefault('credit', i)
            if 'date' in h or 'ngày' in h:
                idxs.setdefault('date', i)
            if 'category' in h or 'danh mục' in h or 'type' in h or 'loại' in h:
                idxs.setdefault('category', i)
            if 'description' in h or 'ghi chú' in h or 'note' in h or 'memo' in h:
                idxs.setdefault('note', i)
        return idxs

    def parse_date(s: str) -> str:
        if not s:
            return ''
        s = s.strip()
        fmts = ['%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y', '%d.%m.%Y']
        for fmt in fmts:
            try:
                d = datetime.strptime(s, fmt)
                return d.strftime('%Y-%m-%d')
            except Exception:
                continue
        # try iso split
        try:
            d = datetime.fromisoformat(s.split(' ')[0])
            return d.strftime('%Y-%m-%d')
        except Exception:
            return s

    records: List[Dict[str, str]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            try:
                tables = page.extract_tables() or []
            except Exception:
                tables = []
            for table in tables:
                if not table:
                    continue
                # Identify header row: first row with >=2 non-empty cells
                header_row = None
                start_idx = 0
                for i, row in enumerate(table):
                    non_empty = [c for c in row if (c or '').strip()]
                    if len(non_empty) >= 2:
                        header_row = [str(c).strip() if c is not None else '' for c in row]
                        start_idx = i + 1
                        break
                if not header_row:
                    # no header recognized, treat each row generically
                    for row in table:
                        cells = [str(c).strip() if c is not None else '' for c in row]
                        # Try inferring date from first cell, amount from last numeric cell
                        date = parse_date(cells[0]) if cells else ''
                        # Find numeric cells
                        amt = None
                        for cell in reversed(cells):
                            val = _parse_amount(cell)
                            if val is not None:
                                amt = val
                                break
                        note = ' '.join([c for c in cells[1:-1] if c])
                        rec = {
                            'Date': date,
                            'Category name': '',
                            'Note': note,
                            'Amount': str(amt if amt is not None else 0),
                        }
                        records.append(rec)
                    continue

                idxs = classify_headers(header_row)
                for row in table[start_idx:]:
                    cells = [str(c).strip() if c is not None else '' for c in row]
                    if not any(cells):
                        continue
                    date = parse_date(cells[idxs['date']]) if 'date' in idxs else parse_date(cells[0])
                    category = cells[idxs['category']] if 'category' in idxs else ''
                    note = cells[idxs['note']] if 'note' in idxs else ''

                    amount_val = None
                    if 'amount' in idxs:
                        amount_val = _parse_amount(cells[idxs['amount']])
                    elif 'debit' in idxs or 'credit' in idxs:
                        dv = _parse_amount(cells[idxs['debit']]) if 'debit' in idxs else 0
                        cv = _parse_amount(cells[idxs['credit']]) if 'credit' in idxs else 0
                        try:
                            amount_val = (cv or 0) - (dv or 0)
                        except Exception:
                            amount_val = None
                    else:
                        # last numeric cell as amount
                        for cell in reversed(cells):
                            val = _parse_amount(cell)
                            if val is not None:
                                amount_val = val
                                break

                    # Aggregate other text into note if note empty
                    if not note:
                        text_cols = []
                        for i, c in enumerate(cells):
                            if i in (idxs.get('date'), idxs.get('category'), idxs.get('amount'), idxs.get('debit'), idxs.get('credit')):
                                continue
                            if c and _parse_amount(c) is None:
                                text_cols.append(c)
                        note = ' '.join(text_cols)

                    rec = {
                        'Date': date,
                        'Category name': category,
                        'Note': note,
                        'Amount': str(amount_val if amount_val is not None else 0),
                    }
                    records.append(rec)

    # Write structured CSV
    with open(out_csv_path, 'w', encoding='utf-8', newline='') as fo:
        w = csv.DictWriter(fo, fieldnames=['Date', 'Category name', 'Note', 'Amount'])
        w.writeheader()
        for r in records:
            w.writerow(r)
