import * as React from "react";
import { cn } from "./cn";
import { inputVariants } from "./input";
import { Tooltip, TooltipTrigger, TooltipContent } from "./tooltip";
import { commitKeyOf } from "./dataGridModel";
import type { EditorContext } from "./dataGridTypes";
import { CellStateContext } from "./dataGridCellState";

/**
 * The one tooltip a grid shows for text cut short. A cell names its text's
 * element and words; the tooltip anchors to a box laid over that element, so
 * nothing about the cell's own element changes as the pointer enters it or a
 * press lands on it, and a window of rows mounts no tooltip of its own.
 */
type TextTips = {
  show: (element: HTMLElement, text: string) => void;
  hide: (element: HTMLElement) => void;
};
const TextTipContext = React.createContext<TextTips>({
  show: () => undefined,
  hide: () => undefined,
});

export function GridTextTip({
  clearRef,
  children,
}: {
  /** Takes the tip away without dismissing it, as when the grid scrolls
   * and the box it was laid over moves. */
  clearRef: React.RefObject<(() => void) | null>;
  children: React.ReactNode;
}) {
  const [tip, setTip] = React.useState<{
    element: HTMLElement;
    text: string;
  } | null>(null);
  // Dismissed by Escape: it stays away until the pointer or focus leaves it.
  const dismissed = React.useRef<HTMLElement | null>(null);
  const tips = React.useMemo<TextTips>(
    () => ({
      show: (element, text) => {
        if (dismissed.current === element) return;
        setTip({ element, text });
      },
      hide: (element) => {
        if (dismissed.current === element) dismissed.current = null;
        setTip((held) => (held?.element === element ? null : held));
      },
    }),
    [],
  );
  React.useImperativeHandle(clearRef, () => () => setTip(null), []);
  const box = tip?.element.getBoundingClientRect();
  return (
    <TextTipContext.Provider value={tips}>
      {children}
      <Tooltip
        open={tip !== null}
        onOpenChange={(open) => {
          if (open || !tip) return;
          dismissed.current = tip.element;
          setTip(null);
        }}
      >
        <TooltipTrigger asChild>
          <span
            aria-hidden="true"
            data-slot="data-grid-text-tip"
            className="pointer-events-none fixed"
            style={
              box
                ? {
                    left: box.left,
                    top: box.top,
                    width: box.width,
                    height: box.height,
                  }
                : { display: "none" }
            }
          />
        </TooltipTrigger>
        <TooltipContent>{tip?.text}</TooltipContent>
      </Tooltip>
    </TextTipContext.Provider>
  );
}

/**
 * Text that ends in an ellipsis where its cell is too narrow, and then shows
 * whole in the shared tooltip under the pointer and while its cell has focus.
 * Text that fits shows no tooltip.
 */
export function DataGridText({
  children,
  className,
}: {
  children: string;
  className?: string;
}) {
  const ref = React.useRef<HTMLSpanElement>(null);
  const { focused } = React.useContext(CellStateContext);
  const tips = React.useContext(TextTipContext);
  const offer = React.useCallback(() => {
    const element = ref.current;
    if (element && element.scrollWidth > element.clientWidth)
      tips.show(element, children);
  }, [tips, children]);
  React.useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (focused) offer();
    return () => tips.hide(element);
  }, [focused, offer, tips]);
  return (
    <span
      ref={ref}
      data-slot="data-grid-text"
      className={cn("min-w-0 truncate", className)}
      onPointerEnter={offer}
      onPointerLeave={() => {
        if (ref.current && !focused) tips.hide(ref.current);
      }}
    >
      {children}
    </span>
  );
}

/**
 * A text editor for a cell. It opens holding the typed character, or the
 * whole value selected; Enter, Tab and Shift+Tab commit and Escape cancels.
 * Leaving it by the pointer commits a changed value and drops an unchanged
 * one.
 */
export function DataGridTextEditor({
  context,
  defaultValue,
  className,
  ...props
}: Omit<
  React.ComponentProps<"input">,
  "defaultValue" | "value" | "onChange" | "onKeyDown" | "onBlur"
> & {
  context: EditorContext;
  defaultValue: string;
}) {
  const input = React.useRef<HTMLInputElement>(null);
  const [value, setValue] = React.useState(context.initial ?? defaultValue);
  const done = React.useRef(false);
  React.useLayoutEffect(() => {
    const element = input.current;
    if (!element) return;
    element.focus({ preventScroll: true });
    if (context.initial === undefined) element.select();
    else element.setSelectionRange(element.value.length, element.value.length);
  }, [context.initial]);
  return (
    <input
      ref={input}
      data-slot="data-grid-editor"
      autoComplete="off"
      aria-label={context.label}
      aria-describedby={context.describedBy}
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onKeyDown={(event) => {
        const how = commitKeyOf(event);
        if (!how) return;
        event.preventDefault();
        event.stopPropagation();
        done.current = true;
        if (how === "cancel") context.cancel();
        else context.commit(value, how);
      }}
      onBlur={() => {
        if (done.current) return;
        done.current = true;
        if (value === defaultValue && context.initial === undefined)
          context.cancel(false);
        else context.commit(value, "pointer");
      }}
      className={cn(
        inputVariants({ controlSize: "sm" }),
        "h-full rounded-none border-ring",
        className,
      )}
      {...props}
    />
  );
}
