import { Select as SelectPrimitive } from "radix-ui";
import { cn } from "@/components/ui/cn";
import { Icon } from "@/components/ui/icon";
import { useStrings } from "../../shell/strings";
import { ProviderMark } from "./ProviderMark";
import type { ProviderOption, ProviderWay } from "./types";

/** One row of the list: a lane of the catalog, named as the catalog names it
 * and drawn with its provider's own mark. */
type Entry = { provider: ProviderOption; way: ProviderWay };

/** Every lane the catalog serves, in the order it serves them. */
const entriesOf = (providers: readonly ProviderOption[]): Entry[] =>
  providers.flatMap((provider) =>
    provider.ways.map((way): Entry => ({ provider, way })),
  );

/**
 * The provider list: a select with one row for each lane the catalog serves,
 * each with its provider's mark and the name the catalog gives it. A lane that
 * cannot be chosen stays in the list, disabled, saying why. Nothing here
 * words a lane beyond that: where two lanes of one provider carry the same
 * name, the list shows the same name twice. It is a custom list because a
 * platform select cannot draw a mark in a row.
 */
export function ProviderSelect({
  id,
  providers,
  value,
  onChange,
}: {
  /** Ties the control to its label. */
  id: string;
  providers: readonly ProviderOption[];
  /** The lane chosen, by `ProviderWay.id`. */
  value: string;
  onChange: (wayId: string) => void;
}) {
  const t = useStrings();
  const entries = entriesOf(providers);
  const chosen = entries.find((entry) => entry.way.id === value);
  return (
    <SelectPrimitive.Root
      value={value}
      onValueChange={onChange}
      disabled={entries.length === 0}
    >
      <SelectPrimitive.Trigger
        id={id}
        data-slot="provider-select"
        className="relative flex h-control-sm w-full min-w-0 cursor-pointer items-center rounded-md border border-input bg-card pr-7 pl-2 text-left text-base text-foreground transition-colors disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span className="flex min-w-0 flex-1 items-center gap-2">
          <SelectPrimitive.Value
            placeholder={t("desktop.agent.choose_provider")}
          >
            {chosen && (
              <span className="flex min-w-0 items-center gap-2">
                <ProviderMark provider={chosen.provider.id} size="md" />
                <span className="truncate">{chosen.provider.name}</span>
              </span>
            )}
          </SelectPrimitive.Value>
        </span>
        <Icon
          name="chevronDown"
          className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 text-faint"
        />
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={4}
          collisionPadding={8}
          className={cn(
            "z-(--layer-menu) max-h-(--radix-select-content-available-height) w-(--radix-select-trigger-width) max-w-(--radix-select-content-available-width) origin-(--radix-select-content-transform-origin) overflow-hidden rounded-lg border bg-popover text-popover-foreground shadow-overlay",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0",
          )}
        >
          <SelectPrimitive.Viewport className="p-1">
            {entries.map(({ provider, way }) => (
              <SelectPrimitive.Item
                key={way.id}
                value={way.id}
                textValue={provider.name}
                disabled={!way.selectable}
                data-way={way.id}
                className={cn(
                  "relative flex min-h-control-sm cursor-pointer items-center gap-2 rounded-sm px-2.5 py-1 text-base outline-none select-none",
                  "data-[disabled]:pointer-events-none data-[disabled]:opacity-60",
                  "data-[highlighted]:bg-selected data-[highlighted]:text-accent-foreground",
                  "before:absolute before:inset-y-1.5 before:left-0 before:w-0.5 before:rounded-xs before:bg-brand before:opacity-0 data-[highlighted]:before:opacity-100",
                  "forced-colors:data-[highlighted]:bg-[Highlight] forced-colors:data-[highlighted]:text-[HighlightText]",
                )}
              >
                <ProviderMark provider={provider.id} size="md" />
                {/* The row is drawn in the system's highlight colours in a
                    forced-colours window; its text takes them itself, or the
                    browser lays a plate of the page colour behind it. */}
                <span className="grid min-w-0 flex-1 forced-colors:in-data-[highlighted]:forced-color-adjust-none forced-colors:in-data-[highlighted]:text-[HighlightText]">
                  <SelectPrimitive.ItemText>
                    {provider.name}
                  </SelectPrimitive.ItemText>
                  {!way.selectable && (
                    <span className="text-sm text-muted-foreground in-data-[highlighted]:text-accent-foreground">
                      {way.unavailableReason ?? t("desktop.agent.unavailable")}
                    </span>
                  )}
                </span>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}
