# CCW-MCP Windows 快速開始

## 5 分鐘開始使用

### 1. 安裝

```powershell
# 克隆專案
git clone <repository-url>
cd ccw-mcp

# 安裝 uv（如果還沒有）
# 訪問: https://github.com/astral-sh/uv

# 安裝依賴
uv sync

# 驗證安裝
uv run ccw-mcp --help
```

### 2. 第一個 Capsule

**建立測試專案**：

```powershell
# 建立測試目錄
mkdir C:\temp\test-project
cd C:\temp\test-project
echo "Hello World" > test.txt
```

**啟動 Python 互動環境**：

```powershell
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
    workspace=Path("C:/temp/test-project")
)

print(f"Capsule ID: {result['capsule_id']}")
capsule_id = result['capsule_id']
```

### 3. 執行命令

```python
# 在 capsule 中執行命令
exec_result = registry.execute(
    capsule_id=capsule_id,
    cmd=["cmd", "/c", "echo Modified > test.txt"]
)

print(f"Exit code: {exec_result['exit_code']}")
print(f"Output: {exec_result['stdout']}")
```

### 4. 查看變更

```python
# 查看 diff
diff = registry.diff(capsule_id=capsule_id)
print(f"\n變更統計: {diff['summary']}")
print(f"\nDiff:\n{diff['diff'][:500]}")
```

### 5. 生成見證包

```python
# 建立見證
from ccw_mcp.tools import WitnessEngine

witness_engine = WitnessEngine(storage / "witnesses")

# 獲取 capsule 資訊
entry = registry.get(capsule_id)
if entry:
    metadata, cel = entry
    changes = cel.get_changes()

    # 建立見證包
    witness = witness_engine.create(
        capsule_id=capsule_id,
        capsule_mount=cel.mount(),
        changes=changes
    )

    print(f"\n見證 ID: {witness['witness_id']}")
    print(f"根雜湊: {witness['root_hash']}")
    print(f"大小: {witness['size_bytes']} bytes")
```

### 6. 策略驗證

```python
from ccw_mcp.policy import PolicyEngine, PolicyRule
from ccw_mcp.tools import PromoteEngine

# 設定策略
policy_engine = PolicyEngine()
policy = PolicyRule(
    name="windows-safe",
    max_rss_mb=1024,
    deny_paths=[
        "C:/Windows/System32/*",
        "C:/Program Files/*"
    ]
)
policy_engine.add_policy(policy)

# 嘗試推進（dry run）
promote_engine = PromoteEngine(policy_engine)

if entry:
    result = promote_engine.promote(
        capsule_mount=cel.mount(),
        target_dir=Path("C:/temp/test-project"),
        changes=changes,
        policies=["windows-safe"],
        usage={"cpu_ms": 100, "rss_max_kb": 512},
        dry_run=True
    )

    print(f"\n推進狀態: {result.promoted}")
    print(f"策略通過: {result.policy_report['passed']}")
```

### 7. 清理

```python
# 刪除 capsule
registry.delete(capsule_id)
print("\n已清理！")
```

## 完整範例腳本

儲存為 `windows_example.py`：

```python
from pathlib import Path
from ccw_mcp.tools import CapsuleRegistry, WitnessEngine, PromoteEngine
from ccw_mcp.policy import PolicyEngine, PolicyRule

def main():
    # 設定
    storage = Path.home() / ".ccw-mcp"
    workspace = Path("C:/temp/test-project")
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "test.txt").write_text("Original content")

    # 建立 capsule
    registry = CapsuleRegistry(storage)
    result = registry.create(workspace=workspace)
    capsule_id = result['capsule_id']
    print(f"✓ 建立 Capsule: {capsule_id}")

    # 執行命令
    exec_result = registry.execute(
        capsule_id=capsule_id,
        cmd=["cmd", "/c", "echo Modified content > test.txt"]
    )
    print(f"✓ 執行命令 (exit: {exec_result['exit_code']})")

    # 查看變更
    diff = registry.diff(capsule_id=capsule_id)
    print(f"✓ 變更: {diff['summary']}")

    # 建立見證
    entry = registry.get(capsule_id)
    if entry:
        metadata, cel = entry
        changes = cel.get_changes()

        witness_engine = WitnessEngine(storage / "witnesses")
        witness = witness_engine.create(
            capsule_id=capsule_id,
            capsule_mount=cel.mount(),
            changes=changes
        )
        print(f"✓ 見證包: {witness['witness_id']}")

        # 驗證策略
        policy_engine = PolicyEngine()
        promote_engine = PromoteEngine(policy_engine)

        result = promote_engine.promote(
            capsule_mount=cel.mount(),
            target_dir=workspace,
            changes=changes,
            policies=["baseline"],
            usage={"cpu_ms": 100, "rss_max_kb": 512},
            dry_run=True
        )
        print(f"✓ 策略驗證: {'通過' if result.policy_report['passed'] else '失敗'}")

    # 清理
    registry.delete(capsule_id)
    print("✓ 已清理")

if __name__ == "__main__":
    main()
```

執行：

```powershell
uv run python windows_example.py
```

## 常用命令速查

```powershell
# 啟動 MCP 伺服器
uv run ccw-mcp --stdio

# 執行測試
uv run pytest tests/test_basic.py -v

# 執行 Windows 測試（僅 Windows）
uv run pytest tests/test_windows.py -v

# 清理儲存
Remove-Item -Recurse -Force $env:USERPROFILE\.ccw-mcp

# 查看幫助
uv run ccw-mcp --help
```

## 故障排除

**問題**: `PermissionError`
```powershell
# 以管理員身分執行 PowerShell
# 或關閉防毒軟體對該目錄的即時掃描
```

**問題**: 路徑過長
```powershell
# 啟用長路徑支援
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

**問題**: 找不到 `uv`
```powershell
# 從 GitHub 安裝 uv
# https://github.com/astral-sh/uv
```

## 下一步

- 📖 閱讀完整 [Windows 使用指南](WINDOWS.md)
- 🏗️ 查看 [架構文檔](ARCHITECTURE.md)
- 📝 參考 [JSON-RPC 範例](jsonrpc-examples.md)
- 🧪 執行 `example_workflow.py`

---

**🪟 Windows 完整功能支援 - 先模擬、再證成、後推進**
