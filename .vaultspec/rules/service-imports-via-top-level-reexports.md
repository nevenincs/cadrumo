# Service imports via top-level re-exports

## Rule

Every cross-package import project-wide MUST resolve to the sole canonical
public top-level `__all__` facade of the symbol's owning package. A
cross-package consumer MUST NEVER import from another package's private
`_module` — ownership of `A.B._C...` is `A.B`. Intra-package private imports,
and a package building its own facade out of its own private modules, are fine.

When the symbol is not yet exported, **promotion to `__all__` is a precondition
of the consuming change, not a follow-up**. Eager (`from .module import Name`)
is the default; lazy `__getattr__` / PEP 562 is equally acceptable where the
owning package already uses that pattern, or where eager import costs enough to
matter. This rule governs WHERE a symbol lives, never WHEN its module executes:
lazy resolution keeps exactly one canonical home and one import path, so it
satisfies the ownership constraint rather than bending it. Converting an eager
facade to lazy is a normal, permitted change.

Never mechanically rename a private `_name` straight into `__all__`. Per symbol,
choose one of: rename-to-public and promote a genuinely shared primitive; expose
a narrower purpose-built public API for a single caller's need; or treat the
reach as a design defect to remove.

**There are no standing non-`__init__` re-export bridge modules.** Every
redefinition belongs on its single canonical home. Do not introduce a
pure-reexport shim to avoid a proper facade promotion.

The one shape that is not a bridge and must not be mistaken for one: a module
defining its own optional-dependency fallback classes inside a
`try`/`except ImportError` branch, where no canonical definition exists
elsewhere. The AST scanner misclassifies that as a pure re-export because its
walk does not see definitions nested inside the branch; read the file before
acting on such a report.

## Why

Letting one consumer dot into a package's internals reads to every later
consumer as permission to do the same, and a single tree scan quantified
thousands of cross-package private imports across hundreds of files, plus a
naming collision and latent violations hidden inside a circular-import
workaround. One canonical facade per symbol makes ownership checkable.

## How

- **Good:** a new application-layer service imports `rename_profile` from the
  `user_profile` package's `__all__` re-export, promoted before the consuming
  file was authored.
- **Good:** an underscore-named symbol reached by two or more unrelated
  production packages is renamed public and promoted; one reached by exactly one
  narrow caller instead gets a purpose-built narrower public API.
- **Bad:** importing from a private submodule path
  (`....application.user_profile._orchestration`) — the next agent reads the
  precedent and erodes the boundary.
- **Bad:** stripping the leading underscore from every reached private symbol
  into `__all__` without judging shared-primitive vs single-caller vs design
  defect.

## Source

ADR `2026-07-01-import-centralization-adr` (generalising
`2026-06-03-cli-workflow-redesign-adr`), research
`2026-07-01-import-centralization-research`. Enforced by
`dev/import_hygiene_scan.py` and `src/cadrumo/tests/test_import_hygiene_gate.py`
(a checked-in production baseline ratcheting toward zero). Companion:
`dynamic-import-targets-the-public-facade`.
