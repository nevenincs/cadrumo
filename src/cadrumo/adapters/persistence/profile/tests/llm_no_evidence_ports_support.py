"""LLM classification ports for tests whose path must never reach a reader."""

from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn

from .....application.ledger.evidence_textlayer_ports import EvidenceTextLayerPorts
from .....application.ledger.llm_classification_ports import LLMClassificationPorts
from .....core.model_roles import ModelRole

__all__ = ["NO_EVIDENCE_LLM_PORTS"]


def _unused_llm_port(*_args: object, **_kwargs: object) -> NoReturn:
    """Fail loudly if a no-evidence test reaches an unused reader port."""
    raise AssertionError("the no-evidence path must not use this reader port")


def _run_reader(_role: ModelRole, run: Callable[[], object]) -> object:
    return run()


def _record_classifier_run(run: Callable[[], object], _provider: str) -> object:
    return run()


NO_EVIDENCE_LLM_PORTS = LLMClassificationPorts(
    resolve_evidence_input=_unused_llm_port,
    text_layer_ports=EvidenceTextLayerPorts(extract_pages_text=_unused_llm_port),
    rasterise_pdf=_unused_llm_port,
    make_text_classifier=_unused_llm_port,
    make_vision_classifier=_unused_llm_port,
    run_reader=_run_reader,
    record_classifier_run=_record_classifier_run,
)
