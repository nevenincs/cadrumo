"""A synthetic repository and docs tree for the per-sequence verdict tests.

The tree carries every kind of input a verdict key reads: product source under
each shipped package, the gate engine with a ``dev`` helper it imports, registry
tooling, the lock file, shared seeds and fixtures, and two pages holding three
sequences with their private contracts and committed goldens.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from ..checks import DiscoveredSequence, discover_sequences
from ..dependency_observation import Observation
from ..verdict_cache import OBSERVATION_SENTINEL, SequenceVerdicts

PROFILE_PREREQUISITE = "Create a profile first with `aeat config profile create`.\n"
CONTRACT_BODY = "@result aeat --format json config profile list\n@expect exit_code == 0\n"

ALPHA = "how-to/alpha"
BETA = "how-to/beta"
PAGE_ONE = (
    f"# Alpha\n\nProse. {PROFILE_PREREQUISITE}\n"
    "```{cli-sequence} a-one\n:verify: One.\n```\n\n"
    "```{cli-sequence} a-two\n:verify: Two.\n```\n"
)
PAGE_TWO = f"# Beta\n\nProse. {PROFILE_PREREQUISITE}\n```{{cli-sequence}} b-one\n:verify: One.\n```\n"

#: Every shared input of the synthetic tree, by repository-relative path.
SHARED_FILES: dict[str, str] = {
    "src/cadrumo/__init__.py": "# product package\n",
    "src/cadrumo/cli.py": "print('cli')\n",
    "src/cadrumo_client/transport.py": "# client\n",
    "src/cadrumo_runtime/host.py": "# runtime\n",
    "dev/__init__.py": "",
    "dev/docs/__init__.py": "",
    "dev/docs/build.py": "# build\n",
    "dev/docs/sequences/__init__.py": "",
    "dev/docs/sequences/runner.py": "# engine\n",
    "dev/docs/sequences/checks.py": "from __future__ import annotations\nfrom dev.helper import assist\n",
    "dev/helper.py": "def assist() -> None: ...\n",
    "dev/registry/__init__.py": "",
    "dev/registry/compiler.py": "# authority tooling\n",
    "dev/registry/pipeline/__init__.py": "",
    "dev/registry/pipeline/authority_publication.py": "from __future__ import annotations\n",
    "uv.lock": "lock\n",
    "docs/_sequences/seeds/shared.json": '{"seed": 1}\n',
    "docs/_sequences/fixtures/shared.txt": "fixture\n",
}


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@dataclass(frozen=True)
class SyntheticTree:
    repo: Path
    docs: Path

    @property
    def sequences(self) -> Path:
        return self.docs / "_sequences"

    def contract(self, page: str, sequence_id: str) -> Path:
        return self.sequences / "contracts" / page / f"{sequence_id}.seq"

    def golden(self, page: str, sequence_id: str) -> Path:
        return self.sequences / page / f"{sequence_id}.json"

    def verdicts(self, identity: str = "generation-1") -> SequenceVerdicts:
        return SequenceVerdicts(
            docs_root=self.docs,
            goldens_root=self.sequences,
            authority_identity=identity,
            repo_root=self.repo,
        )

    def discovered(self) -> dict[tuple[str, str], DiscoveredSequence]:
        found, problems = discover_sequences(docs_root=self.docs)
        assert problems == (), problems
        return {(item.page, item.sequence_id): item for item in found}

    def observe(self, *relatives: str, sentinel: bool = True) -> Observation:
        """Return a complete observation that read ``relatives`` (and so their directories), as a process would.

        Every sequence imports the product package, so the observation also read
        :data:`OBSERVATION_SENTINEL` unless ``sentinel`` is false.
        """
        observation = Observation(self.repo, started_ns=time.time_ns())
        for relative in (*((OBSERVATION_SENTINEL,) if sentinel else ()), *relatives):
            observation.note_file(str(self.repo / relative))
        return observation

    def keys(self, identity: str = "generation-1") -> dict[tuple[str, str], str]:
        """Key every sequence from a freshly constructed authority, as a new process would."""
        verdicts = self.verdicts(identity)
        return {name: verdicts.key(item) for name, item in self.discovered().items()}


def build_tree(root: Path) -> SyntheticTree:
    tree = SyntheticTree(repo=root, docs=root / "docs")
    for relative, text in SHARED_FILES.items():
        write(root / relative, text)
    write(tree.docs / f"{ALPHA}.md", PAGE_ONE)
    write(tree.docs / f"{BETA}.md", PAGE_TWO)
    for page, sequence_id in ((ALPHA, "a-one"), (ALPHA, "a-two"), (BETA, "b-one")):
        write(tree.contract(page, sequence_id), CONTRACT_BODY)
        write(tree.golden(page, sequence_id), f'{{"frames": [], "id": "{sequence_id}"}}\n')
    return tree
