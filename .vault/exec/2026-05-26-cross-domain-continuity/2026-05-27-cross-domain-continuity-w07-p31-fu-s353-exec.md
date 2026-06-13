---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-27
modified: '2026-05-27'
step_id: 'FU-S353'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-cross-domain-continuity-w07-p31-s353-review-exec]]"
---

# `cross-domain-continuity` `W07.P31.FU-S353`

TOML-only grounding fix for GROUNDING-001 MEDIUM finding from S353 review. Removes the wrong `ley-35-2006:art-56` (mínimo personal y familiar) from formula `legal_refs`, establishes `art-50` + `art-63` as the correct authorities, and propagates `aeat-dr-100-2024-dictionary` into both the 2024 formula and its parent construct.

- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0168-renta-2024-base-liquidable-general-sometida-a-gravamen.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/formulas/0177-renta-2025-base-liquidable-general-sometida-a-gravamen.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/constructs/0001-renta-cuota-chain.toml`

## Description

Pre-edit collision check (`git diff -- <files>`) confirmed no peer-agent WIP on any of the three files.

Both formula TOMLs originally listed `ley-35-2006:art-56` as first `legal_refs` entry. The legal registry at `legal/irpf.toml` annotates Art. 56 for "mínimo personal y familiar (casillas 0511-0524)" — an unrelated concept. Both `ley-35-2006:art-50` and `ley-35-2006:art-63` were confirmed present in the registry before being written.

2024 formula: `legal_refs` changed from `["art-56", "art-50"]` to `["art-50", "art-63"]`. `source_refs` extended to include `aeat-dr-100-2024-dictionary` (confirmed in `sources` table of `irpf.toml`).

2025 formula: `legal_refs` changed from `["art-56", "art-50", "art-49", "rd-439-2007:art-109", "orden-hac-277-2026:art-3"]` to `["art-50", "art-63", "art-49", "rd-439-2007:art-109", "orden-hac-277-2026:art-3"]`. `source_refs` extended to include `aeat-dr-100-2025-dictionary` (confirmed present in the 2025 construct and `sources` table).

The registry validator enforces that every formula `source_refs` entry must be a subset of its parent construct's `source_refs`. The 2024 construct did not list `aeat-dr-100-2024-dictionary`, so it was added there as well. The 2025 construct already carried it.

## Tests

No new tests written — this is metadata-only. Registry validation run after changes:

- `aeat app modelo bindings list --modelo 100 --year 2024 --period 0A`: PASS (6 bindings, no integrity errors)
- `aeat app modelo bindings list --modelo 100 --year 2025 --period 0A`: PASS (no integrity errors)

Commit: `de26b923b`
