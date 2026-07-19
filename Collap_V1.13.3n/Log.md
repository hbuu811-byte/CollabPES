# Collap_V1.13.3n — Công tắc BXH công khai

- **Ngày giờ:** 19/07/2026 18:47 — múi giờ Asia/Bangkok.
- **Bản nền chức năng:** `Collap_V1.13.3m`.
- **Loại gói:** trình vá tự động, để không chép đè code của các nhánh tối ưu Request đang thử nghiệm.
- **SQL Supabase:** không cần.

## 1. Công tắc mới trong Admin

Thêm khóa hệ thống:

```text
public_ranking_enabled
```

Nhãn hiển thị:

```text
BXH công khai (không cần đăng nhập)
```

Công tắc nằm tại:

```text
Admin → Bật/tắt tính năng hệ thống
```

Công tắc được quản lý bởi quyền Admin hiện có `system_features_manage`.

## 2. Luồng hoạt động

| Trạng thái | Khách chưa đăng nhập | Người đã đăng nhập | Admin |
|---|---|---|---|
| Bật | Xem được BXH | Xem được BXH | Xem được BXH |
| Tắt | Bị chuyển đến trang Đăng nhập | Xem được BXH | Xem được BXH |

Khi tắt, backend chặn cả ba đường dẫn:

```text
/
/bxh
/ranking
```

Vì vậy khách không thể sửa URL trực tiếp để mở BXH.

## 3. File được sửa

| File | Vị trí ước lượng | Nội dung |
|---|---:|---|
| `app.py` | khu vực `APP_VERSION`, `SYSTEM_FEATURE_DEFAULTS`, route `/`, route `ranking()` | Tăng phiên bản; thêm mặc định công tắc; điều hướng trang chủ; khóa BXH khi chưa đăng nhập |
| `templates/admin.html` | nhóm `Bật/tắt tính năng hệ thống` | Thêm công tắc `BXH công khai (không cần đăng nhập)` |

## 4. Cách áp dụng

1. Chép `apply_Collap_V1.13.3n.py` vào thư mục gốc dự án, cùng cấp `app.py`.
2. Chạy:

```bash
python apply_Collap_V1.13.3n.py
```

3. Commit hai file được trình vá báo:

```text
app.py
templates/admin.html
```

4. Không commit thư mục backup:

```text
.collap_v1_13_3n_backup
```

## 5. Kiểm tra đã thực hiện

- Chạy thử trình vá trên cấu trúc PES Arena có route `/`, `/login`, `/ranking`, `/bxh`: đạt.
- `python -m py_compile app.py`: đạt.
- Parse `templates/admin.html` bằng Jinja2: đạt.
- Chạy trình vá lần hai không tạo công tắc trùng: đạt.
- Không sửa RP, phòng đấu, lịch sử trận, polling, CSS, JavaScript hoặc database.
