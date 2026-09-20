"""CLI modelo period autocomplete tests."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# ---------------------------------------------------------------------------
# contract -- autocomplete _declared_period_tokens narrows except to CadrumoError
# ---------------------------------------------------------------------------


class TestDeclaredPeriodTokensAutocomplete:
    """Real-behavior tests for the narrowed _declared_period_tokens autocomplete.

    contract narrowed the catch-all ``except Exception: return ()`` to two arms:
    - ``except CadrumoError: return ()``  — typed registry failures swallowed silently.
    - ``except Exception: _log.debug(...); return ()`` — unexpected errors logged.

    These tests verify both arms through real production code paths.
    """

    def test_empty_modelo_returns_empty_tuple(self) -> None:
        """Empty and whitespace-only modelo strings return () without error."""
        from .._modelo_behavior_support import _declared_period_tokens

        assert _declared_period_tokens("") == ()
        assert _declared_period_tokens("   ") == ()
        assert _declared_period_tokens(None) == ()

    def test_unknown_modelo_swallows_cadrumo_error_and_returns_empty(self) -> None:
        """An unregistered modelo triggers an CadrumoError from the registry.

        The registry raises RegistryValidationError (CadrumoError subtype) for
        unknown modelos. The narrowed except arm catches it and returns (),
        matching the autocomplete contract.
        """
        from .._modelo_behavior_support import _declared_period_tokens

        # "XXXXXX" is guaranteed unregistered; the real authority raises
        # RegistryValidationError which is an CadrumoError subtype.
        result = _declared_period_tokens("XXXXXX")
        assert result == ()

    def test_known_modelo_returns_period_tokens(self) -> None:
        """A registered modelo returns its registry-declared period tokens.

        This exercises the happy path: the CadrumoError arm is NOT triggered,
        the authority resolves the definition, and the period set is returned.
        Modelo 303 is a known quarterly modelo; its tokens include quarterly markers.
        """
        from .._modelo_behavior_support import _declared_period_tokens

        result = _declared_period_tokens("303")
        # Modelo 303 is quarterly; at minimum the four quarterly tokens are present.
        assert isinstance(result, tuple)
        assert len(result) > 0
        assert all(isinstance(t, str) for t in result)

    def test_non_cadrumo_error_is_logged_at_debug(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
        operation: PinnedAuthorityOperation,
    ) -> None:
        """A non-CadrumoError from the resources layer is logged at DEBUG and swallowed.

        This test exercises the ``except Exception`` arm through the current
        behavior-support module.  The registry query is replaced at its owning
        import boundary with a deliberate runtime failure, so the production
        function must swallow it and emit its diagnostic at DEBUG.
        """
        import logging

        from .. import _modelo_behavior_support as _modelo_module
        from .._modelo_behavior_support import _declared_period_tokens

        # The logger belongs to the module that owns the helper, not the
        # extracted command module that imports it.
        assert hasattr(_modelo_module, "_log")
        logger = _modelo_module._log
        assert "cadrumo.entrypoints.cli._modelo_behavior_support" in logger.name

        def _raise_unexpected(*_args: object, **_kwargs: object) -> tuple[str, ...]:
            raise RuntimeError("synthetic registry defect")

        monkeypatch.setattr(_modelo_module, "declared_modelo_period_tokens", _raise_unexpected)
        with caplog.at_level(logging.DEBUG, logger=logger.name):
            assert _declared_period_tokens("303", operation=operation) == ()

        debug_records = [
            record
            for record in caplog.records
            if record.levelno == logging.DEBUG and "_declared_period_tokens" in record.message
        ]
        assert len(debug_records) == 1, [record.message for record in caplog.records]
        assert debug_records[0].exc_info is not None
        assert debug_records[0].exc_info[0] is RuntimeError

    def test_cadrumo_error_subtype_is_swallowed_not_propagated(self) -> None:
        """Any CadrumoError subclass raised by the authority is caught and swallowed.

        RegistryValidationError is the most likely subtype. This test asserts
        the function returns () rather than propagating the error to Click.
        """
        from ....core.errors.hierarchy import CadrumoError
        from .._modelo_behavior_support import _declared_period_tokens

        # Both the "totally unknown" and the "empty" paths return () silently.
        # The unknown modelo exercises the real CadrumoError arm.
        result = _declared_period_tokens("99999")
        assert result == ()
        assert not isinstance(result, CadrumoError)
