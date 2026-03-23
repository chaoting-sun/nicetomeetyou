# 效能測試結果

## 測試設定

- **工具：** k6，使用 `constant-arrival-rate` 執行器
- **速率：** 每秒 100 個請求
- **時長：** 30 秒
- **目標：** `GET /api/news/`（分頁列表 API）
- **資料庫：** PostgreSQL 16，Redis 7 快取（TTL 60 秒）

### k6 腳本

```javascript
export const options = {
  scenarios: {
    constant_rate: {
      executor: "constant-arrival-rate",
      rate: 100,
      timeUnit: "1s",
      duration: "30s",
      preAllocatedVUs: 20,
      maxVUs: 50,
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
  },
};
```

### `dropped_iterations` 說明

k6 的 `constant-arrival-rate` 執行器每秒嘗試啟動恰好 100 次迭代。若所有 VU 皆忙碌，k6 會跳過（「丟棄」）排程中的迭代。`dropped_iterations` 數值高，代表伺服器無法承受目標負載；接近零則代表目標速率有效維持。

---

## 測試 A — Daphne（單一程序）— 基準線

**伺服器：** `daphne -b 0.0.0.0 -p 8000 config.asgi:application`

```
  █ THRESHOLDS

    http_req_duration
    ✓ 'p(95)<500' p(95)=493.99ms

    http_req_failed
    ✓ 'rate<0.01' rate=0.00%

  █ TOTAL RESULTS

    HTTP
    http_req_duration..............: avg=78.65ms min=2.41ms med=4.85ms max=1.15s p(90)=327.49ms p(95)=493.99ms
    http_req_failed................: 0.00%  0 out of 2855
    http_reqs......................: 2855   95.145316/s

    EXECUTION
    dropped_iterations.............: 146    4.865575/s
    iterations.....................: 2855   95.145316/s
    vus_max........................: 50     min=20        max=50
```

---

## 測試 B — Gunicorn + 2 個 Uvicorn Worker — 最佳化部署

**伺服器：** `gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000`

```
  █ THRESHOLDS

    http_req_duration
    ✓ 'p(95)<500' p(95)=33.96ms

    http_req_failed
    ✓ 'rate<0.01' rate=0.00%

  █ TOTAL RESULTS

    HTTP
    http_req_duration..............: avg=12.34ms min=1.76ms med=3.54ms max=441.37ms p(90)=9.53ms p(95)=33.96ms
    http_req_failed................: 0.00%  0 out of 2989
    http_reqs......................: 2989   99.597604/s

    EXECUTION
    dropped_iterations.............: 12     0.399857/s
    iterations.....................: 2989   99.597604/s
    vus_max........................: 32     min=20        max=32
```

---

## 比較

| Metric | Daphne (1 process) | Gunicorn + 2 Uvicorn Workers | Improvement |
|--------|-------------------|------------------------------|-------------|
| Throughput | 95.1 req/s | 99.6 req/s | +4.7% |
| Avg Latency | 78.65ms | 12.34ms | 6.4x faster |
| Median Latency | 4.85ms | 3.54ms | 1.4x faster |
| p90 Latency | 327.49ms | 9.53ms | 34x faster |
| p95 Latency | 493.99ms | 33.96ms | 14.5x faster |
| Max Latency | 1.15s | 441ms | 2.6x faster |
| Dropped Iterations | 146 (4.9/s) | 12 (0.4/s) | 92% fewer |
| Max VUs Needed | 50 | 32 | 36% fewer |
| Error Rate | 0.00% | 0.00% | Same |

注意：吞吐量為 k6 回報的平均持續速率，非瞬間峰值。

測試期間共預計 3000 次迭代（30 秒 × 100 req/s）。Daphne 丟棄 146 次（丟棄率 4.9%），Gunicorn+Uvicorn 僅丟棄 12 次（丟棄率 0.4%）。

### 目標達成評估

| 設定 | 狀態 | 說明 |
|------|------|------|
| Daphne（1 個程序）| 接近目標，但未完全維持 100 req/s | 丟棄 146 次迭代；實際吞吐量 95.1 req/s |
| Gunicorn + 2 Uvicorn Workers | 有效達成 100 req/s 目標 | 丟棄 12 次迭代；實際吞吐量約 100 req/s |

### 重點摘要

1. **尾部延遲大幅改善。** 單一程序 Daphne 在高負載下請求排隊嚴重，p95 達 ~494ms。改用 2 個 Uvicorn Worker 並行處理後，p95 降至 34ms，改善 14.5 倍。
2. **幾乎零丟棄迭代。** Daphne 丟棄 146 次（無法跟上目標速率），Gunicorn+Uvicorn 僅丟棄 12 次，有效吸收 100 req/s 的完整負載。
3. **最佳化部署仍有餘裕。** 需以更高固定速率測試，才能確定真正的上限。

---

## 結論

在單一程序 Daphne 基準設定下，系統接近但未能完全維持 100 QPS 目標（95.1 req/s，丟棄 146 次迭代）。改用 Gunicorn 管理 2 個 Uvicorn ASGI Worker 後，API 有效達成目標負載，維持約 99.6 req/s，錯誤率 0%，尾部延遲顯著降低。

---

## 已套用的最佳化

1. **Redis 快取**（`django-redis`）：列表 API 套用 `cache_page` 裝飾器，TTL 60 秒
2. **`defer("content")`**：列表查詢跳過載入大型 content 欄位，減少資料庫負擔
3. **快取失效**：爬蟲新增文章時呼叫 `cache.clear()`。此為簡化策略，適合小型專案；正式環境建議改用精細的 key-based 失效或快取版本控制
4. **部署最佳化**：Gunicorn 管理 2 個 Uvicorn ASGI Worker，支援並行請求處理
