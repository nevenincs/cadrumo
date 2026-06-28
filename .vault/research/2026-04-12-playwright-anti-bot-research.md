---
tags:
  - "#research"
  - "#playwright-anti-bot"
date: 2026-04-12
modified: '2026-04-12'
title: "Playwright Anti-Bot Evasion Research"
---

# Playwright Anti-Bot Evasion Research

## 1. Playwright Python Install Path Under `uv`
Using `uv` to manage the environment and dependencies provides a fast and deterministic installation path.

**Exact Incantation:**
```bash
# Pin version explicitly in pyproject.toml / uv.lock
uv add playwright==1.42.0

# Install browser binaries (do NOT use global install)
uv run playwright install chromium
```

**Deliberate Upgrade Workflow:**
Browser binaries are tightly coupled with the `playwright` python package version. A manual upgrade workflow must be followed:
1. Update version in `pyproject.toml` or use `uv lock --upgrade-package playwright`.
2. Sync the environment: `uv sync`.
3. Explicitly install the new matching browser binaries: `uv run playwright install chromium` (or specific channel).
4. Remove old browsers (optional but recommended to free up space): `uv run playwright uninstall --all`.

## 2. Anti-Bot Evasion Options

### `playwright-stealth`
- **Covered Tells:** `navigator.webdriver` removal, patching `navigator.plugins`, `navigator.languages`, overriding `WebGLRenderingContext`, masking `HeadlessChrome` from the User-Agent string.
- **False-Positive Risk on Legitimate AEAT:** Low to Medium. While effective against basic checks, aggressive "stealth" patches can sometimes break legitimate JavaScript executing in the target site if the patched environment deviates from natural execution.
- **Maintenance Health:** Moderate. It is a direct port of the Node.js `puppeteer-extra-plugin-stealth`. While updates occasionally lag behind browser engine changes, it remains the standard drop-in for Python.
- **Fit with `uv`:** Excellent. Simple `uv add playwright-stealth`.
- **Compatibility with Certificate Auth:** High. `playwright-stealth` operates via `page.add_init_script` and CDP overrides, which do not interfere with underlying transport layers or `client_certificates` passed during context creation.

### `undetected-playwright`
- **Maintenance Health:** Very poor. Unlike the thriving `undetected-chromedriver` ecosystem, Python implementations of "undetected" Playwright are fragmented, unmaintained, and mostly abandoned.
- **Fit:** Not recommended for production use due to lack of support.

### Manual Evasion Patches
- **Approach:** Supplying custom `add_init_script` logic to mask known leaks (e.g., overriding `Object.defineProperty(navigator, 'webdriver', {get: () => undefined})`).
- **Maintenance:** High burden. We would be responsible for constantly updating our patches as bot detection evolves.
- **Verdict:** Should be reserved strictly for specific overrides that `playwright-stealth` misses for our exact target.

## 3. Browser Channel Choice

### Bundled Chromium (Default)
- **Trade-off:** Optimized for automation. Contains a clean, predictable footprint but lacks proprietary codecs (H.264/AAC) and exhibits a generic "testing tool" fingerprint. Easily flagged by advanced WAFs.

### Channelled Chrome (`channel: "chrome"`)
- **Trade-off:** Uses the system's installed branded Google Chrome. It possesses proprietary features and a natural, messy fingerprint that blends in with human traffic.
- **Drawback:** Requires an installed Chrome binary on the host/container, introducing a secondary dependency outside of the Playwright versioning lock.

### Firefox
- **Trade-off:** Historically faces fewer explicit anti-bot blocks because Chrome dominates automation. However, Firefox has a highly unique fingerprint. Some modern bot mitigations simply treat non-Chrome traffic as highly suspicious by default if the target's traffic profile is 99% Chrome.

**Recommendation for AEAT:** Use `channel: "chrome"` combined with the "New Headless" mode (which renders a full browser without UI, avoiding the heavily scrutinized headless shell).

## 4. Fingerprint and Entropy Management
A returning bot looks much more suspicious if its physical characteristics change on every visit while using the same identity.

- **Stable-per-Profile:** User-Agent, Locale, Timezone, Viewport dimensions, installed Fonts, WebGL renderer, and Audio Context must remain **stable per AEAT profile**.
- **Storage State:** We must persist `storage_state` (Cookies and LocalStorage). Dropping cookies on every request simulates a brand-new user or an incognito session every time, triggering risk engines.
- **Implementation:** Bind a seeded hash of the AEAT account identifier to deterministically select viewport bounds, timezone, and user-agent variants, ensuring a consistent fingerprint over time.

## 5. Proxy Options
- **Per-Request Datacenter / Rotating Residential:** **WRONG DEFAULT.** Rapid IP hopping while maintaining a static TLS Client Certificate identity is an extreme anomaly. Humans do not change ISPs between HTTP requests while holding the same government auth certificate. This highly correlates with adversarial behavior.
- **Static Residential / No Proxy:** **CORRECT.** A stable IP (or no proxy, if executing from a clean region) that matches the typical geography of the user is required.
- **Configuration Surface:** Proxies should be off by default, and configurable via environment variables (e.g., `AEAT_HTTP_PROXY`). The exact provider is deferred to a follow-up.

## 6. Operational Guardrails
- **Rate Limiting:** Minimum randomized delay between AEAT requests to simulate human pacing (e.g., 2-5 seconds).
- **Retry-After Honouring:** Strict adherence to HTTP 429 `Retry-After` headers.
- **Detection-Event Runbook:** If a hard block is encountered (CAPTCHA challenge, 403 IP block, or certificate revocation warning):
  1. **Pause** all execution for the affected identity.
  2. **Alert** the system operator immediately.
  3. **Do Not Retry** the request blindly, as this exacerbates the block and risks permanent credential burning.

## 7. Concrete Commitments (ADR Output)

### Primary Approach
- Use `playwright` with `playwright-stealth` in Python.
- Execute using `channel: "chrome"` in "New Headless" mode.
- Maintain persistent `storage_state` and deterministic profile entropy (viewport, UA) tied to the certificate identity.
- No proxy by default, with static proxy configuration allowed via environment variables.

### Fallback Approach
- If `channel: "chrome"` proves too brittle due to system-level update mismatch, fallback to the bundled `chromium` with aggressive manual CDP patching for missing codecs/tells.

### What We Are NOT Doing & Why
- **We are NOT doing per-request proxy rotation.** Rotating IPs with the same certificate identity signals a botnet/distributed attack to WAFs.
- **We are NOT using `undetected-playwright`.** The Python ecosystem for this is unmaintained and poses a supply-chain / stability risk.
- **We are NOT dropping cookies/storage between sessions.** This triggers "new device" risk scoring on the AEAT portal.
