"""Inbound adapters: parse external artefacts into strict domain records.

Subpackages turn AEAT-side artefacts (declaración / borrador PDFs,
financial statements, etc.) into pydantic v2 records consumable by
:mod:`aeat.application` and :mod:`aeat.domain`.

This module uses :class:`Declaracion`, :class:`BorradorObservation`,
:class:`FinancialProvider`, and :class:`Justificante` for parsing external inputs.
"""
