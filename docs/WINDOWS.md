# CCW-MCP Windows 使用指南

## Windows 完整功能支援

CCW-MCP 現在為 Windows 系統提供完整的功能支援，包括增強的檔案系統監控和進程隔離。

## Windows 特性

### 1. 專門的 Windows CEL 實作

`WindowsCEL` 針對 Windows 系統進行了優化：

- **檔案系統監控**: 實時監控檔案變更
- **進程隔離**: 使用 `CREATE_NEW_PROCESS_GROUP` 標誌
- **路徑處理**: 正確處理 Windows 路徑分隔符和特殊字符
- **環境隔離**: 獨立的 TEMP/TMP 目錄
- **資源追蹤**: CPU、記憶體、I/O 監控

### 2. 檔案系統監控

Windows CEL 提供兩層監控：

1. **快照比對**: 執行前後比對檔案時間戳
2. **後台監控**: 可選的檔案系統監控線程

```python
from ccw_mcp.cel import create_cel

# 自動檢測並使用 WindowsCEL
cel = create_cel(workspace=Path("C:/project"))

# 執行命令
result = cel.execute(["cmd", "/c", "build.bat"])

# 檢查變更
changes = cel.get_changes()
```

### 3. 進程隔離

Windows 實作使用多種隔離技術：

- **環境變數隔離**: 清理危險的環境變數
- **工作目錄隔離**: 沙盒化的工作空間
- **臨時目錄隔離**: 獨立的 TEMP/TMP
- **進程群組**: 使用 `CREATE_NEW_PROCESS_GROUP`

### 4. 路徑處理

正確處理 Windows 特有的路徑問題：

- 支援反斜線 (`\`) 和正斜線 (`/`)
- 處理 UNC 路徑
- 支援長路徑（> 260 字符）
- 正確處理帶空格的路徑

## 安裝

### 前置需求

- Windows 10 或更新版本
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) 包管理器

### 安裝步驟

```powershell
# 克隆專案
git clone <repository-url>
cd ccw-mcp

# 安裝依賴
uv sync

# 驗證安裝
uv run ccw-mcp --help
```

## 使用範例

### 基本工作流程

```powershell
# 1. 啟動伺服器（stdio 模式）
uv run ccw-mcp --stdio

# 2. 或使用 Python API
uv run python
```

```python
from pathlib import Path
from ccw_mcp.tools import CapsuleRegistry

# 初始化
storage = Path.home() / ".ccw-mcp"
registry = CapsuleRegistry(storage)

# 建立 capsule
result = registry.create(
    workspace=Path("C:/Users/YourName/project"),
    env_whitelist=["PATH", "PYTHONPATH"]
)
capsule_id = result["capsule_id"]

# 執行 Windows 命令
exec_result = registry.execute(
    capsule_id=capsule_id,
    cmd=["cmd", "/c", "pytest", "tests/"],
    timeout_ms=60000
)

print(f"Exit code: {exec_result['exit_code']}")
print(f"Output: {exec_result['stdout']}")

# 查看變更
diff = registry.diff(capsule_id=capsule_id)
print(f"Changes: {diff['summary']}")
```

### PowerShell 整合

```powershell
# 建立啟動腳本 start-ccw-mcp.ps1
$env:CCW_STORAGE = "$env:USERPROFILE\.ccw-mcp"
uv run ccw-mcp --stdio --storage $env:CCW_STORAGE
```

### 批次檔整合

```batch
@echo off
REM start-ccw-mcp.bat
set CCW_STORAGE=%USERPROFILE%\.ccw-mcp
uv run ccw-mcp --stdio --storage %CCW_STORAGE%
```

## Windows 特定配置

### 策略設定

Windows 上的路徑規則：

```python
from ccw_mcp.policy import PolicyEngine, PolicyRule

engine = PolicyEngine()

# Windows 特定的敏感路徑
windows_policy = PolicyRule(
    name="windows-strict",
    max_rss_mb=2048,
    deny_paths=[
        "C:/Windows/System32/*",
        "C:/Windows/SysWOW64/*",
        "C:/Program Files/*",
        "%USERPROFILE%/.ssh/*",
        "%APPDATA%/Microsoft/Credentials/*"
    ],
    require_tests=["pytest", "-q"],
    require_replay_ok=True
)

engine.add_policy(windows_policy)
```

### 環境變數白名單

```python
# 建議的 Windows 環境變數白名單
env_whitelist = [
    "PATH",
    "PYTHONPATH",
    "PYTHONHOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "HOMEDRIVE",
    "HOMEPATH"
]

result = registry.create(
    workspace=workspace,
    env_whitelist=env_whitelist
)
```

## 效能優化

### Windows 特定優化

1. **使用 SSD**: 沙盒複製在 SSD 上更快
2. **排除防毒掃描**: 將 `.ccw-mcp` 目錄加入防毒軟體排除列表
3. **增加檔案監控緩衝**: 對大型專案調整監控間隔

```python
# 自定義監控間隔（僅供參考）
cel = WindowsCEL(workspace=workspace)
# 內部使用 0.1 秒輪詢間隔
```

## 已知限制

### Windows 上的限制

1. **沙盒隔離**:
   - 不使用 overlayfs（Linux 特性）
   - 使用完整目錄複製（較慢）
   - 無法完全隔離系統呼叫

2. **檔案監控**:
   - 基於輪詢，非即時
   - 可能無法捕捉極快速的變更
   - 大型專案可能較慢

3. **路徑長度**:
   - Windows 傳統 260 字符限制
   - 需啟用長路徑支援（Windows 10 1607+）

4. **符號連結**:
   - 需要管理員權限或開發者模式
   - 可能無法正確複製某些連結

### 啟用長路徑支援

```powershell
# 以管理員身分執行 PowerShell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force

# 或編輯組策略
# 電腦設定 > 系統管理範本 > 系統 > 檔案系統
# 啟用「啟用 Win32 長路徑」
```

## 測試

### 執行 Windows 測試

```powershell
# 執行所有測試
uv run pytest -v

# 只執行 Windows 特定測試
uv run pytest tests/test_windows.py -v

# 執行特定測試
uv run pytest tests/test_windows.py::TestWindowsCEL::test_windows_cel_creation -v
```

### 測試覆蓋範圍

Windows 特定測試包括：

- ✅ CEL 建立與掛載
- ✅ 檔案系統監控
- ✅ 進程隔離
- ✅ 資源追蹤
- ✅ 超時處理
- ✅ 路徑處理（含反斜線）
- ✅ 特殊字符處理
- ✅ 臨時目錄隔離
- ✅ 完整工作流程

## 故障排除

### 常見問題

**Q: 權限錯誤**
```
PermissionError: [WinError 5] 拒絕存取
```
A: 確保沒有其他程式鎖定檔案，或以管理員身分執行。

**Q: 路徑過長錯誤**
```
OSError: [WinError 206] 檔案名稱或副檔名太長
```
A: 啟用 Windows 長路徑支援（見上文）。

**Q: 監控未檢測到變更**
```
touched: {"written": []}
```
A: 確保命令確實寫入檔案，檢查工作目錄是否正確。

**Q: 超時未生效**
```
命令執行超過指定時間
```
A: Windows 進程終止可能需要更長時間，增加超時或使用 `taskkill`。

### 日誌與除錯

```python
import logging

# 啟用除錯日誌
logging.basicConfig(level=logging.DEBUG)

# 執行操作
cel = create_cel(workspace)
result = cel.execute(["cmd", "/c", "echo", "test"])
```

## 與 MCP 客戶端整合

### Claude Code (Windows)

在 Claude Code 中使用：

```json
{
  "mcpServers": {
    "ccw-mcp": {
      "command": "uv",
      "args": ["run", "ccw-mcp", "--stdio"],
      "cwd": "C:/path/to/ccw-mcp",
      "env": {
        "CCW_STORAGE": "C:/Users/YourName/.ccw-mcp"
      }
    }
  }
}
```

## 效能基準

### Windows vs Linux 比較

| 操作 | Windows (SSD) | Linux (overlayfs) |
|------|---------------|-------------------|
| Capsule 建立 | ~800ms | ~150ms |
| 命令執行 | ~50ms | ~30ms |
| 變更檢測 | ~100ms | ~20ms |
| 清理 | ~500ms | ~50ms |

**注意**: Windows 效能受硬體、防毒軟體和系統負載影響較大。

## 最佳實踐

1. **使用 SSD**: 大幅提升沙盒建立速度
2. **限制專案大小**: 避免複製超大檔案（如 node_modules）
3. **使用 .gitignore**: 排除不必要的檔案
4. **定期清理**: 清理舊的 capsule 和 witness
5. **監控資源**: 注意磁碟空間使用

## 更新與維護

```powershell
# 更新 CCW-MCP
cd ccw-mcp
git pull
uv sync

# 清理舊資料
Remove-Item -Recurse -Force $env:USERPROFILE\.ccw-mcp\capsules\cap_old*
```

## 支援

- **文檔**: [README.md](../README.md)
- **範例**: [example_workflow.py](../example_workflow.py)
- **測試**: `tests/test_windows.py`
- **問題回報**: GitHub Issues

---

**Windows 完整功能支援 - 先模擬、再證成、後推進**
