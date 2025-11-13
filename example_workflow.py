#!/usr/bin/env python3
"""Example workflow demonstrating CCW-MCP usage"""

import json
import subprocess
import sys
from pathlib import Path


def send_request(server_proc, method: str, params: dict) -> dict:
    """Send JSON-RPC request to server and get response"""
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }

    # Send request
    server_proc.stdin.write(json.dumps(request) + "\n")
    server_proc.stdin.flush()

    # Read response
    response_line = server_proc.stdout.readline()
    return json.loads(response_line)


def main():
    """Run example workflow"""
    print("CCW-MCP Example Workflow")
    print("=" * 50)

    # Start server
    print("\n1. Starting CCW-MCP server...")
    server = subprocess.Popen(
        ["uv", "run", "ccw-mcp", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    try:
        # Create test workspace
        workspace = Path("./test_workspace")
        workspace.mkdir(exist_ok=True)
        (workspace / "test.txt").write_text("Hello, World!")

        # 2. Create capsule
        print("\n2. Creating capsule...")
        response = send_request(
            server,
            "tools/call",
            {
                "name": "capsule/create",
                "arguments": {
                    "workspace": str(workspace.absolute()),
                    "env_whitelist": ["PATH"]
                }
            }
        )

        capsule_id = response["result"]["capsule_id"]
        print(f"   Created capsule: {capsule_id}")
        print(f"   Mount point: {response['result']['mount']}")

        # 3. Execute command
        print("\n3. Executing command in capsule...")
        response = send_request(
            server,
            "tools/call",
            {
                "name": "capsule/exec",
                "arguments": {
                    "capsule_id": capsule_id,
                    "cmd": ["echo", "Modified content > test.txt && cat test.txt"]
                }
            }
        )

        print(f"   Exit code: {response['result']['exit_code']}")
        print(f"   Output: {response['result']['stdout']}")
        print(f"   Resource usage: {response['result']['usage']}")

        # 4. Get diff
        print("\n4. Getting diff...")
        response = send_request(
            server,
            "tools/call",
            {
                "name": "capsule/diff",
                "arguments": {
                    "capsule_id": capsule_id,
                    "format": "unified"
                }
            }
        )

        print(f"   Changes: {response['result']['summary']}")
        if response['result']['diff']:
            print(f"   Diff:\n{response['result']['diff'][:200]}...")

        # 5. Create witness
        print("\n5. Creating witness package...")
        response = send_request(
            server,
            "tools/call",
            {
                "name": "capsule/witness",
                "arguments": {
                    "capsule_id": capsule_id,
                    "compress": "none",
                    "include_blobs": True
                }
            }
        )

        witness_id = response["result"]["witness_id"]
        print(f"   Witness ID: {witness_id}")
        print(f"   Root hash: {response['result']['root_hash']}")
        print(f"   Size: {response['result']['size_bytes']} bytes")

        # 6. Replay witness
        print("\n6. Replaying witness...")
        response = send_request(
            server,
            "tools/call",
            {
                "name": "capsule/replay",
                "arguments": {
                    "witness_id": witness_id
                }
            }
        )

        print(f"   Replay OK: {response['result']['replay_ok']}")
        print(f"   Hash: {response['result']['root_hash']}")

        # 7. Set policy
        print("\n7. Setting validation policy...")
        response = send_request(
            server,
            "tools/call",
            {
                "name": "policy/set",
                "arguments": {
                    "name": "example",
                    "rules": {
                        "max_rss_mb": 1024,
                        "deny_paths": ["~/.ssh/*"],
                        "require_tests": []
                    }
                }
            }
        )

        print(f"   Policy set: {response['result']['ok']}")

        # 8. Promote (dry run)
        print("\n8. Promoting changes (dry run)...")
        response = send_request(
            server,
            "tools/call",
            {
                "name": "capsule/promote",
                "arguments": {
                    "capsule_id": capsule_id,
                    "policies": ["example"],
                    "dry_run": True
                }
            }
        )

        print(f"   Would promote: {response['result']['promoted']}")
        print(f"   Files to apply: {len(response['result']['applied'])}")
        print(f"   Policy report: {response['result']['policy_report']}")

        # 9. Analyze commutativity
        print("\n9. Analyzing change commutativity...")
        response = send_request(
            server,
            "tools/call",
            {
                "name": "capsule/commutativity",
                "arguments": {
                    "capsule_id": capsule_id
                }
            }
        )

        print(f"   Independent sets: {response['result']['independent_sets']}")
        print(f"   Conflict pairs: {response['result']['conflict_pairs']}")

        print("\n" + "=" * 50)
        print("Example workflow completed successfully!")

    finally:
        # Cleanup
        server.terminate()
        server.wait(timeout=5)

        # Clean test workspace
        import shutil
        if workspace.exists():
            shutil.rmtree(workspace)


if __name__ == "__main__":
    main()
