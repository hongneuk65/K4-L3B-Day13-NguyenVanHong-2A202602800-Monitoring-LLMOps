# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `response_sent.latency_ms` P95 và SLO fast_successful_requests.
- Điều kiện và thời gian duy trì: P95 latency > 3000 ms liên tục 5 phút.
- Ảnh hưởng tới người dùng: câu trả lời đến chậm, có thể vượt SLO.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** mở panel Latency, so sánh P50/P95/P99 và TTFT trong đúng cửa sổ 5 phút.
  2. **Logs:** lọc `response_sent` theo cửa sổ, chọn correlation ID có latency cao nhất; kiểm tra `tool_success`, token và prompt metadata an toàn.
  3. **Traces:** mở trace cùng correlation ID, so sánh thời gian child `retrieval` và `generation` để xác định bước chậm.
- Mitigation tạm thời: tắt practice scenario nếu đang bật; nếu generation tăng, rollback production prompt về version đã kiểm chứng; nếu retrieval tăng, giảm tải hoặc khôi phục cấu hình retriever. Ghi lại thay đổi và theo dõi P95 sau mitigation.
- Owner: `student-2A202602800`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: tỷ lệ `request_failed / request_received` và error budget 0.5%.
- Điều kiện và thời gian duy trì: error rate > 2% liên tục 5 phút.
- Ảnh hưởng tới người dùng: request trả HTTP 500 hoặc không có câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** mở panel Errors, xác nhận error rate, số request và error type theo thời gian.
  2. **Logs:** lọc `request_failed`, đọc `error_type` và lấy correlation ID; không dùng payload thô để điều tra.
  3. **Traces:** tìm trace cùng correlation ID; xem root status và child span nào có level ERROR hoặc status message lỗi.
- Mitigation tạm thời: tắt scenario gây lỗi, giảm concurrency, khôi phục prompt/configuration gần nhất đã ổn định; nếu lỗi retrieval diện rộng, chuyển sang fallback local và thông báo owner trước khi retry workload.
- Owner: `student-2A202602800`

## Alert 3

- Tên: `LowRetrievalSuccess`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: retrieval success rate guardrail tối thiểu 90%.
- Điều kiện và thời gian duy trì: `tool_success == true` dưới 90% trên mọi event có `tool_success` trong 10 phút.
- Ảnh hưởng tới người dùng: câu trả lời thiếu context hoặc nhiều request thất bại trước khi generation.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** mở panel Errors, kiểm tra retrieval success cùng error rate và khoảng thời gian giảm.
  2. **Logs:** lọc các record `tool_success=false`, nhóm theo `error_type`/`tool_name`, lấy một correlation ID đại diện.
  3. **Traces:** mở trace cùng correlation ID, kiểm tra child `retrieval` status, duration và lỗi timeout; xác nhận generation không bị nhầm là nguyên nhân.
- Mitigation tạm thời: khôi phục retriever/config đã biết tốt, giảm concurrency hoặc dùng local fallback; sau đó chạy một workload nhỏ và chỉ đóng alert khi success rate vượt 90% đủ 10 phút.
- Owner: `student-2A202602800`
