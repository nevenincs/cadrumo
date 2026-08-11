"""Anthropic optional-extra failures preserve the core typed boundary."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

from ...core import ANTHROPIC_EXTRA

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]


def test_client_and_provider_loader_preserve_the_registered_extra_facts() -> None:
    """Both real lazy-import boundaries propagate one machine-readable refusal."""
    code = textwrap.dedent(
        f"""
        import json
        import sys

        class AbsentAnthropic:
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.', 1)[0] == {ANTHROPIC_EXTRA.import_name!r}:
                    raise ModuleNotFoundError(name=fullname)
                return None

        for module_name in tuple(sys.modules):
            if module_name.split('.', 1)[0] == {ANTHROPIC_EXTRA.import_name!r}:
                del sys.modules[module_name]
        sys.meta_path.insert(0, AbsentAnthropic())

        from cadrumo.core import MissingOptionalExtraError
        from cadrumo.core.config import load_settings
        from cadrumo.llm import LLMClient, LLMProvider
        from cadrumo.llm._providers.anthropic import _load_anthropic_sdk

        client = LLMClient(settings=load_settings())
        boundaries = (
            lambda: client._build_adapter(LLMProvider.ANTHROPIC),
            _load_anthropic_sdk,
        )
        outcomes = []
        for boundary in boundaries:
            try:
                boundary()
            except MissingOptionalExtraError as error:
                outcomes.append(error.extra.model_dump(mode='json'))
        print('ANTHROPIC_BOUNDARIES:' + json.dumps(outcomes, sort_keys=True))
        """,
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and test-owned driver source
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    marker = "ANTHROPIC_BOUNDARIES:"
    line = next(row for row in completed.stdout.splitlines() if row.startswith(marker))
    outcomes = json.loads(line.removeprefix(marker))
    expected = ANTHROPIC_EXTRA.model_dump(mode="json")
    assert outcomes == [expected, expected]
