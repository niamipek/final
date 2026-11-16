# Tiêu chí đánh giá bài Final (Kiến trúc Microservices)

Tổng điểm: **10**

| # | Tiêu chí | Nội dung đánh giá | Điểm tối đa |
|---|----------|-------------------|:-----------:|
| 1 | **Phân tích và thiết kế hệ thống** | Xác định yêu cầu và xây dựng Use Case phù hợp; thiết kế cơ sở dữ liệu (ERD, bảng, quan hệ) hợp lý, nhất quán với nghiệp vụ và kiến trúc hệ thống. | 1.5 |
| 2 | **Kiến trúc Microservices** | Phân chia các service hợp lý; xác định rõ trách nhiệm, kiến trúc tổng thể và cách giao tiếp giữa các service. | 1.5 |
| 3 | **Chức năng và nghiệp vụ** | Hiện thực đầy đủ các chức năng theo yêu cầu; xử lý nghiệp vụ chính xác; các service hoạt động và phối hợp đúng. | 1.5 |
| 4 | **Giao tiếp và tích hợp dịch vụ** | Triển khai REST API; giao tiếp giữa các service; tích hợp dịch vụ bên ngoài (nếu có); xử lý lỗi phù hợp. | 1.0 |
| 5 | **Quản lý dữ liệu và bảo mật** | Quản lý dữ liệu phù hợp với kiến trúc Microservices; có cơ chế xác thực, phân quyền và bảo vệ API theo yêu cầu. | 1.0 |
| 6 | **Đóng gói và triển khai** | Sử dụng Docker và Docker Compose để đóng gói, cấu hình và triển khai các service; hệ thống khởi chạy ổn định và có thể truy cập từ Internet thông qua ngrok hoặc giải pháp tương đương. | 1.0 |
| 7 | **Giám sát hệ thống** | Tích hợp Prometheus để thu thập metrics; xây dựng Grafana Dashboard để giám sát hoạt động của các service. | 1.0 |
| 8 | **Kiểm thử và chất lượng mã nguồn** | Kiểm thử API/chức năng; xử lý lỗi; mã nguồn có cấu trúc rõ ràng, dễ đọc và bảo trì. | 0.5 |
| 9 | **Báo cáo, Demo và Hỏi đáp** | Tài liệu đầy đủ; demo hệ thống hoạt động; giải thích được thiết kế, kiến trúc và kỹ thuật triển khai; trả lời câu hỏi. | 1.0 |
|   | **TỔNG ĐIỂM** | | **10** |

## Checklist sản phẩm cần có (suy ra từ tiêu chí)

- [ ] Tài liệu Use Case (sơ đồ + đặc tả)
- [ ] ERD + thiết kế bảng, quan hệ (mỗi service một database riêng — *database per service*)
- [ ] Sơ đồ kiến trúc tổng thể: danh sách service, trách nhiệm từng service, API Gateway, cách giao tiếp (REST đồng bộ / message bất đồng bộ)
- [ ] REST API cho từng service, có xử lý lỗi thống nhất (mã HTTP, format lỗi)
- [ ] Giao tiếp service-to-service; tích hợp dịch vụ bên ngoài nếu có (thanh toán, email, ...)
- [ ] Xác thực (JWT/OAuth2), phân quyền theo vai trò, bảo vệ API (qua Gateway)
- [ ] `Dockerfile` cho mỗi service + `docker-compose.yml` khởi chạy toàn bộ hệ thống
- [ ] Public hệ thống ra Internet qua ngrok (hoặc tương đương)
- [ ] Mỗi service expose metrics cho Prometheus; Grafana dashboard giám sát các service
- [ ] Kiểm thử API (unit test / Postman collection / integration test)
- [ ] Mã nguồn cấu trúc rõ ràng, dễ đọc, dễ bảo trì
- [ ] Báo cáo đầy đủ + chuẩn bị demo và trả lời câu hỏi về thiết kế, kiến trúc, triển khai
