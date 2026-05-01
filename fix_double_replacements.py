"""Fix double-replacement errors in docstrings/comments.

Our update script accidentally double-replaced paths like:
  aeat.adapters.outbound.aeat.auth -> aeat.adapters.outbound.aeat.adapters.outbound.aeat.auth

This script reverts those double-replacements.
"""
import pathlib
import re

# Canonical prefixes and their common double-replacement patterns
# When we had aeat.adapters.outbound.aeat.auth and replaced aeat.auth again
# we got aeat.adapters.outbound.aeat.adapters.outbound.aeat.auth

fixes = [
    # auth double-replacement
    (
        'aeat.adapters.outbound.aeat.adapters.outbound.aeat.auth',
        'aeat.adapters.outbound.aeat.auth',
    ),
    # browser double-replacement
    (
        'aeat.adapters.outbound.aeat.adapters.outbound.aeat.browser',
        'aeat.adapters.outbound.aeat.browser',
    ),
    # sede double-replacement
    (
        'aeat.adapters.outbound.aeat.adapters.outbound.aeat.sede',
        'aeat.adapters.outbound.aeat.sede',
    ),
    # export/submission double-replacement
    (
        'aeat.adapters.outbound.aeat.adapters.outbound.aeat.export',
        'aeat.adapters.outbound.aeat.export',
    ),
]

root = pathlib.Path('Y:/code/aeat-worktrees/chore-476-restructure-execution/src/aeat')
updated = []

for py in sorted(root.rglob('*.py')):
    try:
        content = py.read_text(encoding='utf-8')
    except Exception:
        continue

    new_content = content
    for wrong, correct in fixes:
        new_content = new_content.replace(wrong, correct)

    if new_content != content:
        py.write_text(new_content, encoding='utf-8')
        rel = str(py.relative_to('Y:/code/aeat-worktrees/chore-476-restructure-execution'))
        updated.append(rel)

print(f'Fixed double-replacements in {len(updated)} files:')
for f in updated:
    print(f'  {f}')
