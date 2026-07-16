# PES 2026 WEB V1.11.0 – RP Engine 2026

## Thay đổi chính

- Nâng phiên bản từ V1.10.12 lên V1.11.0.
- Tách và thay toàn bộ công thức RP trong `modules/rp_engine.py`.
- RP thắng cơ bản ngẫu nhiên 21–23.
- Biến thiên thắng ngẫu nhiên từ -1 đến +3.
- 10 trận đầu của người thắng cộng thêm 1–4; tổng trước thưởng chuỗi được giới hạn 22–29.
- Chủ phòng chỉ bị áp dụng hệ số 0,95 khi thắng; trong 10 trận đầu kết quả sau hệ số vẫn được giữ 22–29.
- Người thua trong 10 trận đầu bị trừ 14–19.
- Từ trận 11, người thua bị trừ nền 19–23 và thêm biến thiên -1, 0 hoặc +1.
- Chuỗi thua tăng dần từ trận thứ 4: trận 4 trừ 26–27, trận 5 trừ 27–28, trận 6 trừ 28–29, từ trận 7 trừ 29–30.
- Trận hòa: cùng cấp Rank nhận 0/0; khác cấp Rank thì người Rank thấp hơn +5, người Rank cao hơn +0.
- Thưởng chuỗi thắng chỉ đúng mốc: 3 trận +5, 5 trận +10, 10 trận +15, sau đó 15/20/25/... đều +15.
- Không còn thưởng RP theo chênh Rank trong trận thắng.

## File đã sửa

- `modules/rp_engine.py`: toàn bộ bộ máy RP mới.
- `app.py`: cập nhật version, đọc chuỗi thua từ lịch sử, giữ RP hòa +5/0 và áp dụng hệ số chủ phòng đúng điều kiện.

## Cài đặt

1. Sao lưu dự án và dữ liệu hiện tại.
2. Giải nén ZIP; các file nằm ngay ở thư mục gốc.
3. Chép đè toàn bộ file vào repository hiện tại.
4. Commit với tên gợi ý: `V1.11.0 - RP Engine 2026`.
5. Push lên nhánh thử nghiệm và deploy Vercel.
6. Test tối thiểu: thắng/thua trong 10 trận đầu, trận thứ 11, chuỗi thua 4–7, hòa lệch Rank, chủ phòng thắng và các mốc chuỗi 3/5/10/15.
