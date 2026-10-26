"""Import root boundaries."""

from __future__ import annotations

from .import_check_models import Authority


def root_boundary_pairs(authority: Authority) -> frozenset[tuple[str, str]]:
    """Return the root-to-root separations declared by forbidden contracts.

    A contract whose source and forbidden members are both whole first-party
    roots separates independently shipped trees.  That separation holds for
    every module in the source root, test modules included, so it is never
    ratchetable debt.
    """
    roots = authority.root_names
    return frozenset(
        (source, forbidden)
        for contract in authority.forbidden_contracts
        for source in contract.source_modules
        if source in roots
        for forbidden in contract.forbidden_modules
        if forbidden in roots
    )


def crosses_root_boundary(source_module: str, target_module: str, pairs: frozenset[tuple[str, str]]) -> bool:
    """Check the root pair against the declared forbidden contracts."""
    return (source_module.partition(".")[0], target_module.partition(".")[0]) in pairs


def source_module_exists(authority: Authority, module: str) -> bool:
    """Return whether ``module`` is a module or package file below its declared root."""
    for root in sorted(authority.roots, key=lambda item: len(item.name), reverse=True):
        if module != root.name and not module.startswith(f"{root.name}."):
            continue
        relative = module.split(".")[len(root.name.split(".")) :]
        base = root.path.joinpath(*relative)
        if (base / "__init__.py").is_file():
            return True
        return bool(relative) and base.with_name(f"{relative[-1]}.py").is_file()
    return False
