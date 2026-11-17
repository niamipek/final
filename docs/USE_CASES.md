# Đặc tả Use Case – Hệ thống đặt vé máy bay

> - Danh sách đầy đủ 34 use case xem tại [PLAN.md](PLAN.md#2-danh-sách-use-case). Nghiệp vụ được đối chiếu với Vietnam Airlines, Vietjet, Traveloka (nguồn ở cuối PLAN.md).
> - File này đặc tả **tất cả UC P1** và các **UC P2 có nghiệp vụ phức tạp** (UC18, UC21, UC31, UC32), theo mẫu: Actor, Service phụ trách, Tiền điều kiện, Luồng chính, Ngoại lệ, Hậu điều kiện, API.
> - Đường dẫn API là đường dẫn đi qua Gateway (`/api/...`). Các endpoint `/internal/...` chỉ gọi được giữa các service trong mạng Docker; Gateway không public các endpoint này.

## Thuật ngữ
| Thuật ngữ | Ý nghĩa |
|---|---|
| **PNR** | Mã đặt chỗ gồm 6 ký tự chữ và số, áp dụng cho cả booking (khứ hồi vẫn chỉ có 1 PNR) |
| **Segment (chặng)** | Một chuyến bay trong booking: `OUT` là chiều đi, `IN` là chiều về |
| **Cabin (khoang)** | `ECONOMY`, `BUSINESS` |
| **Fare family (gói giá)** | `ECO_SAVER`, `ECO_STANDARD`, `ECO_FLEX`, `BUSINESS`. Mỗi gói có một **fare rule** quy định hành lý, quyền đổi/hoàn và phí |
| **Ancillary** | Dịch vụ bổ trợ: hành lý ký gửi thêm, suất ăn, ghế trả phí |
| **ADT / CHD / INF** | Người lớn (≥ 12 tuổi) / Trẻ em (2–11 tuổi) / Em bé (7 ngày đến < 2 tuổi). ADT/CHD tính tuổi tại ngày bay chặng đầu; INF tính tại ngày bay từng chặng |

---

## Use case tổng quát và phân rã
Sơ đồ use case nhóm theo **mục tiêu của actor**. Mỗi use case tổng quát được phân rã ở một trang của `docs/diagrams/use-case.drawio`:

| Trang | Use case tổng quát | Actor | Use case chi tiết |
|:-:|---|---|---|
| 1 | Quản lý tài khoản | Guest, Customer | UC01–UC05 |
| 2 | Tìm kiếm chuyến bay | Guest | UC07–UC09 |
| 3 | Check-in trực tuyến | Guest, Customer | UC21, UC32 |
| 4 | Đặt vé | Customer, Thời gian | UC10, UC14, UC15, UC17–UC19, UC31, UC33 |
| 5 | Gửi thông báo | Thời gian (và gián tiếp qua UC12, UC20) | UC27–UC29 |
| 6 | Thanh toán | Customer, VNPay, Admin | UC16, UC20, UC23–UC26 |
| 7 | Quản lý chuyến bay | Admin | UC11–UC13, UC34 |
| 0 | (vẽ trực tiếp, không phân rã) | Admin | UC06, UC22, UC30 |

Đặc tả bên dưới vẫn sắp theo thứ tự mã UC; dòng **Service** của mỗi đặc tả chỉ cho biết service nào cài đặt use case đó.

## A. Xác thực & tài khoản

### UC01 – Đăng ký tài khoản
- **Actor:** Guest
- **Service:** auth-service

**Luồng chính:**
1. Guest nhập email, mật khẩu, họ tên, số điện thoại.
2. Hệ thống validate:
   - email đúng định dạng;
   - mật khẩu ≥ 8 ký tự, có cả chữ và số;
   - số điện thoại đúng định dạng VN.
3. Hệ thống kiểm tra email chưa tồn tại.
4. Hệ thống hash mật khẩu bằng bcrypt và tạo user với `role=CUSTOMER`, `status=ACTIVE`.
5. Trả về thông tin user (không kèm mật khẩu).

**Ngoại lệ:**
- 2a. Dữ liệu không hợp lệ → `400 VALIDATION_ERROR`.
- 3a. Email đã tồn tại → `409 EMAIL_ALREADY_EXISTS`.

- **API:** `POST /api/auth/register`

### UC02 – Đăng nhập
- **Actor:** Guest
- **Service:** auth-service

**Luồng chính:**
1. Guest nhập email và mật khẩu.
2. Hệ thống so khớp hash và kiểm tra `status=ACTIVE`.
3. Hệ thống cấp **access token** (JWT, hạn 15 phút, payload `{sub, email, role}`) và **refresh token** (hạn 7 ngày; chỉ lưu bản hash).
4. Trả về hai token và thông tin user.

**Ngoại lệ:**
- Sai email hoặc mật khẩu → `401 INVALID_CREDENTIALS`.
- Tài khoản bị khóa → `403 ACCOUNT_LOCKED`.
- Gửi quá 5 lần/phút → `429` (rate limit tại Gateway).

- **API:** `POST /api/auth/login`

### UC03 – Làm mới token / Đăng xuất
- **Actor:** Customer
- **Service:** auth-service

**Luồng chính:**
- **Làm mới:** client gửi refresh token. Nếu token hợp lệ, hệ thống thu hồi token cũ và cấp cặp token mới (*rotation*).
- **Đăng xuất:** hệ thống thu hồi refresh token.

**Ngoại lệ:** Token không hợp lệ hoặc đã bị thu hồi → `401 INVALID_REFRESH_TOKEN`.

- **API:** `POST /api/auth/refresh`, `POST /api/auth/logout`

---

## B. Chuyến bay, giá & tìm kiếm

### UC07 – Tìm chuyến bay
- **Actor:** Guest/Customer
- **Service:** flight-service

**Luồng chính:**
1. Người dùng nhập:
   - loại hành trình: một chiều hoặc khứ hồi;
   - điểm đi, điểm đến (mã IATA);
   - ngày đi, và ngày về nếu khứ hồi;
   - số khách ADT/CHD/INF;
   - khoang.
2. Hệ thống validate:
   - điểm đi khác điểm đến;
   - ngày đi không ở quá khứ, ngày về ≥ ngày đi;
   - 1 ≤ ADT, ADT + CHD ≤ 9, INF ≤ ADT.
3. Hệ thống lọc các chuyến thỏa cả 4 điều kiện:
   - `status=SCHEDULED`;
   - khởi hành trong ngày đã chọn;
   - giờ khởi hành còn cách hiện tại ≥ `BOOKING_CUTOFF_HOURS` (mặc định 3h);
   - số chỗ trống của khoang (`total - held - sold`) ≥ ADT + CHD.
4. Với mỗi chuyến, hệ thống trả về:
   - số hiệu, hãng, giờ đi/đến, thời gian bay;
   - **giá thấp nhất** trong các gói của khoang;
   - số chỗ còn lại.

   Kết quả được cache trong Redis 60 giây.
5. Nếu là khứ hồi: trả về hai danh sách `outbound` và `inbound`.

**Ngoại lệ:**
- Input sai → `400`.
- Không có chuyến → trả mảng rỗng.

- **API:** `GET /api/flights/search?tripType=ROUND_TRIP&from=SGN&to=HAN&departDate=2026-12-20&returnDate=2026-12-25&adults=2&children=1&infants=0&cabin=ECONOMY`

### UC09 – Xem chi tiết chuyến bay và giá gói
- **Actor:** Guest/Customer
- **Service:** flight-service

**Luồng chính:**
1. Người dùng chọn một chuyến.
2. Hệ thống trả về thông tin chuyến bay và **danh sách gói giá của khoang**. Mỗi gói gồm:
   - giá;
   - hành lý xách tay và ký gửi;
   - đổi chuyến: được hay không, phí đổi;
   - hoàn vé: được hay không, % phí hoàn;
   - chọn ghế miễn phí hay tính phí.
3. Nếu có query số khách, hệ thống trả kèm **giá tạm tính theo từng gói**, chia theo ADT/CHD/INF và thuế/phí.

**Ngoại lệ:** Không tìm thấy chuyến → `404 FLIGHT_NOT_FOUND`.

- **API:** `GET /api/flights/:id?adults=2&children=1&infants=0`

### UC10 – Xem sơ đồ ghế và chọn ghế
- **Actor:** Customer
- **Service:** flight-service (dữ liệu ghế) + booking-service (gán ghế cho hành khách)
- **Tiền điều kiện:** Booking đang ở `PENDING_PAYMENT`, nghĩa là đã giữ chỗ (UC14–15).

**Luồng chính:**
1. Hệ thống trả sơ đồ ghế của từng chặng. Mỗi ghế có:
   - `seatNo`, `cabin`;
   - `seatType`: STANDARD / FRONT / EXIT;
   - `extraFee`;
   - `status`: AVAILABLE / HELD / SOLD. Ghế `HELD` đã quá hạn được trả về như AVAILABLE.
2. Customer chọn ghế cho từng hành khách (trừ INF) trên từng chặng, chỉ trong khoang của gói đã mua.
3. Booking-service gọi flight-service `POST /internal/seats/hold` với `{holdRef: bookingId, flightId, seatNos}`.
   - Việc giữ ghế là all-or-nothing.
   - Ghế giữ trước đó của cùng booking nhưng không còn được chọn sẽ được nhả.
4. Booking-service tính **phí ghế** cho từng hành khách × chặng (lưu vào `passenger_segments.seat_fee`):

   | Gói | Ghế STANDARD | Ghế FRONT / EXIT |
   |---|---|---|
   | ECO_SAVER | Phí cơ bản (vd 50.000đ) | `extraFee` |
   | ECO_STANDARD | Miễn phí | `extraFee` |
   | ECO_FLEX, BUSINESS | Miễn phí | Miễn phí |

   - Không chọn ghế thì luôn miễn phí (tự gán khi check-in).
   - Ghế EXIT chỉ cho hành khách ADT không bế INF (quy định an toàn) → vi phạm trả `400 EXIT_SEAT_NOT_ALLOWED`.
5. Cập nhật tổng tiền booking và trả về.

**Ngoại lệ:**
- Ghế đã bị người khác giữ hoặc bán → `409 SEAT_UNAVAILABLE` kèm danh sách ghế lỗi.
- Ghế khác khoang → `400 SEAT_CABIN_MISMATCH`.
- Booking không còn `PENDING_PAYMENT` → `409 BOOKING_NOT_EDITABLE`.
- Bỏ qua bước chọn ghế → hợp lệ; ghế sẽ được tự gán khi check-in (UC21).

- **API:** `GET /api/flights/:id/seats`, `PUT /api/bookings/:id/seats`

### UC11 – Quản lý sân bay, hãng bay, máy bay
- **Actor:** Admin
- **Service:** flight-service
- **Tiền điều kiện:** Đăng nhập với `role=ADMIN`; Gateway kiểm tra RBAC.

**Luồng chính:** CRUD sân bay (mã IATA là duy nhất), hãng bay, máy bay.
- Máy bay có `seat_layout`, ví dụ: Business hàng 1–3 kiểu 2-2; Economy hàng 4–30 kiểu 3-3.
- Ghế FRONT là hàng 4–5, ghế EXIT là hàng 12–13; hai loại này có `extraFee`.

**Ngoại lệ:**
- Trùng mã → `409`.
- Xóa tài nguyên đang được chuyến bay dùng → `409 RESOURCE_IN_USE`.
- Không phải admin → `403`.

- **API:** `/api/admin/airports`, `/api/admin/airlines`, `/api/admin/aircrafts`

### UC12 – Quản lý chuyến bay
- **Actor:** Admin
- **Service:** flight-service

**Luồng chính (tạo chuyến):**
1. Admin nhập số hiệu, hãng, máy bay, điểm đi/đến, giờ đi/đến.
2. Hệ thống validate và kiểm tra máy bay không trùng lịch với chuyến khác.
3. Hệ thống tạo chuyến với `status=SCHEDULED`.
4. Hệ thống **tự sinh dữ liệu** từ `seat_layout`:
   - `flight_seats`;
   - `cabin_inventory` (`total` = số ghế của khoang).

**Luồng đổi trạng thái:**
1. Admin chuyển chuyến sang `DELAYED` (kèm giờ mới) hoặc `CANCELLED`.
2. Hệ thống publish `flight.status_changed`.
3. Các service khác xử lý event:
   - Booking: nếu chuyến bị hủy, hủy và **hoàn 100%** cho mọi booking có chặng thuộc chuyến này.
   - Notification: gửi email cho hành khách (UC28).

**Ngoại lệ:**
- Sửa chuyến đã cất cánh → `409 FLIGHT_ALREADY_DEPARTED`.
- Trùng lịch máy bay → `409 AIRCRAFT_SCHEDULE_CONFLICT`.

- **API:** `POST/PUT/GET /api/admin/flights`, `PATCH /api/admin/flights/:id/status`

### UC13 – Cấu hình gói giá và fare rule
- **Actor:** Admin
- **Service:** flight-service

**Luồng chính:**
1. Admin quản lý danh mục **fare family**. Mỗi gói gồm: `code`, `cabin`, `name`, `carry_on_kg`, `checked_kg`, `changeable`, `change_fee`, `refundable`, `refund_fee_pct`, `free_seat_selection`.
2. Với mỗi chuyến, admin bật các gói được bán và đặt giá cho từng gói (`flight_fares`).
   - Gói của khoang nào thì dùng chung chỗ trống của khoang đó.

**Ngoại lệ:**
- Giá ≤ 0 → `400`.
- Gói khác khoang với chỗ đang bán → `400`.
- Đổi giá hoặc rule không ảnh hưởng booking đã tạo, vì booking lưu **snapshot** giá và rule.

- **API:** `/api/admin/fare-families`, `PUT /api/admin/flights/:id/fares`

---

## C. Đặt vé

### UC14 + UC15 – Tạo booking và giữ chỗ tạm thời
- **Actor:** Customer. UC15 (giữ chỗ) không có actor riêng, được UC14 «include»
- **Service:** booking-service (điều phối) + flight-service (tồn chỗ)
- **Tiền điều kiện:** Đã đăng nhập; đã chọn chuyến và gói giá cho chiều đi (và chiều về nếu khứ hồi).

**Luồng chính:**
1. Customer gửi:
   - `segments`: danh sách `[{flightId, fareFamilyCode, direction}]`;
   - `passengers`: mỗi người gồm `type`, `fullName`, `dob`, `gender`, `idNumber`; INF có thêm `accompanyingAdultIndex`;
   - `contact`: `{email, phone}`.
2. Booking-service validate theo quy tắc nghiệp vụ:
   - 1 ≤ ADT, ADT + CHD ≤ 9, INF ≤ ADT;
   - mỗi INF gắn với một ADT khác nhau;
   - tuổi khớp với loại khách: ADT/CHD tính tại ngày bay chặng đi; INF phải từ 7 ngày đến dưới 2 tuổi tại ngày bay của **mỗi** chặng (khứ hồi mà bé tròn 2 tuổi ở chiều về thì báo lỗi, yêu cầu đặt vé CHD);
   - khứ hồi: chặng về cùng tuyến ngược chiều và khởi hành sau chặng đi.
3. Với mỗi chặng, booking-service gọi flight-service `GET /internal/flights/:id/fares/:code` để lấy **snapshot** chuyến bay, giá gói và fare rule.
   - Kiểm tra chuyến ở `SCHEDULED` và còn ≥ 3h trước giờ bay.
4. Booking-service tính tiền cho mỗi chặng: `Σ(giá gói × hệ số khách) + thuế/phí × số khách`, với hệ số ADT 1.0, CHD 0.9, INF 0.1 (Vietnam Airlines, chặng nội địa; đọc từ cấu hình).
5. Booking-service gọi flight-service `POST /internal/inventory/hold` với `{holdRef: bookingId, items: [{flightId, cabin, quantity: ADT+CHD}], ttlMinutes: 15}`.
6. Flight-service giữ chỗ **nguyên tử cho mọi chặng**:
   - Mở transaction, khóa dòng `cabin_inventory` bằng `SELECT ... FOR UPDATE`.
   - Kiểm tra `total - held - sold ≥ quantity`, rồi tăng `held`.
   - Lưu bản ghi hold kèm thời hạn.
   - Chỉ cần một chặng thiếu chỗ là rollback toàn bộ.
7. Booking-service **sinh PNR**: 6 ký tự ngẫu nhiên, không dùng ký tự dễ nhầm 0/O, 1/I (ví dụ `K7XQ2M`). Cột `pnr` là UNIQUE; nếu trùng thì sinh lại (tối đa 5 lần).
8. Booking-service lưu `bookings` (`pnr`, `PENDING_PAYMENT`, `expires_at = now + 15'`), `booking_segments` (kèm snapshot), `passengers` và `passenger_segments` (chưa có ghế).
9. Booking-service publish `booking.created` và trả booking (kèm PNR) về cho FE; FE hiển thị đồng hồ đếm ngược.

**Ngoại lệ:**
- 2a. Vi phạm quy tắc hành khách → `400 INVALID_PASSENGERS`.
- 3a. Chuyến không đặt được → `409 FLIGHT_NOT_BOOKABLE`.
- 3b. Flight-service không phản hồi (timeout 3s, retry 2 lần) → `503 SERVICE_UNAVAILABLE`.
- 6a. Không đủ chỗ → `409 INSUFFICIENT_SEATS` kèm thông tin chặng thiếu chỗ.
- 7a. Lưu booking lỗi → gọi `POST /internal/inventory/release` (bù trừ).

- **Hậu điều kiện:** Chỗ được giữ trong 15 phút; booking có PNR và ở trạng thái `PENDING_PAYMENT`. Số vé **chưa** được sinh (chỉ sinh khi thanh toán xong, UC20).
- **API:** `POST /api/bookings`

### UC31 – Mua dịch vụ bổ trợ (P2)
- **Actor:** Customer
- **Service:** booking-service (+ flight-service lấy danh mục)
- **Tiền điều kiện:** Booking ở `PENDING_PAYMENT`.

**Luồng chính:**
1. FE lấy danh mục dịch vụ: `GET /api/ancillaries?flightId=` trả về các gói hành lý thêm (+10kg, +20kg, +30kg) và suất ăn kèm giá.
2. Customer chọn dịch vụ cho từng hành khách × chặng.
3. Booking-service lấy giá từ flight-service, **không tin giá gửi từ FE**.
4. Booking-service lưu `booking_ancillaries` (thay toàn bộ lựa chọn cũ), rồi tính lại tổng tiền.

**Ngoại lệ:**
- Mã dịch vụ không tồn tại → `400`.
- Mua hành lý cho INF → `400` (INF không có hành lý ký gửi riêng).
- Booking đã thanh toán → `409 BOOKING_NOT_EDITABLE`. Mua thêm sau khi thanh toán nằm ngoài phạm vi.

- **API:** `PUT /api/bookings/:id/ancillaries`

### UC17 – Xem lịch sử và chi tiết booking ("Đặt chỗ của tôi")
- **Actor:** Customer
- **Service:** booking-service

**Luồng chính:**
1. Customer xem danh sách booking: phân trang, lọc theo trạng thái; tách "Sắp bay" và "Đã bay/Đã hủy".
2. Customer xem chi tiết booking:
   - các chặng (snapshot);
   - hành khách, ghế, dịch vụ bổ trợ;
   - tổng tiền chia theo từng phần;
   - trạng thái và e-ticket;
   - các nút hành động hiển thị theo fare rule: Hủy/Hoàn, Đổi chuyến, Check-in.

**Ngoại lệ:** Xem booking của người khác → `404`. Admin xem được tất cả (UC22).

- **API:** `GET /api/bookings/me`, `GET /api/bookings/:id`

### UC32 – Tra cứu đặt chỗ bằng PNR + họ (P2)
- **Actor:** Guest (hành khách không phải người đặt, không có tài khoản)
- **Service:** booking-service

> **Khác UC17 thế nào?**
> - UC17 dành cho **chủ tài khoản**: xem **mọi booking** mình đã đặt.
> - UC32 dành cho **người đi máy bay nhưng không phải người đặt**, ví dụ con được bố mẹ đặt hộ, nhân viên được công ty đặt hộ. Họ chỉ có mã PNR trong email nên tra cứu bằng **PNR + họ**, và chỉ xem được **đúng 1 booking**.
> - Các hãng thật cũng dùng đúng cách này cho "Quản lý đặt chỗ" và check-in online.

**Luồng chính:**
1. Guest nhập PNR và họ (không dấu, không phân biệt hoa thường).
2. Hệ thống tìm booking có PNR đó **và** có ít nhất một hành khách mang họ này.
3. Hệ thống trả về chi tiết booking ở dạng **che bớt thông tin** (số giấy tờ và SĐT chỉ hiện 3 số cuối), kèm e-ticket.
4. Hệ thống cấp `lookupToken` (JWT ngắn hạn, 30 phút, chỉ có quyền trên booking này) để thực hiện check-in (UC21).

**Ngoại lệ:**
- Không khớp PNR hoặc họ → `404 BOOKING_NOT_FOUND`. Không báo trường nào sai để tránh bị dò.
- Tra cứu quá 10 lần/phút/IP → `429`.

- **API:** `POST /api/bookings/lookup`

### UC18 – Hủy booking và hoàn tiền (P2)
- **Actor:** Customer
- **Service:** booking-service + payment-service
- **Tiền điều kiện:** Booking ở `CONFIRMED`, chưa check-in, và chặng đầu tiên chưa khởi hành.

**Luồng chính:**
1. Customer bấm "Hủy vé". Hệ thống **hiển thị trước số tiền sẽ được hoàn** (`GET /api/bookings/:id/refund-quote`).
2. Booking-service tính tiền hoàn cho từng chặng theo **snapshot fare rule**:
   - Hủy trong **24h kể từ lúc mua** và chuyến còn > 24h mới khởi hành → hoàn **100%** tiền vé.
   - Ngoài trường hợp trên:
     - `refundable=false` → hoàn 0;
     - ngược lại → hoàn `giá vé × (1 − refund_fee_pct)`.
   - Thuế/phí sân bay luôn được hoàn. Dịch vụ bổ trợ và phí ghế **không hoàn**.
3. Customer xác nhận hủy. Booking chuyển sang `CANCELLED`, ghi nhận số tiền hoàn và publish `booking.cancelled` với `{refundAmount}`.
4. Xử lý event `booking.cancelled`:
   - Flight trả chỗ và ghế về trạng thái trống (giảm `sold`).
   - Payment tạo `refunds` (gọi VNPay refund sandbox, hoặc ghi nhận `PROCESSED`), rồi publish `payment.refunded`.
5. Booking chuyển sang `REFUNDED`; Notification gửi email xác nhận hoàn tiền.

**Ngoại lệ:**
- Đã check-in hoặc đã bay → `409 BOOKING_NOT_CANCELLABLE`.
- Số tiền hoàn bằng 0 → vẫn cho hủy (nhả chỗ), sau khi FE đã cảnh báo rõ.
- Hoàn tiền VNPay lỗi → refund ở trạng thái `FAILED` để admin xử lý lại thủ công (UC25).

- **API:** `GET /api/bookings/:id/refund-quote`, `POST /api/bookings/:id/cancel`

### UC19 – Tự động hủy booking quá hạn
- **Actor:** Thời gian (Time): cron job chạy mỗi phút
- **Service:** booking-service (+ flight-service)

**Luồng chính:**
1. Cron chạy mỗi phút, tìm các booking `PENDING_PAYMENT` có `expires_at < now`.
2. Với mỗi booking tìm được: chuyển sang `EXPIRED` và publish `booking.expired`.
3. Flight-service nhả mọi hold có `holdRef=bookingId`: giảm `held`, ghế `HELD` trở về AVAILABLE.
4. **Lưới an toàn:** flight-service cũng có job riêng dọn các hold quá hạn, phòng trường hợp mất event.

**Ngoại lệ:** IPN báo thành công **sau khi** booking đã `EXPIRED`:
- Booking **không** được xác nhận lại, vì chỗ đã nhả.
- Booking publish `booking.payment_late`, Payment hoàn 100%.
- Đây là điểm cần giải thích khi bảo vệ.

### UC20 – Xuất vé điện tử
- **Actor:** VNPay (gián tiếp: UC24 nhận IPN thành công rồi «include» UC20)
- **Service:** booking-service

**Luồng chính:**
1. Khi booking chuyển sang `CONFIRMED`, hệ thống sinh (PNR đã có từ lúc tạo booking, UC14):
   - mỗi hành khách × chặng một `ticket_no` 13 chữ số dạng `738-XXXXXXXXXX` (3 số mã hãng + 10 số lấy từ DB sequence, nên không bao giờ trùng);
   - QR code chứa PNR và ticket_no.
2. Publish `booking.confirmed`. Payload gồm PNR, chặng, hành khách, ghế, dịch vụ và contact email.
   - Flight chuyển chỗ/ghế sang `SOLD`.
   - Notification gửi email (UC27).
3. Customer xem e-ticket trên web (P3: tải file PDF).

- **API:** `GET /api/bookings/:id/ticket`

### UC21 – Check-in online (P2)
- **Actor:** Customer, hoặc Guest có `lookupToken` từ UC32
- **Service:** booking-service (+ flight-service gán ghế)
- **Tiền điều kiện:** Booking ở `CONFIRMED`; chặng cần check-in khởi hành trong khoảng **24h đến 1h** tới.

**Luồng chính:**
1. Người dùng chọn chặng và các hành khách cần check-in. INF được check-in cùng người lớn đi kèm.
2. Với hành khách chưa có ghế:
   - Booking-service gọi flight-service `POST /internal/seats/auto-assign`.
   - Ưu tiên xếp ghế STANDARD trống, các khách cùng booking ngồi cạnh nhau nếu có thể.
3. Hệ thống ghi nhận `checked_in_at` và sinh `boarding_pass_no` cùng QR (cổng, giờ lên máy bay = giờ bay − 40 phút).
4. Khi mọi hành khách đã check-in mọi chặng sắp bay, booking chuyển sang `CHECKED_IN`. Publish `booking.checked_in`; Notification gửi boarding pass.

**Ngoại lệ:**
- Ngoài khung giờ → `409 CHECKIN_WINDOW_CLOSED`. FE hiển thị giờ mở check-in.
- Chuyến bị `CANCELLED` → `409`.
- Hết ghế để tự gán (gần như không xảy ra vì đã giữ chỗ) → `409` và báo admin.

- **API:** `POST /api/bookings/:id/check-in`, `GET /api/bookings/:id/boarding-pass`

---

## D. Thanh toán

### UC23 – Thanh toán qua VNPay
- **Actor:** Customer
- **Service:** payment-service (+ booking-service)
- **Tiền điều kiện:** Booking ở `PENDING_PAYMENT` và chưa hết hạn.

**Luồng chính:**
1. FE gọi `POST /api/payments/vnpay` với `{bookingId}`.
2. Payment-service gọi booking-service `GET /internal/bookings/:id` để kiểm tra:
   - đúng chủ booking;
   - đúng trạng thái và chưa hết hạn;
   - lấy `total_amount` (vé + ghế + dịch vụ). **Không tin số tiền gửi từ FE.**
3. Payment-service tạo `payments` với `status=PENDING`, `purpose=BOOKING` và `vnp_txn_ref` duy nhất.
4. Payment-service ký HMAC-SHA512 và tạo URL thanh toán.
   - `vnp_ExpireDate` = `expires_at` của booking.
   - `vnp_Amount` = số tiền × 100.
5. FE redirect người dùng sang VNPay sandbox để thanh toán (thẻ test NCB).

**Ngoại lệ:**
- Booking hết hạn hoặc đã thanh toán → `409 BOOKING_NOT_PAYABLE`.
- Đã có payment `PENDING` cùng số tiền → trả lại URL cũ (idempotent).
- Tổng tiền đã đổi do chọn thêm ghế/dịch vụ → hủy payment cũ, tạo payment mới.

- **API:** `POST /api/payments/vnpay`

### UC24 – Nhận kết quả thanh toán từ VNPay
- **Actor:** VNPay
- **Service:** payment-service

**Luồng chính (IPN, server-to-server qua URL public của ngrok):**
1. VNPay gọi `GET /api/payments/vnpay/ipn?...&vnp_SecureHash=...`.
2. Payment-service verify chữ ký, tìm payment theo `vnp_TxnRef` và kiểm tra số tiền khớp.
3. Nếu payment đang `PENDING`:
   - cập nhật `SUCCESS` (khi `vnp_ResponseCode=00`) hoặc `FAILED`;
   - lưu `vnp_TransactionNo` và `paid_at`.
4. Publish `payment.succeeded` hoặc `payment.failed`.
5. Trả `{RspCode: "00", Message: "Confirm Success"}`.
6. Booking-service xử lý `payment.succeeded`: chuyển `CONFIRMED`, rồi thực hiện UC20.

**Return URL:** VNPay redirect người dùng về FE `/payment/result`. FE gọi `GET /api/payments/vnpay/return`, nhưng **chỉ để hiển thị**. Trạng thái chính thức luôn lấy từ IPN.

**Ngoại lệ (mã trả về theo chuẩn VNPay):**

| Tình huống | Mã trả về |
|---|---|
| Sai chữ ký | `97` |
| Không tìm thấy giao dịch | `01` |
| Sai số tiền | `04` |
| Giao dịch đã xử lý trước đó (**idempotent**, không publish lại) | `02` |

---

## E. Thông báo

### UC27 – Email xác nhận đặt vé
- **Actor:** VNPay (gián tiếp: UC20 «include» UC27 sau khi xuất vé)
- **Service:** notification-service

**Luồng chính:**
1. Consume event `booking.confirmed`.
2. Render template gồm: PNR, các chặng, hành khách, ghế, hành lý theo gói và hành lý mua thêm, tổng tiền, QR.
3. Gửi đến **contact email** của booking qua **Gmail SMTP thật** (Nodemailer + App Password của Gmail). Không dùng Mailpit/Mailtrap để giả lập; email phải đến được hộp thư thật.
4. Ghi `notification_logs`.

**Ngoại lệ:**
- Gửi lỗi → retry 3 lần (requeue có delay), vẫn lỗi thì đưa vào DLQ và ghi `FAILED`.
- Event trùng (cùng `bookingId` và loại email) → bỏ qua (idempotent).

---

## Ma trận Use Case – Service – Event
| UC | Service chính | Gọi đồng bộ | Event phát ra |
|---|---|---|---|
| UC01–03 | auth | – | – |
| UC07, 09 | flight | – | – |
| UC10 | booking | booking → flight (giữ ghế) | – |
| UC11–13 | flight | – | `flight.status_changed` |
| UC14–15 | booking | booking → flight (snapshot, giữ chỗ) | `booking.created` |
| UC31 | booking | booking → flight (giá dịch vụ) | – |
| UC17, 32 | booking | – | – |
| UC18 | booking | – | `booking.cancelled` → `payment.refunded` |
| UC19 | booking | – | `booking.expired` |
| UC20 | booking | – | `booking.confirmed` |
| UC21 | booking | booking → flight (tự gán ghế) | `booking.checked_in` |
| UC23 | payment | payment → booking (kiểm tra) | – |
| UC24 | payment | – | `payment.succeeded` / `payment.failed` |
| UC27 | notification | – | – (chỉ consume) |
