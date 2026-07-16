# PES 2026 WEB V1.11.1 – Điều chỉnh RP thua

## Thay đổi chính

- Nâng phiên bản từ V1.11.0 lên V1.11.1.
- Giữ nguyên toàn bộ công thức RP thắng, hòa, hệ số chủ phòng và thưởng chuỗi thắng.
- Người thua trong 10 trận đầu tiếp tục bị trừ ngẫu nhiên 14–19 RP.
- Người thua từ trận thứ 11 trở đi bị trừ trực tiếp ngẫu nhiên 19–23 RP.
- Bỏ biến thiên phụ `-1/0/+1` ở thua thường để giảm hiện tượng nhiều kết quả cùng hội tụ về -20 RP.
- Chuỗi thua áp dụng khoảng mới:
  - Trận thua liên tiếp thứ 4: trừ 22–24 RP.
  - Trận thứ 5: trừ 23–26 RP.
  - Trận thứ 6: trừ 25–27 RP.
  - Từ trận thứ 7 trở đi: trừ 25–30 RP.

## File đã sửa

- `modules/rp_engine.py`: thay công thức RP thua thường và các khoảng chuỗi thua.
- `app.py`: cập nhật phiên bản ứng dụng thành V1.11.1.
- `test_rp_engine.py`: cập nhật kiểm thử các khoảng 14–19, 19–23, 22–24, 23–26, 25–27 và 25–30.

## Hướng dẫn cài đặt

1. Tạo branch thử nghiệm, ví dụ `test-v1.11.1-loss-rp`.
2. Sao lưu repository hiện tại.
3. Giải nén ZIP và chép toàn bộ file bên trong vào thư mục gốc repository.
4. Chọn ghi đè các file trùng tên.
5. Chạy `python test_rp_engine.py`.
6. Commit gợi ý: `V1.11.1 - Dieu chinh RP thua`.
7. Push branch và deploy Vercel để kiểm tra trước khi merge vào `main`.

Không cần chạy SQL và không cần thay đổi cấu trúc Supabase.
