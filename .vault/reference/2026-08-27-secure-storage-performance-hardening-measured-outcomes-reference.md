---
tags:
  - '#reference'
  - '#secure-storage-performance-hardening'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:ccf32d62a417dc1001773274e34dc111ed33c3577f313e15c9158d75ef2cc402'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
  - "[[2026-08-22-secure-storage-performance-hardening-adr]]"
  - "[[2026-08-27-secure-storage-performance-hardening-w02-demand-loading-residue-audit]]"
---

# `secure-storage-performance-hardening` reference: measured outcomes

Every figure below was measured on this tree, in fresh child processes, and is
reproducible by the gate named beside it. Nothing here is estimated.

## Import reductions

| Surface | Before | After |
| --- | --- | --- |
| Registry modules at CLI bootstrap | 138 | **0** |
| `domain.modelos` root import | 277 modules, 60 registry | **3 modules, 0 registry** |
| `application.filing` root import | 518 modules, 61 persistence | **378 modules, 0 persistence** |
| `app/registry/manuals/list` resolution | registry 176, crypto 30, custody 3, storage 192 | **registry 150** |
| Profile-summary boundary | 116 modules (aggregate path) | **49 modules** |

The bootstrap figure is the widest: `_common` imported the registry authority
at module scope for ONE call site on a refusal path, and `_common` loads on
every command, so all 365 nodes -- including all 68 state-free ones -- paid for
the calculation registry.

## Filesystem effects

| Observation | Before | After |
| --- | --- | --- |
| Paths created by `config profile list` | 27 | **2** |
| Nodes exempt from storage materialisation | 0 | **218 of 365** |

The 2 remaining are `logs` and `logs/cadrumo.log`, the process-wide diagnostic
channel opened at module import before any command is selected. Every leaf
invocation previously ran an unconditional `ensure_storage_tree()`, so a
read-only listing built `blobs`, `financial`, `secrets`, `submissions` and the
whole `cache` tree before doing anything.

Gate: `test_cli_side_effect_contract` -- 93 bare-invocable side-effect-free
leaves, 98 cases green.

## Populated scaling

| Store | Storage calls |
| --- | --- |
| Empty | 3619 |
| One profile | 3787 |
| Eight profiles | 4858 |

First profile 168 calls, marginal profile 155, ratio **0.92** -- linear, and
slightly sublinear from caching. Asserted as a shape rather than a threshold.

Gate: `test_cli_storage_scaling`.

## Census coverage

| Property | Coverage |
| --- | --- |
| Live nodes in the CommandSpec graph | 365 |
| Distinct capability declarations | 25 (they PARTITION the node set) |
| Nodes resolving without loading ANY capability family | **351 of 365** |
| Capability groups loading only what they declare | 23 of 25 |
| State-free nodes free of all five families | **68 of 68** |
| Import-linter contracts evaluated | 0 (suite aborted) -> **10, 4 kept / 6 broken** |

## Defects the gates found

Nine, every one in a Step already marked complete.

1. Registry loaded at CLI bootstrap for every command.
2. The custody adapter dragged in the authenticated profile aggregate through a
   ten-module chain.
3. Every leaf invocation materialised the whole storage tree.
4. A payload monolith pulled a sibling command's application services.
5. `profile_bucket_scan` was a second, heavier definition of "which profiles
   exist", taking a custody lock and able to publish a label head as a side
   effect of resolving a NAME.
6. `_sandbox_notice` contradicted its own cheapness contract, calling the full
   authenticated path on EVERY emitted line of every command.
7. Three shipped commands could not be constructed at all -- `app ledger ratios
   set`, `app ledger evidence batch`, `app modelo reconcile import` -- each
   raising `ValueError: wrong parameter order`. Unreachable through the real
   CLI.
8. `.importlinter` aborted before evaluating any contract, so all eleven had
   been silently unenforced; the layered architecture contract among them.
9. The shared profiler's family table carried `cadrumo.core.crypto`, a prefix
   matching no module in the tree -- a family scan that could not see part of
   what it claimed to watch.

## Method notes worth keeping

**The union formulation.** Where the expected result is "nothing", a whole set
resolves in ONE child process and the union must be empty -- an empty union is
exactly the claim that each member loaded nothing. 351 nodes settle in one
process. It is NOT valid where the expectation is non-empty: a union proves a
set CONTAINS a violation and never which member, which produced two false reads
in this campaign before it was understood.

**Wall time does not measure code here.** A quiet-control CLI resolution takes
~1.75s on this share, and peer agents routinely run 200 concurrent processes.
Latency assertions would gate contention. Every performance property in this
campaign is therefore asserted on a deterministic proxy -- imported module
counts, storage-call counts, filesystem deltas -- which are exact and immune to
load.

**Hybrid package roots take a lazy map.** `__getattr__` runs only for names
absent from module globals, so a root that DEFINES code and also re-exports can
defer just its re-exports. `application.registry` (89 of 91 names) and
`application.filing` both took it; only the handful of internally-used names
stay eager.
