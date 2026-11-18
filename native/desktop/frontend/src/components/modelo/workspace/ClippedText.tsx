import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/components/ui/cn";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * Words held to the room their place keeps: cut with an ellipsis after one
 * line, or after `lines` lines, so that what they say never changes the
 * height or width of what holds them. While they are cut, and whenever there
 * is `help`, the whole text is a tooltip away, on hover or on focus.
 */
export function ClippedText({
  text,
  lines = 1,
  help,
  icon,
  className,
  textClassName,
}: {
  text: string;
  lines?: 1 | 2;
  /** Said under the whole text in the tooltip, cut or not. */
  help?: ReactNode;
  /** Drawn before the words, outside the cut. */
  icon?: ReactNode;
  className?: string;
  textClassName?: string;
}) {
  const words = useRef<HTMLSpanElement | null>(null);
  const [clipped, setClipped] = useState(false);
  useLayoutEffect(() => {
    const node = words.current;
    if (!node) return;
    const measure = () =>
      setClipped(
        lines === 1
          ? node.scrollWidth > node.clientWidth
          : node.scrollHeight > node.clientHeight,
      );
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const watch = new ResizeObserver(measure);
    watch.observe(node);
    return () => watch.disconnect();
  }, [text, lines]);
  const tip = clipped || Boolean(help);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={tip ? 0 : undefined}
          data-clipped={clipped ? "" : undefined}
          className={cn(
            "flex min-w-0 items-center gap-1.5 rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring",
            className,
          )}
        >
          {icon}
          <span
            ref={words}
            className={cn(
              "min-w-0",
              lines === 1 ? "truncate" : "line-clamp-2",
              textClassName,
            )}
          >
            {text}
          </span>
        </span>
      </TooltipTrigger>
      {tip && (
        <TooltipContent className="flex max-w-xs flex-col gap-1">
          {clipped && <span>{text}</span>}
          {help}
        </TooltipContent>
      )}
    </Tooltip>
  );
}
