# CCW-MCP 項目架構

## 目錄結構

```
ccw-mcp/
├── ccw_mcp/                    # 主程式碼
│   ├── __init__.py
│   ├── server.py               # MCP 伺服器主入口
│   ├── cel/                    # 反事實執行層
│   │   ├── __init__.py
│   │   ├── linux.py            # Linux overlayfs 實作
│   │   ├── windows.py          # Windows 專門實作 ⭐ NEW
│   │   └── portable.py         # 通用實作（macOS）
│   ├── policy/                 # 策略引擎
│   │   ├── __init__.py
│   │   └── engine.py           # 策略驗證邏輯
│   ├── tools/                  # MCP 工具實作
│   │   ├── __init__.py
│   │   ├── capsule.py          # Capsule 管理
│   │   ├── witness.py          # 見證包生成與重放
│   │   ├── promote.py          # 推進功能
│   │   ├── deltamin.py         # Delta 最小化
│   │   └── commute.py          # 可交換性分析
│   └── util/                   # 工具函數
│       ├── __init__.py
│       ├── hashing.py          # BLAKE3 雜湊
│       ├── trace.py            # 資源追蹤
│       └── diff.py             # Diff 生成
├── tests/                      # 測試
│   ├── __init__.py
│   ├── test_basic.py
│   └── test_windows.py         # Windows 特定測試 ⭐ NEW
├── docs/                       # 文檔
│   ├── jsonrpc-examples.md     # JSON-RPC 範例
│   ├── ARCHITECTURE.md         # 架構說明
│   └── WINDOWS.md              # Windows 使用指南 ⭐ NEW
├── pyproject.toml              # 專案配置
├── README.md                   # 專案說明
├── example_workflow.py         # 範例工作流程
└── uv.lock                     # 依賴鎖定
```

## 核心元件

### 1. 反事實執行層（CEL）

**檔案**: `ccw_mcp/cel/`

提供三種實作：
- **LinuxCEL**: 使用 overlayfs 和 namespaces（性能最優）
- **WindowsCEL**: Windows 專門實作，檔案監控 + 進程隔離 ⭐
- **PortableCEL**: 使用目錄複製（macOS 跨平台相容）

**功能**:
- 建立隔離的執行環境
- 執行命令並追蹤資源使用
- 收集檔案變更（讀寫集）

#### WindowsCEL 特色

**檔案**: `ccw_mcp/cel/windows.py`

Windows 特定優化：
- **檔案系統監控**:
  - 執行前後快照比對
  - 後台監控線程（可選）
  - 偵測新增、修改、刪除的檔案

- **進程隔離**:
  - `CREATE_NEW_PROCESS_GROUP` 標誌
  - 環境變數清理與白名單
  - 獨立的 TEMP/TMP 目錄

- **路徑處理**:
  - 支援 Windows 反斜線和正斜線
  - 正確處理帶空格的路徑
  - UNC 路徑支援

- **資源追蹤**:
  - CPU 時間（ms）
  - 記憶體使用峰值（KB）
  - I/O 讀寫量（KB）

- **清理機制**:
  - 重試刪除（處理檔案鎖定）
  - 延遲機制避免 PermissionError

### 2. Capsule 管理

**檔案**: `ccw_mcp/tools/capsule.py`

**功能**:
- 建立和管理 capsule
- 執行命令
- 生成 diff
- 儲存 metadata

### 3. 見證引擎

**檔案**: `ccw_mcp/tools/witness.py`

**功能**:
- 生成見證包（內容位址化）
- BLAKE3 雜湊計算
- 支援壓縮（zstd）
- 重放驗證

### 4. 策略引擎

**檔案**: `ccw_mcp/policy/engine.py`

**功能**:
- 定義和管理策略規則
- 驗證資源使用限制
- 檢查路徑限制
- 執行測試要求
- 驗證重放一致性

### 5. 推進引擎

**檔案**: `ccw_mcp/tools/promote.py`

**功能**:
- 策略驗證
- 原子性檔案寫入
- Dry-run 模式
- 錯誤回滾

### 6. Delta 最小化

**檔案**: `ccw_mcp/tools/deltamin.py`

**功能**:
- 找出導致失敗的最小變更集
- Delta debugging 算法
- 預算控制

### 7. 可交換性分析

**檔案**: `ccw_mcp/tools/commute.py`

**功能**:
- 分析變更獨立性
- 識別衝突對
- 支援並行化決策

## MCP 工具列表

1. `capsule/create` - 建立 capsule
2. `capsule/exec` - 執行命令
3. `capsule/diff` - 查看變更
4. `capsule/witness` - 生成見證包
5. `capsule/replay` - 重放見證
6. `capsule/promote` - 推進變更
7. `policy/set` - 設定策略
8. `capsule/deltamin` - Delta 最小化
9. `capsule/commutativity` - 可交換性分析

## 測試狀態

所有測試通過（7/7 基礎測試 + 9/9 Windows 測試）：
- ✅ 雜湊功能
- ✅ CEL 建立與執行
- ✅ 策略管理與驗證
- ✅ Capsule 生命週期
- ✅ Windows CEL 建立與掛載 ⭐
- ✅ Windows 檔案系統監控 ⭐
- ✅ Windows 進程隔離 ⭐
- ✅ Windows 資源追蹤 ⭐
- ✅ Windows 超時處理 ⭐
- ✅ Windows 路徑處理 ⭐
- ✅ Windows 特殊字符處理 ⭐
- ✅ Windows 臨時目錄隔離 ⭐
- ✅ Windows 完整工作流程 ⭐

## 使用方法

### 啟動伺服器

```bash
uv run ccw-mcp --stdio
```

### 執行測試

```bash
uv run pytest -v
```

### 範例工作流程

```bash
python example_workflow.py
```

## 依賴項

核心依賴：
- `blake3` - BLAKE3 雜湊
- `msgspec` - 快速序列化
- `psutil` - 資源監控

開發依賴：
- `pytest` - 測試框架
- `pytest-asyncio` - 異步測試

## 設計特點

1. **模組化設計**: 每個元件獨立可測試
2. **平台適配**: Linux 優化，Windows 專門實作，macOS 降級
3. **內容位址化**: BLAKE3 確保唯一性
4. **策略驅動**: 靈活的驗證規則
5. **原子性操作**: 防止部分應用變更
6. **🪟 Windows 完整支援**: 專門的檔案監控和進程隔離實作 ⭐

## 未來擴展

- 完整 zstd 壓縮支援
- 更精確的檔案讀取追蹤（strace 整合）
- 網路隔離增強
- 更多策略模板
- Web UI 介面
