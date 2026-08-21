---
name: aeat-architecture-boundaries
trigger: always_on
---

# AEAT architecture boundaries

## Placement

Place Python application code under `src/cadrumo/`. Do not add top-level Python
packages, ad-hoc module roots, or hidden parallel implementations. Keep the
accepted hexagonal direction: domain logic independent from adapters, and
inbound, outbound, persistence, application, entrypoint and core responsibilities
separated. Keep the CLI root surface to `config` and `app` — never a third root
command family.

**Every Python test file lives under a `tests/` directory** at the narrowest
owning package or architectural boundary. A naked `test_*.py` beside
implementation modules pollutes the code namespace and is forbidden.

**A registry binding or resolver family** — counterpart, ledger, invoice,
detail-record, withholding, previous-filing, and any new one — lives in its own
per-family module under `domain/calculations/registry/`, consumed only through
the package facade. New families follow the established shape: selector model,
typed validator registered in the dispatch table, `resolve_*` functions. The
`_bindings.py` aggregator holds the cross-family dispatch table and re-exports;
it does not accrete family implementations.

## Typed boundaries

Expose validated boundary data through pydantic v2 models, with strict config
where practical. Do not expose bare `dict[str, Any]` for persisted records, wire
payloads, configuration, CLI input, MCP messages, LLM responses, or fixtures.

**Type every constant-like axis.** Closed value sets — period codes, output
languages, lifecycle states, source kinds, auth providers — MUST be a StrEnum (or
`Literal` where appropriate) in `core/`. Production code and CLI handlers accept
and emit enum members, not raw strings; registry TOML stays free-form and the
loader hydrates the typed enum at the boundary; tests assert against enum
members.

**Hint accepted values at the CLI boundary.** Every Typer argument whose value is
a closed enum declares that enum as its type, so click renders the accepted set
on parse failure. A late registry-driven refusal is acceptable for axes depending
on dynamic registry data, but it MUST list the accepted set — never a bare "value
invalid".

## Imports resolve to the owning package's facade

Every cross-package import MUST resolve to the sole canonical public top-level
`__all__` facade of the symbol's owning package. A cross-package consumer MUST
NEVER import from another package's private `_module` — ownership of `A.B._C...`
is `A.B`. Intra-package private imports, and a package building its own facade
from its own private modules, are fine.

When the symbol is not yet exported, **promotion to `__all__` is a precondition
of the consuming change, not a follow-up.** Eager is the default; lazy
`__getattr__` / PEP 562 is equally acceptable where the package already uses that
pattern or eager import costs enough to matter. This governs WHERE a symbol
lives, never WHEN its module executes — lazy resolution keeps one canonical home
and one import path, and converting an eager facade to lazy is permitted.

Never mechanically rename a private `_name` into `__all__`. Per symbol: rename
and promote a genuinely shared primitive; expose a narrower purpose-built public
API for a single caller's need; or treat the reach as a design defect to remove.

**A dynamic `importlib.import_module` cycle-break is sanctioned, but its module
string is bound by the same ownership rule** — it must name the public facade,
never a private submodule. The AST scanner cannot see a string-built target, so
this is author discipline: read the target exactly as if it were
`from X import Y`.

**There are no standing non-`__init__` re-export bridge modules.** The one shape
that is not a bridge: a module defining its own optional-dependency fallback
classes inside a `try`/`except ImportError` branch, with no canonical definition
elsewhere — the scanner misclassifies that as a pure re-export because its walk
does not see definitions nested inside the branch.

## No shims, no parallel write paths

Do not introduce shims, compatibility layers, deprecation paths, or duplicate
legacy APIs. Move callers to the canonical path instead.

**A new service must delegate to an existing single-writer primitive rather than
re-implementing its write path**, preserving its atomicity and lifecycle-event
emission. The service emits its own surface-level event **in addition to** the
primitive's: the lifecycle event records the data change, the surface event
records the operator's verb invocation, and a later query distinguishing "record
relabelled" from "operator invoked the verb" depends on both. Re-implementing
re-introduces the torn-write risk the primitive eliminates and creates shadow
event emission.

## Relocations are atomic

Land every symbol relocation in ONE explicit-path commit: the canonical-site
move, every consumer update, every fixture update, and every `__all__` baseline
update share one git index and one commit. Run
`uv run --no-sync pytest --collect-only -q` immediately before and observe clean
collection. Never split the move from the consumer sweep, and never reintroduce a
re-export as a temporary bridge. One Step = one symbol = one atomic commit; tag
the subject `relocation:<symbol>`.

## Source hygiene

Keep source free of project-management metadata: no waves, phases, agent names,
issue workflow, handover state, temporary migration labels, or process history in
production identifiers, comments, fixtures, schemas, or public APIs. Use domain
names that stay true after the current plan changes. Do not land design-only
implementation shells — ship working behavior, executable validation and tests
together. Add comments sparingly and only for *why*; never describe changes
through comments.

**The term "binding" is RESERVED** for the registry-data-input concept
(`DataBindingDefinition`, its value carrier, its source resolvers). Account
scoping, parsing helpers, verification gates and other concepts MUST NOT be named
"binding"; when two concepts would share the name, the non-registry-input one is
renamed to what it actually does. Two unrelated `_profile_binding.py` modules
once shipped side by side, one an OAuth scoping resolver and one the registry
profile-fact resolver.

## How

- **Good:** a new service imports `rename_profile` from the owning package's
  `__all__` re-export, promoted before the consuming file was authored.
- **Good:** the OAuth resolver is `_active_profile.py`; the string-to-Decimal
  parser is `_decimal_parsing.py`. The registry profile-fact resolver keeps the
  binding name — it is correct there.
- **Good:** `src/cadrumo/application/modelo/tests/test_work_addressing.py`.
- **Bad:** `src/cadrumo/application/modelo/test_work_addressing.py` beside the
  implementation modules.
- **Bad:** importing from a private submodule path, or a blanket
  underscore-strip promotion without judging shared-primitive versus
  single-caller versus design defect.
- **Bad:** naming a new module `_*_binding.py` for a session, identity, parsing
  or verification concern.
- **Bad:** a `rename` that opens its own bucket session, decrypts, mutates,
  re-encrypts, then separately rewrites the manifest label — re-implementing the
  cross-store atomicity the repository holds.

Enforced by `dev/quality/import_hygiene_scan.py` and
`dev/tests/test_import_hygiene_gate.py` -- both outside the `src/` test lanes, so
run them explicitly. Source: ADRs
`2026-07-01-import-centralization-adr`, `2026-06-05-test-topology-refactor-adr`,
`2026-06-03-cli-workflow-redesign-adr`,
`2026-06-14-bindings-interface-hardening-adr` (decisions E, F).
