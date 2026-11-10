# egx-mcp-runner

Probes an open-source **MCP server for the Egyptian Exchange (EGX)** from
GitHub Actions, using the COMMANDS-variable runner pattern: edit the
`COMMANDS` repository variable, dispatch the workflow manually
(`workflow_dispatch` only), and read the output from the `results`
artifact uploaded at the end of the run.

- `.github/workflows/run.yml` — Python 3.11, installs `requirements.txt`,
  clones the MCP server into `server_src/`, then runs a step named
  "Run commands" whose run line is exactly `run: ${{ vars.COMMANDS }}`,
  and always uploads `results/` as the `results` artifact.
- `scripts/mcp_probe.py` — the pilot (see below).
- `requirements.txt` — client + server dependencies, with the reasons for
  every pin documented inline.

## The server that was located

**https://github.com/Patrickboules/EGX-MCP** — a FastMCP server exposing
EGX stock data as MCP tools, built on the **egxpy** library.

Evidence (all read from the repo itself):

- `pyproject.toml` declares the dependency `egxpy`, sourced in
  `[tool.uv.sources]` from a git repo, plus `mcp[cli]>=1.26.0`, `bs4`,
  `httpx`. Its `uv.lock` pins egxpy **1.1.0**.
- `server.py` creates `FastMCP("EGX-MCP")` and registers tools including
  `get_last_price(company_ticker)`, `get_live_price(company_ticker)`,
  `get_price_change`, `get_intraday_readings`, `get_risers_overtime`,
  `get_riser_intraday`, `get_current_gold_price`, `get_current_time`,
  `get_timeperiod_date`, plus the resource `egx://companies`.
- `Domain/egx_controller.py` does
  `from egxpy.download import get_OHLCV_data, get_EGX_intraday_data, get_EGXdata`
  and its company dictionary maps `"Cairo Poultry": "POUL"`.
- README: "Live & closing stock prices for EGX-listed companies …
  MCP-compatible — plug directly into Claude Desktop", tech stack lists
  egxpy for "EGX market data (OHLCV, intraday, historical)".

### Other candidates found (and why they were not chosen)

| Repo | Evidence | Verdict |
| --- | --- | --- |
| M-Abdelmegeed/EGX-Data-MCP-Server | FastMCP server, tools `stock_price_egx` / `stock_data_egx`; data via `tradingview_ta` TA_Handler (screener `egypt`, exchange `EGX`) | Real EGX MCP server, but **not** built on egxpy |
| PierreEhab/EGX-MCP-SERVER | FastMCP, deps include `egx>=0.3.0` + `mcp>=1.26,<2` | Index data only (index history / analytics) — no stock price tool for POUL |
| omarswar/egx-server | "MCP server + REST API (FastAPI)"; `requirements.txt` is only fastapi/uvicorn/requests | MCP claim not backed by an MCP dependency |
| armaaar/thndr-mcp | TypeScript toolkit for the Thndr broker (EGX/US/ADX) | Broker account toolkit, not an egxpy market-data server |
| essawy/EGX_MCP | GitHub search-index hit ("Real-time EGX market data as an MCP server", Rust); a hosted version exists at egx-mcp.essawy.workers.dev requiring a Bearer key | Repo itself returns **HTTP 404** now — not verifiable, not installable |
| marcamgad/esis-quant | Quant research system with "its own MCP server written from scratch" | Whole research system, not a standalone EGX data server |

Searches performed — GitHub repository search API and web search, terms:
`EGX MCP`, `egx mcp server`, `egyptian exchange mcp`, `egxmcp`,
`mcp egxpy`, `egxpy mcp`, `egxpy`, `egxpy in:name`,
`EGX MCP server egyptian exchange`, `"egx" "mcp" server github egxpy`.

## Install / launch quirks (all verified, not assumed)

1. **The server's pinned egxpy source is dead.** `uv.lock` / uv sources
   point at `https://github.com/egxlytics/egxpy.git`, which returns
   HTTP 404 today, and `egxpy` is not on PyPI. The pilot installs egxpy
   from the live mirror **https://github.com/mmabas77/egxpy** — egxpy
   **1.1.0** (same version the server pins) whose `egxpy/download.py`
   provides exactly the functions the server imports.
2. **Python version conflict.** The server's `pyproject.toml` says
   `requires-python >=3.14` (its README says 3.10+), so the package
   itself cannot be pip-installed on this runner's Python 3.11. Its
   dependencies are installed directly (`requirements.txt`) and the
   server is run from a plain clone.
3. **`server.py` never calls `mcp.run()`.** Running `python server.py`
   exits immediately with code 0. The server is started the README's own
   alternative way: `mcp run server.py` (the MCP CLI imports the module
   and serves its FastMCP app over stdio).
4. **`mcp` must stay on the 1.x line.** mcp 2.x removed
   `mcp.server.fastmcp`, which the server imports. The author's own
   `uv.lock` pins mcp 1.26.0; `requirements.txt` here pins
   `mcp[cli]>=1.26.0,<2`.
5. **egxpy has an undeclared import.** `egxpy/download.py` does
   `import streamlit`, which egxpy's `setup.py` does not declare —
   streamlit is installed explicitly in `requirements.txt`.
6. **Known upstream bug (not probed):** the server's `get_live_price`
   calls `EGXController.getLivePrice(company_ticker)` but the
   controller's signature is `getLivePrice(todays_date, ticker)`. The
   pilot therefore uses `get_last_price`, whose signature matches.

## The pilot

`COMMANDS` variable:

```
mkdir -p results
set -o pipefail; python scripts/mcp_probe.py 2>&1 | tee results/run.log
```

`scripts/mcp_probe.py` uses the official MCP Python SDK client over
stdio to start the server, then:

- `list_tools` → `results/tools.json` (full tool list: names,
  descriptions, input schemas),
- calls `get_last_price` for **POUL** (Cairo Poultry), taking the
  argument name from the tool's own reported input schema →
  `results/probe_result.json` (verbatim response JSON) and
  `results/probe.md` (server source, tool called, verbatim response).

Note: `get_last_price` fetches through egxpy → tvDatafeed's anonymous
("nologin") TradingView feed, so the value is whatever that feed returns
at run time.
