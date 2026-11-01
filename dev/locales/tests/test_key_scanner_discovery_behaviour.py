"""Synthetic-source behaviour of the locale key scanners: which literals, tables and wrappers they confirm."""

from __future__ import annotations

import pytest

from cadrumo.core.directory_scan import scan_directory

from .._paths import SRC_DIR

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("read_only", (False, True))
def test_a_locale_key_mapping_declares_its_values_and_not_its_lookup_tokens(read_only: bool) -> None:
    """Incident 3: a registry's KEYS are what the runtime selects on, not translations.

    A locale-key mapping is keyed by whatever picks the entry -- an enum value,
    a route identity, a catalogue action id -- and only its values are locale
    keys. Those tokens are dotted often enough to pass for keys:
    ``workbench.home`` is a TUI route and ``operator.profile.edit`` a catalogue
    action, and collecting them made the parity gate demand translations for
    24 identifiers no catalogue should ever have carried.

    The distinction only exists for a mapping. A tuple or list under the same
    naming convention is a flat set of keys and is still collected whole, which
    is the half this must not break.
    """
    from .._ast_scanner import scan_source_text

    source = chr(10).join(
        (
            "_ROUTE_LOCALE_KEYS = MappingProxyType({" if read_only else "_ROUTE_LOCALE_KEYS = {",
            '    "workbench.home": "tui.search.destination.home",',
            '    "operator.profile.edit": "tui.search.action.edit_profile",',
            "})" if read_only else "}",
            "_FLAT_LOCALE_KEYS = (",
            '    "tui.search.refusal.unknown",',
            ")",
        )
    )

    keys = scan_source_text(source, filename="probe.py")

    assert "tui.search.destination.home" in keys
    assert "tui.search.action.edit_profile" in keys
    assert "tui.search.refusal.unknown" in keys, "a flat registry must still be collected whole"
    assert "workbench.home" not in keys, "a route identity is not a locale key"
    assert "operator.profile.edit" not in keys, "a catalogue action id is not a locale key"


def test_a_key_suffix_is_not_an_identity_wrapped_catalogue_key(tmp_path) -> None:
    """A local prefixing helper must not invent translations for its suffixes."""
    from .._ast_scanner import scan_source_text, scan_source_tree

    source = "\n".join(
        (
            'def _key(suffix): return f"application.example.{suffix}"',
            "def tr(translation_key, **values): return translation_key",
            'tr(_key("entry.first"))',
            'tr(_key("entry.second"), role="role")',
            'tr(TranslationKey("application.example.entry.first"))',
            'tr(TranslationKey("application.example.entry.second"))',
            'option(help_key=_key("cli.config.help"))',
            'tr("application.direct.first" if condition else "application.direct.second")',
        )
    )
    (tmp_path / "wording.py").write_text(source, encoding="utf-8")
    text_keys = scan_source_text(source, filename="wording.py")
    tree_keys = scan_source_tree(tmp_path)

    for keys in (text_keys, tree_keys):
        assert "entry.first" not in keys
        assert "entry.second" not in keys
        assert {
            "application.example.entry.first",
            "application.example.entry.second",
            "cli.config.help",
            "application.direct.first",
            "application.direct.second",
        } <= keys


def test_a_row_table_is_confirmed_by_its_key_column_and_not_a_prose_sibling() -> None:
    """Incident 4: which COLUMN reaches the sink decides whether a table holds keys.

    A row table is confirmed by being iterated into a translator. Confirming on
    ANY unpacked name is too loose: the sibling columns are prose by design, so
    a table whose English refusal reaches ``raise ValueError(...)`` was read as
    a locale-key table, and its key column -- canonical COMMAND keys like
    ``ledger.review`` -- was collected as translations to demand.

    The genuine shape must keep working, so both directions are pinned here:
    the key column reaching ``tr`` still confirms.
    """
    from .._ast_scanner import scan_source_text

    prose_sink = chr(10).join(
        (
            '_GUARDS = (("review_action", "ledger.review", "injected action is not canonical"),)',
            "def guard(supplied):",
            "    for attribute, command_key, refusal in _GUARDS:",
            "        if supplied[attribute] != command_key:",
            "            raise ValueError(refusal)",
        )
    )
    key_sink = chr(10).join(
        (
            '_ROWS = (("prefix", "flows.errors.blank_required", "English source"),)',
            "def render():",
            "    for prefix, key, default in _ROWS:",
            "        tr(key)",
        )
    )

    assert "ledger.review" not in scan_source_text(prose_sink, filename="guards.py"), (
        "a command key is not a translation key because its prose sibling reached a raise"
    )
    assert "flows.errors.blank_required" in scan_source_text(key_sink, filename="rows.py"), (
        "a key column reaching tr must still confirm its table"
    )


def test_a_positional_translation_key_needs_every_same_named_helper_to_agree(tmp_path) -> None:
    """Incident 5: resolving a key by parameter NAME collides on function name.

    A command spec fills its help key positionally into a helper defined in
    another module, so the key is invisible without the callee signature.
    Resolving it by bare function name collides: eight ``_leaf`` helpers ship
    here, carrying ``help_key`` at index 3, 1 or 2, and one whose index 1 is
    ``module``. Taking the union collected module import paths as translation
    keys, and the parity gate reported them as missing translations.

    A position counts only when EVERY definition of that name carries a
    translation-key parameter there. Both halves are pinned here: the agreeing
    name resolves, the disagreeing one yields nothing rather than guessing.
    """
    from .._ast_scanner import scan_source_tree

    (tmp_path / "helpers.py").write_text(
        chr(10).join(
            (
                "def option(name, flags, help_key):",
                "    return (name, flags, help_key)",
                "def leaf(token, help_key, handler):",
                "    return (token, help_key, handler)",
            )
        ),
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        chr(10).join(
            (
                "def leaf(token, module, parameters):",
                "    return (token, module, parameters)",
            )
        ),
        encoding="utf-8",
    )
    (tmp_path / "specs.py").write_text(
        chr(10).join(
            (
                'option("note", ("--note",), "cli.app.ledger.note_help")',
                'leaf("calculate", "cadrumo.entrypoints.cli._work_cli", "handler")',
            )
        ),
        encoding="utf-8",
    )

    keys = scan_source_tree(tmp_path)

    assert "cli.app.ledger.note_help" in keys, "an agreeing helper must resolve its positional key"
    assert "cadrumo.entrypoints.cli._work_cli" not in keys, (
        "definitions that disagree on the position must collect nothing there"
    )


def test_a_local_translator_wrapper_is_followed_but_only_when_it_forwards_its_key(tmp_path) -> None:
    """Incident 6: every TUI surface routes copy through its own boundary helper.

    `def aeat_sync_copy(key, **values): return tr(key, **values)` means the call
    sites read `aeat_sync_copy("tui.aeat_sync.column.area")` and never `tr(...)`.
    The scanner resolved aliased IMPORTS of tr but not a wrapper defined as a
    function, so every key reaching the catalogue through one of these
    boundaries read as an orphan -- 89 of them.

    The shape is deliberately tight, and the negative case is what keeps it so:
    the function must forward its OWN first parameter. A helper that calls tr on
    something else is not a key channel, and its arguments are not keys.
    """
    from .._ast_scanner import scan_source_tree

    (tmp_path / "boundary.py").write_text(
        chr(10).join(
            (
                "def copy(key, **values):",
                "    return tr(key, **values)",
                "def shout(text):",
                '    return tr("ui.fixed.banner") + text',
            )
        ),
        encoding="utf-8",
    )
    (tmp_path / "screen.py").write_text(
        chr(10).join(
            (
                'copy("tui.aeat_sync.column.area")',
                'shout("tui.aeat_sync.column.not_a_key")',
            )
        ),
        encoding="utf-8",
    )

    keys = scan_source_tree(tmp_path)

    assert "tui.aeat_sync.column.area" in keys, "a wrapper forwarding its key must be followed"
    assert "ui.fixed.banner" in keys, "the non-forwarding helper still declares its own literal"
    assert "tui.aeat_sync.column.not_a_key" not in keys, (
        "a helper that does not forward its first parameter is not a key channel"
    )


def test_a_translation_key_kwarg_is_read_through_a_conditional(tmp_path) -> None:
    """Incident 7: a key chosen by a conditional is still a key.

    `empty_key="a.b" if not rows else None` is how a surface says "this label
    depends on state". The collector read only a bare literal, so BOTH arms
    vanished -- and the failure is asymmetric in the worst direction: the key
    that ships is the one behind the condition, so the catalogue looks complete
    on the path a developer happens to exercise and is missing on the other.

    The negative arm matters as much: `None` is not a key, and a value that is
    not a dotted literal must not be invented into one.
    """
    from .._ast_scanner import scan_source_text

    source = chr(10).join(
        (
            "def render(rows):",
            "    return table(",
            '        label_key="flows.progress.rows_present",',
            '        empty_key="flows.progress.rows_absent" if not rows else None,',
            "    )",
        )
    )

    keys = scan_source_text(source, filename="table.py")

    assert "flows.progress.rows_present" in keys, "a plain key kwarg must be collected"
    assert "flows.progress.rows_absent" in keys, "a key inside a conditional is the key that ships on that branch"
    assert not any(key.endswith("None") for key in keys), "a non-literal arm is not a key"


def test_a_key_registry_is_flow_confirmed_through_a_boundary_wrapper(tmp_path) -> None:
    """Incident 8: the same wrapper blindness as Incident 6, one layer down.

    A dict shaped as a key registry is admitted only when it is proved to
    REACH a translator -- shape alone is deliberately insufficient, because
    same-shaped lookup tables exist that never translate. That proof consulted
    only `tr` and its import aliases, so a registry read through the boundary
    helper every surface is asked to use was never confirmed, and every key in
    it read as an orphan.

    Shape alone must still not be enough, which is what the second registry
    pins: a same-shaped table nothing reads stays unconfirmed even in a module
    that has a wrapper in it.
    """
    from .._ast_scanner import scan_source_tree

    (tmp_path / "boundary.py").write_text(
        chr(10).join(("def screen_copy(key, **values):", "    return tr(key, **values)")),
        encoding="utf-8",
    )
    (tmp_path / "controller.py").write_text(
        chr(10).join(
            (
                "_AVAILABILITY_KEYS = {",
                '    Availability.STALE: "workspace.declarations.availability.stale",',
                "}",
                "_ROUTING_TABLE = {",
                '    Notice.RETRY: "notice.machine.retry",',
                "}",
                "def label(value):",
                "    return screen_copy(_AVAILABILITY_KEYS[value])",
            )
        ),
        encoding="utf-8",
    )

    keys = scan_source_tree(tmp_path)

    assert "workspace.declarations.availability.stale" in keys, (
        "a registry read through a boundary wrapper reaches the translator and is confirmed"
    )
    assert "notice.machine.retry" not in keys, (
        "shape alone must still not confirm a table nothing reads into a translator"
    )


def test_a_dynamic_namespace_is_read_when_its_prefix_is_selected_from_a_table() -> None:
    """Incident 9: a screen that renders every enum through one helper.

    The namespace rule required the f-string's HEAD to be the dotted literal.
    A workspace that renders each public enum through one helper does not write
    the prefix at the call site -- it declares a table of prefixes, selects one
    by the enum's class name, and appends the member value. The head is then an
    interpolation, so no namespace was declared at all and every key the helper
    builds read as an orphan.

    The tail is an enum member value, so the key space is bounded by the enum
    definition -- the same criterion the wizard namespaces already qualify
    under.

    The negative arm is what keeps the rule from becoming "any f-string that
    starts with a variable": the segment after the interpolation must begin
    with the dot, which is what proves the name is being used AS a dotted
    prefix rather than as ordinary leading text.
    """
    from .._ast_scanner import scan_namespace_markers_in_text

    source = chr(10).join(
        (
            "_LABEL_PREFIXES = {",
            '    "AeatSyncCensusStatus": "tui.aeat_sync.census_status",',
            "}",
            "_GREETINGS = {",
            '    "morning": "cli.greeting.morning",',
            "}",
            "def label(value):",
            "    prefix = _LABEL_PREFIXES.get(type(value).__name__)",
            '    return copy(f"{prefix}.{value.value}")',
            "def greet(slot):",
            "    greeting = _GREETINGS.get(slot)",
            '    return f"{greeting} and welcome"',
        )
    )

    markers = scan_namespace_markers_in_text(source, filename="screens.py")

    assert "tui.aeat_sync.census_status.*" in markers, (
        "a prefix selected from a declared table and dotted onto is a namespace"
    )
    assert "cli.greeting.morning.*" not in markers, (
        "an interpolation not followed by a dot is not being used as a prefix"
    )


def test_a_column_table_is_read_as_an_attribute_and_confirmed_by_its_key_index() -> None:
    """Incident 10: the screen column table, held as a ClassVar and indexed.

    Three things stood between this table and the scanner, and each alone was
    enough to hide every heading key in it:

    * the row carries a WIDTH, and the shape test demanded all-string rows, so
      the table was never even a candidate;
    * it is read back as `self._COLUMNS`, an attribute, while confirmation
      required a bare name to be iterated;
    * the row is bound whole and the key taken as `column[1]`, while
      confirmation looked for an unpacked name.

    The key-column discipline is unchanged and is what the negative arm pins:
    indexing a PROSE sibling into the translator says nothing about the table,
    exactly as it says nothing when the row is unpacked. A width is no more a
    key than prose is, which is why a non-string cell is carried as a position
    that can never be a key column rather than as grounds to reject the table.
    """
    from .._ast_scanner import scan_source_text

    key_index = chr(10).join(
        (
            "class Screen:",
            "    _COLUMNS = (",
            '        ("date", "tui.ledger.column.date", 10),',
            '        ("amount", "tui.ledger.column.amount", 14),',
            "    )",
            "    def render(self):",
            "        for column in self._COLUMNS:",
            "            yield tr(column[1])",
        )
    )
    prose_index = key_index.replace("tr(column[1])", "tr(column[0])")

    collected = scan_source_text(key_index, filename="entries.py")

    assert "tui.ledger.column.date" in collected, "a width sibling must not disqualify the table"
    assert "tui.ledger.column.amount" in collected, "the attribute read and the key index both confirm"
    assert "tui.ledger.column.amount" not in scan_source_text(prose_index, filename="entries.py"), (
        "indexing a prose column into the translator does not confirm the table"
    )

    # A sibling need not be a literal at all. The choice table pairs its key
    # with the ENUM member the choice sets, and demanding literal constants
    # rejected that table as surely as demanding strings rejected the one
    # above -- same shape, different sibling.
    enum_sibling = chr(10).join(
        (
            "_CHOICES = (",
            '    (BusinessClassification.BUSINESS, "tui.ledger.classification.business"),',
            '    (BusinessClassification.PERSONAL, "tui.ledger.classification.personal"),',
            ")",
            "for classification, key in _CHOICES:",
            "    table.add_row(tr(key), key=classification.value)",
        )
    )

    assert "tui.ledger.classification.business" in scan_source_text(enum_sibling, filename="classification.py"), (
        "an enum member sibling must not disqualify the table either"
    )


def test_a_class_attribute_key_is_confirmed_by_the_attribute_the_base_renders(tmp_path) -> None:
    """Incident 11: a screen family names its banner on the subclass.

    The subclass declares `heading = "tui.aeat_sync.census.title"` and the base
    renders `aeat_sync_copy(self.heading)`. That declaration is not a call, a
    suffixed registry constant, or a collection, so every rule in the scanner
    looked straight past it and each subclass banner read as an orphan.

    The negative arm is the one this scanner has already been bitten by: a
    class attribute holding a dotted literal is just as likely to be a route or
    an action id as a translation key, and `workbench.home` is a lookup token,
    not copy. The attribute NAME must be read into a translator for its
    literals to count -- the same bargain the dict and row-table shapes strike.
    """
    from .._ast_scanner import scan_source_tree

    (tmp_path / "boundary.py").write_text(
        chr(10).join(("def screen_copy(key, **values):", "    return tr(key, **values)")),
        encoding="utf-8",
    )
    (tmp_path / "screens.py").write_text(
        chr(10).join(
            (
                "class Base:",
                "    def compose(self):",
                "        yield Static(screen_copy(self.heading))",
                "class Census(Base):",
                '    heading = "tui.aeat_sync.census.title"',
                '    route = "workbench.census.home"',
            )
        ),
        encoding="utf-8",
    )

    keys = scan_source_tree(tmp_path)

    assert "tui.aeat_sync.census.title" in keys, "the attribute the base renders carries a real key"
    assert "workbench.census.home" not in keys, "a class attribute nothing renders is a route or an action id, not copy"


def test_every_translation_key_annotated_parameter_is_declared_a_key_kwarg() -> None:
    """Incident 12: the kwarg set was grown one orphan at a time.

    `_TRANSLATION_KEY_KWARGS` decides which keyword arguments carry a locale
    key, and every entry in it arrived because somebody chased a key that had
    gone missing. That is discovery by casualty: a parameter is only added
    after its keys have already been invisible for a while.

    The codebase states the answer in the type. A parameter annotated
    `TranslationKey` IS a translation key, so the annotation -- not a
    maintainer's memory -- is what the set must agree with. Three names were
    missing when this gate was written (`reason_key`, `short_help_key`,
    `prompt_key`, `confirmation_prompt_key`).

    The set stays hand-written rather than derived, deliberately: it is read at
    five sites and an explicit list is auditable, while a set computed from a
    tree walk hides the surface it admits. The gate is what makes the list
    honest.
    """
    import ast

    from .._ast_key_policy import _TRANSLATION_KEY_KWARGS

    def _names_the_translation_key_type(annotation: ast.expr | None) -> bool:
        if isinstance(annotation, ast.Name):
            return annotation.id == "TranslationKey"
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            return annotation.value.split("|")[0].strip() == "TranslationKey"
        if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            return _names_the_translation_key_type(annotation.left) or _names_the_translation_key_type(annotation.right)
        return False

    annotated: set[str] = set()
    for module in scan_directory(SRC_DIR, pattern="*.py", recursive=True):
        if "TranslationKey" not in module.read_text(encoding="utf-8"):
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if _names_the_translation_key_type(node.annotation):
                    annotated.add(node.target.id)
            elif isinstance(node, ast.arg) and _names_the_translation_key_type(node.annotation):
                annotated.add(node.arg)

    assert annotated, "no TranslationKey-annotated parameter was found, so this proved nothing"
    undeclared = sorted(annotated - set(_TRANSLATION_KEY_KWARGS))
    assert not undeclared, (
        "these parameters are annotated TranslationKey but are not declared translation-key "
        f"kwargs, so every dotted literal passed to one is invisible to the scanner: {undeclared}"
    )


def test_a_column_table_handed_to_a_shared_fitter_is_still_confirmed() -> None:
    """Incident 13: the table is not iterated where it is declared.

    Every AEAT Sync screen sizes its columns with one shared helper rather than
    repeating the rule, so the table is HANDED OVER::

        _fit_columns(self.app.size.width, self._COLUMNS, self._VALUE_COLUMNS)

    Inside the helper the parameter is iterated in a GENERATOR EXPRESSION and
    each row is translated. Two things hid that: confirmation walked only
    ``for`` statements, and a parameter name said nothing about which table had
    been passed into it.

    A parameter filled by several tables confirms all of them. That is not a
    guess -- one helper serves every screen, so if its parameter's rows reach a
    translator then every table handed to it is translated. Dropping the name
    as ambiguous, which is what a first attempt did, failed the common case for
    being common: only the table that happened to be unique was recovered.

    The key-column discipline is unchanged, and the negative arm holds it: a
    helper that indexes the PROSE column confirms nothing, however many tables
    are handed to it.
    """
    from .._ast_scanner import scan_source_text

    handed_over = chr(10).join(
        (
            "_CENSUS = (",
            '    ("field", "tui.aeat_sync.column.field", 26),',
            ")",
            "_VALUES = (",
            '    ("local_value", "tui.aeat_sync.column.local_value", 16),',
            ")",
            "def _fit(width, standalone, pair=()):",
            "    def _sized(column):",
            "        return column[0], tr(column[1])",
            "    return [_sized(column) for column in standalone]",
            "def render(self):",
            "    return _fit(80, _CENSUS, _VALUES) + _fit(80, _VALUES)",
        )
    )
    prose_fitter = handed_over.replace("tr(column[1])", "tr(column[0])")

    collected = scan_source_text(handed_over, filename="screens.py")

    assert "tui.aeat_sync.column.field" in collected, "a table handed to the shared fitter is translated"
    assert "tui.aeat_sync.column.local_value" in collected, (
        "a parameter filled by several tables confirms every one of them"
    )
    assert "tui.aeat_sync.column.field" not in scan_source_text(prose_fitter, filename="screens.py"), (
        "a fitter that indexes the prose column confirms nothing"
    )


def test_a_row_table_written_inline_at_the_call_site_is_confirmed() -> None:
    """Incident 14: a column table with no name of its own.

    One screen builds its columns in the argument list rather than binding them
    first. Every rule in this scanner registers a candidate under an assignment
    target, so a table with no name was invisible -- although it is the same
    table, handed to the same fitter, doing the same job as its named siblings
    two screens away.

    It is admitted on exactly the same terms as a named one: registered under a
    synthetic name so the parameter alias and the key-column rule both apply
    unchanged, and confirmed only when that parameter's rows actually reach a
    translator. The negative arm is what proves the terms are the same -- an
    inline table handed to a helper that never translates stays out, so being
    anonymous buys no shortcut past confirmation.
    """
    from .._ast_scanner import scan_source_text

    confirmed = chr(10).join(
        (
            "def _fit(width, standalone):",
            "    return [tr(column[1]) for column in standalone]",
            "def _measure(width, rows):",
            "    return [column[2] for column in rows]",
            "def render(self):",
            "    return _fit(",
            "        80,",
            "        (",
            '            ("declaration", "tui.aeat_sync.column.declaration", 20),',
            '            ("resolution", "tui.aeat_sync.column.resolution", 14),',
            "        ),",
            "    )",
        )
    )
    never_translated = chr(10).join(
        (
            "def _measure(width, rows):",
            "    return [column[2] for column in rows]",
            "def render(self):",
            "    return _measure(",
            "        80,",
            "        (",
            '            ("declaration", "tui.aeat_sync.column.untranslated", 20),',
            '            ("resolution", "tui.aeat_sync.column.also_untranslated", 14),',
            "        ),",
            "    )",
        )
    )

    keys = scan_source_text(confirmed, filename="screens.py")

    assert "tui.aeat_sync.column.resolution" in keys, "an inline table reaching the translator is confirmed"
    assert "tui.aeat_sync.column.declaration" in keys, "every key column entry in it comes with it"

    unconfirmed = scan_source_text(never_translated, filename="screens.py")

    assert "tui.aeat_sync.column.untranslated" not in unconfirmed, (
        "an inline table handed to a helper that never translates must stay unconfirmed"
    )


def test_a_key_held_in_a_local_is_confirmed_by_the_translator_that_reads_it() -> None:
    """Incident 15: the surface names its choice before rendering it.

    A screen picking between two labels writes the choice down first::

        status_key = "tui.ledger.evidence.pending" if pending else "tui.ledger.evidence.reviewed"
        table.add_row(..., ledger_copy(status_key))

    The call site passes a NAME, so the literal resolver saw no key there, and
    the value is a bare scalar rather than a registry, so the constant and
    collection rules had nothing to match either. BOTH branches were invisible.

    The negative arm is the one this scanner keeps having to relearn: a dotted
    literal in a local is as likely to be a route or a lookup token as copy.
    `destination = "workbench.home"` handed to a router is not a translation,
    and only the name reaching a TRANSLATOR admits its literals.
    """
    from .._ast_scanner import scan_source_text

    source = chr(10).join(
        (
            "def render(self, pending, rows):",
            '    status_key = "tui.ledger.evidence.pending" if pending else "tui.ledger.evidence.reviewed"',
            '    destination = "workbench.home"',
            "    self.navigate(destination)",
            "    return tr(status_key)",
        )
    )

    keys = scan_source_text(source, filename="evidence.py")

    assert "tui.ledger.evidence.pending" in keys, "the branch that renders when pending is a key"
    assert "tui.ledger.evidence.reviewed" in keys, "so is the other branch, which no run exercises first"
    assert "workbench.home" not in keys, "a local handed to a router is a route, not copy"


def test_a_local_bound_to_a_registry_is_left_to_the_registry_rules() -> None:
    """The local rule must not claim a shape it does not confirm.

    A local bound to a dict or a subscript is already the business of the
    registry and row-table rules, which confirm it by how it is READ. Widening
    the local rule to any expression would let it collect those shapes without
    that confirmation, so its candidate value stays a string constant or a
    conditional between them.
    """
    import ast

    from .._ast_key_flows import _flow_confirmed_local_key_names
    from .._ast_scanner import scan_source_text

    source = chr(10).join(
        (
            "_ROUTES = {",
            '    "home": "workbench.routes.home",',
            "}",
            "def render(self, token):",
            "    chosen = _ROUTES[token]",
            "    return tr(chosen)",
        )
    )

    assert not _flow_confirmed_local_key_names(ast.parse(source)), (
        "the local rule must not claim a name bound to a registry; its value is not a key expression"
    )

    # The restriction earns its place on this shape. A local bound to a CALL
    # can carry a dotted literal that is not a key at all -- a module path is
    # the form this campaign has already been bitten by -- and admitting any
    # expression would collect it the moment the name is translated.
    derived = chr(10).join(
        (
            "def render(self):",
            '    label = _humanise("cadrumo.core.wizard_catalogue")',
            "    return tr(label)",
        )
    )

    assert not _flow_confirmed_local_key_names(ast.parse(derived)), (
        "a local bound to a call is not a key expression, whatever literals the call mentions"
    )

    # The key is still collected here -- by the DICT rule, which confirmed the
    # registry through the subscript that reads it. That is the point: the two
    # rules do not overlap, and this one is not doing the other's work.
    assert "workbench.routes.home" in scan_source_text(source, filename="router.py"), (
        "the registry rule still confirms the dict it owns"
    )


def test_a_mapping_get_literal_fallback_reaching_translation_is_discovered() -> None:
    """A runtime fallback needs no scanner-only aggregate registry."""
    from .._ast_scanner import scan_source_text

    source = chr(10).join(
        (
            "LABELS = {'known': 'tui.search.destination.known'}",
            "def render(token):",
            "    key = LABELS.get(token, 'tui.search.destination.unknown')",
            "    return tr(key)",
            "def route(token):",
            "    destination = LABELS.get(token, 'workbench.destination.unknown')",
            "    return navigate(destination)",
        )
    )

    keys = scan_source_text(source, filename="fallback.py")

    assert "tui.search.destination.unknown" in keys
    assert "workbench.destination.unknown" not in keys


def test_a_guard_that_admits_only_authored_keys_declares_them(tmp_path) -> None:
    """Incident 16: the keys are declared in one module and rendered in another.

    A boundary that will not render an arbitrary string states the keys it
    accepts::

        _SAFE_SOURCE_KEYS = frozenset({"tui.ledger.import.source.prepared"})
        if source_label_key not in _SAFE_SOURCE_KEYS:
            raise ...

    and the screen beside it renders the admitted value as
    `ledger_copy(choice.source_label_key)`. Nothing in the module that DECLARES
    the keys translates them, and nothing in the module that translates them
    mentions a literal, so each half looked inert on its own.

    The link is the membership test, NOT a naming convention -- the guarded
    name has to be one this tree actually passes to a translator. The negative
    arm is a guard over a name nothing translates: an allow-list of choice ids
    is the same shape and proves nothing about copy, so it stays out.
    """
    from .._ast_scanner import scan_source_tree

    (tmp_path / "boundary.py").write_text(
        chr(10).join(("def ledger_copy(key, **values):", "    return tr(key, **values)")),
        encoding="utf-8",
    )
    (tmp_path / "models.py").write_text(
        chr(10).join(
            (
                '_SAFE_SOURCE_KEYS = frozenset({"tui.ledger.import.source.prepared"})',
                '_SAFE_CHOICE_IDS = frozenset({"ledger.choice.prepared"})',
                "def seal(source_label_key, choice_id):",
                "    if source_label_key not in _SAFE_SOURCE_KEYS:",
                "        raise ValueError",
                "    if choice_id not in _SAFE_CHOICE_IDS:",
                "        raise ValueError",
            )
        ),
        encoding="utf-8",
    )
    (tmp_path / "import_flow.py").write_text(
        chr(10).join(("def row(choice):", "    return ledger_copy(choice.source_label_key)")),
        encoding="utf-8",
    )

    keys = scan_source_tree(tmp_path)

    assert "tui.ledger.import.source.prepared" in keys, (
        "a guard admitting a value the tree translates is declaring keys"
    )
    assert "ledger.choice.prepared" not in keys, (
        "the same shape over a name nothing translates is an identity allow-list, not copy"
    )


def test_a_function_whose_every_return_is_a_key_is_followed_into_its_caller() -> None:
    """Incident 17: the refusal names its own reason through a factory.

    A gate that must pick a reason writes the choice as a FUNCTION and the
    caller assigns the result before passing it on::

        def session_refusal_translation_key(refusal):
            return "cli...absent" if refusal in _LOGGED_OUT else "cli...expired"
        ...
        key = session_refusal_translation_key(refusal)
        raise CliRefusedBoundaryError(translated_message=key, ...)

    The local rule (Incident 15) declines this deliberately: its candidate value
    must be a key EXPRESSION and a call is not one. So both branches were
    invisible, and the asymmetry is the familiar one -- whichever refusal a
    developer happens to trigger looks translated.

    The admission rule is that EVERY return must be a key expression. The
    negative arm is a function with one ordinary return among its keys: it is
    not a key factory, and none of its literals count. Without that, this would
    collect from any function that mentions a dotted string.
    """
    from .._ast_scanner import scan_source_text

    source = chr(10).join(
        (
            "def refusal_key(reason):",
            '    return "cli.config.errors.profile_session_absent"'
            ' if reason else "cli.config.errors.profile_session_expired"',
            "def route_for(reason):",
            "    if reason:",
            '        return "workbench.routes.home"',
            "    return compute_route(reason)",
            "def refuse(reason):",
            "    key = refusal_key(reason)",
            "    routed = route_for(reason)",
            # Deliberately TRANSLATED, not merely navigated. Sending it somewhere
            # inert would let flow confirmation reject it and leave the
            # every-return rule untested -- the arm below has to fail for the
            # reason it names.
            "    banner(tr(routed))",
            "    raise CliRefusedBoundaryError(translated_message=key)",
        )
    )

    keys = scan_source_text(source, filename="gate.py")

    assert "cli.config.errors.profile_session_absent" in keys, "the branch a logged-out refusal renders is a key"
    assert "cli.config.errors.profile_session_expired" in keys, "so is the branch no run may have exercised"
    assert "workbench.routes.home" not in keys, (
        "a function with one non-key return is not a key factory, whatever its other returns hold"
    )
