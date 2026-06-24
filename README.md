# AIMP Stats MCP

Standalone read-only MCP connector for AIMP usage statistics.

## Direct MCP Config

Use this config in Codex, OpenClaw, or another MCP-capable agent:

```json
{
  "mcpServers": {
    "aimp-stats": {
      "command": "python",
      "args": [
        "-c",
        "import sys,urllib.request;url='https://raw.githubusercontent.com/gg8023ly-crypto/aimp-stats-mcp/main/aimp_stats_mcp.py';code=urllib.request.urlopen(url,timeout=20).read();sys.argv=['aimp_stats_mcp.py']+sys.argv[1:];exec(compile(code,url,'exec'),{'__name__':'__main__','__file__':url})",
        "--base-url",
        "http://192.168.0.102:8765"
      ]
    }
  }
}
```

Config link:

```text
https://raw.githubusercontent.com/gg8023ly-crypto/aimp-stats-mcp/main/aimp_stats_mcp.remote.json
```

Script link:

```text
https://raw.githubusercontent.com/gg8023ly-crypto/aimp-stats-mcp/main/aimp_stats_mcp.py
```

The connector only calls the AIMP statistics HTTP API. It does not connect to any database and does not expose write operations.
