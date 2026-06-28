---
tags:
  - "#research"
  - "#normatives"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-normatives-adr]]"
  - "[[2026-04-12-normatives-plan]]"
  - "[[2026-04-12-manual-practico-adr]]"
  - "[[2026-04-12-trilingual-i18n-adr]]"
---

# normatives research: codifying the spanish tax normative layer

## Problem framing

Issue `#45` asks for a typed, machine-readable catalogue of the Spanish tax
normatives governing the autónomo regime. Every casilla, every rule, every
deadline the project computes ultimately cites one of these laws. Without
a typed catalogue the citations are free-text strings that no validator
can check, no CLI can render, and no regression test can pin.

The research question is narrow: **what does a stable, link-based
catalogue of the Spanish tax normatives look like, and what do its
permalinks actually resolve to?**

## BOE permalink structure

The Boletín Oficial del Estado publishes two views for every law:

- the **PDF of the original publication** at
  `https://www.boe.es/boe/dias/YYYY/MM/DD/pdfs/BOE-A-YYYY-NNNNN.pdf`,
  frozen on the day of publication; and
- the **consolidated text** at
  `https://www.boe.es/buscar/act.php?id=BOE-A-YYYY-NNNNN`, updated in
  place every time a subsequent act amends the source, with a
  machine-readable history of the amendments appended to the footer.

The consolidated view is the one the project should always link to. It
is:

- stable — the URL is canonical, never changes, and the BOE commits to
  preserving it;
- current — it reflects every amending act up to the most recent BOE
  publication, so a `cite(...)` rendered today always points at the
  law *as it applies today*;
- fragment-addressable — the consolidated page emits one HTML anchor
  per article of the form `#a{numero}` (e.g. `#a32` for *artículo 32*,
  `#a27bis` for *artículo 27 bis*), plus `#da-1`, `#dt-1`, `#df-1` for
  *disposiciones adicionales / transitorias / finales*.

A permalink of the shape
`https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764#a32` therefore
resolves deterministically to the current text of
*Ley 35/2006, artículo 32* without any further state on the caller's
side.

### BOE-A identifier shape

The identifier is `BOE-A-{year}-{ordinal}` where `{ordinal}` is the
1-indexed disposition number assigned by the BOE within that year. It
is:

- unique within a year;
- assigned on publication day and never re-used;
- the same identifier used by the BOE's REST endpoints
  (`/datosabiertos`, `/legislacion`, `/diario_boe/txt.php?id=...`) and
  by every external tool that integrates with the BOE.

Storing the identifier and the canonical URL side-by-side is belt-and-
braces: if the URL format ever shifts (it has not in a decade), the
identifier is still the primary key. If the identifier ever collides
(it cannot, by construction), the URL still carries the human-facing
text.

## Consolidated text: why never mirror the body

The research question that looked most tempting — *should the project
mirror full article text inside the repo?* — has a clear answer: **no,
for v1**.

- **Size**: the seven in-scope normatives total roughly 3,000 printed
  pages. Mirroring them as JSON would bloat the repo and explode every
  PR diff adjacent to the corpus.
- **Staleness**: the consolidated BOE text is updated in place. A
  local mirror would need a continuous sync job just to stay honest,
  which is a large and orthogonal deliverable.
- **Legal risk**: the BOE's terms of use permit linking freely, but
  verbatim re-publication of consolidated text is a grey area the
  project should not step into without counsel.
- **Use case**: every downstream consumer (casilla DB, rule extractor,
  deadline engine, filing reports) needs the *citation*, not the body.
  A human reader follows the link; an automated test compares the
  identifier; a renderer emits a canonical string.

v1 therefore ships **link-only references**: one record per
normative, one record per codified article, and every record carries a
BOE permalink. If a future PR decides full-text is needed for LLM
retrieval or offline mode, the schema already has `notes` and the
loader already tolerates additive fields; a body-field migration is
straightforward and has an obvious hand-off from the link-only layer.

## Historical revisions are out of scope

The BOE publishes the **history** of every consolidated text: each
amendment lists its own BOE-A identifier and the date the amendment
took effect. The project deliberately does **not** model this history
in v1. `cite(...)` always resolves to the consolidated text, which is
by construction the version currently in force. When a casilla rule
needs to reference a specific historical state (e.g. *art. 32 as it
stood in 2023*), that requirement belongs to a follow-up issue with
its own schema.

## In-scope normatives (verified against BOE consolidated texts)

Every entry below was verified by fetching
`https://www.boe.es/buscar/act.php?id=<BOE-A>` during this research
session and confirming the title, publication date, and the presence
of the articles the project cites.

| normative                                          | kind             | number     | BOE-A id          | published  |
| -------------------------------------------------- | ---------------- | ---------- | ----------------- | ---------- |
| Ley 35/2006 (IRPF)                                 | LEY              | 35/2006    | BOE-A-2006-20764  | 2006-11-29 |
| Real Decreto 439/2007 (Reglamento IRPF)            | REAL_DECRETO     | 439/2007   | BOE-A-2007-6820   | 2007-03-31 |
| Ley 37/1992 (IVA)                                  | LEY              | 37/1992    | BOE-A-1992-28740  | 1992-12-29 |
| Real Decreto 1624/1992 (Reglamento IVA)            | REAL_DECRETO     | 1624/1992  | BOE-A-1992-28925  | 1992-12-31 |
| Ley 58/2003 (Ley General Tributaria)               | LEY              | 58/2003    | BOE-A-2003-23186  | 2003-12-18 |
| Real Decreto 1065/2007 (Reglamento gestión/inspección) | REAL_DECRETO | 1065/2007  | BOE-A-2007-15984  | 2007-09-05 |
| Orden HAC/242/2025 (modelos IRPF / Patrimonio 2024)| ORDEN_MINISTERIAL | HAC/242/2025 | BOE-A-2025-5049 | 2025-03-14 |

Note: the current annual Orden is issued by the *Ministerio de Hacienda
y Administraciones Públicas* under the HAC prefix (*Orden HAC/…*). The
historical HFP prefix (*Ministerio de Hacienda y Función Pública*) and
the current HAC prefix are both valid
`NormativeKind.ORDEN_MINISTERIAL` values; the enum does not distinguish
them because the ministry name shifts each time the cabinet is
reshuffled and the legal nature of the act is unchanged.

## Articles to codify in v1

The issue scope is *the specific articles the project cites* — not
the entire article tree of every normative. v1 codifies the minimum
set the autónomo automation will need to emit citations for as the
downstream subpackages land. Additional articles can be appended in
follow-ups without a schema change.

- **Ley 35/2006** — arts. 27 (rendimientos de actividades económicas),
  28 (reglas generales de cálculo), 30 (estimación directa), 31
  (estimación objetiva), 32 (reducciones), 99 (retenciones).
- **RD 439/2007** — arts. 80 (retenciones), 95 (actividades económicas),
  109 (obligaciones formales), 110 (pagos fraccionados).
- **Ley 37/1992** — arts. 4 (hecho imponible), 90 (tipo general), 91
  (tipos reducidos), 164 (obligaciones formales del sujeto pasivo).
- **RD 1624/1992** — art. 71 (declaración-liquidación periódica).
- **Ley 58/2003** — arts. 27 (recargos por declaración extemporánea),
  29 (obligaciones tributarias formales), 66 (prescripción).
- **RD 1065/2007** — art. 30 (declaraciones informativas).
- **Orden HAC/242/2025** — apartado primero (aprobación del modelo).

## Schema decisions captured here

- **id shape**: kebab-case `ley-35-2006`, `rd-439-2007`,
  `orden-hac-242-2025`. Matches the `_StableId` shape already used by
  `aeat.domain.manuals` and other sibling subpackages.
- **Title / summary / article summary**: `Translatable` nested dicts
  imported directly from `aeat.core.i18n` (already on `main` via `#20`).
  Authoritative language is Spanish; Hungarian summaries are the
  user-facing target; English is the authoritative engineering
  language.
- **Permalink**: `AnyHttpUrl`; validation rejects anything that does
  not round-trip through pydantic's strict URL parser.
- **Review metadata**: every persisted record carries
  `reviewed_by` + `last_reviewed_at`. Hand-review is mandatory and
  enforced by `aeat normatives verify` — mirrors the review gate the
  `aeat.domain.manuals` subpackage ships under `#25`.

## Non-decisions (deferred)

- **Full-text mirroring** — deferred indefinitely; see above.
- **Historical revisions** — deferred; link to consolidated text.
- **Autonomic normatives** (Catalonian, Basque, Galician equivalents)
  — deferred; the project's first milestone is AEAT-level autónomo
  automation.
- **LLM-assisted summary drafting** — deferred; v1 summaries are
  hand-written by the reviewer and committed as authoritative
  content.
- **Cross-reference rewire** — `aeat.domain.manuals`, `aeat.domain.modelos`, and
  `aeat.domain.casillas` will eventually cite normatives by id. Those
  rewires are pure additions to the consuming subpackages and are
  not v1 normatives work.

## References

- BOE portal: https://www.boe.es/
- BOE consolidated-text index:
  https://www.boe.es/legislacion/legislacion.php
- `aeat.domain.manuals` schema: `src/aeat/domain/manuals/_schema.py` on `main` —
  the review-gate and trilingual-field idiom this subpackage mirrors.
- `aeat.core.i18n` public surface: `src/aeat/core/i18n/__init__.py` — provides
  `Translatable` and `Language`.
