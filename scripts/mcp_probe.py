#!/usr/bin/env python3
"""Probe the EGX MCP server (Patrickboules/EGX-MCP) over stdio.

Server source: https://github.com/Patrickboules/EGX-MCP
  - FastMCP server (server.py) exposing EGX stock tools built on the
    `egxpy` library (from egxpy.download import get_OHLCV_data, ...).
  - The workflow clones that repo into ./server_src and installs its
    dependencies (see requirements.txt). egxpy itself is installed from
    the live mirror https://github.com/mmabas77/egxpy (egxpy 1.1.0,
    identical download.py API) because the server's pinned egxpy source
    https://github.com/egxlytics/egxpy.git no longer resolves (HTTP 404)
    and egxpy is not on PyPI.

Launch note: server.py defines the FastMCP app (`mcp = FastMCP("EGX-MCP")`)
but never calls mcp.run() — running `python server.py` exits immediately.
It is therefore started the README's own alternative way, via the MCP CLI
(`mcp run server.py`, console script from mcp[cli]), which imports the
module and serves its FastMCP app over stdio.

This probe, using the official MCP Python SDK client over stdio:
  1. starts the server (`mcp run server.py` in server_src/),
  2. lists its tools  -> results/tools.json (names + descriptions + input schemas),
  3. calls ONE price tool for symbol POUL (Cairo Poultry) — preferring
     `get_last_price`, with the argument taken from the tool's own
     reported input schema — and saves the verbatim response JSON to
     results/probe_result.json and results/probe.md.

On a hard failure it still writes results/probe.md with the error and
exits non-zero.
"""
import asyncio
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = ROOT / "server_src"
SERVER_PY = SERVER_DIR / "server.py"
RESULTS = ROOT / "results"
SYMBOL = "POUL"
PREFERRED_TOOL = "get_last_price"

SERVER_SOURCE = "https://github.com/Patrickboules/EGX-MCP"


def write_probe_md(tool_name, arguments, payload_json, error_text=None):
    lines = [
        "# EGX MCP probe",
        "",
        f"- Server source: {SERVER_SOURCE} (cloned into `server_src/`, run as `server.py` over stdio)",
        "- Server library: egxpy (installed from https://github.com/mmabas77/egxpy — egxpy 1.1.0; "
        "the server's pinned source https://github.com/egxlytics/egxpy.git returns HTTP 404 and egxpy is not on PyPI)",
        f"- Symbol probed: {SYMBOL} (Cairo Poultry)",
        f"- Tool called: `{tool_name}`" if tool_name else "- Tool called: (none — probe failed before the call)",
        f"- Arguments: `{json.dumps(arguments)}`" if arguments is not None else "- Arguments: (none)",
        "",
    ]
    if error_text:
        lines += ["## Error", "", "```", error_text, "```", ""]
    if payload_json:
        lines += ["## Tool response (verbatim JSON)", "", "```json", payload_json, "```", ""]
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "probe.md").write_text("\n".join(lines), encoding="utf-8")


async def run():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    if not SERVER_PY.exists():
        raise FileNotFoundError(f"server not found at {SERVER_PY} — workflow clone step did not run?")

    mcp_cli = Path(sys.executable).parent / "mcp"
    if mcp_cli.exists():
        command, args = str(mcp_cli), ["run", "server.py"]
    else:  # fallback: import the module and run its FastMCP app directly
        command = sys.executable
        args = ["-c", "import server; server.mcp.run(transport='stdio')"]
    params = StdioServerParameters(
        command=command,
        args=args,
        cwd=str(SERVER_DIR),
        env={**os.environ, "PYTHONPATH": str(SERVER_DIR), "PYTHONUNBUFFERED": "1"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=300)
            tools_resp = await asyncio.wait_for(session.list_tools(), timeout=300)
            tools = [
                {"name": t.name, "description": t.description, "inputSchema": t.inputSchema}
                for t in tools_resp.tools
            ]
            RESULTS.mkdir(parents=True, exist_ok=True)
            (RESULTS / "tools.json").write_text(
                json.dumps(tools, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"list_tools returned {len(tools)} tools: {[t['name'] for t in tools]}")

            names = [t["name"] for t in tools]
            if PREFERRED_TOOL in names:
                tool_name = PREFERRED_TOOL
            else:
                tool_name = next((n for n in names if "price" in n.lower()), None)
            if not tool_name:
                raise RuntimeError(f"no price tool found among {names}")

            schema = next(t["inputSchema"] for t in tools if t["name"] == tool_name) or {}
            props = list((schema.get("properties") or {}).keys())
            if not props:
                raise RuntimeError(f"tool {tool_name} reports no input properties: {schema}")
            arguments = {props[0]: SYMBOL}
            print(f"calling {tool_name} with {arguments}")
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments), timeout=900
            )
            payload = result.model_dump_json(indent=2)
            (RESULTS / "probe_result.json").write_text(payload, encoding="utf-8")
            write_probe_md(tool_name, arguments, payload)
            print(f"tool isError={result.isError}")
            print(payload[:2000])
            return


def main():
    try:
        asyncio.run(run())
    except Exception:
        err = traceback.format_exc()
        print(err, file=sys.stderr)
        write_probe_md(None, None, None, error_text=err)
        sys.exit(1)


if __name__ == "__main__":
    main()
