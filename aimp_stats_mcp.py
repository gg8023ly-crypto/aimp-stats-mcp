from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from io import BufferedIOBase
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8765"
PROTOCOL_VERSION = "2025-06-18"


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]


def enum_schema(values: list[str], default: str | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string", "enum": values}
    if default is not None:
        schema["default"] = default
    return schema


TOOLS: list[Tool] = [
    Tool(
        name="get_sync_status",
        description="查询 AIMP 用量统计系统最近一次同步状态、日志 ID、读取/匹配数量和统计时区。",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    Tool(
        name="get_usage_overview",
        description="查询指定时间范围的总览统计，包括总金额、总 Token、缓存 Token、调用次数和 Top5 部门/人员/模型。",
        input_schema={
            "type": "object",
            "properties": {
                "period": enum_schema(["today", "yesterday", "before_yesterday", "3d", "7d", "30d"], "today"),
                "metric": enum_schema(["amount", "tokens"], "amount"),
            },
            "additionalProperties": False,
        },
    ),
    Tool(
        name="get_usage_ranking",
        description="查询人员、部门、职位或模型排行。支持按金额或 Token 排序，部门/职位可查询总量或人均。",
        input_schema={
            "type": "object",
            "properties": {
                "kind": enum_schema(["person", "department", "position", "model"], "person"),
                "period": enum_schema(["today", "yesterday", "before_yesterday", "3d", "7d", "30d"], "today"),
                "metric": enum_schema(["amount", "tokens"], "amount"),
                "sort": enum_schema(["total", "average"], "total"),
                "limit": {"type": "integer", "minimum": 0, "maximum": 10000, "default": 10},
                "department": {"type": "string", "description": "仅 kind=person 时可选，用于按部门筛选。"},
            },
            "required": ["kind"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="get_person_usage",
        description="查询某个 NewAPI username 的个人用量详情、每日趋势和模型分布。",
        input_schema={
            "type": "object",
            "properties": {
                "username": {"type": "string", "minLength": 1},
                "period": enum_schema(["today", "yesterday", "before_yesterday", "3d", "7d", "30d"], "30d"),
            },
            "required": ["username"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="get_drilldown_people",
        description="按部门、职位或模型下钻查询对应人员用量明细。",
        input_schema={
            "type": "object",
            "properties": {
                "kind": enum_schema(["department", "position", "model"], "department"),
                "value": {"type": "string", "minLength": 1},
                "period": enum_schema(["today", "yesterday", "before_yesterday", "3d", "7d", "30d"], "30d"),
                "metric": enum_schema(["amount", "tokens"], "amount"),
                "limit": {"type": "integer", "minimum": 0, "maximum": 10000, "default": 100},
            },
            "required": ["kind", "value"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="get_unmatched_users",
        description="查询有用量日志但尚未匹配到花名册的 NewAPI 用户。",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
]


class AimpStatsClient:
    def __init__(self, base_url: str, token: str | None = None, timeout: float = 20):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = urllib.parse.urlencode(
            {key: value for key, value in (params or {}).items() if value not in (None, "")}
        )
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"AIMP stats API returned HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not connect to AIMP stats API at {self.base_url}: {exc.reason}") from exc


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.input_schema,
        }
        for tool in TOOLS
    ]


def call_tool(client: AimpStatsClient, name: str, arguments: dict[str, Any] | None) -> Any:
    args = arguments or {}
    if name == "get_sync_status":
        return client.get("/api/sync-status")
    if name == "get_usage_overview":
        return client.get("/api/overview", {"period": args.get("period", "today"), "metric": args.get("metric", "amount")})
    if name == "get_usage_ranking":
        return client.get(
            "/api/ranking",
            {
                "kind": args.get("kind", "person"),
                "period": args.get("period", "today"),
                "metric": args.get("metric", "amount"),
                "sort": args.get("sort", "total"),
                "limit": args.get("limit", 10),
                "department": args.get("department"),
            },
        )
    if name == "get_person_usage":
        username = require_arg(args, "username")
        return client.get("/api/person", {"username": username, "period": args.get("period", "30d")})
    if name == "get_drilldown_people":
        return client.get(
            "/api/drilldown",
            {
                "kind": args.get("kind", "department"),
                "value": require_arg(args, "value"),
                "period": args.get("period", "30d"),
                "metric": args.get("metric", "amount"),
                "limit": args.get("limit", 100),
            },
        )
    if name == "get_unmatched_users":
        return client.get("/api/unmatched")
    raise ValueError(f"Unknown tool: {name}")


def require_arg(args: dict[str, Any], key: str) -> Any:
    value = args.get(key)
    if value in (None, ""):
        raise ValueError(f"{key} is required")
    return value


def json_text_result(data: Any, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(data, ensure_ascii=False, indent=2),
            }
        ],
        "isError": is_error,
    }


def response(message_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def error_response(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def handle_message(client: AimpStatsClient, message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    message_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        requested_version = params.get("protocolVersion") or PROTOCOL_VERSION
        return response(
            message_id,
            {
                "protocolVersion": requested_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "aimp-stats", "version": "0.1.0"},
            },
        )
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return response(message_id, {})
    if method == "tools/list":
        return response(message_id, {"tools": tool_definitions()})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            result = call_tool(client, name, arguments)
            return response(message_id, json_text_result(result))
        except Exception as exc:
            return response(message_id, json_text_result({"error": str(exc)}, is_error=True))
    if method == "resources/list":
        return response(message_id, {"resources": []})
    if method == "prompts/list":
        return response(message_id, {"prompts": []})
    return error_response(message_id, -32601, f"Method not found: {method}")


def read_mcp_message(input_buffer: BufferedIOBase) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    saw_header = False

    while True:
        line = input_buffer.readline()
        if line == b"":
            return None
        stripped = line.strip()
        if not stripped and not saw_header:
            continue
        if stripped.startswith(b"{"):
            return json.loads(stripped.decode("utf-8"))
        if not stripped:
            break
        saw_header = True
        try:
            name, value = line.decode("ascii").split(":", 1)
        except ValueError as exc:
            raise ValueError(f"Invalid MCP header line: {line!r}") from exc
        headers[name.strip().lower()] = value.strip()

    if "content-length" not in headers:
        raise ValueError("Missing Content-Length header")
    try:
        length = int(headers["content-length"])
    except ValueError as exc:
        raise ValueError(f"Invalid Content-Length: {headers['content-length']}") from exc
    if length < 0:
        raise ValueError("Content-Length must be non-negative")

    body = input_buffer.read(length)
    if len(body) != length:
        raise EOFError(f"Expected {length} bytes, received {len(body)}")
    return json.loads(body.decode("utf-8"))


def write_mcp_message(output_buffer: BufferedIOBase, message: dict[str, Any]) -> None:
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    output_buffer.write(header + body)
    output_buffer.flush()


def serve(
    client: AimpStatsClient,
    input_buffer: BufferedIOBase | None = None,
    output_buffer: BufferedIOBase | None = None,
) -> None:
    input_buffer = input_buffer or sys.stdin.buffer
    output_buffer = output_buffer or sys.stdout.buffer

    while True:
        try:
            message = read_mcp_message(input_buffer)
            if message is None:
                break
            outgoing = handle_message(client, message)
        except json.JSONDecodeError as exc:
            outgoing = error_response(None, -32700, f"Parse error: {exc}")
        except Exception as exc:
            outgoing = error_response(None, -32603, f"Internal error: {exc}")
        if outgoing is None:
            continue
        write_mcp_message(output_buffer, outgoing)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only MCP server for AIMP usage statistics.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("AIMP_STATS_BASE_URL", DEFAULT_BASE_URL),
        help="AIMP stats web base URL. Default: AIMP_STATS_BASE_URL or http://127.0.0.1:8765",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("AIMP_STATS_API_TOKEN"),
        help="Optional bearer token for future read API authentication.",
    )
    parser.add_argument("--timeout", type=float, default=float(os.getenv("AIMP_STATS_API_TIMEOUT", "20")))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    serve(AimpStatsClient(args.base_url, args.token, args.timeout))


if __name__ == "__main__":
    main()
