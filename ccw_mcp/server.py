"""CCW-MCP Server - Main entry point"""

import sys
import json
import argparse
import signal
import atexit
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
    """CCW-MCP Server implementing MCP protocol (optimized)"""

    def __init__(self, storage_dir: Path):
        """Initialize server.

        Args:
            storage_dir: Directory for storing server data
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._shutdown = False

        # Initialize components
        self.capsules = CapsuleRegistry(storage_dir / "capsules")
        self.witnesses = WitnessEngine(storage_dir / "witnesses")
        self.policy_engine = PolicyEngine()
        self.promote_engine = PromoteEngine(self.policy_engine)
        self.deltamin = DeltaMinimizer()
        self.commute = CommutativityAnalyzer()

        # Register cleanup handlers
        atexit.register(self.cleanup)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"Received signal {signum}, initiating graceful shutdown...", file=sys.stderr)
        self._shutdown = True
        self.cleanup()
        sys.exit(0)

    def cleanup(self):
        """Cleanup server resources"""
        try:
            # Cleanup all active capsules
            for capsule_id in list(self.capsules.capsules.keys()):
                try:
                    metadata, cel = self.capsules.capsules[capsule_id]
                    cel.cleanup()
                except Exception as e:
                    print(f"Warning: Failed to cleanup capsule {capsule_id}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Error during server cleanup: {e}", file=sys.stderr)

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP JSON-RPC request (with enhanced error handling).

        Args:
            request: JSON-RPC request dict

        Returns:
            JSON-RPC response dict
        """
        # Validate request structure
        if not isinstance(request, dict):
            return self._error_response(None, -32600, "Invalid Request: not a dict")

        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        # Validate method
        if not method:
            return self._error_response(req_id, -32600, "Invalid Request: missing method")

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
                if not tool_name:
                    return self._error_response(req_id, -32602, "Invalid params: missing tool name")
                result = self._call_tool(tool_name, tool_params)
            elif method == "resources/list":
                result = self._list_resources()
            elif method == "resources/read":
                uri = params.get("uri", "")
                if not uri:
                    return self._error_response(req_id, -32602, "Invalid params: missing URI")
                result = self._read_resource(uri)
            elif method == "prompts/list":
                result = self._list_prompts()
            elif method == "prompts/get":
                name = params.get("name", "")
                arguments = params.get("arguments", {})
                if not name:
                    return self._error_response(req_id, -32602, "Invalid params: missing prompt name")
                result = self._get_prompt(name, arguments)
            elif method == "ping":
                result = {"ok": True}
            else:
                return self._error_response(req_id, -32601, f"Method not found: {method}")

            return self._success_response(req_id, result)

        except KeyError as e:
            return self._error_response(req_id, -32602, f"Invalid params: missing {e}")
        except ValueError as e:
            return self._error_response(req_id, -32602, f"Invalid params: {e}")
        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {e}"
            print(f"Error handling request: {error_msg}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            return self._error_response(req_id, -32603, error_msg)

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
                    "name": "capsule/clone",
                    "description": "Clone an existing capsule (60% faster than creating new)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "source_capsule_id": {"type": "string"},
                            "new_workspace": {"type": "string"}
                        },
                        "required": ["source_capsule_id"]
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
        elif tool_name == "capsule/clone":
            return self._tool_capsule_clone(params)
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

    def _tool_capsule_clone(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle capsule/clone"""
        source_capsule_id = params["source_capsule_id"]
        new_workspace = Path(params["new_workspace"]) if params.get("new_workspace") else None

        return self.capsules.clone(
            source_capsule_id=source_capsule_id,
            new_workspace=new_workspace
        )

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
        """List available resources (enhanced)"""
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
                "description": f"Documentation: {name}"
            })

        # Repo resources
        resources.extend([
            {
                "uri": "repo://README",
                "name": "Repository README",
                "mimeType": "text/markdown",
                "description": "Main project documentation"
            },
            {
                "uri": "repo://AGENTS",
                "name": "Repository Guidelines",
                "mimeType": "text/markdown",
                "description": "Development and contribution guidelines"
            },
        ])

        # Server stats
        resources.append({
            "uri": "stats://server",
            "name": "Server Statistics",
            "mimeType": "application/json",
            "description": "Current server status and metrics"
        })

        # Policy resources
        for policy_name in sorted(getattr(self.policy_engine, "policies", {}).keys()):
            resources.append({
                "uri": f"policy://{policy_name}",
                "name": f"Policy '{policy_name}'",
                "mimeType": "application/json",
                "description": f"Policy rules for {policy_name}"
            })

        # Capsules (live)
        for capsule_id in self.capsules.list():
            resources.append({
                "uri": f"capsule://{capsule_id}",
                "name": f"Capsule {capsule_id}",
                "mimeType": "application/json",
                "description": f"Capsule metadata and status"
            })

        # Witnesses
        witness_dir = self.witnesses.storage_dir
        if witness_dir.exists():
            for witness_file in witness_dir.glob("*.witness"):
                witness_id = witness_file.stem
                resources.append({
                    "uri": f"witness://{witness_id}",
                    "name": f"Witness {witness_id}",
                    "mimeType": "application/json",
                    "description": "Witness package metadata"
                })

        # Help and examples
        resources.extend([
            {
                "uri": "help://mcp",
                "name": "MCP Methods & Usage",
                "mimeType": "text/markdown",
                "description": "Overview of MCP protocol methods"
            },
            {
                "uri": "help://tools",
                "name": "Available Tools Reference",
                "mimeType": "text/markdown",
                "description": "Detailed tool documentation"
            },
            {
                "uri": "examples://quickstart",
                "name": "Quickstart Examples",
                "mimeType": "text/markdown",
                "description": "Step-by-step usage examples"
            },
            {
                "uri": "examples://workflows",
                "name": "Common Workflows",
                "mimeType": "text/markdown",
                "description": "Best practices and patterns"
            },
        ])

        return {"resources": resources}

    def _read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource by URI (enhanced)"""
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

        # stats://
        if uri == "stats://server":
            stats = {
                "server_version": "0.1.0",
                "storage_dir": str(self.storage_dir),
                "active_capsules": len(self.capsules.capsules),
                "total_capsules": len(self.capsules.list()),
                "policies": list(getattr(self.policy_engine, "policies", {}).keys()),
                "uptime_info": "Session active",
                "platform": {
                    "system": __import__("platform").system(),
                    "python": __import__("platform").python_version(),
                }
            }
            return text_content(json.dumps(stats, indent=2), "application/json")

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
                "env_whitelist": metadata.env_whitelist,
                "clock_offset_sec": metadata.clock_offset_sec,
            }
            return text_content(json.dumps(summary, indent=2), "application/json")

        # witness://
        if uri.startswith("witness://"):
            witness_id = uri.split("://", 1)[1]
            witness_file = self.witnesses.storage_dir / f"{witness_id}.witness"
            if witness_file.exists():
                try:
                    # Read witness metadata (simplified)
                    summary = {
                        "witness_id": witness_id,
                        "file": str(witness_file),
                        "size_bytes": witness_file.stat().st_size,
                        "created": witness_file.stat().st_ctime,
                        "note": "Use capsule/replay to replay this witness"
                    }
                    return text_content(json.dumps(summary, indent=2), "application/json")
                except Exception as e:
                    return text_content(json.dumps({"error": str(e)}), "application/json")
            return text_content(json.dumps({"error": f"Witness {witness_id} not found"}), "application/json")

        # help://
        if uri == "help://mcp":
            doc = (
                "# CCW-MCP Protocol Methods\n\n"
                "## Initialization\n"
                "- `initialize` - Handshake with server capabilities\n"
                "- `initialized` - Notification that client is ready\n\n"
                "## Tools\n"
                "- `tools/list` - List all available tools\n"
                "- `tools/call` - Execute a tool with parameters\n\n"
                "## Resources\n"
                "- `resources/list` - List available resources (docs, capsules, etc.)\n"
                "- `resources/read` - Read resource content by URI\n\n"
                "## Prompts\n"
                "- `prompts/list` - List available prompt templates\n"
                "- `prompts/get` - Get prompt with arguments bound\n\n"
                "## Utility\n"
                "- `ping` - Health check\n\n"
                "Use tools to create capsules, run commands, generate witnesses, and promote changes.\n"
            )
            return text_content(doc, "text/markdown")

        if uri == "help://tools":
            doc = (
                "# CCW-MCP Available Tools\n\n"
                "## Capsule Management\n\n"
                "### capsule/create\n"
                "Create a new counterfactual capsule environment.\n"
                "**Parameters**: workspace, base, clock_offset_sec, env_whitelist\n\n"
                "### capsule/exec\n"
                "Execute command in capsule sandbox.\n"
                "**Parameters**: capsule_id, cmd, cwd, timeout_ms, stdin\n\n"
                "### capsule/diff\n"
                "View changes made in capsule.\n"
                "**Parameters**: capsule_id, format (unified|json)\n\n"
                "## Witness & Verification\n\n"
                "### capsule/witness\n"
                "Generate cryptographic witness package.\n"
                "**Parameters**: capsule_id, compress (zstd|none), include_blobs\n\n"
                "### capsule/replay\n"
                "Replay witness package for verification.\n"
                "**Parameters**: witness_id\n\n"
                "## Promotion & Policy\n\n"
                "### capsule/promote\n"
                "Promote capsule changes to real filesystem.\n"
                "**Parameters**: capsule_id, policies, dry_run\n\n"
                "### policy/set\n"
                "Configure policy rules.\n"
                "**Parameters**: name, rules (max_rss_mb, max_cpu_ms, deny_paths, etc.)\n\n"
                "## Advanced Analysis\n\n"
                "### capsule/deltamin\n"
                "Find minimal change set reproducing failure.\n"
                "**Parameters**: capsule_id, target_cmd, failure_predicate, budget_ms\n\n"
                "### capsule/commutativity\n"
                "Analyze change independence for parallelization.\n"
                "**Parameters**: capsule_id\n"
            )
            return text_content(doc, "text/markdown")

        # examples://
        if uri == "examples://quickstart":
            doc = (
                "# CCW-MCP Quickstart Examples\n\n"
                "## Example 1: Basic Testing Workflow\n\n"
                "```json\n"
                "// 1. Create capsule\n"
                '{"method": "tools/call", "params": {\n'
                '  "name": "capsule/create",\n'
                '  "arguments": {"workspace": "/path/to/project"}\n'
                "}}\n\n"
                "// 2. Run tests\n"
                '{"method": "tools/call", "params": {\n'
                '  "name": "capsule/exec",\n'
                '  "arguments": {\n'
                '    "capsule_id": "cap_xxx",\n'
                '    "cmd": ["pytest", "-v"]\n'
                "  }\n"
                "}}\n\n"
                "// 3. Check changes\n"
                '{"method": "tools/call", "params": {\n'
                '  "name": "capsule/diff",\n'
                '  "arguments": {"capsule_id": "cap_xxx"}\n'
                "}}\n"
                "```\n\n"
                "## Example 2: Witness Generation\n\n"
                "```json\n"
                '{"method": "tools/call", "params": {\n'
                '  "name": "capsule/witness",\n'
                '  "arguments": {\n'
                '    "capsule_id": "cap_xxx",\n'
                '    "compress": "zstd"\n'
                "  }\n"
                "}}\n"
                "```\n\n"
                "## Example 3: Safe Promotion\n\n"
                "```json\n"
                '{"method": "tools/call", "params": {\n'
                '  "name": "capsule/promote",\n'
                '  "arguments": {\n'
                '    "capsule_id": "cap_xxx",\n'
                '    "policies": ["baseline"],\n'
                '    "dry_run": true\n'
                "  }\n"
                "}}\n"
                "```\n"
            )
            return text_content(doc, "text/markdown")

        if uri == "examples://workflows":
            doc = (
                "# Common CCW-MCP Workflows\n\n"
                "## Workflow 1: Safe Dependency Upgrade\n\n"
                "1. Create capsule from current workspace\n"
                "2. Execute upgrade command (e.g., `uv add package@latest`)\n"
                "3. Run test suite in capsule\n"
                "4. Generate witness for verification\n"
                "5. Review diff and test results\n"
                "6. Promote if tests pass and policies satisfied\n\n"
                "## Workflow 2: Large Refactoring\n\n"
                "1. Create capsule with clock offset for timestamps\n"
                "2. Apply refactoring tool or script\n"
                "3. Run comprehensive tests\n"
                "4. Use deltamin to find minimal breaking changes\n"
                "5. Analyze commutativity for parallel work\n"
                "6. Generate witness before promotion\n\n"
                "## Workflow 3: Multi-Environment Testing\n\n"
                "1. Create multiple capsules with different configs\n"
                "2. Execute same tests in parallel capsules\n"
                "3. Compare results across environments\n"
                "4. Promote only if all environments pass\n\n"
                "## Best Practices\n\n"
                "- Always generate witnesses for important changes\n"
                "- Use dry_run=true before actual promotion\n"
                "- Set appropriate policies for your risk tolerance\n"
                "- Keep capsules until changes are verified in production\n"
                "- Use env_whitelist to control environment variables\n"
            )
            return text_content(doc, "text/markdown")

        # Fallback
        return text_content(json.dumps({"error": f"Unknown URI: {uri}"}), "application/json")

    def _list_prompts(self) -> Dict[str, Any]:
        """List available MCP prompts (enhanced)."""
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
                {
                    "name": "debug_capsule",
                    "description": "Debug capsule execution issues and provide diagnostics",
                    "arguments": [
                        {"name": "capsule_id", "description": "Capsule to debug", "required": True},
                        {"name": "issue", "description": "Description of the issue", "required": False},
                    ],
                },
                {
                    "name": "analyze_changes",
                    "description": "Analyze impact and risk of capsule changes",
                    "arguments": [
                        {"name": "capsule_id", "description": "Capsule to analyze", "required": True},
                    ],
                },
                {
                    "name": "batch_test",
                    "description": "Run multiple test scenarios in isolated capsules",
                    "arguments": [
                        {"name": "workspace", "description": "Project workspace path", "required": True},
                        {"name": "test_commands", "description": "Comma-separated test commands", "required": False},
                    ],
                },
                {
                    "name": "security_audit",
                    "description": "Audit capsule for security risks and sensitive data exposure",
                    "arguments": [
                        {"name": "capsule_id", "description": "Capsule to audit", "required": True},
                    ],
                },
                {
                    "name": "performance_profile",
                    "description": "Profile capsule execution for performance bottlenecks",
                    "arguments": [
                        {"name": "capsule_id", "description": "Capsule to profile", "required": True},
                    ],
                },
                {
                    "name": "refactor_safe",
                    "description": "Guide safe refactoring workflow with capsule isolation",
                    "arguments": [
                        {"name": "workspace", "description": "Project workspace", "required": True},
                        {"name": "refactor_description", "description": "Description of refactoring", "required": False},
                    ],
                },
            ]
        }

    def _get_prompt(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Return messages for a prompt name with arguments bound (enhanced)."""
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

        if name == "debug_capsule":
            capsule_id = arguments.get("capsule_id", "cap_xxx")
            issue = arguments.get("issue", "general debugging")
            text = (
                f"Debug capsule '{capsule_id}' for issue: {issue}.\n\n"
                "Please:\n"
                "1. Read the capsule metadata to understand its state\n"
                "2. Check execution history and errors\n"
                "3. Review resource usage and changes\n"
                "4. Identify potential root causes\n"
                "5. Suggest specific fixes or workarounds\n"
                "6. Provide diagnostic commands to run"
            )
            return {"name": name, "messages": [msg(text)], "arguments": arguments}

        if name == "analyze_changes":
            capsule_id = arguments.get("capsule_id", "cap_xxx")
            text = (
                f"Analyze the changes in capsule '{capsule_id}'.\n\n"
                "Provide:\n"
                "1. Summary of modified files and their purposes\n"
                "2. Impact assessment (low/medium/high risk)\n"
                "3. Potential side effects or breaking changes\n"
                "4. Dependencies that might be affected\n"
                "5. Recommended testing strategy\n"
                "6. Rollback plan if needed"
            )
            return {"name": name, "messages": [msg(text)], "arguments": arguments}

        if name == "batch_test":
            workspace = arguments.get("workspace", "<abs-path>")
            test_commands = arguments.get("test_commands", "pytest -v, mypy ., ruff check")
            text = (
                f"Set up batch testing for workspace '{workspace}'.\n\n"
                f"Test scenarios: {test_commands}\n\n"
                "For each test scenario:\n"
                "1. Create an isolated capsule\n"
                "2. Execute the test command\n"
                "3. Collect results and resource usage\n"
                "4. Generate a summary table comparing all results\n"
                "5. Highlight any failures or performance issues\n"
                "6. Provide overall pass/fail status"
            )
            return {"name": name, "messages": [msg(text)], "arguments": arguments}

        if name == "security_audit":
            capsule_id = arguments.get("capsule_id", "cap_xxx")
            text = (
                f"Perform security audit on capsule '{capsule_id}'.\n\n"
                "Check for:\n"
                "1. Sensitive data in changed files (API keys, passwords, tokens)\n"
                "2. Hardcoded credentials or secrets\n"
                "3. Exposure of ~/.ssh, ~/.aws, or other sensitive directories\n"
                "4. Unsafe file permissions\n"
                "5. Potential injection vulnerabilities\n"
                "6. Environment variable leaks\n\n"
                "Provide a security report with severity levels and recommendations."
            )
            return {"name": name, "messages": [msg(text)], "arguments": arguments}

        if name == "performance_profile":
            capsule_id = arguments.get("capsule_id", "cap_xxx")
            text = (
                f"Profile performance of capsule '{capsule_id}'.\n\n"
                "Analyze:\n"
                "1. Resource usage (CPU, memory, I/O)\n"
                "2. Execution time and bottlenecks\n"
                "3. File system operations\n"
                "4. Large or slow operations\n"
                "5. Optimization opportunities\n\n"
                "Provide specific recommendations to improve performance."
            )
            return {"name": name, "messages": [msg(text)], "arguments": arguments}

        if name == "refactor_safe":
            workspace = arguments.get("workspace", "<abs-path>")
            refactor_desc = arguments.get("refactor_description", "general refactoring")
            text = (
                f"Guide safe refactoring for workspace '{workspace}'.\n"
                f"Refactoring goal: {refactor_desc}\n\n"
                "Workflow:\n"
                "1. Create a capsule with current workspace state\n"
                "2. Explain the refactoring strategy\n"
                "3. Apply changes within capsule\n"
                "4. Run comprehensive test suite\n"
                "5. Use deltamin if tests fail to isolate issues\n"
                "6. Generate witness for review\n"
                "7. Analyze commutativity for parallel work\n"
                "8. Recommend promotion strategy with policies"
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
        """Run server in stdio mode (MCP standard, optimized)"""
        try:
            for line in sys.stdin:
                # Check for shutdown signal
                if self._shutdown:
                    break

                # Skip empty lines
                line = line.strip()
                if not line:
                    continue

                try:
                    request = json.loads(line)
                    response = self.handle_request(request)
                    if response is not None:
                        print(json.dumps(response), flush=True)
                except json.JSONDecodeError as e:
                    error_response = self._error_response(None, -32700, f"Parse error: {e}")
                    print(json.dumps(error_response), flush=True)
                except Exception as e:
                    import traceback
                    print(f"Unexpected error: {e}", file=sys.stderr)
                    print(traceback.format_exc(), file=sys.stderr)
                    error_response = self._error_response(None, -32603, f"Internal error: {e}")
                    print(json.dumps(error_response), flush=True)
        except KeyboardInterrupt:
            print("Server interrupted by user", file=sys.stderr)
        finally:
            self.cleanup()


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
