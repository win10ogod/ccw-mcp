# CCW-MCP 在 Claude Desktop 中的安裝指南

## 📋 前置需求

### 1. 安裝 Claude Desktop

從官方網站下載並安裝 Claude Desktop：
- 訪問: https://claude.ai/download

### 2. 安裝 Python 和 uv

**Windows**:
```powershell
# 安裝 Python 3.11+
# 從 https://python.org 下載安裝

# 安裝 uv
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 驗證安裝
uv --version
python --version
```

**Linux/macOS**:
```bash
# 安裝 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 驗證安裝
uv --version
python3 --version
```

---

## 🚀 安裝步驟

### 步驟 1: 克隆專案

```bash
# 選擇安裝位置
cd ~
# 或 Windows: cd C:\Users\YourName

# 克隆專案（或下載解壓）
git clone <repository-url> ccw-mcp
cd ccw-mcp

# 初始化依賴
uv sync
```

### 步驟 2: 測試伺服器

**驗證伺服器可以啟動**:

```bash
# Linux/macOS
uv run ccw-mcp --stdio

# Windows PowerShell
uv run ccw-mcp --stdio
```

按 `Ctrl+C` 退出。如果看到伺服器等待輸入，表示安裝成功！

---

## ⚙️ 配置 Claude Desktop

### Windows 配置

**1. 找到配置檔案位置**:

```powershell
# 配置檔案路徑
$configPath = "$env:APPDATA\Claude\claude_desktop_config.json"

# 創建目錄（如果不存在）
New-Item -ItemType Directory -Force -Path "$env:APPDATA\Claude"

# 打開配置檔案
notepad $configPath
```

**2. 編輯配置檔案**:

```json
{
  "mcpServers": {
    "ccw-mcp": {
      "command": "uv",
      "args": ["run", "ccw-mcp", "--stdio"],
      "cwd": "C:\\Users\\YourName\\ccw-mcp",
      "env": {
        "CCW_STORAGE": "C:\\Users\\YourName\\.ccw-mcp"
      }
    }
  }
}
```

**重要**:
- 將 `C:\\Users\\YourName` 替換為您的實際用戶目錄
- 路徑使用雙反斜線 `\\`
- 確保 `cwd` 指向專案目錄的絕對路徑

---

### Linux/macOS 配置

**1. 找到配置檔案位置**:

```bash
# Linux
CONFIG_PATH="$HOME/.config/Claude/claude_desktop_config.json"

# macOS
CONFIG_PATH="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

# 創建目錄
mkdir -p "$(dirname "$CONFIG_PATH")"

# 編輯配置
nano "$CONFIG_PATH"
# 或使用您喜歡的編輯器: vim, code, etc.
```

**2. 編輯配置檔案**:

```json
{
  "mcpServers": {
    "ccw-mcp": {
      "command": "uv",
      "args": ["run", "ccw-mcp", "--stdio"],
      "cwd": "/home/yourname/ccw-mcp",
      "env": {
        "CCW_STORAGE": "/home/yourname/.ccw-mcp"
      }
    }
  }
}
```

**重要**:
- 將 `/home/yourname` 替換為您的實際主目錄
- 使用絕對路徑
- macOS 使用 `/Users/yourname`

---

## 🔍 配置說明

### 配置欄位解釋

```json
{
  "mcpServers": {
    "ccw-mcp": {                              // 伺服器名稱（可自訂）
      "command": "uv",                        // 執行命令
      "args": [                               // 命令參數
        "run",                                //   uv run
        "ccw-mcp",                            //   ccw-mcp
        "--stdio"                             //   --stdio 模式
      ],
      "cwd": "C:\\path\\to\\ccw-mcp",        // 工作目錄（專案路徑）
      "env": {                                // 環境變數
        "CCW_STORAGE": "C:\\path\\.ccw-mcp"  //   儲存位置
      }
    }
  }
}
```

### 可選配置

```json
{
  "mcpServers": {
    "ccw-mcp": {
      "command": "uv",
      "args": ["run", "ccw-mcp", "--stdio", "--storage", "C:\\custom\\path"],
      "cwd": "C:\\Users\\YourName\\ccw-mcp",
      "env": {
        "CCW_STORAGE": "C:\\Users\\YourName\\.ccw-mcp",
        "PYTHONPATH": "C:\\Users\\YourName\\ccw-mcp",
        "UV_PYTHON": "python3.11"
      }
    }
  }
}
```

---

## ✅ 驗證安裝

### 步驟 1: 重啟 Claude Desktop

完全關閉並重新啟動 Claude Desktop 應用程式。

### 步驟 2: 檢查 MCP 伺服器

在 Claude Desktop 中：

1. 打開設定（Settings）
2. 查看 "Developer" 或 "MCP Servers" 標籤
3. 應該看到 `ccw-mcp` 伺服器顯示為 **已連接** 或 **綠色**

### 步驟 3: 測試功能

在對話中輸入：

```
請使用 ccw-mcp 創建一個測試 capsule
```

Claude 應該能夠：
- 看到 CCW-MCP 的工具
- 調用 `capsule/create` 工具
- 返回 capsule ID

---

## 🐛 故障排除

### 問題 1: 伺服器未連接

**症狀**: Claude Desktop 顯示 CCW-MCP 未連接或紅色

**解決方案**:

1. **檢查路徑**:
```powershell
# Windows: 確認路徑存在
Test-Path "C:\Users\YourName\ccw-mcp"

# Linux/macOS
ls -la ~/ccw-mcp
```

2. **檢查 uv 命令**:
```bash
# 確認 uv 在 PATH 中
which uv      # Linux/macOS
where.exe uv  # Windows

# 測試直接執行
cd C:\Users\YourName\ccw-mcp  # Windows
cd ~/ccw-mcp                   # Linux/macOS
uv run ccw-mcp --stdio
```

3. **檢查配置格式**:
```bash
# 使用 JSON 驗證器
python -m json.tool claude_desktop_config.json
```

### 問題 2: 權限錯誤

**Windows**:
```powershell
# 以管理員身分執行 PowerShell
# 然後重新安裝
cd ccw-mcp
uv sync
```

**Linux/macOS**:
```bash
# 確保有執行權限
chmod +x ~/.local/bin/uv
chmod -R u+w ~/ccw-mcp
```

### 問題 3: Python 版本錯誤

**檢查 Python 版本**:
```bash
python --version
# 或
python3 --version

# 需要 Python 3.11+
```

**指定 Python 版本**:
```json
{
  "mcpServers": {
    "ccw-mcp": {
      "command": "uv",
      "args": ["run", "--python", "3.11", "ccw-mcp", "--stdio"],
      "cwd": "C:\\Users\\YourName\\ccw-mcp"
    }
  }
}
```

### 問題 4: 找不到模組

**重新安裝依賴**:
```bash
cd ccw-mcp
rm -rf .venv uv.lock  # Windows: Remove-Item -Recurse -Force .venv, uv.lock
uv sync
```

### 問題 5: 配置檔案位置錯誤

**確認正確位置**:

| 系統 | 配置檔案位置 |
|------|-------------|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

**檢查實際位置**:
```powershell
# Windows
echo $env:APPDATA\Claude\claude_desktop_config.json

# Linux/macOS
echo ~/.config/Claude/claude_desktop_config.json  # Linux
echo ~/Library/Application\ Support/Claude/claude_desktop_config.json  # macOS
```

---

## 📝 完整配置範例

### Windows 完整範例

```json
{
  "mcpServers": {
    "ccw-mcp": {
      "command": "uv",
      "args": [
        "run",
        "ccw-mcp",
        "--stdio",
        "--storage",
        "C:\\Users\\YourName\\.ccw-mcp"
      ],
      "cwd": "C:\\Users\\YourName\\Documents\\ccw-mcp",
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "CCW_STORAGE": "C:\\Users\\YourName\\.ccw-mcp"
      }
    }
  }
}
```

### Linux/macOS 完整範例

```json
{
  "mcpServers": {
    "ccw-mcp": {
      "command": "uv",
      "args": [
        "run",
        "ccw-mcp",
        "--stdio",
        "--storage",
        "/home/yourname/.ccw-mcp"
      ],
      "cwd": "/home/yourname/ccw-mcp",
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "CCW_STORAGE": "/home/yourname/.ccw-mcp",
        "PATH": "/home/yourname/.local/bin:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```

---

## 🎯 驗證清單

安裝完成後，確認以下項目：

- [ ] Python 3.11+ 已安裝
- [ ] uv 已安裝並在 PATH 中
- [ ] ccw-mcp 專案已克隆/下載
- [ ] `uv sync` 成功執行
- [ ] `uv run ccw-mcp --stdio` 可以啟動
- [ ] 配置檔案路徑正確
- [ ] 配置檔案 JSON 格式正確
- [ ] 路徑使用絕對路徑
- [ ] Windows 路徑使用雙反斜線 `\\`
- [ ] Claude Desktop 已重啟
- [ ] CCW-MCP 在 Claude Desktop 中顯示為已連接
- [ ] 可以在對話中調用 CCW-MCP 工具

---

## 🎓 使用範例

安裝成功後，在 Claude Desktop 中嘗試：

**範例 1: 創建 Capsule**
```
請使用 ccw-mcp 在 C:\temp\myproject 創建一個 capsule
```

**範例 2: 執行測試**
```
在剛才的 capsule 中執行 pytest tests/
```

**範例 3: 查看變更**
```
顯示 capsule 中的變更
```

**範例 4: 生成見證包**
```
為這個 capsule 生成見證包
```

---

## 📚 更多資源

- [CCW-MCP 主文檔](../README.md)
- [Windows 使用指南](WINDOWS.md)
- [Windows 快速開始](QUICKSTART-WINDOWS.md)
- [JSON-RPC 範例](jsonrpc-examples.md)
- [架構說明](ARCHITECTURE.md)

---

## 🆘 獲取幫助

如果仍有問題：

1. **查看日誌**:
   - Windows: `%APPDATA%\Claude\logs`
   - macOS: `~/Library/Logs/Claude`
   - Linux: `~/.config/Claude/logs`

2. **測試獨立運行**:
   ```bash
   cd ccw-mcp
   uv run python -c "from ccw_mcp.server import CCWMCPServer; print('OK')"
   ```

3. **檢查依賴**:
   ```bash
   uv run pip list
   ```

4. **回報問題**:
   - 提供操作系統版本
   - 提供 Python 版本
   - 提供錯誤訊息
   - 提供配置檔案（移除敏感資訊）

---

**🎉 安裝完成！開始使用 CCW-MCP 先模擬、再證成、後推進！**
