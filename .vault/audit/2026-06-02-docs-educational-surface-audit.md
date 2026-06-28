---
tags:
  - '#audit'
  - '#docs-educational-surface'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-06-01-docs-educational-surface-adr]]'
---

# `docs-educational-surface` audit: `documentation overhaul multi-review and docstring rollout`

## Scope

A multi-reviewed documentation overhaul driven through a fan-out
orchestration: every user-facing narrative document was read by two
independent zero-context reviewers (one Diátaxis type-purity lens, one
newcomer-clarity lens against the prose-style rules), and the codebase
docstring surface was audited by `interrogate`, drafted, and
readability-reviewed by a non-developer persona. The pass covered the
seven-document narrative corpus (`docs/tutorials/index.md`,
`docs/how-to/index.md`, `docs/explanation/index.md`,
`docs/getting-started.md`, `docs/architecture.md`,
`docs/authoring-guide.md`, `README.md`) and the top docstring-gap
modules outside the actively-refactored registry schema.

## Findings

### Per-document Diátaxis + clarity verdicts

- **tutorial** — needs-revision (both lenses). Diátaxis: 10 findings, 3
  high. Clarity: 7 findings, 2 high. Most serious: the document opens
  declaring one carried example (Modelo 303, IVA, period 1T) but Step 4
  silently switches to Modelo 130, contradicting the on-rails promise
  and the transactions imported in Steps 2-3. Compounded by How-to /
  Reference contamination (exhaustive provider lists, JSON-envelope
  field catalogs, flag enumerations, troubleshooting branches, "why"
  asides) that belong in the How-to or generated Reference.
- **how-to** — needs-revision. Diátaxis 7 (0 high); clarity 8 (3 high):
  load-bearing terms (`modelo`, `casilla`, `fichero-BOE`) used before
  they are glossed.
- **explanation** — needs-revision. Diátaxis 4 (1 high): a numbered
  command sequence reads as a how-to inside an explanation. Clarity 12
  (4 high): `modelo`, `casilla`, `autónomos`, `fichero-BOE`, `BOE`,
  `AEAT` unglossed at first use.
- **getting-started** — minor (Diátaxis 4, clarity ready).
- **authoring-guide** — clarity needs-revision (2 high): a "three
  surfaces" count stated inconsistently; `apidocs` / "stub" undefined.
- **architecture** — clean (both lenses ready).
- **README** — clean (Reference-primary, light How-to secondary).

### Docstring rollout (landed)

Sixty-four readability-reviewed Google-style docstrings were applied
across nine modules: the three modelo persistence repositories
(`bucket_id` / `exists` / `load` / `save`), four registry oracle
modules (driver-protocol and oracle members), and the user-profile and
censo application repositories. Each docstring was drafted against the
`core/identity` baseline, glosses the domain nouns on first use, and
uses plain double-backtick literals (stdlib cross-references
module-qualified) so the nitpicky `-n -W` gate resolves them.

### Documentation-build gate

The gate ran `sphinx -b html -n -W` single-threaded (~27 min). Switched
to the `dummy` builder with `-j auto` (measured 27:27 -> 7:52, a
control run confirmed the dummy builder still raises every
cross-reference warning the html builder did). A relocation-orphan stub
(`aeat.adapters.inbound.pdf._errors`) was found hard-crashing the gate;
`apidocs scaffold` resynced the stub tree (2 orphans removed, 9 missing
stubs added) and a surfaced bare `InvalidOperation` reference was
module-qualified.

## Recommendations

1. **Tutorial structural fix (highest priority).** Resolve the
   303-vs-130 contradiction by committing to one modelo end to end.
   Requires grounding: verify the Modelo 303 lifecycle runs end to end
   through the CLI with the imported transactions before rewriting
   Steps 4-6 to 303; otherwise re-ground the intro and Steps 2-3 to the
   modelo that does. Then strip the How-to / Reference contamination to
   link-outs.
2. **Clarity glosses (high value, low risk).** Apply one-line first-use
   glosses for `modelo`, `casilla`, `fichero-BOE`, `BOE`, `AEAT`,
   `autónomos` across how-to, explanation, and getting-started; fix the
   authoring-guide "three surfaces" count and define `apidocs`/"stub".
3. **Explanation type-purity.** Convert the numbered command sequence to
   discursive prose that explains the conceptual progression, naming
   commands only illustratively, and link to the tutorial for the steps.
4. **Continue the docstring cadence** down the `interrogate` worklist;
   re-enrol `registry/_schema.py` once its concurrent refactor settles.

Each user-facing prose change is applied through a documentation review
agent (not hand-edited) and verified by the nitpicky build before
commit, per the educational-surface ADR.

## Codification candidates

The durable lessons from this pass were already codified as project
rules during the campaign and need no new rule here:

- `aeat-docs-scaffolding-cli` — maintain `docs/api/*.rst` only through
  `aeat.apidocs`; re-scaffold on every relocation (orphan stubs crash
  the nitpicky gate).
- `aeat-locales-cli` — the sibling locale-catalogue CLI discipline.

The documentation-build performance fix (`dummy` builder + `-j auto`)
landed directly in the gate harness and the `just docs` recipe; it is a
one-site configuration change, not a cross-session constraint, so it is
recorded here rather than promoted to a rule.
