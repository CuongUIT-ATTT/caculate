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

Ghi chú Render:

- Nếu cần tính năng chuyển PDF → CSV, đảm bảo `pdfplumber` nằm trong `requirements.txt` (đã thêm sẵn). Render sẽ cài và hoạt động bình thường.

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

- Thư mục `Uploads/` dùng để lưu file CSV tải lên hoặc CSV sinh từ PDF; dữ liệu là tạm thời (ephemeral) trên đa số hosting.
- Trên Linux, nếu không cài `openpyxl/reportlab`, các nút tải XLSX/PDF sẽ ẩn (CSV/JSON/MD vẫn hoạt động).

## Sử dụng

- Màn hình chính hiển thị danh sách file CSV trong `Transactions/`.
- Điền tuỳ chọn `person`, `paid_on` (ngày trả gần nhất), `start` (ngày bắt đầu tính).
- Nhấn "Tính toán" để xem tổng hợp và chi tiết.

### Chuyển PDF thành CSV và tính ngay

- Ở phần "Tạo CSV từ PDF", chọn file PDF chứa bảng giao dịch.
- Hệ thống sẽ ánh xạ cột về định dạng CSV chuẩn: `Date`, `Category name`, `Note`, `Amount` (tự nhận biết `Debit/Credit`, số âm trong ngoặc, dấu phân cách).
- Sau khi chuyển, trang kết quả sẽ mở ngay với dữ liệu vừa tạo (file CSV được lưu vào `Uploads/`).

### Xuất kết quả (Web)

- Tại trang kết quả, dùng các nút "Tải" để tải xuống các định dạng: CSV, JSON, MD.
- Nếu cài `openpyxl`, có thêm XLSX; nếu cài `reportlab`, có thêm PDF.
- Bộ lọc tìm kiếm, ngày bắt đầu/kết thúc, và danh mục sẽ áp dụng vào dữ liệu trước khi tải.

## Ghi chú

- Ứng dụng nạp trực tiếp hàm `compute_summary` từ file `Caculate-auto.py` nên không cần đổi tên file.
- Web đã hỗ trợ tải xuống CSV/JSON/MD (XLSX/PDF nếu có thư viện). Chế độ CLI vẫn có đủ tuỳ chọn xuất.
  "# caculate"
