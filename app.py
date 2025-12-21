import os
import io
import csv
import json
from decimal import Decimal
import importlib.util
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(__file__)
TRANSACTIONS_DIR = os.path.join(BASE_DIR, 'Transactions')
UPLOADS_DIR = os.path.join(BASE_DIR, 'Uploads')

# Dynamically load compute_summary from Caculate-auto.py (hyphenated filename)
_script_path = os.path.join(BASE_DIR, 'Caculate-auto.py')
spec = importlib.util.spec_from_file_location("calc_module", _script_path)
calc_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calc_module)
compute_summary = getattr(calc_module, 'compute_summary')

# Optional export libs
try:
    from openpyxl import Workbook
    HAS_OPENPYXL = True
except Exception:
    HAS_OPENPYXL = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except Exception:
    HAS_REPORTLAB = False

app = Flask(__name__)


def list_transaction_files():
    if not os.path.isdir(TRANSACTIONS_DIR):
        return []
    files = [f for f in os.listdir(TRANSACTIONS_DIR) if os.path.isfile(os.path.join(TRANSACTIONS_DIR, f))]
    files.sort()
    return files


@app.route('/', methods=['GET'])
def index():
    files = list_transaction_files()
    return render_template('index.html', files=files)


@app.route('/compute', methods=['POST'])
def compute():
    # Ensure uploads folder exists
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    file_name = (request.form.get('file') or '').strip()
    person = (request.form.get('person') or 'Quân').strip()
    paid_on = (request.form.get('paid_on') or None)
    start = (request.form.get('start') or None)

    uploaded_flag = False
    upload_file = request.files.get('upload')
    csv_path = None

    if upload_file and upload_file.filename:
        # Save uploaded CSV
        uploaded_flag = True
        fn = secure_filename(upload_file.filename)
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        saved_name = f"{ts}_{fn}"
        csv_path = os.path.join(UPLOADS_DIR, saved_name)
        upload_file.save(csv_path)
        file_name = saved_name
    else:
        if not file_name:
            return redirect(url_for('index'))
        csv_path = os.path.join(TRANSACTIONS_DIR, file_name)
        if not os.path.exists(csv_path):
            return redirect(url_for('index'))

    data = compute_summary(csv_path, person=person, paid_on=paid_on, start=start)

    # Convert to display-friendly values
    def fmt_int_str(s):
        v = Decimal(s).quantize(Decimal('1'))
        return f"{int(v):,}".replace(',', '.')

    totals = {
        'total_shared': fmt_int_str(data['totals']['total_shared']),
        'total_paid_by_person': fmt_int_str(data['totals']['total_paid_by_person']),
        'remaining': fmt_int_str(data['totals']['remaining']),
        'person': data['totals']['person'],
        'cutoff': data['totals']['cutoff'],
        'base_name': os.path.splitext(os.path.basename(file_name))[0],
    }

    available_exports = ['csv', 'json', 'md']
    if HAS_OPENPYXL:
        available_exports.append('xlsx')
    if HAS_REPORTLAB:
        available_exports.append('pdf')

    params = {
        'file': file_name,
        'uploaded': '1' if uploaded_flag else '0',
        'person': person,
        'paid_on': paid_on or '',
        'start': start or '',
    }

    return render_template(
        'result.html',
        totals=totals,
        shared_rows=data['shared_rows'],
        applied_payments=data['applied_payments'],
        unapplied_payments=data['unapplied_payments'],
        available_exports=available_exports,
        params=params,
    )


def _resolve_path(file_name: str, uploaded_flag: str) -> str:
    if uploaded_flag == '1':
        return os.path.join(UPLOADS_DIR, file_name)
    return os.path.join(TRANSACTIONS_DIR, file_name)


@app.route('/export/<fmt>', methods=['GET'])
def export(fmt: str):
    fmt = (fmt or '').lower()
    file_name = (request.args.get('file') or '').strip()
    uploaded_flag = request.args.get('uploaded') or '0'
    person = (request.args.get('person') or 'Quân').strip()
    paid_on = (request.args.get('paid_on') or None)
    start = (request.args.get('start') or None)

    if not file_name:
        return redirect(url_for('index'))

    csv_path = _resolve_path(file_name, uploaded_flag)
    if not os.path.exists(csv_path):
        return redirect(url_for('index'))

    data = compute_summary(csv_path, person=person, paid_on=paid_on, start=start)
    base_name = os.path.splitext(os.path.basename(file_name))[0]

    if fmt == 'csv':
        bio = io.StringIO()
        w = csv.writer(bio)
        w.writerow(['section', 'date', 'category', 'note', 'amount', 'share', 'reason'])
        for r in data['shared_rows']:
            w.writerow(['shared', r['date'], r['category'], r['note'], r['amount'], r['share'], r['reason']])
        w.writerow([])
        w.writerow(['applied_payment', 'date', 'category', 'note', 'amount'])
        for r in data['applied_payments']:
            w.writerow(['applied', r['date'], r['category'], r['note'], r['amount']])
        w.writerow([])
        w.writerow(['unapplied_payment', 'date', 'category', 'note', 'amount'])
        for r in data['unapplied_payments']:
            w.writerow(['unapplied', r['date'], r['category'], r['note'], r['amount']])
        w.writerow([])
        w.writerow(['total_shared', data['totals']['total_shared']])
        w.writerow(['total_paid_by_person', data['totals']['total_paid_by_person']])
        w.writerow(['remaining', data['totals']['remaining']])
        bytes_io = io.BytesIO(bio.getvalue().encode('utf-8'))
        return send_file(bytes_io, as_attachment=True, download_name=f"{base_name}.{person}.summary.csv", mimetype='text/csv')

    if fmt == 'json':
        content = json.dumps(data, ensure_ascii=False, indent=2)
        bytes_io = io.BytesIO(content.encode('utf-8'))
        return send_file(bytes_io, as_attachment=True, download_name=f"{base_name}.{person}.summary.json", mimetype='application/json')

    if fmt == 'md':
        lines = []
        lines.append(f"# Summary for {person} - {base_name}\n\n")
        lines.append('## Totals\n')
        lines.append(f"- Total shared: {data['totals']['total_shared']}\n")
        lines.append(f"- Total paid by {person}: {data['totals']['total_paid_by_person']}\n")
        lines.append(f"- Remaining: {data['totals']['remaining']}\n\n")
        lines.append('## Shared rows\n\n')
        lines.append('| date | category | note | amount | share | reason |\n')
        lines.append('|---|---|---|---:|---:|---|\n')
        for r in data['shared_rows']:
            note = (r['note'] or '').replace('|', '\\|')
            lines.append(f"| {r['date']} | {r['category']} | {note} | {r['amount']} | {r['share']} | {r['reason']} |\n")
        lines.append('\n## Applied payments\n\n')
        lines.append('| date | category | note | amount |\n')
        lines.append('|---|---|---|---:|\n')
        for r in data['applied_payments']:
            note = (r['note'] or '').replace('|', '\\|')
            lines.append(f"| {r['date']} | {r['category']} | {note} | {r['amount']} |\n")
        lines.append('\n## Unapplied payments\n\n')
        lines.append('| date | category | note | amount |\n')
        lines.append('|---|---|---|---:|\n')
        for r in data['unapplied_payments']:
            note = (r['note'] or '').replace('|', '\\|')
            lines.append(f"| {r['date']} | {r['category']} | {note} | {r['amount']} |\n")
        bytes_io = io.BytesIO(''.join(lines).encode('utf-8'))
        return send_file(bytes_io, as_attachment=True, download_name=f"{base_name}.{person}.summary.md", mimetype='text/markdown')

    if fmt == 'xlsx' and HAS_OPENPYXL:
        wb = Workbook()
        ws = wb.active
        ws.title = 'shared'
        ws.append(['date', 'category', 'note', 'amount', 'share', 'reason'])
        for r in data['shared_rows']:
            ws.append([r['date'], r['category'], r['note'], r['amount'], r['share'], r['reason']])
        ws2 = wb.create_sheet('applied_payments')
        ws2.append(['date', 'category', 'note', 'amount'])
        for r in data['applied_payments']:
            ws2.append([r['date'], r['category'], r['note'], r['amount']])
        ws3 = wb.create_sheet('unapplied_payments')
        ws3.append(['date', 'category', 'note', 'amount'])
        for r in data['unapplied_payments']:
            ws3.append([r['date'], r['category'], r['note'], r['amount']])
        ws4 = wb.create_sheet('totals')
        ws4.append(['total_shared', data['totals']['total_shared']])
        ws4.append(['total_paid_by_person', data['totals']['total_paid_by_person']])
        ws4.append(['remaining', data['totals']['remaining']])
        bytes_io = io.BytesIO()
        wb.save(bytes_io)
        bytes_io.seek(0)
        return send_file(bytes_io, as_attachment=True, download_name=f"{base_name}.{person}.summary.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    if fmt == 'pdf' and HAS_REPORTLAB:
        bytes_io = io.BytesIO()
        c = canvas.Canvas(bytes_io, pagesize=A4)
        w, h = A4
        y = h - 40
        c.setFont('Helvetica-Bold', 12)
        c.drawString(40, y, f"Summary for {person} - {base_name}")
        y -= 24
        c.setFont('Helvetica', 10)
        c.drawString(40, y, f"Totals: shared={data['totals']['total_shared']} paid={data['totals']['total_paid_by_person']} remaining={data['totals']['remaining']}")
        y -= 24
        c.drawString(40, y, 'Shared rows:')
        y -= 18
        for r in data['shared_rows']:
            line = f"{r['date']} | {r['category']} | {r['note'] or ''} | amt:{r['amount']} | share:{r['share']}"
            c.drawString(40, y, line[:120])
            y -= 14
            if y < 80:
                c.showPage()
                y = h - 40
        c.save()
        bytes_io.seek(0)
        return send_file(bytes_io, as_attachment=True, download_name=f"{base_name}.{person}.summary.pdf", mimetype='application/pdf')

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
