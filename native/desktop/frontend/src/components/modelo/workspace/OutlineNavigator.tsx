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
  PublicModeloFormField,
  PublicModeloFormSection,
} from "../../../shell/modeloContract/modeloWorkForm";
import type { PublicModeloWorkForm } from "../../../shell/modeloContract/modeloWorkFormPart2";
import { useStrings, type Translate } from "../../../shell/strings";
import { calm } from "../form/FieldRow";
import {
  ANSWERS_PAGE,
  UNPLACED_PAGE,
  WORKING_FIGURES_PAGE,
} from "../form/session";

// The form's outline as the read model serves it: its groups in order, the
// sections each gathers, and what each still asks of the filer. Nothing here
// knows a modelo. A declaration whose layout declares no outline is served
// one group per page, and is drawn the same way. Applicability and counts are
// the read's; the navigator only hides or folds what the filer asks it to.
// The two lists the form keeps apart from its pages are groups of their own,
// with no sections: choosing one jumps to the page the form draws that list on.

/** One section of a group, with what the read says of it. */
type OutlineSection = {
  id: string;
  heading: ModeloFormText;
  counts: ModeloFormCounts;
  applies: boolean | null;
};

/** One group with the sections the read places in it, and whether any box
 * of them is kept in the profile. */
type OutlineGroup = {
  group: ModeloFormOutlineGroup;
  sections: OutlineSection[];
  inProfile: boolean;
  /** The page the form draws a list kept apart from its pages on, which a
   * choice of the group jumps to; null for a group of sections. */
  target: string | null;
};

/** The page the form draws the boxes of a group on, when the group gathers a
 * list kept apart from the pages. */
function apartPage(group: ModeloFormOutlineGroup): string | null {
  switch (group.kind) {
    case "unplaced":
      return UNPLACED_PAGE;
    case "working_figures":
      return WORKING_FIGURES_PAGE;
    case "answers":
      return ANSWERS_PAGE;
    default:
      return null;
  }
}

/** Every box a section draws. */
function fieldsOf(section: PublicModeloFormSection): PublicModeloFormField[] {
  return section.blocks.flatMap((block) => {
    switch (block.kind) {
      case "field":
        return [block.field];
      case "binding_inputs":
        return block.fields;
      case "grid":
        return block.rows.flatMap((row) =>
          row.cells.flatMap((cell) => (cell.field ? [cell.field] : [])),
        );
      default:
        return [];
    }
  });
}

/** The outline's groups with their sections looked up on the pages; a
 * section id the pages do not hold is not drawn. */
function outlineOf(form: PublicModeloWorkForm): OutlineGroup[] {
  const sections = new Map<string, OutlineSection>();
  const kept = new Set<string>();
  for (const page of form.pages)
    for (const section of page.sections) {
      sections.set(section.id, {
        id: section.id,
        heading: section.heading,
        counts: section.counts,
        applies: section.applies,
      });
      // A box says where its source is kept and corrected, as the form's own
      // rows do when they offer the way there.
      if (
        fieldsOf(section).some(
          (field) => field.bindings[0]?.policy.surface === "profile",
        )
      )
        kept.add(section.id);
    }
  return form.outline.map((group) => ({
    group,
    sections: group.section_ids.flatMap((id) => {
      const section = sections.get(id);
      return section ? [section] : [];
    }),
    inProfile: group.section_ids.some((id) => kept.has(id)),
    target: apartPage(group),
  }));
}

/** A treeitem's id, kept apart for groups, sections and the way to where a
 * group's boxes are kept. */
const itemId = (kind: "group" | "section" | "profile", id: string) =>
  `${kind}:${id}`;

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
  onOpenProfile,
}: {
  form: PublicModeloWorkForm;
  /** The section the form shows the filer at, marked as the current one. */
  currentSectionId: string | null;
  onJump(sectionId: string): void;
  /** Opens the profile, where a group's profile-kept boxes are corrected;
   * absent where the window has no profile page. */
  onOpenProfile?: () => void;
}) {
  const t = useStrings();
  const base = useId();
  const groups = useMemo(() => outlineOf(form), [form]);
  const [open, setOpen] = useState<ReadonlySet<string>>(
    () =>
      new Set(
        groups
          .filter(
            ({ group, target }) => target === null && group.applies !== false,
          )
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
  for (const { group, sections, inProfile, target } of shownGroups) {
    const groupItem = itemId("group", group.id);
    visible.push({ id: groupItem, parent: null });
    if (target === null && open.has(group.id)) {
      for (const section of sections)
        visible.push({ id: itemId("section", section.id), parent: groupItem });
      if (inProfile && onOpenProfile)
        visible.push({ id: itemId("profile", group.id), parent: groupItem });
    }
  }
  const currentEntry = currentSectionId
    ? groups.find(
        ({ group, target }) =>
          group.section_ids.includes(currentSectionId) ||
          target === currentSectionId,
      )
    : undefined;
  const currentGroup = currentEntry?.group.id;
  // The row that marks where the form is: a section, or the group of a list
  // kept apart, which has no sections.
  const currentItemId = !currentSectionId
    ? null
    : currentEntry?.target === currentSectionId
      ? itemId("group", currentEntry.group.id)
      : itemId("section", currentSectionId);

  const [focused, setFocused] = useState<string | null>(null);
  const tabStop =
    focused && visible.some((item) => item.id === focused)
      ? focused
      : currentItemId && visible.some((item) => item.id === currentItemId)
        ? currentItemId
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
  const jump = (sectionId: string, row = itemId("section", sectionId)) => {
    setFocused(row);
    onJump(sectionId);
  };
  // Whether a group gathers sections, which fold, and not a list kept apart.
  const groupHolds = (groupId: string) =>
    groups.find(({ group }) => group.id === groupId)?.target === null;
  const jumpApart = (groupId: string) => {
    const target = groups.find(({ group }) => group.id === groupId)?.target;
    if (target) jump(target, itemId("group", groupId));
    return target != null;
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
          if (kind === "group" && groupHolds(id)) {
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
          if (kind === "group") {
            if (!jumpApart(id)) toggle(id);
          } else if (kind === "profile") onOpenProfile?.();
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

  const foldable = shownGroups.filter(({ target }) => target === null);
  const allOpen = foldable.every(({ group }) => open.has(group.id));
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
                : new Set(foldable.map(({ group }) => group.id)),
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
        {shownGroups.map(({ group, sections, inProfile, target }) => {
          const groupItem = itemId("group", group.id);
          const apart = target !== null;
          const expanded = !apart && open.has(group.id);
          const childList = `${base}-${group.id}-sections`;
          return (
            // The treeitem is the row alone, so its name is the row's words
            // and not its sections'; its sections are owned beside it.
            <li key={group.id} role="none">
              <div
                ref={keep(groupItem)}
                role="treeitem"
                aria-level={1}
                aria-expanded={apart ? undefined : expanded}
                aria-owns={expanded ? childList : undefined}
                aria-current={
                  currentGroup === group.id && (apart || !expanded)
                    ? "location"
                    : undefined
                }
                data-outline-group={group.id}
                data-outline-kind={group.kind}
                data-applies={String(group.applies)}
                tabIndex={tabStop === groupItem ? 0 : -1}
                onFocus={() => setFocused(groupItem)}
                onClick={() =>
                  apart ? jump(target, groupItem) : toggle(group.id)
                }
                className={cn(
                  row,
                  apart ? "cursor-pointer" : "cursor-default",
                  "font-medium",
                  group.applies === false ? "text-faint" : "text-foreground",
                  apart && currentGroup === group.id && "bg-selected",
                )}
              >
                <Icon
                  name={
                    apart ? "forward" : expanded ? "chevronDown" : "forward"
                  }
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
                  {inProfile && onOpenProfile && (
                    <li role="none">
                      <div
                        ref={keep(itemId("profile", group.id))}
                        role="treeitem"
                        aria-level={2}
                        data-outline-profile={group.id}
                        tabIndex={
                          tabStop === itemId("profile", group.id) ? 0 : -1
                        }
                        onFocus={() => setFocused(itemId("profile", group.id))}
                        onClick={onOpenProfile}
                        className={cn(
                          row,
                          "cursor-pointer pl-7 text-muted-foreground hover:text-foreground",
                        )}
                      >
                        <span className="min-w-0 flex-1 truncate">
                          {t("desktop.profile.open_from_form")}
                        </span>
                        <Icon
                          name="forward"
                          size="xs"
                          className="shrink-0 text-faint"
                        />
                      </div>
                    </li>
                  )}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
