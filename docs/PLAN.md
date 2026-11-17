# Plan đồ án cuối kỳ: Hệ thống đặt vé máy bay (Microservices)

## Bối cảnh
- Thời gian: **1 tháng**. Nhóm: **2–3 người**. Chấm theo [TIEU_CHI_DANH_GIA.md](../TIEU_CHI_DANH_GIA.md), thang 10 điểm.
- Công nghệ: NestJS (backend), React (FE, thiết kế trước bằng Claude Design), VNPay sandbox (thanh toán).
- **Phạm vi khai thác:** chỉ chặng bay **nội địa Việt Nam**, tiền tệ **VND**. Hành khách khai giấy tờ nội địa (CCCD), không cần hộ chiếu/visa.
- Nghiệp vụ mô phỏng theo cách vận hành thực tế của Vietnam Airlines, Vietjet và Traveloka (xem mục *Nguồn tham khảo*).
- **Ngoài phạm vi:** chặng bay quốc tế (hộ chiếu, visa, ngoại tệ, hệ số CHD 75%), hành trình nhiều chặng (multi-city), chuyến nối chuyến, hội viên/tích dặm, bảo hiểm, giữ chỗ trả sau. Thiết kế vẫn mở rộng được: hệ số giá nằm trong cấu hình, sân bay quản lý bằng CRUD.

---

## 1. Tác nhân (Actors)
| Actor | Mô tả |
|---|---|
| **Guest** | Khách chưa đăng nhập: tìm chuyến, xem giá, tra cứu đặt chỗ bằng PNR |
| **Customer** | Khách đã đăng nhập: đặt vé, thanh toán, quản lý booking, check-in |
| **Admin** | Quản trị: chuyến bay, gói giá, dịch vụ bổ trợ, booking, báo cáo |
| **VNPay** | Hệ thống ngoài: thanh toán, gọi IPN |
| **Thời gian (Time)** | Mốc thời gian kích hoạt các việc tự động: hủy booking quá hạn thanh toán, nhắc mở check-in. Cài đặt bằng cron job trong service |

## 2. Danh sách Use Case
Mức ưu tiên: **P1** bắt buộc, **P2** nên có, **P3** làm nếu còn thời gian.

Use case được nhóm theo **mục tiêu của actor**, mỗi nhóm là một use case tổng quát và được phân rã ở trang cùng số trong sơ đồ use case (`docs/diagrams/use-case.drawio`). Cách nhóm này không phụ thuộc việc chia service; ánh xạ sang service nằm ở §3.

### 1. Quản lý tài khoản
| ID | Use Case | Actor | Ưu tiên |
|---|---|---|:-:|
| UC01 | Đăng ký tài khoản | Guest | P1 |
| UC02 | Đăng nhập (JWT access + refresh token) | Guest | P1 |
| UC03 | Đăng xuất / làm mới token | Customer | P1 |
| UC04 | Xem/cập nhật hồ sơ (lưu sẵn hành khách hay đi cùng) | Customer | P2 |
| UC05 | Quên mật khẩu (OTP qua email) | Guest | P3 |

### 2. Tìm kiếm chuyến bay
| ID | Use Case | Actor | Ưu tiên |
|---|---|---|:-:|
| UC07 | Tìm chuyến bay một chiều/khứ hồi theo điểm đi/đến, ngày, số khách ADT/CHD/INF, khoang; trả về giá thấp nhất mỗi chuyến | Guest/Customer | P1 |
| UC08 | Lọc/sắp xếp theo giá, giờ cất cánh, hãng, thời gian bay | Guest/Customer | P2 |
| UC09 | Xem chi tiết chuyến bay và **giá gói** | Guest/Customer | P1 |

### 3. Check-in trực tuyến
| ID | Use Case | Actor | Ưu tiên |
|---|---|---|:-:|
| UC32 | **Tra cứu đặt chỗ bằng PNR + họ** (không cần đăng nhập) | Guest | P2 |
| UC21 | **Check-in online** (mở 24h, đóng 1h trước giờ bay), tự gán ghế nếu chưa chọn, xuất boarding pass | Customer | P2 |

> **UC32 khác UC17 thế nào?**
> - **UC17**: chủ tài khoản đăng nhập, xem **tất cả** booking mình đã đặt.
> - **UC32**: người đi nhưng không phải người đặt (bố mẹ đặt cho con, công ty đặt cho nhân viên). Chỉ có PNR trong email, nhập **PNR + họ** để xem **đúng 1 booking** và check-in (UC21).
> - PNR + họ đóng vai trò thay mật khẩu, nên phải có rate limit chống dò mã.

### 4. Đặt vé: nghiệp vụ lõi
| ID | Use Case | Actor | Ưu tiên |
|---|---|---|:-:|
| UC14 | Tạo booking: chọn chuyến + gói giá cho từng chiều, nhập hành khách (ADT/CHD/INF) và **thông tin liên hệ** | Customer | P1 |
| UC15 | **Giữ chỗ tạm thời** 15 phút: trừ tồn chỗ của khoang; nếu đã chọn ghế thì giữ cả ghế | Customer («include» từ UC14) | P1 |
| UC10 | Xem sơ đồ ghế, chọn ghế cho từng hành khách × chặng (phí ghế theo §3.3) | Customer | P1 |
| UC31 | Mua **dịch vụ bổ trợ**: hành lý ký gửi thêm, suất ăn, ghế trả phí | Customer | P2 |
| UC17 | Xem lịch sử và chi tiết booking ("Đặt chỗ của tôi") | Customer | P1 |
| UC18 | Hủy booking và hoàn tiền **theo fare rule** (miễn phí trong 24h kể từ lúc mua) | Customer | P2 |
| UC33 | **Đổi chuyến bay** (gói cho phép; trả chênh lệch + phí đổi; trước giờ bay ≥ 3h) | Customer | P3 |
| UC19 | Tự động hủy booking quá hạn thanh toán, nhả chỗ và ghế | Thời gian | P1 |

### 5. Gửi thông báo
| ID | Use Case | Actor | Ưu tiên |
|---|---|---|:-:|
| UC27 | Email xác nhận đặt vé kèm e-ticket | VNPay («include» từ UC20) | P1 |
| UC28 | Thông báo chuyến bay delay/hủy | Admin («extend» từ UC12) | P2 |
| UC29 | Email nhắc **mở check-in** (24h trước giờ bay) | Thời gian | P3 |

### 6. Thanh toán
| ID | Use Case | Actor | Ưu tiên |
|---|---|---|:-:|
| UC23 | Thanh toán VNPay: tạo URL, redirect | Customer | P1 |
| UC24 | Nhận IPN/return URL, xác minh chữ ký | VNPay | P1 |
| UC20 | Xuất **vé điện tử** (PNR, số vé, QR) | VNPay («include» từ UC24) | P1 |
| UC16 | Áp mã giảm giá (voucher) | Customer | P3 |
| UC25 | Hoàn tiền (VNPay refund API sandbox, hoặc ghi nhận hoàn) | Customer («include» từ UC18) / Admin | P2 |
| UC26 | Lịch sử giao dịch | Customer/Admin | P2 |

### 7. Quản lý chuyến bay
| ID | Use Case | Actor | Ưu tiên |
|---|---|---|:-:|
| UC11 | Quản lý sân bay, hãng bay, máy bay (CRUD, sơ đồ ghế) | Admin | P1 |
| UC12 | Quản lý chuyến bay (tạo, sửa, đổi trạng thái DELAYED/CANCELLED) | Admin | P1 |
| UC13 | Cấu hình **gói giá** cho chuyến bay: giá từng gói kèm **fare rule** (hành lý, đổi, hoàn, phí) | Admin | P1 |
| UC34 | Quản lý danh mục **dịch vụ bổ trợ** (hành lý thêm, suất ăn, loại ghế trả phí) | Admin | P2 |

### Use case quản trị đơn lẻ (vẽ trực tiếp ở trang tổng quan, không phân rã)
| ID | Use Case | Actor | Ưu tiên |
|---|---|---|:-:|
| UC06 | Quản lý người dùng (khóa/mở, gán role) | Admin | P2 |
| UC22 | Quản lý booking toàn hệ thống | Admin | P2 |
| UC30 | Dashboard: doanh thu (vé + dịch vụ bổ trợ), số vé bán, tỉ lệ lấp đầy | Admin | P2 |

**Tổng cộng 34 UC: 17 P1, 13 P2, 4 P3.**

> Use case không có người khởi động trực tiếp (giữ chỗ, xuất vé, gửi email, hoàn tiền) ghi actor là **actor của use case gốc** kèm quan hệ «include»/«extend», khớp với sơ đồ use case. Hệ thống không bao giờ là actor của chính nó.

## 2.1 Quy trình đặt vé phía người dùng
1. **Tìm chuyến bay**: một chiều/khứ hồi, số khách, khoang.
2. **Chọn chuyến + gói giá** cho chiều đi (và chiều về). Bảng gói giá hiển thị giá, hành lý, điều kiện đổi/hoàn.
3. **Nhập hành khách + liên hệ** → `POST /bookings`. Hệ thống giữ chỗ 15 phút, cấp **PNR**, hiển thị đồng hồ đếm ngược.
4. **Chọn ghế + dịch vụ bổ trợ** (bỏ qua được) → `PUT /bookings/:id/seats`, `PUT /bookings/:id/ancillaries`. Tổng tiền tính lại.
5. **Thanh toán** VNPay.
6. **Xác nhận**: xuất số vé, gửi e-ticket qua email liên hệ.

---

## 3. Kiến trúc Microservices
```
          React FE
             │  HTTPS (ngrok)
      ┌──────▼──────┐
      │ API Gateway │  ← xác thực JWT, phân quyền, rate limit, route
      └──────┬──────┘
   ┌────────┬────────┼─────────┬────────────┐
   ▼        ▼        ▼         ▼            ▼
 Auth    Flight   Booking   Payment    Notification
 (PG)    (PG)     (PG)      (PG)       (PG)
                    │ Redis (lock giữ chỗ/ghế, cache tìm kiếm)
   ─────────── RabbitMQ (event bus) ───────────
   Prometheus ← /metrics của mọi service → Grafana
```

| Service | Trách nhiệm |
|---|---|
| **api-gateway** | Điểm vào duy nhất: verify JWT, kiểm tra role, proxy, rate limit, correlation-id |
| **auth-service** | Tài khoản, token, role, hồ sơ, hành khách lưu sẵn |
| **flight-service** | Sân bay, hãng, máy bay, chuyến bay; gói giá + fare rule; danh mục dịch vụ bổ trợ; tồn chỗ theo khoang; sơ đồ ghế; giữ/nhả/chốt chỗ và ghế; tìm kiếm |
| **booking-service** | Booking nhiều chặng, hành khách, liên hệ, dịch vụ bổ trợ, tính tiền, vòng đời booking, PNR/e-ticket, check-in, hủy/đổi, tra cứu PNR, saga |
| **payment-service** | VNPay (URL, IPN, verify), giao dịch, hoàn tiền, thu thêm khi đổi chuyến |
| **notification-service** | Nhận event, gửi email, lưu log |

### 3.1 Giao tiếp giữa các service
- **REST đồng bộ** (cần câu trả lời ngay):
  - Booking → Flight: snapshot giá + fare rule; giữ/nhả chỗ và ghế; tra danh mục dịch vụ bổ trợ.
  - Payment → Booking: kiểm tra booking và số tiền.
- **RabbitMQ bất đồng bộ** (báo tin "việc này đã xảy ra", ai quan tâm thì tự xử lý). Exchange `flight-booking.events` (topic):

| Event | Publisher | Consumer |
|---|---|---|
| `booking.created` | Booking | Notification |
| `payment.succeeded` / `payment.failed` | Payment | Booking |
| `booking.confirmed` | Booking | Flight (chỗ/ghế → SOLD), Notification (gửi e-ticket) |
| `booking.cancelled` / `booking.expired` | Booking | Flight (nhả), Payment (hoàn theo số tiền Booking đã tính) |
| `booking.checked_in` | Booking | Notification (gửi boarding pass) |
| `flight.status_changed` | Flight | Booking (hủy/hoàn 100% nếu chuyến bị hủy), Notification |

- **Xử lý lỗi:** format lỗi chung; timeout + retry khi gọi REST; dead-letter queue (DLQ) cho message xử lý lỗi nhiều lần; idempotency cho IPN và consumer; outbox pattern (P3).

### 3.2 Saga đặt vé (choreography)
1. `POST /bookings` → Booking lấy snapshot các chặng từ Flight, validate, tính giá.
2. Flight `POST /internal/inventory/hold`: giữ N chỗ trong khoang mỗi chặng (all-or-nothing, transaction có lock), hết hạn sau 15 phút.
3. Booking sinh PNR, lưu `PENDING_PAYMENT` → publish `booking.created`.
4. (Tùy chọn) Chọn ghế: Flight `POST /internal/seats/hold`.
5. Thanh toán VNPay → IPN → `payment.succeeded` → Booking `CONFIRMED`, sinh số vé → `booking.confirmed` → Flight chốt `SOLD`, Notification gửi email.
6. Thất bại hoặc hết 15 phút → `EXPIRED` → Flight nhả chỗ và ghế (**bù trừ**).

**Trạng thái booking:** `PENDING_PAYMENT → CONFIRMED → CHECKED_IN → COMPLETED`, nhánh phụ `CANCELLED / EXPIRED / REFUNDED`.

### 3.3 Quy tắc nghiệp vụ
- **Hành khách:** tối đa 9 (ADT + CHD), ít nhất 1 ADT, INF ≤ ADT. ADT ≥ 12, CHD 2–11, INF từ 7 ngày đến dưới 2 tuổi. Tuổi ADT/CHD tính tại ngày bay **chặng đầu tiên**; tuổi INF tính tại ngày bay **từng chặng** (theo Vietnam Airlines). INF không có ghế, không check-in riêng.
- **Giá vé** = `giá gói × hệ số khách` + thuế/phí mỗi khách + dịch vụ bổ trợ + phí ghế − voucher. Booking lưu **snapshot** giá và fare rule tại thời điểm đặt.
  - Hệ số khách: **ADT 1.0, CHD 0.9, INF 0.1**, theo quy định chặng nội địa của Vietnam Airlines (chặng quốc tế CHD là 0.75). Hệ số lưu trong cấu hình, không gắn cứng trong code.
  - Hệ số chỉ áp cho **giá vé gốc**; thuế/phí tính riêng theo từng loại khách.
- **Gói giá mẫu** (seed):

  | Gói | Xách tay | Ký gửi | Đổi chuyến | Hoàn vé | Chọn ghế |
  |---|---|---|---|---|---|
  | ECO_SAVER (Siêu tiết kiệm) | 7kg | 0 | Không | Không | Mọi ghế tính phí |
  | ECO_STANDARD (Tiêu chuẩn) | 7kg | 20kg | Phí 350k + chênh lệch | Phí 30% | Ghế thường miễn phí, ghế đặc biệt tính phí |
  | ECO_FLEX (Linh hoạt) | 7kg | 30kg | Miễn phí, trả chênh lệch | Phí 10% | Miễn phí mọi ghế |
  | BUSINESS | 2×7kg | 40kg | Miễn phí | Phí 10% | Miễn phí mọi ghế |

- **Phí chọn ghế:**
  - Ghế có `seat_type`: `STANDARD` (thường), `FRONT` (hàng đầu, xuống máy bay nhanh), `EXIT` (cạnh lối thoát hiểm, rộng chân). Ghế đặc biệt có `extra_fee` riêng.
  - Phí = `extra_fee` của loại ghế, được miễn theo cờ `free_seat_selection` của gói (bảng trên). SAVER chọn ghế thường vẫn mất phí cơ bản (vd 50k).
  - **Không chọn ghế thì luôn miễn phí**: hệ thống tự gán ghế trống khi check-in.
  - Ghế `EXIT` chỉ dành cho ADT không đi kèm INF (quy định an toàn).
- **PNR và số vé:**
  - **PNR** do booking-service tự sinh khi tạo booking: 6 ký tự từ bảng chữ/số bỏ ký tự dễ nhầm (`0 O 1 I`), ví dụ `K7XQ2M`. Cột `pnr` UNIQUE; trùng thì sinh lại.
  - **Số vé** (`ticket_no`) sinh khi `CONFIRMED`, mỗi hành khách × chặng một số: 13 chữ số = mã hãng 3 số + số thứ tự từ DB sequence.
- **Đặt vé:** chỉ chuyến `SCHEDULED` và còn ≥ **3h** trước giờ bay (cấu hình qua env).
- **Hoàn vé:** hoàn **100%** nếu hủy trong 24h kể từ lúc mua **và** chuyến còn trên 24h mới bay; ngoài ra hoàn theo `refund_fee` của gói; gói không hoàn thì 0đ. Phí dịch vụ bổ trợ không hoàn, trừ khi hãng hủy chuyến.
- **Hãng hủy chuyến:** hoàn 100% toàn bộ và gửi email.
- **Đổi chuyến:** cùng tuyến, giá mới ≥ giá cũ, trước giờ bay ≥ 3h; trả chênh lệch + phí đổi (phí không hoàn).
- **Sau khi xuất vé:** không sửa họ tên hành khách.
- **Check-in online:** mở 24h, đóng 1h trước giờ bay; chỉ booking `CONFIRMED`; hành khách chưa có ghế được tự gán ghế trống cùng khoang.

### 3.4 Monitoring (Prometheus + Grafana)
- **Mục đích:** biết hệ thống đang khỏe hay không khi chạy, thay vì đợi người dùng báo lỗi. Rubric có tiêu chí monitoring.
- **Cách tích hợp:**
  1. Mỗi service cài `@willsoto/nestjs-prometheus` + `prom-client`, mở endpoint `GET /metrics` (số request, thời gian phản hồi, lỗi, RAM/CPU Node).
  2. Thêm metric nghiệp vụ: `bookings_created_total`, `bookings_confirmed_total`, `payments_failed_total`, `seat_hold_conflicts_total`.
  3. Container **Prometheus** đọc `prometheus.yml` liệt kê địa chỉ `/metrics` của 6 service, cứ 15s lấy số liệu một lần.
  4. Container **Grafana** dùng Prometheus làm data source; dashboard provision sẵn bằng file JSON: request/s, latency p95, tỉ lệ lỗi 5xx theo service, số booking/thanh toán.
  5. RabbitMQ bật plugin `rabbitmq_prometheus` để Grafana thấy độ dài hàng đợi và message trong DLQ.

---

## 4. Thiết kế dữ liệu (database per service)
| Service | Bảng chính |
|---|---|
| auth | `users`, `refresh_tokens`, `saved_passengers` (P2) |
| flight | `airports`, `airlines`, `aircrafts`(seat_layout), `flights`, `cabin_inventory`(flight_id, cabin, total, held, sold), `fare_families`(code, cabin, name, carry_on_kg, checked_kg, changeable, change_fee, refundable, refund_fee_pct, free_seat_selection), `flight_fares`(flight_id, fare_family_id, price), `flight_seats`(flight_id, seat_no, cabin, seat_type STANDARD/FRONT/EXIT, extra_fee, status, hold_ref, hold_expires_at), `ancillary_catalog`(type BAGGAGE/MEAL, code, name, price) |
| booking | `bookings`(id, pnr UNIQUE, user_id, status, contact_email, contact_phone, total_amount, expires_at, created_at), `booking_segments`(booking_id, flight_id, direction OUT/IN, fare snapshot, flight snapshot), `passengers`(booking_id, type, full_name, dob, gender, id_number), `passenger_segments`(passenger_id, segment_id, seat_no, seat_fee, ticket_no, checked_in_at, boarding_pass_no), `booking_ancillaries`(passenger_segment_id, type, code, price), `booking_changes` (P3) |
| payment | `payments`(booking_id, amount, purpose BOOKING/CHANGE, status, vnp_txn_ref, ...), `refunds`(payment_id, amount, reason, status) |
| notification | `notification_logs` |

## 5. Công nghệ & cấu trúc repo
- Monorepo NestJS (`apps/<service>` + `libs/common`), Prisma/TypeORM + PostgreSQL, Redis, RabbitMQ.
- Swagger cho từng service; JWT + RBAC tại Gateway.
- Monitoring: `@willsoto/nestjs-prometheus`, Prometheus, Grafana.
- Email: Nodemailer + **Gmail SMTP thật** (App Password, khai báo trong `.env`, không commit). Không dùng công cụ giả lập như Mailpit/Mailtrap.
- Deploy: Docker Compose + ngrok. Test: Jest (có unit test tính tiền hoàn, phí ghế, tiền đổi chuyến) + Postman/Newman.
- FE: React + Vite theo bản thiết kế Claude Design.

## 6. Lộ trình 4 tuần
| Tuần | Mục tiêu |
|---|---|
| **1** | Tài liệu: Use Case diagram, đặc tả P1, ERD, sequence diagram đặt vé và check-in. Dựng monorepo + hạ tầng Docker. Thiết kế FE theo 6 bước §2.1 |
| **2** | Auth, Gateway, Flight: CRUD, gói giá + fare rule, tìm kiếm một chiều/khứ hồi, tồn chỗ, sơ đồ ghế, giữ/nhả. Seed dữ liệu |
| **3** | Booking (nhiều chặng, giữ chỗ, chọn ghế, saga, hết hạn, PNR, e-ticket), Payment VNPay, Notification. FE luồng đặt vé |
| **4** | P2: dịch vụ bổ trợ, tra cứu PNR, hủy/hoàn, check-in online, delay/hủy chuyến, dashboard admin. Monitoring, ngrok, test, báo cáo, demo |

**Chia việc:** A: Gateway + Auth + DevOps/monitoring · B: Flight + Booking · C: Payment + Notification + FE.

## 7. Đối chiếu tiêu chí chấm
- **Phân tích & thiết kế:** nghiệp vụ có cơ sở thực tế (gói giá, dịch vụ bổ trợ, check-in), trích dẫn nguồn trong báo cáo.
- **Kiến trúc microservice:** 5 service + gateway, database per service, REST + RabbitMQ, saga có bù trừ.
- **Chức năng & nghiệp vụ:** đủ vòng đời đặt → thanh toán → check-in → hoàn/đổi.
- **Bảo mật:** JWT access/refresh, RBAC, rate limit, xác minh chữ ký VNPay.
- **Monitoring & deploy:** Prometheus + Grafana, Docker Compose, ngrok.
- **Kiểm thử:** Jest + Newman end-to-end.

## 8. Kiểm chứng
- `docker compose up -d`: mọi container healthy.
- Newman end-to-end (thẻ test VNPay NCB): tìm khứ hồi → chọn gói → tạo booking (có PNR) → chọn ghế + mua hành lý → thanh toán → `CONFIRMED` → email có PNR + số vé; tra cứu bằng PNR + họ; check-in chuyến bay gần → boarding pass.
- Nhánh lỗi: 2 người tranh ghế cuối, chỉ 1 người giữ được; hết 15 phút → `EXPIRED`, trả tồn chỗ; hủy SAVER hoàn 0đ; hủy STANDARD sau 24h hoàn 70%; hủy trong 24h hoàn 100%; admin hủy chuyến → hoàn 100% + email.
- Prometheus targets đều `UP`; Grafana có số liệu; IPN VNPay qua ngrok gọi về thành công.

## Thuật ngữ loại hành khách
| Mã | Viết tắt của | Nghĩa | Tuổi | Ghế riêng? | Hệ số giá vé (nội địa) |
|---|---|---|---|---|
| **ADT** | Adult | Người lớn | từ 12 tuổi trở lên | Có | 100% |
| **CHD** | Child | Trẻ em | 2–11 tuổi | Có | 90% |
| **INF** | Infant | Em bé | 7 ngày đến dưới 2 tuổi | **Không**, ngồi trong lòng người lớn | 10% |

## Nguồn tham khảo
- Vietnam Airlines – Mua vé trên website: https://www.vietnamairlines.com/vn/vi/buy-tickets-other-products/how-to-buy-tickets-and-make-payment/how-to-purchase-tickets/purchase-on-website
- Vietnam Airlines – Hoàn/đổi vé tự nguyện: https://www.vietnamairlines.com/vn/vi/buy-tickets-other-products/booking-and-manage-bookings/voluntary-refund-rebook
- Vietjet – Hạng vé: https://www.vietjetair.com/vi/diem-den/kinh-nghiem/hang-ve-vietjet-va-mo-hinh-hang-khong-hybrid-so-sanh-chi-tiet
- Vietjet – Vé Eco: https://www.vietjetair.com/vi/diem-den/kinh-nghiem/ve-vietjet-eco-la-gi-nhung-dieu-can-biet-khi-mua-ve-eco
- Vietnam Airlines – Dịch vụ cho trẻ em (hệ số giá CHD/INF, cách tính tuổi): https://www.vietnamairlines.com/vn/vi/travel-information/special-services/infants-children
- Traveloka – Hủy vé, hoàn tiền: https://quantrimang.com/cong-nghe/cach-hoan-tien-ve-may-bay-traveloka-203024
