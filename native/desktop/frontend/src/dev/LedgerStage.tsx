import {
  useCallback,
  useReducer,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
} from "react";
import { LedgerPage, type LedgerMemory } from "@/components/ledger/LedgerPage";
import {
  DEFAULT_SORT,
  NO_FILTERS,
  readinessSets,
} from "@/components/ledger/movements/movementsModel";
import type { MovementsMemory } from "@/components/ledger/movements/useMovementsView";
import type { PaneControl } from "@/components/PaneHeader";
import { DEFAULT_LAYOUT, type LedgerView } from "../shell/layout";
import type { LedgerPort, LedgerRow } from "../shell/ledger";
import type { LedgerPeriod } from "../shell/ledgerGrammar";
import {
  readinessSnapshot,
  shownRows,
  useLedgerWindow,
  type LedgerWindow,
  type Readiness,
} from "../shell/ledgerWindow";
import { useLedgerReadiness } from "../shell/ledgerReadiness";
import { useLedgerYears } from "../shell/ledgerYears";
import {
  EMPTY_STAGE,
  reduceStage,
  type StageEvent,
  type StageState,
} from "../shell/ledgerStage";
import { useStrings } from "../shell/strings";
import { fixtureLedger, type FixtureMovement } from "./fixtures/ledger";
import { ledgerFixture, type LedgerShape } from "./ledgerFixture";

// What the Ledger stories share: the scenario's ledger port, made once for a
// story, the page laid out the way the window lays it out with its view held
// in the story as the window holds it in its layout, and the reads the
// page's own parts are given, made through the same hooks.

const noop = () => undefined;

/** Whose ledger the stories show. */
export const STORY_READER = "synthetic";

/** The quarter the synthetic ledger's movements fall in. */
export const STORY_PERIOD: LedgerPeriod = { year: 2026, code: "4T" };

/** The scenario's ledger port for one story, made on its first render. */
export function useLedgerPort(
  shape: LedgerShape = "fixture",
  signedIn = true,
): LedgerPort {
  const port = useRef<LedgerPort | null>(null);
  port.current ??= ledgerFixture({
    say: noop,
    wait: async () => undefined,
    signedIn: () => signedIn,
    shape,
  });
  return port.current;
}

/** The page's view as the window's layout starts it, with a story's changes
 * over it. */
export function ledgerViewOf(changes: Partial<LedgerView> = {}): LedgerView {
  return { ...DEFAULT_LAYOUT.ledgerView, ...changes };
}

/** The ids of the synthetic ledger's movements that `pick` takes, in the
 * order the ledger holds them. The port's ledger is made from the same seed,
 * so the ids are its own. */
export function storyMovementIds(
  pick: (movement: FixtureMovement) => boolean,
  count = Infinity,
  /** The movements' dates start with this; the fourth quarter by default. */
  dates: string | readonly string[] = ["2026-10", "2026-11", "2026-12"],
): string[] {
  const starts = typeof dates === "string" ? [dates] : dates;
  return fixtureLedger()
    .movements.filter(
      (movement) =>
        starts.some((start) => movement.transaction.date.startsWith(start)) &&
        pick(movement),
    )
    .slice(0, count)
    .map((movement) => movement.transaction.transaction_id);
}

/** What the movements section keeps of itself, with a story's changes over
 * how the person starts. */
export function movementsMemoryOf(
  changes: Partial<MovementsMemory> = {},
): MovementsMemory {
  return {
    filters: NO_FILTERS,
    search: "",
    sort: DEFAULT_SORT,
    collapsed: [],
    selection: [],
    ...changes,
  };
}

/** The pane controls the window gives the page. */
export function useStoryControls(): PaneControl[] {
  const t = useStrings();
  return [
    {
      id: "maximize",
      icon: "maximize",
      label: t("desktop.ledger.maximize"),
      run: noop,
    },
    {
      id: "close",
      icon: "close",
      label: t("desktop.ledger.close"),
      run: noop,
    },
  ];
}

/** The Ledger page over the scenario's ledger, as the window mounts it. */
export function LedgerStage({
  shape = "fixture",
  signedOut = false,
  view: initial,
  period = STORY_PERIOD,
  movements,
  locale,
}: {
  shape?: LedgerShape;
  signedOut?: boolean;
  view?: Partial<LedgerView>;
  /** The period the page opens on; null shows every period. */
  period?: LedgerPeriod | null;
  /** How the person has been looking at the movements. */
  movements?: Partial<MovementsMemory>;
  locale: string;
}) {
  const t = useStrings();
  const port = useLedgerPort(shape, !signedOut);
  const page = useRef<HTMLElement>(null);
  const memory = useRef<LedgerMemory>({
    period,
    ...(movements ? { movements: movementsMemoryOf(movements) } : {}),
  });
  const [view, setView] = useState(() => ledgerViewOf(initial));
  const changeView = useCallback(
    (update: (current: LedgerView) => LedgerView) => setView(update),
    [],
  );
  const controls = useStoryControls();
  const withheld: ReactNode = (
    <p className="p-6 text-sm text-muted-foreground">
      {t("desktop.ledger.signed_out")}
    </p>
  );
  return (
    <div className="flex h-full min-h-0 flex-col">
      <LedgerPage
        port={port}
        reader={signedOut ? null : STORY_READER}
        withheld={withheld}
        locale={locale}
        shown
        page={page}
        view={view}
        onViewChange={changeView}
        memory={memory}
        contribute={noop}
        copy={async () => undefined}
        pane={{
          title: t("desktop.ledger.title"),
          onToggleMaximize: noop,
          controls,
        }}
      />
    </div>
  );
}

/** What the page reads of a period for its parts: the movements, the years,
 * and the readiness check, as the page makes them. */
export function useLedgerRead(
  port: LedgerPort,
  period: LedgerPeriod | null = STORY_PERIOD,
): {
  window: LedgerWindow | null;
  reread: () => void;
  rows: LedgerRow[] | null;
  generation: number | null;
  years: number[] | null;
  readiness: Readiness;
  recheck: () => void;
  sets: ReturnType<typeof readinessSets>;
} {
  const { window: read, reread } = useLedgerWindow(
    port,
    STORY_READER,
    period,
    true,
  );
  const rows = read ? (shownRows(read)?.rows ?? null) : null;
  const generation = read?.phase === "ready" ? read.generation : null;
  const { years } = useLedgerYears(port, STORY_READER, true);
  const { readiness, recheck } = useLedgerReadiness(
    port,
    STORY_READER,
    period,
    generation,
  );
  const sets = readinessSets(rows ?? [], readinessSnapshot(readiness));
  return {
    window: read,
    reread,
    rows,
    generation,
    years,
    readiness,
    recheck,
    sets,
  };
}

/** What the page stages, held as the page holds it. */
export function useStoryStage(): {
  stage: StageState;
  onStage: Dispatch<StageEvent>;
} {
  const [stage, onStage] = useReducer(reduceStage, EMPTY_STAGE);
  return { stage, onStage };
}
