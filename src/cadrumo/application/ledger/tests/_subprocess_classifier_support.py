"""Real-behaviour subprocess classifier harness, for tests only.

Relocated here from ``domain.transactions`` when the cloud transport was
deleted from production, and the distinction is why it survives the deletion at
all. As a PRODUCTION path this class was the off-host route the campaign exists
to remove: it shelled out to a cloud provider CLI and sent taxpayer document
text to it. As a TEST vehicle it is something else entirely -- it spawns a local
Python process that echoes canned JSON, so the test drives a real subprocess, a
real stdout parse and the real allow-list-guarded validation.

That is why it was not replaced by a stub. A canned-response Protocol
implementation would be a fake, which the project's testing discipline refuses,
and it would stop exercising the parse and validation the real classifier path
depends on. Moving the harness to the test side keeps the real behaviour while
removing the production transport -- the rule bars *a test double living in
production*, not a real harness living in tests.

Ten test modules inject it: classification apply and reject, saturation, split
proposal and apply, the review workflow, run telemetry and evidence wiring.
None of them is a cloud test; they test ledger logic that survives the
deletion, and this was simply their only injection point.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field

from ....domain.transactions.llm import (
    LLMClassificationResponse,
    LLMClassifierError,
    LLMSplitResponse,
    PromptSpec,
    build_split_prompt,
    default_prompt_spec,
    parse_response,
    parse_split_response,
)
from ....domain.transactions.models import Transaction

__all__ = ["SubprocessLLMClassifier"]

_logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 120.0
"""Per-call subprocess budget, carried over from the production original."""


@dataclass(frozen=True)
class SubprocessLLMClassifier:
    """LLM classifier that shells out to a local CLI binary.

    Pipes the prompt via stdin by default (more reliable than a
    positional argument for long multi-line prompts, especially on
    Windows where CreateProcess quoting can corrupt arguments).

    Reads output from stdout. Transaction prompts and classifier
    responses are sensitive financial data, so this adapter deliberately
    avoids file-backed subprocess handoff.

    Set ``prompt_via_argument=True`` for CLIs that reject stdin and
    require the prompt as the final positional argument.
    """

    name: str
    command: tuple[str, ...]
    model: str | None = None
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    spec: PromptSpec = field(default_factory=default_prompt_spec)
    prompt_via_argument: bool = False

    @property
    def decided_by(self) -> str:
        """Return the ``classified_by`` identifier including the model when set."""
        if self.model:
            return f"llm:{self.name}:{self.model}"
        return f"llm:{self.name}"

    def classify(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMClassificationResponse:
        """Shell out to the LLM CLI, parse, validate, return.

        Args:
            transaction: The transaction to classify.
            evidence_text: Optional on-host-extracted attached-evidence text injected
                into the prompt (sent via stdin, never a file).

        Returns:
            A :class:`LLMClassificationResponse` with the parsed classification result.
        """
        stdout = self._run_cli(
            self.spec.render(transaction, evidence_text=evidence_text),
            transaction_id=transaction.transaction_id,
        )
        response = parse_response(stdout, spec=self.spec)
        _logger.debug(
            "llm classify: %s returned classification=%s confidence=%s for transaction %s",
            self.name,
            response.classification.value,
            response.confidence,
            transaction.transaction_id,
        )
        return response

    def propose_split(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMSplitResponse:
        """Shell out with a split-proposal prompt, parse and validate the split.

        Args:
            transaction: The transaction to split.
            evidence_text: Optional on-host-extracted attached-evidence text injected
                into the prompt (sent via stdin, never a file).

        Returns:
            A validated :class:`LLMSplitResponse`.
        """
        stdout = self._run_cli(
            build_split_prompt(transaction, spec=self.spec, evidence_text=evidence_text),
            transaction_id=transaction.transaction_id,
        )
        return parse_split_response(stdout, spec=self.spec)

    def _run_cli(self, prompt: str, *, transaction_id: str) -> str:
        """Shell out to the CLI with ``prompt`` via stdin (never a file) and return stdout."""
        resolved_binary = shutil.which(self.command[0])
        if resolved_binary is None:
            _logger.warning("llm classifier %s not found on PATH: %s", self.name, self.command[0])
            raise LLMClassifierError(f"{self.name} CLI not found on PATH: {self.command[0]}")

        argv: list[str] = [resolved_binary, *self.command[1:]]
        stdin_input: str | None = None
        if self.prompt_via_argument:
            argv.append(prompt)
        else:
            stdin_input = prompt

        _logger.debug("llm classify: spawning %s argv=%s transaction_id=%s", self.name, argv[0], transaction_id)
        try:
            completed = subprocess.run(
                argv,
                input=stdin_input,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            _logger.warning(
                "llm classify: %s timed out after %ss for transaction %s",
                self.name,
                self.timeout_seconds,
                transaction_id,
                exc_info=True,
            )
            raise LLMClassifierError(f"{self.name} CLI timed out after {self.timeout_seconds}s") from exc
        except OSError as exc:
            # Spawn-time failures (PermissionError, ENOEXEC, ENOMEM, Windows
            # CreateProcess errors). Translate so the --all CLI loop can
            # skip this one transaction and continue on the next.
            _logger.error("llm classify: %s spawn failed", self.name, exc_info=True)
            raise LLMClassifierError(f"{self.name} CLI spawn failed: {exc}") from exc
        if completed.returncode != 0:
            _logger.warning(
                "llm classify: %s exited with returncode=%d for transaction %s",
                self.name,
                completed.returncode,
                transaction_id,
            )
            raise LLMClassifierError(
                f"{self.name} CLI exited with {completed.returncode}: {(completed.stderr or completed.stdout)[:400]!r}",
            )
        return completed.stdout


# ── builders + registry ───────────────────────────────────────────
