# CCW-MCP

**Counterfactual & Certificate-Carrying MCP Server**

Simulate before commit. Build counterfactual worlds, generate verifiable witnesses, and validate changes with policy gates.

## Overview

CCW-MCP implements a novel approach to safe code changes:

1. **Counterfactual Execution Layer (CEL)**: Run commands in isolated sandbox environments with zero side effects
2. **Delta-Graph Witness (DGW)**: Generate content-addressed, replayable evidence packages
3. **Policy-Gated Promotion**: Validate changes against configurable policies before applying to real filesystem

## Key Features

- **反事實模擬 (Counterfactual Simulation)**: Test changes in isolated environments
- **見證包 (Witness Packages)**: Cryptographically verifiable execution traces
- **策略驗證 (Policy Validation)**: Automated testing, resource limits, and path constraints
- **差分最小化 (Delta Minimization)**: Find minimal change sets that reproduce failures
- **可交換性分析 (Commutativity Analysis)**: Identify safe parallel execution opportunities
- **🪟 完整 Windows 支援**: 專門的 Windows CEL 實作，包含檔案監控與進程隔離

## Installation

### For Claude Desktop Users

**完整安裝指南**: 📘 [Claude Desktop 安裝教學](docs/CLAUDE-DESKTOP-INSTALL.md)

快速步驟：
1. 安裝 Python 3.11+ 和 [uv](https://github.com/astral-sh/uv)
2. 克隆專案並執行 `uv sync`
3. 編輯 Claude Desktop 配置檔案
4. 重啟 Claude Desktop

### Standalone Installation

```bash
# Clone repository
cd ccw-mcp

# Initialize with uv
uv sync

# Run server
uv run ccw-mcp --stdio
```

## Quick Start

### 1. Create a Capsule

```bash
# Send JSON-RPC request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "capsule/create",
    "arguments": {
      "workspace": "/path/to/project",
      "env_whitelist": ["PATH", "PYTHONPATH"]
    }
  }
}
```

### 2. Execute Commands

```bash
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "capsule/exec",
    "arguments": {
      "capsule_id": "cap_1699999999999",
      "cmd": ["uv", "run", "pytest", "-v"]
    }
  }
}
```

### 3. Generate Witness

```bash
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "capsule/witness",
    "arguments": {
      "capsule_id": "cap_1699999999999",
      "compress": "zstd"
    }
  }
}
```

### 4. Promote Changes

```bash
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "capsule/promote",
    "arguments": {
      "capsule_id": "cap_1699999999999",
      "policies": ["baseline"],
      "dry_run": false
    }
  }
}
```

## MCP Tools

### Core Tools

- `capsule/create` - Create isolated environment
- `capsule/exec` - Execute commands in capsule
- `capsule/diff` - View changes
- `capsule/witness` - Generate witness package
- `capsule/replay` - Replay witness
- `capsule/promote` - Apply changes to filesystem

### Advanced Tools

- `capsule/deltamin` - Minimize failure-reproducing change set
- `capsule/commutativity` - Analyze change independence
- `policy/set` - Configure validation policies

## Architecture

```
┌─────────────────┐
│  MCP Client     │
│  (Claude Code)  │
└────────┬────────┘
         │ JSON-RPC
         │
┌────────▼────────────────────────────────────────┐
│  CCW-MCP Server                                 │
│  ┌──────────────┐  ┌─────────────┐             │
│  │  Capsule     │  │  Witness    │             │
│  │  Registry    │  │  Engine     │             │
│  └──────────────┘  └─────────────┘             │
│  ┌──────────────┐  ┌─────────────┐             │
│  │  Policy      │  │  Promote    │             │
│  │  Engine      │  │  Engine     │             │
│  └──────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────┘
         │
┌────────▼────────────────────────────────────────┐
│  Counterfactual Execution Layer (CEL)           │
│  ┌──────────────┐  ┌─────────────┐             │
│  │  Linux CEL   │  │  Portable   │             │
│  │  (overlayfs) │  │  CEL (copy) │             │
│  └──────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────┘
```

## Policy Configuration

```python
# Set custom policy
{
  "name": "strict",
  "rules": {
    "max_rss_mb": 1024,
    "max_cpu_ms": 60000,
    "deny_paths": ["~/.ssh/*", "~/.aws/*", "/etc/*"],
    "require_tests": ["uv run pytest -q"],
    "require_replay_ok": true
  }
}
```

## Platform Support

- **Linux** (Tier 1): Overlayfs + namespaces for optimal performance (~200ms capsule creation)
- **Windows** (Tier 1): 專門的 WindowsCEL 實作，檔案監控 + 進程隔離 (~800ms capsule creation)
- **macOS** (Tier 2): Portable CEL with directory copy (~500ms capsule creation)

### Windows 特色功能

- ✅ 實時檔案系統監控
- ✅ CREATE_NEW_PROCESS_GROUP 進程隔離
- ✅ 獨立的 TEMP/TMP 目錄
- ✅ 正確處理 Windows 路徑和特殊字符
- ✅ 資源追蹤（CPU、記憶體、I/O）
- ✅ 完整測試覆蓋

📖 **詳細說明**: 查看 [Windows 使用指南](docs/WINDOWS.md)

## Performance Targets

- Capsule creation: < 200ms (Linux), < 800ms (Windows), < 500ms (macOS)
- Witness size: ≤ 20% of touched data (with deduplication)
- Replay consistency: ≥ 99%
- Policy blocking: ≥ 95% of non-compliant changes

## Use Cases

1. **Large Refactoring**: Simulate impact before committing
2. **Dependency Upgrades**: Test in isolation, verify with witnesses
3. **Batch Operations**: Find minimal failure-reproducing changes
4. **Risk Assessment**: Compare multiple approaches with policy reports

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Type checking
uv run mypy ccw_mcp/
```

## License

See LICENSE file.

## Contributing

Contributions welcome! Please see CONTRIBUTING.md.

---

**先模擬、再證成、後推進**
