import { useLayoutEffect, useRef, useState, type Ref } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../../shell/strings";
import { fittingEntries, type InspectorSection } from "./inspectorModel";

/**
 * The inspector's jump index: a bar of links to its sections, not tabs.
 * The section being read is marked as the current location. What does not
 * fit goes into a More menu, so no entry is ever cut off.
 */
export function JumpIndex({
  sections,
  current,
  onJump,
  names,
  badges,
  firstRef,
}: {
  sections: readonly InspectorSection[];
  current: InspectorSection | null;
  onJump: (section: InspectorSection) => void;
  names: Record<InspectorSection, string>;
  /** A count beside an entry, with what it counts. */
  badges?: Partial<Record<InspectorSection, { count: number; label: string }>>;
  /** The first entry, which Alt+I focuses. */
  firstRef?: Ref<HTMLButtonElement>;
}) {
  const t = useStrings();
  const bar = useRef<HTMLElement>(null);
  const measure = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState(sections.length);
  const chose = useRef<InspectorSection | null>(null);

  // The entries are measured once, laid out off screen at their own width,
  // and fitted again whenever the bar changes width.
  useLayoutEffect(() => {
    const element = bar.current;
    const probe = measure.current;
    if (!element || !probe) return;
    const refit = () => {
      const items = [...probe.children] as HTMLElement[];
      const width = (item: HTMLElement | undefined) =>
        item?.getBoundingClientRect().width ?? 0;
      const widths = items.slice(0, -1).map(width);
      const style = getComputedStyle(element);
      const gap = parseFloat(style.columnGap) || 0;
      // The bar's own padding is not room for an entry.
      const room =
        element.clientWidth -
        (parseFloat(style.paddingLeft) || 0) -
        (parseFloat(style.paddingRight) || 0);
      setFit(fittingEntries(widths, width(items.at(-1)), room, gap));
    };
    refit();
    const observer = new ResizeObserver(refit);
    observer.observe(element);
    return () => observer.disconnect();
  }, [sections, names, badges]);

  const shown = sections.slice(0, fit);
  const rest = sections.slice(fit);
  const entry = (section: InspectorSection, at: number) => {
    const badge = badges?.[section];
    return (
      <Button
        key={section}
        ref={at === 0 ? firstRef : undefined}
        variant="ghost"
        size="xs"
        data-section={section}
        aria-current={current === section ? "location" : undefined}
        // The name keeps the visible words, the count included, and adds what
        // the count counts.
        aria-label={
          badge ? `${names[section]} ${badge.count}, ${badge.label}` : undefined
        }
        className="ledger-jump shrink-0 rounded-none border-b-2 border-transparent aria-[current=location]:border-muted-foreground aria-[current=location]:text-foreground"
        onClick={() => onJump(section)}
      >
        {/* The space keeps the visible text, "Classify 1", the opening
            words of the name below; the flex row does not draw it. */}
        {badge ? `${names[section]} ` : names[section]}
        {badge && (
          <span
            aria-hidden="true"
            className="rounded-full bg-secondary px-1 text-2xs tabular-nums"
          >
            {badge.count}
          </span>
        )}
      </Button>
    );
  };

  return (
    <nav
      ref={bar}
      aria-label={t("desktop.ledger.inspector.index")}
      className="ledger-jump-index relative flex shrink-0 items-end gap-1 overflow-hidden border-b bg-background px-2"
    >
      {shown.map(entry)}
      {rest.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="xs"
              className="ledger-jump-more shrink-0 rounded-none border-b-2 border-transparent aria-[current=location]:border-muted-foreground"
              aria-current={
                current !== null && rest.includes(current)
                  ? "location"
                  : undefined
              }
            >
              {t("desktop.ledger.inspector.more")}
              <Icon name="chevronDown" size="xs" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            // The menu holds the focus while it is open, so a chosen
            // section is jumped to once it has closed; Escape hands the
            // focus back to More.
            onCloseAutoFocus={(event) => {
              const section = chose.current;
              chose.current = null;
              if (!section) return;
              event.preventDefault();
              onJump(section);
            }}
          >
            {rest.map((section) => (
              <DropdownMenuItem
                key={section}
                onSelect={() => {
                  chose.current = section;
                }}
              >
                {names[section]}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
      {/* The same entries, laid out at their own width where no one sees
          or reaches them, to measure what fits. */}
      <div
        ref={measure}
        aria-hidden="true"
        inert
        className="pointer-events-none invisible absolute top-0 left-0 flex gap-1 whitespace-nowrap"
      >
        {sections.map((section) => (
          <Button
            key={section}
            variant="ghost"
            size="xs"
            tabIndex={-1}
            className="shrink-0 border-b-2"
          >
            {names[section]}
            {badges?.[section] && (
              <span className="rounded-full px-1 text-2xs">
                {badges[section].count}
              </span>
            )}
          </Button>
        ))}
        <Button
          variant="ghost"
          size="xs"
          tabIndex={-1}
          className="shrink-0 border-b-2"
        >
          {t("desktop.ledger.inspector.more")}
          <Icon name="chevronDown" size="xs" />
        </Button>
      </div>
    </nav>
  );
}
