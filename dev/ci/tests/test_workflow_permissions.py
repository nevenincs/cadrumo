"""The resolver must read the effective grant, never the declared text."""
from __future__ import annotations
from typing import Any
import pytest
from ..workflow_permissions import effective_job_permissions, granted_level, jobs_granting, jobs_with_unsettled_grant
pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

def _document() -> dict[str, Any]:
    """A workflow shaped like the live packaging lanes: read at the top, one job writing."""
    return {'permissions': {'actions': 'read', 'contents': 'read'}, 'jobs': {'watchdog': {'permissions': {'actions': 'write', 'contents': 'read'}, 'steps': []}, 'acquisition': {'permissions': {'actions': 'read', 'contents': 'read'}, 'steps': []}, 'inheritor': {'steps': []}}}

def test_a_job_block_replaces_the_workflow_block_rather_than_merging() -> None:
    """The runtime obeys the job map wholesale; the workflow map does not top it up."""
    document = _document()
    document['jobs']['watchdog']['permissions'] = {'actions': 'write'}
    assert effective_job_permissions(document, 'watchdog') == {'actions': 'write'}
    assert granted_level(document, 'watchdog', 'contents') == 'none'
    assert granted_level(document, 'inheritor', 'contents') == 'read'

def test_an_omitted_block_inherits_while_an_empty_block_denies() -> None:
    """Absence and an explicit deny-all are different declarations, not one falsy value."""
    document = _document()
    document['jobs']['emptied'] = {'permissions': {}, 'steps': []}
    assert effective_job_permissions(document, 'inheritor') == {'actions': 'read', 'contents': 'read'}
    assert effective_job_permissions(document, 'emptied') == {}
    assert granted_level(document, 'inheritor', 'contents') == 'read'
    assert granted_level(document, 'emptied', 'contents') == 'none'

def test_an_undeclared_permission_set_is_unknown_rather_than_none() -> None:
    """Repository settings decide it, so the file cannot answer and must not guess."""
    document = {'jobs': {'bare': {'steps': []}}}
    assert effective_job_permissions(document, 'bare') is None
    assert granted_level(document, 'bare', 'contents') is None
    assert jobs_granting(document, 'contents', 'write') == ()
    assert jobs_with_unsettled_grant(document, 'contents') == ('bare',)

def test_scalar_shorthands_resolve_to_the_level_they_grant_everywhere() -> None:
    """`write-all` is a write grant on every scope, including ones no map names."""
    document = {'permissions': 'read-all', 'jobs': {'wide': {'permissions': 'write-all', 'steps': []}, 'narrow': {'steps': []}}}
    assert granted_level(document, 'wide', 'id-token') == 'write'
    assert granted_level(document, 'narrow', 'id-token') == 'read'
    assert jobs_granting(document, 'id-token', 'write') == ('wide',)

def test_jobs_granting_names_the_write_holder_the_workflow_text_hides() -> None:
    """The two-sided case: the declared map says read, one job effectively writes."""
    document = _document()
    assert document['permissions']['actions'] == 'read'
    assert jobs_granting(document, 'actions', 'write') == ('watchdog',)
    assert jobs_granting(document, 'contents', 'write') == ()
    document['jobs']['sneaky'] = {'permissions': {'actions': 'write', 'contents': 'write'}, 'steps': []}
    assert document['permissions'] == {'actions': 'read', 'contents': 'read'}
    assert jobs_granting(document, 'actions', 'write') == ('watchdog', 'sneaky')
    assert jobs_granting(document, 'contents', 'write') == ('sneaky',)

def test_read_floor_admits_read_and_write_but_not_an_unmentioned_scope() -> None:
    """`level` is a floor, so a read query must not miss a write holder."""
    document = _document()
    assert jobs_granting(document, 'actions', 'read') == ('watchdog', 'acquisition', 'inheritor')
    assert jobs_granting(document, 'id-token', 'read') == ()

def test_an_unknown_job_or_level_refuses_instead_of_answering() -> None:
    """A typo'd job name must not read as a job holding nothing."""
    document = _document()
    with pytest.raises(KeyError):
        effective_job_permissions(document, 'no-such-job')
    with pytest.raises(ValueError, match='unknown permission level'):
        jobs_granting(document, 'actions', 'admin')

def test_an_unsettled_grant_is_distinguished_from_a_denied_one() -> None:
    """The two-sided case a confinement gate cannot see through `jobs_granting`.

    Both a workflow that denies a scope and one that never mentions it answer
    `jobs_granting(...) == ()`. Only the first has actually denied anything; the
    second defers to repository settings this file cannot read.
    """
    denied = {'jobs': {'sealed': {'permissions': {}, 'steps': []}}}
    silent = {'jobs': {'sealed': {'steps': []}}}
    assert jobs_granting(denied, 'contents', 'write') == ()
    assert jobs_granting(silent, 'contents', 'write') == ()
    assert jobs_with_unsettled_grant(denied, 'contents') == ()
    assert jobs_with_unsettled_grant(silent, 'contents') == ('sealed',)

def test_a_declared_map_settles_every_scope_including_ones_it_omits() -> None:
    """A declared block is an answer for scopes it never names: it grants them nothing."""
    document = _document()
    assert granted_level(document, 'watchdog', 'id-token') == 'none'
    assert jobs_with_unsettled_grant(document, 'id-token') == ()
    assert jobs_with_unsettled_grant(document, 'contents') == ()
    document.pop('permissions')
    for job in document['jobs'].values():
        _dp_pop('dev/ci/tests/test_workflow_permissions.py:130:pop', job, 'permissions', None)
    assert jobs_with_unsettled_grant(document, 'contents') == ('watchdog', 'acquisition', 'inheritor')