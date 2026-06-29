"""Inbound adapter namespace for external artefact import.

This package root exports no parser classes. Focused child packages own the
actual import contracts: :mod:`aeat.adapters.inbound.declaracion`,
:mod:`aeat.adapters.inbound.borrador`,
:mod:`aeat.adapters.inbound.justificante`, :mod:`aeat.adapters.inbound.pdf`,
:mod:`aeat.adapters.inbound.financial`, :mod:`aeat.adapters.inbound.identity`,
and :mod:`aeat.adapters.inbound.sanitizer`.

Inbound adapters parse AEAT-side PDFs, financial statements, identity inputs,
and sanitised fixture artefacts into strict records consumed by
:mod:`aeat.application` and :mod:`aeat.domain`. They do not own application
workflow, persistence policy, or CLI presentation.
"""
