# Triển khai web cho Thu chi

Ứng dụng web nhỏ bằng Flask để chạy thuật toán tính nợ dựa trên các file CSV trong thư mục `Transactions`.

## Chuẩn bị môi trường

- Yêu cầu: Python 3.10+
- Thư mục chứa: `Caculate-auto.py`, `Transactions/` và các file CSV.

## Cài đặt phụ thuộc

```powershell
# Tại thư mục dự án
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Chạy ứng dụng

```powershell
# Chạy Flask app
python app.py
# Truy cập trình duyệt: http://localhost:5000
```

## Deploy lên Internet

### Render (đơn giản, không cần Docker)

- Push toàn bộ thư mục này lên Git (GitHub/GitLab).
- Tạo dịch vụ Web mới trên Render, chọn repo, Render sẽ đọc [render.yaml](render.yaml).
- Render tự cài requirements và chạy `gunicorn app:app`.

### Docker (VPS, Fly.io, Railway, …)

```bash
# Build
docker build -t thu-chi-web:latest .
# Run
docker run -p 8000:8000 --name thu-chi --rm thu-chi-web:latest
# Mở http://localhost:8000
```

### Heroku (nếu dùng)

- App dùng [Procfile](Procfile) và [runtime.txt](runtime.txt).

```bash
heroku create
heroku buildpacks:set heroku/python
git push heroku main
```

Ghi chú:

- Thư mục `Uploads/` dùng để lưu file CSV tải lên, là tạm thời trên đa số hosting (ephemeral).
- Trên Linux, nếu không cài `openpyxl/reportlab`, các nút tải XLSX/PDF sẽ ẩn (CSV/JSON/MD vẫn hoạt động).

## Sử dụng

- Màn hình chính hiển thị danh sách file CSV trong `Transactions/`.
- Điền tuỳ chọn `person`, `paid_on` (ngày trả gần nhất), `start` (ngày bắt đầu tính).
- Nhấn "Tính toán" để xem tổng hợp và chi tiết.

## Ghi chú

- Ứng dụng nạp trực tiếp hàm `compute_summary` từ file `Caculate-auto.py` nên không cần đổi tên file.
- Các tuỳ chọn xuất (CSV/JSON/MD/XLSX/PDF) hiện chỉ có trong chế độ CLI; có thể mở rộng lên web sau.
  "# caculate"
