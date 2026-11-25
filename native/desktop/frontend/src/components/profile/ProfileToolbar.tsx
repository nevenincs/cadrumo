import type { ReactNode, RefObject } from "react";
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
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Spinner } from "@/components/ui/spinner";
import type { ProfileView } from "../../shell/layout";
import {
  requiredSection,
  type Group,
  type Show,
  type Sort,
} from "../../shell/profileRows";
import { useStrings } from "../../shell/strings";
import type { ProfileSection } from "../../shell/userProfile";
import { RequiredMark } from "./ProfileMarks";
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

/**
 * The profile page's toolbar: the search over its details, what they show,
 * how they are grouped and sorted, a way to each section, and folding every
 * group at once. Full screen gives each choice a control of its own; the
 * column puts them in one menu.
 */
export function ProfileToolbar({
  sections,
  onGoToSection,
  maximized,
  search,
  onSearch,
  searchInput,
  page,
  show,
  group,
  sort,
  onView,
  collapsedCount,
  onToggleCollapsed,
  loading,
  filtering,
  results,
}: {
  sections: ProfileSection[];
  onGoToSection(key: string): void;
  maximized: boolean;
  search: string;
  onSearch(search: string): void;
  searchInput: RefObject<HTMLInputElement | null>;
  /** The page, whose first detail the search hands the keyboard to. */
  page: RefObject<HTMLElement | null>;
  show: Show;
  group: Group;
  sort: Sort;
  onView(patch: Partial<ProfileView>): void;
  /** How many groups are folded. */
  collapsedCount: number;
  /** Unfolds every group where some are folded, else folds them all. */
  onToggleCollapsed(): void;
  loading: boolean;
  /** A search or a show choice narrows the details. */
  filtering: boolean;
  /** How many details are shown. */
  results: number;
}) {
  const t = useStrings();
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
  const sectionsMenu = (
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
        {sections.map((section) => (
          <DropdownMenuItem
            key={section.key}
            onSelect={() => onGoToSection(section.key)}
          >
            <span className="min-w-0 flex-1 truncate">{section.title}</span>
            {requiredSection(section) && <RequiredMark />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
  return (
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
          placeholder={t("desktop.profile.search_placeholder")}
          className="h-control-sm pr-8 pl-8"
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape" && search) {
              event.preventDefault();
              event.stopPropagation();
              onSearch("");
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
            onValueChange={(value) => onView({ show: value as Show })}
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
              onChange={(value: Group) => onView({ group: value })}
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
              onChange={(value: Sort) => onView({ sort: value })}
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
            onChange={(value: Show) => onView({ show: value })}
          />
          <DropdownMenuSeparator />
          <MenuChoice
            label={t("desktop.profile.view.group")}
            value={group}
            options={groupOptions}
            onChange={(value: Group) => onView({ group: value })}
          />
          <DropdownMenuSeparator />
          <MenuChoice
            label={t("desktop.profile.view.sort")}
            value={sort}
            options={sortOptions}
            onChange={(value: Sort) => onView({ sort: value })}
          />
        </ChoiceButton>
      )}
      {sectionsMenu}
      <IconButton
        size="sm"
        variant="ghost"
        label={t(
          collapsedCount
            ? "desktop.profile.action.expand"
            : "desktop.profile.action.collapse",
        )}
        onClick={onToggleCollapsed}
      >
        <Icon name={collapsedCount ? "expandAll" : "collapseAll"} />
      </IconButton>
      {loading && (
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
          {t("desktop.profile.view.results", { count: results })}
          <Button
            size="xs"
            variant="ghost"
            onClick={() => {
              onSearch("");
              onView({ show: "all" });
            }}
          >
            <Icon name="close" size="xs" />
            {t("desktop.profile.view.show_all")}
          </Button>
        </p>
      )}
    </div>
  );
}
