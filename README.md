# AIMP Stats MCP

Remote read-only MCP connector for AIMP usage statistics. The preferred endpoint is Streamable HTTP and requires no local Python installation.

## Direct MCP Config

Use this config in OpenClaw or another JSON-configured MCP client:

```json
{
  "mcpServers": {
    "aimp-stats": {
      "url": "http://192.168.0.102:8765/mcp"
    }
  }
}
```

Config link:

```text
https://raw.githubusercontent.com/gg8023ly-crypto/aimp-stats-mcp/main/aimp_stats_mcp.remote.json
```

Codex TOML:

```powershell
codex mcp add aimp-stats --url http://192.168.0.102:8765/mcp
```

```toml
[mcp_servers.aimp-stats]
url = "http://192.168.0.102:8765/mcp"
```

The endpoint exposes read-only statistics tools and no write operations. `aimp_stats_mcp.py` and `aimp_stats_mcp.stdio.json` remain available as a Python-based fallback for clients without Streamable HTTP support.
