---
step_id: S663
tags:
  - "#exec"
  - "#codebase-solidification"
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-31-codebase-solidification-audit]]"
---

# codebase-solidification W26.P58.S663 — Playwright adapter no-untyped-def cluster

## Outcome

Proper parameter and return-type annotations added to three async functions in
`src/aeat/adapters/outbound/aeat/sede/_renta_web_open.py`. All three
`# type: ignore[no-untyped-def]` lines removed.

- `_open_renta_web_open_session(browser_session: BrowserSession, *, live_payload: RentaWebOpenLivePayload) -> tuple[Page, BrowserContext]`
- `_drive_open_simulator_identification(page: Page, *, live_payload: RentaWebOpenLivePayload) -> None`
- `_scrape_renta_web_open_values(page: Page, *, live_payload: RentaWebOpenLivePayload, expected: Mapping[str, object]) -> dict[str, str]`

`BrowserContext` added to `TYPE_CHECKING` import block. `BrowserSession` added to
the runtime `..browser` import line.

Design choice: proper annotation (no marker fallback). All types exist in the
project at runtime or under `TYPE_CHECKING`.

Allowlist paydown: 3 entries removed.
