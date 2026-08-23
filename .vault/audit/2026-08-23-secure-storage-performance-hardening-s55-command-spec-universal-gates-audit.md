---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:f5273ace9593255d5cf04c5c67f437bd64bbeba7bd514701b3e8e1cdacd3b0dd'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
  - "[[2026-08-23-secure-storage-performance-hardening-command-spec-authority-adr]]"
---

# `secure-storage-performance-hardening` audit: `S55 CommandSpec universal gate review`

## Scope

Audit the S55 universal authority gates against the accepted production-authored `CommandSpec` decision. The review covers detector independence, complete current/future field traversal, distributed-module enrollment, exact deferred-target resolution, legacy-authority absence, and planted negative controls.

## Findings

### former-authority-detector | high | Direct structural declarations could evade the first AST gate

The first detector rejected named legacy registrars and artifacts but accepted direct Typer construction, command decorators, registrar function families, add-command calls, and command path mirrors. The gate was expanded with structural AST classification and independently planted examples for every shape. It also exposed and removed the dormant `OutputLanguageOpt` Typer declaration.

### deferred-target-resolution | high | Module-only checks did not prove public executable symbols

The first target gate used module discovery only, so a missing, private, or wrong-kind qualname inside an existing module could pass. The corrected gate resolves every dotted public qualname, requires callable handlers, requires model-schema target types, and proves missing-module, missing-symbol, private-symbol, and wrong-kind controls.

### distributed-enrollment | high | Aggregate-to-graph equality was circular

The first exact-set test compared a tuple with a graph constructed directly from that tuple. The corrected development gate independently discovers all production `*_command_specs.py` modules, follows the aggregate's import edges, and proves an omitted planted module is detected.

### translation-key-traversal | medium | Confirmation prompt keys were omitted

The first explicit field list did not traverse `confirmation_prompt_key`. The corrected detector recursively walks immutable dataclass fields, so every current and future `TranslationKey` field is enrolled without another maintained field list.

### adversarial-representation-coverage | high | Equivalent syntax could bypass early structural detectors

Repeated independent adversarial passes found representation-specific holes in import and assignment aliases, bound structural methods, dead constructors inside factories and exports, dotted or single-token route maps, and deferred targets nested below parameter, default, and machine-secret records. The final detector resolves alias chains, authorizes constructors only through a closed export grammar, rejects semantic route/path/alias maps independent of mapped representation, and recursively validates every deferred target according to its field role. Every discovered bypass was retained as a planted negative.

## Recommendations

- Keep production runtime consumers on the immutable graph; retain filesystem discovery strictly as a development/release gate.
- Require a planted control whenever the forbidden-authority classifier grows a new structural shape.
- Keep deferred targets public and importable, and keep every operator-facing string represented by an authored locale key.
