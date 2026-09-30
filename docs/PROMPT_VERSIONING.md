# Prompt versioning cơ bản

Mục tiêu của phần này là biết một request đã dùng prompt nào và có thể rollback an toàn. Đây không phải bài tối ưu prompt hoặc A/B testing.

## Prompt contract

Trong project Langfuse cá nhân `day13-k4-l3b-<MSSV>`, tạo text prompt tên `day13-chat`. Prompt phải giữ ba biến:

```text
Feature={{feature}}
Docs={{docs}}
Question={{message}}
```

App lấy prompt theo hai biến môi trường:

```dotenv
LANGFUSE_PROMPT_NAME=day13-chat
LANGFUSE_PROMPT_LABEL=production
```

Nếu Langfuse không khả dụng, app dùng template local và trace metadata ghi `prompt_source=local` hoặc `local-fallback` thay vì giả vờ đã lấy được prompt managed.

## Thao tác trên Langfuse UI

Tên menu/nút trên Langfuse có thể thay đổi nhẹ theo phiên bản, nhưng luồng thao tác cần giữ như sau:

1. Mở đúng project cá nhân `day13-k4-l3b-<MSSV>`.
2. Vào khu vực quản lý prompt/prompt management.
3. Tạo text prompt tên `day13-chat` với đủ ba biến `{{feature}}`, `{{docs}}`, `{{message}}`.
4. Lưu version đầu tiên và gắn labels `baseline` + `production`.
5. Tạo một version mới từ prompt đó, chỉnh nhẹ format hoặc độ dài câu trả lời, rồi gắn label `candidate`.
6. Chạy workload với label tương ứng trong `.env`, sau đó mở trace để kiểm tra metadata `prompt_name`, `prompt_label`, `prompt_version`.
7. Để promote, chuyển label `production` sang version mới. Để rollback, chuyển label `production` quay lại version cũ.

Điểm quan trọng: app không cần sửa code khi đổi version. Code chỉ hỏi Langfuse theo `LANGFUSE_PROMPT_NAME` và `LANGFUSE_PROMPT_LABEL`; label `production` đang trỏ tới version nào thì Langfuse quyết định.

## Việc cần làm

1. Tạo version 1, gắn labels `baseline` và `production`.
2. Tạo version 2 với một thay đổi nhỏ về format hoặc độ dài câu trả lời, gắn label `candidate`.
3. Chạy cùng một input với `LANGFUSE_PROMPT_LABEL=baseline` và `candidate`.
4. Mở hai trace, kiểm tra `prompt_name`, `prompt_label`, `prompt_version` và prompt link.
5. Chuyển label `production` sang version 2, chạy lại một request.
6. Rollback `production` về version 1 và lưu ảnh evidence.

Không chấm prompt nào “hay hơn”. Điểm nằm ở khả năng truy xuất version, đổi label và rollback có bằng chứng.

## Cách chạy workload và kiểm tra an toàn bằng script

Sau mỗi lần đổi `LANGFUSE_PROMPT_LABEL`, restart API để bỏ cache prompt khoảng 60 giây. Từ root repository:

```powershell
python scripts/load_test.py --concurrency 5
python scripts/verify_langfuse.py --hours 2 --limit 1000
```

`verify_langfuse.py` chỉ in trace/observation ID, cây cha-con, metadata prompt/correlation ID và model/usage/cost; script không in raw input/output, API key hoặc secret. Dùng output này để đối chiếu nhanh trước khi mở UI và chụp ảnh `06`–`10`.

### Checklist chụp ảnh evidence

1. **Trace list (`06-trace-list.png`):** mở project cá nhân `day13-k4-l3b-<MSSV>` → Traces, chọn khoảng thời gian vừa chạy; chụp ít nhất 10 trace và tên project.
2. **Waterfall (`07-trace-waterfall.png`):** mở một trace có correlation ID trong log, bấm `lab-agent-run`; cây phải có `retrieval` và `generation`. Không mở phần Input/Output raw.
3. **Metadata (`08-trace-metadata.png`):** tại root `lab-agent-run`, mở Metadata; chỉ chụp `correlation_id`, `prompt_name`, `prompt_label`, `prompt_version`, `prompt_source`, model; che mọi key/PII nếu xuất hiện.
4. **Prompt versions (`09-prompt-versions.png`):** mở Prompt Management → `day13-chat`, chụp v1/v2 và labels `baseline`, `candidate`, `production`.
5. **Promote/rollback (`10-prompt-rollback.png`):** chụp hai trạng thái label `production`: sau promote trỏ v2 và sau rollback trỏ v1. Evidence phải thuộc project cá nhân, không chụp trang API Keys.

Nếu `prompt_source=local-fallback`, không chụp như evidence managed prompt; kiểm tra project/region/key/name/label, restart API và chạy lại.

## Evidence

- Một ảnh danh sách hai prompt version.
- Hai trace ID chứng minh hai version/label khác nhau.
- Một ảnh trước/sau khi đổi label hoặc rollback `production`.
- Ghi các ID và đường dẫn ảnh vào `submission/REPORT.md`.
