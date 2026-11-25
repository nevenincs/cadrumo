import * as React from "react";
import { RadioGroup as RadioGroupPrimitive } from "radix-ui";
import { cn } from "@/components/ui/cn";

/**
 * An arrow key moves the choice along with the focus. The foundation checks
 * the radio only while it still sees the key held down, which a key sent by
 * software may no longer be. Keyboard focus arriving on an unchecked radio of
 * a group that has a choice is that move.
 */
function chooseOnArrowFocus(event: React.FocusEvent<HTMLButtonElement>) {
  const item = event.currentTarget;
  if (
    item.getAttribute("aria-checked") === "false" &&
    item.matches(":focus-visible") &&
    item.closest('[role="radiogroup"]')?.querySelector('[aria-checked="true"]')
  )
    item.click();
}

/**
 * One choice among options that each need a line of their own. It is one tab
 * stop, and arrow keys move the choice. Give it an accessible name with
 * `aria-label` or `aria-labelledby`.
 */
function RadioGroup({
  className,
  ...props
}: React.ComponentProps<typeof RadioGroupPrimitive.Root>) {
  return (
    <RadioGroupPrimitive.Root
      data-slot="radio-group"
      className={cn("grid gap-1.5", className)}
      {...props}
    />
  );
}

/** One option. Wrap it in a `label` with its words. */
function RadioGroupItem({
  className,
  onFocus,
  ...props
}: React.ComponentProps<typeof RadioGroupPrimitive.Item>) {
  return (
    <RadioGroupPrimitive.Item
      data-slot="radio-group-item"
      onFocus={(event) => {
        onFocus?.(event);
        chooseOnArrowFocus(event);
      }}
      className={cn(
        "grid size-icon-sm shrink-0 cursor-pointer place-items-center rounded-full border border-input bg-card transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-destructive data-[state=checked]:not-aria-invalid:border-primary",
        className,
      )}
      {...props}
    >
      <RadioGroupPrimitive.Indicator
        data-slot="radio-group-indicator"
        className="size-2 rounded-full bg-primary forced-colors:bg-[Highlight]"
      />
    </RadioGroupPrimitive.Item>
  );
}

export { chooseOnArrowFocus, RadioGroup, RadioGroupItem };
