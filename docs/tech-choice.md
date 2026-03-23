# 技術選型

## 1. ASGI 伺服器：Daphne vs Gunicorn + Uvicorn

| 比較項目       | Daphne                           | Gunicorn + Uvicorn            |
| -------------- | -------------------------------- | ----------------------------- |
| **程序模型**   | 單一程序                         | 多程序（pre-fork，`-w N`）    |
| **WebSocket**  | 原生支援（Django Channels 官方） | 透過 Uvicorn Worker 支援 ASGI |
| **吞吐量上限** | ~200–500 QPS                     | ~1000+ QPS（4 workers）       |
| **複雜度**     | 單一依賴                         | 兩個依賴，指令語法較長        |

### 決策：Gunicorn + Uvicorn

壓力測試顯示 Daphne 單一程序在 100 QPS 下請求排隊嚴重（p95 達 494ms、丟棄 4.9% 請求）。改用 Gunicorn + 2 Uvicorn Workers 後，p95 降至 34ms、丟棄率降至 0.4%。詳見 [`docs/performance.md`](performance.md)。

**取捨**：多了兩個依賴，但換來可量化的效能提升與生產環境標準部署模式。既有 WebSocket 路由（`ProtocolTypeRouter`）無需修改。

**何時重新評估**：若需更高吞吐量，可增加 `-w` worker 數量。

---

## 2. 壓力測試工具：wrk vs wrk2 vs k6 vs Locust

| 比較項目                 | wrk                   | wrk2                    | k6                         | Locust                          |
| ------------------------ | --------------------- | ----------------------- | -------------------------- | ------------------------------- |
| **負載模型**             | 開放迴圈（盡量打滿）  | 固定速率（`--rate N`）  | 彈性（固定速率、漸進式等） | 封閉迴圈（控制併發數）          |
| **QPS 設定方式**         | 間接（調 `-t`、`-c`） | 直接（`--rate 100`）    | 直接（`rate: 100`）        | 間接（調 `users`、`wait_time`） |
| **Coordinated Omission** | 有此問題              | 已修正                  | 固定速率模式下準確         | 有此問題                        |
| **通過/失敗門檻**        | 無                    | 無                      | 內建（`thresholds`）       | 需自行撰寫                      |
| **macOS ARM 安裝**       | 可                    | 困難（LuaJIT 編譯問題） | 可（`brew install k6`）    | 可（`pip install`）             |

### 決策：k6

需求為「可承受 100 QPS」，k6 的 `constant-arrival-rate` 執行器可精確發送固定速率請求，搭配內建 `thresholds` 判定通過與否，並透過 `dropped_iterations` 指標量化伺服器是否跟得上目標速率。

**何時重新評估**：若需 HdrHistogram 等級的延遲精度，wrk2 在相容平台上更合適；若需複雜使用者旅程與視覺化儀表板，Locust 是較佳選擇。

---

## 3. Redis 快取：共用現有容器 vs 獨立容器

| 比較項目            | 同容器不同 DB                   | 獨立容器                                               |
| ------------------- | ------------------------------- | ------------------------------------------------------ |
| **隔離性**          | 邏輯隔離（DB 0–15 共享記憶體）  | 物理隔離（獨立程序與記憶體）                           |
| **Eviction policy** | 共用（per-instance，非 per-DB） | 獨立（Cache 用 `allkeys-lru`，Broker 用 `noeviction`） |
| **故障範圍**        | Redis 當機影響全部功能          | 各自獨立                                               |
| **複雜度**          | 零額外設定                      | 多一個 service、healthcheck、環境變數                  |

### 決策：共用容器，以 DB 編號隔離

本專案負載極低（快取 ~100KB/s、Celery 每小時一次、少量 WebSocket 廣播），資源競爭與記憶體壓力不存在。`cache.clear()` 呼叫 `FLUSHDB` 只清 DB 1，不影響 DB 0 上的 Celery 與 Channel Layer。

**何時重新評估**：當流量成長至需區分 eviction policy（Cache 用 `allkeys-lru`、Broker 用 `noeviction`）或需要獨立故障域時，應拆為兩個 Redis 容器。
