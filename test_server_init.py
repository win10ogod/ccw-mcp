#!/usr/bin/env python3
"""Test server initialization to catch any errors"""

import sys
import traceback
from pathlib import Path

# Test imports
try:
    print("Testing imports...", file=sys.stderr)
    from ccw_mcp.server import CCWMCPServer
    print("✓ Imported CCWMCPServer", file=sys.stderr)
except Exception as e:
    print(f"✗ Failed to import CCWMCPServer: {e}", file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)

# Test server creation
try:
    print("Creating server instance...", file=sys.stderr)
    storage_dir = Path("~/.ccw-mcp-test").expanduser()
    server = CCWMCPServer(storage_dir)
    print("✓ Created server instance", file=sys.stderr)
except Exception as e:
    print(f"✗ Failed to create server: {e}", file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)

# Test initialization request
try:
    print("Testing initialize request...", file=sys.stderr)
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    }
    response = server.handle_request(request)
    print(f"✓ Initialize response: {response}", file=sys.stderr)
except Exception as e:
    print(f"✗ Failed to handle initialize: {e}", file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)

# Test tools/list request
try:
    print("Testing tools/list request...", file=sys.stderr)
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    response = server.handle_request(request)
    print(f"✓ tools/list response has {len(response.get('result', {}).get('tools', []))} tools", file=sys.stderr)
except Exception as e:
    print(f"✗ Failed to handle tools/list: {e}", file=sys.stderr)
    traceback.print_exc()
    sys.exit(1)

print("✓ All tests passed!", file=sys.stderr)
server.cleanup()
