---
tags:
  - '#research'
  - '#modelo-180-calc-verify'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-27-modelo-115-calc-verify-adr]]"
  - "[[2026-04-27-modelo-123-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
---

# `modelo-180-calc-verify` research: `2024-2026 annual rental withholding summary`

## Findings

The primary-source scope for Modelo 180 is narrower than the handover prompt's broad "M111 + M115 + M123" description. The GitHub issue body and the BOE/AEAT sources define Modelo 180 as the annual summary of retenciones e ingresos a cuenta on rendimientos from urban property leases, i.e. the annual partner of Modelo 115. Modelo 111 rolls into Modelo 190, and Modelo 123 rolls into Modelo 193 in the current AEAT taxonomy.

Primary sources consulted:

- BOE-A-2000-21430, Orden de 20 de noviembre de 2000, approves Modelos 115 and 180 and the Modelo 180 physical/logical layouts. The consolidated text identifies the current update trail through 2023-11-30.
- BOE-A-2021-20004, Orden HFP/1351/2021, modifies the 2000 order and keeps Modelo 180 as the arrendamiento/subarrendamiento de inmuebles urbanos annual summary.
- BOE-A-2007-6820, RD 439/2007 RIRPF art. 100, fixes the 19 percent withholding rate for urban property leases, excluding VAT from the base.
- BOE-A-2006-20764, Ley 35/2006 LIRPF arts. 99-101, supplies the statutory withholding obligation and rate delegation.
- AEAT Modelo 180 presentation help and the AEAT activities-folleto page confirm Modelo 115 is quarterly and Modelo 180 is the annual summary for the same rental-withholding obligation.

Existing code state:

- `modelo_180_2024.py` and `modelo_180_2025.py` already model the four summary casillas: 01 recipients, 02 retention base, 03 retentions, 04 in-kind payments on account.
- The only computed casilla is 03 = 19 percent of 02.
- `modelo_180_v2025.py` extracted only the summary block for 2025; sibling extractor classes were missing for 2024 and 2026.
- No M390 ADR or rule-delta artifact was present in this worktree, so M390 could not be mirrored.

Cumulation design:

- Chosen approach: A, per-fixture preserving, scoped to Modelo 115 quarterly sources. The implementation uses four Modelo 115-style quarterly summaries to derive the annual Modelo 180 summary.
- The helper keeps per-recipient rows out of the ruleset DAG for this issue because the current extractor and generator surfaces only print summary casillas. The rule-delta manifest records per-recipient detail as a future extractor/model expansion.
- The "forgot Q3" risk is addressed by requiring exactly four quarter sources before producing the annual summary.

L1 anchor decision:

- Waiver. Modelo 180 declarations contain taxpayer/recipient data; no normative public declaration PDF was found. The public AEAT help/instructions and BOE layout sources are retained as legal anchors, while the PDF round-trip remains L3 synthetic.
