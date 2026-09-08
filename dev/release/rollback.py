"""The rollback procedure for a released version that must be pulled.

Read-only and human-run: this prints the steps, it never performs them. The
git and PyPI actions in step 2 and step 3 are deliberately NOT automated -
reverting a published release is a judgement call with an irreversible half.

The text lived twice in the justfile, as an `echo` body and a `Write-Host`
body. Forty-two lines of duplicated prose is a documentation-drift hazard with
no upside: the two copies had to be edited in lockstep, and nothing checked
that they still said the same thing.
"""

from __future__ import annotations

#: The projects whose artifacts are yanked together, because they are released
#: as a set and a partial yank leaves an inconsistent resolution.
PYPI_PROJECTS = ("cadrumo", "cadrumo-data-manuals", "cadrumo-data-official")


def _yank_urls(version: str) -> list[str]:
    """Return the PyPI yank URL for each co-released project.

    Args:
        version: The released version being pulled.

    Returns:
        One management URL per project, in release-set order.
    """
    return [
        f"     https://pypi.org/manage/project/{project}/release/{version}/  -> Options -> Yank release"
        for project in PYPI_PROJECTS
    ]


def procedure(version: str) -> str:
    """Render the rollback procedure for one version.

    Args:
        version: The released version being pulled.

    Returns:
        The complete procedure, ready to print.
    """
    yanks = "\n".join(_yank_urls(version))
    return f"""Rollback procedure for cadrumo v{version} \
(RELEASING.md#diagnose-and-recover):

1. Confirm the rollback trigger (data loss/corruption, security disclosure,
   widespread regression, or a compatibility mis-computation) - see
   docs/_release_checklist.yaml 'rollback.triggers'.
2. Revert the release commit and tag on main (human-run, never automated):
     git revert --no-commit <release-commit-sha>
     git commit -m 'revert: roll back v{version}'
     git tag -a v{version}-rollback -m 'marks the rollback of v{version}'
     git push origin main
     git push origin refs/tags/v{version}-rollback
3. Yank the bad version from PyPI so pip/uv skip it by default (this does
   NOT delete the artifact; it only stops new installs from resolving it):
{yanks}
4. Publish a corrected patch release following the emergency hotfix cycle
   time for the trigger category (docs/_release_checklist.yaml 'hotfix').
5. Update docs/updates.md per its critical-updates contract and note the
   rollback + corrected version in the GitHub Release notes for v{version}."""


def print_procedure(version: str) -> int:
    """Print the rollback procedure.

    Args:
        version: The released version being pulled.

    Returns:
        Always 0 - this is a document, not a gate.
    """
    print(procedure(version), flush=True)
    return 0
