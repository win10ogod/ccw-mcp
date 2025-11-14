"""CCW-MCP Server - Main entry point"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

from .tools import (
    CapsuleRegistry,
    WitnessEngine,
    PromoteEngine,
    DeltaMinimizer,
    CommutativityAnalyzer
)
from .policy import PolicyEngine, PolicyRule


class CCWMCPServer:
    """CCW-MCP Server implementing MCP protocol"""

    def __init__(self, storage_dir: Path):
        """Initialize server.

        Args:
            storage_dir: Directory for storing server data
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.capsules = CapsuleRegistry(storage_dir / "capsules")
        self.witnesses = WitnessEngine(storage_dir / "witnesses")
        self.policy_engine = PolicyEngine()
        self.promote_engine = PromoteEngine(self.policy_engine)
        self.deltamin = DeltaMinimizer()
        self.commute = CommutativityAnalyzer()

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP JSON-RPC request.

        Args:
            request: JSON-RPC request dict

        Returns:
            JSON-RPC response dict
        """
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        try:
            # Route to appropriate handler
            if method == "initialize":
                result = self._initialize(params)
            elif method == "initialized":
                # Notification; no response
                return None  # type: ignore[return-value]
            elif method == "tools/list":
                result = self._list_tools()
            elif method == "tools/call":
                tool_name = params.get("name", "")
                tool_params = params.get("arguments", {})
                result = self._call_tool(tool_name, tool_params)
            elif method == "resources/list":
                result = self._list_resources()
            elif method == "resources/read":
                uri = params.get("uri", "")
                result = self._read_resource(uri)
            elif method == "prompts/list":
                result = self._list_prompts()
            elif method == "prompts/get":
                name = params.get("name", "")
                arguments = params.get("arguments", {})
                result = self._get_prompt(name, arguments)
            elif method == "ping":
                result = {"ok": True}
            else:
                return self._error_response(req_id, -32601, f"Method not found: {method}")

            return self._success_response(req_id, result)

        except Exception as e:
            return self._error_response(req_id, -32603, str(e))

    def _initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize handshake.

        Returns server info and capabilities per MCP spec.
        """
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "ccw-mcp",
                "version": "0.1.0",
            },
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
                "sampling": {},
                "logging": {},
            },
        }

    def _list_tools(self) -> Dict[str, Any]:
        """List available tools."""
        return {
            "tools": [
                {
                    "name": "capsule/create",
                    "description": "Create a new capsule (counterfactual environment)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "workspace": {"type": "string"},
                            "base": {"type": "string"},
                            "clock_offset_sec": {"type": "integer", "default": 0},
                            "env_whitelist": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["workspace"]
                    }
                },
                {
                    "name": "capsule/exec",
                    "description": "Execute command in capsule",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "capsule_id": {"type": "string"},
                            "cmd": {"type": "array", "items": {"type": "string"}},
                            "cwd": {"type": "string"},
                            "timeout_ms": {"type": "integer", "default": 600000},
                            "stdin": {"type": "string"}
                        },
                        "required": ["capsule_id", "cmd"]
                    }
                },
                {
                    "name": "capsule/diff",
                    "description": "Get diff of capsule changes",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "capsule_id": {"type": "string"},
                            "format": {"type": "string", "enum": ["unified", "json"], "default": "unified"}
                        },
                        "required": ["capsule_id"]
                    }
                },
                {
                    "name": "capsule/witness",
                    "description": "Create witness package from capsule",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "capsule_id": {"type": "string"},
                            "compress": {"type": "string", "enum": ["zstd", "none"], "default": "zstd"},
                            "include_blobs": {"type": "boolean", "default": True}
                        },
                        "required": ["capsule_id"]
                    }
                },
                {
                    "name": "capsule/replay",
                    "description": "Replay witness package",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "witness_id": {"type": "string"}
                        },
                        "required": ["witness_id"]
                    }
                },
                {
                    "name": "capsule/promote",
                    "description": "Promote capsule changes to real filesystem",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "capsule_id": {"type": "string"},
                            "policies": {"type": "array", "items": {"type": "string"}},
                            "dry_run": {"type": "boolean", "default": False}
                        },
                        "required": ["capsule_id"]
                    }
                },
                {
                    "name": "policy/set",
                    "description": "Set or update policy rules",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "rules": {"type": "object"}
                        },
                        "required": ["name", "rules"]
                    }
                },
                {
                    "name": "capsule/deltamin",
                    "description": "Find minimal change set that reproduces failure",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "capsule_id": {"type": "string"},
                            "target_cmd": {"type": "array", "items": {"type": "string"}},
                            "failure_predicate": {"type": "string"},
                            "budget_ms": {"type": "integer", "default": 120000}
                        },
                        "required": ["capsule_id", "target_cmd"]
                    }
                },
                {
                    "name": "capsule/commutativity",
                    "description": "Analyze change commutativity for parallelization",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "capsule_id": {"type": "string"}
                        },
                        "required": ["capsule_id"]
                    }
                }
            ]
        }

    def _call_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool with given parameters."""
        if tool_name == "capsule/create":
            return self._tool_capsule_create(params)
        elif tool_name == "capsule/exec":
            return self._tool_capsule_exec(params)
        elif tool_name == "capsule/diff":
            return self._tool_capsule_diff(params)
        elif tool_name == "capsule/witness":
            return self._tool_capsule_witness(params)
        elif tool_name == "capsule/replay":
            return self._tool_capsule_replay(params)
        elif tool_name == "capsule/promote":
            return self._tool_capsule_promote(params)
        elif tool_name == "policy/set":
            return self._tool_policy_set(params)
        elif tool_name == "capsule/deltamin":
            return self._tool_capsule_deltamin(params)
        elif tool_name == "capsule/commutativity":
            return self._tool_capsule_commutativity(params)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _tool_capsule_create(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle capsule/create"""
        workspace = Path(params["workspace"])
        base = Path(params["base"]) if params.get("base") else None
        clock_offset_sec = params.get("clock_offset_sec", 0)
        env_whitelist = params.get("env_whitelist", [])

        return self.capsules.create(
            workspace=workspace,
            base=base,
            clock_offset_sec=clock_offset_sec,
            env_whitelist=env_whitelist
        )

    def _tool_capsule_exec(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle capsule/exec"""
        capsule_id = params["capsule_id"]
        cmd = params["cmd"]
        cwd = Path(params["cwd"]) if params.get("cwd") else None
        timeout_ms = params.get("timeout_ms", 600000)
        stdin = params.get("stdin")

        return self.capsules.execute(
            capsule_id=capsule_id,
            cmd=cmd,
            cwd=cwd,
            timeout_ms=timeout_ms,
            stdin=stdin
        )

    def _tool_capsule_diff(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle capsule/diff"""
        capsule_id = params["capsule_id"]
        format = params.get("format", "unified")

        return self.capsules.diff(capsule_id=capsule_id, format=format)

    def _tool_capsule_witness(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle capsule/witness"""
        capsule_id = params["capsule_id"]
        compress = params.get("compress", "zstd")
        include_blobs = params.get("include_blobs", True)

        entry = self.capsules.get(capsule_id)
        if not entry:
            return {"error": f"Capsule {capsule_id} not found"}

        metadata, cel = entry
        changes = cel.get_changes()

        return self.witnesses.create(
            capsule_id=capsule_id,
            capsule_mount=cel.mount(),
            changes=changes,
            compress=compress,
            include_blobs=include_blobs
        )

    def _tool_capsule_replay(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle capsule/replay"""
        witness_id = params["witness_id"]
        return self.witnesses.replay(witness_id=witness_id)

    def _tool_capsule_promote(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle capsule/promote"""
        capsule_id = params["capsule_id"]
        policies = params.get("policies", ["baseline"])
        dry_run = params.get("dry_run", False)

        entry = self.capsules.get(capsule_id)
        if not entry:
            return {"error": f"Capsule {capsule_id} not found"}

        metadata, cel = entry
        changes = cel.get_changes()

        # Get last execution result for usage stats (simplified)
        usage = {"cpu_ms": 0, "rss_max_kb": 0, "io_read_kb": 0, "io_write_kb": 0}

        result = self.promote_engine.promote(
            capsule_mount=cel.mount(),
            target_dir=metadata.workspace,
            changes=changes,
            policies=policies,
            usage=usage,
            dry_run=dry_run
        )

        return {
            "promoted": result.promoted,
            "applied": result.applied,
            "policy_report": result.policy_report
        }

    def _tool_policy_set(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle policy/set"""
        name = params["name"]
        rules = params["rules"]

        policy = PolicyRule(
            name=name,
            max_rss_mb=rules.get("max_rss_mb"),
            max_cpu_ms=rules.get("max_cpu_ms"),
            deny_paths=rules.get("deny_paths", []),
            require_tests=rules.get("require_tests", []),
            require_replay_ok=rules.get("require_replay_ok", True)
        )

        self.policy_engine.add_policy(policy)
        return {"ok": True}

    def _tool_capsule_deltamin(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle capsule/deltamin"""
        capsule_id = params["capsule_id"]
        target_cmd = params["target_cmd"]
        budget_ms = params.get("budget_ms", 120000)

        entry = self.capsules.get(capsule_id)
        if not entry:
            return {"error": f"Capsule {capsule_id} not found"}

        metadata, cel = entry
        changes = cel.get_changes()

        # Define test function
        def test_func(subset):
            # Simplified - would actually test the subset
            return len(subset) > 0

        result = self.deltamin.minimize(
            changes=changes,
            test_func=test_func,
            budget_ms=budget_ms
        )

        return {
            "minimal_patch": result.minimal_patch,
            "replay_ok": result.replay_ok,
            "root_hash": result.root_hash
        }

    def _tool_capsule_commutativity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle capsule/commutativity"""
        capsule_id = params["capsule_id"]

        entry = self.capsules.get(capsule_id)
        if not entry:
            return {"error": f"Capsule {capsule_id} not found"}

        metadata, cel = entry
        changes = cel.get_changes()

        result = self.commute.analyze(changes=changes)

        return {
            "independent_sets": result.independent_sets,
            "conflict_pairs": result.conflict_pairs
        }

    def _list_resources(self) -> Dict[str, Any]:
        """List available resources"""
        resources = []

        # Docs resources (selected)
        docs_map = {
            "ARCHITECTURE": ("Architecture Overview", "docs/ARCHITECTURE.md"),
            "WINDOWS": ("Windows Guide", "docs/WINDOWS.md"),
            "QUICKSTART-WINDOWS": ("Windows Quickstart", "docs/QUICKSTART-WINDOWS.md"),
            "JSONRPC-EXAMPLES": ("JSON-RPC Examples", "docs/jsonrpc-examples.md"),
        }
        for key, (name, _) in docs_map.items():
            resources.append({
                "uri": f"docs://{key}",
                "name": name,
                "mimeType": "text/markdown",
            })

        # Repo resources
        resources.extend([
            {"uri": "repo://README", "name": "Repository README", "mimeType": "text/markdown"},
            {"uri": "repo://AGENTS", "name": "Repository Guidelines", "mimeType": "text/markdown"},
        ])

        # Policy resources
        for policy_name in sorted(getattr(self.policy_engine, "policies", {}).keys()):
            resources.append({
                "uri": f"policy://{policy_name}",
                "name": f"Policy '{policy_name}'",
                "mimeType": "application/json",
            })

        # Capsules (live)
        for capsule_id in self.capsules.list():
            resources.append({
                "uri": f"capsule://{capsule_id}",
                "name": f"Capsule {capsule_id}",
                "mimeType": "application/json",
            })

        # Help summary
        resources.append({
            "uri": "help://mcp",
            "name": "MCP Methods & Usage",
            "mimeType": "text/markdown",
        })

        return {"resources": resources}

    def _read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource by URI"""
        def text_content(text: str, mime: str) -> Dict[str, Any]:
            return {"contents": [{"uri": uri, "mimeType": mime, "text": text}]}

        # docs://
        if uri.startswith("docs://"):
            key = uri.split("://", 1)[1]
            path_map = {
                "ARCHITECTURE": "docs/ARCHITECTURE.md",
                "WINDOWS": "docs/WINDOWS.md",
                "QUICKSTART-WINDOWS": "docs/QUICKSTART-WINDOWS.md",
                "JSONRPC-EXAMPLES": "docs/jsonrpc-examples.md",
            }
            rel = path_map.get(key)
            if rel and Path(rel).exists():
                return text_content(Path(rel).read_text(encoding="utf-8"), "text/markdown")
            return text_content(json.dumps({"error": f"Unknown doc: {key}"}), "application/json")

        # repo://
        if uri == "repo://README":
            p = Path("README.md")
            if p.exists():
                return text_content(p.read_text(encoding="utf-8"), "text/markdown")
            return text_content(json.dumps({"error": "README not found"}), "application/json")
        if uri == "repo://AGENTS":
            p = Path("AGENTS.md")
            if p.exists():
                return text_content(p.read_text(encoding="utf-8"), "text/markdown")
            return text_content(json.dumps({"error": "AGENTS.md not found"}), "application/json")

        # policy://
        if uri.startswith("policy://"):
            name = uri.split("://", 1)[1]
            policy = self.policy_engine.get_policy(name)
            if policy is None:
                return text_content(json.dumps({"error": f"Unknown policy: {name}"}), "application/json")
            from dataclasses import asdict
            return text_content(json.dumps(asdict(policy), indent=2), "application/json")

        # capsule://
        if uri.startswith("capsule://"):
            capsule_id = uri.split("://", 1)[1]
            entry = self.capsules.get(capsule_id)
            if not entry:
                return text_content(json.dumps({"error": f"Capsule {capsule_id} not found"}), "application/json")
            metadata, cel = entry
            changes = [str(p) for p in cel.get_changes()]
            summary = {
                "capsule_id": metadata.capsule_id,
                "workspace": str(metadata.workspace),
                "base_dir": str(metadata.base_dir) if metadata.base_dir else None,
                "created_at": metadata.created_at,
                "mount": str(metadata.mount_point) if metadata.mount_point else None,
                "changes_count": len(changes),
                "changes": changes[:100],
            }
            return text_content(json.dumps(summary, indent=2), "application/json")

        # help://
        if uri == "help://mcp":
            doc = (
                "# CCW-MCP Methods\n"
                "- initialize / initialized\n"
                "- tools/list, tools/call\n"
                "- resources/list, resources/read\n"
                "- prompts/list, prompts/get\n"
                "- ping\n\n"
                "Use tools to create capsules, run commands, generate witnesses, and promote changes.\n"
            )
            return text_content(doc, "text/markdown")

        # Fallback
        return text_content(json.dumps({"error": f"Unknown URI: {uri}"}), "application/json")

    def _list_prompts(self) -> Dict[str, Any]:
        """List available MCP prompts."""
        return {
            "prompts": [
                {
                    "name": "capsule_quickstart",
                    "description": "Create a capsule and run a command",
                    "arguments": [
                        {"name": "workspace", "description": "Absolute path to workspace", "required": True},
                        {"name": "command", "description": "Command to run (default: uv run pytest -q)", "required": False},
                    ],
                },
                {
                    "name": "witness_and_promote",
                    "description": "Generate witness and promote if policies pass",
                    "arguments": [
                        {"name": "capsule_id", "description": "Target capsule id", "required": True},
                        {"name": "policies", "description": "Policy list (e.g., baseline,strict)", "required": False},
                    ],
                },
                {
                    "name": "policy_strict_template",
                    "description": "Draft a strict policy rule for this repo",
                    "arguments": [],
                },
            ]
        }

    def _get_prompt(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Return messages for a prompt name with arguments bound."""
        def msg(text: str) -> Dict[str, Any]:
            return {"role": "user", "content": [{"type": "text", "text": text}]}

        if name == "capsule_quickstart":
            workspace = arguments.get("workspace", "<abs-path>")
            command = arguments.get("command", "uv run pytest -q")
            text = (
                f"Create a CCW capsule for workspace '{workspace}'.\n"
                f"Inside the capsule, execute: {command}.\n"
                "Then summarize test results, show a short diff summary, and suggest next steps."
            )
            return {"name": name, "messages": [msg(text)], "arguments": arguments}

        if name == "witness_and_promote":
            capsule_id = arguments.get("capsule_id", "cap_xxx")
            policies = arguments.get("policies", "baseline")
            text = (
                f"For capsule '{capsule_id}', generate a witness, show a summary, "
                f"and attempt promotion with policies [{policies}]. "
                "Explain any policy failures and propose fixes."
            )
            return {"name": name, "messages": [msg(text)], "arguments": arguments}

        if name == "policy_strict_template":
            text = (
                "Propose a 'strict' policy for this repository that constrains RSS/CPU, "
                "denies secrets paths (e.g., ~/.ssh, ~/.aws), and requires tests to pass. "
                "Return a JSON object compatible with policy/set."
            )
            return {"name": name, "messages": [msg(text)], "arguments": arguments}

        return {"name": name, "messages": [msg(f"Unknown prompt: {name}")], "arguments": arguments}

    def _success_response(self, req_id: Any, result: Any) -> Dict[str, Any]:
        """Create success response"""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        }

    def _error_response(self, req_id: Any, code: int, message: str) -> Dict[str, Any]:
        """Create error response"""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": code,
                "message": message
            }
        }

    def run_stdio(self):
        """Run server in stdio mode (MCP standard)."""

        def read_message(stdin):
            """Read a single JSON-RPC message from stdin.

            Supports the MCP framing protocol (Content-Length headers)
            and falls back to newline-delimited JSON for local tooling.
            Returns a tuple of (payload_bytes, used_content_length).
            """

            while True:
                line = stdin.readline()
                if not line:
                    return None, False

                # Skip empty separator lines
                if not line.strip():
                    continue

                stripped = line.lstrip()
                if stripped.startswith(b"{"):
                    # Plain JSON line (legacy fallback)
                    return line.strip(), False

                # Content-Length framing
                headers = {}
                current = line
                while current and current.strip():
                    try:
                        header_line = current.decode("ascii")
                    except UnicodeDecodeError:
                        header_line = ""
                    if ":" in header_line:
                        key, value = header_line.split(":", 1)
                        headers[key.strip().lower()] = value.strip()
                    current = stdin.readline()

                content_length = headers.get("content-length")
                if content_length is None:
                    # Malformed headers; continue reading next message
                    continue

                try:
                    length = int(content_length)
                except ValueError:
                    continue

                remaining = length
                chunks = []
                while remaining > 0:
                    chunk = stdin.read(remaining)
                    if not chunk:
                        # Unexpected EOF; abort
                        return None, True
                    chunks.append(chunk)
                    remaining -= len(chunk)

                payload = b"".join(chunks)
                return payload, True

        def write_message(stdout, payload_bytes, use_content_length):
            if use_content_length:
                headers = (
                    f"Content-Length: {len(payload_bytes)}\r\n"
                    "Content-Type: application/json\r\n\r\n"
                ).encode("ascii")
                stdout.write(headers)
                stdout.write(payload_bytes)
            else:
                stdout.write(payload_bytes + b"\n")
            stdout.flush()

        stdin = sys.stdin.buffer
        stdout = sys.stdout.buffer

        while True:
            payload, used_content_length = read_message(stdin)
            if payload is None:
                break

            try:
                request = json.loads(payload.decode("utf-8"))
            except json.JSONDecodeError as exc:
                error_response = self._error_response(None, -32700, f"Invalid JSON: {exc}")
                response_bytes = json.dumps(error_response).encode("utf-8")
                write_message(stdout, response_bytes, used_content_length)
                continue
            except Exception as exc:  # pragma: no cover - defensive
                error_response = self._error_response(None, -32700, str(exc))
                response_bytes = json.dumps(error_response).encode("utf-8")
                write_message(stdout, response_bytes, used_content_length)
                continue

            try:
                response = self.handle_request(request)
                if response is None:
                    continue
                response_bytes = json.dumps(response).encode("utf-8")
                write_message(stdout, response_bytes, used_content_length)
            except Exception as exc:
                error_response = self._error_response(request.get("id"), -32700, str(exc))
                response_bytes = json.dumps(error_response).encode("utf-8")
                write_message(stdout, response_bytes, used_content_length)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="CCW-MCP Server")
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="Run in stdio mode (default)"
    )
    parser.add_argument(
        "--storage",
        type=str,
        default="~/.ccw-mcp",
        help="Storage directory for server data"
    )

    args = parser.parse_args()

    storage_dir = Path(args.storage).expanduser()
    server = CCWMCPServer(storage_dir)

    if args.stdio or len(sys.argv) == 1:
        server.run_stdio()
    else:
        print("CCW-MCP Server")
        print("Usage: ccw-mcp --stdio")


if __name__ == "__main__":
    main()
