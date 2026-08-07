---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:3a304d73b705660f922db8f74c6009b2375db53a7c76e9e5c1f204d713c5b821'
step_id: 'S54'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Guard every cadrumo.llm entry point with require_optional_extra on the llm extra and enrol cadrumo.llm in the import-linter layers and forbidden contracts, proven by a deliberate violating import observing red

## Scope

- `src/cadrumo/llm/__init__.py`

## Description

- Pin the injection regression test's reach through the outbound adapter, restoring the inference persistence contract.
- Mutation-prove the outward contract by injecting a persistence import into the inference facade.
- Mutation-prove the three inward enrolments with temporary probe modules on the domain, core and application tiers.
- Leave the guard half undone, and open it as its own row.

## Outcome

**This row is deliberately left unchecked.** Its text conjoins two deliverables — guard every entry point, *and* enrol the subpackage in the contracts — and only the second was delivered. The first was deferred by decision, not missed, so checking the row would make a deliberate deferral indistinguishable from completed work. The carried half is tracked as its own row rather than as a note here.

The enrolment half turned out to be **already complete on arrival**. The subpackage was already listed in the domain-not-adapters and core-not-outer forbidden sets, already had its own contract forbidding it to reach persistence, and was already placed in the layered contract as a sibling of the adapters package on the adapter tier. This is the same shape the dependency-closure Step hit earlier in the same Phase: the declaration had landed from other work and the **proof had not**. Two occurrences in one Phase is enough to name it as a pattern — a Step whose deliverable is a declaration will often read as undone when what is actually missing is the evidence that the declaration bites.

So the work became proving it. All four contracts were mutation-proven, and each fired on precisely the injected edge.

The baseline was **two broken contracts, not one**. Beside the known application-to-adapters break from a neighbouring lane's uncommitted work, the persistence contract was broken by the injection regression test that landed with the boundary gate: it reaches the outbound adapter, whose usage recorder resolves the crypto substrate. That was pinned per chain origin, matching the fourteen test carve-outs the contract already carried, so a new *production* edge still fails. The production edge inventory is unchanged.

**The guard half cannot be done where the Step says to do it, and that is the substantive finding.** The Step names the package facade as its target. A guard there fires when the attribute is *resolved*, and the ledger's classification module binds three of these symbols at module level, one of which resolves through the facade's lazy attribute hook. So in a core install the guard would raise while the ledger module was being imported, and the ledger CLI would refuse to load at all — the "silently absent verb" outcome the governing decision explicitly forbids, reached from the opposite direction. The guard has to fire at **invocation**, not at attribute access.

The established idiom already answers where that is: the availability check sits inside the entry point, immediately before the lazy third-party import, at five production sites. A facade wrapper would be a second competing refusal idiom beside those, which the architecture rules forbid outright, and wrapping the classes would break identity checks against them. So the guards belong in the entry-point modules, which are outside this row's declared file scope and two of which belong to lanes active at the time.

Five entry points carry no guard: the vision draft reader, the text draft reader, the vision classifier, the text classifier, and the tabular column-role mapper. Only the page rasteriser is guarded. The honest exposure statement is narrower than five, because the PDF vision route funnels through that guarded rasteriser — the genuinely exposed paths are the image-input vision route, the whole text route, and the tabular mapping call.

The carried row deliberately bundles the guards **with** the probe repoint rather than landing them first. The probe still names the imaging package, which is an unconditional base dependency, so every guard would be inert on landing. Landing them separately would put guards in the tree that gate nothing while appearing to, across two review surfaces. Landing them together makes the boundary real in one reviewable change, and clears the absent-extra packaging lane's precondition in the same window.

## Verification

Baseline, then after the test pin:

    uv run --no-sync lint-imports
    Contracts: 5 kept, 1 broken.

The one remaining break is the neighbouring lane's application-to-adapters edge, left alone deliberately.

Outward contract, injecting a persistence import into the facade. The mutation window opened and closed inside a single command with restoration in a finally block, and the restored file was compared by SHA-256 rather than assumed:

    RESTORED EXACTLY: True
    Contracts: 4 kept, 2 broken.
    cadrumo.llm is not allowed to import cadrumo.adapters.persistence:
    -   cadrumo.llm -> cadrumo.adapters.persistence.storage.sql

Inward enrolments, proven with three **temporary new modules** on the domain, core and application tiers rather than edits to peer-owned files. The technique is worth reusing: a new file cannot be swept into a peer's commit as a modification to their work, it is obvious on sight if a run dies before cleanup, and it needs no captured-bytes restore.

    ALL PROBES REMOVED: True
    Contracts: 3 kept, 3 broken.
    cadrumo.domain is not allowed to import cadrumo.llm:      domain._mutation_probe -> cadrumo.llm
    cadrumo.core is not allowed to import cadrumo.llm:        core._mutation_probe -> cadrumo.llm
    cadrumo.application is not allowed to import cadrumo.llm: application._mutation_probe -> cadrumo.llm

The contracts that fired are the persistence contract, the domain forbidden set, the core forbidden set, and the layered contract. The last is the one worth reading twice: application-to-inference edges are pinned individually, and the probe confirms a **new unpinned** edge still fails while the pinned ones pass — which is the property that makes the layered enrolment load-bearing rather than decorative.

## Notes

The guard half is carried forward as its own row rather than recorded only here, so it is a tracked obligation with a verification gate instead of a paragraph someone has to find.

That row's test approach is already settled: block the imported module with a meta-path finder in a fresh interpreter, the way the existing refusal test does. That proves each refusal on the real path without depending on the probe, so the guards can be verified even though the probe is what makes them live.

One surface underneath that future work has already moved: a neighbouring lane landed role-named cloud settings and a cloud candidate in the model catalogue, so the general model setting now resolves to the weakest cloud candidate rather than a hand-typed literal. It does not change the guard placement, but the row's author should not assume the settings surface is as this record found it.

No environment sync was run, and no accelerator was touched. The probe repoint was deliberately not made here: the NVML binding is absent from the current environment, so flipping the probe today would make the extra read as absent and begin refusing live surfaces including rasterisation, which the vision route depends on.
