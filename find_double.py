"""Find all double-replacement occurrences in source files."""
import pathlib
import re

# Match patterns like aeat.adapters.X...aeat.adapters or aeat.application.X...aeat.application
double_pattern = re.compile(
    r'aeat\.(adapters|application|entrypoints|domain|core)\.'
    r'[^"\'\s]+'
    r'aeat\.(adapters|application|entrypoints|domain|core)\.'
)

root = pathlib.Path('Y:/code/aeat-worktrees/chore-476-restructure-execution/src/aeat')
hits = []
hit_files = set()
for py in sorted(root.rglob('*.py')):
    try:
        content = py.read_text(encoding='utf-8')
    except Exception:
        continue
    for i, line in enumerate(content.split('\n'), 1):
        stripped = line.strip()
        if stripped.startswith('from ') or stripped.startswith('import '):
            continue
        if double_pattern.search(line):
            rel = str(py.relative_to('Y:/code/aeat-worktrees/chore-476-restructure-execution'))
            hits.append(f'{rel}:{i}: {line.strip()[:140]}')
            hit_files.add(rel)

print(f'Double-replacement hits: {len(hits)} in {len(hit_files)} files')
for h in hits[:50]:
    print(h)
