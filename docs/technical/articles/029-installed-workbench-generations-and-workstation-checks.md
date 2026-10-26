# Installed workbench generations and workstation checks

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-029` · **Topic:** [Application orchestration and diagnostics](../topics/application-orchestration-and-diagnostics.md)

<!-- preserved:article -->
## Scope

This chunk covers five application files: secure-source assembly for the installed workbench; the operation and public result projection for generation reads; and the canonical workstation health report and its worker operation. Static review only; no authenticated worker, private storage, external provider, or runtime check was executed. This report describes application contracts and does not validate the underlying tax or legal content.

## Workbench generation

The secure read door takes profile-bound repositories and projectors from composition, reads each authority once, and turns the results into immutable safe inputs for Home, Ledger, Declarations, AEAT Sync, Modelo, calendar, and search. Availability is a closed state rather than an empty-list convention: `AVAILABLE` and `STALE` carry a value and observation time; `LOCKED`, `NEVER_CAPTURED`, and `UNAVAILABLE` carry a refusal and no value. A missing reader is therefore distinguishable from a measured empty store. Search is built only when all of its source projections exist; otherwise it preserves a refusal derived from the missing inputs. Input state contract and secure reader (`src/cadrumo/application/workbench_generation.py`) Generation assembly and search (`src/cadrumo/application/workbench_generation.py`)

The reader composes profile, work-unit, calculation-revision, filing, verification, event, custody, and ledger facts. It uses revision tokens where stores provide them and compares decoded catalogues otherwise; before publishing, it rereads the profile and source revisions and refuses a generation if the observed inputs changed. That prevents a Home/search bundle from presenting a stitch across several local writes. Declarations lifecycle output is drawn from a closed event vocabulary and joined only to current work units. Unsupported bulk Modelo projection refuses that source as a whole instead of silently omitting one work unit. Secure reader and capture checks (`src/cadrumo/application/workbench_generation.py`) End-of-capture comparison (`src/cadrumo/application/workbench_generation.py`) Modelo refusal boundary (`src/cadrumo/application/workbench_generation.py`)

Calendar and agenda work can be reused within the authenticated session using a key containing profile content digest, work-unit and filing revisions, local date, pinned authority generation, and a digest of AEAT calendar evidence. The computation uses the Europe/Madrid date derived from its observation time. No memo means recompute; the session owner closes the memo at session end. The calendar evidence is included in the memo key but not reread in `_capture_is_unchanged`; confirm its read result is pinned for the whole generation, or include its source generation in the close check. Calendar memo key and use (`src/cadrumo/application/workbench_generation.py`) Session memo lifecycle (`src/cadrumo/application/workbench_capture_memory.py`)

Home keeps separate zone states for declarations, ledger, actions, agenda evidence, and messages. It offers only supported next actions, orders declaration-specific work ahead of cross-cutting ledger work, and marks a declaration ready only for the verified-complete revision state. Unmeasured ledger areas do not become zero-count actions. An AEAT message store with no captured snapshot is `NEVER_CAPTURED`, not a broken reader. These distinctions give the renderer enough evidence to explain what the operator knows and what is simply absent. Home zone and next-action assembly (`src/cadrumo/application/workbench_generation.py`)

The registered `workbench.generation` operation is profile- and subject-bound, requires a human session (the person's own sign-in, not an enrolled key), and discloses profile/tax values only on the result action. It projects one immutable generation into a strict public mirror, withholds the private search identity base, restores that identity from the sibling projections inside the reader process, and checks that the search state agrees. An exact reviewed-exclusion inventory fails if canonical fields omitted from the public projection change; restoration checks UTC timestamps, profile binding, and projection round-trip equivalence. A serialized result above the paging document limit is refused. Operation access boundary (`src/cadrumo/application/workbench_generation_operation.py`) Public projection and exclusion checks (`src/cadrumo/application/workbench_generation_projection.py`) Projection and restore validation (`src/cadrumo/application/workbench_generation_projection.py`)

## Workstation health operation

`run_workstation_check` gathers effective capabilities, dependency status, preflight rows, and capability/dependency inconsistencies for one immutable profile. It rechecks the active bucket around each stage. The local AI program's row is judged from the components role's quick status row, which the operation reads through an injected reader; a role that returns no row reads as unknown. The report judges the program, the Playwright browser and the optional extras, and reports the measured hardware without judging it. It judges no model and no load: which model each role reads with is the person's selection in the agent's catalogue, and whether a load fits the memory free is cadrumo-agent's answer when it loads the model. An unmeasurable hardware figure is reported as unverified and never as a shortfall. Canonical workstation report (`src/cadrumo/application/workstation_check.py`) Dependency statuses (`src/cadrumo/application/workstation_check.py`)

The worker operation checks the request, operation identity, and active profile; builds ports for that exact profile and authority operation; runs the report in a worker thread; and checks the profile again before retaining it. The snapshot models round-trip dependency and preflight facts through the existing canonical validators. The result projector requires a successful terminal receipt with `NONE` effect, the exact profile subject, and no refusal/failure references. The report is request-bound rather than replayed as if a later check were the same observation. Worker execution and profile checks (`src/cadrumo/application/workstation_check_operation.py`) Receipt-checked result projection (`src/cadrumo/application/workstation_check_operation.py`)

## Coverage appendix

- workbench_generation.py (1,803 lines) (`src/cadrumo/application/workbench_generation.py`)
- workbench_generation_operation.py (216 lines) (`src/cadrumo/application/workbench_generation_operation.py`)
- workbench_generation_projection.py (1,167 lines) (`src/cadrumo/application/workbench_generation_projection.py`)
- workstation_check.py (126 lines) (`src/cadrumo/application/workstation_check.py`)
- workstation_check_operation.py (375 lines) (`src/cadrumo/application/workstation_check_operation.py`)
<!-- /preserved:article -->
