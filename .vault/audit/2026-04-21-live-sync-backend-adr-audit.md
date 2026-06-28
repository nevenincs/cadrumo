---
tags:
  - '#audit'
  - '#live-sync-backend'
date: '2026-04-21'
modified: '2026-04-21'
related:
  - '[[2026-04-21-live-sync-backend-adr]]'
---

# `live-sync-backend` Code Review



ADR-001 | LOW | Caching strategy detail
The ADR mentions utilizing `StatusCache` for both features. `StatusCache` is JSON-backed and revalidates via Pydantic models. We need to ensure that parsing PDFs (if used) doesn't try to JSON-serialize binary data.

ADR-002 | CRITICAL | Anti-Write enforcement
The ADR mandates only `domcontentloaded` for `page.goto`. We must ensure no other Navigation forms (e.g. form submissions) are triggered by BeautifulSoup or playwright when expanding pagination on the Sede.
