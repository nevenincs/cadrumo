import * as React from "react";
import { Tabs as TabsPrimitive } from "radix-ui";
import { useBareClick } from "@/components/ui/bareClick";
import { cn } from "@/components/ui/cn";

/** Chooses a tab of the row a trigger belongs to. */
const ChooseTab = React.createContext<((value: string) => void) | null>(null);

/**
 * A tab row whose chosen tab is underlined in the brand colour. The list is
 * one tab stop; arrow keys move and choose. A view that must never unmount
 * (a live terminal) renders its own panel and names it on the trigger with
 * `aria-controls`.
 */
function Tabs({
  className,
  value: valueProp,
  defaultValue = "",
  onValueChange,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  const [ownValue, setOwnValue] = React.useState(defaultValue);
  const value = valueProp ?? ownValue;
  const choose = React.useCallback(
    (next: string) => {
      if (valueProp === undefined) setOwnValue(next);
      onValueChange?.(next);
    },
    [valueProp, onValueChange],
  );
  return (
    <ChooseTab.Provider value={choose}>
      <TabsPrimitive.Root
        data-slot="tabs"
        className={cn("flex min-h-0 flex-col", className)}
        value={value}
        onValueChange={choose}
        {...props}
      />
    </ChooseTab.Provider>
  );
}

function TabsList({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn("flex h-control-lg items-stretch gap-0.5", className)}
      {...props}
    />
  );
}

/**
 * A tab: a press of the pointer, Enter, Space or an arrow key chooses it, and
 * so does a click nothing else started, which is what an assistive
 * technology's or automation's activation sends (UI Automation's Invoke, a
 * screen reader's default action), with or without the window's focus.
 */
function TabsTrigger({
  className,
  onKeyDown,
  onClick,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  const choose = React.useContext(ChooseTab);
  const bare = useBareClick();
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      onKeyDown={(event) => {
        bare.onKeyDown(event);
        onKeyDown?.(event);
      }}
      onClick={(event) => {
        onClick?.(event);
        if (
          bare.isBare(event) &&
          !props.disabled &&
          event.currentTarget.getAttribute("aria-selected") !== "true"
        )
          choose?.(props.value);
      }}
      className={cn(
        "relative inline-flex min-w-control-md cursor-pointer items-center justify-center gap-1.5 px-3 text-base font-medium whitespace-nowrap text-muted-foreground select-none",
        "-outline-offset-2 transition-colors hover:text-foreground disabled:pointer-events-none disabled:opacity-50",
        "data-[state=active]:text-foreground",
        "after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-brand after:opacity-0 after:transition-opacity data-[state=active]:after:opacity-100 forced-colors:after:bg-[Highlight]",
        "[&_svg]:pointer-events-none [&_svg]:shrink-0",
        className,
      )}
      {...props}
    />
  );
}

function TabsContent({
  className,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("min-h-0 flex-1 outline-none", className)}
      {...props}
    />
  );
}

export { Tabs, TabsContent, TabsList, TabsTrigger };
