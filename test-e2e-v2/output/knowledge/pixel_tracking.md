# Pixel Tracking Knowledge File

## Nền tảng Pixel Tracking

### Facebook Pixel tracks key ecommerce events with proper parameters

**ID:** atom_0007

**Nội dung:**
Facebook Pixel là một mã JavaScript được cài đặt trên trang web của bạn để theo dõi các hành động của người dùng: PageView, ViewContent, AddToCart, InitiateCheckout, và Purchase. Mỗi sự kiện phải bao gồm các tham số chính xác để đảm bảo theo dõi chính xác và tối ưu hóa. Triển khai pixel đúng cách là rất cần thiết để theo dõi chuyển đổi và xây dựng đối tượng.

**Tags:** facebook pixel, event tracking, conversion

**Confidence Score:** 0.95

**Status:** Unverified

---

### Attribution window default is 7-day click and 1-day view for conversion credit

**ID:** atom_0022

**Nội dung:**
Cửa sổ thuộc tính mặc định của Facebook ghi nhận các chuyển đổi nếu chúng xảy ra trong vòng 7 ngày sau một lần nhấp hoặc 1 ngày sau một lần xem. Cửa sổ này xác định những tương tác nào nhận được công nhân cho các chuyển đổi. Hiểu rõ cửa sổ thuộc tính của bạn là rất cần thiết để tính toán ROI chính xác và đánh giá chiến dịch.

**Tags:** attribution, conversion window, measurement

**Confidence Score:** 0.95

**Status:** Verified

---

### Event Match Quality score above 6.0 improves conversion tracking accuracy

**ID:** atom_0009

**Nội dung:**
Event Match Quality (EMQ) đo lường mức độ tốt mà Facebook có thể khớp các sự kiện chuyển đổi với các hồ sơ người dùng. Nhắm đến điểm EMQ trên 6.0. Cải thiện EMQ bằng cách gửi dữ liệu người dùng bổ sung thông qua CAPI: email, số điện thoại, tên, họ, thành phố, tiểu bang và mã ZIP. Điểm EMQ cao hơn dẫn đến tối ưu hóa chiến dịch tốt hơn.

**Tags:** event match quality, user data, optimization

**Confidence Score:** 0.95

**Status:** Verified

---

## Theo dõi phía máy chủ và API

### Conversions API is the primary tool for tracking conversions

**ID:** atom_0033

**Nội dung:**
Conversions API là một phần của bộ Marketing và Commerce của Meta, cho phép các nhà phát triển gửi dữ liệu chuyển đổi từ máy chủ của họ trực tiếp đến Meta. Đây là một trong những công cụ chính để tối ưu hóa quảng cáo và theo dõi hiệu suất chiến dịch. API hoạt động cùng với Meta Pixel để cung cấp dữ liệu chuyển đổi toàn diện. Nó cho phép theo dõi phía máy chủ của các sự kiện thương mại điện tử chính với các tham số thích hợp để theo dõi và tối ưu hóa chính xác.

**Tags:** Conversions API, tracking, conversion data, server-side, CAPI

**Confidence Score:** 0.9

**Status:** Unverified

---

### Conversions API provides server-side tracking to overcome iOS tracking limitations

**ID:** atom_0008

**Nội dung:**
Conversions API (CAPI) là một giải pháp theo dõi phía máy chủ trở nên quan trọng vì iOS 14.5 hạn chế theo dõi cấp trình duyệt. Triển khai CAPI cùng với Pixel trong cấu hình Redundant Setup và khử trùng sự kiện bằng event_id. Cách tiếp cận theo dõi kép này đảm bảo bạn nắm bắt dữ liệu chuyển đổi mà theo dõi trình duyệt có thể bỏ lỡ.

**Tags:** CAPI, server-side tracking, iOS compliance

**Confidence Score:** 0.95

**Status:** Unverified

---

### Conversions API Gateway enhances conversion data management capabilities

**ID:** atom_0034

**Nội dung:**
Conversions API Gateway là một thành phần bổ sung trong hệ thống Conversions API của Meta giúp quản lý và xử lý dữ liệu chuyển đổi hiệu quả hơn. Nó cung cấp các tính năng nâng cao để gửi và xác nhận dữ liệu chuyển đổi từ nhiều nguồn.

**Tags:** Conversions API Gateway, data management, conversion tracking

**Confidence Score:** 0.8

**Status:** Verified

---