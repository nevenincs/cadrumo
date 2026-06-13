---
tags:
  - '#reference'
  - '#cli-testimonial'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-cli-testimonial-findings-inventory-audit]]"
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# Testimonial-driven CLI verification playbook

A repeatable verification pattern that complements codebase audits and
schema-data reviews. Codebase audits read the code; this method
*exercises the product*. It catches a class of defect static review
structurally cannot: import-time crashes, broken readiness checks,
missing operator surfaces, help/runtime drift, silent failure,
exit-code lies, and dead-end workflows.

It found, in two rounds, what the registry-data audits never could:
the `verify -> export` path is unreachable, `profile rename` corrupts
the registry, `auth test` ignores the active profile, `allocate`
silently corrupts tax treatment.

## The pattern

### 1. Discovery

Map the real surface first: `aeat --help`, `aeat config --help`,
`aeat app --help`, and `--help` on subtrees. The persona agents get
accurate ground truth, not guesses.

### 2. Persona swarm

Dispatch sub-agents, each briefed as a concrete HUMAN persona with a
realistic tax goal (a first-time autonoma, a bookkeeper, a company
admin, someone chasing deadlines, ...). Hard rules every persona gets:

- Interact ONLY through `uv run --no-sync aeat ...` and `--help`.
  **No reading source code, tests, or vault docs** - a real user
  cannot, and source-peeking hides real UX walls.
- Isolate state:
  `AEAT_LOCAL_STORAGE_ROOT=.vault-scratch/persona-<name>` - a fresh
  dir per persona so concurrent runs never collide.
- Behave like a non-expert: follow help literally, make plausible
  mistakes, get confused by jargon, capture friction.
- Run REAL commands, quote REAL output verbatim, never invent results.
- Never attempt live AEAT network/submission.

### 3. Testimonial

Each persona writes a first-person testimonial to
`.vault/audit/yyyy-mm-dd-cli-testimonial-<name>.md`: what they tried,
the exact command, expected vs actual (quoted), how it felt, did the
goal succeed, and a numbered **Bugs and gaps** list graded
blocker/major/minor/cosmetic with command + expected + actual.

### 4. Coordinator reproduction

The coordinator does NOT trust testimonials blindly. Reproduce every
blocker/major directly against the live CLI; mark confirmed findings
`[verified]`. Distinguish stable defects from `[transient]`
shared-worktree mid-refactor breakage (an import-smoke over all
`src/aeat/` modules separates the two).

### 5. Consolidated inventory

One verified, severity-graded inventory. Note what genuinely works -
the calculation engine does; say so. Cross-reference findings hit by
multiple personas (independent confirmation raises confidence).

### 6. Remediation loop

Fix safest-first: contained, additive, low-semantic-risk changes
before subtle ones. Each fix: change -> reproduce-fixed against the
live CLI -> add a real-behavior regression test -> commit with
explicit paths (`git commit -- <paths>`). Shared CLI files mean fix
work is sequential, not parallel, to avoid intra-batch collision.
On a shared worktree, cross-committing onto in-flight slices is
accepted once safe standalone work is exhausted.

## Running it again

Re-run when: a CLI-surface change lands; a refactor touches the
import graph; or on a calendar cadence. Vary the personas to reach
uncovered paths (round 2 reached export, profile lifecycle, repair,
deep ledger grooming that round 1 missed). The import-smoke
(`pkgutil.walk_packages` over `aeat`, import each, report failures)
is a cheap standing guard for the import-crash class - worth
promoting into the CI test surface.

## Why it is locked in

Schema/data audits and code review verify *structure and intent*.
This verifies *behaviour and reachability*. The two are complementary
and neither substitutes for the other. Treat this as a standing,
recurring axis of the verification cadence - not a one-off.
