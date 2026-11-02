import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import type {
  ModeloFormCounts,
  ModeloFormOutlineGroup,
  ModeloFormText,
  PublicModeloWorkForm,
} from "../../../shell/modeloContract";
import { useStrings, type Translate } from "../../../shell/strings";
import { calm } from "../form/FieldRow";

// The form's outline as the read model serves it: its groups in order, the
// sections each gathers, and what each still asks of the filer. Nothing here
// knows a modelo. A declaration whose layout declares no outline is served
// one group per page, and is drawn the same way. Applicability and counts are
// the read's; the navigator only hides or folds what the filer asks it to.

/** One section of a group, with what the read says of it. */
type OutlineSection = {
  id: string;
  heading: ModeloFormText;
  counts: ModeloFormCounts;
  applies: boolean | null;
};

/** One group with the sections the read places in it. */
type OutlineGroup = {
  group: ModeloFormOutlineGroup;
  sections: OutlineSection[];
};

/** The outline's groups with their sections looked up on the pages; a
 * section id the pages do not hold is not drawn. */
function outlineOf(form: PublicModeloWorkForm): OutlineGroup[] {
  const sections = new Map<string, OutlineSection>();
  for (const page of form.pages)
    for (const section of page.sections)
      sections.set(section.id, {
        id: section.id,
        heading: section.heading,
        counts: section.counts,
        applies: section.applies,
      });
  return form.outline.map((group) => ({
    group,
    sections: group.section_ids.flatMap((id) => {
      const section = sections.get(id);
      return section ? [section] : [];
    }),
  }));
}

/** A treeitem's id, kept apart for groups and sections. */
const itemId = (kind: "group" | "section", id: string) => `${kind}:${id}`;

/** What one row of the outline says, for the eye and for the reader. Each
 * state keeps its own mark: what needs the filer, what could not be
 * calculated, what may apply and what does not apply. */
function Marks({
  counts,
  applies,
  t,
}: {
  counts: ModeloFormCounts;
  applies: boolean | null;
  t: Translate;
}) {
  // A part that does not apply asks nothing of the filer.
  const live = applies !== false;
  const needs = live ? counts.needs_you : 0;
  const failed = live ? counts.could_not_calculate : 0;
  const words = [
    needs > 0 && t("desktop.modelo.outline.needs_you", { count: needs }),
    failed > 0 &&
      t("desktop.modelo.outline.could_not_calculate", { count: failed }),
    applies === false && t("desktop.modelo.outline.does_not_apply"),
    applies === null && t("desktop.modelo.outline.may_apply"),
  ].filter((said): said is string => typeof said === "string");
  return (
    <>
      <span className="sr-only">
        {words.map((said) => `, ${said}`).join("")}
      </span>
      <span
        aria-hidden="true"
        className="ml-auto flex shrink-0 items-center gap-1"
      >
        {needs > 0 && (
          <span
            data-mark="needs_you"
            title={t("desktop.modelo.outline.needs_you", { count: needs })}
            className="inline-flex items-center gap-1 rounded-full bg-secondary px-1.5 py-0.5 text-xs font-medium tabular-nums text-secondary-foreground"
          >
            <Icon name="edit" size="xs" className="text-warning" />
            {needs}
          </span>
        )}
        {failed > 0 && (
          <span
            data-mark="could_not_calculate"
            title={t("desktop.modelo.outline.could_not_calculate", {
              count: failed,
            })}
            className="inline-flex items-center gap-1 rounded-full bg-secondary px-1.5 py-0.5 text-xs font-medium tabular-nums text-secondary-foreground"
          >
            <Icon name="alert" size="xs" className="text-destructive" />
            {failed}
          </span>
        )}
        {applies === null && (
          <span
            data-mark="may_apply"
            title={t("desktop.modelo.outline.may_apply")}
            className="inline-flex text-faint"
          >
            <Icon name="unknown" size="xs" />
          </span>
        )}
        {applies === false && (
          <span
            data-mark="does_not_apply"
            className="rounded-full border border-dashed border-border px-1.5 py-0.5 text-xs text-faint"
          >
            {t("desktop.modelo.outline.does_not_apply")}
          </span>
        )}
      </span>
    </>
  );
}

/**
 * The navigator of a long form: the served outline as a tree of groups and
 * their sections, each with the served counts of what needs the filer and
 * what could not be calculated. Groups fold; those that do not apply start
 * folded and can be hidden. Choosing a section jumps the form to it.
 */
export function OutlineNavigator({
  form,
  currentSectionId,
  onJump,
}: {
  form: PublicModeloWorkForm;
  /** The section the form shows the filer at, marked as the current one. */
  currentSectionId: string | null;
  onJump(sectionId: string): void;
}) {
  const t = useStrings();
  const base = useId();
  const groups = useMemo(() => outlineOf(form), [form]);
  const [open, setOpen] = useState<ReadonlySet<string>>(
    () =>
      new Set(
        groups
          .filter(({ group }) => group.applies !== false)
          .map(({ group }) => group.id),
      ),
  );
  const [hideNotApplicable, setHideNotApplicable] = useState(false);
  const anyNotApplicable = groups.some(
    ({ group, sections }) =>
      group.applies === false ||
      sections.some((section) => section.applies === false),
  );

  const shownGroups = hideNotApplicable
    ? groups
        .filter(({ group }) => group.applies !== false)
        .map((entry) => ({
          ...entry,
          sections: entry.sections.filter(
            (section) => section.applies !== false,
          ),
        }))
    : groups;
  // Every row the tree shows, in reading order, for the arrow keys.
  const visible: { id: string; parent: string | null }[] = [];
  for (const { group, sections } of shownGroups) {
    const groupItem = itemId("group", group.id);
    visible.push({ id: groupItem, parent: null });
    if (open.has(group.id))
      for (const section of sections)
        visible.push({ id: itemId("section", section.id), parent: groupItem });
  }
  const currentGroup = currentSectionId
    ? groups.find(({ group }) => group.section_ids.includes(currentSectionId))
        ?.group.id
    : undefined;

  const [focused, setFocused] = useState<string | null>(null);
  const tabStop =
    focused && visible.some((item) => item.id === focused)
      ? focused
      : currentSectionId &&
          visible.some(
            (item) => item.id === itemId("section", currentSectionId),
          )
        ? itemId("section", currentSectionId)
        : (visible[0]?.id ?? null);
  const items = useRef(new Map<string, HTMLDivElement>());
  const moved = useRef(false);
  useEffect(() => {
    if (!moved.current || !tabStop) return;
    moved.current = false;
    items.current.get(tabStop)?.focus();
  }, [tabStop]);
  const focusItem = (id: string | undefined) => {
    if (!id) return;
    moved.current = true;
    setFocused(id);
  };

  const toggle = (groupId: string, to?: boolean) =>
    setOpen((now) => {
      const next = new Set(now);
      if (to ?? !next.has(groupId)) next.add(groupId);
      else next.delete(groupId);
      return next;
    });
  const jump = (sectionId: string) => {
    setFocused(itemId("section", sectionId));
    onJump(sectionId);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLUListElement>) => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const at = visible.findIndex((item) => item.id === tabStop);
    const item = visible[at];
    if (!item) return;
    const [kind, id] = [
      item.id.slice(0, item.id.indexOf(":")),
      item.id.slice(item.id.indexOf(":") + 1),
    ];
    const handled = (() => {
      switch (event.key) {
        case "ArrowDown":
          focusItem(visible[at + 1]?.id);
          return true;
        case "ArrowUp":
          focusItem(visible[at - 1]?.id);
          return true;
        case "Home":
          focusItem(visible[0]?.id);
          return true;
        case "End":
          focusItem(visible.at(-1)?.id);
          return true;
        case "ArrowRight":
          if (kind === "group") {
            if (!open.has(id)) toggle(id, true);
            else if (visible[at + 1]?.parent === item.id)
              focusItem(visible[at + 1]?.id);
          }
          return true;
        case "ArrowLeft":
          if (kind === "group") {
            if (open.has(id)) toggle(id, false);
          } else focusItem(item.parent ?? undefined);
          return true;
        case "Enter":
        case " ":
          if (kind === "group") toggle(id);
          else jump(id);
          return true;
        default:
          return false;
      }
    })();
    if (handled) {
      event.preventDefault();
      event.stopPropagation();
    }
  };

  const allOpen = shownGroups.every(({ group }) => open.has(group.id));
  const row =
    "flex w-full min-w-0 items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring";
  const keep = (id: string) => (element: HTMLDivElement | null) => {
    if (element) items.current.set(id, element);
    else items.current.delete(id);
  };

  return (
    <nav
      aria-label={t("desktop.modelo.outline.label")}
      className="flex min-h-0 flex-col"
    >
      <div className="flex items-center justify-end gap-1 px-2 pt-2">
        {anyNotApplicable && (
          <IconButton
            label={t("desktop.modelo.outline.hide_not_applicable")}
            size="xs"
            aria-pressed={hideNotApplicable}
            onClick={() => setHideNotApplicable(!hideNotApplicable)}
          >
            <Icon name={hideNotApplicable ? "eye" : "eyeOff"} />
          </IconButton>
        )}
        <IconButton
          label={t(
            allOpen
              ? "desktop.modelo.outline.collapse_all"
              : "desktop.modelo.outline.expand_all",
          )}
          size="xs"
          onClick={() =>
            setOpen(
              allOpen
                ? new Set()
                : new Set(shownGroups.map(({ group }) => group.id)),
            )
          }
        >
          <Icon name={allOpen ? "collapseAll" : "expandAll"} />
        </IconButton>
      </div>
      <ul
        role="tree"
        aria-label={t("desktop.modelo.outline.label")}
        onKeyDown={onKeyDown}
        className="flex flex-col gap-0.5 p-2"
      >
        {shownGroups.map(({ group, sections }) => {
          const groupItem = itemId("group", group.id);
          const expanded = open.has(group.id);
          const childList = `${base}-${group.id}-sections`;
          return (
            // The treeitem is the row alone, so its name is the row's words
            // and not its sections'; its sections are owned beside it.
            <li key={group.id} role="none">
              <div
                ref={keep(groupItem)}
                role="treeitem"
                aria-level={1}
                aria-expanded={expanded}
                aria-owns={expanded ? childList : undefined}
                aria-current={
                  currentGroup === group.id && !expanded
                    ? "location"
                    : undefined
                }
                data-outline-group={group.id}
                data-applies={String(group.applies)}
                tabIndex={tabStop === groupItem ? 0 : -1}
                onFocus={() => setFocused(groupItem)}
                onClick={() => toggle(group.id)}
                className={cn(
                  row,
                  "cursor-default font-medium",
                  group.applies === false ? "text-faint" : "text-foreground",
                )}
              >
                <Icon
                  name={expanded ? "chevronDown" : "forward"}
                  size="xs"
                  className="shrink-0 text-faint"
                />
                <span className="min-w-0 flex-1 truncate">
                  {calm(group.heading.text)}
                </span>
                <Marks counts={group.counts} applies={group.applies} t={t} />
              </div>
              {expanded && (
                <ul id={childList} role="group" className="flex flex-col">
                  {sections.map((section) => {
                    const sectionItem = itemId("section", section.id);
                    const current = section.id === currentSectionId;
                    return (
                      <li key={section.id} role="none">
                        <div
                          ref={keep(sectionItem)}
                          role="treeitem"
                          aria-level={2}
                          aria-current={current ? "location" : undefined}
                          data-outline-section={section.id}
                          data-applies={String(section.applies)}
                          tabIndex={tabStop === sectionItem ? 0 : -1}
                          onFocus={() => setFocused(sectionItem)}
                          onClick={() => jump(section.id)}
                          title={section.heading.text}
                          className={cn(
                            row,
                            "cursor-pointer pl-7 hover:text-foreground",
                            current
                              ? "bg-selected text-foreground"
                              : section.applies === false
                                ? "text-faint"
                                : "text-muted-foreground",
                          )}
                        >
                          <span className="min-w-0 flex-1 truncate">
                            {calm(section.heading.text)}
                          </span>
                          <Marks
                            counts={section.counts}
                            applies={section.applies}
                            t={t}
                          />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
