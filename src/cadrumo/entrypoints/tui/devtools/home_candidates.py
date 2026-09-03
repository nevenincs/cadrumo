"""Pure Textual candidates over an injected immutable Home projection.

The candidates deliberately stop at selection.  They neither read state nor
invoke an application action; later prototype measurement can therefore
compare layout and keyboard cost without acquiring business authority.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar, Final, cast, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ....application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from ....application.overview.home import (
    HomeAgendaEntry,
    HomeAvailability,
    HomeDeclarationResume,
    HomeDeclarationState,
    HomeNextAction,
    HomeProjectionV1,
    HomeSessionPosture,
    HomeTargetKind,
    HomeZoneState,
)
from ....core.external_constants import OutputLanguage
from ..components.widgets import ContentDataTable, ContentScroll
from ..home import (
    home_action_identity as _action_identity,
)
from ..home import (
    home_address as _address,
)
from ..home import (
    home_agenda_identity as _agenda_identity,
)
from ..home import (
    home_declaration_identity as _declaration_identity,
)


@dataclass(frozen=True, slots=True)
class HomeCandidateTarget:
    """One semantic prototype selection, independent of row position."""

    kind: HomeTargetKind
    identity: str


_AVAILABILITY_COPY: Final[dict[HomeAvailability, str]] = {
    HomeAvailability.AVAILABLE: "Available",
    HomeAvailability.LOCKED: "Locked — unlock the selected profile to view this information",
    HomeAvailability.STALE: "Stale — the last local snapshot needs refresh",
    HomeAvailability.NEVER_CAPTURED: "Not captured yet",
    HomeAvailability.UNAVAILABLE: "Unavailable — this source cannot be read in the current session",
}
_SESSION_COPY: Final[dict[HomeSessionPosture, str]] = {
    HomeSessionPosture.NO_PROFILE: "No profile selected",
    HomeSessionPosture.LOCKED: "Profile locked",
    HomeSessionPosture.ACTIVE: "Active local session",
    HomeSessionPosture.EXPIRED: "Session expired",
}
_DECLARATION_COPY: Final[dict[HomeDeclarationState, str]] = {
    HomeDeclarationState.DRAFT: "Draft",
    HomeDeclarationState.NEEDS_REVIEW: "Needs review",
    HomeDeclarationState.READY: "Ready",
    HomeDeclarationState.FILED: "Filed",
    HomeDeclarationState.DISCARDED: "Discarded",
}
_PERIOD_COPY: Final[dict[OverviewPeriodState, str]] = {
    OverviewPeriodState.DUE: "Due",
    OverviewPeriodState.LATE: "Overdue",
    OverviewPeriodState.FILED: "Filed",
    OverviewPeriodState.UNKNOWN: "Schedule unknown",
}
_LOCAL_COPY: Final[dict[OverviewLocalFilingState, str]] = {
    OverviewLocalFilingState.NOT_READY_TO_FILE: "not ready locally",
    OverviewLocalFilingState.READY_TO_FILE: "ready locally",
    OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED: "external filing baseline stored locally",
}
_AEAT_COPY: Final[dict[OverviewAeatSubmissionState, str]] = {
    OverviewAeatSubmissionState.NOT_OBSERVED: "not observed at AEAT",
    OverviewAeatSubmissionState.SUBMITTED_OBSERVED: "submission observed at AEAT",
    OverviewAeatSubmissionState.ACCEPTED: "accepted by AEAT",
    OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED: "AEAT receipt verified",
}
_ACTION_COPY: Final[dict[str, str]] = {
    "fixture.review": "Review declaration",
    "fixture.classify": "Classify Ledger entries",
    "fixture.evidence": "Add missing evidence",
    "fixture.resolve_blocker": "Resolve declaration blocker",
    "fixture.review_blocker": "Review blocked work",
    "fixture.evidence_blocker": "Resolve missing evidence",
}
_ACTION_REASON_COPY: Final[dict[str, str]] = {
    "fixture.review_required": "Declaration needs review",
    "fixture.classification_pending": "Ledger classification is pending",
    "fixture.evidence_missing": "Supporting evidence is missing",
    "fixture.blocked_dependency": "A declaration dependency is blocked",
    "fixture.blocked_review": "Blocked work needs review",
    "fixture.blocked_evidence": "A blocker needs supporting evidence",
}

_TRANSLATIONS: Final[dict[OutputLanguage, dict[str, str]]] = {
    OutputLanguage.EN: {},
    OutputLanguage.ES: {
        "Home": "Inicio",
        "due-driven candidate": "candidato por vencimientos",
        "task-launcher candidate": "candidato lanzador de tareas",
        "No profile selected": "Ningún perfil seleccionado",
        "Profile locked": "Perfil bloqueado",
        "Active local session": "Sesión local activa",
        "Session expired": "Sesión caducada",
        "Account": "Cuenta",
        "Available": "Disponible",
        "Locked — unlock the selected profile to view this information": (
            "Bloqueado — desbloquee el perfil para ver esta información"
        ),
        "Stale — the last local snapshot needs refresh": "Desactualizado — actualice la última captura local",
        "Not captured yet": "Aún no capturado",
        "Unavailable — this source cannot be read in the current session": (
            "No disponible — la fuente no puede leerse en esta sesión"
        ),
        "Next actions": "Próximas acciones",
        "Declarations": "Declaraciones",
        "Filing agenda": "Agenda de presentación",
        "Ledger": "Libros registro",
        "Messages": "Mensajes",
        "Quick tasks": "Tareas rápidas",
        "Task detail": "Detalle de la tarea",
        "Declaration needs review": "La declaración necesita revisión",
        "Ledger classification is pending": "Hay clasificación pendiente en libros",
        "Supporting evidence is missing": "Falta documentación justificativa",
        "A declaration dependency is blocked": "Una dependencia de la declaración está bloqueada",
        "Blocked work needs review": "El trabajo bloqueado necesita revisión",
        "A blocker needs supporting evidence": "Un bloqueo necesita documentación",
        "Review declaration": "Revisar declaración",
        "Classify Ledger entries": "Clasificar asientos",
        "Add missing evidence": "Añadir justificante",
        "Resolve declaration blocker": "Resolver bloqueo",
        "Review blocked work": "Revisar trabajo bloqueado",
        "Resolve missing evidence": "Resolver justificante pendiente",
        "Draft": "Borrador",
        "Needs review": "Requiere revisión",
        "Ready": "Preparada",
        "Filed": "Presentada",
        "Discarded": "Descartada",
        "Due": "Próxima",
        "Overdue": "Fuera de plazo",
        "Schedule unknown": "Calendario desconocido",
        "not ready locally": "no preparada localmente",
        "ready locally": "preparada localmente",
        "external filing baseline stored locally": "referencia externa guardada localmente",
        "not observed at AEAT": "no observada en AEAT",
        "submission observed at AEAT": "presentación observada en AEAT",
        "accepted by AEAT": "aceptada por AEAT",
        "AEAT receipt verified": "justificante AEAT verificado",
        "Across records": "Para varios registros",
        "Suggested": "Sugerida",
        "Resume": "Continuar",
        "Inspect": "Consultar",
        "Local": "Local",
        "Deadline": "Plazo",
        "Date": "Fecha",
        "Status": "Estado",
        "Actions": "Acciones",
        "Agenda": "Agenda",
        "AEAT evidence": "Evidencia AEAT",
        "need review": "requieren revisión",
        "entries": "asientos",
        "unclassified": "sin clasificar",
        "missing evidence": "sin justificante",
        "Local declaration status": "Estado local de la declaración",
        "requiring attention": "requieren atención",
        "no suggested actions": "sin acciones sugeridas",
        "no resumable declarations": "sin declaraciones para continuar",
        "no upcoming filing dates": "sin próximas fechas",
        "none suggested": "ninguna sugerida",
        "none resumable": "ninguna para continuar",
        "no dates": "sin fechas",
        "last observed": "última observación",
        "Choose a task to inspect its context.": "Elija una tarea para consultar su contexto.",
        "Use Up/Down to choose and Enter to confirm.": "Use Arriba/Abajo y Entrar para confirmar.",
        "No quick tasks are available from the captured local information.": (
            "No hay tareas rápidas en la información local capturada."
        ),
    },
    OutputLanguage.CA: {
        "Home": "Inici",
        "due-driven candidate": "candidat per venciments",
        "task-launcher candidate": "candidat llançador de tasques",
        "No profile selected": "Cap perfil seleccionat",
        "Profile locked": "Perfil bloquejat",
        "Active local session": "Sessió local activa",
        "Session expired": "Sessió caducada",
        "Account": "Compte",
        "Available": "Disponible",
        "Locked — unlock the selected profile to view this information": (
            "Bloquejat — desbloquegeu el perfil per veure aquesta informació"
        ),
        "Stale — the last local snapshot needs refresh": "Desactualitzat — actualitzeu la darrera captura local",
        "Not captured yet": "Encara no capturat",
        "Unavailable — this source cannot be read in the current session": (
            "No disponible — la font no es pot llegir en aquesta sessió"
        ),
        "Next actions": "Accions següents",
        "Declarations": "Declaracions",
        "Filing agenda": "Agenda de presentació",
        "Ledger": "Llibres registre",
        "Messages": "Missatges",
        "Quick tasks": "Tasques ràpides",
        "Task detail": "Detall de la tasca",
        "Declaration needs review": "La declaració necessita revisió",
        "Ledger classification is pending": "Hi ha classificació pendent als llibres",
        "Supporting evidence is missing": "Falta documentació justificativa",
        "A declaration dependency is blocked": "Una dependència de la declaració està bloquejada",
        "Blocked work needs review": "La tasca bloquejada necessita revisió",
        "A blocker needs supporting evidence": "Un bloqueig necessita documentació",
        "Review declaration": "Revisar declaració",
        "Classify Ledger entries": "Classificar assentaments",
        "Add missing evidence": "Afegir justificant",
        "Resolve declaration blocker": "Resoldre bloqueig",
        "Review blocked work": "Revisar tasca bloquejada",
        "Resolve missing evidence": "Resoldre justificant pendent",
        "Draft": "Esborrany",
        "Needs review": "Requereix revisió",
        "Ready": "Preparada",
        "Filed": "Presentada",
        "Discarded": "Descartada",
        "Due": "Pròxima",
        "Overdue": "Fora de termini",
        "Schedule unknown": "Calendari desconegut",
        "not ready locally": "no preparada localment",
        "ready locally": "preparada localment",
        "external filing baseline stored locally": "referència externa desada localment",
        "not observed at AEAT": "no observada a l'AEAT",
        "submission observed at AEAT": "presentació observada a l'AEAT",
        "accepted by AEAT": "acceptada per l'AEAT",
        "AEAT receipt verified": "justificant AEAT verificat",
        "Across records": "Per a diversos registres",
        "Suggested": "Suggerida",
        "Resume": "Continuar",
        "Inspect": "Consultar",
        "Deadline": "Termini",
        "Date": "Data",
        "Status": "Estat",
        "Actions": "Accions",
        "Agenda": "Agenda",
        "AEAT evidence": "Evidència AEAT",
        "need review": "requereixen revisió",
        "entries": "assentaments",
        "unclassified": "sense classificar",
        "missing evidence": "sense justificant",
        "Local declaration status": "Estat local de la declaració",
        "requiring attention": "requereixen atenció",
        "no suggested actions": "sense accions suggerides",
        "no resumable declarations": "sense declaracions per continuar",
        "no upcoming filing dates": "sense dates pròximes",
        "none suggested": "cap suggerida",
        "none resumable": "cap per continuar",
        "no dates": "sense dates",
        "last observed": "darrera observació",
        "Choose a task to inspect its context.": "Trieu una tasca per consultar-ne el context.",
        "Use Up/Down to choose and Enter to confirm.": "Useu Amunt/Avall i Retorn per confirmar.",
        "No quick tasks are available from the captured local information.": (
            "No hi ha tasques ràpides a la informació local capturada."
        ),
    },
    OutputLanguage.HU: {
        "Home": "Kezdőlap",
        "due-driven candidate": "határidő-központú változat",
        "task-launcher candidate": "feladatindító változat",
        "No profile selected": "Nincs kiválasztott profil",
        "Profile locked": "Zárolt profil",
        "Active local session": "Aktív helyi munkamenet",
        "Session expired": "Lejárt munkamenet",
        "Account": "Fiók",
        "Available": "Elérhető",
        "Locked — unlock the selected profile to view this information": "Zárolt — az adatokhoz oldja fel a profilt",
        "Stale — the last local snapshot needs refresh": "Elavult — frissítse az utolsó helyi pillanatképet",
        "Not captured yet": "Még nincs lekérve",
        "Unavailable — this source cannot be read in the current session": (
            "Nem elérhető — a forrás ebben a munkamenetben nem olvasható"
        ),
        "Next actions": "Következő műveletek",
        "Declarations": "Bevallások",
        "Filing agenda": "Beadási határidők",
        "Ledger": "Nyilvántartások",
        "Messages": "Üzenetek",
        "Quick tasks": "Gyors feladatok",
        "Task detail": "Feladat részletei",
        "Declaration needs review": "A bevallást felül kell vizsgálni",
        "Ledger classification is pending": "Függő nyilvántartási besorolás",
        "Supporting evidence is missing": "Hiányzó bizonylat",
        "A declaration dependency is blocked": "A bevallás egyik függősége blokkolt",
        "Blocked work needs review": "A blokkolt munkát felül kell vizsgálni",
        "A blocker needs supporting evidence": "A blokkoláshoz bizonylat szükséges",
        "Review declaration": "Bevallás áttekintése",
        "Classify Ledger entries": "Tételek besorolása",
        "Add missing evidence": "Bizonylat hozzáadása",
        "Resolve declaration blocker": "Blokkolás feloldása",
        "Review blocked work": "Blokkolt munka áttekintése",
        "Resolve missing evidence": "Hiányzó bizonylat rendezése",
        "Draft": "Piszkozat",
        "Needs review": "Felülvizsgálandó",
        "Ready": "Kész",
        "Filed": "Beadva",
        "Discarded": "Elvetve",
        "Due": "Esedékes",
        "Overdue": "Lejárt",
        "Schedule unknown": "Ismeretlen ütemezés",
        "not ready locally": "helyben nem kész",
        "ready locally": "helyben kész",
        "external filing baseline stored locally": "külső beadási alap helyben tárolva",
        "not observed at AEAT": "az AEAT-nál nem észlelt",
        "submission observed at AEAT": "az AEAT-nál észlelt beadás",
        "accepted by AEAT": "az AEAT elfogadta",
        "AEAT receipt verified": "ellenőrzött AEAT-igazolás",
        "Across records": "Több rekordot érint",
        "Suggested": "Javasolt",
        "Resume": "Folytatás",
        "Inspect": "Megtekintés",
        "Local": "Helyi",
        "Deadline": "Határidő",
        "Date": "Dátum",
        "Status": "Állapot",
        "Actions": "Műveletek",
        "Agenda": "Határidők",
        "AEAT evidence": "AEAT-bizonyíték",
        "need review": "felülvizsgálandó",
        "entries": "tétel",
        "unclassified": "besorolatlan",
        "missing evidence": "hiányzó bizonylat",
        "Local declaration status": "Helyi bevallási állapot",
        "requiring attention": "figyelmet igényel",
        "no suggested actions": "nincs javasolt művelet",
        "no resumable declarations": "nincs folytatható bevallás",
        "no upcoming filing dates": "nincs közelgő dátum",
        "none suggested": "nincs javaslat",
        "none resumable": "nincs folytatható",
        "no dates": "nincs dátum",
        "last observed": "utoljára észlelve",
        "Choose a task to inspect its context.": "Válasszon feladatot a részletekhez.",
        "Use Up/Down to choose and Enter to confirm.": "Válasszon a Fel/Le gombbal, majd nyomjon Entert.",
        "No quick tasks are available from the captured local information.": (
            "A helyi adatokból nem érhető el gyors feladat."
        ),
    },
}


def _text(locale: OutputLanguage, value: str) -> str:
    translated = value
    for source, target in sorted(_TRANSLATIONS[locale].items(), key=lambda item: len(item[0]), reverse=True):
        translated = translated.replace(source, target)
    return translated


def _state_copy(state: HomeZoneState, locale: OutputLanguage, *, empty_copy: str | None = None) -> str:
    label = _text(locale, _AVAILABILITY_COPY[state.availability])
    if state.availability is HomeAvailability.STALE and state.observed_at is not None:
        observed = state.observed_at.strftime("%d/%m/%Y %H:%M UTC")
        return f"{label}; {_text(locale, 'last observed')} {observed}"
    if state.availability is HomeAvailability.AVAILABLE and empty_copy is not None:
        return f"{label} — {_text(locale, empty_copy)}"
    return label


def _action_cells(item: HomeNextAction, locale: OutputLanguage) -> tuple[str, str, str]:
    label = _ACTION_COPY.get(item.action.action.action_id, "Open suggested task")
    reason = _ACTION_REASON_COPY.get(item.reason_code, "Suggested by the local overview")
    if item.period is None:
        context = "Across records"
    elif item.modelo is None or item.filing_year is None:  # pragma: no cover - model validation rejects this
        raise ValueError("an addressed Home action requires Modelo, year, and period")
    else:
        context = _address(item.modelo, item.filing_year, item.period.registry_token)
    return _text(locale, reason), _text(locale, label), _text(locale, context)


def _declaration_cells(item: HomeDeclarationResume, locale: OutputLanguage) -> tuple[str, str, str]:
    return (
        _address(item.modelo, item.filing_year, item.period.registry_token),
        item.name,
        _text(locale, _DECLARATION_COPY[item.state]),
    )


def _agenda_cells(item: HomeAgendaEntry, locale: OutputLanguage) -> tuple[str, str, str]:
    return (
        item.due_on.strftime("%d/%m"),
        f"M{item.modelo} {item.period.registry_token}",
        _text(locale, _PERIOD_COPY[item.period_state]),
    )


def _evidence_copy(item: HomeAgendaEntry, locale: OutputLanguage) -> str:
    value = f"Local: {_LOCAL_COPY[item.local_filing_state]} · AEAT: {_AEAT_COPY[item.aeat_submission_state]}"
    return _text(locale, value)


class _ProjectionCandidateScreen(Screen[None]):
    """Shared projection binding and responsive-class behavior only."""

    WIDE_MINIMUM: ClassVar[int] = 120
    BINDINGS: ClassVar = [Binding("escape", "close_candidate", "", show=False)]

    def __init__(
        self,
        projection: HomeProjectionV1,
        *,
        locale: OutputLanguage | str = OutputLanguage.EN,
        restore_target: HomeCandidateTarget | None = None,
    ) -> None:
        super().__init__()
        self._projection = projection
        self._locale = OutputLanguage(locale)
        self._restore_target = restore_target
        self._selected_target: HomeCandidateTarget | None = None
        self._highlighted_target: HomeCandidateTarget | None = None
        self._targets: dict[str, HomeCandidateTarget] = {}
        self._was_closed = False

    @property
    def projection(self) -> HomeProjectionV1:
        """Return the exact immutable projection supplied by the caller."""
        return self._projection

    @property
    def selected_target(self) -> HomeCandidateTarget | None:
        """Return the last keyboard-confirmed prototype target."""
        return self._selected_target

    @property
    def highlighted_target(self) -> HomeCandidateTarget | None:
        """Return the semantic target under the keyboard cursor."""
        return self._highlighted_target

    @property
    def was_closed(self) -> bool:
        """Report whether the operator invoked the prototype return binding."""
        return self._was_closed

    def on_resize(self, event: events.Resize) -> None:
        """Switch layout classes without changing content or selection."""
        self.set_class(event.size.width >= self.WIDE_MINIMUM, "wide")
        self.set_class(event.size.width < self.WIDE_MINIMUM, "compact")

    def _remember(self, kind: HomeTargetKind, identity: str) -> str:
        self._targets[identity] = HomeCandidateTarget(kind=kind, identity=identity)
        return identity

    def _confirm(self, row_key: object) -> HomeCandidateTarget | None:
        target = self._targets.get(str(row_key))
        if target is not None:
            self._selected_target = target
        return target

    def _highlight(self, row_key: object) -> None:
        self._highlighted_target = self._targets.get(str(row_key))

    def _restore(self, tables: Iterable[DataTable[str]]) -> bool:
        target = self._restore_target
        if target is None:
            return False
        for table in tables:
            for index, row in enumerate(table.ordered_rows):
                if row.key.value == target.identity:
                    table.move_cursor(row=index)
                    self.set_focus(table)
                    self._highlighted_target = target
                    return True
        return False

    def action_close_candidate(self) -> None:
        """Return from the prototype without executing the selected target."""
        self._was_closed = True
        self.dismiss(None)


class DueDrivenHomeCandidateScreen(_ProjectionCandidateScreen):
    """Actions-first overview with declarations and a deadline/status rail."""

    CSS = """
    DueDrivenHomeCandidateScreen { layout: vertical; }
    #due-page { width: 100%; height: 1fr; }
    #due-layout, #due-main, #due-sidebar { width: 100%; height: auto; }
    #due-layout { layout: vertical; }
    DueDrivenHomeCandidateScreen.wide #due-layout { layout: horizontal; }
    DueDrivenHomeCandidateScreen.wide #due-main { width: 2fr; }
    DueDrivenHomeCandidateScreen.wide #due-sidebar { width: 1fr; }
    .candidate-panel { height: auto; margin: 0 1 1 0; padding: 0 1; border: round $primary-darken-2; }
    .candidate-heading { text-style: bold; margin-top: 1; }
    .candidate-state { color: $text-muted; }
    .candidate-table { width: 100%; height: auto; }
    """

    @override
    def compose(self) -> ComposeResult:
        projection = self.projection
        yield Static(
            _text(self._locale, "Home · due-driven candidate"),
            id="due-title",
            classes="candidate-heading",
            markup=False,
        )
        yield Static(
            f"{projection.account.profile_label or _text(self._locale, 'Account')} · "
            f"{_text(self._locale, _SESSION_COPY[projection.account.posture])}",
            id="due-session",
            markup=False,
        )
        with ContentScroll(id="due-page"), Static(id="due-layout"):
            with Static(id="due-main"):
                yield Static(_text(self._locale, "Next actions"), classes="candidate-heading", markup=False)
                yield Static(
                    _state_copy(
                        projection.actions_state,
                        self._locale,
                        empty_copy="no suggested actions" if not projection.actions else None,
                    ),
                    id="due-actions-state",
                    classes="candidate-state",
                    markup=False,
                )
                yield ContentDataTable[str](
                    id="due-actions",
                    cursor_type="row",
                    zebra_stripes=True,
                    show_header=False,
                    cell_padding=0,
                    classes="candidate-table",
                )
                yield Static(id="due-action-contexts", classes="candidate-state", markup=False)
                yield Static(_text(self._locale, "Declarations"), classes="candidate-heading", markup=False)
                yield Static(
                    _state_copy(
                        projection.declarations_state,
                        self._locale,
                        empty_copy="no resumable declarations" if not projection.declarations else None,
                    ),
                    id="due-declarations-state",
                    classes="candidate-state",
                    markup=False,
                )
                yield ContentDataTable[str](
                    id="due-declarations",
                    cursor_type="row",
                    zebra_stripes=True,
                    show_header=False,
                    cell_padding=0,
                    classes="candidate-table",
                )
            with Static(id="due-sidebar"):
                yield Static(_text(self._locale, "Filing agenda"), classes="candidate-heading", markup=False)
                yield Static(
                    _state_copy(
                        projection.agenda_state,
                        self._locale,
                        empty_copy="no upcoming filing dates" if not projection.agenda else None,
                    ),
                    id="due-agenda-state",
                    classes="candidate-state",
                    markup=False,
                )
                yield ContentDataTable[str](
                    id="due-agenda",
                    cursor_type="row",
                    zebra_stripes=True,
                    show_header=False,
                    cell_padding=0,
                    classes="candidate-table",
                )
                yield Static(id="due-agenda-rows-evidence", classes="candidate-state", markup=False)
                yield Static(id="due-evidence", classes="candidate-state", markup=False)
                yield Static(_text(self._locale, "Ledger"), classes="candidate-heading", markup=False)
                yield Static(id="due-ledger", classes="candidate-state", markup=False)
                yield Static(_text(self._locale, "Messages"), classes="candidate-heading", markup=False)
                yield Static(id="due-messages", classes="candidate-state", markup=False)

    def on_mount(self) -> None:
        """Populate the three keyboard lists from the supplied projection."""
        projection = self.projection
        actions = cast("ContentDataTable[str]", self.query_one("#due-actions", ContentDataTable))
        actions.add_column("")
        action_contexts: list[str] = []
        for item in projection.actions:
            reason, action, context = _action_cells(item, self._locale)
            actions.add_row(action, key=self._remember(HomeTargetKind.ACTION, _action_identity(item)))
            action_contexts.append(f"{action} — {reason} · {context}")
        actions.display = bool(projection.actions)
        self.query_one("#due-action-contexts", Static).update("\n".join(action_contexts))

        declarations = cast("ContentDataTable[str]", self.query_one("#due-declarations", ContentDataTable))
        declarations.add_column("")
        for item in projection.declarations:
            address, name, state = _declaration_cells(item, self._locale)
            declarations.add_row(
                f"{address} · {name} · {state}",
                key=self._remember(HomeTargetKind.DECLARATION, _declaration_identity(item)),
            )
        declarations.display = bool(projection.declarations)

        agenda = cast("ContentDataTable[str]", self.query_one("#due-agenda", ContentDataTable))
        agenda.add_column("")
        evidence_rows: list[str] = []
        for item in projection.agenda:
            due, address, state = _agenda_cells(item, self._locale)
            agenda.add_row(
                f"{due} · {address} · {state}",
                key=self._remember(HomeTargetKind.AGENDA, _agenda_identity(item)),
            )
            evidence_rows.append(f"{address} — {_evidence_copy(item, self._locale)}")
        agenda.display = bool(projection.agenda)
        self.query_one("#due-agenda-rows-evidence", Static).update("\n".join(evidence_rows))

        self.query_one("#due-evidence", Static).update(
            _text(self._locale, f"AEAT evidence: {_state_copy(projection.agenda_evidence_state, self._locale)}")
        )
        ledger = projection.ledger
        self.query_one("#due-ledger", Static).update(
            _state_copy(projection.ledger_state, self._locale)
            if ledger is None
            else _text(
                self._locale,
                f"Available — {ledger.entries} entries; {ledger.requiring_review} need review; "
                f"{ledger.unclassified} unclassified; {ledger.missing_evidence} missing evidence",
            )
        )
        messages = projection.messages_requiring_attention
        self.query_one("#due-messages", Static).update(
            _state_copy(projection.messages_state, self._locale)
            if messages is None
            else _text(self._locale, f"Available — {messages} requiring attention")
        )
        first = next((table for table in (actions, declarations, agenda) if table.row_count), None)
        if first is not None and not self._restore((actions, declarations, agenda)):
            self.set_focus(first)
            self._highlight(first.ordered_rows[0].key.value)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Track the semantic target independently of row order."""
        table = cast("DataTable[str]", event.data_table)
        if table is self.focused:
            self._highlight(event.row_key.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Record Enter against a semantic target without executing it."""
        self._confirm(event.row_key.value)


class TaskLauncherHomeCandidateScreen(_ProjectionCandidateScreen):
    """Single quick-task chooser with contextual detail and compact signals."""

    CSS = """
    TaskLauncherHomeCandidateScreen { layout: vertical; }
    #launcher-page { width: 100%; height: 1fr; }
    #launcher-layout { width: 100%; height: auto; layout: vertical; }
    TaskLauncherHomeCandidateScreen.wide #launcher-layout { layout: horizontal; }
    #launcher-chooser-panel, #launcher-detail-panel { width: 100%; height: auto; }
    TaskLauncherHomeCandidateScreen.wide #launcher-chooser-panel { width: 3fr; }
    TaskLauncherHomeCandidateScreen.wide #launcher-detail-panel { width: 2fr; }
    .candidate-panel { height: auto; margin: 0 1 1 0; padding: 0 1; border: round $primary-darken-2; }
    .candidate-heading { text-style: bold; margin-top: 1; }
    .candidate-state { color: $text-muted; }
    .candidate-table { width: 100%; height: auto; }
    """

    def __init__(
        self,
        projection: HomeProjectionV1,
        *,
        locale: OutputLanguage | str = OutputLanguage.EN,
        restore_target: HomeCandidateTarget | None = None,
    ) -> None:
        """Bind one projection and an initially empty detail catalogue."""
        super().__init__(projection, locale=locale, restore_target=restore_target)
        self._details: dict[str, str] = {}

    @override
    def compose(self) -> ComposeResult:
        projection = self.projection
        yield Static(
            _text(self._locale, "Home · task-launcher candidate"),
            id="launcher-title",
            classes="candidate-heading",
            markup=False,
        )
        yield Static(
            f"{projection.account.profile_label or _text(self._locale, 'Account')} · "
            f"{_text(self._locale, _SESSION_COPY[projection.account.posture])}",
            id="launcher-session",
            markup=False,
        )
        with ContentScroll(id="launcher-page"):
            with Static(id="launcher-layout"):
                with Static(id="launcher-chooser-panel", classes="candidate-panel"):
                    yield Static(_text(self._locale, "Quick tasks"), classes="candidate-heading", markup=False)
                    yield ContentDataTable[str](
                        id="launcher-chooser",
                        cursor_type="row",
                        zebra_stripes=True,
                        show_header=False,
                        cell_padding=0,
                        classes="candidate-table",
                    )
                    yield Static(id="launcher-empty", classes="candidate-state", markup=False)
                with Static(id="launcher-detail-panel", classes="candidate-panel"):
                    yield Static(_text(self._locale, "Task detail"), classes="candidate-heading", markup=False)
                    yield Static(
                        _text(self._locale, "Choose a task to inspect its context."),
                        id="launcher-detail",
                        markup=False,
                    )
            yield Static(id="launcher-signals", classes="candidate-state candidate-panel", markup=False)

    def on_mount(self) -> None:
        """Build one unified chooser; compact signals remain non-interactive."""
        projection = self.projection
        chooser = cast("ContentDataTable[str]", self.query_one("#launcher-chooser", ContentDataTable))
        chooser.add_column("")

        for item in projection.actions:
            identity = self._remember(HomeTargetKind.ACTION, _action_identity(item))
            reason, label, context = _action_cells(item, self._locale)
            chooser.add_row(label, key=identity)
            self._details[identity] = f"{reason}. {context}."
        for item in projection.declarations[:1]:
            identity = self._remember(HomeTargetKind.DECLARATION, _declaration_identity(item))
            address, name, state = _declaration_cells(item, self._locale)
            chooser.add_row(f"{_text(self._locale, 'Resume')} {address}", key=identity)
            self._details[identity] = _text(self._locale, f"{name}. Local declaration status: {state}.")
        for item in projection.agenda[:1]:
            identity = self._remember(HomeTargetKind.AGENDA, _agenda_identity(item))
            due, address, state = _agenda_cells(item, self._locale)
            chooser.add_row(f"{_text(self._locale, 'Inspect')} {address}", key=identity)
            self._details[identity] = _text(self._locale, f"Due {due}. {state}. {_evidence_copy(item, self._locale)}.")

        self.query_one("#launcher-empty", Static).update(
            _text(self._locale, "No quick tasks are available from the captured local information.")
            if not chooser.row_count
            else _text(self._locale, "Use Up/Down to choose and Enter to confirm.")
        )
        chooser.display = bool(chooser.row_count)
        self.query_one("#launcher-detail-panel", Static).display = bool(chooser.row_count)
        self.query_one("#launcher-signals", Static).update("\n".join(self._signal_lines()))
        if chooser.row_count and not self._restore((chooser,)):
            self.set_focus(chooser)
            self._show_detail(chooser.ordered_rows[0].key.value)
        elif self._restore_target is not None:
            self._show_detail(self._restore_target.identity)

    def _signal_lines(self) -> Iterable[str]:
        projection = self.projection
        actions = _state_copy(
            projection.actions_state,
            self._locale,
            empty_copy="none suggested" if not projection.actions else None,
        )
        declarations = _state_copy(
            projection.declarations_state,
            self._locale,
            empty_copy="none resumable" if not projection.declarations else None,
        )
        agenda = _state_copy(
            projection.agenda_state,
            self._locale,
            empty_copy="no dates" if not projection.agenda else None,
        )
        yield _text(self._locale, f"Actions: {actions}")
        yield _text(self._locale, f"Declarations: {declarations}")
        yield _text(self._locale, f"Agenda: {agenda}")
        yield _text(self._locale, f"AEAT evidence: {_state_copy(projection.agenda_evidence_state, self._locale)}")
        if projection.ledger is None:
            yield _text(self._locale, f"Ledger: {_state_copy(projection.ledger_state, self._locale)}")
        else:
            yield _text(self._locale, f"Ledger: Available — {projection.ledger.requiring_review} need review")
        if projection.messages_requiring_attention is None:
            yield _text(self._locale, f"Messages: {_state_copy(projection.messages_state, self._locale)}")
        else:
            yield _text(
                self._locale,
                f"Messages: Available — {projection.messages_requiring_attention} requiring attention",
            )

    def _show_detail(self, row_key: object) -> None:
        detail = self._details.get(str(row_key))
        if detail is not None:
            widget = self.query_one("#launcher-detail", Static)
            widget.update(detail)
            widget.scroll_visible(animate=False)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Keep detail synchronized with arrow-key selection."""
        table = cast("DataTable[str]", event.data_table)
        if table is self.focused:
            self._highlight(event.row_key.value)
            self._show_detail(event.row_key.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Record Enter against a semantic target without executing it."""
        target = self._confirm(event.row_key.value)
        if target is not None:
            self._show_detail(target.identity)


__all__ = [
    "DueDrivenHomeCandidateScreen",
    "HomeCandidateTarget",
    "TaskLauncherHomeCandidateScreen",
]
