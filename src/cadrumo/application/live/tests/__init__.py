"""Public test-support facade for live-service integration suites."""

from ._notification_document_support import build_service, sancion_pdf_bytes, served_document

__all__ = ["build_service", "sancion_pdf_bytes", "served_document"]
