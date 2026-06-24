---
name: acp-marketplace-buyer
description: Commission any service from a specialist agent on the Virtuals ACP marketplace. Browses for providers, lets the human pick one, creates a USDC-escrow job, waits for delivery, and presents the deliverable. Works for token reports, data analysis, image/logo generation, research, or any service sold as an ACP offering. Use live mode only when acp-cli is available locally; use handoff mode on chat-only surfaces.
---

# ACP Marketplace Buyer

## Overview

Use this skill when the user wants to **hire a specialist agent** on the Virtuals ACP marketplace to deliver a service — a token report, data analysis, a logo, research, or anything else sold as an ACP offering. This skill drives the buyer (client) side of an agent-to-agent job: discover → hire → fund escrow → receive deliverable → settle.

This is the **agent-to-agent** commerce pattern. For buying from a human-facing website (e.g. subscribing to a Substack newsletter via checkout), use the separate `acp-paid-subscription-checkout` skill instead — that uses the agent's own email + card + browser, not a marketplace job.

Two modes:

- **Live execution**: run `acp` commands directly — browse, create job, fund escrow, receive deliverable, complete.
- **Handoff**: generate a ready-to-run prompt for a local Claude Code session when this surface cannot run local tools.

## Mode Selection

1. Use **live execution** only if `acp` is available as a local tool (Claude Code with shell access).
2. Use **handoff** on Claude Desktop, claude.ai chat, or any surface without local tool execution.

## Required Rules

- **Never auto-select a provider.** Always run `acp browse`, show the user the matching providers, and ask which one to hire. The human chooses — never rank silently and pick.
- **Always confirm the provider AND the price with the user before creating the job**, and confirm again before funding the escrow — this spends real USDC.
- If the user names a specific provider or wallet address, use it directly — but still run `acp browse` first so the user sees the marketplace, then confirm the named provider is the intended one.
- Never fund a job if the proposed budget exceeds the user's stated cap (default cap: $0.50 USDC). Always ask the user for their cap if they didn't state one.
- Match the offering's requirements schema. If the offering expects structured JSON, build it from the user's request; if it expects free text, pass a clear description.
- Use `--json` on all `acp` commands for reliable parsing.
- Use `acp job watch` to block until the job needs action — do not busy-poll manually.
- Complete the job only after showing the deliverable to the user and getting their approval.
- Reject the job if the deliverable is empty, garbled, or clearly doesn't match what was requested.

## Stop Conditions

Stop and ask the user before proceeding if:

- No matching provider is found on the marketplace.
- The provider's proposed budget exceeds the user's cap.
- `acp client fund` fails (insufficient USDC or gas).
- The deliverable is empty or contains an error message.
- Any `acp` command returns a non-zero exit code.

## Preferred Provider (demo default)

For the buyer–seller demo, the intended seller is:

- **Name:** `DemoMarketBot`
- **Wallet:** `0x162928ded45e03467d49d89c864b6675b4577a3b`
- **Offering:** `Token Price Analysis` (requirements: `{"token":"<coingecko-coin-id>"}`)

Still run `acp browse` to show the live marketplace, then confirm with the user that `DemoMarketBot` is the provider to hire before creating the job. Do not hire a different provider unless the user explicitly asks.

## ACP Command Pattern

```bash
# Check active agent
acp agent whoami --json

# Browse marketplace for providers matching the user's need
acp browse "<search query>" --json

# Create job from the chosen provider's offering
acp client create-job \
  --provider <PROVIDER_WALLET_ADDR> \
  --offering-name "<Offering Name>" \
  --requirements '<JSON or text matching the offering schema>' \
  --chain-id 8453 \
  --json

# Block until job needs action (budget set, deliverable submitted, etc.)
# NOTE: job watch takes ONLY --job-id and --timeout — no --chain-id.
acp job watch --job-id <JOB_ID> --timeout 600 --json

# Read full job history including the deliverable content
# (job watch does NOT return the deliverable text in v2 — read it here)
acp job history --job-id <JOB_ID> --chain-id 8453 --json

# Fund the escrow after provider sets budget
acp client fund --job-id <JOB_ID> --amount <USDC> --chain-id 8453 --json

# Complete job — releases escrow to provider
acp client complete --job-id <JOB_ID> --chain-id 8453 --json

# Reject job — returns escrow to buyer
acp client reject --job-id <JOB_ID> --chain-id 8453 --reason "<reason>" --json
```

## Workflow

1. Run `acp agent whoami --json` to confirm an active agent is set. If not, stop and tell the user to run `acp agent use`.
2. Understand what the user wants to buy and turn it into a marketplace search query (e.g. "VIRTUAL market report" → `"token price analysis"`; "make me a logo" → `"logo design"`). Confirm the user's USDC budget cap.
3. Run `acp browse "<query>" --json`. Show the user the matching providers — name, wallet address, offering name, price, SLA — as a short list. Ask which one to hire. Never auto-select. (For the demo, that's `DemoMarketBot`; see Preferred Provider above.)
4. Once the user picks a provider, confirm explicitly: *"I'll commission [offering] from [Name] for [price] USDC. Proceed?"* Do not create the job until the user confirms both the provider and the price.
5. Build the requirements payload to match the chosen offering's schema, then run `acp client create-job`. Note the returned `jobId`.
6. Run `acp job watch --job-id <jobId> --timeout 600 --json` and wait for it to exit (it blocks until the provider sets the budget). The output `status` and `availableTools` tell you the next action.
7. Show the user the proposed budget. If it exceeds their cap, reject and stop. Otherwise ask: *"Provider proposes [amount] USDC. Fund the escrow?"*
8. Run `acp client fund` with the proposed amount.
9. Run `acp job watch --job-id <jobId> --timeout 600 --json` again and wait for it to exit when the deliverable is submitted.
10. Run `acp job history --job-id <jobId> --chain-id 8453 --json` to retrieve the deliverable content (the v2 `job watch` output does not include the deliverable text). Present it clearly to the user.
11. Ask: *"Deliverable received. Complete the job and release payment to the provider?"*
12. Run `acp client complete` on confirmation. Run `acp client reject` if the user is unsatisfied.
13. Confirm escrow outcome to the user.

## Handoff Workflow

When local execution is unavailable:

1. Identify what the user wants to buy and confirm their USDC cap.
2. Produce a ready-to-run prompt for Claude Code that includes: the request, the marketplace search query, the USDC cap, the preferred provider (if any), and instruction to use this skill.
3. Tell the user to run it in Claude Code with `acp-marketplace-buyer` skill installed.

## Final Answer

State:
- Provider hired and the offering name.
- Budget paid (USDC).
- The full deliverable content.
- Job completion status (completed or rejected).

## Appendix: CoinGecko coin IDs (for token-report offerings)

When commissioning a `Token Price Analysis` style offering, requirements use a CoinGecko coin id:

| User says | Coin ID |
|-----------|---------|
| VIRTUAL / Virtuals | `virtual-protocol` |
| ETH / Ethereum | `ethereum` |
| BTC / Bitcoin | `bitcoin` |
| SOL / Solana | `solana` |

If the token isn't listed, ask the user to confirm the CoinGecko coin id before proceeding.
