"""Canonical catalogue of Google Workspace test fixtures.

This module is the single source of truth for which Drive / Sheets /
Docs / Forms fixtures the project provisions for its
``@pytest.mark.live_read`` suite. The catalogue lives as a Python literal so
code review and diff are trivial, and every entry is a strict
pydantic v2 model per the project-wide pydantic mandate.

The companion :mod:`provision_google_fixtures` and
:mod:`teardown_google_fixtures` scripts read :data:`CATALOGUE` and walk
the parent/child tree. Tests may also import :data:`CATALOGUE` via an
inline ``sys.path`` adjustment — see
``tests/live/test_google_fixtures_smoke.py``.

Adding a new fixture is an additive edit: append a ``FixtureSpec``
entry, pick a stable kebab-case ``fixture_id``, add the matching env
var to :class:`aeat.core.config.Settings` and ``env/.env.example``, and
re-run ``just google-fixtures-provision``.

The fixtures are **synthetic-only**. No real client data, real AEAT
response content, real credential material, or real PII ever belongs in
a Google Workspace fixture. The seed values below are deliberately
inert machine-generated sentinels.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# The inert sentinel written into every seedable fixture. Any live
# smoke test asserts this exact string is readable through the Google
# Workspace integration path.
SMOKE_SENTINEL = "aeat-fixture-smoke-ok"


class FixtureKind(StrEnum):
    """Closed enumeration of supported Google Workspace fixture kinds."""

    DRIVE_FOLDER = "drive_folder"
    SHEET = "sheet"
    DOC = "doc"
    FORM = "form"


class FixtureSpec(BaseModel):
    """Strict, frozen metadata for a single Google Workspace test fixture.

    Attributes:
        fixture_id: Stable kebab-case slug identifying the fixture in
            the catalogue. Used as the key in :class:`FixtureCatalogue`.
        kind: The fixture's Workspace type.
        title: Title to set on the provisioned Google document. Also
            used by the idempotent find-or-create dedup to locate an
            existing fixture on re-runs.
        parent_id: The catalogue ``fixture_id`` of the parent folder, or
            ``None`` for the root folder itself.
        seed_a1: Value to write to cell ``A1`` on a freshly provisioned
            Sheet. Ignored for non-Sheet kinds.
        seed_body: Body text to write into a freshly provisioned Doc.
            Ignored for non-Doc kinds.
        env_var_name: The uppercase environment variable name under
            which the provisioned resource ID is persisted into
            ``env/.env``. Must match a field on
            :class:`aeat.core.config.Settings`.
        description: Human-readable description of the fixture's role.
        consumed_by: Free-form reference to the issue(s) or test
            module(s) that read this fixture at runtime.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    fixture_id: str = Field(..., min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    kind: FixtureKind
    title: str = Field(..., min_length=1)
    parent_id: str | None = None
    seed_a1: str | None = None
    seed_body: str | None = None
    env_var_name: str = Field(..., pattern=r"^[A-Z][A-Z0-9_]*$")
    description: str = Field(..., min_length=1)
    consumed_by: str = Field(..., min_length=1)


class FixtureCatalogue(BaseModel):
    """Strict container bundling every :class:`FixtureSpec` in the project."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    entries: dict[str, FixtureSpec]

    def root_folder_spec(self) -> FixtureSpec:
        """Return the single :attr:`FixtureKind.DRIVE_FOLDER` entry with no parent.

        Returns:
            The catalogue's root folder spec.

        Raises:
            ValueError: If zero or more than one candidate root folder
                exists. The catalogue is expected to hold exactly one.
        """
        roots = [
            spec for spec in self.entries.values() if spec.kind is FixtureKind.DRIVE_FOLDER and spec.parent_id is None
        ]
        if len(roots) != 1:
            msg = f"fixture catalogue must declare exactly one root folder, found {len(roots)}"
            raise ValueError(msg)
        return roots[0]

    def children_of(self, parent_fixture_id: str) -> list[FixtureSpec]:
        """Return every fixture whose ``parent_id`` equals ``parent_fixture_id``.

        Args:
            parent_fixture_id: The ``fixture_id`` of the parent folder.

        Returns:
            Ordered list (catalogue insertion order) of child specs.
        """
        return [spec for spec in self.entries.values() if spec.parent_id == parent_fixture_id]

    def iter_specs(self) -> Iterator[FixtureSpec]:
        """Iterate specs in catalogue insertion order.

        Explicitly named (not ``__iter__``) because ``BaseModel.__iter__``
        yields ``(field_name, value)`` tuples — overriding it would break
        pydantic's model-iteration contract and force a ``type: ignore``.
        """
        return iter(self.entries.values())


# ── Catalogue literal ──────────────────────────────────────────────────────
#
# Keep this list minimal. Add a new entry only when a concrete live test
# is ready to consume it — see the ADR decision matrix for the rationale.

_ROOT_FOLDER = FixtureSpec(
    fixture_id="aeat-test-fixtures-root",
    kind=FixtureKind.DRIVE_FOLDER,
    title="aeat-test-fixtures",
    parent_id=None,
    seed_a1=None,
    seed_body=None,
    env_var_name="AEAT_GOOGLE_TEST_FIXTURES_FOLDER_ID",
    description="Root Drive folder that parents every Google Workspace test fixture.",
    consumed_by="#13 and any future live test that reads a project-owned fixture",
)

_SMOKE_SHEET = FixtureSpec(
    fixture_id="aeat-test-smoke-sheet",
    kind=FixtureKind.SHEET,
    title="aeat-test-smoke-sheet",
    parent_id="aeat-test-fixtures-root",
    seed_a1=SMOKE_SENTINEL,
    seed_body=None,
    env_var_name="AEAT_GOOGLE_TEST_FIXTURE_SMOKE_SHEET_ID",
    description="Smoke-test Sheet: cell A1 holds the inert sentinel read by the live smoke test.",
    consumed_by="#13 tests/live/test_google_fixtures_smoke.py",
)

_SMOKE_DOC = FixtureSpec(
    fixture_id="aeat-test-smoke-doc",
    kind=FixtureKind.DOC,
    title="aeat-test-smoke-doc",
    parent_id="aeat-test-fixtures-root",
    seed_a1=None,
    seed_body=SMOKE_SENTINEL,
    env_var_name="AEAT_GOOGLE_TEST_FIXTURE_SMOKE_DOC_ID",
    description="Smoke-test Doc: body holds the inert sentinel read by the live smoke test.",
    consumed_by="#13 tests/live/test_google_fixtures_smoke.py",
)


CATALOGUE: FixtureCatalogue = FixtureCatalogue(
    entries={
        _ROOT_FOLDER.fixture_id: _ROOT_FOLDER,
        _SMOKE_SHEET.fixture_id: _SMOKE_SHEET,
        _SMOKE_DOC.fixture_id: _SMOKE_DOC,
    }
)


__all__ = [
    "CATALOGUE",
    "SMOKE_SENTINEL",
    "FixtureCatalogue",
    "FixtureKind",
    "FixtureSpec",
]
