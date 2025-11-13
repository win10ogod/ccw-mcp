# CCW-MCP JSON-RPC Examples

This document provides example JSON-RPC requests and responses for all CCW-MCP tools.

## 1. capsule/create

Create a new counterfactual capsule.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "capsule/create",
    "arguments": {
      "workspace": "/home/user/project",
      "base": "/home/user/project",
      "clock_offset_sec": 0,
      "env_whitelist": ["PATH", "PYTHONPATH", "HOME"]
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "capsule_id": "cap_1699999999999",
    "mount": "/tmp/ccw-mcp-xxxxx/overlay/merged",
    "clock": "2024-01-01T00:00:00.000000+00:00"
  }
}
```

## 2. capsule/exec

Execute a command in the capsule.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "capsule/exec",
    "arguments": {
      "capsule_id": "cap_1699999999999",
      "cmd": ["python", "-m", "pytest", "tests/"],
      "cwd": null,
      "timeout_ms": 300000,
      "stdin": null
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "exit_code": 0,
    "stdout": "===== test session starts =====\n...",
    "stderr": "",
    "usage": {
      "cpu_ms": 1250,
      "rss_max_kb": 45678,
      "io_read_kb": 1024,
      "io_write_kb": 512
    },
    "touched": {
      "read": ["tests/test_foo.py", "src/module.py"],
      "written": [".pytest_cache/", "__pycache__/"]
    }
  }
}
```

## 3. capsule/diff

Get diff of changes in the capsule.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "capsule/diff",
    "arguments": {
      "capsule_id": "cap_1699999999999",
      "format": "unified"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "summary": {
      "added": 15,
      "deleted": 3,
      "modified": 12
    },
    "diff": "--- src/module.py\n+++ src/module.py\n@@ -10,7 +10,7 @@\n..."
  }
}
```

## 4. capsule/witness

Create a witness package from the capsule.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "capsule/witness",
    "arguments": {
      "capsule_id": "cap_1699999999999",
      "compress": "zstd",
      "include_blobs": true
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "witness_id": "wit_1700000000000",
    "path": "/home/user/.ccw-mcp/witnesses/wit_1700000000000",
    "root_hash": "blake3:abc123...",
    "size_bytes": 4567
  }
}
```

## 5. capsule/replay

Replay a witness package.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "capsule/replay",
    "arguments": {
      "witness_id": "wit_1700000000000"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "replay_ok": true,
    "root_hash": "blake3:abc123...",
    "metrics": {
      "cpu_ms": 0,
      "rss_max_kb": 0
    }
  }
}
```

## 6. capsule/promote

Promote capsule changes to real filesystem.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "tools/call",
  "params": {
    "name": "capsule/promote",
    "arguments": {
      "capsule_id": "cap_1699999999999",
      "policies": ["baseline", "strict"],
      "dry_run": false
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "result": {
    "promoted": true,
    "applied": ["src/module.py", "tests/test_new.py"],
    "policy_report": {
      "passed": true,
      "tests_ok": true,
      "replay_ok": true,
      "resource_ok": true,
      "paths_ok": true,
      "deny_paths": [],
      "resource_violations": [],
      "test_failures": [],
      "details": "All checks passed"
    }
  }
}
```

## 7. policy/set

Set or update a policy.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "policy/set",
    "arguments": {
      "name": "custom",
      "rules": {
        "max_rss_mb": 2048,
        "max_cpu_ms": 120000,
        "deny_paths": ["~/.ssh/*", "~/.aws/*", "/etc/*"],
        "require_tests": ["uv run pytest -q", "uv run mypy ."],
        "require_replay_ok": true
      }
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "result": {
    "ok": true
  }
}
```

## 8. capsule/deltamin

Find minimal change set that reproduces a failure.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 8,
  "method": "tools/call",
  "params": {
    "name": "capsule/deltamin",
    "arguments": {
      "capsule_id": "cap_1699999999999",
      "target_cmd": ["pytest", "tests/test_failing.py"],
      "failure_predicate": "exit_code",
      "budget_ms": 120000
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 8,
  "result": {
    "minimal_patch": "--- src/critical.py\n+++ src/critical.py\n...",
    "replay_ok": true,
    "root_hash": "blake3:def456..."
  }
}
```

## 9. capsule/commutativity

Analyze change commutativity.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 9,
  "method": "tools/call",
  "params": {
    "name": "capsule/commutativity",
    "arguments": {
      "capsule_id": "cap_1699999999999"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 9,
  "result": {
    "independent_sets": [
      ["src/module_a.py", "tests/test_a.py"],
      ["src/module_b.py", "tests/test_b.py"],
      ["docs/README.md"]
    ],
    "conflict_pairs": [
      ["src/shared.py", "src/module_a.py"],
      ["src/shared.py", "src/module_b.py"]
    ]
  }
}
```

## 10. tools/list

List all available tools.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/list",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "result": {
    "tools": [
      {
        "name": "capsule/create",
        "description": "Create a new capsule (counterfactual environment)",
        "inputSchema": { "..." }
      },
      {
        "name": "capsule/exec",
        "description": "Execute command in capsule",
        "inputSchema": { "..." }
      }
    ]
  }
}
```

## Error Response Example

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "Capsule cap_invalid not found"
  }
}
```
