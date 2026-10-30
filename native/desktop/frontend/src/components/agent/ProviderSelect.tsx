import { Fragment, useState } from "react";
import { cn } from "@/components/ui/cn";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Icon } from "@/components/ui/icon";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { described, labelled } from "../../shell/compose";
import { useStrings } from "../../shell/strings";
import { ProviderMark } from "./ProviderMark";
import type { ProviderOption, ProviderTransport, ProviderWay } from "./types";

/** One row of the list: a lane of the catalog, named as the catalog names it
 * and distinguished by how it reaches the provider. */
type Entry = { provider: ProviderOption; way: ProviderWay };

/** Every lane the catalog serves, in the order it serves them. */
const entriesOf = (providers: readonly ProviderOption[]): Entry[] =>
  providers.flatMap((provider) =>
    provider.ways.map((way): Entry => ({ provider, way })),
  );

function connectionWords(
  t: ReturnType<typeof useStrings>,
  transport: ProviderTransport,
) {
  return transport === "api"
    ? t("desktop.providers.connection_api")
    : t("desktop.providers.connection_app");
}

/** Keep an entry whose words hold what was typed, as the provider settings
 * search does; a fuzzy match would let a short word like "app" match almost
 * every provider. */
const containsSearch = (
  _value: string,
  search: string,
  keywords?: string[],
): number => {
  const typed = search.trim().toLocaleLowerCase();
  if (!typed) return 1;
  return (keywords ?? []).join(" ").toLocaleLowerCase().includes(typed) ? 1 : 0;
};

/**
 * The provider picker: one searchable row for every connection the catalog
 * serves. Duplicate provider names stay separate, and unavailable choices
 * remain visible with a plain explanation.
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
  const [open, setOpen] = useState(false);
  const entries = entriesOf(providers);
  const chosen = entries.find((entry) => entry.way.id === value);
  const groups = [
    entries.filter(({ way }) => way.selectable),
    entries.filter(({ way }) => !way.selectable),
  ].filter((group) => group.length > 0);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          id={id}
          type="button"
          aria-label={
            chosen
              ? labelled(
                  t,
                  t("desktop.agent.provider"),
                  described(
                    t,
                    chosen.provider.name,
                    connectionWords(t, chosen.way.transport),
                  ),
                )
              : t("desktop.agent.provider")
          }
          data-slot="provider-select"
          disabled={entries.length === 0}
          className="relative flex h-control-sm w-full min-w-0 cursor-pointer items-center rounded-md border border-input bg-card pr-7 pl-2 text-left text-base text-foreground transition-colors disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span className="flex min-w-0 flex-1 items-center gap-2">
            {chosen ? (
              <>
                <ProviderMark provider={chosen.provider.id} size="md" />
                <span className="truncate">{chosen.provider.name}</span>
                <span className="shrink-0 text-sm text-muted-foreground">
                  {connectionWords(t, chosen.way.transport)}
                </span>
              </>
            ) : (
              <span className="text-muted-foreground">
                {t("desktop.agent.choose_provider")}
              </span>
            )}
          </span>
          <Icon
            name="chevronDown"
            className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 text-faint"
          />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        role="dialog"
        aria-label={t("desktop.agent.provider")}
        className="w-(--radix-popover-trigger-width) min-w-64 overflow-hidden p-0"
      >
        <Command
          label={t("desktop.providers.search_label")}
          filter={containsSearch}
          className="max-h-(--radix-popover-content-available-height)"
        >
          <CommandInput
            placeholder={t("desktop.providers.search_placeholder")}
          />
          <CommandList
            label={t("desktop.providers.search_label")}
            className="max-h-(--radix-popover-content-available-height) flex-1"
          >
            <CommandEmpty>{t("desktop.providers.search_empty")}</CommandEmpty>
            {groups.map((group, index) => (
              <Fragment
                key={group[0]?.way.selectable ? "available" : "unavailable"}
              >
                {index > 0 && (
                  <div role="separator" className="my-1 border-t" />
                )}
                <CommandGroup>
                  {group.map(({ provider, way }) => {
                    const connection = connectionWords(t, way.transport);
                    const reason = way.selectable
                      ? null
                      : (way.unavailableReason ??
                        t("desktop.agent.unavailable"));
                    return (
                      <CommandItem
                        key={way.id}
                        value={way.id}
                        keywords={[
                          provider.name,
                          connection,
                          ...(reason ? [reason] : []),
                        ]}
                        disabled={!way.selectable}
                        data-way={way.id}
                        onSelect={() => {
                          if (!way.selectable) return;
                          onChange(way.id);
                          setOpen(false);
                        }}
                        className={cn(
                          "relative cursor-pointer rounded-sm px-2.5 py-1",
                          "data-[disabled=true]:pointer-events-none data-[disabled=true]:opacity-60",
                          "data-[selected=true]:bg-selected data-[selected=true]:text-accent-foreground",
                        )}
                      >
                        <ProviderMark provider={provider.id} size="md" />
                        <span className="grid min-w-0 flex-1">
                          <span className="flex min-w-0 flex-wrap items-baseline gap-x-2">
                            <span className="truncate font-medium">
                              {provider.name}
                            </span>
                            <span className="text-sm text-muted-foreground in-data-[selected=true]:text-accent-foreground">
                              {connection}
                            </span>
                          </span>
                          {reason && (
                            <span className="text-sm text-muted-foreground in-data-[selected=true]:text-accent-foreground">
                              {reason}
                            </span>
                          )}
                        </span>
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              </Fragment>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
