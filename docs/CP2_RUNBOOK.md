# CP2 — Lệnh chạy và checklist chụp evidence

Các lệnh dưới đây chạy từ root repository trên PowerShell. Không đưa `.env`, API key, raw prompt, raw answer hoặc PII vào ảnh/evidence.

## 1. Kiểm tra source và contract

```powershell
python -m pytest -q
python scripts/validate_logs.py
python scripts/validate_dashboard.py
python -m py_compile app/agent.py app/mock_rag.py app/mock_llm.py scripts/dashboard.py scripts/verify_langfuse.py
git diff --check
```

Kỳ vọng hiện tại: pytest `24 passed`, log validator `100/100`, dashboard validator `HỢP LỆ: 6/6 panel`.

## 2. Tạo trace runtime

Terminal 1 — API:

```powershell
uvicorn app.main:app --reload --env-file .env
```

Terminal 2 — workload:

```powershell
python scripts/load_test.py --concurrency 5
```

Đợi ít nhất 5–10 giây sau request cuối trước khi dừng/restart API để Langfuse background worker flush dữ liệu. Kiểm tra cây và metadata an toàn:

```powershell
python scripts/verify_langfuse.py --hours 2 --limit 1000
```

Kỳ vọng mỗi trace hợp lệ có:

```text
lab-agent-run
├── retrieval (RETRIEVER)
└── generation (GENERATION)
```

`generation` phải có model, input/output/total tokens, cost và prompt name/version. Script không in input/output raw.

## 3. Chạy dashboard và chụp ảnh

Giữ API chạy, mở Terminal 3:

```powershell
python scripts/dashboard.py --host 127.0.0.1 --port 8501
```

Mở <http://127.0.0.1:8501/>. Trang đọc `data/logs.jsonl`, tự refresh 30 giây và hiển thị cửa sổ 60 phút UTC. Chạy workload trước khi chụp nếu log sạch chưa có đủ điểm:

```powershell
python scripts/load_test.py --concurrency 5
```

Dùng Snipping Tool hoặc `Win+Shift+S`, chụp đủ sáu panel `Latency`, `Traffic`, `Errors`, `Cost`, `Tokens`, `Quality`; phải nhìn thấy unit và đường threshold. Lưu thành:

```text
submission/evidence/11-dashboard-overview.png
```

## 4. Prompt versioning trên Langfuse

Tạo **text prompt** `day13-chat` với chính xác ba biến:

```text
Feature={{feature}}
Docs={{docs}}
Question={{message}}
```

Tạo v1, gắn `baseline` + `production`; tạo v2 với thay đổi nhỏ (ví dụ thêm `Please answer briefly.`), gắn `candidate`. Mỗi lần đổi label phải restart API vì app cache prompt 60 giây.

PowerShell:

```powershell
# Trước mỗi label: sửa LANGFUSE_PROMPT_LABEL trong .env rồi restart API
$env:LANGFUSE_PROMPT_LABEL = 'baseline'
python scripts/load_test.py --concurrency 1

$env:LANGFUSE_PROMPT_LABEL = 'candidate'
python scripts/load_test.py --concurrency 1

# Trên UI: dời production sang v2, restart, chạy 1 request.
# Sau đó dời production về v1, restart, chạy 1 request.
$env:LANGFUSE_PROMPT_LABEL = 'production'
python scripts/verify_langfuse.py --hours 2 --limit 1000
```

## 5. Danh sách ảnh Langfuse cần chụp

Mở đúng project cá nhân `day13-k4-l3b-<MSSV>`; không mở trang API Keys:

| File | Màn hình cần thấy |
|---|---|
| `06-trace-list.png` | Ít nhất 10 trace trong khoảng thời gian vừa chạy và tên project |
| `07-trace-waterfall.png` | Một trace có root `lab-agent-run`, child `retrieval` và `generation` |
| `08-trace-metadata.png` | `correlation_id`, `prompt_name`, `prompt_label`, `prompt_version`; không chụp Input/Output raw |
| `09-prompt-versions.png` | `day13-chat`, v1/v2, labels `baseline`, `candidate`, `production` |
| `10-prompt-rollback.png` | Hai trạng thái: production → v2 sau promote và production → v1 sau rollback |
| `11-dashboard-overview.png` | Dashboard local đủ 6 panel, 60 phút, unit và threshold |

Đối chiếu một `correlation_id` trong ảnh metadata với `data/logs.jsonl` và file `submission/evidence/cp2-prompt-runtime.txt`. Không dùng trace ID hoặc ảnh của project khác.

## 6. Cleanup và kiểm tra cuối

```powershell
Get-NetTCPConnection -LocalPort 8000,8501 -State Listen -ErrorAction SilentlyContinue
python -m pytest -q
python scripts/validate_logs.py
python scripts/validate_dashboard.py
git status --short --untracked-files=all
git diff --check
```

Nếu từng in credential vào terminal, revoke key cũ trên Langfuse Project Settings → API Keys, tạo key mới, cập nhật `.env`, rồi tuyệt đối không commit `.env`.