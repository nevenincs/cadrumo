import {
  Fragment,
  memo,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { flushSync } from "react-dom";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import {
  Empty,
  EmptyDescription,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import {
  deadlineDistance,
  evaluatedDay,
  evaluatedLabel,
  evaluatedWord,
  isoDay as day,
  localDay,
  type CalendarState,
} from "../shell/calendar";
import { entryKey } from "../shell/calendarGrid";
import { useMetric } from "../shell/metrics";
import { useStrings } from "../shell/strings";
import type {
  CalendarEntry,
  CalendarEvent,
  CalendarUserState,
} from "../shell/views";
import { CalendarMonths } from "./CalendarMonths";
import { EVENT_MARK, STATE_MARK } from "./calendarMarks";

const STATE_TONE: Record<
  CalendarUserState,
  "neutral" | "danger" | "success" | "warning"
> = { due: "neutral", late: "danger", filed: "success", unknown: "warning" };

// What needs the person first comes first.
const STATE_ORDER: readonly CalendarUserState[] = [
  "late",
  "due",
  "unknown",
  "filed",
];

const DAY_MS = 86_400_000;

/** A reader's place in a face: what is at the top of their view, by its
 * month or its obligation, and how far under the head it sits; or that
 * they are at the very start. */
type Place = { key: string; top: number; start: boolean };

/**
 * What the calendar keeps of a reader's use of it, held by whoever shows
 * the page so that it outlives the page being put away: the face, the
 * choice, the crowded months asked for whole, and the place in each face.
 */
export type CalendarMemory = {
  view?: "months" | "list";
  selected?: string | null;
  asked?: ReadonlySet<string>;
  months?: Place | null;
  list?: Place | null;
  /** Whether the chosen obligation was in view when the reader last moved. */
  chosenSeen?: boolean;
};

const markKey = (mark: HTMLElement) =>
  mark.dataset.month ?? mark.dataset.entry ?? "today";

// The formats of a language, made once: a row needs four and there are
// many rows.
const FORMATS = new Map<string, ReturnType<typeof makeFormats>>();
const makeFormats = (locale: string) => ({
  short: new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }),
  full: new Intl.DateTimeFormat(locale, { dateStyle: "full" }),
  weekday: new Intl.DateTimeFormat(locale, { weekday: "short" }),
  relative: new Intl.RelativeTimeFormat(locale, { numeric: "auto" }),
});
function formatsFor(locale: string) {
  let formats = FORMATS.get(locale);
  if (!formats) FORMATS.set(locale, (formats = makeFormats(locale)));
  return formats;
}

// A row is drawn again only when it changes: choosing one obligation does
// not redraw the others.
const Entry = memo(function Entry({
  entry,
  locale,
  selected,
  onSelect,
  onOpen,
}: {
  entry: CalendarEntry;
  locale: string;
  /** Chosen, here or in the months beside the list. */
  selected: boolean;
  onSelect: (key: string) => void;
  onOpen?: (entry: CalendarEntry) => void;
}) {
  const t = useStrings();
  const closes = day(entry.adjusted_closes_on);
  const { short, full, weekday, relative: distance } = formatsFor(locale);
  // How far the binding date is from the day the product evaluated: the
  // product's own count where it gives one.
  const away =
    entry.days_overdue !== null
      ? -entry.days_overdue
      : Math.round(
          (closes.getTime() - day(entry.evaluated_on).getTime()) / DAY_MS,
        );
  // A filed obligation has no distance left to say.
  const { value, unit } = deadlineDistance(away, entry.days_overdue !== null);
  const relative =
    entry.user_state === "filed" ? null : distance.format(value, unit);
  const name = t("desktop.calendar.modelo", { modelo: entry.modelo });
  const notes = [
    t(`desktop.calendar.local.${entry.local_filing_state}`),
    t(`desktop.calendar.aeat.${entry.aeat_submission_state}`),
    entry.adjusted_closes_on !== entry.closes_on
      ? t("desktop.calendar.moved", {
          date: short.format(day(entry.closes_on)),
        })
      : null,
    entry.payment_cutoff_on
      ? t("desktop.calendar.payment_cutoff", {
          date: short.format(day(entry.payment_cutoff_on)),
        })
      : null,
  ].filter((note): note is string => note !== null);
  return (
    <li
      data-entry={entryKey(entry)}
      aria-current={selected || undefined}
      // The chosen row carries a bar as well as a surface, as a chosen item
      // does everywhere in the window.
      className="grid scroll-mt-[calc(var(--calendar-head)+--spacing(8))] grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 border-b border-l-2 border-l-transparent px-4 py-2 hover:bg-accent aria-[current=true]:border-l-ring aria-[current=true]:bg-selected forced-colors:border-l-[Canvas] forced-colors:aria-[current=true]:border-l-[Highlight]"
    >
      <time
        dateTime={entry.adjusted_closes_on}
        className="grid w-10 justify-items-center"
      >
        {/* The eye has the month in the heading above; read aloud, a day
            and a weekday alone are not a date, so the whole date is said. */}
        <span className="sr-only">{full.format(closes)}</span>
        <span
          aria-hidden="true"
          className="text-md leading-tight font-semibold tabular-nums"
        >
          {closes.getDate()}
        </span>
        <span aria-hidden="true" className="text-xs text-muted-foreground">
          {weekday.format(closes)}
        </span>
      </time>
      <div className="grid min-w-0 gap-0.5">
        {/* The row's name is what chooses it: the same obligation is then
            shown among the months. */}
        <button
          type="button"
          aria-pressed={selected}
          className="flex min-h-control-xs cursor-pointer flex-wrap items-center gap-x-2 justify-self-start rounded-sm text-left hover:underline"
          onClick={() => onSelect(entryKey(entry))}
        >
          <span className="font-medium">{name}</span>
          <span className="text-muted-foreground">{entry.period}</span>
        </button>
        <span className="text-sm text-muted-foreground">
          {notes.join(" · ")}
        </span>
        {/* In a narrow pane the distance moves under the notes: it is what
            the person came for, and is never the thing left out. */}
        {relative && (
          <span className="calendar-distance text-sm text-muted-foreground @md:hidden">
            {relative}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span className="grid justify-items-end gap-0.5">
          <Badge variant={STATE_TONE[entry.user_state]}>
            {t(`desktop.calendar.state.${entry.user_state}`)}
          </Badge>
          {relative && (
            <span className="calendar-distance text-xs text-muted-foreground @max-md:hidden">
              {relative}
            </span>
          )}
        </span>
        {onOpen && (
          <IconButton
            label={t("desktop.calendar.open_tui")}
            accessibleName={`${t("desktop.calendar.open_tui")}: ${name} ${entry.period}`}
            side="left"
            onClick={() => onOpen(entry)}
          >
            <Icon name="arrow" />
          </IconButton>
        )}
      </div>
    </li>
  );
});

/**
 * Where the past ends: a line across the list at the day the product worked
 * the states out for, so what is behind and what is ahead are told apart at
 * a glance. It is said in the language's own word for today where that day
 * is today here; a calendar worked out for another day says the day alone.
 */
function TodayMark({
  on,
  today,
  locale,
}: {
  on: string;
  /** The local day. */
  today: string;
  locale: string;
}) {
  const label = evaluatedLabel(on, today, locale);
  return (
    <div
      role="separator"
      aria-label={label}
      className="calendar-today flex items-center gap-2 px-4 py-1.5 text-xs font-semibold text-brand"
    >
      <span aria-hidden="true">{label}</span>
      <span aria-hidden="true" className="h-px flex-1 bg-current opacity-40" />
    </div>
  );
}

/**
 * The filing calendar: every obligation in a range of dates, by month, with
 * the product's own reading of where each stands. It keeps apart what the
 * product keeps apart: the local filing work, what has been seen of the tax
 * agency, and what could not be determined at all.
 *
 * The page is one region that scrolls and can hold focus, so the keyboard
 * scrolls it from wherever focus is inside. A control that held focus and
 * has gone, because the read it asked for answered or the sign-in ended,
 * leaves focus on the page rather than on nothing.
 */
export function FilingCalendarView({
  state,
  withheld,
  attempt = 0,
  locale,
  today: localToday,
  defaultView = "months",
  memory,
  refreshing = false,
  page,
  onRefresh,
  onOpen,
}: {
  state: CalendarState;
  /** What stands in the page while the account withholds the calendar: the
   * account's own account of why, and the ways on. */
  withheld?: ReactNode;
  /** Which read this is. A failure is announced again when a new read
   * fails the same way. */
  attempt?: number;
  /** The chrome language, for dates. */
  locale: string;
  /** The local day, as an ISO date, from whoever keeps it current. The
   * calendar's mark is called today only where its day is this one. */
  today?: string;
  /** The face a page too narrow for both shows first. */
  defaultView?: "months" | "list";
  /** Where the reader's use of the page is kept while it is away. Left
   * out, the page keeps it only for as long as it is shown. */
  memory?: RefObject<CalendarMemory>;
  /** A newer read is in flight over what is shown. */
  refreshing?: boolean;
  /** The page's own element, for whoever sends focus to it. */
  page?: RefObject<HTMLElement | null>;
  onRefresh: () => void;
  /** Take the person to where this obligation is worked on. Left out where
   * the window cannot: no row then offers a way it does not have. */
  onOpen?: (entry: CalendarEntry) => void;
}) {
  const t = useStrings();
  const heading = useId();
  const own = useRef<HTMLElement>(null);
  const root = page ?? own;
  const calendar = state.kind === "ready" ? state.calendar : null;

  // The calendar has two faces that complete each other: the months, where
  // each obligation is drawn across the days its window is open, and the
  // list, which says where each stands. A wide page shows both side by
  // side; a narrower one shows one, the months first, with a switch.
  //
  // What the reader has made of it is kept by whoever shows the page, so
  // that putting the page away and bringing it back loses none of it: the
  // face, the choice, the months asked for whole, and the place in each face.
  const ownMemory = useRef<CalendarMemory>({});
  const remembered = memory ?? ownMemory;
  const [view, setViewNow] = useState<"months" | "list">(
    () => remembered.current.view ?? defaultView,
  );
  const setView = (next: "months" | "list") => {
    remembered.current.view = next;
    setViewNow(next);
  };
  const [asked, setAsked] = useState<ReadonlySet<string>>(
    () => remembered.current.asked ?? new Set(),
  );
  const onAsked = useCallback(
    (month: string, whole: boolean) =>
      setAsked((held) => {
        const next = new Set(held);
        if (whole) next.add(month);
        else next.delete(month);
        remembered.current.asked = next;
        return next;
      }),
    [remembered],
  );
  const evaluatedOn = calendar ? evaluatedDay(calendar) : null;
  const here = localToday ?? localDay();
  const splitAt = useMetric("--calendar-split", 896);
  const tallAt = useMetric("--calendar-tall", 352);
  // Only what changes the drawing is state: whether there is room for both
  // faces, and whether the page is tall enough for its whole head to stay.
  // The sizes themselves go to the page's styles as they are measured, and
  // draw nothing again.
  const [room, setRoom] = useState({ wide: false, tall: true });
  const wide = room.wide;
  const widthWas = useRef<number | null>(null);
  const wideNow = useRef(false);
  // The row of controls stays at the top while the page scrolls under it.
  const head = useRef<HTMLDivElement>(null);
  const bar = useRef<HTMLDivElement>(null);
  const aside = useRef<HTMLDivElement>(null);
  // How much of the page's top the head keeps: all of it, or its controls.
  const kept = useCallback(
    () => head.current?.offsetHeight || bar.current?.offsetHeight || 0,
    [],
  );

  // The reader's place in each face: the month, or the row of the list, at
  // the top of their view and how far under the head it sits, or that they
  // are at the very start. A face is put back on its place whenever it is
  // laid out anew. Measured from under the head, because the head's own
  // height changes with the page's width.
  const place = useRef<{ months: Place | null; list: Place | null }>({
    months: null,
    list: null,
  });
  // The scroll position this page last set by itself, per scroller: the
  // scroll event that reports it is not the reader's, and is not taken for
  // a new place. Taken for one, a place would drift a little at each layout.
  const ours = useRef(new WeakMap<Element, number>());
  // Whether the chosen obligation was in view among the months when the
  // reader last moved: if so it is kept in view when they are laid out anew.
  const chosenSeen = useRef(false);

  /** Where the months, or the list, are scrolled and what stays above them. */
  const frame = useCallback(
    (face: "months" | "list") => {
      const el = root.current;
      if (!el) return null;
      const inAside = face === "list" && wideNow.current;
      const scroller = inAside ? aside.current : el;
      if (!scroller || !el.querySelector(`.calendar-${face}`)) return null;
      // The list keeps a month's name above its rows as well.
      const name =
        face === "list"
          ? (el.querySelector<HTMLElement>(".calendar-list h2")?.offsetHeight ??
            0)
          : 0;
      return {
        scroller,
        under:
          scroller.getBoundingClientRect().top + (inAside ? 0 : kept()) + name,
        marks: [
          ...el.querySelectorAll<HTMLElement>(
            face === "months"
              ? ".calendar-month"
              : ".calendar-list :is(li[data-entry], .calendar-today)",
          ),
        ],
      };
    },
    [root, kept],
  );
  const scrollTo = useCallback((scroller: HTMLElement, top: number) => {
    scroller.scrollTop = top;
    ours.current.set(scroller, scroller.scrollTop);
  }, []);
  const remember = useCallback(
    (face: "months" | "list") => {
      const at = frame(face);
      if (!at) return;
      let on: Place | null = null;
      if (at.scroller.scrollTop <= 0) on = { key: "", top: 0, start: true };
      else {
        // The row at the top of the view: the first that reaches below what
        // stays at the top, whether it begins there or far above. A month
        // drawn whole can be taller than the page, and the reader inside it
        // is on that month, not on the next one down.
        let row: number | null = null;
        const current = evaluatedOn?.slice(0, 7);
        for (const mark of at.marks) {
          const box = mark.getBoundingClientRect();
          if (row !== null && box.top > row + 1) break;
          if (row === null && box.bottom <= at.under + 1) continue;
          // Of the months of that row, the current one where it is among
          // them: a view left where it opened stays on the current month
          // however its row is made up next. Otherwise the row's first.
          if (row === null || (face === "months" && markKey(mark) === current))
            on = { key: markKey(mark), top: box.top - at.under, start: false };
          row ??= box.top;
        }
      }
      if (!on) return;
      place.current[face] = on;
      remembered.current[face] = on;
    },
    [frame, evaluatedOn, remembered],
  );
  /** Puts a face back on the reader's place. False where it has none. */
  const restore = useCallback(
    (face: "months" | "list") => {
      const at = frame(face);
      const on = place.current[face];
      if (!at || !on) return false;
      if (on.start) {
        scrollTo(at.scroller, 0);
        return true;
      }
      const mark = at.marks.find((candidate) => markKey(candidate) === on.key);
      if (!mark) return false;
      scrollTo(
        at.scroller,
        at.scroller.scrollTop +
          mark.getBoundingClientRect().top -
          at.under -
          on.top,
      );
      return true;
    },
    [frame, scrollTo],
  );

  const shown = calendar !== null;
  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const fit = () => {
      wideNow.current = el.clientWidth >= splitAt;
      setRoom((held) => {
        const next = {
          wide: el.clientWidth >= splitAt,
          tall: el.clientHeight >= tallAt,
        };
        return held.wide === next.wide && held.tall === next.tall ? held : next;
      });
    };
    const measure = () => {
      el.style.setProperty("--calendar-head", `${kept()}px`);
      el.style.setProperty("--calendar-height", `${el.clientHeight}px`);
    };
    const resized = () => {
      measure();
      const width = el.clientWidth;
      const changed = widthWas.current !== null && width !== widthWas.current;
      widthWas.current = width;
      // A change of face is drawn now, before the browser paints: a page
      // that has just become wide enough for both faces is never shown for
      // a moment with one, laid out for the other. The faces it shows are
      // then placed by their own rule. How much of the head stays can wait
      // for the next frame, and has to: drawn here it would resize what is
      // being observed, inside the observation.
      if (width >= splitAt !== wideNow.current) {
        flushSync(fit);
        measure();
        return;
      }
      fit();
      // The same faces at another width: their rows are made up anew, and
      // each is put back on the reader's place, here, before the browser
      // reports the scroll that the new layout caused.
      if (changed) {
        restore("months");
        restore("list");
      }
    };
    measure();
    fit();
    widthWas.current = el.clientWidth;
    const observer = new ResizeObserver(resized);
    observer.observe(el);
    if (head.current) observer.observe(head.current);
    if (bar.current) observer.observe(bar.current);
    return () => observer.disconnect();
  }, [root, splitAt, tallAt, shown, kept, restore]);

  // The obligation chosen, by Modelo and period, and which face it was
  // chosen in: the other face brings it into view.
  const [selected, setSelected] = useState<string | null>(
    () => remembered.current.selected ?? null,
  );
  const chosenIn = useRef<"months" | "list">("months");
  const select = useCallback(
    (key: string, from: "months" | "list") => {
      chosenIn.current = from;
      setSelected((held) => {
        const next = held === key ? null : key;
        remembered.current.selected = next;
        return next;
      });
    },
    [remembered],
  );
  // Another memory is another profile's, or the same one signed in anew:
  // nothing made of the page before is carried into it.
  const [memoryWas, setMemoryWas] = useState(remembered);
  if (memoryWas !== remembered) {
    setMemoryWas(remembered);
    setViewNow(defaultView);
    setAsked(new Set());
    setSelected(null);
  }
  const selectInList = useCallback(
    (key: string) => select(key, "list"),
    [select],
  );
  const selectInMonths = useCallback(
    (key: string) => select(key, "months"),
    [select],
  );
  /** A scroll of one of the page's scrollers, as the reader's or not. */
  const scrolled = (scroller: HTMLElement, faces: ("months" | "list")[]) => {
    const el = root.current;
    // Reported while the page is a width its faces have not yet been put
    // back for: the new layout's doing, not the reader's.
    if (!el || el.clientWidth !== widthWas.current) return;
    // Reported for a position this page set by itself.
    const set = ours.current.get(scroller);
    ours.current.delete(scroller);
    if (set !== undefined && Math.abs(set - scroller.scrollTop) < 1) return;
    for (const face of faces) remember(face);
    const chosen =
      selected === null
        ? null
        : el.querySelector(
            `.calendar-months [data-entry="${CSS.escape(selected)}"]`,
          );
    if (chosen) {
      const box = chosen.getBoundingClientRect();
      const page = el.getBoundingClientRect();
      chosenSeen.current =
        box.bottom > page.top + kept() && box.top < page.bottom;
      remembered.current.chosenSeen = chosenSeen.current;
    }
  };

  // A face that comes to be shown opens on where the person is. One that
  // was already shown, beside or without the other, and is only laid out
  // anew goes back to the reader's place, with what they chose kept in
  // view if it was. One shown afresh opens on what is chosen, or else on
  // the place it was left at, or else where the calendar stands: the month
  // of the day the product evaluated, and the list's mark for today.
  const placed = useRef<string | null>(null);
  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    if (evaluatedOn === null) {
      // Nothing is shown: a calendar read anew opens as a first one does.
      placed.current = null;
      place.current = { months: null, list: null };
      remembered.current.months = null;
      remembered.current.list = null;
      return;
    }
    // The width was measured in this same pass and the drawing may not have
    // caught up with it: the faces are placed when it has, so that a page
    // brought back wide places both of its faces as brought back.
    if (wideNow.current !== wide) return;
    const face = wide ? "both" : view;
    if (placed.current === face) return;
    if (
      !el.querySelector(face === "list" ? ".calendar-list" : ".calendar-months")
    )
      return;
    const before = placed.current;
    // A page brought back has the places it was put away with.
    if (before === null) {
      place.current = {
        months: remembered.current.months ?? null,
        list: remembered.current.list ?? null,
      };
      chosenSeen.current = remembered.current.chosenSeen ?? false;
    }
    placed.current = face;
    const chosen = (within: string) =>
      selected === null
        ? null
        : el.querySelector<HTMLElement>(
            `${within} [data-entry="${CSS.escape(selected)}"]`,
          );
    // Its top to just under what stays at the top, with some air.
    const bring = (
      of: "months" | "list",
      to: Element | null,
      air: number,
    ): boolean => {
      const at = frame(of);
      if (!at || !to) return false;
      scrollTo(
        at.scroller,
        at.scroller.scrollTop + to.getBoundingClientRect().top - at.under - air,
      );
      // A place the page chose is the reader's until they move.
      remember(of);
      return true;
    };
    const had = (of: "months" | "list") =>
      before === of ||
      before === "both" ||
      (before === null && place.current[of] !== null);
    if (face !== "list") {
      const window = chosen(".calendar-months");
      const stands = () =>
        bring(
          "months",
          el.querySelector(`[data-month="${evaluatedOn.slice(0, 7)}"]`),
          12,
        );
      if (had("months")) {
        if (!restore("months")) stands();
        if (window && chosenSeen.current) {
          window.scrollIntoView({ block: "nearest" });
          ours.current.set(el, el.scrollTop);
        }
      } else if (!(window && bring("months", window, 48)) && !restore("months"))
        stands();
    }
    if (face !== "months") {
      const row = chosen(".calendar-list");
      const stands = () =>
        bring("list", el.querySelector(".calendar-list .calendar-today"), 0);
      if (had("list")) {
        if (!restore("list")) stands();
      } else if (!(row && bring("list", row, 0)) && !restore("list")) stands();
    }
  }, [
    evaluatedOn,
    root,
    room,
    view,
    wide,
    selected,
    frame,
    scrollTo,
    remember,
    restore,
    remembered,
  ]);
  // Back to where the calendar stands: the month of the evaluated day among
  // the months, and its mark in the list, each where a face first opens.
  const toToday = () => {
    const el = root.current;
    if (!el || evaluatedOn === null) return;
    for (const [face, to, air] of [
      [
        "months",
        el.querySelector(
          `.calendar-months [data-month="${evaluatedOn.slice(0, 7)}"]`,
        ),
        12,
      ],
      ["list", el.querySelector(".calendar-list .calendar-today"), 0],
    ] as const) {
      const at = frame(face);
      if (!at || !to) continue;
      at.scroller.scrollTop += to.getBoundingClientRect().top - at.under - air;
      remember(face);
    }
  };
  // Just chosen, an obligation is in view: it was pressed, or is brought
  // into view below. Whether it still is, is the reader's scrolling to say.
  const selectedWas = useRef(selected);
  useEffect(() => {
    // Only when the choice changes: a page brought back with its choice
    // has what was last said of it.
    if (selectedWas.current === selected) return;
    selectedWas.current = selected;
    chosenSeen.current = selected !== null;
    remembered.current.chosenSeen = chosenSeen.current;
  }, [selected, remembered]);
  useEffect(() => {
    if (selected === null) return;
    const other = chosenIn.current === "months" ? "list" : "months";
    root.current
      ?.querySelector(
        `.calendar-${other} [data-entry="${CSS.escape(selected)}"]`,
      )
      ?.scrollIntoView({ block: "nearest" });
  }, [selected, root]);

  // Whether the last thing focused or pressed was in the page. Removing a
  // focused control reports nothing, so this is how its loss is known.
  const within = useRef(false);
  useEffect(() => {
    const track = (event: Event) => {
      within.current =
        event.target instanceof Node &&
        (root.current?.contains(event.target) ?? false);
    };
    document.addEventListener("focusin", track);
    document.addEventListener("pointerdown", track);
    return () => {
      document.removeEventListener("focusin", track);
      document.removeEventListener("pointerdown", track);
    };
  }, [root]);
  useEffect(() => {
    if (within.current && document.activeElement === document.body)
      root.current?.focus();
  });

  const months = useMemo(() => {
    const month = new Intl.DateTimeFormat(locale, {
      month: "long",
      year: "numeric",
    });
    const groups = new Map<
      string,
      {
        title: string;
        entries: CalendarEntry[];
        events: CalendarEvent[];
        ahead: number;
      }
    >();
    for (const entry of [...(calendar?.entries ?? [])].sort(
      (a, b) =>
        a.adjusted_closes_on.localeCompare(b.adjusted_closes_on) ||
        a.modelo.localeCompare(b.modelo),
    )) {
      const key = entry.adjusted_closes_on.slice(0, 7);
      const group = groups.get(key) ?? {
        title: month.format(day(entry.adjusted_closes_on)),
        entries: [],
        events: [],
        ahead: 0,
      };
      // How many of the month's obligations bind on or after the day the
      // product evaluated: they are listed last, being sorted by date.
      if (evaluatedOn !== null && entry.adjusted_closes_on >= evaluatedOn)
        group.ahead += 1;
      group.entries.push(entry);
      groups.set(key, group);
    }
    // What was observed, in the month it happened, whether or not anything
    // falls due in that month.
    for (const event of [...(calendar?.events ?? [])].sort((a, b) =>
      a.event_date.localeCompare(b.event_date),
    )) {
      const key = event.event_date.slice(0, 7);
      const group = groups.get(key) ?? {
        title: month.format(day(event.event_date)),
        entries: [],
        events: [],
        ahead: 0,
      };
      group.events.push(event);
      groups.set(key, group);
    }
    return [...groups].sort(([a], [b]) => a.localeCompare(b));
  }, [calendar, locale, evaluatedOn]);
  // The day the product worked the states out for, and the month in which
  // the first obligation still ahead falls: the mark for today stands just
  // before that obligation, or after the last one when none is ahead.
  const today = evaluatedOn;
  const turning = months.find(([, month]) => month.ahead > 0)?.[0] ?? null;

  let body: ReactNode;
  if (state.kind === "loading") {
    body = (
      <Empty role="status">
        <Spinner />
        <EmptyDescription>{t("desktop.calendar.loading")}</EmptyDescription>
      </Empty>
    );
  } else if (state.kind === "withheld") {
    body = withheld ?? (
      <Empty>
        <EmptyMedia>
          <Icon name="lock" />
        </EmptyMedia>
        <div className="grid gap-1">
          <EmptyTitle>{t("desktop.account.signed_out")}</EmptyTitle>
          <EmptyDescription>
            {t("desktop.calendar.signed_out")}
          </EmptyDescription>
        </div>
      </Empty>
    );
  } else if (state.kind === "failed") {
    body = (
      <Empty>
        <EmptyMedia>
          <Icon name="alert" />
        </EmptyMedia>
        {/* The sentence is the alert, made anew for each read that fails,
            so a second failure is heard. The button beside it stays as it
            is, and keeps the keyboard. */}
        <EmptyDescription key={attempt} role="alert">
          {t("desktop.calendar.failed", { code: state.code })}
        </EmptyDescription>
        <Button variant="outline" pending={refreshing} onClick={onRefresh}>
          {t("desktop.calendar.refresh")}
        </Button>
      </Empty>
    );
  } else {
    const { warnings, coverage, generated_at } = state.calendar;
    const asOf = generated_at
      ? new Intl.DateTimeFormat(locale, {
          dateStyle: "medium",
          timeStyle: "short",
        }).format(new Date(generated_at))
      : "—";
    // How the range stands, in the product's own four readings: counted,
    // never combined into a verdict.
    const standing = STATE_ORDER.map(
      (kind) =>
        [
          kind,
          state.calendar.entries.filter((entry) => entry.user_state === kind)
            .length,
        ] as const,
    ).filter(([, count]) => count > 0);
    const short = new Intl.DateTimeFormat(locale, {
      day: "numeric",
      month: "short",
    });
    const nothing = months.length === 0;
    const observedKinds = (["filing", "message"] as const).filter((kind) =>
      state.calendar.events.some((event) => event.event_type === kind),
    );
    // What the page is made from, and what it is not.
    const provenance = (
      <p className="text-sm text-muted-foreground">
        {t("desktop.calendar.as_of", { date: asOf })}
      </p>
    );
    const list = (
      <div className="calendar-list @container">
        {months.map(([key, month]) => (
          <section key={key} aria-labelledby={`${heading}-${key}`}>
            {/* Before the month's heading where the whole month is ahead. */}
            {today &&
              key === turning &&
              month.ahead === month.entries.length && (
                <TodayMark on={today} today={here} locale={locale} />
              )}
            <h2
              id={`${heading}-${key}`}
              className={cn(
                "sticky top-(--calendar-head) z-(--layer-separator) border-b bg-background px-4 pt-3 pb-1.5",
                "text-xs font-semibold tracking-wider text-muted-foreground uppercase",
              )}
            >
              {month.title}
            </h2>
            {/* Within the month where today falls between its dates: the
                month is then two lists with the mark between them. */}
            {(today && key === turning && month.ahead < month.entries.length
              ? [
                  month.entries.slice(0, month.entries.length - month.ahead),
                  month.entries.slice(month.entries.length - month.ahead),
                ]
              : [month.entries]
            ).map((entries, part) => (
              <Fragment key={part}>
                {part === 1 && today && (
                  <TodayMark on={today} today={here} locale={locale} />
                )}
                {entries.length > 0 && (
                  <ul>
                    {entries.map((entry) => (
                      <Entry
                        key={entryKey(entry)}
                        entry={entry}
                        locale={locale}
                        selected={selected === entryKey(entry)}
                        onSelect={selectInList}
                        onOpen={onOpen}
                      />
                    ))}
                  </ul>
                )}
              </Fragment>
            ))}
            {/* What was observed that month: the profile's own filing
                history and the agency's messages, each on its day. */}
            {month.events.length > 0 && (
              <ul
                className="calendar-observed"
                aria-label={t("desktop.calendar.observed")}
              >
                {month.events.map((event) => (
                  <li
                    key={event.reference_id}
                    data-event={event.event_type}
                    className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 border-b px-4 py-1.5 pl-[calc(--spacing(4)+2px)] text-sm text-muted-foreground"
                  >
                    <span className="grid w-10 justify-items-center">
                      <Icon
                        name={event.event_type === "filing" ? "check" : "mail"}
                        size="sm"
                      />
                    </span>
                    <span className="min-w-0">
                      <time dateTime={event.event_date}>
                        {short.format(day(event.event_date))}
                      </time>
                      {" · "}
                      {t(`desktop.calendar.event.${event.event_type}`)}
                      {" · "}
                      <span className="text-foreground">{event.summary}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}
        {today && turning === null && (
          <TodayMark on={today} today={here} locale={locale} />
        )}
      </div>
    );
    const note = coverage.advised.length > 0 && (
      <p className="px-4 py-3 text-sm text-muted-foreground">
        {t("desktop.calendar.undetermined", {
          modelos: coverage.advised.map((item) => item.modelo).join(", "),
        })}
      </p>
    );
    body = (
      <div
        className={cn(
          "calendar-layout",
          wide &&
            !nothing &&
            "grid grid-cols-[minmax(0,1fr)_minmax(20rem,26rem)] items-start",
        )}
      >
        <div className="min-w-0">
          {/* The head stays while the page scrolls under it: the calendar
              opens on the current month, which is seldom the first. Where
              the page is narrow or short only the controls stay, and the
              counts and the sentence scroll with the rest. */}
          <div
            ref={head}
            className="calendar-head contents @md:group-data-[head=whole]/calendar:sticky @md:group-data-[head=whole]/calendar:top-0 @md:group-data-[head=whole]/calendar:z-(--layer-pinned) @md:group-data-[head=whole]/calendar:block @md:group-data-[head=whole]/calendar:border-b @md:group-data-[head=whole]/calendar:bg-background"
          >
            <div className="contents @md:group-data-[head=whole]/calendar:grid @md:group-data-[head=whole]/calendar:grid-cols-[minmax(0,1fr)_auto] @md:group-data-[head=whole]/calendar:items-center @md:group-data-[head=whole]/calendar:gap-x-3 @md:group-data-[head=whole]/calendar:px-4 @md:group-data-[head=whole]/calendar:py-1.5">
              {/* The counts are also the key to the months' colours. With
                  nothing to count, the sentence takes their place. */}
              {standing.length > 0 ? (
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-4 pt-2.5 @md:group-data-[head=whole]/calendar:p-0">
                  <ul
                    className="calendar-standing flex flex-wrap gap-1.5"
                    aria-label={t("desktop.calendar.standing")}
                  >
                    {standing.map(([kind, count]) => (
                      <li key={kind} className="flex">
                        <Badge variant={STATE_TONE[kind]}>
                          {/* The same mark the reading has among the months. */}
                          {STATE_MARK[kind] && (
                            <Icon name={STATE_MARK[kind] ?? "info"} size="xs" />
                          )}
                          {t(`desktop.calendar.state.${kind}`)}{" "}
                          <span className="font-semibold tabular-nums">
                            {count}
                          </span>
                        </Badge>
                      </li>
                    ))}
                  </ul>
                  {/* What the marks on the months' days are, where the months
                    are shown and have any. */}
                  {(wide || view === "months") && observedKinds.length > 0 && (
                    <ul
                      className="calendar-key flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground"
                      aria-label={t("desktop.calendar.observed")}
                    >
                      {observedKinds.map((kind) => (
                        <li key={kind} className="flex items-center gap-1.5">
                          <span
                            aria-hidden="true"
                            className={cn(
                              "size-2 rounded-full",
                              EVENT_MARK[kind],
                            )}
                          />
                          {t(`desktop.calendar.event.${kind}`)}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : (
                <div className="px-4 pt-2.5 @md:group-data-[head=whole]/calendar:p-0">
                  {provenance}
                </div>
              )}
              <div
                ref={bar}
                className="calendar-controls sticky top-0 z-(--layer-pinned) flex items-center justify-end gap-2 border-b bg-background px-4 py-1 @md:group-data-[head=whole]/calendar:static @md:group-data-[head=whole]/calendar:border-b-0 @md:group-data-[head=whole]/calendar:p-0"
              >
                {/* One face at a time where there is no room for both. */}
                {!wide && !nothing && (
                  <SegmentedControl
                    className="calendar-view"
                    aria-label={t("desktop.calendar.view")}
                    value={view}
                    onValueChange={(next) =>
                      setView(next === "list" ? "list" : "months")
                    }
                  >
                    <SegmentedControlItem value="months">
                      {t("desktop.calendar.view_months")}
                    </SegmentedControlItem>
                    <SegmentedControlItem value="list">
                      {t("desktop.calendar.view_list")}
                    </SegmentedControlItem>
                  </SegmentedControl>
                )}
                {/* The way back to where the calendar stands, from
                    wherever the reader has gone in it. */}
                {!nothing && today && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="calendar-to-today min-w-control-sm"
                    // Named for today it needs no more. Named for another
                    // day, the day alone is not a name: it says where to.
                    aria-label={
                      today === here
                        ? undefined
                        : t("desktop.calendar.to_day", {
                            date: new Intl.DateTimeFormat(locale, {
                              dateStyle: "medium",
                            }).format(day(today)),
                          })
                    }
                    onClick={toToday}
                  >
                    {evaluatedWord(today, here, locale)}
                  </Button>
                )}
                <IconButton
                  label={t("desktop.calendar.refresh")}
                  pending={refreshing}
                  onClick={onRefresh}
                >
                  {!refreshing && <Icon name="reset" />}
                </IconButton>
              </div>
            </div>
            {standing.length > 0 && (
              <div className="border-b px-4 py-1.5 @md:group-data-[head=whole]/calendar:border-b-0 @md:group-data-[head=whole]/calendar:pt-0 @md:group-data-[head=whole]/calendar:pb-2">
                {provenance}
              </div>
            )}
          </div>
          {warnings.length > 0 && (
            <Alert
              tone="warning"
              className="mx-4 mt-3 w-auto"
              icon={<Icon name="alert" />}
            >
              <p>{t("desktop.calendar.warnings")}</p>
              <ul className="mt-1 grid gap-0.5 text-sm">
                {warnings.map((warning) => (
                  <li key={warning.code + warning.affected_modelos.join()}>
                    {warning.message}
                  </li>
                ))}
              </ul>
            </Alert>
          )}
          {nothing ? (
            <Empty role="status">
              <EmptyMedia>
                <Icon name="calendar" />
              </EmptyMedia>
              <EmptyDescription>{t("desktop.calendar.empty")}</EmptyDescription>
            </Empty>
          ) : wide || view === "months" ? (
            <CalendarMonths
              calendar={state.calendar}
              locale={locale}
              today={here}
              selected={selected}
              onSelect={selectInMonths}
              asked={asked}
              onAsked={onAsked}
            />
          ) : (
            list
          )}
          {note}
        </div>
        {/* Beside the months where the page is wide: the list keeps its own
            place and scrolls by itself, as tall as the page. */}
        {wide && !nothing && (
          <div
            ref={aside}
            onScroll={(event) => scrolled(event.currentTarget, ["list"])}
            className="calendar-aside sticky top-0 h-(--calendar-height) overflow-y-auto border-l bg-background [--calendar-head:0px]"
          >
            {list}
          </div>
        )}
      </div>
    );
  }

  return (
    <section
      ref={root}
      tabIndex={-1}
      aria-label={t("desktop.calendar.title")}
      aria-busy={refreshing || undefined}
      data-head={room.tall ? "whole" : "controls"}
      // Where the reader is, in the face or faces this page itself scrolls.
      onScroll={(event) =>
        scrolled(event.currentTarget, wide ? ["months"] : [view])
      }
      // The scrollbar's room is kept whether or not there is one: a month
      // drawn whole must not change the page's width by making it scroll.
      className="group/calendar calendar-page @container flex min-h-0 flex-1 flex-col overflow-y-auto bg-background [scrollbar-gutter:stable] focus-visible:-outline-offset-2"
    >
      {body}
    </section>
  );
}
