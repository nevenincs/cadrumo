"""Apply all dead-export pruning changes to the aeat codebase."""
import pathlib
import re

BASE = "Y:/code/aeat-worktrees/chore-476-restructure-execution/src/aeat"


def edit(relpath, replacements):
    p = pathlib.Path(BASE + "/" + relpath)
    content = p.read_text(encoding="utf-8")
    original = content
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new, 1)
    if content != original:
        p.write_text(content, encoding="utf-8")
        return True
    return False


def delete_func(relpath, func_name, kind="def"):
    p = pathlib.Path(BASE + "/" + relpath)
    content = p.read_text(encoding="utf-8")
    pattern = r"\n\n" + kind + r" " + re.escape(func_name) + r"\b"
    m = re.search(pattern, content)
    if not m:
        return False
    func_start = m.start()
    remaining = content[func_start + 2 :]
    next_m = re.search(r"\n\n(def |class |__all__|[A-Z_][A-Z_0-9]* ?[=:])", remaining)
    func_end = func_start + 2 + (next_m.start() if next_m else len(remaining))
    new_content = content[:func_start] + content[func_end:]
    p.write_text(new_content, encoding="utf-8")
    return True


# Adapters
edit(
    "adapters/inbound/borrador/_tarifa.py",
    [('    "TarifaFinding",\n    "apply_tarifa"', '    "apply_tarifa"')],
)

p = pathlib.Path(BASE + "/adapters/inbound/declaracion/_extract.py")
content = p.read_text(encoding="utf-8")
content = content.replace('    "LabelExtractionHit",\n', "", 1)
content = re.sub(
    r"from [^\n]+\(\n\s+LabelHit as LabelExtractionHit,?\n\)\n", "", content
)
p.write_text(content, encoding="utf-8")

edit(
    "adapters/inbound/declaracion/_parsers/modelo_100/_scanner.py",
    [('    "HEADER_FORWARD_CIDS",\n    "ScannedCasilla"', '    "ScannedCasilla"')],
)
edit(
    "adapters/outbound/aeat/auth/_clave_movil.py",
    [('    "AEAT_CLAVE_MOVIL_SIDECAR_SCHEMA_VERSION",\n', "")],
)
edit(
    "adapters/outbound/aeat/export/_formats/_ingest.py",
    [('    "IngestSourceMeta",\n', "")],
)
edit(
    "adapters/outbound/aeat/export/_formats/_serialise.py",
    [('"HeaderValue", "serialise"', '"serialise"')],
)
edit(
    "adapters/outbound/aeat/export/_formats/_test_fixtures.py",
    [('    "KentProfile",\n', "")],
)

# Domain transactions (moved)
edit("domain/transactions/_repository.py", [('    "DirectionResolver",\n', "")])

# Domain vat (moved)
p = pathlib.Path(BASE + "/domain/vat/_catalogue.py")
content = p.read_text(encoding="utf-8")
content = content.replace('    "total_citation_count",\n', "", 1)
m = re.search(r"\n\ndef total_citation_count\b", content)
if m:
    remaining = content[m.start() + 2 :]
    nm = re.search(r"\n\n(def |class |__all__|#)", remaining)
    fe = m.start() + 2 + (nm.start() if nm else len(remaining))
    content = content[: m.start()] + content[fe:]
p.write_text(content, encoding="utf-8")

p = pathlib.Path(BASE + "/domain/vat/_rates.py")
content = p.read_text(encoding="utf-8")
content = re.sub(r',? ?"total_rate_count"', "", content)
m = re.search(r"\n\ndef total_rate_count\b", content)
if m:
    remaining = content[m.start() + 2 :]
    nm = re.search(r"\n\n(def |class |__all__|#)", remaining)
    fe = m.start() + 2 + (nm.start() if nm else len(remaining))
    content = content[: m.start()] + content[fe:]
p.write_text(content, encoding="utf-8")

# Normatives
p = pathlib.Path(BASE + "/domain/normatives/__init__.py")
content = p.read_text(encoding="utf-8")
content = content.replace('    "NORMATIVE_CATALOGUE",\n', "", 1)
old_def = '\nNORMATIVE_CATALOGUE: _LazyCatalogue = _LazyCatalogue()\n"""Lazy module-level :class:`NormativeCatalogue` singleton."""\n'
content = content.replace(old_def, "\n", 1)
p.write_text(content, encoding="utf-8")

# Testing schema
p = pathlib.Path(BASE + "/domain/testing/_schema.py")
content = p.read_text(encoding="utf-8")
content = content.replace('    "SYNTHETIC_COMMENT_REQUIRED_SUBSTRING",\n', "", 1)
content = content.replace('SYNTHETIC_COMMENT_REQUIRED_SUBSTRING = "SYNTHETIC"\n', "", 1)
content = re.sub(r"\n{3,}", "\n\n", content)
p.write_text(content, encoding="utf-8")

# Formulas
edit(
    "domain/formulas/_rulesets/_common.py",
    [('    "currency_casilla",\n', ""), ('    "round2",\n', "")],
)

edit(
    "domain/formulas/_rulesets/_mutators.py",
    [
        ('    "MutationCase",\n', ""),
        ('    "PercentRateLocation",\n', ""),
        ('    "build_percent_rate_mutants",\n', ""),
        ('    "build_scalar_mutants",\n', ""),
    ],
)
delete_func("domain/formulas/_rulesets/_mutators.py", "MutationCase", "class")
delete_func("domain/formulas/_rulesets/_mutators.py", "build_percent_rate_mutants")
delete_func("domain/formulas/_rulesets/_mutators.py", "build_scalar_mutants")

p = pathlib.Path(BASE + "/domain/formulas/_rulesets/modelo_100/_ccaa.py")
content = p.read_text(encoding="utf-8")
content = re.sub(r'    "TARIFA_[^"]+",\n', "", content)
p.write_text(content, encoding="utf-8")

p = pathlib.Path(BASE + "/domain/formulas/_rulesets/modelo_100/_common.py")
content = p.read_text(encoding="utf-8")
dead_urls = [
    "LIRPF_BASE_URL",
    "LIS_BASE_URL",
    "RIRPF_BASE_URL",
    "RD_LEY_4_2024_URL",
    "LEY_7_2024_URL",
    "LEY_12_2023_URL",
    "ORDEN_HAC_242_2025_URL",
    "ORDEN_HAC_277_2026_URL",
]
for name in dead_urls + ["LIS_CONSULT_2026_02_28_URL", "RIRPF_CONSULT_2026_02_28_URL"]:
    content = content.replace('    "' + name + '",\n', "", 1)
for name in dead_urls:
    m = re.search("\n" + re.escape(name) + r'[^\n]+\n(?:"""[^"]*"""\n)?', content)
    if m:
        content = content.replace(m.group(), "\n", 1)
p.write_text(content, encoding="utf-8")

p = pathlib.Path(BASE + "/domain/formulas/_rulesets/modelo_100/_minimos.py")
content = p.read_text(encoding="utf-8")
content = re.sub(r'    "MINIMO_[^"]+",\n', "", content)
p.write_text(content, encoding="utf-8")

edit(
    "domain/formulas/_rulesets/modelo_100/anexo_g_2024.py",
    [('    "TARIFA_ESTATAL_AHORRO_2024",\n', "")],
)

# Profile
for name in [
    "ASSETS_AMORTIZATION_LEDGER_FILENAME",
    "ASSETS_LEDGER_FILENAME",
    "AmortizationRecordResult",
    "AssetsLedgerDocument",
    "AssetsLedgerRepository",
    "save_amortization_ledger",
]:
    edit("domain/profile/assets/__init__.py", [('    "' + name + '",\n', "")])

for name in [
    "INVENTORY_LEDGER_FILENAME",
    "InventoryLedgerDocument",
    "InventoryLedgerRepository",
    "InventoryValuationResult",
]:
    edit("domain/profile/inventory/__init__.py", [('    "' + name + '",\n', "")])

# Rental
edit("domain/rental/_amortization_ledger.py", [('    "DAYS_PER_YEAR",\n', "")])
edit(
    "domain/rental/_anexo_c_aggregator.py",
    [
        ('    "CATASTRAL_REVISION_LOOKBACK_YEARS",\n', ""),
        ('    "IMPUTACION_RATE_OLD_OR_NO_REVISION",\n', ""),
        ('    "IMPUTACION_RATE_RECENT_REVISION",\n', ""),
    ],
)
edit(
    "domain/rental/_tier_resolver.py",
    [
        ('    "JOVEN_TENANT_AGE_MAX",\n', ""),
        ('    "JOVEN_TENANT_AGE_MIN",\n', ""),
        ('    "PRIOR_RENT_REBAJA_THRESHOLD",\n', ""),
        ('    "REHAB_LOOKBACK_DAYS",\n', ""),
    ],
)

# Entrypoints
edit(
    "entrypoints/cli/_errors.py",
    [('"command_error_boundary",\n    "decorate_typer_app"', '"decorate_typer_app"')],
)
edit("entrypoints/cli/audit/__init__.py", [('    "rulesets_app",\n', "")])
edit(
    "entrypoints/cli/financial/__init__.py",
    [('", "profile_app"', ""), (', "profile_app"', "")],
)
edit(
    "entrypoints/cli/financial/aggregate.py",
    [('"FinancialAggregateJson", "aggregate_cmd"', '"aggregate_cmd"')],
)
edit("entrypoints/cli/workflow/_helpers.py", [('    "EngineFactory",\n', "")])

print("All edits applied successfully")
