---
tags:
  - '#research'
  - '#corpus-evidence-integrity'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:b94b7fac01d9929a82f576e91c39f3d3984a90549c0c5801cf8a1e90366e67f4'
related:
  - '[[2026-08-28-corpus-evidence-integrity-corpus-editorial-gloss-hazard-audit]]'
  - '[[2026-08-28-corpus-evidence-integrity-corpus-anchor-resolvability-audit]]'
  - '[[2026-09-10-registry-temporal-coverage-corpus-tier-enforcement-research]]'
---

# `corpus-evidence-integrity` research: `Five corpus files are hand-shaped text, and corpus_tier is dead on the model that would catch them`

The bundled normative corpus is the evidence layer under every filing-grade legal citation:
a registry entry names a file under `src/cadrumo/_data/corpus/normatives/html/`, and the
evidence gate checks that the entry's `required_text` phrases appear in it. That check
establishes *correspondence* between the citation and the file. Nothing establishes the
file's own *provenance* — that its text was derived from BOE rather than typed by an
author. This document measures how much text in the shipped corpus is hand-shaped, which
citations rest on it, and what signals could tell the two apart. It does not decide the
remedy.

The headline number is small, and that is the useful part: the corpus is 476 files, and the
strictly hand-shaped population is 5 files carrying 6 citations. An earlier framing put it
near 180; that estimate conflated "lacks an excerpt header" with "authored", and the two
are not the same population.

## Findings

### The corpus splits four ways, and only the smallest band is hand-shaped

Classifying all 476 files in `src/cadrumo/_data/corpus/normatives/html/` by the strongest
provenance evidence each file carries in its own bytes:

| Band | Files | Signal |
| --- | ---: | --- |
| `excerpt-header` | 189 | carries the literal marker `Official BOE consolidated source excerpt` |
| `boe-attributed` | 269 | carries a `BOE-A-YYYY-NNNNN` document identifier |
| `boe-markup-only` | 13 | carries BOE's own `class="articulo"` / `class="parrafo"` structure, no identifier |
| `hand-shaped` | 5 | none of the above |

The `boe-markup-only` band matters as a grey zone: BOE's stylesheet class names are strong
evidence a slice came out of a BOE page, but they are also trivially typeable, so the band
is presumptive rather than proven.

The five hand-shaped files, with byte sizes:

- `ley-12-2002.html` (2,570 B)
- `ley-35-2006-art-48.html` (1,980 B)
- `orden-eha-3290-2008.html` (1,385 B)
- `orden-hac-1526-2024-art-1.html` (444 B)
- `orden-hac-1526-2024-df-unica.html` (365 B)

Six registry entries cite them, all `corpus_ref` on `LegalReference`, none declaring
`corpus_tier`: `legal/censo.toml` (both `orden-hac-1526-2024` files), `legal/irnr.toml`
(`orden-eha-3290-2008`, twice — anchors `#a1` and `#a4`), `legal/irpf.toml`
(`ley-35-2006-art-48`), and `legal/iva.toml` (`ley-12-2002`).

### The gate that looks like it should catch this was built to accept these exact files

`_validate_dispositive_content` (`src/cadrumo/domain/calculations/registry/legal.py:142`)
refuses corpus text that states no operative provision of its own. It is scoped to
`#modelo-<id>` anchors by `_MODELO_ANCHOR` (`legal.py:139`, checked at `legal.py:154`), so
it does not run on an `#a1` anchor. But scope is not the interesting part: the module's own
comment at `legal.py:112-115` names `orden-eha-3290-2008` and `orden-hac-1526-2024`
explicitly as "real near-miss files ... both using the unaccented convention" that the
signal is calibrated to **pass**.

These files are therefore not gate escapes. They are known, accepted inputs. The gate's
target is a *stub* — text with no operative provision — and a hand-authored paraphrase that
does state a provision is a different defect that no gate currently names. That distinction
is the substance of this research: correspondence, dispositive content, and provenance are
three axes, and only the first two are checked.

### `corpus_tier` classifies the wrong axis, and would not catch the M037 file even if declared

`corpus_tier` is a two-valued classification — `FULL_CONSOLIDATED` or `PROVISION_EXCERPT` —
verified by `_validate_corpus_tier_declaration` (`legal.py:182`). It answers "is this the
whole instrument or one provision", not "where did this text come from".

Tracing `orden-hac-1526-2024-art-1.html` through that validator shows the axis mismatch
concretely. Declaring `PROVISION_EXCERPT` reaches `legal.py:213`, where a filename matching
`_PROVISION_SUFFIXED_FILENAME` (`legal.py:180`) returns clean — and `-art-` matches. The
declaration would be accepted without the text ever being read. Declaring
`FULL_CONSOLIDATED` would correctly raise, but that is not the claim an author would make
about a 444-byte file. **Making `corpus_tier` mandatory would therefore not close this
case.** That is a change from the option an earlier pass favoured.

The field is also asymmetrically populated: 19 declarations exist, all on `LegalReference`
via `corpus_ref` (`legal/irpf-impatriados.toml`, `legal/modelo-185.toml`,
`legal/patrimonio.toml`), and zero on any `SourceReference` via `corpus_path` across 531
such entries. `schema_references.py:526` records why — `SourceReference` targets have no
`#anchor` convention, so no resolved-anchor read applies.

### A stale docstring overstates that the tier check is inert

`legal.py:185-186` states that "nothing in the committed catalogue declares `corpus_tier`
today, so this can never fire against the existing tree". Eighteen committed
`LegalReference` entries declare it. The parallel claim in `corpus_catalogue.py:83` is
scoped to `SourceReference` and remains accurate. This is a documentation defect, not a
behavioural one — the validator is correct — but it misleads the next reader about the
check's live coverage.

### Two independent provenance signals exist, and neither is sufficient alone

Genuine BOE text is accented Spanish. Measuring accented-character density over
tag-stripped text finds **10 files with zero accented characters**, which for a Spanish
legal instrument is not plausibly authentic: `trlirnr-rdleg-5-2004`,
`rd-1624-1992-art-81`, `orden-eha-3290-2008`, `rd-1624-1992-art-79`,
`rd-1624-1992-art-80`, `convenio-es-ma-1978-art-11`, `convenio-es-de-2011-art-11`,
`convenio-es-gb-2013-art-6`, `orden-hac-1526-2024-art-1`, and
`orden-hac-1526-2024-df-unica`. One further file, `convenio-es-ar-1992-art-19`, sits at a
density of 0.00084, an order of magnitude below any other.

The two signals are complementary, not nested. The accent signal catches
`rd-1624-1992-art-79/80/81`, the `convenio-*` files, and `trlirnr-rdleg-5-2004`, which the
structural classification placed in the attributed bands. It misses `ley-12-2002` and
`ley-35-2006-art-48`, both correctly accented. Their union is roughly a dozen files out of
476 — still small enough to resolve by hand, and large enough that the population is not
self-evident from any one probe.

### One gloss-bearing file is outside the prior audit's census

`2026-08-28-corpus-evidence-integrity-corpus-editorial-gloss-hazard-audit` recorded five
corpus files mixing BOE text with an appended editorial gloss. Its detector keyed on a
`Fuente:` attribution line, and exactly five files in the corpus carry that string:
`ley-19-1991-art-30`, `-art-31`, `-art-4-9`, `ley-35-2006-art-49`, and `-art-93`.

`ley-35-2006-art-48.html` carries the same hazard shape without the marker. Its law text is
followed by an authored section headed "IRPF — Ley 35/2006, compensación de saldos
negativos de la base general (Modelo 100)" that names product casillas 1391 and 1388.
Casilla numbers are not BOE text. The census is six, not five.

The hazard remains latent here, consistent with the audit's finding. `legal/irpf.toml:3354`
declares three `required_text` phrases for `ley-35-2006:art-48`, and all three resolve
against the law-text portion. What is notable is the entry's self-description: it carries
`evidence_tier = "legal_authority"`, `review_status = "operator_reviewed"`, and
`reviewed_at = 2026-06-02` against a file whose text no signal in the repository attributes
to BOE.

### Precedent exists, and the decision was explicitly deferred

`2026-08-15-registry-temporal-coverage-legal-grounding-consolidation-audit`, finding
`no-corpus-tier-in-schema`, named the classification gap and sketched the two-valued design
that became `corpus_tier`, closing with the note that whether to build it further is an
operator call. No ADR records that decision. The `corpus-evidence-integrity` feature
already holds three audits on adjacent corpus-integrity hazards, which makes it the natural
home rather than a new feature.

### What the ADR must settle

The evidence favours treating **provenance as a third axis**, distinct from `corpus_tier`'s
excerpt/full-text classification, rather than overloading `corpus_tier` — which the M037
trace shows would not catch the case that motivated it. Open questions for the decision:

- Whether provenance is declared per citation, recorded per corpus file (a sidecar or an
  in-file marker), or derived by a detector at validation time.
- Whether hand-authored text is refused outright, or admitted under an explicit non-filing
  classification that `no-silent-under-declaration` keeps visible through calculation and
  filing handoff.
- Whether the `boe-markup-only` band of 13 files is treated as attested or as presumptive.
- Whether the six citations resting on hand-shaped text are re-grounded against real BOE
  text before or as part of any gate landing, given that five of them currently claim
  `legal_authority` tier.
- Whether the `ley-35-2006-art-48` gloss is separated from the law text, which the prior
  audit already framed as the more faithful of the two remediation shapes it considered.

### Not investigated

Whether the hand-shaped texts are *substantively* faithful to the instruments they
paraphrase was not verified against live BOE; that is a grounding question per
`aeat-calculation-grounding` and needs the official sources, not a corpus sweep. The 359
registry entries whose `corpus_path` targets fall outside `corpus/normatives/html/`
(`corpus/aeat_official/` calendars, record designs, manuals) were counted but not
classified — a different tree with a different provenance convention.

## Sources

- `src/cadrumo/domain/calculations/registry/legal.py:82` — `_DISPOSITIVE_KINDS`
- `src/cadrumo/domain/calculations/registry/legal.py:112-119` — `_DISPOSITIVE_CONTENT_SIGNAL` and the calibration comment naming the near-miss files
- `src/cadrumo/domain/calculations/registry/legal.py:139` — `_MODELO_ANCHOR`
- `src/cadrumo/domain/calculations/registry/legal.py:142` — `_validate_dispositive_content`
- `src/cadrumo/domain/calculations/registry/legal.py:180` — `_PROVISION_SUFFIXED_FILENAME`
- `src/cadrumo/domain/calculations/registry/legal.py:182-186` — `_validate_corpus_tier_declaration` and the stale coverage docstring
- `src/cadrumo/domain/calculations/registry/legal.py:213` — the provision-suffixed early return
- `src/cadrumo/domain/calculations/registry/corpus_catalogue.py:83` — the accurate `SourceReference`-scoped parallel claim
- `src/cadrumo/domain/calculations/registry/schema_references.py:526` — why `SourceReference` has no resolved-anchor read
- `src/cadrumo/_data/registry/aeat/legal/irpf.toml:3340-3358` — the `ley-35-2006:art-48` entry
- `src/cadrumo/_data/registry/aeat/legal/censo.toml`, `irnr.toml`, `iva.toml` — the remaining citations of hand-shaped text
- `src/cadrumo/_data/registry/aeat/legal/irpf-impatriados.toml`, `modelo-185.toml`, `patrimonio.toml` — the 19 `corpus_tier` declarations
- `src/cadrumo/_data/corpus/normatives/html/` — the 476 classified files

File-count, citation-count, and accent-density figures were measured on 2026-09-10 by
throwaway probes under the gitignored `.logs/` directory. They are reproducible from the
tree and the locators above, and are not claims from memory.
