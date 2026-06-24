#!/usr/bin/env python3
"""
DemoMarketBot — autonomous seller agent for the buyer-seller demo.

Watches for incoming ACP jobs, fetches live token price data from CoinGecko,
and submits the report as a deliverable automatically.

Usage:
    python3 seller_agent.py

Requires:
    - acp-cli installed and DemoMarketBot set as the active agent
    - Internet access (CoinGecko public API, no key required)
"""

import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

EVENTS_FILE = Path("seller-events.jsonl")
CHAIN_ID = "8453"
POLL_INTERVAL = 3       # seconds between event drain calls
BUDGET_USDC = "0.01"
COINGECKO_TIMEOUT = 10  # seconds

# Track requirements per job so we know which token to fetch when funded
job_tokens: dict[str, str] = {}


def run_acp(args: list[str]) -> str | None:
    result = subprocess.run(["acp"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[error] acp {' '.join(args[:2])}: {result.stderr.strip()}", flush=True)
        return None
    return result.stdout.strip()


def drain_events() -> list[dict]:
    out = run_acp(["events", "drain", "--file", str(EVENTS_FILE), "--json"])
    if not out:
        return []
    try:
        return json.loads(out).get("events", [])
    except json.JSONDecodeError:
        return []


def fetch_coingecko(token_id: str) -> str:
    url = f"https://api.coingecko.com/api/v3/coins/{token_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "acp-demo/1.0"})
        with urllib.request.urlopen(req, timeout=COINGECKO_TIMEOUT) as resp:
            d = json.loads(resp.read())
        m = d["market_data"]
        return (
            f"Token: {d['name']} ({d['symbol'].upper()}) | "
            f"Price: ${m['current_price']['usd']} | "
            f"24h Change: {m['price_change_percentage_24h']:+.2f}% | "
            f"Market Cap: ${m['market_cap']['usd']:,.0f} | "
            f"24h Volume: ${m['total_volume']['usd']:,.0f} | "
            f"Source: CoinGecko | Updated: {d['last_updated']}"
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"Error: token '{token_id}' not found on CoinGecko. Check the coin id."
        return f"Error: CoinGecko returned HTTP {e.code}."
    except Exception as e:
        return f"Error fetching data for '{token_id}': {e}"


def on_job_created(job_id: str, chain_id: str, entry: dict) -> None:
    # Try to extract the token from the requirement message in this entry.
    # Requirements are sent as the first message content in the job room.
    token = "virtual-protocol"
    content = entry.get("content", "")
    if content:
        try:
            req = json.loads(content)
            token = req.get("token", token)
        except (json.JSONDecodeError, AttributeError):
            pass

    job_tokens[job_id] = token
    print(f"[job.created] Job #{job_id} — token: {token}", flush=True)
    print(f"[set-budget]  Proposing {BUDGET_USDC} USDC ...", flush=True)
    run_acp(["provider", "set-budget", "--job-id", job_id, "--amount", BUDGET_USDC, "--chain-id", chain_id])


def on_job_funded(job_id: str, chain_id: str) -> None:
    token = job_tokens.get(job_id, "virtual-protocol")
    print(f"[job.funded]  Job #{job_id} — fetching price data for '{token}' ...", flush=True)

    report = fetch_coingecko(token)
    print(f"[report]      {report}", flush=True)
    print(f"[submit]      Submitting deliverable ...", flush=True)

    run_acp(["provider", "submit", "--job-id", job_id, "--chain-id", chain_id, "--deliverable", report])
    print(f"[done]        Job #{job_id} deliverable submitted.", flush=True)


def process_event(ev: dict) -> None:
    job_id = ev.get("jobId")
    chain_id = str(ev.get("chainId", CHAIN_ID))
    entry = ev.get("entry", {})

    # System events carry event.type; message entries carry entry.content directly.
    sys_event = entry.get("event", {}) if isinstance(entry, dict) else {}
    event_type = sys_event.get("type", "")

    if event_type == "job.created":
        if job_id:
            on_job_created(job_id, chain_id, entry)
    elif event_type == "job.funded":
        if job_id:
            on_job_funded(job_id, chain_id)
    elif event_type in ("job.completed", "job.rejected", "job.expired"):
        print(f"[{event_type}] Job #{job_id} — final state.", flush=True)
        job_tokens.pop(job_id, None)
    elif not event_type and isinstance(entry, dict) and entry.get("content"):
        # Message entry (e.g. requirement sent by buyer before job.created fires).
        # Store the token in case job.created entry didn't carry content.
        if job_id:
            content = entry.get("content", "")
            try:
                req = json.loads(content)
                if "token" in req:
                    job_tokens[job_id] = req["token"]
            except (json.JSONDecodeError, AttributeError):
                pass


def main() -> None:
    print("DemoMarketBot seller agent starting ...", flush=True)
    print(f"Polling every {POLL_INTERVAL}s | Budget: {BUDGET_USDC} USDC | Chain: {CHAIN_ID}", flush=True)
    print("Press Ctrl+C to stop.\n", flush=True)

    listener = subprocess.Popen(
        ["acp", "events", "listen", "--output", str(EVENTS_FILE)],
        stderr=subprocess.DEVNULL,
    )

    try:
        while True:
            for ev in drain_events():
                process_event(ev)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\n[shutdown] Stopping listener ...", flush=True)
        listener.terminate()
        listener.wait()
        sys.exit(0)


if __name__ == "__main__":
    main()
