import {
  memo,
  useCallback,
  useDeferredValue,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type RefObject,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon, type IconName } from "@/components/ui/icon";
import { Spinner } from "@/components/ui/spinner";
import { chordMatches, type ChordKeys } from "@/shared/chords";
import type { Action, Chord } from "../../shell/actions";
import type { Host } from "../../shell/host";
import type { ProfileView } from "../../shell/layout";
import type { LedgerProfileStep } from "../../shell/ledger";
import { facts } from "../../shell/compose";
import { useNavigationGuard } from "../../shell/navigation/hooks";
import { useCensoSync, type CensoSnapshot } from "../../shell/profileCenso";
import {
  columns,
  counts,
  entries,
  aeatMethod,
  fieldAt,
  marked,
  matches,
  nameOf,
  rowsOf,
  sorted,
  type Row,
} from "../../shell/profileRows";
import { useStrings } from "../../shell/strings";
import {
  fieldValue,
  profileText,
  useUserProfile,
  type ProfileField,
  type ProfileSection,
  type UserProfile,
} from "../../shell/userProfile";
import type { MenuEntry, OpenMenu } from "../ContextMenu";
import { AeatAccessEditor } from "./AeatAccessEditor";
import { Household } from "./Household";
import { PasswordChange, ProfileShortcuts } from "./ProfileDialogs";
import { ProfileDetails, STATUS_GROUPS } from "./ProfileDetails";
import { ProfileEditor, type ProfileDraft } from "./ProfileEditor";
import { PROFILE_KEYS } from "./profileKeys";
import { ProfileSectionIndex } from "./ProfileSectionIndex";
import { ProfileSummaryHeader } from "./ProfileSummaryHeader";
import { ProfileSync } from "./ProfileSync";
import { ProfileToolbar } from "./ProfileToolbar";
import { ProfileCompletionNotice } from "./ProfileCompletionNotice";

/** A profile action and, where the page runs it by a key of its own, that
 * key: the page's menus show it from the declaration its handlers match. */
type PageAction = Action & { pageKey?: ChordKeys };

// Drawn again only when what it is given changes: the window redraws far more
// often than the profile does.
export const UserProfilePage = memo(function UserProfilePage({
  host,
  reader,
  sessionEnded,
  language,
  shown,
  page,
  maximized,
  onToggleMaximize,
  maximizeChord,
  view,
  onViewChange,
  aeatAsked,
  onAeatHandled,
  censoAsked,
  onCensoHandled,
  profileStep,
  onProfileStepHandled,
  contribute,
  openMenu,
  accountActions,
  onCopy,
  onNotice,
}: {
  host: Host;
  reader: string;
  /** Whether the window asked the signed-in session to end. */
  sessionEnded?: () => boolean;
  language: string;
  shown: boolean;
  page: RefObject<HTMLElement | null>;
  /** Full screen: the page has the window to itself. */
  maximized: boolean;
  onToggleMaximize(): void;
  /** The registry's chord for full screen, shown beside it in the menus. */
  maximizeChord?: Chord;
  view: ProfileView;
  onViewChange(update: (current: ProfileView) => ProfileView): void;
  /** The AEAT access editor was asked for, by a link or the palette: the
   * page opens it once it has the profile, then says it did. */
  aeatAsked: boolean;
  onAeatHandled(): void;
  censoAsked: boolean;
  onCensoHandled(): void;
  /** The step a refusal elsewhere served for putting this profile right,
   * held as the backend served it; the page answers its kind once it has the
   * profile, then says it did. Null when none is asked for. */
  profileStep: LedgerProfileStep | null;
  onProfileStepHandled(): void;
  /** Hands the window's palette what the page offers, read when it opens. */
  contribute(actions: (() => Action[]) | null): void;
  openMenu: OpenMenu;
  /** The window's own account actions, offered among the profile's, as
   * they stand when a menu opens. */
  accountActions(): Action[];
  onCopy(text: string): void;
  onNotice(text: string): void;
}) {
  const t = useStrings();
  const profile = useUserProfile(host.userProfile, reader, language, shown);
  const data = profile.data;
  const sync = useCensoSync(host.censo, data, shown && !!data, profile.refresh);
  const [search, setSearch] = useState("");
  const [active, setActive] = useState<string | null>(null);
  const [current, setCurrent] = useState("");
  const [draft, setDraft] = useState<ProfileDraft | null>(null);
  // The profile the AEAT access editor opened on.
  const [aeat, setAeat] = useState<UserProfile | null>(null);
  const [password, setPassword] = useState(false);
  const [shortcuts, setShortcuts] = useState(false);
  const [fromAeat, setFromAeat] = useState<ReadonlySet<string>>(new Set());
  const scroller = useRef<HTMLDivElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const { show, group, sort } = view;
  const collapsed = useMemo(() => new Set(view.collapsed), [view.collapsed]);
  const needle = profileText(useDeferredValue(search).trim());
  const filtering = show !== "all" || !!needle;
  const missing = useMemo(() => new Set(data?.missing_required), [data]);
  const allRows = useMemo(() => (data ? rowsOf(data) : []), [data]);
  const visible = useMemo(
    () =>
      sorted(
        allRows.filter((row) => matches(row, show, needle)),
        sort,
        language,
      ),
    [allRows, show, needle, sort, language],
  );
  const busy = profile.saving || profile.loading;
  const review = sync.snapshot?.state === "review" ? sync.snapshot : null;
  const incoming = useMemo(
    () => new Map(review?.fields.map((field) => [field.path, field])),
    [review],
  );
  // Leaving the page loses a save or a Censo pull in flight, whose outcome
  // only this page shows, and a Censo review not yet answered. A field
  // draft is its editor's own to weigh.
  const censoState = sync.snapshot?.state;
  useNavigationGuard(
    "profile",
    profile.saving ||
      sync.busy ||
      censoState === "reading" ||
      censoState === "device"
      ? "busy"
      : review
        ? "dirty"
        : "clean",
  );

  const setView = useCallback(
    (patch: Partial<ProfileView>) =>
      onViewChange((now) => ({ ...now, ...patch })),
    [onViewChange],
  );
  const toggle = useCallback(
    (key: string, open?: boolean) =>
      onViewChange((now) => {
        const next = new Set(now.collapsed);
        if (open ?? next.has(key)) next.delete(key);
        else next.add(key);
        return { ...now, collapsed: [...next] };
      }),
    [onViewChange],
  );

  // What a review brings is remembered until it is answered, so the values
  // it saved can say where they came from.
  const reviewed = useRef<CensoSnapshot["fields"]>([]);
  useEffect(() => {
    if (review) reviewed.current = review.fields;
  }, [review]);
  const syncState = sync.snapshot?.state;
  useEffect(() => {
    if (syncState === "done")
      setFromAeat(
        new Set(
          reviewed.current
            .filter((field) => !field.preserve && field.incoming !== null)
            .map((field) => field.path),
        ),
      );
    if (
      syncState === "done" ||
      syncState === "stopped" ||
      syncState === "failed"
    )
      reviewed.current = [];
  }, [syncState]);

  const saved = profile.saved;
  useEffect(() => {
    if (saved) onNotice(t("desktop.profile.saved_notice"));
  }, [saved, onNotice, t]);

  // Which section is in view, for the section index.
  useEffect(() => {
    const root = scroller.current;
    if (!root || !maximized) return;
    const observer = new IntersectionObserver(
      (records) => {
        const top = records
          .filter((record) => record.isIntersecting)
          .sort(
            (a, b) => a.boundingClientRect.top - b.boundingClientRect.top,
          )[0];
        if (top) setCurrent((top.target as HTMLElement).dataset.section ?? "");
      },
      { root, rootMargin: "0px 0px -70% 0px" },
    );
    root
      .querySelectorAll("[data-section]")
      .forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [group, visible, collapsed, maximized, data]);

  const focusNav = (id: string) => {
    const element = page.current?.querySelector<HTMLElement>(
      `[data-nav="${CSS.escape(id)}"]`,
    );
    element?.focus();
    element?.scrollIntoView({ block: "nearest" });
  };
  // Each change of view is drawn before focus moves into it.
  const afterDraw = (then: () => void) =>
    requestAnimationFrame(() => requestAnimationFrame(then));

  const goToSection = (key: string) => {
    const hidden =
      !!needle ||
      (show !== "all" &&
        !visible.some((row) => row.section.key === key) &&
        !data?.sections.find((section) => section.key === key)?.repeatable);
    if (hidden) setSearch("");
    onViewChange((now) => ({
      ...now,
      show: hidden ? "all" : now.show,
      group: "section",
      collapsed: now.collapsed.filter((held) => held !== key),
    }));
    afterDraw(() => {
      const target = page.current?.querySelector<HTMLElement>(
        `[data-section="${CSS.escape(key)}"]`,
      );
      target?.scrollIntoView({ block: "start" });
      target?.querySelector<HTMLElement>("[data-nav]")?.focus({
        preventScroll: true,
      });
    });
  };
  const showDetail = (id: string) => {
    setSearch("");
    const section = id.slice(0, id.indexOf("."));
    onViewChange((now) => ({
      ...now,
      show: "all",
      collapsed: now.collapsed.filter((held) => held !== section),
    }));
    afterDraw(() => focusNav(id));
  };

  const openEditor = (
    section: ProfileSection,
    fields: ProfileField[],
    kind: ProfileDraft["kind"],
  ) => {
    if (!data || !fields.length) return;
    // The method is one edit of its own, with its route and certificate.
    if (kind === "field" && aeatMethod(fields[0]!)) {
      setAeat(data);
      return;
    }
    setDraft({ base: data, section, fields, kind });
  };
  // A detail of a section holding no entry is filled in as its first entry.
  const editRow = (row: Row) =>
    row.section.repeatable
      ? openEditor(row.section, columns(row.section), "add_row")
      : openEditor(row.section, [row.field], "field");
  const editEntry = (section: ProfileSection, entry: string | null) =>
    entry === null
      ? openEditor(section, columns(section), "add_row")
      : openEditor(
          section,
          section.fields.filter((field) => field.row_index === entry),
          "update_row",
        );
  const removeEntry = (section: ProfileSection, entry: string) =>
    openEditor(
      section,
      section.fields.filter((field) => field.row_index === entry),
      "remove_row",
    );

  const writable = !!data && !busy && profile.error !== "unknown";
  // Asked for from outside the page, the editor opens on the profile read,
  // and an editor already open keeps the one it has.
  useEffect(() => {
    if (!aeatAsked || !data) return;
    setAeat((open) => open ?? data);
    onAeatHandled();
  }, [aeatAsked, data, onAeatHandled]);
  const rowById = (id: string | null) =>
    allRows.find((row) => row.id === id) ?? null;
  const entryOf = (id: string | null) => {
    const [kind, key, entry] = id?.split(":") ?? [];
    const section = data?.sections.find((item) => item.key === key);
    return kind === "entry" && section && entry !== undefined
      ? { section, entry }
      : null;
  };

  // ── Actions ─────────────────────────────────────────────────────────────
  const action = (
    id: string,
    label: string,
    icon: IconName,
    run: () => void,
    extra: Partial<PageAction> = {},
  ): PageAction => ({
    id: `profile.${id}`,
    label,
    group: "profile",
    icon,
    run,
    ...extra,
  });
  const rowActions = (row: Row): PageAction[] => {
    const { field } = row;
    const value = field.masked ? null : fieldValue(field);
    return [
      action(
        "edit",
        t("desktop.profile.edit_field", { field: field.label }),
        "edit",
        () => editRow(row),
        { pageKey: PROFILE_KEYS.edit, enabled: () => writable },
      ),
      action(
        "copy",
        t("desktop.profile.action.copy", { field: field.label }),
        "copy",
        () => {
          if (value) onCopy(value);
        },
        { pageKey: PROFILE_KEYS.copy, enabled: () => !!value },
      ),
      action(
        "clear",
        t("desktop.profile.action.clear", { field: field.label }),
        "erase",
        () => {
          if (data)
            void profile.save(data, {
              kind: "field",
              path: field.path,
              value: "",
            });
        },
        {
          enabled: () =>
            writable &&
            row.state === "filled" &&
            !marked(row) &&
            !aeatMethod(field),
        },
      ),
      action(
        "about",
        t("desktop.profile.action.about", { field: field.label }),
        "info",
        () => onNotice(field.help?.join(" ") || field.about || field.label),
        { enabled: () => !!field.help?.length || !!field.about },
      ),
    ];
  };
  const entryActions = (
    section: ProfileSection,
    entry: string,
  ): PageAction[] => [
    action(
      "edit",
      t("desktop.profile.action.edit_entry"),
      "edit",
      () => editEntry(section, entry),
      { pageKey: PROFILE_KEYS.edit, enabled: () => writable },
    ),
    action(
      "add",
      t("desktop.profile.add"),
      "plus",
      () => editEntry(section, null),
      { enabled: () => writable },
    ),
    action(
      "remove",
      t("desktop.profile.remove"),
      "trash",
      () => removeEntry(section, entry),
      { enabled: () => writable },
    ),
  ];
  const focusedActions = (): PageAction[] => {
    const row = rowById(active);
    if (row) return rowActions(row);
    const owner = entryOf(active);
    return owner ? entryActions(owner.section, owner.entry) : [];
  };
  const syncReady =
    !!sync.readiness?.ready &&
    !sync.busy &&
    !sync.recovering &&
    !sync.uncertain &&
    (!sync.snapshot ||
      sync.snapshot.state === "done" ||
      sync.snapshot.state === "stopped" ||
      sync.snapshot.state === "failed");
  const pullCenso = () => {
    if (sync.snapshot?.state === "done") sync.dismiss();
    void sync.start();
  };
  // Asked for from outside the page (the global palette action): a pull
  // already running or awaiting review is left to its band, and otherwise the
  // check of what a pull needs is awaited and the pull starts if it passes.
  // A refused check is shown by the band.
  const censoWaiting =
    !!sync.snapshot &&
    sync.snapshot.state !== "done" &&
    sync.snapshot.state !== "stopped" &&
    sync.snapshot.state !== "failed";
  useEffect(() => {
    if (!censoAsked) return;
    if (!host.censo) return onCensoHandled();
    if (!data || !shown || sync.recovering) return;
    if (censoWaiting || sync.busy || sync.uncertain) return onCensoHandled();
    if (sync.snapshot && !sync.readiness) return sync.dismiss();
    if (!sync.readiness && !sync.error) return;
    if (syncReady) void sync.start();
    onCensoHandled();
  }, [
    censoAsked,
    data,
    shown,
    host.censo,
    censoWaiting,
    onCensoHandled,
    sync,
    syncReady,
  ]);
  // Declaring the setup complete: the one door that ends it, offered as a
  // page action and run by the step a refusal elsewhere served.
  const completeReady =
    writable &&
    !!data &&
    data.setup_state !== "complete" &&
    missing.size === 0 &&
    data.valid;
  const completeSetup = () => {
    if (data) void profile.save(data, { kind: "complete" });
  };
  // How a step is answered, kept on a ref so the ask is answered once per ask
  // rather than on every redraw the page's own handlers are rebuilt in.
  const answerStep = useRef<(step: LedgerProfileStep) => void>(() => {});
  useLayoutEffect(() => {
    answerStep.current = (step) => {
      // A field step reveals and focuses that detail's own row; a detail of a
      // section holding no entry yet is filled in as its first entry, so the
      // step opens that entry. The completion step runs the action where it
      // is ready, and otherwise reveals the first detail still outstanding,
      // which is what the action is waiting for.
      if (step.kind === "open_profile_field") {
        const owner = data?.sections.find(
          (section) =>
            section.key === step.path.slice(0, step.path.indexOf(".")),
        );
        if (owner?.repeatable && entries(owner).length === 0 && writable)
          editEntry(owner, null);
        else showDetail(step.path);
      } else if (completeReady) completeSetup();
      else {
        const first = data?.missing_required[0];
        if (first !== undefined) showDetail(first);
      }
    };
  });
  // Asked for from outside the page: answered once the profile is read.
  useEffect(() => {
    if (profileStep === null || !data || !shown) return;
    answerStep.current(profileStep);
    onProfileStepHandled();
  }, [profileStep, data, shown, onProfileStepHandled]);
  const changePassword = host.profiles?.changePassword;
  const profileActions: PageAction[] = [
    ...(host.censo
      ? [
          action(
            "sync",
            t("desktop.profile.censo.title"),
            "sync",
            pullCenso,
            // The global palette entry runs the same flow from any page.
            { enabled: () => syncReady, hidden: true },
          ),
        ]
      : []),
    ...(host.userProfile && data
      ? [
          action(
            "aeatAccess",
            t("desktop.profile.action.aeat_access"),
            "shield",
            () => setAeat(data),
            { enabled: () => writable },
          ),
        ]
      : []),
    ...(changePassword
      ? [
          action("password", t("desktop.profile.password.title"), "key", () =>
            setPassword(true),
          ),
        ]
      : []),
    action(
      "complete",
      t("desktop.profile.complete"),
      "selectAll",
      completeSetup,
      {
        enabled: () => completeReady,
      },
    ),
    action(
      "refresh",
      t("desktop.profile.action.refresh"),
      "reset",
      () => profile.refresh(),
      { enabled: () => !busy },
    ),
  ];
  const viewActions: PageAction[] = [
    action(
      "search",
      t("desktop.profile.search"),
      "search",
      () => {
        searchInput.current?.focus();
        searchInput.current?.select();
      },
      { pageKey: PROFILE_KEYS.search },
    ),
    action(
      "expand",
      t("desktop.profile.action.expand"),
      "expandAll",
      () => setView({ collapsed: [] }),
      { enabled: () => collapsed.size > 0 },
    ),
    action(
      "collapse",
      t("desktop.profile.action.collapse"),
      "collapseAll",
      () => setView({ collapsed: groupKeys() }),
      {
        enabled: () => collapsed.size < groupKeys().length,
      },
    ),
    action(
      "fullScreen",
      t(maximized ? "desktop.profile.compact" : "desktop.profile.maximize"),
      maximized ? "restore" : "maximize",
      onToggleMaximize,
      { chords: maximizeChord ? [maximizeChord] : undefined },
    ),
    action(
      "shortcuts",
      t("desktop.profile.keys.title"),
      "keyboard",
      () => setShortcuts(true),
      { pageKey: PROFILE_KEYS.help },
    ),
  ];
  function groupKeys() {
    return [
      ...(data?.sections.map((section) => section.key) ?? []),
      ...STATUS_GROUPS.map((state) => `status-${state}`),
      "all",
    ];
  }

  // The palette asks for these when it opens: the focused detail's own
  // actions only while focus is on the page, then the profile's, and a way
  // to every section once something is typed.
  const latest = useRef<() => Action[]>(() => []);
  useEffect(() => {
    latest.current = () =>
      shown && data
        ? [
            ...(page.current?.contains(document.activeElement)
              ? focusedActions()
              : []),
            ...profileActions,
            ...viewActions.filter((item) => item.id !== "profile.fullScreen"),
            ...data.sections.map((section) =>
              action(
                `goto.${section.key}`,
                t("desktop.profile.action.go_to", { section: section.title }),
                "forward",
                () => goToSection(section.key),
                { quiet: true },
              ),
            ),
          ]
        : [];
  });
  useEffect(() => {
    contribute(() => latest.current());
    return () => contribute(null);
  }, [contribute]);

  const entry = (item: PageAction): MenuEntry => ({
    id: item.id,
    label: item.label,
    icon: item.icon,
    chord: item.pageKey ?? item.chords?.[0],
    enabled: item.enabled ? item.enabled() : true,
    run: item.run,
  });
  const menuOf = (...groups: PageAction[][]): MenuEntry[] =>
    groups
      .filter((items) => items.length)
      .flatMap((items, index) => [
        ...(index ? [{ separator: true as const }] : []),
        ...items.map(entry),
      ]);
  const detailMenu = (at: { x: number; y: number; height?: number }) =>
    openMenu(
      menuOf(
        focusedActions(),
        profileActions.filter((item) =>
          ["profile.sync", "profile.refresh"].includes(item.id),
        ),
      ),
      at,
    );
  const actionsMenu = (button: HTMLElement) => {
    const box = button.getBoundingClientRect();
    openMenu(
      menuOf(
        profileActions,
        viewActions,
        accountActions().filter((item) => !item.enabled || item.enabled()),
      ),
      { x: box.left, y: box.top, height: box.height },
    );
  };

  // ── Keys ────────────────────────────────────────────────────────────────
  // The page's own keys. The palette and full screen are the window's.
  const onPageKey = (event: ReactKeyboardEvent<HTMLElement>) => {
    const typing = (event.target as HTMLElement).closest(
      "input, textarea, select, [role='dialog'], [role='menu']",
    );
    const mod = event.ctrlKey || event.metaKey;
    if (typing || event.altKey) return;
    if (chordMatches(PROFILE_KEYS.search, event)) {
      event.preventDefault();
      searchInput.current?.focus();
      searchInput.current?.select();
    } else if (chordMatches(PROFILE_KEYS.help, event)) {
      event.preventDefault();
      setShortcuts(true);
    } else if (mod && !event.shiftKey && event.code === "KeyF") {
      event.preventDefault();
      searchInput.current?.focus();
    }
  };
  // Arrow keys walk the details in the order they are shown.
  const onListKey = (event: ReactKeyboardEvent<HTMLElement>) => {
    const target = event.target as HTMLElement;
    const id = target.dataset.nav;
    if (!id) return;
    const items = [
      ...(page.current?.querySelectorAll<HTMLElement>("[data-nav]") ?? []),
    ];
    const at = items.indexOf(target);
    const heads = items.filter((item) => item.dataset.kind === "head");
    const go = (element: HTMLElement | undefined) => {
      if (!element) return;
      event.preventDefault();
      element.focus();
      element.scrollIntoView({ block: "nearest" });
    };
    const row = rowById(id);
    const owner = entryOf(id);
    const head = target.dataset.kind === "head";
    const key = head ? id.slice("head:".length) : "";
    if (event.altKey) return;
    if (
      [PROFILE_KEYS.edit, ...PROFILE_KEYS.editToo].some((keys) =>
        chordMatches(keys, event),
      )
    ) {
      if (head) return;
      event.preventDefault();
      if (!writable) return;
      if (row) editRow(row);
      else if (owner) editEntry(owner.section, owner.entry);
      return;
    }
    if (chordMatches(PROFILE_KEYS.copy, event)) {
      if (row && !row.field.masked && !window.getSelection()?.toString()) {
        event.preventDefault();
        const value = fieldValue(row.field);
        if (value) onCopy(value);
      }
      return;
    }
    switch (event.key) {
      case "ArrowDown":
      case "j":
        return go(items[at + 1]);
      case "ArrowUp":
      case "k":
        return go(items[at - 1]);
      case "Home":
        return go(items[0]);
      case "End":
        return go(items.at(-1));
      case "]":
      case "PageDown":
        return go(heads.find((item) => items.indexOf(item) > at));
      case "[":
      case "PageUp":
        return go(
          [...heads].reverse().find((item) => items.indexOf(item) < at),
        );
      case "ArrowLeft":
        if (head) {
          event.preventDefault();
          toggle(key, false);
        } else
          go(
            items.find(
              (item) => item.dataset.nav === `head:${target.dataset.of}`,
            ),
          );
        return;
      case "ArrowRight":
        if (head) {
          event.preventDefault();
          if (collapsed.has(key)) toggle(key, true);
          else go(items[at + 1]);
        }
        return;
      case "Delete":
        if (owner && writable) {
          event.preventDefault();
          removeEntry(owner.section, owner.entry);
        }
        return;
      case "ContextMenu":
      case "F10":
        if (event.key === "F10" && !event.shiftKey) return;
        if (head) return;
        event.preventDefault();
        {
          const box = target.getBoundingClientRect();
          detailMenu({ x: box.left + 24, y: box.top, height: box.height });
        }
        return;
    }
  };

  // ── Summary header ──────────────────────────────────────────────────────
  const total = data ? counts(data) : null;
  const header = data && total && (
    <ProfileSummaryHeader
      name={nameOf(data)}
      full={maximized}
      facts={[
        ["idCard", fieldAt(data, "identity.tax_id")],
        ["mail", fieldAt(data, "identity.email")],
        ["phone", fieldAt(data, "contact.contact_person_phone")],
        [
          "place",
          fieldAt(data, "contact.fiscal_address"),
          facts(t, [
            fieldAt(data, "contact.fiscal_address")?.value,
            fieldAt(data, "contact.postcode")?.value,
          ]),
        ],
      ]}
      missing={missing}
      filled={total.filled}
      total={total.total}
      missingCount={total.missing}
      onMissing={() => setView({ show: "required", group: "section" })}
      actions={
        <Button
          size="sm"
          variant="outline"
          aria-haspopup="menu"
          aria-keyshortcuts="Shift+F10"
          onClick={(event) => actionsMenu(event.currentTarget)}
        >
          {t("desktop.profile.action.menu")}
          <Icon name="chevronDown" size="xs" />
        </Button>
      }
    />
  );

  // ── Toolbar ─────────────────────────────────────────────────────────────
  const toolbar = data && (
    <ProfileToolbar
      sections={data.sections}
      onGoToSection={goToSection}
      maximized={maximized}
      search={search}
      onSearch={setSearch}
      searchInput={searchInput}
      page={page}
      show={show}
      group={group}
      sort={sort}
      onView={setView}
      collapsedCount={collapsed.size}
      onToggleCollapsed={() =>
        setView({ collapsed: collapsed.size ? [] : groupKeys() })
      }
      loading={profile.loading}
      filtering={filtering}
      results={visible.length}
    />
  );

  // ── Details ─────────────────────────────────────────────────────────────
  // Entries are listed with the details they belong beside, except where
  // the person asked only for what is missing.
  const listsEntries = show === "all" || show === "filled";
  const nothing =
    !!data &&
    !visible.length &&
    !(
      listsEntries &&
      data.sections.some(
        (section) => section.repeatable && (!needle || entries(section).length),
      )
    );

  const index = data && maximized && (
    <ProfileSectionIndex
      sections={data.sections}
      missing={missing}
      current={current}
      onGoToSection={goToSection}
    />
  );

  const errorKeys = {
    unavailable: "desktop.profile.unavailable",
    not_signed_in: "desktop.profile.signed_out",
    refused: "desktop.profile.refused",
    conflict: "desktop.profile.conflict",
    unknown: "desktop.profile.unknown",
    saved_unread: "desktop.profile.saved_unread",
  } as const;
  const error = profile.error ? t(errorKeys[profile.error]) : null;

  return (
    <section
      ref={page}
      tabIndex={-1}
      aria-label={t("desktop.profile.title")}
      onKeyDown={onPageKey}
      className="user-profile-page @container/profile relative flex min-h-0 flex-1 flex-col outline-none"
    >
      {header}
      {data && host.censo && (
        <ProfileSync
          sync={sync}
          compact={!maximized}
          onTaxId={() => {
            const row = rowById("identity.tax_id");
            if (row && writable) editRow(row);
          }}
          onSetup={() => {
            if (writable) setAeat(data);
          }}
          onReview={() => {
            const first = review?.fields.find((field) =>
              allRows.some((row) => row.id === field.path),
            );
            if (first) showDetail(first.path);
          }}
        />
      )}
      {error && (
        <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2">
          <Alert role="alert" tone="danger" className="min-w-0 flex-1">
            {error}
          </Alert>
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={profile.refresh}
          >
            {t("desktop.profile.refresh")}
          </Button>
        </div>
      )}
      {profile.loading && !data && (
        <div role="status" className="flex items-center gap-2 px-4 py-3">
          <Spinner />
          {t("desktop.profile.loading")}
        </div>
      )}
      {data && (
        <div className="flex min-h-0 flex-1">
          {index}
          <div
            ref={scroller}
            className="min-w-0 flex-1 overflow-y-auto"
            onKeyDown={onListKey}
          >
            {toolbar}
            <div className="grid gap-3 p-4">
              <ProfileCompletionNotice
                key={data.profile_id}
                profile={profile.loading || profile.error ? null : data}
              />
              <ProfileDetails
                data={data}
                visible={visible}
                group={group}
                needle={needle}
                listsEntries={listsEntries}
                collapsed={collapsed}
                onToggle={toggle}
                missing={missing}
                incoming={incoming}
                fromAeat={fromAeat}
                writable={writable}
                maximized={maximized}
                active={active}
                onActive={setActive}
                onEditRow={editRow}
                onEditEntry={editEntry}
                onRemoveEntry={removeEntry}
                onMenu={detailMenu}
              />
              {/* The household is not one of the profile's details: it is
                  the people the declaration lists, read and written as a
                  whole, so a text search of details does not hide it. */}
              {host.profileCompanions && host.userProfile && !needle && (
                <Household
                  reads={host.profileCompanions}
                  change={host.userProfile.change}
                  observe={host.userProfile.observe}
                  language={language}
                  writable={writable}
                  sessionEnded={sessionEnded}
                />
              )}
              {nothing && (
                <p className="py-5 text-muted-foreground">
                  {t("desktop.profile.empty")}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
      {draft && (
        <ProfileEditor
          draft={draft}
          busy={profile.saving}
          blocked={profile.error === "unknown"}
          onRefresh={profile.refresh}
          changed={
            !data ||
            draft.base.record_revision !== data.record_revision ||
            draft.base.content_digest !== data.content_digest
          }
          error={error}
          onSave={(edit) => profile.save(draft.base, edit)}
          onClose={() => setDraft(null)}
        />
      )}
      {aeat && host.userProfile && (
        <AeatAccessEditor
          base={aeat}
          current={data}
          port={host.userProfile.aeat}
          censo={host.censo}
          busy={profile.saving}
          blocked={profile.error === "unknown"}
          error={error}
          latest={profile.latest}
          onRefresh={profile.refresh}
          onSave={profile.save}
          onSettled={sync.retry}
          onClose={() => setAeat(null)}
        />
      )}
      <ProfileShortcuts open={shortcuts} onClose={() => setShortcuts(false)} />
      {changePassword && (
        <PasswordChange
          change={changePassword}
          open={password}
          onClose={() => setPassword(false)}
          onChanged={() => {
            setPassword(false);
            onNotice(t("desktop.profile.password.changed"));
          }}
        />
      )}
    </section>
  );
});
