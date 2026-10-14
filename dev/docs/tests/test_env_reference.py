"""Drift gates binding the environment-overrides surface to the settings model.

Four surfaces describe the product environment overrides:

- :class:`cadrumo.core.config.Settings` — the live model, the source of truth
  for the command line;
- ``native/application-environment.toml`` — the package's declaration of which
  names each packaged program passes, the source of truth for the installed
  package section of the generated page;
- ``docs/reference/environment-overrides.md`` — the generated reference page
  (:mod:`dev.docs.env_reference`);
- ``env/.env.example`` — the hand-annotated template operators copy.

These gates fail loudly when any of the three drifts: a stale generated page,
a template key the model no longer reads (a dead knob an operator could set
in vain), or a model field the template omits (an override no operator can
discover). User-facing guides carry no environment overrides at all — the
companion conformance sweep in the docs gates keeps the one sanctioned home
under ``docs/reference``.
"""

from __future__ import annotations

import re
from dataclasses import replace

import pytest

from cadrumo.core.storage_environment import TOOL_STORAGE_LOCATIONS
from dev._paths import REPO_ROOT
from dev.cache_root import DEV_CACHE_ROOT_ENV
from dev.deploy.docs_delivery_contracts import DELIVERY_CREDENTIAL_ENV
from dev.packaging.native.application_environment import ApplicationEnvironment, load

from ..env_reference import render_environment_reference, render_installed_package, target_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT = REPO_ROOT
_ENV_EXAMPLE = _REPO_ROOT / "env" / ".env.example"
_KEY_RE = re.compile(r"^#?\s*([A-Z][A-Z0-9_]+)=", re.MULTILINE)

#: Template keys for development tooling, which reads them itself rather than
#: through the product settings model.
_DEVELOPMENT_TOOLING_KEYS = frozenset(
    {
        DEV_CACHE_ROOT_ENV,
        *DELIVERY_CREDENTIAL_ENV,
        *(variable for variable, _default in TOOL_STORAGE_LOCATIONS.values()),
        "CADRUMO_NATIVE_BUILD_ROOT",
        "CADRUMO_DOCS_BUILD_ROOT",
        "CADRUMO_HOMEBREW_ROOT",
        "CADRUMO_SCOOP_ROOT",
        "CADRUMO_HOMEBREW_PREFIX",
        "CADRUMO_SCOOP_INSTALL_ROOT",
        "CADRUMO_HOMEBREW_CACHE_DIR",
        "CADRUMO_HOMEBREW_LOGS_DIR",
        "CADRUMO_HOMEBREW_TEMP_DIR",
        "CADRUMO_SCOOP_CACHE_DIR",
        "CADRUMO_DEV_ARTIFACTS_DIR",
        "CADRUMO_ACTIONLINT_DIR",
        "CADRUMO_REGISTRY_DISK_CACHE_DIR",
        "CADRUMO_RECORD_DESIGN_CACHE_DIR",
        "CADRUMO_CORPUS_TEXT_CACHE_DIR",
        "CADRUMO_REGISTRY_VERDICT_CACHE_DIR",
        "CADRUMO_RUNTIME_WHEEL_CACHE_DIR",
    }
)

#: Runner and SDK inputs read outside product Settings. Inherited run IDs and
#: artifact paths are intentionally absent: the harness creates those itself.
_TEST_RUNNER_KEYS = frozenset(
    {
        "CADRUMO_PYTEST_WORKERS",
        "CADRUMO_SCRATCH_BASE",
        "CADRUMO_TEST_LOG_ROOT",
        "CADRUMO_CI_REPORTS_DIR",
        "VAULTSPEC_CI_REPORTS",
        "VAULTSPEC_CI_REPORT_NAME",
        "AEAT_CLAVE_MOVIL_FULL_LIVE_AUTH",
    },
)


def _settings_env_names() -> frozenset[str]:
    """Return the names an environment source can actually populate.

    Keyed on the model's own environment inventory rather than every field,
    so a field whose environment source has been severed is neither demanded
    in the template nor reported as a dead knob.
    """
    from cadrumo.core.config import Settings

    return frozenset(Settings.env_var_names())


def test_generated_page_is_fresh() -> None:
    """The committed page equals fresh generator output byte for byte."""
    path = target_path(_REPO_ROOT)
    assert path.is_file(), f"missing generated page: {path}; run python -m dev.docs.env_reference"
    assert path.read_bytes() == render_environment_reference().encode("utf-8"), (
        f"{path} is stale; regenerate with python -m dev.docs.env_reference"
    )


def test_env_example_keys_all_resolve_to_settings_fields() -> None:
    """Every template key is read by Settings or the declared tooling/SDKs."""
    keys = frozenset(_KEY_RE.findall(_ENV_EXAMPLE.read_text(encoding="utf-8")))
    dead = sorted(keys - _settings_env_names() - _DEVELOPMENT_TOOLING_KEYS - _TEST_RUNNER_KEYS)
    assert not dead, f"env/.env.example keys with no Settings field (dead knobs): {dead}"


def test_settings_fields_all_present_in_env_example() -> None:
    """Every Settings env name appears in env/.env.example."""
    keys = frozenset(_KEY_RE.findall(_ENV_EXAMPLE.read_text(encoding="utf-8")))
    undocumented = sorted(_settings_env_names() - keys)
    assert not undocumented, f"Settings fields missing from env/.env.example: {undocumented}"


def test_every_settings_field_carries_a_description() -> None:
    """A field without a description renders an empty reference row."""
    from cadrumo.core.config import Settings

    assert Settings.model_fields, "Settings declares no fields; this gate would pass over an empty model"
    missing = sorted(
        name for name, field in Settings.model_fields.items() if field.description is None or not field.description
    )
    assert not missing, f"Settings fields without descriptions: {missing}"


def _declaration() -> ApplicationEnvironment:
    return load(_REPO_ROOT)


def _profile_text(page: str, name: str) -> str:
    """Return the page's text for one launch profile, from its heading to the next heading."""
    heading = f"#### `{name}`\n"
    assert heading in page, f"the page has no section for profile {name}"
    start = page.index(heading) + len(heading)
    end = page.find("\n#", start)
    return page[start : end if end != -1 else len(page)]


def test_every_name_a_profile_admits_is_on_its_section_of_the_page() -> None:
    """The page states, per profile, every name the declaration passes, accepts or sets."""
    declaration = _declaration()
    page = render_environment_reference()
    assert declaration.profiles, "the declaration has no profiles; this gate would pass over an empty page"
    for name, profile in declaration.profiles.items():
        section = _profile_text(page, name)
        admitted = {
            *profile["pass"],
            *(slot.name for slot in profile["slots"]),
            *(fixed.name for fixed in profile["fixed"]),
        }
        for group, members in declaration.groups.items():
            if members and set(members) <= set(profile["operator"]):
                assert f"`{group}`" in section, f"profile {name} passes group {group}; its section omits it"
                admitted -= set(members)
        missing = sorted(variable for variable in admitted if f"`{variable}`" not in section)
        assert not missing, f"profile {name} admits {missing}; its section on the page omits them"
        assert f"`{profile['image']}`" in section


def test_a_profile_that_admits_a_prefix_states_it_and_the_names_it_never_admits() -> None:
    """The page names the prefix a profile admits whole and each name it keeps out."""
    declaration = _declaration()
    page = render_environment_reference()
    prefixed = {name: profile for name, profile in declaration.profiles.items() if profile["prefix"]}
    assert prefixed, "no profile admits a prefix; this gate would pass over an empty page"
    for name, profile in prefixed.items():
        section = _profile_text(page, name)
        assert f"every name that starts with `{profile['prefix']}` except" in section, name
        missing = [refused for refused in profile["prefix_refused"] if f"`{refused}`" not in section]
        assert not missing, f"profile {name} never admits {missing}; its section omits them"
    for name, profile in declaration.profiles.items():
        if not profile["prefix"]:
            assert "every name that starts with" not in _profile_text(page, name), name


def test_every_name_group_and_refusal_is_listed_once_on_the_page() -> None:
    """Groups, operating-system names, the refusal status and every refusal code are stated."""
    declaration = _declaration()
    page = render_environment_reference()
    for group, members in declaration.groups.items():
        row = next(line for line in page.splitlines() if line.startswith(f"| `{group}` | `{members[0]}`"))
        assert all(f"`{member}`" in row for member in members), f"group {group} is not listed whole"
    for family, base in declaration.base.items():
        for names in base.values():
            assert all(f"`{name}`" in page for name in names), f"operating-system names of {family} are missing"
    assert f"status {declaration.native_host['launch_profile_refused']}" in page
    assert all(f"`{code}`" in page for code in declaration.native_host["refusals"])


def test_the_installed_package_section_follows_the_declaration() -> None:
    """A name added to a profile of the declaration reaches the page; nothing is kept as a copy."""
    declaration = _declaration()
    planted_name = "CADRUMO_PLANTED_PASS_THROUGH"
    profiles = {
        name: {**profile, "pass": (*profile["pass"], planted_name)} if name == "aeat" else profile
        for name, profile in declaration.profiles.items()
    }
    planted = replace(
        declaration,
        names={**declaration.names, planted_name: {"kind": "text", "role": "pass"}},
        profiles=profiles,
    )
    section = render_installed_package(planted, ())
    assert f"`{planted_name}`" in _profile_text(section, "aeat")
    assert f"`{planted_name}`" not in _profile_text(section, "python")
    assert f"| `{planted_name}` | text |" in section
    assert planted_name not in render_installed_package(declaration, ())


def test_every_declared_invocation_is_spelled_on_its_profiles_section_with_its_options_marked_optional() -> None:
    """A profile's section lists each invocation that selects it; an option reads ``[--flag <slot:kind>]``."""
    declaration = _declaration()
    page = render_environment_reference()
    for invocation in declaration.invocations:
        spelled = " ".join(
            argument.literal
            if argument.literal is not None
            else f"<{argument.slot}:{argument.kind}>"
            if argument.option is None
            else f"[{argument.option} <{argument.slot}:{argument.kind}>]"
            for argument in invocation.arguments
        )
        assert f"`{spelled}`" in _profile_text(page, invocation.profile), (invocation.profile, spelled)
    gateway = _profile_text(page, "agent-gateway")
    assert "`-m cadrumo_agent.cli.main version --json`" in gateway
    assert (
        "`-m cadrumo_agent.cli.main migrate [--expect-from <expected_from:revision>] "
        "[--expect-head <expected_head:revision>]`" in gateway
    )
    assert "`[--flag <name:kind>]` stands for an option" in page


def test_names_the_settings_table_lists_are_not_repeated_among_package_only_names() -> None:
    """The package-only table holds exactly the declared names the settings model does not read."""
    declaration = _declaration()
    page = render_environment_reference()
    only_package = page[page.index("### Names only the package declares") : page.index("### Refused launches")]
    for name in declaration.names:
        listed = f"| `{name}` |" in only_package
        assert listed == (name not in _settings_env_names()), f"{name} is misplaced in the package-only table"


def test_a_refusal_code_the_page_does_not_describe_stops_generation() -> None:
    """A new refusal code in the declaration fails generation until the page describes it."""
    declaration = _declaration()
    undescribed_code = replace(
        declaration, native_host={**declaration.native_host, "refusals": [*declaration.native_host["refusals"], "x"]}
    )
    with pytest.raises(RuntimeError, match="does not describe"):
        render_installed_package(undescribed_code, ())
