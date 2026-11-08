import type { MouseEvent as ReactMouseEvent, ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { facts, labelled, listed, noted } from "../../shell/compose";
import type { CensoSnapshot } from "../../shell/profileCenso";
import {
  entries,
  marked,
  requiredSection,
  sectionCounts,
  shownValue,
  type Group,
  type Row,
} from "../../shell/profileRows";
import { useStrings } from "../../shell/strings";
import {
  fieldValue,
  profileText,
  type ProfileSection,
  type UserProfile,
} from "../../shell/userProfile";
import { RequiredMark, Unset } from "./ProfileMarks";

/** The status groups, in the order the page shows them. */
export const STATUS_GROUPS = ["required", "unset", "filled"] as const;

/**
 * The profile's details as the page shows them: grouped by section, by
 * status or not at all, each group a card that folds, and each repeatable
 * section's entries in a card of their own. The keyboard has one stop among
 * them: the detail last focused, else the first.
 */
export function ProfileDetails({
  data,
  visible,
  group,
  needle,
  listsEntries,
  collapsed,
  onToggle,
  missing,
  incoming,
  fromAeat,
  writable,
  maximized,
  active,
  onActive,
  onEditRow,
  onEditEntry,
  onRemoveEntry,
  onMenu,
}: {
  data: UserProfile;
  /** The details the view shows, in its order. */
  visible: Row[];
  group: Group;
  /** The search, as profile text; empty where none. */
  needle: string;
  /** Entries are listed beside the details. */
  listsEntries: boolean;
  collapsed: ReadonlySet<string>;
  onToggle(key: string): void;
  /** The paths of the required details still missing. */
  missing: Set<string>;
  /** What a Censo review brings, by path. */
  incoming: ReadonlyMap<string, CensoSnapshot["fields"][number]>;
  /** The paths whose values the last Censo pull saved. */
  fromAeat: ReadonlySet<string>;
  writable: boolean;
  maximized: boolean;
  /** The detail last focused. */
  active: string | null;
  onActive(id: string): void;
  onEditRow(row: Row): void;
  onEditEntry(section: ProfileSection, entry: string | null): void;
  onRemoveEntry(section: ProfileSection, entry: string): void;
  /** Opens the focused detail's menu at a point. */
  onMenu(at: { x: number; y: number; height?: number }): void;
}) {
  const t = useStrings();
  let placed = false;
  const navProps = (id: string, kind: "head" | "row", of?: string) => {
    const first = !placed;
    placed = true;
    return {
      "data-nav": id,
      "data-kind": kind,
      "data-of": of,
      tabIndex: (active === null ? first : active === id) ? 0 : -1,
      onFocus: () => onActive(id),
    };
  };
  const renderRow = (row: Row, prefix?: string) => {
    const { field } = row;
    const change = incoming.get(field.path);
    const replaced = !!change && !change.preserve && change.incoming !== null;
    const required = marked(row);
    return (
      <li
        key={row.id}
        {...navProps(row.id, "row", row.section.key)}
        aria-label={labelled(
          t,
          required
            ? noted(t, field.label, t("desktop.profile.required"))
            : field.label,
          row.state === "filled"
            ? (shownValue(field) ?? t("desktop.profile.not_set"))
            : row.state === "required"
              ? t("desktop.profile.missing")
              : t("desktop.profile.not_set"),
        )}
        aria-keyshortcuts="Enter"
        onDoubleClick={() => {
          if (writable) onEditRow(row);
        }}
        onContextMenu={(event: ReactMouseEvent<HTMLElement>) => {
          event.preventDefault();
          event.currentTarget.focus();
          onActive(row.id);
          onMenu({ x: event.clientX, y: event.clientY });
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
          onClick={() => onEditRow(row)}
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
            onClick={() => onToggle(key)}
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
      ? facts(t, [
          c.entries
            ? t("desktop.profile.entries_count", { count: c.entries })
            : t("desktop.profile.entries_none"),
          needed,
        ])
      : facts(t, [`${c.filled}/${c.total}`, needed]);
  };

  const detailList = (rows: Row[], prefix = false) => (
    <ul className={cn("gap-x-6 p-1.5", maximized && "@4xl/profile:columns-2")}>
      {rows.map((row) =>
        renderRow(row, prefix ? row.section.title : undefined),
      )}
    </ul>
  );

  /** `blank` is the group of details a section holding no entry stands for,
   * listed where nothing else lists them, so a required one is marked and can
   * be filled in as the first entry. */
  const entriesCard = (section: ProfileSection, blank: Row[] = []) => {
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
          onClick={() => onEditEntry(section, null)}
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
                      if (writable) onEditEntry(section, entry);
                    }}
                    onContextMenu={(event) => {
                      event.preventDefault();
                      event.currentTarget.focus();
                      onActive(id);
                      onMenu({ x: event.clientX, y: event.clientY });
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
                        {facts(
                          t,
                          rest.map((field) =>
                            field.value
                              ? labelled(
                                  t,
                                  field.label,
                                  shownValue(field) ?? "",
                                )
                              : null,
                          ),
                        ) || "–"}
                      </span>
                      {needs.length > 0 && (
                        <span className="block text-sm font-medium text-foreground italic">
                          {labelled(
                            t,
                            t("desktop.profile.missing"),
                            listed(
                              t,
                              needs.map((field) => field.label),
                            ),
                          )}
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
                        onClick={() => onEditEntry(section, entry)}
                      >
                        <Icon name="edit" size="xs" />
                      </IconButton>
                      <IconButton
                        size="xs"
                        variant="ghost"
                        tabIndex={-1}
                        disabled={!writable}
                        label={t("desktop.profile.remove")}
                        onClick={() => onRemoveEntry(section, entry)}
                      >
                        <Icon name="trash" size="xs" />
                      </IconButton>
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <>
              <p className="px-2 py-1.5 text-muted-foreground">
                {t("desktop.profile.entries_none")}
                {anyRequired && (
                  <span className="ml-2 text-xs">
                    {t("desktop.profile.entry_required")}
                  </span>
                )}
              </p>
              {blank.length > 0 && detailList(blank)}
            </>
          )}
        </div>
      ),
    });
  };

  let body: ReactNode;
  if (group === "section")
    body = data.sections.map((section) => {
      if (section.repeatable)
        return listsEntries
          ? entriesCard(
              section,
              visible.filter((row) => row.section.key === section.key),
            )
          : null;
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
  else if (group === "status")
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
        ? data.sections
            .filter((s) => s.repeatable)
            .map((section) => entriesCard(section))
        : []),
    ];
  else
    body = [
      visible.length
        ? card({
            key: "all",
            title: t("desktop.profile.view.results", { count: visible.length }),
            children: detailList(visible, true),
          })
        : null,
      ...(listsEntries
        ? data.sections
            .filter((s) => s.repeatable)
            .map((section) => entriesCard(section))
        : []),
    ];
  return <>{body}</>;
}
