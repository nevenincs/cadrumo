"""Typed pytest lane scopes and non-vacuous coverage reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: Workflow events that fire only when somebody asks for them. A lane every one
#: of whose reaching workflows is triggered solely by these is WIRED and
#: UNREACHED-IN-PRACTICE: it exists, it is declared, CI can run it, and no push
#: or pull request ever does. Its failure therefore cannot fail anything until
#: an operator goes looking, which is a different and weaker guarantee than the
#: one a green lane list implies. ``repository_dispatch`` is included on the
#: same reasoning -- an external API call, not a change to this tree -- though
#: no workflow here uses it today.
MANUAL_TRIGGERS: Final[frozenset[str]] = frozenset({"workflow_dispatch", "repository_dispatch"})


@dataclass(frozen=True, slots=True)
class TestMarkers:
    """One test and the effective markers pytest resolves for it."""

    test: str
    markers: frozenset[str]


@dataclass(frozen=True, slots=True)
class UnreachableTest:
    """One test no declared lane can select, named so the remedy is decidable."""

    path: str
    test: str
    markers: frozenset[str]

    def describe(self) -> str:
        """Return a one-line report naming the test and why it is held out."""
        markers = ", ".join(sorted(self.markers)) or "no markers"
        return f"{self.path}::{self.test} [{markers}]"


@dataclass(frozen=True, slots=True)
class ReachabilityReport:
    """The reachability finding plus the corpus it was computed over.

    ``analysed`` and ``skipped`` exist so the gate can refuse a vacuous pass: an
    empty ``unreachable`` means nothing if the reader parsed nothing, and a
    reader that silently stopped matching is the false-green this whole module
    is built to refuse.
    """

    unreachable: tuple[UnreachableTest, ...]
    unnamed: tuple[str, ...]
    analysed: int
    skipped: tuple[str, ...]

    def affected_files(self) -> tuple[str, ...]:
        """Return every file holding at least one unreachable test.

        Deliberately NOT "files where no test is selectable": that weaker
        question is what hid the ``os_keychain`` hole, because the file also
        held reachable tests and so never appeared.
        """
        return tuple(sorted({entry.path for entry in self.unreachable}))


@dataclass(frozen=True, slots=True)
class DirectoryCoverageReport:
    """Which test directories a lane's path scope sweeps, and which none does.

    ``analysed`` exists for the same reason :class:`ReachabilityReport` carries
    it: an empty ``uncovered`` means nothing if the walker discovered nothing,
    and a walker that silently stopped matching is indistinguishable from a
    clean tree unless the corpus size is pinned alongside the finding.

    There is no declaration channel. A test directory no lane sweeps is a
    finding, and the remedy is a lane path or deleting the directory.
    """

    uncovered: tuple[str, ...]
    analysed: int


def _within(candidate: str, scope: str) -> bool:
    """Return whether ``candidate`` is ``scope`` itself or sits beneath it.

    One predicate for both path scopes and ``--ignore`` scopes, because two
    spellings of containment drift and only one of them gets the trailing-slash
    case right.
    """
    normalised = scope.replace("\\", "/").rstrip("/")
    return candidate == normalised or candidate.startswith(f"{normalised}/")


@dataclass(frozen=True, slots=True)
class Lane:
    """One declared pytest invocation: what it reaches and what it accepts.

    ``recipe`` names the justfile recipe the invocation sits in, or None when
    the invocation is written inline in a workflow. It is what makes
    :func:`ci_invoked_lanes` able to ask whether CI actually reaches a lane,
    rather than only whether the repository declares one.

    ``triggers`` carries the workflow events that reach the lane -- the union
    over every route, because a lane runs automatically when ANY route to it
    does. It answers the question `recipe` cannot: a lane can be declared,
    wired, and invoked by a workflow that only ever fires on
    ``workflow_dispatch``, so nothing it would catch is caught until a person
    asks. An empty tuple is NOT "manual"; it is "no workflow reaches this lane",
    which is the separate finding :func:`ci_invoked_lanes` already reports by
    dropping the lane. Keep the two apart: conflating them turns a lane CI never
    runs into a lane CI runs on request.

    ``opt_in`` is the second, independent weakening ``triggers`` cannot express.
    A lane can be invoked, and carry real reaching events, and still be skipped
    on every one of them because every job invoking it also requires a
    ``workflow_dispatch`` input whose declared default is falsy. ``triggers``
    answers "what starts the run"; ``opt_in`` answers "does the run then do
    this". Folding the second into the first would report a lane nothing reaches
    by default as merely manual, which is a materially stronger claim.
    """

    source: str
    paths: tuple[str, ...]
    marker_expression: str | None
    recipe: str | None = None
    exclusions: tuple[str, ...] = ()
    triggers: tuple[str, ...] = ()
    opt_in: bool = False

    @property
    def runs_on_change(self) -> bool:
        """Return whether some workflow reaching this lane fires from a change.

        True for a lane any of whose reaching workflows carries a non-manual
        event (``push``, ``pull_request``, ``release``, ``schedule``, ...).
        False both for a manual-only lane and for a lane no workflow reaches, so
        it is never the whole answer on its own -- pair it with
        :attr:`is_manual_only`.
        """
        return any(event not in MANUAL_TRIGGERS for event in self.triggers)

    @property
    def is_manual_only(self) -> bool:
        """Return whether CI reaches this lane but only when asked.

        True exactly when the lane HAS reaching workflows and every event that
        reaches it is in :data:`MANUAL_TRIGGERS`. A lane no workflow reaches is
        False here, because its problem is the stronger, separately reported one.
        """
        return bool(self.triggers) and not self.runs_on_change

    def covers(self, relative_path: str) -> bool:
        """Return whether this lane's path scope reaches ``relative_path``.

        A path inside an excluded ``--ignore`` scope is not covered even when
        it sits inside a covered ``paths`` scope: ``covers()`` had no concept
        of ``--ignore`` at all, so a lane that both selects ``src/`` and
        excludes two files under it read as reaching them anyway.
        """
        if not self.paths:
            # A pathless invocation takes the configured testpaths, which the
            # caller supplies as this lane's paths. An empty scope reaches
            # nothing rather than everything: treating it as everything is how a
            # gate silently reports full coverage.
            return False
        posix = relative_path.replace("\\", "/")
        if any(_within(posix, excluded) for excluded in self.exclusions):
            return False
        return any(_within(posix, scope) for scope in self.paths)

    def covers_directory(self, relative_directory: str) -> bool:
        """Return whether this lane's path scope SWEEPS ``relative_directory``.

        Deliberately not :meth:`covers` applied to a directory string, and the
        difference is the whole question. A lane naming one FILE inside a
        directory covers that file and sweeps nothing around it, so the next
        module written beside it is collected by nobody -- which is the state
        ``dev/harness/tests`` sat in while every file-level check passed. Only a
        scope that IS the directory or an ancestor of it sweeps the directory.

        A file-level ``--ignore`` inside the directory does not remove the
        sweep: the excluded file is held out, while a new sibling is still
        collected. Only an exclusion of the directory itself or an ancestor
        does, which is what makes the harness package honestly uncovered by the
        corpus lanes that ``--ignore`` it and covered by the one that runs it.
        """
        posix = relative_directory.replace("\\", "/").rstrip("/")
        if not self.paths or not posix:
            return False
        if any(_within(posix, excluded) for excluded in self.exclusions):
            return False
        return any(_within(posix, scope) for scope in self.paths)
