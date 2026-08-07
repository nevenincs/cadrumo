---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:d897f5dfd61eba365c026937a87525d8d24854a751e803858a3ae3ae2454af0b'
step_id: 'S23'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W05.P07.S23

## Outcome

Ruled, and the ruling is implemented: `EInvoiceXmlParseError` derives from the project error base. It does NOT declare a bare-base rationale.

## The call was live, not hypothetical

`test_exception_base_hygiene.py::test_production_exception_classes_do_not_introduce_unregistered_builtin_roots` was RED and named exactly one class:

    cadrumo.adapters.inbound.einvoice._xml.EInvoiceXmlParseError(ValueError)

The gate offers precisely the two options this Step asks to choose between: derive from `CadrumoError` so the class binds to the error registry, or declare `__bare_base_rationale__` stating why the bare root is deliberate.

## Why the registry, not the rationale

A bare-base rationale is a claim that the refusal is deliberately outside the registry. That is false for this one. It is operator-facing, it is raised on a file the operator supplied, and its own docstring already argues it must refuse loudly rather than return a partial record. An error with that job should reach the operator with a stable code and a translated message, not a bare traceback — which is exactly what registry binding provides.

The sibling settles it. `SanitizerValidationError` in the same `adapters/inbound` tree derives from `(SanitizationError, ValueError)` for the stated reason that it must satisfy pydantic's validator contract "while remaining catchable under the package's unified error hierarchy". The einvoice reader is the same kind of boundary with the same two obligations, and was the only inbound error not following that pattern.

## What landed

- `EInvoiceXmlParseError(CadrumoError, ValueError)` — both bases, each justified in the docstring rather than left to be re-derived.
- `REFUSED_EINVOICE_XML_PARSE` registered in the adapter error-code table, category `REFUSED`, non-retryable.
- `errors.refused.refused_einvoice_xml_parse` translated in all four catalogues through the locales CLI.

Verified directly: the class binds its code, both `issubclass` checks hold, and `parse_hardened_xml(b"")` still raises the refusal.

## Note on the gate

The hygiene gate cannot currently confirm this, because its subclass walk crashes on a peer's in-flight `llm-package-split` module (`NameError: name 'SubprocessProvider' is not defined`). That failure predates and is independent of this change; the binding was therefore verified by direct import rather than through the gate, and the gate should be re-run once the peer's relocation lands.
