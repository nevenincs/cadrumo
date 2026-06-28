---
tags:
  - "#reference"
  - "#playwright-anti-bot"
date: 2026-04-12
modified: '2026-04-12'
title: Operational Runbook - Playwright Anti-Bot
related:
  - "[[2026-04-12-playwright-anti-bot-adr]]"
---

# Operational Runbook: Playwright Anti-Bot & Detection Events

## Context
When interacting with AEAT, there's always a risk of triggering bot-detection mechanisms. This runbook details how to handle these events when they surface during automation sessions.

## 1. CAPTCHA Challenges
- **Symptom**: The AEAT page redirects to a CAPTCHA or a challenge (e.g., Cloudflare Turnstile, reCAPTCHA).
- **Action**: Do **NOT** attempt to solve the CAPTCHA automatically using third-party services.
- **Runbook**:
  1. Pause the automation pipeline immediately.
  2. Raise a critical alert to the operator (via logging/monitoring).
  3. Wait for the operator to either manually clear the IP block/CAPTCHA or wait out the temporary block.

## 2. IP Blocks
- **Symptom**: Connection timed out, connection reset, or explicit 403 Forbidden / 429 Too Many Requests responses.
- **Action**: Do **NOT** rapidly rotate proxies to bypass it. Rapid IP rotation correlates poorly with your identity and increases the risk of certificate revocation.
- **Runbook**:
  1. Honor `Retry-After` headers if provided.
  2. If an IP block is confirmed, pause the pipeline and alert.

## 3. Certificate Revocation Risk
- **Symptom**: Authentication failures after successful connections, or explicit warnings from AEAT.
- **Action**: Cease all automation immediately.
- **Runbook**:
  1. Investigate the cause of the detection.
  2. Ensure the fingerprint entropy (UA, locale, WebGL) is stable.

## Best Practices
- **Rate Limiting**: Always enforce the minimum delay between AEAT requests (default `AEAT_RATE_LIMIT_DELAY_SECONDS=2.0`).
- **Profile Stability**: Do not drop the `storage_state` (cookies/local-storage) unless absolutely necessary. Keep the profile consistent to appear as a returning legitimate user.
