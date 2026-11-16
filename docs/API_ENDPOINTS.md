# Danh sách API Endpoint – Hệ thống đặt vé máy bay

Tài liệu này liệt kê toàn bộ endpoint dùng cho báo cáo. Nghiệp vụ chi tiết của từng endpoint xem trong [USE_CASES.md](USE_CASES.md); kiến trúc tổng thể xem trong [PLAN.md](PLAN.md).

## 1. Quy ước chung

| Hạng mục | Quy ước |
|---|---|
| Điểm vào | Mọi request từ FE đều đi qua **API Gateway** (`:3000`), dạng `https://<ngrok-domain>/api/...` |
| Endpoint nội bộ | Prefix `/internal/...`: chỉ gọi giữa các service trong mạng Docker, Gateway **không** public |
| Xác thực | Header `Authorization: Bearer <accessToken>`. Gateway verify JWT, rồi chuyển tiếp `x-user-id` và `x-user-role` cho service phía sau |
| Phân quyền | Mọi đường dẫn `/api/admin/**` yêu cầu `role=ADMIN`, kiểm tra ngay tại Gateway |
| Định dạng | JSON; thời gian theo ISO-8601 (UTC); tiền là số nguyên VND |
| Phân trang | `?page=1&limit=20`. Response trả về `{ data: [...], meta: { page, limit, total } }` |
| Truy vết | Header `x-correlation-id`, do Gateway sinh nếu client không gửi; được ghi vào log của mọi service |
| Rate limit | Mặc định 100 request/phút/IP. Riêng `/api/auth/login` giới hạn 5 request/phút, `/api/bookings/lookup` giới hạn 10 request/phút |

**Format lỗi chung** (dùng chung một `HttpExceptionFilter` trong `libs/common`):

```json
{
  "statusCode": 409,
  "errorCode": "SEAT_UNAVAILABLE",
  "message": "Ghế 12A đã có người giữ",
  "details": { "seats": ["12A"] },
  "timestamp": "2026-12-01T08:00:00Z",
  "path": "/api/bookings/abc/seats",
  "correlationId": "c0a8..."
}
```

**Ký hiệu cột Quyền:**

| Ký hiệu | Ý nghĩa |
|---|---|
| Public | Không cần đăng nhập |
| User | Đã đăng nhập, mọi role |
| Owner | Đã đăng nhập và là chủ của tài nguyên |
| Admin | Đã đăng nhập với role ADMIN |
| Lookup | Có `lookupToken` cấp từ UC32 |
| VNPay | Lời gọi từ VNPay, xác thực bằng chữ ký HMAC |
| Internal | Chỉ gọi giữa các service |

## 2. Bảng định tuyến của API Gateway

| Prefix | Service đích | Cổng |
|---|---|---|
| `/api/auth/**`, `/api/users/**`, `/api/admin/users/**` | auth-service | 3001 |
| `/api/airports/**`, `/api/flights/**`, `/api/ancillaries/**`, `/api/admin/{airports,airlines,aircrafts,flights,fare-families,ancillaries}/**`, `/api/admin/reports/load-factor` | flight-service | 3002 |
| `/api/bookings/**`, `/api/admin/bookings/**`, `/api/admin/vouchers/**`, `/api/admin/reports/sales` | booking-service | 3003 |
| `/api/payments/**`, `/api/admin/payments/**`, `/api/admin/refunds/**`, `/api/admin/reports/revenue` | payment-service | 3004 |
| `/api/admin/notifications/**` | notification-service | 3005 |

Endpoint vận hành có ở **mọi service**:

| Endpoint | Mục đích |
|---|---|
| `GET /health` | Health check cho Docker Compose |
| `GET /metrics` | Prometheus scrape |
| `GET /docs` | Swagger UI |

---

## 3. auth-service (`:3001`)

| # | Method | Endpoint | Quyền | Mô tả | UC | Ưu tiên |
|---|---|---|---|---|---|:-:|
| A1 | POST | `/api/auth/register` | Public | Đăng ký tài khoản | UC01 | P1 |
| A2 | POST | `/api/auth/login` | Public | Đăng nhập, trả về access token + refresh token | UC02 | P1 |
| A3 | POST | `/api/auth/refresh` | Public | Đổi refresh token lấy cặp token mới (rotation) | UC03 | P1 |
| A4 | POST | `/api/auth/logout` | User | Thu hồi refresh token | UC03 | P1 |
| A5 | GET | `/api/users/me` | User | Xem hồ sơ | UC04 | P2 |
| A6 | PATCH | `/api/users/me` | User | Cập nhật hồ sơ | UC04 | P2 |
| A7 | PATCH | `/api/users/me/password` | User | Đổi mật khẩu | UC04 | P2 |
| A8 | GET / POST | `/api/users/me/saved-passengers` | User | Xem / thêm hành khách lưu sẵn | UC04 | P2 |
| A9 | PUT / DELETE | `/api/users/me/saved-passengers/:id` | User | Sửa / xóa hành khách lưu sẵn | UC04 | P2 |
| A10 | POST | `/api/auth/forgot-password` | Public | Gửi OTP đặt lại mật khẩu qua email | UC05 | P3 |
| A11 | POST | `/api/auth/reset-password` | Public | Đặt lại mật khẩu bằng OTP | UC05 | P3 |
| A12 | GET | `/api/admin/users` | Admin | Danh sách user (lọc theo role, trạng thái) | UC06 | P2 |
| A13 | GET | `/api/admin/users/:id` | Admin | Chi tiết user | UC06 | P2 |
| A14 | PATCH | `/api/admin/users/:id/status` | Admin | Khóa / mở khóa tài khoản | UC06 | P2 |
| A15 | PATCH | `/api/admin/users/:id/role` | Admin | Gán role | UC06 | P2 |

## 4. flight-service (`:3002`)

### 4.1 Public / Customer
| # | Method | Endpoint | Quyền | Mô tả | UC | Ưu tiên |
|---|---|---|---|---|---|:-:|
| F1 | GET | `/api/airports` | Public | Danh sách sân bay (cho ô chọn điểm đi/đến) | UC07 | P1 |
| F2 | GET | `/api/flights/search` | Public | Tìm chuyến một chiều/khứ hồi kèm lọc và sắp xếp (xem tham số bên dưới) | UC07, UC08 | P1 |
| F3 | GET | `/api/flights/:id` | Public | Chi tiết chuyến bay và giá gói; giá tạm tính khi truyền số khách | UC09 | P1 |
| F4 | GET | `/api/flights/:id/seats` | User | Sơ đồ ghế và trạng thái ghế | UC10 | P1 |
| F5 | GET | `/api/ancillaries?flightId=` | Public | Danh mục dịch vụ bổ trợ của chuyến | UC31 | P2 |

**Tham số của F2:**

| Nhóm | Tham số | Ghi chú |
|---|---|---|
| Hành trình | `tripType` | `ONE_WAY` \| `ROUND_TRIP` |
|  | `from`, `to` | Mã sân bay IATA |
|  | `departDate`, `returnDate` | `returnDate` chỉ dùng khi khứ hồi |
| Hành khách | `adults`, `children`, `infants` | Số khách ADT/CHD/INF |
| Khoang | `cabin` | `ECONOMY` \| `BUSINESS` |
| Sắp xếp | `sort` | `price` \| `departTime` \| `duration` |
| Lọc | `airlines`, `minPrice`, `maxPrice`, `departFrom`, `departTo` | — |

### 4.2 Admin
| # | Method | Endpoint | Quyền | Mô tả | UC | Ưu tiên |
|---|---|---|---|---|---|:-:|
| F6 | GET / POST | `/api/admin/airports` | Admin | Danh sách / thêm sân bay | UC11 | P1 |
| F7 | PUT / DELETE | `/api/admin/airports/:code` | Admin | Sửa / xóa sân bay | UC11 | P1 |
| F8 | GET / POST | `/api/admin/airlines` | Admin | Danh sách / thêm hãng bay | UC11 | P1 |
| F9 | PUT / DELETE | `/api/admin/airlines/:id` | Admin | Sửa / xóa hãng bay | UC11 | P1 |
| F10 | GET / POST | `/api/admin/aircrafts` | Admin | Danh sách / thêm máy bay (kèm `seatLayout`) | UC11 | P1 |
| F11 | PUT / DELETE | `/api/admin/aircrafts/:id` | Admin | Sửa / xóa máy bay | UC11 | P1 |
| F12 | GET / POST | `/api/admin/flights` | Admin | Danh sách / tạo chuyến bay (tự sinh ghế và tồn chỗ) | UC12 | P1 |
| F13 | GET / PUT | `/api/admin/flights/:id` | Admin | Chi tiết / sửa chuyến bay | UC12 | P1 |
| F14 | PATCH | `/api/admin/flights/:id/status` | Admin | Đổi trạng thái `DELAYED` / `CANCELLED` (phát event `flight.status_changed`) | UC12 | P1 |
| F15 | GET / POST | `/api/admin/fare-families` | Admin | Danh sách / tạo gói giá kèm fare rule | UC13 | P1 |
| F16 | PUT / DELETE | `/api/admin/fare-families/:code` | Admin | Sửa / xóa gói giá | UC13 | P1 |
| F17 | PUT | `/api/admin/flights/:id/fares` | Admin | Đặt giá cho từng gói trên chuyến bay | UC13 | P1 |
| F18 | GET / POST | `/api/admin/ancillaries` | Admin | Danh mục dịch vụ bổ trợ | UC34 | P2 |
| F19 | PUT / DELETE | `/api/admin/ancillaries/:code` | Admin | Sửa / xóa dịch vụ bổ trợ | UC34 | P2 |
| F20 | GET | `/api/admin/reports/load-factor` | Admin | Tỉ lệ lấp đầy theo chuyến / tuyến | UC30 | P2 |

### 4.3 Internal (booking-service gọi)
| # | Method | Endpoint | Mô tả | UC |
|---|---|---|---|---|
| FI1 | GET | `/internal/flights/:id/fares/:fareCode` | Snapshot chuyến bay, giá gói và fare rule | UC14 |
| FI2 | POST | `/internal/inventory/hold` | Giữ N chỗ của khoang trên các chặng (all-or-nothing, TTL 15 phút) | UC15 |
| FI3 | POST | `/internal/inventory/release` | Nhả chỗ và ghế theo `holdRef` (bước bù trừ) | UC14, UC19 |
| FI4 | POST | `/internal/seats/hold` | Giữ ghế cụ thể cho booking | UC10 |
| FI5 | POST | `/internal/seats/auto-assign` | Tự gán ghế khi check-in | UC21 |
| FI6 | POST | `/internal/ancillaries/quote` | Báo giá dịch vụ bổ trợ theo danh sách mã | UC31 |

## 5. booking-service (`:3003`)

### 5.1 Customer / Guest
| # | Method | Endpoint | Quyền | Mô tả | UC | Ưu tiên |
|---|---|---|---|---|---|:-:|
| B1 | POST | `/api/bookings` | User | Tạo booking, giữ chỗ 15 phút, trả về PNR | UC14, UC15 | P1 |
| B2 | GET | `/api/bookings/me` | User | Danh sách booking của tôi (lọc theo trạng thái, phân trang) | UC17 | P1 |
| B3 | GET | `/api/bookings/:id` | Owner / Lookup | Chi tiết booking | UC17 | P1 |
| B4 | PUT | `/api/bookings/:id/seats` | Owner | Chọn / đổi ghế cho hành khách × chặng | UC10 | P1 |
| B5 | PUT | `/api/bookings/:id/ancillaries` | Owner | Chọn dịch vụ bổ trợ | UC31 | P2 |
| B6 | GET | `/api/bookings/:id/ticket` | Owner / Lookup | Vé điện tử (PNR, số vé, QR) | UC20 | P1 |
| B7 | POST | `/api/bookings/lookup` | Public | Tra cứu bằng PNR + họ, trả về `lookupToken` | UC32 | P2 |
| B8 | GET | `/api/bookings/:id/refund-quote` | Owner | Xem trước số tiền được hoàn | UC18 | P2 |
| B9 | POST | `/api/bookings/:id/cancel` | Owner | Hủy booking và yêu cầu hoàn tiền | UC18 | P2 |
| B10 | POST | `/api/bookings/:id/check-in` | Owner / Lookup | Check-in online (tự gán ghế nếu chưa có) | UC21 | P2 |
| B11 | GET | `/api/bookings/:id/boarding-pass` | Owner / Lookup | Boarding pass | UC21 | P2 |
| B12 | POST | `/api/bookings/:id/voucher` | Owner | Áp mã giảm giá | UC16 | P3 |
| B13 | GET | `/api/bookings/:id/change-quote?newFlightId=` | Owner | Báo giá đổi chuyến (chênh lệch + phí) | UC33 | P3 |
| B14 | POST | `/api/bookings/:id/change` | Owner | Đổi chuyến (tạo payment `purpose=CHANGE`) | UC33 | P3 |

### 5.2 Admin
| # | Method | Endpoint | Quyền | Mô tả | UC | Ưu tiên |
|---|---|---|---|---|---|:-:|
| B15 | GET | `/api/admin/bookings` | Admin | Danh sách booking (lọc theo PNR, chuyến, trạng thái, ngày) | UC22 | P2 |
| B16 | GET | `/api/admin/bookings/:id` | Admin | Chi tiết booking | UC22 | P2 |
| B17 | GET | `/api/admin/reports/sales` | Admin | Số vé bán và doanh thu dịch vụ bổ trợ theo ngày / tuyến | UC30 | P2 |
| B18 | CRUD | `/api/admin/vouchers` | Admin | Quản lý mã giảm giá | UC16 | P3 |

### 5.3 Internal (payment-service gọi)
| # | Method | Endpoint | Mô tả | UC |
|---|---|---|---|---|
| BI1 | GET | `/internal/bookings/:id` | Trạng thái, chủ booking, `total_amount`, `expires_at` | UC23 |

## 6. payment-service (`:3004`)

| # | Method | Endpoint | Quyền | Mô tả | UC | Ưu tiên |
|---|---|---|---|---|---|:-:|
| P1 | POST | `/api/payments/vnpay` | Owner | Tạo URL thanh toán VNPay cho booking | UC23 | P1 |
| P2 | GET | `/api/payments/vnpay/ipn` | VNPay | IPN server-to-server: verify chữ ký, cập nhật giao dịch, phát event | UC24 | P1 |
| P3 | GET | `/api/payments/vnpay/return` | Public | Verify tham số return URL để FE hiển thị kết quả | UC24 | P1 |
| P4 | GET | `/api/payments/me` | User | Lịch sử giao dịch của tôi | UC26 | P2 |
| P5 | GET | `/api/payments/bookings/:bookingId` | Owner | Các giao dịch của một booking | UC26 | P2 |
| P6 | GET | `/api/admin/payments` | Admin | Danh sách giao dịch | UC26 | P2 |
| P7 | GET | `/api/admin/refunds` | Admin | Danh sách hoàn tiền (lọc `FAILED`) | UC25 | P2 |
| P8 | POST | `/api/admin/refunds/:id/retry` | Admin | Xử lý lại khoản hoàn tiền bị lỗi | UC25 | P2 |
| P9 | GET | `/api/admin/reports/revenue` | Admin | Doanh thu theo ngày / tháng | UC30 | P2 |

> **Lưu ý:** IPN URL đăng ký với VNPay là `https://<ngrok-domain>/api/payments/vnpay/ipn`. Gateway cho endpoint này đi qua mà không cần JWT; tính xác thực dựa trên chữ ký `vnp_SecureHash`.

## 7. notification-service (`:3005`)

| # | Method | Endpoint | Quyền | Mô tả | UC | Ưu tiên |
|---|---|---|---|---|---|:-:|
| N1 | GET | `/api/admin/notifications` | Admin | Nhật ký email đã gửi / lỗi | UC27–29 | P2 |
| N2 | POST | `/api/admin/notifications/:id/resend` | Admin | Gửi lại email lỗi | UC27 | P3 |

notification-service chủ yếu **consume event**, không có API cho người dùng cuối.

---

## 8. Danh sách Event (RabbitMQ)

| Event | Publisher | Consumer | Payload chính | UC |
|---|---|---|---|---|
| `booking.created` | booking | notification | bookingId, expiresAt, contact | UC14 |
| `booking.confirmed` | booking | flight, notification | bookingId, pnr, segments, passengers, seats, contact | UC20 |
| `booking.expired` | booking | flight | bookingId (holdRef) | UC19 |
| `booking.cancelled` | booking | flight, payment, notification | bookingId, refundAmount, reason | UC18 |
| `booking.payment_late` | booking | payment | bookingId, paymentId | UC19 |
| `booking.checked_in` | booking | notification | bookingId, boardingPasses | UC21 |
| `payment.succeeded` | payment | booking | bookingId, paymentId, amount, paidAt | UC24 |
| `payment.failed` | payment | booking | bookingId, paymentId, reason | UC24 |
| `payment.refunded` | payment | booking, notification | bookingId, refundId, amount | UC18, UC25 |
| `flight.status_changed` | flight | booking, notification | flightId, oldStatus, newStatus, newDepartAt | UC12, UC28 |

- **Exchange:** `flight-booking.events` (kiểu topic).
- **Queue:** mỗi consumer có queue riêng, ví dụ `notification.booking.confirmed`.
- **Dead-letter:** mỗi queue gắn với DLQ `*.dlq`.

## 9. Thống kê

| Service | Public / User | Admin | Internal | Tổng |
|---|:-:|:-:|:-:|:-:|
| auth | 11 | 4 | 0 | 15 |
| flight | 5 | 15 | 6 | 26 |
| booking | 14 | 4 | 1 | 19 |
| payment | 5 | 4 | 0 | 9 |
| notification | 0 | 2 | 0 | 2 |
| **Tổng** | **35** | **29** | **7** | **71** |

- Số đếm theo dòng trong bảng; một dòng có thể gom 2 method trên cùng một path.
- Theo mức ưu tiên:

  | Mức ưu tiên | Số endpoint | Đầu mục |
  |---|:-:|---|
  | **P1** | 33 | A1–A4, F1–F4, F6–F17, FI1–FI4, B1–B4, B6, BI1, P1–P3 |
  | **P2** | 31 | Phần còn lại, trừ P3 |
  | **P3** | 7 | A10–A11, B12–B14, B18, N2 |
