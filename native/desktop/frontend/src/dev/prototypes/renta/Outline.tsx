import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Switch } from "@/components/ui/switch";
import { useStrings } from "@/shell/strings";
import type {
  Attention,
  Outline as OutlineData,
  ServedSection,
} from "./fixtures";

// The section navigator over a long form. "As served" lists the pages and
// sections the generated layout serves today, with their headings as served
// and disclosed as technical where the layout has no reviewed one. "Proposed"
// groups the same sections under an outline the backend would serve. Every
// count is one the fixture carries; the navigator counts nothing itself.

export type OutlineMode = "served" | "proposed";

function Counts({ attention }: { attention: Attention | undefined }) {
  const t = useStrings();
  if (!attention) return null;
  return (
    <span className="flex shrink-0 items-center gap-1.5 text-xs tabular-nums">
      {attention.failed > 0 && (
        <span className="inline-flex items-center gap-0.5 text-destructive">
          <Icon name="alert" size="xs" />
          <span className="sr-only">
            {t("desktop.renta.proto.nav.failed", { count: attention.failed })}
          </span>
          <span aria-hidden="true">{attention.failed}</span>
        </span>
      )}
      {attention.needs_you > attention.failed && (
        <span className="inline-flex items-center gap-0.5 text-warning">
          <Icon name="edit" size="xs" />
          <span className="sr-only">
            {t("desktop.renta.proto.nav.needs_you", {
              count: attention.needs_you,
            })}
          </span>
          <span aria-hidden="true">{attention.needs_you}</span>
        </span>
      )}
    </span>
  );
}

function SectionRow({
  section,
  attention,
  selected,
  onSelect,
}: {
  section: ServedSection;
  attention: Attention | undefined;
  selected: boolean;
  onSelect: () => void;
}) {
  const t = useStrings();
  const technical = section.heading.disclosure === "technical";
  return (
    <button
      type="button"
      aria-current={selected ? "true" : undefined}
      onClick={onSelect}
      className={cn(
        "flex w-full items-center gap-2 rounded-sm px-2 py-1 text-left text-sm hover:bg-accent",
        selected && "bg-accent font-medium",
      )}
    >
      <span
        className={cn(
          "min-w-0 flex-1 truncate",
          technical && "font-mono text-xs text-muted-foreground",
        )}
        title={technical ? t("desktop.renta.proto.nav.technical") : undefined}
      >
        {section.heading.text}
      </span>
      <span className="text-2xs text-faint tabular-nums">
        {t("desktop.renta.proto.nav.boxes", { count: section.counts.total })}
      </span>
      <Counts attention={attention} />
    </button>
  );
}

export function Outline({
  outline,
  mode,
  onModeChange,
  selected,
  onSelect,
  onlyAttention,
  onOnlyAttentionChange,
}: {
  outline: OutlineData;
  mode: OutlineMode;
  onModeChange: (mode: OutlineMode) => void;
  selected: string | null;
  onSelect: (sectionId: string) => void;
  onlyAttention: boolean;
  onOnlyAttentionChange: (on: boolean) => void;
}) {
  const t = useStrings();
  const attentionOf = new Map(
    outline.proposed.flatMap((group) =>
      group.sections.map((item) => [item.id, item.attention] as const),
    ),
  );
  const sectionOf = new Map(
    outline.served.flatMap((page) =>
      page.sections.map((section) => [section.id, section] as const),
    ),
  );
  const shown = (id: string) =>
    !onlyAttention || (attentionOf.get(id)?.needs_you ?? 0) > 0;
  return (
    <nav
      aria-label={t("desktop.renta.proto.nav.title")}
      className="flex h-full min-h-0 w-80 shrink-0 flex-col border-r border-border"
    >
      <div className="flex flex-col gap-2 border-b border-border p-3">
        <SegmentedControl
          value={mode}
          onValueChange={(value) => onModeChange(value as OutlineMode)}
          aria-label={t("desktop.renta.proto.nav.title")}
        >
          <SegmentedControlItem value="served">
            {t("desktop.renta.proto.nav.served")}
          </SegmentedControlItem>
          <SegmentedControlItem value="proposed">
            {t("desktop.renta.proto.nav.proposed")}
          </SegmentedControlItem>
        </SegmentedControl>
        <label className="flex items-center gap-2 text-sm">
          <Switch
            checked={onlyAttention}
            onCheckedChange={onOnlyAttentionChange}
          />
          {t("desktop.renta.proto.nav.only_attention")}
        </label>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {mode === "served"
          ? outline.served.map((page) => (
              <section key={page.id} className="mb-3">
                <h3 className="px-2 py-1 font-mono text-xs text-muted-foreground">
                  {page.heading.text}
                </h3>
                {page.sections
                  .filter((section) => shown(section.id))
                  .map((section) => (
                    <SectionRow
                      key={section.id}
                      section={section}
                      attention={attentionOf.get(section.id)}
                      selected={selected === section.id}
                      onSelect={() => onSelect(section.id)}
                    />
                  ))}
              </section>
            ))
          : outline.proposed.map((group) => {
              const items = group.sections.filter((item) => shown(item.id));
              if (items.length === 0) return null;
              return (
                <section key={group.id} className="mb-3">
                  <h3 className="flex items-center justify-between px-2 py-1 text-sm font-semibold">
                    {t(`workspace.renta.outline.${group.id}`)}
                    <Counts attention={group.attention} />
                  </h3>
                  {items.map((item) => {
                    const section = sectionOf.get(item.id);
                    return section ? (
                      <SectionRow
                        key={item.id}
                        section={section}
                        attention={item.attention}
                        selected={selected === item.id}
                        onSelect={() => onSelect(item.id)}
                      />
                    ) : null;
                  })}
                </section>
              );
            })}
      </div>
    </nav>
  );
}
