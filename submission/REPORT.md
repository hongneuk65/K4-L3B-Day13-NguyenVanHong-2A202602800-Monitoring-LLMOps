# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Văn Hồng
- **MSSV:** 2A202602800
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/hongneuk65/K4-L3B-Day13-NguyenVanHong-2A202602800-Monitoring-LLMOps
- **Commit SHA CP4 cơ sở (source và evidence):** `d4d31d0`; commit cuối chứa bản cập nhật metadata của báo cáo được tạo ngay sau đó.
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602800`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| 01 — Pytest cuối | [01-pytest.png](evidence/01-pytest.png) |
| 02 — Log validator | [02-log-validator.png](evidence/02-log-validator.png) |
| 03 — Dashboard validator | [03-dashboard-validator.png](evidence/03-dashboard-validator.png) |
| 04 — Structured log | [04-structured-log.png](evidence/04-structured-log.png) |
| 05 — PII redaction | [05-pii-redaction.png](evidence/05-pii-redaction.png) |
| 06 — Trace list | [06-trace-list.png](evidence/06-trace-list.png) |
| 07 — Trace waterfall | [07-trace-waterfall.png](evidence/07-trace-waterfall.png) |
| 08 — Trace metadata và generation | [08a-trace-metadata.png](evidence/08a-trace-metadata.png), [08b-generation.png](evidence/08b-generation.png) |
| 09 — Prompt versions | [09-prompt-versions.png](evidence/09-prompt-versions.png) |
| 10 — Prompt promote/rollback | [10a-prompt-promote.png](evidence/10a-prompt-promote.png), [10b-prompt-rollback.png](evidence/10b-prompt-rollback.png) |
| 11 — Dashboard overview | [11-dashboard-overview.png](evidence/11-dashboard-overview.png) |
| 12 — Incident metric | [12-incident-metric.png](evidence/12-incident-metric.png) |
| 13 — Incident log | [13-incident-log.png](evidence/13-incident-log.png) |
| 14 — Incident trace | [14-incident-trace.png](evidence/14-incident-trace.png) |
| Supporting text — prompt runtime/labels | [cp2-prompt-runtime.txt](evidence/cp2-prompt-runtime.txt), [cp2-prompt-labels.txt](evidence/cp2-prompt-labels.txt) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Workload sạch cuối có 21 records, 10 correlation IDs, không thiếu field và không có PII leak. |
| `validate_dashboard.py` | 6/6 panel contract | 6/6 panel contract | Contract dashboard vẫn hợp lệ. |
| `pytest` | 22 passed | 24 passed | Bao gồm test CCCD và số thẻ. |
| Số traces hợp lệ | 0 | 39 complete trees đã xác nhận bằng `scripts/verify_langfuse.py --hours 2 --limit 1000` | Kết quả verifier là `observations=117`, `traces=39`, `root_traces=39`, `complete_trees=39`; mỗi cây có root `lab-agent-run`, child `retrieval` và `generation`. |
| Số PII leak | 0 | 0 | Validator độc lập không phát hiện PII thô trong log. |
| Latency P50 / P95 / P99 / TTFT P95 | — | 151 / 175 / 175 / 50 ms | Tính trên workload sạch cuối: 10 response trong `data/logs.jsonl`; CP1 baseline trước đó là P95 1357 ms. |
| Retrieval success rate | — | 100% | Workload sạch cuối có 10/10 response với `tool_success=true`; retrieval success tính trên mọi event có boolean `tool_success`. |
| Quality average / cost total | — | 0.8800 / 0.016959 USD | Tính trên 10 response workload sạch cuối. |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** middleware xoá context cũ ở đầu request, nhận `x-request-id` hợp lệ dạng `req-` + 8 ký tự hex hoặc sinh ID mới, bind vào structlog contextvars, truyền vào agent/trace, response body và trả lại qua `x-request-id`.
- **Các metadata được ghi vào structured log:** `user_id_hash`, `session_id`, `feature`, `model`, `env`, correlation ID; response thêm latency, TTFT, token, cost, quality, retrieval success.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` duyệt đệ quy string/dict/list/tuple và chạy trước `JsonlFileProcessor` và JSON renderer; preview request/response cũng được scrub từ trước.
- **Cách kiểm chứng kết quả:** workload sạch cuối chạy `python scripts/validate_logs.py` đạt 100/100 với 10 correlation ID hợp lệ, không thiếu required/enrichment field, không phát hiện PII. Runtime response đã kiểm tra `x-request-id` khớp `response.correlation_id` và `x-response-time-ms`; baseline trước đó có 24 correlation ID và được lưu ngoài repo trước lần đo cuối.

## 5. Tracing và prompt versioning

- **Trạng thái runtime:** Đã hoàn tất phần source và runtime CP2. `@observe` tạo child `retrieval` loại `RETRIEVER` và `generation` loại `GENERATION`; cả hai cùng nằm dưới `lab-agent-run`. `scripts/verify_langfuse.py --hours 2 --limit 1000` xác nhận 39 complete trees trong project cá nhân, vượt yêu cầu tối thiểu 10 trace.
- **Bảo vệ dữ liệu:** root và child decorator đều `capture_input=False, capture_output=False`; observation API trả `input=null`, `output=null` cho generation. Generation vẫn có `model`, `usage_details`, `cost_details` và prompt object managed.
- **Cách nối trace với log:** `correlation_id` xuất hiện trong metadata của root/child. Một số trace runtime tiêu biểu: `req-4a5b6c7d` → trace `19daa409296c9a4a1192d501b8b0f40b` (baseline v1), `req-5b6c7d8e` → trace `151c67c23183cf2a992629255d1e4fa8` (candidate v2), `req-6c7d8e9f` → trace `ee73ce30dbe57411bc55e5c642a549dd` (production v2), `req-7d8e9fab` → trace `70b916fc47bc99c1525177e3da5209de` (rollback v1). Chi tiết child IDs/model/token/cost nằm trong `evidence/cp2-prompt-runtime.txt`.
- **Prompt versioning:** prompt text `day13-chat` được tạo với đúng `{{feature}}`, `{{docs}}`, `{{message}}`; v1 có `baseline` + `production`, v2 có `candidate` (Langfuse tự thêm `latest`). Runtime xác nhận baseline v1 input 38 tokens, candidate v2 input 44 tokens, promote production v2 input 44 tokens, rollback production v1 input 38 tokens. Trạng thái cuối production trỏ v1; không sửa code khi đổi label.
- **Evidence đã lưu:** các ảnh Langfuse `06`–`10` và `14` đã được lưu trong `submission/evidence/`; output text `cp2-prompt-runtime.txt` và `cp2-prompt-labels.txt` là bản đối chiếu an toàn, không chứa raw input/output hay secret.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `config/dashboard.yaml` giữ đúng 6 panel, time range 60 phút, refresh 30 giây và threshold. `scripts/dashboard.py` đọc `data/logs.jsonl`, render HTML/SVG không thêm plotting dependency; ảnh runtime là `evidence/11-dashboard-overview.png`.
- **SLO và lý do chọn:** cấu hình hiện tại đặt 99.5% request thành công và latency không quá 3000 ms trong cửa sổ 28 ngày.
- **Cách tính error budget:** 100% - 99.5% = 0.5%; với 10.000 request tương ứng tối đa 50 request không đạt. Cấu hình ghi rõ `error_budget_requests_per_10000: 50`; baseline CP1 có P95 latency 1357 ms, thấp hơn ngưỡng 3000 ms.
- **Ba alert và runbook tương ứng:** đã hoàn thiện `HighLatencyP95`, `HighErrorRate`, `LowRetrievalSuccess` trong `config/alert_rules.yaml`; mỗi alert có condition, duration, severity, owner, Slack channel và link tới `docs/alerts.md`. Runbook giữ thứ tự Metrics → Logs → Traces và mitigation.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (cohort `K4`, incident `rag_slow`, threshold `2000 ms`).
- **Khoảng thời gian điều tra:** `2026-09-30 07:28:45–07:28:59 UTC`. Baseline chạy ngay trước challenge có P50/P95/P99 lần lượt `152/153/153 ms`, TTFT P95 `50 ms`, error rate `0.00%` và retrieval success `100.0%`.
- **Triệu chứng từ metrics:** Panel latency bất thường: trong challenge P50/P95/P99 là `152/2653/2653 ms`; P95 tăng từ `153 ms` lên `2653 ms` và vượt threshold `2000 ms`. Năm request challenge có `latency_ms` từ `2651` đến `2653 ms`. Error rate vẫn `0.00%`, retrieval success `100.0%`, TTFT P95 vẫn `50 ms`, nên triệu chứng là tail latency chứ không phải lỗi request hoặc generation.
- **Log line và correlation ID liên quan:** `data/logs.jsonl:27`, event `response_sent`, `ts=2026-09-30T07:28:48.766489Z`, `correlation_id=req-1e44110c`, `latency_ms=2652`, `tool_name=retrieval`, `tool_success=true`. Request tương ứng nằm ở line `26`; log ghi `session_id=k4-l3b-challenge-s05` và `feature=monitoring`, không ghi PII thô.
- **Trace ID và span gây ảnh hưởng:** Trace `a9adbc067713479a0e3d37c84fdfc521` có metadata cùng `correlation_id=req-1e44110c`. Root `lab-agent-run` (`9b03fee01b47af58`) kéo dài `2652 ms`; child `retrieval` (`13c05f5cf4ade1fc`) kéo dài `2501 ms`; child `generation` (`282da5cdbea1dc4f`) chỉ kéo dài `151 ms`. Các span ở trạng thái mặc định, không có status error.
- **Root cause:** Incident chính thức `rag_slow` làm chậm bước `retrieval` khoảng `2.5 s`. Ba tín hiệu thống nhất: latency tail vượt threshold, log vẫn có `tool_success=true` với `tool_name=retrieval`, và trace cho thấy gần như toàn bộ thời gian nằm ở span `retrieval` (`2501/2652 ms`), không nằm ở `generation`.
- **Fix action:** Tắt incident sau điều tra bằng `python scripts/inject_incident.py --scenario rag_slow --disable`; `/health` sau đó xác nhận `rag_slow=false`, `tool_fail=false`, `cost_spike=false`. Khi triển khai thực tế, khôi phục cấu hình retriever đã biết tốt và theo dõi lại P95 sau mitigation.
- **Preventive measure:** Giữ alert `HighLatencyP95` với runbook Metrics → Logs → Traces; theo dõi riêng duration của span `retrieval`, đặt timeout/fallback cho retriever và kiểm tra retrieval success cùng latency trong canary/load test trước khi promote thay đổi. Chỉ đóng alert sau khi P95 trở về dưới threshold và workload xác nhận lại bằng correlation ID/trace tương ứng.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** dùng `@observe` trực tiếp trên retrieval/generation theo public test và SDK v4; generation cập nhật usage/cost/prompt object sau khi FakeLLM trả response, còn raw input/output bị tắt để tránh PII.
- **Một lỗi/blocker đã gặp:** Langfuse Cloud project mới trả lỗi legacy trace API 410; chuyển sang Observations API v2 với field groups `core,basic,metadata,model,usage,prompt,metrics,trace_context`. Ngoài ra phải restart API sau mỗi lần đổi label vì prompt cache 60 giây.
- **Cách tìm nguyên nhân và xử lý:** dùng `scripts/verify_langfuse.py` để đối chiếu parent/child, correlation ID và prompt metadata; không dùng raw I/O.
- **Cách hiểu luồng Metrics → Logs → Traces:** dashboard khoanh vùng panel/thời gian; log chọn request qua correlation ID; trace xác định retrieval hay generation và kiểm tra model/token/cost.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** prompt label cho phép promote/rollback không sửa code; input token tăng từ 38 lên 44 ở v2 được nhìn thấy trong generation; cost/usage hỗ trợ phát hiện tăng bất thường; SLO 99.5% giới hạn error budget 0.5%.
- **Điều quan trọng nhất đã học:** evidence phải nối được cùng một request xuyên Metrics → Logs → Traces và phải phân biệt local-fallback với managed prompt.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Langfuse UI không hiển thị raw input/output theo chủ ý (`capture_input=False`, `capture_output=False`); vì vậy evidence chỉ dùng metadata, timing, model, usage, cost và prompt version. API key không nằm trong repository; nếu key từng được in ở môi trường thao tác thì cần rotate trước khi nộp.

## 9. Checklist trước khi nộp

- [x] Kết quả CP0/CP1 và evidence hiện có thuộc commit cuối.
- [x] Evidence CP0/CP1 hiện có dùng đường dẫn tương đối và mở được.
- [x] Incident evidence nối đúng metric → log → trace cho challenge `day13-k4-l3b-monitoring-llmops-v1`.
- [x] Ảnh UI metadata/prompt `08`–`10` thuộc project Langfuse cá nhân; trace list `06`, waterfall `07`, metadata/generation `08`, prompt versions `09` và promote/rollback `10` đều có file trong `submission/evidence/`.
- [x] Source CP2 có root/child trace, prompt v1/v2, promote/rollback và dashboard runtime.
- [x] Repository chạy lại được theo README; pytest và các validator đều đạt.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác trong commit.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs (thao tác nộp ngoài repository).
