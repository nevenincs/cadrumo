"""Deployment stays unreachable from every development check surface.

The three publishing verbs were filed under ``[group('docs')]``, which asserted
that publishing to production and building documentation locally were the same
category of operation. They are not: building is verification, publishing is a
release act. The recipes now sit in their own ``deploy`` group.

Regrouping alone would be a label, and a label is not an isolation. What was
measured at the time of the move is that nothing in the repository could reach a
deploy verb at all -- no recipe named one as a prerequisite, no recipe body
invoked one, and exactly one workflow step in eighteen workflow files ran a
publisher, in a delivery-only workflow behind a protected environment. The
isolation was already true.

It was true by accident. Nothing observed it, so nothing would notice it ending:
a ``check-all: docs-deploy`` prerequisite, or a verification job growing a
publish step, would both have landed green. That is the same shape as the
boundary audit's drift-detectability finding -- a property held by "nobody has
done it yet" rather than by a guarantee -- and this module converts it into the
guarantee.

Scope is reachability and grouping only. Who may publish, and from where, is a
different question and belongs to ``test_publish_authority``; this module never
asserts anything about publish behaviour.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT
from ...ci.lane_reachability import resolve_just_executable
from ...ci.workflow_run_text import executed_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = REPO_ROOT
_JUSTFILE = _REPO_ROOT / "justfile"
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"

#: Both suffixes, because GitHub Actions reads either from the workflows
#: directory. A sweep pinned to ``*.yml`` silently skips a lane filed as
#: ``.yaml``, and both claims below check their result for the ABSENCE of
#: other publishers -- so an unswept lane reads exactly like a clean one.
_WORKFLOW_SUFFIXES = (".yml", ".yaml")

#: Floor for the workflow corpus. Live it holds 16 documents. The pinned
#: equalities below fail loud on a sweep that found nothing, but not on
#: one narrowed to the few files that happen to satisfy them.
_MINIMUM_WORKFLOWS = 8


def _workflow_documents() -> tuple[Path, ...]:
    """Return every workflow document GitHub Actions would read."""
    documents = tuple(sorted(path for path in scan_directory(_WORKFLOWS) if path.suffix in _WORKFLOW_SUFFIXES))
    assert len(documents) >= _MINIMUM_WORKFLOWS, (
        f"the sweep found only {len(documents)} workflow document(s) under {_WORKFLOWS}; "
        "every claim keyed on it would then range over almost no lane"
    )
    return documents


#: The publishing verbs. Membership is asserted rather than trusted, so an
#: undeclared publisher cannot join the command surface.
_DEPLOY_RECIPES = frozenset({"docs-deploy", "docs-stack-deploy"})

#: The prefixes that name a development check surface. Deliberately broad: the
#: question is "can verification reach publication", so over-including a recipe
#: costs nothing while missing one would hide the very edge being gated.
_CHECK_PREFIXES = ("check", "test", "audit", "docs-check", "packaging", "lint", "verify", "ci")

#: The word ``just`` used as a COMMAND, not the four letters wherever they
#: fall. The lookbehinds admit every prefix a justfile body or a shell line
#: puts in front of it -- ``@just`` (quiet), ``-just`` (ignore-error),
#: ``uv run just``, a separator -- while refusing ``adjust`` and ``ad-just``.
#:
#: No recipe name is captured here. The names are read from the tokens that
#: follow, because just's argument grammar accepts several recipes in one
#: invocation (``just docs-check docs-deploy``) and flags that carry a value
#: (``just --set workers 4 docs-deploy``). The pattern this replaces captured
#: ONE trailing name and got both forms wrong in the same direction: it missed
#: ``docs-deploy`` in the first, and in the second it landed on the flag VALUE
#: ``workers`` -- not a recipe, so the intersection below discarded it and the
#: edge vanished entirely. A vanished edge here is a silent pass of the very
#: severance this module exists to hold.
_JUST_COMMAND = re.compile(r"(?<!\w)(?<!\w-)just(?=\s)", re.MULTILINE)

#: One argument token of such an invocation. Quotes and separators are not
#: modelled: the caller's real recipe set decides which token is a name.
_INVOCATION_TOKEN = re.compile(r"[\w.\-/=]+")

#: The two ways a workflow step can reach a publisher other than by naming the
#: verb. The verb itself is read through :func:`_recipes_invoked_in`, for the
#: reason above: a pattern demanding the recipe immediately after ``just``
#: cannot see ``just --no-deps docs-deploy``, and an unseen publisher does not
#: fail this gate -- it drops out of the census the gate compares.
_DEPLOY_IN_WORKFLOW = (
    re.compile(r"dev\.deploy\.docs_static_site"),
    re.compile(r"--confirm\s+(?:publish|provision)-cadrumo-\w+"),
)


def _recipes_invoked_in(text: str, names: frozenset[str] | set[str]) -> set[str]:
    """Return every recipe named by a ``just`` invocation in ``text``.

    Every non-flag token of the invocation line is offered and the caller's
    real recipe set decides, rather than a pattern deciding which token is
    the name. Over-including costs nothing here -- the question is whether
    verification CAN reach publication, and a spurious edge fails loudly --
    while missing one hides the edge being gated.
    """
    invoked: set[str] = set()
    for match in _JUST_COMMAND.finditer(text):
        tail = text[match.end() :].split("\n", 1)[0]
        tokens = _INVOCATION_TOKEN.findall(tail)
        invoked |= {token for token in tokens if not token.startswith("-")} & set(names)
    return invoked


#: The one workflow permitted to publish, and the environment that gates it.
_DELIVERY_WORKFLOW = "docs-publish.yml"
_DELIVERY_ENVIRONMENT = "docs"


def _dump(justfile: Path) -> dict[str, object]:
    """Return just's own parse of a justfile.

    The parse comes from ``just`` rather than from a regex over the text: the
    recipe graph is exactly what ``just`` would execute, so asking any other
    parser risks gating a graph the tool does not agree with.
    """
    just = resolve_just_executable()
    result = subprocess.run(  # noqa: S603 - execute the resolved real just binary against repository recipes.
        [
            just,
            "--justfile",
            str(justfile),
            "--working-directory",
            str(_REPO_ROOT),
            "--unstable",
            "--dump",
            "--dump-format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["recipes"]


def _recipe_graph(justfile: Path) -> dict[str, set[str]]:
    """Return recipe -> the recipes it can reach in one hop.

    Both edge kinds count, because both actually run the target: a declared
    prerequisite, and a body line invoking ``just <recipe>``. Gating only the
    first would let a recipe reach a publisher through its body and still pass.
    """
    recipes = _dump(justfile)
    names = set(recipes)
    graph: dict[str, set[str]] = {}
    for name, body in recipes.items():
        edges = {dep["recipe"] for dep in body.get("dependencies", [])}
        fragments: list[str] = []
        for line in body.get("body", []):
            fragments.extend(part if isinstance(part, str) else json.dumps(part) for part in line)
        edges |= _recipes_invoked_in("\n".join(fragments), names)
        graph[name] = edges
    return graph


def _reachable(graph: dict[str, set[str]], start: str) -> set[str]:
    """Return every recipe transitively reachable from ``start``."""
    seen: set[str] = set()
    stack = [start]
    while stack:
        for nxt in graph.get(stack.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _deploy_reaching_recipes(graph: dict[str, set[str]]) -> dict[str, set[str]]:
    """Return every recipe that can reach a deploy verb, and which ones."""
    return {name: hit for name in sorted(graph) if (hit := _reachable(graph, name) & _DEPLOY_RECIPES)}


def test_no_development_check_lane_can_reach_a_deploy_verb() -> None:
    """The severance this module exists to hold.

    Walked over the whole check surface rather than sampled, because the edge
    that matters is the one nobody thought to look for.
    """
    graph = _recipe_graph(_JUSTFILE)
    lanes = sorted(name for name in graph if name.startswith(_CHECK_PREFIXES))
    assert lanes, "no check lanes found; the traversal is looking at the wrong file"

    violations = {lane: sorted(_reachable(graph, lane) & _DEPLOY_RECIPES) for lane in lanes}
    reaching = {lane: hit for lane, hit in violations.items() if hit}
    assert reaching == {}, f"check lanes reaching a deploy verb: {reaching}"


@pytest.mark.parametrize(
    ("invocation", "why"),
    [
        ("just docs-check docs-deploy", "two recipes in one invocation"),
        ("just --set workers 4 docs-deploy", "a flag carrying a value"),
        ("just --no-deps docs-deploy", "a bare flag"),
        ("@just docs-deploy", "just's quiet prefix"),
        ("-just docs-deploy", "just's ignore-error prefix"),
    ],
    ids=["multi-recipe", "valued-flag", "bare-flag", "quiet", "ignore-error"],
)
def test_a_body_reaching_a_publisher_is_seen_however_it_is_written(tmp_path: Path, invocation: str, why: str) -> None:
    """Detector teeth for the edge reader, against an isolated justfile.

    Each form runs the publisher. The pattern this replaced saw only the
    first token after ``just``: it missed ``docs-deploy`` behind a second
    recipe name and, behind a valued flag, landed on ``workers`` -- a name
    no recipe carries, so the intersection dropped it and the edge did not
    exist. A dropped edge does not fail the severance claim above; it
    removes the lane from the walk, which is the silent pass this module
    is here to prevent.
    """
    justfile = tmp_path / "justfile"
    justfile.write_text(
        f'docs-deploy:\n    @echo "publish"\n\ndocs-check:\n    @echo "check"\n\ncheck-reaching:\n    {invocation}\n',
        encoding="utf-8",
    )

    graph = _recipe_graph(justfile)

    assert "docs-deploy" in _reachable(graph, "check-reaching"), f"{why} hid the publisher edge: {graph}"


def test_a_body_that_only_mentions_a_publisher_is_not_an_edge(tmp_path: Path) -> None:
    """Negative control: the reader must not manufacture an edge from prose.

    ``adjust`` contains the four letters and the line names a real recipe.
    Reading an edge here would report a severance violation that does not
    exist, which is the other half of trusting a harvested identifier.
    """
    justfile = tmp_path / "justfile"
    justfile.write_text(
        'docs-deploy:\n    @echo "publish"\n\ncheck-quiet:\n    @echo "adjust docs-deploy by hand"\n',
        encoding="utf-8",
    )

    graph = _recipe_graph(justfile)

    assert graph["check-quiet"] == set(), graph


def test_nothing_at_all_reaches_a_deploy_verb() -> None:
    """Stronger than the check-lane sweep, and cheaper to keep honest.

    The check-prefix set is a judgement about which names are verification
    surfaces, and a judgement can be wrong. This assertion needs no such
    judgement: a deploy verb is reached by nothing whatsoever, so a recipe that
    grows an edge fails here even if its name never suggested it was a check.
    """
    graph = _recipe_graph(_JUSTFILE)
    assert _deploy_reaching_recipes(graph) == {}


def test_the_deploy_verbs_depend_on_nothing_and_nothing_depends_on_them() -> None:
    """Self-containment, asserted in both directions.

    Inbound emptiness is the isolation. Outbound emptiness is what keeps the
    isolation cheap to verify: a publisher that first ran a build recipe would
    make every future reader trace that recipe's own edges before trusting this
    module.
    """
    graph = _recipe_graph(_JUSTFILE)
    for recipe in sorted(_DEPLOY_RECIPES):
        assert recipe in graph, f"{recipe} is not a recipe; the deploy set has drifted"
        assert graph[recipe] == set(), f"{recipe} reaches {sorted(graph[recipe])}"
    inbound = {name: sorted(_DEPLOY_RECIPES & edges) for name, edges in graph.items() if _DEPLOY_RECIPES & edges}
    assert inbound == {}, f"recipes naming a deploy verb as a prerequisite: {inbound}"


def test_the_traversal_fires_on_a_planted_edge(tmp_path: Path) -> None:
    """Anti-tautology proof: a clean result must be a finding, not a blind spot.

    A traversal that silently parsed nothing would report the same empty result
    as a genuinely isolated graph, and every assertion above would pass over a
    repository that had lost the property entirely. So both edge kinds are
    planted into a scratch copy and each must be caught.
    """
    source = _JUSTFILE.read_bytes()
    planted = tmp_path / "justfile"

    prerequisite = source.replace(b"\ncheck-all:", b"\ncheck-all: docs-deploy", 1)
    assert prerequisite != source, "could not plant a prerequisite edge; check-all was not found"
    planted.write_bytes(prerequisite)
    assert "docs-deploy" in _reachable(_recipe_graph(planted), "check-all"), (
        "a planted prerequisite edge was not detected; the traversal is blind"
    )

    invocation = source.replace(b"\naudit-all:", b"\naudit-all:\n    just docs-stack-deploy", 1)
    assert invocation != source, "could not plant a body invocation; audit-all was not found"
    planted.write_bytes(invocation)
    assert "docs-stack-deploy" in _reachable(_recipe_graph(planted), "audit-all"), (
        "a planted body invocation was not detected; the traversal is blind"
    )


def test_the_deploy_group_holds_exactly_the_publishing_verbs() -> None:
    """Membership is pinned in both directions.

    A new publishing verb filed under another group would sit outside every
    assertion in this module, and a build verb filed into ``deploy`` would make
    the group stop meaning "this writes to production".
    """
    recipes = _dump(_JUSTFILE)
    # Read the `group` key exactly. Matching "deploy" anywhere in the attribute
    # blob instead catches any recipe whose `doc` text merely mentions the word
    # -- which it did on the first run, pulling in a testing-group lane whose
    # description names the dev/deploy subsystem it covers.
    grouped = {
        name
        for name, body in recipes.items()
        if any(
            isinstance(attribute, dict) and attribute.get("group") == "deploy"
            for attribute in body.get("attributes", [])
        )
    }
    assert grouped == set(_DEPLOY_RECIPES), (
        f"deploy group membership drifted: {sorted(grouped)} != {sorted(_DEPLOY_RECIPES)}"
    )


def test_only_the_delivery_workflow_runs_a_publisher() -> None:
    """A deploy step inside a verification job is the same violation one level up.

    Swept across every workflow rather than the two that were known to matter,
    so a newly added verification lane cannot acquire a publish step unobserved.
    """
    workflows = _workflow_documents()

    publishing: dict[str, list[str]] = {}
    for path in workflows:
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_name, job in (document.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                command = str(step.get("run", "") or "")
                if _recipes_invoked_in(executed_text(command), _DEPLOY_RECIPES) or any(
                    pattern.search(command) for pattern in _DEPLOY_IN_WORKFLOW
                ):
                    publishing.setdefault(path.name, []).append(job_name)

    assert set(publishing) == {_DELIVERY_WORKFLOW}, (
        f"workflows running a publisher: {publishing}; only {_DELIVERY_WORKFLOW} may"
    )

    document = yaml.safe_load((_WORKFLOWS / _DELIVERY_WORKFLOW).read_text(encoding="utf-8"))
    for job_name in publishing[_DELIVERY_WORKFLOW]:
        job = document["jobs"][job_name]
        assert job.get("environment") == _DELIVERY_ENVIRONMENT, (
            f"{job_name} publishes without the protected {_DELIVERY_ENVIRONMENT} environment"
        )


def test_no_publisher_here_reaches_the_site_root() -> None:
    """Only the documentation publisher may be reachable from this repository."""
    text = "\n".join(path.read_text(encoding="utf-8") for path in _workflow_documents())
    invoked = {
        module
        for module in ("docs_static_site", "frontend_static_site")
        if re.search(rf"^\s*(?!#).*dev\.deploy\.{module}", text, re.MULTILINE)
    }
    assert invoked == {"docs_static_site"}, (
        f"workflow-invoked publishers: {sorted(invoked)}; only the documentation publisher lives here"
    )
    assert not (_REPO_ROOT / "dev" / "deploy" / "frontend_static_site.py").exists(), (
        "an external-site publisher entered the product repository"
    )
