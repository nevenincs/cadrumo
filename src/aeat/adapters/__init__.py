"""Adapter layer of the hexagonal architecture.

Houses the inbound (:mod:`aeat.adapters.inbound`) and outbound concrete
integrations that translate between external interfaces (PDFs, banks,
AEAT endpoints) and the pure :mod:`aeat.domain` model.

This module uses :class:`SensitivityClass` for data classification policies
and :class:`Envelope` for encrypted storage.
"""
