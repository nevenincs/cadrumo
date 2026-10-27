import {
  memo,
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon, type IconName } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import { Progress } from "@/components/ui/progress";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import { chordMatches, type ChordKeys } from "@/shared/chords";
import type { Action, Chord } from "../../shell/actions";
import type { Host } from "../../shell/host";
import type { ProfileView } from "../../shell/layout";
import { useNavigationGuard } from "../../shell/navigation/hooks";
import { useCensoSync, type CensoSnapshot } from "../../shell/profileCenso";
import {
  columns,
  counts,
  entries,
  aeatMethod,
  fieldAt,
  initials,
  marked,
  matches,
  nameOf,
  requiredSection,
  rowsOf,
  sectionCounts,
  shownValue,
  sorted,
  type Group,
  type Row,
  type Show,
  type Sort,
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
import { PasswordChange, ProfileShortcuts } from "./ProfileDialogs";
import { ProfileEditor, type ProfileDraft } from "./ProfileEditor";
import { PROFILE_KEYS } from "./profileKeys";
import { ProfileSync } from "./ProfileSync";
import { ProfileCompletionNotice } from "./ProfileCompletionNotice";

/** A profile action and, where the page runs it by a key of its own, that
 * key: the page's menus show it from the declaration its handlers match. */
type PageAction = Action & { pageKey?: ChordKeys };

const STATUS_GROUPS = ["required", "unset", "filled"] as const;

// Drawn again only when what it is given changes: the window redraws far more
// often than the profile does.
export const UserProfilePage = memo(function UserProfilePage({
  host,
  reader,
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
  contribute,
  openMenu,
  accountActions,
  onCopy,
  onNotice,
}: {
  host: Host;
  reader: string;
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
  const editRow = (row: Row) => openEditor(row.section, [row.field], "field");
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
    !sync.uncertain &&
    (!sync.snapshot ||
      sync.snapshot.state === "done" ||
      sync.snapshot.state === "stopped" ||
      sync.snapshot.state === "failed");
  const changePassword = host.profiles?.changePassword;
  const profileActions: PageAction[] = [
    ...(host.censo
      ? [
          action(
            "sync",
            t("desktop.profile.censo.title"),
            "sync",
            () => {
              if (sync.snapshot?.state === "done") sync.dismiss();
              void sync.start();
            },
            { enabled: () => syncReady },
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
      () => {
        if (data) void profile.save(data, { kind: "complete" });
      },
      {
        enabled: () =>
          writable &&
          !!data &&
          data.setup_state !== "complete" &&
          missing.size === 0 &&
          data.valid,
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

  // One stop in the tab order: the detail last focused, else the first.
  let placed = false;
  const navProps = (id: string, kind: "head" | "row", of?: string) => {
    const first = !placed;
    placed = true;
    return {
      "data-nav": id,
      "data-kind": kind,
      "data-of": of,
      tabIndex: (active === null ? first : active === id) ? 0 : -1,
      onFocus: () => setActive(id),
    };
  };

  // ── Summary header ──────────────────────────────────────────────────────
  const total = data ? counts(data) : null;
  const header = data && total && (
    <SummaryHeader
      name={nameOf(data)}
      full={maximized}
      facts={[
        ["idCard", fieldAt(data, "identity.tax_id")],
        ["mail", fieldAt(data, "identity.email")],
        ["phone", fieldAt(data, "contact.contact_person_phone")],
        [
          "place",
          fieldAt(data, "contact.fiscal_address"),
          [
            fieldAt(data, "contact.fiscal_address")?.value,
            fieldAt(data, "contact.postcode")?.value,
          ]
            .filter(Boolean)
            .join(" · "),
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
  const showOptions: { value: Show; label: string }[] = [
    { value: "all", label: t("desktop.profile.view.show_all") },
    { value: "unset", label: t("desktop.profile.view.show_unset") },
    { value: "required", label: t("desktop.profile.view.show_required") },
    { value: "filled", label: t("desktop.profile.view.show_filled") },
  ];
  const groupOptions: { value: Group; label: string }[] = [
    { value: "section", label: t("desktop.profile.view.group_section") },
    { value: "status", label: t("desktop.profile.view.group_status") },
    { value: "none", label: t("desktop.profile.view.group_none") },
  ];
  const sortOptions: { value: Sort; label: string }[] = [
    { value: "form", label: t("desktop.profile.view.sort_form") },
    { value: "missing", label: t("desktop.profile.view.sort_missing") },
    { value: "alpha", label: t("desktop.profile.view.sort_alpha") },
  ];
  const labelOf = <T extends string>(
    options: { value: T; label: string }[],
    value: T,
  ) => options.find((option) => option.value === value)?.label ?? value;
  const sectionsMenu = data && (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          size="sm"
          variant="outline"
          className={cn(maximized && "@2xl/profile:hidden")}
        >
          {t("desktop.profile.sections")}
          <Icon name="chevronDown" size="xs" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="max-w-menu">
        {data.sections.map((section) => (
          <DropdownMenuItem
            key={section.key}
            onSelect={() => goToSection(section.key)}
          >
            <span className="min-w-0 flex-1 truncate">{section.title}</span>
            {requiredSection(section) && <RequiredMark />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
  const toolbar = data && (
    <div
      role="search"
      aria-label={t("desktop.profile.search")}
      className="sticky top-0 z-(--layer-pinned) flex flex-wrap items-center gap-2 border-b bg-background px-4 py-2"
    >
      <div className="relative min-w-0 flex-1 basis-44">
        <Icon
          name="search"
          className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-faint"
        />
        <Input
          ref={searchInput}
          type="search"
          aria-label={t("desktop.profile.search")}
          aria-keyshortcuts="/"
          placeholder={t("desktop.profile.search")}
          className="h-control-sm pr-8 pl-8"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape" && search) {
              event.preventDefault();
              event.stopPropagation();
              setSearch("");
            } else if (event.key === "ArrowDown" || event.key === "Enter") {
              event.preventDefault();
              page.current
                ?.querySelector<HTMLElement>("[data-kind='row']")
                ?.focus();
            }
          }}
        />
        {!search && (
          <Kbd className="absolute top-1/2 right-2 -translate-y-1/2">/</Kbd>
        )}
      </div>
      {maximized ? (
        <>
          <SegmentedControl
            aria-label={t("desktop.profile.view.show")}
            value={show}
            onValueChange={(value) => setView({ show: value as Show })}
          >
            {showOptions.map((option) => (
              <SegmentedControlItem
                key={option.value}
                value={option.value}
                className="px-2.5 text-sm"
              >
                {option.label}
              </SegmentedControlItem>
            ))}
          </SegmentedControl>
          <ChoiceButton
            label={t("desktop.profile.view.group")}
            current={labelOf(groupOptions, group)}
          >
            <MenuChoice
              label={t("desktop.profile.view.group")}
              value={group}
              options={groupOptions}
              onChange={(value: Group) => setView({ group: value })}
            />
          </ChoiceButton>
          <ChoiceButton
            label={t("desktop.profile.view.sort")}
            current={labelOf(sortOptions, sort)}
          >
            <MenuChoice
              label={t("desktop.profile.view.sort")}
              value={sort}
              options={sortOptions}
              onChange={(value: Sort) => setView({ sort: value })}
            />
          </ChoiceButton>
        </>
      ) : (
        <ChoiceButton
          label={t("desktop.profile.view.options")}
          current={show === "all" ? null : labelOf(showOptions, show)}
        >
          <MenuChoice
            label={t("desktop.profile.view.show")}
            value={show}
            options={showOptions}
            onChange={(value: Show) => setView({ show: value })}
          />
          <DropdownMenuSeparator />
          <MenuChoice
            label={t("desktop.profile.view.group")}
            value={group}
            options={groupOptions}
            onChange={(value: Group) => setView({ group: value })}
          />
          <DropdownMenuSeparator />
          <MenuChoice
            label={t("desktop.profile.view.sort")}
            value={sort}
            options={sortOptions}
            onChange={(value: Sort) => setView({ sort: value })}
          />
        </ChoiceButton>
      )}
      {sectionsMenu}
      <IconButton
        size="sm"
        variant="ghost"
        label={t(
          collapsed.size
            ? "desktop.profile.action.expand"
            : "desktop.profile.action.collapse",
        )}
        onClick={() =>
          setView({ collapsed: collapsed.size ? [] : groupKeys() })
        }
      >
        <Icon name={collapsed.size ? "expandAll" : "collapseAll"} />
      </IconButton>
      {profile.loading && (
        <span
          role="status"
          className="flex items-center gap-1.5 text-xs text-muted-foreground"
        >
          <Spinner className="size-icon-xs" />
          {t("desktop.profile.loading")}
        </span>
      )}
      <span className="ml-auto text-xs whitespace-nowrap text-muted-foreground">
        <span aria-hidden="true">* </span>
        {t("desktop.profile.required")}
      </span>
      {filtering && (
        <p
          role="status"
          className="flex w-full items-center gap-2 text-xs text-muted-foreground"
        >
          {t("desktop.profile.view.results", { count: visible.length })}
          <Button
            size="xs"
            variant="ghost"
            onClick={() => {
              setSearch("");
              setView({ show: "all" });
            }}
          >
            <Icon name="close" size="xs" />
            {t("desktop.profile.view.show_all")}
          </Button>
        </p>
      )}
    </div>
  );

  // ── Details ─────────────────────────────────────────────────────────────
  const renderRow = (row: Row, prefix?: string) => {
    const { field } = row;
    const change = incoming.get(field.path);
    const replaced = !!change && !change.preserve && change.incoming !== null;
    const required = marked(row);
    return (
      <li
        key={row.id}
        {...navProps(row.id, "row", row.section.key)}
        aria-label={`${field.label}${required ? ` (${t("desktop.profile.required")})` : ""}: ${
          row.state === "filled"
            ? shownValue(field)
            : row.state === "required"
              ? t("desktop.profile.missing")
              : t("desktop.profile.not_set")
        }`}
        aria-keyshortcuts="Enter"
        onDoubleClick={() => {
          if (writable) editRow(row);
        }}
        onContextMenu={(event: ReactMouseEvent<HTMLElement>) => {
          event.preventDefault();
          event.currentTarget.focus();
          setActive(row.id);
          detailMenu({ x: event.clientX, y: event.clientY });
        }}
        className={cn(
          "group/row relative flex min-h-control-xs cursor-default items-start gap-3 rounded-md px-2 py-0.5 break-inside-avoid outline-none",
          "hover:bg-accent focus-visible:bg-selected focus-visible:ring-2 focus-visible:ring-ring",
          change && "my-1 rounded-l-none border-l-2 border-foreground",
        )}
      >
        <span
          data-part="label"
          className={cn(
            "min-w-0 shrink-0 basis-2/5 pt-px text-muted-foreground",
            row.state === "required" && "font-medium text-foreground",
          )}
        >
          {prefix && (
            <span className="block truncate text-xs text-faint">{prefix}</span>
          )}
          <span className="break-words">{field.label}</span>
          {required && <RequiredMark />}
        </span>
        <span className="min-w-0 flex-1 pt-px break-words">
          <span className={cn(replaced && "line-through decoration-1")}>
            {row.state === "filled" ? (
              <>
                {shownValue(field)}
                {fromAeat.has(field.path) && !change && (
                  <span
                    title={t("desktop.profile.censo.source")}
                    className="ml-2 rounded-sm border px-1 text-2xs font-medium text-muted-foreground"
                  >
                    {t("desktop.profile.censo.incoming")}
                  </span>
                )}
              </>
            ) : row.state === "required" ? (
              <span className="font-medium text-foreground italic">
                {t("desktop.profile.missing")}
              </span>
            ) : (
              <Unset />
            )}
          </span>
          {change && (
            <span className="mt-0.5 block text-sm">
              <span className="mr-1.5 rounded-sm border border-border-strong px-1 text-xs font-medium">
                {t("desktop.profile.censo.incoming")}
              </span>
              <span className={cn(!replaced && "text-muted-foreground")}>
                {change.incoming ?? "–"}
              </span>
              <span className="ml-2 text-xs text-muted-foreground italic">
                {t(
                  change.preserve
                    ? "desktop.profile.censo.preserve"
                    : change.incoming === null
                      ? "desktop.profile.censo.absent"
                      : "desktop.profile.censo.adopt",
                )}
              </span>
            </span>
          )}
        </span>
        <button
          type="button"
          tabIndex={-1}
          disabled={!writable}
          aria-label={t("desktop.profile.edit_field", { field: field.label })}
          onClick={() => editRow(row)}
          className={cn(
            "flex size-control-xs shrink-0 cursor-pointer items-center justify-center rounded-sm text-muted-foreground opacity-0 hover:bg-selected hover:text-foreground disabled:cursor-default",
            "group-hover/row:opacity-100 group-focus-visible/row:opacity-100",
          )}
        >
          <Icon name="edit" size="xs" />
        </button>
      </li>
    );
  };

  const card = ({
    key,
    title,
    required,
    meta,
    extra,
    children,
    sectionKey,
  }: {
    key: string;
    title: string;
    required?: boolean;
    meta?: string;
    extra?: ReactNode;
    children: ReactNode;
    sectionKey?: string;
  }) => {
    const open = !collapsed.has(key);
    return (
      <section
        key={key}
        data-section={sectionKey}
        aria-labelledby={`profile-title-${key}`}
        className="group/section scroll-mt-14 overflow-hidden rounded-lg border bg-card"
      >
        <h3 className="flex min-h-control-md items-center gap-2 border-b bg-chrome pr-2 pl-1">
          <button
            type="button"
            {...navProps(`head:${key}`, "head")}
            id={`profile-title-${key}`}
            aria-expanded={open}
            aria-controls={`profile-body-${key}`}
            onClick={() => toggle(key)}
            className="flex min-w-0 flex-1 cursor-pointer items-center gap-1.5 rounded-sm px-1.5 py-1 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Icon name={open ? "chevronDown" : "forward"} />
            <span className="truncate font-semibold text-foreground">
              {title}
            </span>
            {required && <RequiredMark />}
          </button>
          {extra}
          {meta && (
            <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
              {meta}
            </span>
          )}
        </h3>
        <div id={`profile-body-${key}`} hidden={!open}>
          {children}
        </div>
      </section>
    );
  };

  const sectionMeta = (section: ProfileSection) => {
    const c = sectionCounts(section, missing);
    const needed = c.missing
      ? t("desktop.profile.required_missing", { count: c.missing })
      : "";
    return section.repeatable
      ? [
          c.entries
            ? t("desktop.profile.entries_count", { count: c.entries })
            : t("desktop.profile.entries_none"),
          needed,
        ]
          .filter(Boolean)
          .join(" · ")
      : [`${c.filled}/${c.total}`, needed].filter(Boolean).join(" · ");
  };

  const detailList = (rows: Row[], prefix = false) => (
    <ul className={cn("gap-x-6 p-1.5", maximized && "@4xl/profile:columns-2")}>
      {rows.map((row) =>
        renderRow(row, prefix ? row.section.title : undefined),
      )}
    </ul>
  );

  const entriesCard = (section: ProfileSection) => {
    const rows = entries(section);
    const shownRows = needle
      ? rows.filter(([, fields]) =>
          profileText(
            [
              section.title,
              ...fields.map((field) =>
                field.masked ? "" : (fieldValue(field) ?? ""),
              ),
            ].join(" "),
          ).includes(needle),
        )
      : rows;
    if (needle && !shownRows.length) return null;
    const anyRequired = section.fields.some((field) => field.required);
    return card({
      key: section.key,
      sectionKey: section.key,
      title: section.title,
      meta: sectionMeta(section),
      extra: (
        <Button
          size="xs"
          variant="ghost"
          disabled={!writable}
          className="opacity-0 group-focus-within/section:opacity-100 group-hover/section:opacity-100 focus-visible:opacity-100"
          onClick={() => editEntry(section, null)}
        >
          <Icon name="plus" size="xs" />
          {t("desktop.profile.add")}
        </Button>
      ),
      children: (
        <div className="p-1.5">
          {shownRows.length ? (
            <ul>
              {shownRows.map(([entry, fields], index) => {
                const [lead, ...rest] = fields;
                const id = `entry:${section.key}:${entry}`;
                const needs = fields.filter((field) => missing.has(field.path));
                return (
                  <li
                    key={entry}
                    {...navProps(id, "row", section.key)}
                    aria-label={`${index + 1}. ${(lead && shownValue(lead)) || t("desktop.profile.not_set")}`}
                    aria-keyshortcuts="Enter Delete"
                    onDoubleClick={() => {
                      if (writable) editEntry(section, entry);
                    }}
                    onContextMenu={(event) => {
                      event.preventDefault();
                      event.currentTarget.focus();
                      setActive(id);
                      detailMenu({ x: event.clientX, y: event.clientY });
                    }}
                    className="group/row flex items-center gap-3 rounded-md px-2 py-1 outline-none hover:bg-accent focus-visible:bg-selected focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <span className="w-5 shrink-0 text-right text-xs text-faint tabular-nums">
                      {index + 1}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-foreground">
                        {(lead && shownValue(lead)) || <Unset />}
                      </span>
                      <span className="block truncate text-sm text-muted-foreground">
                        {rest
                          .map((field) =>
                            field.value
                              ? `${field.label}: ${shownValue(field)}`
                              : null,
                          )
                          .filter(Boolean)
                          .join(" · ") || "–"}
                      </span>
                      {needs.length > 0 && (
                        <span className="block text-sm font-medium text-foreground italic">
                          {t("desktop.profile.missing")}:{" "}
                          {needs.map((field) => field.label).join(", ")}
                        </span>
                      )}
                    </span>
                    <span className="flex shrink-0 gap-0.5 opacity-0 group-hover/row:opacity-100 group-focus-visible/row:opacity-100">
                      <IconButton
                        size="xs"
                        variant="ghost"
                        tabIndex={-1}
                        disabled={!writable}
                        label={t("desktop.profile.action.edit_entry")}
                        onClick={() => editEntry(section, entry)}
                      >
                        <Icon name="edit" size="xs" />
                      </IconButton>
                      <IconButton
                        size="xs"
                        variant="ghost"
                        tabIndex={-1}
                        disabled={!writable}
                        label={t("desktop.profile.remove")}
                        onClick={() => removeEntry(section, entry)}
                      >
                        <Icon name="trash" size="xs" />
                      </IconButton>
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="px-2 py-1.5 text-muted-foreground">
              {t("desktop.profile.entries_none")}
              {anyRequired && (
                <span className="ml-2 text-xs">
                  {t("desktop.profile.entry_required")}
                </span>
              )}
            </p>
          )}
        </div>
      ),
    });
  };

  // Entries are listed with the details they belong beside, except where
  // the person asked only for what is missing.
  const listsEntries = show === "all" || show === "filled";
  let body: ReactNode = null;
  if (data && group === "section")
    body = data.sections.map((section) => {
      if (section.repeatable) return listsEntries ? entriesCard(section) : null;
      const rows = visible.filter((row) => row.section.key === section.key);
      if (!rows.length) return null;
      return card({
        key: section.key,
        sectionKey: section.key,
        title: section.title,
        required: requiredSection(section),
        meta: sectionMeta(section),
        children: detailList(rows),
      });
    });
  else if (data && group === "status")
    body = [
      ...STATUS_GROUPS.map((state) => {
        const rows = visible.filter((row) => row.state === state);
        if (!rows.length) return null;
        return card({
          key: `status-${state}`,
          title: t(`desktop.profile.view.status_${state}`),
          required: state === "required",
          meta: String(rows.length),
          children: detailList(rows, true),
        });
      }),
      ...(listsEntries
        ? data.sections.filter((s) => s.repeatable).map(entriesCard)
        : []),
    ];
  else if (data)
    body = [
      visible.length
        ? card({
            key: "all",
            title: t("desktop.profile.view.results", { count: visible.length }),
            children: detailList(visible, true),
          })
        : null,
      ...(listsEntries
        ? data.sections.filter((s) => s.repeatable).map(entriesCard)
        : []),
    ];
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
    <nav
      aria-label={t("desktop.profile.sections")}
      className="hidden w-menu shrink-0 overflow-y-auto border-r py-2 @2xl/profile:block"
    >
      <ul className="px-2">
        {data.sections.map((section) => {
          const c = sectionCounts(section, missing);
          return (
            <li key={section.key}>
              <button
                type="button"
                aria-current={current === section.key ? "location" : undefined}
                onClick={() => goToSection(section.key)}
                className={cn(
                  "flex w-full cursor-pointer items-baseline gap-2 rounded-md px-2 py-1 text-left text-sm text-muted-foreground hover:bg-accent hover:text-foreground",
                  "aria-[current]:bg-selected aria-[current]:font-medium aria-[current]:text-foreground",
                )}
              >
                <span className="flex min-w-0 flex-1 gap-1">
                  <span className="truncate">{section.title}</span>
                  {requiredSection(section) && <RequiredMark />}
                </span>
                <span className="shrink-0 text-xs text-faint tabular-nums">
                  {section.repeatable ? c.entries : `${c.filled}/${c.total}`}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
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
              {body}
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

function RequiredMark() {
  const t = useStrings();
  return (
    <>
      <span aria-hidden="true" className="font-semibold text-foreground">
        {" "}
        *
      </span>
      <span className="sr-only"> ({t("desktop.profile.required")})</span>
    </>
  );
}

function Unset() {
  const t = useStrings();
  return (
    <span className="text-faint" title={t("desktop.profile.not_set")}>
      –<span className="sr-only">{t("desktop.profile.not_set")}</span>
    </span>
  );
}

function SummaryHeader({
  name,
  full,
  facts,
  missing,
  filled,
  total,
  missingCount,
  onMissing,
  actions,
}: {
  name: string;
  full: boolean;
  /** Icon, field and, where it differs from the field's, the value shown. */
  facts: [IconName, ProfileField | undefined, string?][];
  missing: Set<string>;
  filled: number;
  total: number;
  missingCount: number;
  onMissing(): void;
  actions: ReactNode;
}) {
  const t = useStrings();
  const letters = initials(name);
  return (
    <header
      className={cn(
        "flex items-start gap-3 border-b px-4",
        full ? "gap-4 py-4" : "py-3",
      )}
    >
      <div
        aria-hidden="true"
        className={cn(
          "flex shrink-0 items-center justify-center rounded-full border border-border-strong bg-secondary font-semibold text-foreground select-none",
          full ? "size-16 text-lg" : "size-10 text-base",
        )}
      >
        {letters || <Icon name="person" size={full ? "lg" : "md"} />}
      </div>
      <div className="min-w-0 flex-1">
        <h3
          className={cn(
            "truncate font-semibold text-foreground",
            full ? "text-lg" : "text-md",
          )}
        >
          {name || t("desktop.profile.unnamed")}
        </h3>
        <dl
          className={cn(
            "mt-0.5 flex min-w-0 flex-wrap gap-x-4 gap-y-0.5 text-sm text-muted-foreground",
            !full && "gap-x-3",
          )}
        >
          {facts.map(([icon, field, shown], at) => {
            if (!field) return null;
            const value = shown || shownValue(field);
            if (!full && at >= 2 && !value) return null;
            return (
              <div
                key={field.path}
                className="flex min-w-0 items-center gap-1.5"
                title={field.label}
              >
                <dt className="flex items-center">
                  <Icon name={icon} />
                  <span className="sr-only">{field.label}</span>
                </dt>
                <dd className="min-w-0 truncate text-foreground">
                  {value ||
                    (missing.has(field.path) ? (
                      <span className="font-medium italic">
                        {t("desktop.profile.missing")}
                      </span>
                    ) : (
                      <Unset />
                    ))}
                </dd>
              </div>
            );
          })}
        </dl>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className="flex items-center gap-2">
            <Progress
              value={filled}
              max={total || 1}
              aria-label={t("desktop.profile.progress", { filled, total })}
              className="w-24 text-foreground"
            />
            <span className="tabular-nums">
              {t("desktop.profile.progress", { filled, total })}
            </span>
          </span>
          {missingCount ? (
            <button
              type="button"
              className="cursor-pointer font-medium text-foreground underline-offset-2 hover:underline"
              onClick={onMissing}
            >
              <span aria-hidden="true">* </span>
              {t("desktop.profile.required_missing", { count: missingCount })}
            </button>
          ) : (
            <span className="flex items-center gap-1">
              <Icon name="tick" size="xs" />
              {t("desktop.profile.required_done")}
            </span>
          )}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">{actions}</div>
    </header>
  );
}

function ChoiceButton({
  label,
  current,
  children,
}: {
  label: string;
  current: string | null;
  children: ReactNode;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="sm" variant="outline" className="gap-1">
          <span className={cn(current && "text-muted-foreground")}>
            {label}
            {current && ":"}
          </span>
          {current && <span>{current}</span>}
          <Icon
            name="chevronDown"
            size="xs"
            className="text-muted-foreground"
          />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">{children}</DropdownMenuContent>
    </DropdownMenu>
  );
}

function MenuChoice<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange(value: T): void;
}) {
  return (
    <DropdownMenuGroup label={label}>
      <DropdownMenuRadioGroup
        value={value}
        onValueChange={(next) => onChange(next as T)}
      >
        {options.map((option) => (
          <DropdownMenuRadioItem key={option.value} value={option.value}>
            {option.label}
          </DropdownMenuRadioItem>
        ))}
      </DropdownMenuRadioGroup>
    </DropdownMenuGroup>
  );
}
