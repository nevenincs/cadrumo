import {
  Children,
  cloneElement,
  createContext,
  isValidElement,
  useCallback,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ComponentProps,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactElement,
  type ReactNode,
  type RefObject,
} from "react";
import { createPortal } from "react-dom";
import { clsx as cx } from "clsx";
import { Icon, type IconName, type IconSize } from "./Icon";

/* ── Primitives: the ui/ layer, rebuilt on the same roles and recipes.
   They know nothing of the ledger. ─────────────────────────────────── */

/* Overlays render inside the prototype's own root, so the scoped styles
   reach them and their content is never outside a landmark; fixed
   positioning is unaffected. */
export const OverlayCtx = createContext<HTMLElement | null>(null);
export function Overlay({ children }: { children: ReactNode }) {
  const root = useContext(OverlayCtx);
  return root ? createPortal(children, root) : null;
}

/* Chords match their exact modifiers; the shell's own chords are never
   taken by the page (Ctrl+K, Ctrl+, F6, Ctrl+Shift+letters, Ctrl+`). */
type KeyLike = Pick<
  KeyboardEvent,
  "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey"
>;
export function chord(
  e: KeyLike,
  key: string,
  { ctrl = false, shift = false, alt = false } = {},
) {
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  return (
    k === key &&
    !!(e.ctrlKey || e.metaKey) === ctrl &&
    e.shiftKey === shift &&
    e.altKey === alt
  );
}
export const SHELL_CHORDS = [
  "Control+k",
  "Control+,",
  "F6",
  "Shift+F6",
  "Control+Shift+a",
  "Control+Shift+t",
  "Control+Shift+h",
  "Control+Shift+m",
  "Control+Shift+l",
  "Control+Shift+d",
  "Control+Shift+1",
  "Control+Shift+2",
  "Control+Shift+3",
  "Control+`",
];
export function isShellChord(e: KeyLike) {
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  const name = [
    (e.ctrlKey || e.metaKey) && "Control",
    e.shiftKey && "Shift",
    e.altKey && "Alt",
    k,
  ]
    .filter(Boolean)
    .join("+");
  return (
    SHELL_CHORDS.includes(name) ||
    (e.shiftKey && (e.ctrlKey || e.metaKey) && /^[!@#]$/.test(e.key))
  );
}
let announceFn: (text: string) => void = () => {};
export const announce = (t: string) => announceFn(t);
export function LiveRegion() {
  const [msg, setMsg] = useState("");
  useEffect(() => {
    let t: ReturnType<typeof setTimeout> | undefined;
    announceFn = (x) => {
      clearTimeout(t);
      setMsg("");
      t = setTimeout(() => setMsg(x), 30);
    };
    return () => {
      clearTimeout(t);
      announceFn = () => {};
    };
  }, []);
  return (
    <div
      className="sr-only"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {msg}
    </div>
  );
}
export const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Spinner({
  label,
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <span
      role={label ? "status" : undefined}
      aria-label={label}
      className="row"
    >
      <Icon name="loader" className={cx("spin", className)} />
    </span>
  );
}

type ButtonProps = ComponentProps<"button"> & {
  variant?: string;
  size?: string;
  pending?: boolean;
  icon?: IconName;
  iconRight?: IconName;
};
export function Button({
  variant = "primary",
  size = "md",
  className,
  pending,
  icon,
  iconRight,
  children,
  type = "button",
  onClick,
  ...p
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cx("btn", variant, size, className)}
      aria-busy={pending || undefined}
      aria-disabled={pending || p["aria-disabled"] || undefined}
      onClick={pending ? (e) => e.preventDefault() : onClick}
      {...p}
    >
      {pending ? (
        <Icon name="loader" className="spin" />
      ) : icon ? (
        <Icon name={icon} />
      ) : null}
      {children}
      {iconRight ? <Icon name={iconRight} size="xs" /> : null}
    </button>
  );
}
/* An icon-only control always has a name, shown as its tooltip. */
type IconButtonProps = Omit<ComponentProps<"button">, "children"> & {
  label: string;
  shortcut?: string;
  hint?: string;
  size?: string;
  variant?: string;
  icon: IconName;
  iconSize?: IconSize;
  side?: string;
  accessibleName?: string;
  pending?: boolean;
  children?: ReactNode;
};
export function IconButton({
  label,
  shortcut,
  hint,
  size = "xs",
  variant = "ghost",
  icon,
  iconSize,
  className,
  children,
  side,
  accessibleName,
  pending,
  onClick,
  ...p
}: IconButtonProps) {
  return (
    <button
      type="button"
      className={cx("btn", variant, "icon-" + size, className)}
      aria-busy={pending || undefined}
      onClick={pending ? (e) => e.preventDefault() : onClick}
      aria-label={accessibleName || (hint ? `${label}, ${hint}` : label)}
      aria-keyshortcuts={
        shortcut ? shortcut.replace(/Ctrl/g, "Control") : undefined
      }
      data-tip={label}
      data-tip-hint={hint}
      data-kbd={shortcut}
      data-side={side}
      {...p}
    >
      <Icon
        name={pending ? "loader" : icon}
        size={iconSize}
        className={pending ? "spin" : undefined}
      />
      {children}
    </button>
  );
}
export function Badge({
  variant = "neutral",
  className,
  children,
  ...p
}: ComponentProps<"span"> & { variant?: string }) {
  return (
    <span
      className={cx("badge", variant !== "neutral" && variant, className)}
      {...p}
    >
      {children}
    </span>
  );
}
export function Hint({
  text,
  label = "About this",
}: {
  text: string;
  label?: string;
}) {
  return (
    <button
      type="button"
      className="btn ghost icon-xs hint"
      aria-label={label + ": " + text}
      data-tip={text}
    >
      <Icon name="info" size="xs" />
    </button>
  );
}
export function Kbd({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <kbd className={cx("kbd", className)}>{children}</kbd>;
}
export function Keys({ chord }: { chord: string }) {
  return (
    <span className="row g1">
      {chord.split("+").map((k, i) => (
        <Kbd key={i}>{k}</Kbd>
      ))}
    </span>
  );
}
export function Alert({
  tone = "neutral",
  icon,
  title,
  children,
  role = "status",
  className,
  action,
}: {
  tone?: string;
  icon?: IconName;
  title?: ReactNode;
  children?: ReactNode;
  role?: string;
  className?: string;
  action?: ReactNode;
}) {
  const ic: IconName =
    icon ||
    (tone === "danger"
      ? "alert"
      : tone === "warning"
        ? "alert"
        : tone === "success"
          ? "check"
          : "info");
  return (
    <div
      role={role}
      className={cx("alert", tone !== "neutral" && tone, className)}
    >
      <Icon name={ic} />
      <div className="alert-body">
        {title ? <div className="alert-title">{title}</div> : null}
        {children ? (
          <div className={title ? "alert-desc" : ""}>{children}</div>
        ) : null}
      </div>
      {action}
    </div>
  );
}
export function Empty({
  icon,
  title,
  desc,
  busy,
  children,
  className,
}: {
  icon?: IconName;
  title?: ReactNode;
  desc?: ReactNode;
  busy?: boolean;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cx("empty", className)} aria-busy={busy || undefined}>
      {busy ? (
        <Spinner />
      ) : icon ? (
        <div className="empty-media">
          <Icon name={icon} />
        </div>
      ) : null}
      {title || desc ? (
        <div className="empty-text">
          {title ? <p className="empty-title">{title}</p> : null}
          {desc ? <p className="empty-desc">{desc}</p> : null}
        </div>
      ) : null}
      {children}
    </div>
  );
}
export function Meter({
  value,
  max = 1,
  label,
  className,
}: {
  value: number;
  max?: number;
  label: string;
  className?: string;
}) {
  return (
    <div
      className={cx("meter", className)}
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
    >
      <span style={{ width: (value / max) * 100 + "%" }}></span>
    </div>
  );
}
/* An active filter: a soft badge with a remove target of at least 1.5rem. */
export function FilterChip({
  label,
  tip,
  onRemove,
}: {
  label: string;
  tip?: string;
  onRemove: () => void;
}) {
  return (
    <span
      className="badge soft filter-chip"
      data-tip={tip ? `${tip}: ${label}` : undefined}
    >
      {label}
      <button
        type="button"
        className="btn ghost icon-xs"
        aria-label={"Remove filter: " + (tip ? tip + " " : "") + label}
        onClick={onRemove}
      >
        <Icon name="close" size="xs" />
      </button>
    </span>
  );
}
export function Progress({
  value,
  max = 100,
  label,
  className,
}: {
  value?: number;
  max?: number;
  label: string;
  className?: string;
}) {
  const share = Math.max(0, Math.min(1, (value || 0) / max));
  return (
    <div
      className={cx("progress", className)}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
    >
      <span style={{ transform: `scaleX(${share})` }}></span>
    </div>
  );
}
export function Switch({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked?: boolean;
  onChange: (next: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      className="switch"
      aria-checked={!!checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
    >
      <span></span>
    </button>
  );
}
export function Checkbox(p: Omit<ComponentProps<"input">, "type">) {
  return <input type="checkbox" className="checkbox" {...p} />;
}
export function Input({
  size,
  className,
  ...p
}: Omit<ComponentProps<"input">, "size"> & { size?: string }) {
  return <input className={cx("input", size, className)} {...p} />;
}
export function Select({
  size,
  className,
  children,
  ...p
}: Omit<ComponentProps<"select">, "size"> & { size?: string }) {
  return (
    <div className="select-wrap">
      <select className={cx("input select", size, className)} {...p}>
        {children}
      </select>
      <Icon name="chevronDown" />
    </div>
  );
}
/* A labelled control. The hint and the error describe the control
   (aria-describedby) instead of joining its name. */
export function Field({
  label,
  req,
  hint,
  error,
  children,
  className,
}: {
  label: ReactNode;
  req?: boolean;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  const described = error || hint ? id + "-d" : undefined;
  const kids = Children.map(children, (c, i) =>
    i === 0 && isValidElement(c) && typeof c.type !== "string"
      ? cloneElement(c as ReactElement<Record<string, unknown>>, {
          "aria-describedby": described,
        })
      : c,
  );
  return (
    <div className={cx("field", className)}>
      <label className="field-wrap">
        <span className="field-label">
          {label}
          {req ? (
            <span className="req" aria-hidden="true">
              {" "}
              *
            </span>
          ) : null}
          {req ? <span className="sr-only"> (required)</span> : null}
        </span>
        {kids}
      </label>
      {error ? (
        <span id={described} className="field-error">
          <Icon name="alert" size="xs" />
          {error}
        </span>
      ) : hint ? (
        <span id={described} className="field-hint">
          {hint}
        </span>
      ) : null}
    </div>
  );
}

export type SegOption = {
  value: string;
  label: ReactNode;
  disabled?: boolean;
  tip?: string;
};
/* A radio group drawn as one segmented row: one tab stop, arrows move. */
export function Seg({
  value,
  onChange,
  options,
  label,
  size,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  options: SegOption[];
  label: string;
  size?: string;
  className?: string;
  disabledReason?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const idx = Math.max(
    0,
    options.findIndex((o) => o.value === value),
  );
  const move = (d: number) => {
    let i = idx;
    for (let n = 0; n < options.length; n++) {
      i = (i + d + options.length) % options.length;
      if (!options[i]?.disabled) break;
    }
    onChange(options[i]!.value);
    requestAnimationFrame(() =>
      ref.current?.querySelectorAll<HTMLElement>('[role="radio"]')[i]?.focus(),
    );
  };
  return (
    <div
      ref={ref}
      role="radiogroup"
      aria-label={label}
      className={cx("seg", size, className)}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight" || e.key === "ArrowDown") {
          e.preventDefault();
          move(1);
        } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
          e.preventDefault();
          move(-1);
        }
      }}
    >
      {options.map((o, i) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          className="seg-item"
          aria-checked={o.value === value}
          tabIndex={i === idx ? 0 : -1}
          disabled={o.disabled}
          data-tip={o.tip}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
export type TabDef = {
  value: string;
  label: ReactNode;
  icon?: IconName;
  tip?: string;
  badge?: ReactNode;
  badgeLabel?: string;
  badgeVariant?: string;
};
/* A tab row: the chosen tab carries the brand bar. Arrows move and choose. */
export function Tabs({
  value,
  onChange,
  tabs,
  label,
  size,
  className,
  idBase,
}: {
  value: string | null;
  onChange: (value: string) => void;
  tabs: TabDef[];
  label: string;
  size?: string;
  className?: string;
  idBase?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const idx = Math.max(
    0,
    tabs.findIndex((t) => t.value === value),
  );
  const go = (i: number) => {
    onChange(tabs[i]!.value);
    requestAnimationFrame(() =>
      ref.current?.querySelectorAll<HTMLElement>('[role="tab"]')[i]?.focus(),
    );
  };
  return (
    <div
      ref={ref}
      role="tablist"
      aria-label={label}
      className={cx("tabs", size, className)}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight") {
          e.preventDefault();
          go((idx + 1) % tabs.length);
        } else if (e.key === "ArrowLeft") {
          e.preventDefault();
          go((idx - 1 + tabs.length) % tabs.length);
        } else if (e.key === "Home") {
          e.preventDefault();
          go(0);
        } else if (e.key === "End") {
          e.preventDefault();
          go(tabs.length - 1);
        }
      }}
    >
      {tabs.map((t, i) => (
        <button
          key={t.value}
          type="button"
          role="tab"
          id={idBase ? idBase + "-" + t.value : undefined}
          className="tab"
          aria-selected={t.value === value}
          tabIndex={i === idx ? 0 : -1}
          onClick={() => onChange(t.value)}
          data-tip={t.tip || t.badgeLabel}
        >
          {t.icon ? <Icon name={t.icon} /> : null}
          {t.label}
          {t.badge != null ? (
            <>
              <Badge
                variant={t.badgeVariant || "neutral"}
                className="tnum"
                aria-hidden="true"
              >
                {t.badge}
              </Badge>
              <span className="sr-only">, {t.badgeLabel || t.badge}</span>
            </>
          ) : null}
        </button>
      ))}
    </div>
  );
}

/* ── Placement of floating surfaces. ─────────────────────────────────── */
export type Anchor =
  HTMLElement | { x: number; y: number } | DOMRect | null | undefined;
type Box = {
  left: number;
  top: number;
  right: number;
  bottom: number;
  width: number;
  height: number;
};
export function rectOf(anchor: Anchor): Box {
  if (!anchor)
    return { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 };
  if (anchor instanceof HTMLElement) return anchor.getBoundingClientRect();
  if ("x" in anchor && !("width" in anchor))
    return {
      left: anchor.x,
      right: anchor.x,
      top: anchor.y,
      bottom: anchor.y,
      width: 0,
      height: 0,
    };
  return anchor as DOMRect;
}
export type Placement = { align?: string; side?: string; gap?: number };
export function place(
  anchor: Anchor,
  el: HTMLElement,
  { align = "start", side = "bottom", gap = 6 }: Placement = {},
) {
  const r = rectOf(anchor);
  const w = el.offsetWidth,
    h = el.offsetHeight;
  const vw = window.innerWidth,
    vh = window.innerHeight;
  let left: number, top: number;
  if (side === "right") {
    left = r.right + gap;
    top = r.top;
    if (left + w > vw - 8) left = r.left - w - gap;
  } else {
    left =
      align === "end"
        ? r.right - w
        : align === "center"
          ? r.left + r.width / 2 - w / 2
          : r.left;
    top = r.bottom + gap;
    if (top + h > vh - 8 && r.top - h - gap > 8) top = r.top - h - gap;
  }
  left = Math.max(8, Math.min(left, vw - w - 8));
  top = Math.max(8, Math.min(top, vh - h - 8));
  return { left, top, maxHeight: vh - 16 };
}
type Position = ReturnType<typeof place>;
export function useFloating(
  anchor: Anchor,
  opts: Placement,
): [RefObject<HTMLDivElement | null>, Position | null] {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<Position | null>(null);
  const placement = useRef(opts);
  placement.current = opts;
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const upd = () => setPos(place(anchor, el, placement.current));
    upd();
    const ro = new ResizeObserver(upd);
    ro.observe(el);
    window.addEventListener("resize", upd);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", upd);
    };
  }, [anchor]);
  return [ref, pos];
}
/* Escape closes the topmost floating surface first, wherever focus is,
   and never reaches the dialog beneath it. */
const FLOATS: object[] = [];
export function useDismiss(
  ref: RefObject<HTMLElement | null>,
  onClose: (why: string) => void,
  anchor?: Anchor,
) {
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const me = {};
    FLOATS.push(me);
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape" && FLOATS[FLOATS.length - 1] === me) {
        e.preventDefault();
        e.stopPropagation();
        closeRef.current("escape");
      }
    };
    document.addEventListener("keydown", key, true);
    return () => {
      FLOATS.splice(FLOATS.indexOf(me), 1);
      document.removeEventListener("keydown", key, true);
    };
  }, []);
  useEffect(() => {
    const down = (e: PointerEvent) => {
      const target = e.target as Element;
      if (
        ref.current &&
        !ref.current.contains(target) &&
        !(anchor instanceof HTMLElement && anchor.contains(target)) &&
        !target.closest?.("[data-float]")
      )
        closeRef.current("outside");
    };
    const t = setTimeout(
      () => document.addEventListener("pointerdown", down, true),
      0,
    );
    return () => {
      clearTimeout(t);
      document.removeEventListener("pointerdown", down, true);
    };
  }, [ref, anchor]);
}

/* A non-modal surface anchored to its opener. Escape or a press outside
   closes it, and focus goes back to the opener. */
export function Popover({
  anchor,
  onClose,
  children,
  className,
  align,
  side,
  width,
  label,
  role = "dialog",
  autoFocus = true,
}: {
  anchor: Anchor;
  onClose: (why: string) => void;
  children: ReactNode;
  className?: string;
  align?: string;
  side?: string;
  width?: string;
  label?: string;
  role?: string;
  autoFocus?: boolean;
}) {
  const [ref, pos] = useFloating(anchor, { align, side });
  useDismiss(ref, onClose, anchor);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    const host = ref.current;
    if (autoFocus)
      requestAnimationFrame(() => {
        const f =
          ref.current?.querySelector<HTMLElement>("[data-autofocus]") ||
          ref.current?.querySelector<HTMLElement>(FOCUSABLE);
        (f || ref.current)?.focus();
      });
    return () => {
      if (
        prev &&
        document.contains(prev) &&
        (!host?.isConnected || host.contains(document.activeElement))
      )
        prev.focus?.({ preventScroll: true });
    };
  }, [autoFocus, ref]);
  return (
    <Overlay>
      <div
        ref={ref}
        data-float=""
        className={cx("popover", className)}
        role={role}
        aria-label={label}
        tabIndex={-1}
        style={{
          left: pos?.left ?? -9999,
          top: pos?.top ?? -9999,
          width,
          maxHeight: pos?.maxHeight,
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.stopPropagation();
            onClose("escape");
          }
        }}
      >
        {children}
      </div>
    </Overlay>
  );
}

export type MenuItem = {
  label?: string;
  sep?: boolean;
  heading?: string;
  icon?: IconName;
  checked?: boolean;
  disabled?: boolean;
  reason?: string | null;
  note?: string;
  shortcut?: string;
  keepOpen?: boolean;
  onSelect?: () => void;
};
/* A menu of actions or choices. Arrows, Home, End and typing move;
   Enter or Space chooses; Escape or Tab closes. */
export function Menu({
  anchor,
  items,
  onClose,
  align,
  side,
  label = "Actions",
  minWidth,
}: {
  anchor: Anchor;
  items: MenuItem[];
  onClose: (why: string) => void;
  align?: string;
  side?: string;
  label?: string;
  minWidth?: string;
}) {
  const [ref, pos] = useFloating(anchor, { align, side });
  useDismiss(ref, onClose, anchor);
  const selectable = items
    .map((it, i) => (!it.sep && !it.heading && !it.disabled ? i : -1))
    .filter((i) => i >= 0);
  const [hl, setHl] = useState(() => {
    const c = items.findIndex((it) => it.checked);
    return c >= 0 ? c : (selectable[0] ?? -1);
  });
  const typed = useRef({ s: "", t: 0 });
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    requestAnimationFrame(() => ref.current?.focus());
    return () => prev?.focus?.({ preventScroll: true });
  }, [ref]);
  useEffect(() => {
    ref.current
      ?.querySelector(`[data-i="${hl}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [hl, ref]);
  const choose = (it: MenuItem | undefined) => {
    if (!it || it.disabled) return;
    if (!it.keepOpen) onClose("select");
    setTimeout(() => it.onSelect?.(), 0);
  };
  const step = (d: number) => {
    const p = selectable.indexOf(hl);
    const n = selectable[(p + d + selectable.length) % selectable.length];
    if (n != null) setHl(n);
  };
  const id = useId();
  return (
    <Overlay>
      <div
        ref={ref}
        data-float=""
        role="menu"
        aria-label={label}
        tabIndex={0}
        className="menu"
        aria-activedescendant={hl >= 0 ? id + "-" + hl : undefined}
        style={{
          left: pos?.left ?? -9999,
          top: pos?.top ?? -9999,
          maxHeight: pos?.maxHeight,
          minWidth,
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            step(1);
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            step(-1);
          } else if (e.key === "Home") {
            e.preventDefault();
            setHl(selectable[0] ?? -1);
          } else if (e.key === "End") {
            e.preventDefault();
            setHl(selectable[selectable.length - 1] ?? -1);
          } else if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            choose(items[hl]);
          } else if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            onClose("escape");
          } else if (e.key === "Tab") {
            e.preventDefault();
            onClose("tab");
          } else if (e.key.length === 1 && /\S/.test(e.key)) {
            const now = Date.now();
            const t = typed.current;
            t.s =
              now - t.t > 700 ? e.key.toLowerCase() : t.s + e.key.toLowerCase();
            t.t = now;
            const hit = selectable.find((i) =>
              items[i]?.label?.toLowerCase().startsWith(t.s),
            );
            if (hit != null) setHl(hit);
          }
        }}
      >
        {items.map((it, i) =>
          it.sep ? (
            <div key={i} className="menu-sep" role="separator"></div>
          ) : it.heading ? (
            <div
              key={i}
              className="menu-label"
              role="presentation"
              aria-hidden="true"
            >
              {it.heading}
            </div>
          ) : (
            <div
              key={i}
              id={id + "-" + i}
              data-i={i}
              role={it.checked != null ? "menuitemradio" : "menuitem"}
              aria-checked={it.checked != null ? !!it.checked : undefined}
              aria-disabled={it.disabled ? "true" : undefined}
              className="menu-item"
              data-hl={i === hl}
              data-tip={it.disabled && it.reason ? it.reason : undefined}
              onPointerMove={() => !it.disabled && setHl(i)}
              onClick={() => choose(it)}
            >
              {it.checked != null ? (
                <span className="menu-check">
                  {it.checked ? <Icon name="tick" /> : null}
                </span>
              ) : it.icon ? (
                <Icon name={it.icon} />
              ) : null}
              <span className="truncate">{it.label}</span>
              {it.note ? <span className="menu-note">{it.note}</span> : null}
              {it.shortcut ? (
                <span className="menu-short">{it.shortcut}</span>
              ) : null}
            </div>
          ),
        )}
      </div>
    </Overlay>
  );
}

/* A modal surface over a scrim. Focus is trapped inside and returns to
   the opener when it closes. */
const MODALS: string[] = [];
export function Dialog({
  onClose,
  title,
  desc,
  children,
  footer,
  className,
  closeLabel = "Close",
  label,
  placement,
  bodyClass,
  sheet,
  headExtra,
  focusFirst,
}: {
  onClose: () => void;
  title?: ReactNode;
  desc?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  className?: string;
  closeLabel?: string | false;
  label?: string;
  placement?: string;
  bodyClass?: string;
  sheet?: boolean;
  headExtra?: ReactNode;
  focusFirst?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const tid = useId();
  const root = useContext(OverlayCtx);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  // Escape reaches the topmost dialog even when focus was pulled outside it.
  useEffect(() => {
    MODALS.push(tid);
    // Everything behind a modal is inert, as the shell's Dialog makes it.
    const behind = [
      ...(root?.querySelectorAll(".titlebar, .rail, .pane, .proto") ?? []),
    ];
    behind.forEach((el) => {
      el.setAttribute("inert", "");
      el.setAttribute("aria-hidden", "true");
    });
    const onDoc = (e: KeyboardEvent) => {
      if (
        e.key === "Escape" &&
        MODALS[MODALS.length - 1] === tid &&
        !ref.current?.contains(document.activeElement)
      ) {
        e.preventDefault();
        closeRef.current();
      }
    };
    document.addEventListener("keydown", onDoc);
    return () => {
      MODALS.splice(MODALS.indexOf(tid), 1);
      document.removeEventListener("keydown", onDoc);
      if (!MODALS.length)
        root?.querySelectorAll("[inert]").forEach((el) => {
          el.removeAttribute("inert");
          el.removeAttribute("aria-hidden");
        });
    };
  }, [tid, root]);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    requestAnimationFrame(() => {
      const el = ref.current;
      if (!el) return;
      const f =
        el.querySelector<HTMLElement>("[data-autofocus]") ||
        (focusFirst
          ? el.querySelector<HTMLElement>(
              ".dialog-body input, .dialog-body select, .dialog-body textarea, .dialog-body button",
            )
          : null) ||
        el.querySelector<HTMLElement>(
          ".dialog-body button, .dialog-body input, .dialog-body select, .dialog-body [tabindex='0']",
        ) ||
        el.querySelector<HTMLElement>(FOCUSABLE);
      (f || el).focus({ preventScroll: true });
    });
    return () => prev?.focus?.({ preventScroll: true });
  }, [focusFirst]);
  const onKey = (e: ReactKeyboardEvent) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      onClose();
    } else if (e.key === "Tab" && ref.current) {
      const els = [
        ...ref.current.querySelectorAll<HTMLElement>(FOCUSABLE),
      ].filter((x) => x.offsetParent !== null);
      const first = els[0],
        last = els[els.length - 1];
      if (!first || !last) return;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  };
  return (
    <Overlay>
      <div className="scrim" onClick={onClose}></div>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? tid : undefined}
        aria-label={label}
        tabIndex={-1}
        className={cx(sheet ? "sheet" : "dialog", placement, className)}
        onKeyDown={onKey}
      >
        {title ? (
          <div className="dialog-head">
            <h2 id={tid} className="dialog-title" tabIndex={-1}>
              {title}
            </h2>
            {desc ? <p className="dialog-desc">{desc}</p> : null}
            {headExtra}
          </div>
        ) : null}
        <div className={cx("dialog-body", bodyClass)} tabIndex={0}>
          {children}
        </div>
        {footer ? <div className="dialog-foot">{footer}</div> : null}
        {closeLabel ? (
          <IconButton
            className="dialog-close"
            size="sm"
            icon="close"
            label={closeLabel}
            onClick={onClose}
          />
        ) : null}
      </div>
    </Overlay>
  );
}

type Tip = {
  text: string | null;
  hint: string | null;
  kbd: string | null;
  side: string;
  r: DOMRect;
};
/* One tooltip for the whole window: anything with data-tip gets it. */
export function TooltipLayer() {
  const [tip, setTip] = useState<Tip | null>(null);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let cur: Element | null = null;
    const show = (el: Element, now?: boolean) => {
      clearTimeout(timer);
      timer = setTimeout(
        () => {
          if (!document.contains(el)) return;
          const r = el.getBoundingClientRect();
          setTip({
            text: el.getAttribute("data-tip"),
            hint: el.getAttribute("data-tip-hint"),
            kbd: el.getAttribute("data-kbd"),
            side: el.getAttribute("data-side") || "bottom",
            r,
          });
        },
        now ? 0 : 450,
      );
    };
    const hide = () => {
      clearTimeout(timer);
      cur = null;
      setTip(null);
    };
    const truncatedOk = (el: Element) => {
      if (!el.hasAttribute("data-tip-trunc")) return true;
      const t = el.querySelector(".v") || el;
      return t.scrollWidth > t.clientWidth + 1;
    };
    const over = (e: PointerEvent) => {
      const el = (e.target as Element).closest?.("[data-tip]") ?? null;
      if (el === cur) return;
      cur = el;
      if (el && el.getAttribute("data-tip") && truncatedOk(el)) show(el);
      else hide();
    };
    const focus = (e: FocusEvent) => {
      const el = (e.target as Element).closest?.("[data-tip]");
      if (
        el &&
        (el.matches(":focus-visible") ||
          el.getAttribute("role") === "gridcell") &&
        el.getAttribute("data-tip") &&
        truncatedOk(el)
      ) {
        cur = el;
        show(el, false);
      }
    };
    const blur = () => hide();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") hide();
    };
    document.addEventListener("pointerover", over);
    document.addEventListener("focusin", focus);
    document.addEventListener("focusout", blur);
    document.addEventListener("pointerdown", hide, true);
    document.addEventListener("keydown", key, true);
    document.addEventListener("scroll", hide, true);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("pointerover", over);
      document.removeEventListener("focusin", focus);
      document.removeEventListener("focusout", blur);
      document.removeEventListener("pointerdown", hide, true);
      document.removeEventListener("keydown", key, true);
      document.removeEventListener("scroll", hide, true);
    };
  }, []);
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<Position | null>(null);
  useLayoutEffect(() => {
    if (tip && ref.current)
      setPos(place(tip.r, ref.current, { align: "center", side: tip.side }));
    else setPos(null);
  }, [tip]);
  if (!tip) return null;
  return (
    <Overlay>
      <div
        ref={ref}
        className="tooltip"
        role="tooltip"
        style={{ left: pos?.left ?? -9999, top: pos?.top ?? -9999 }}
      >
        <span>
          {tip.text}
          {tip.hint ? <span className="tip-hint"> · {tip.hint}</span> : null}
        </span>
        {tip.kbd ? <Kbd>{tip.kbd}</Kbd> : null}
      </div>
    </Overlay>
  );
}

export const ToastCtx = createContext<(text: string) => void>(() => {});
export function ToastHost({ children }: { children: ReactNode }) {
  const [msg, setMsg] = useState<{ text: string; n: number } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const say = useCallback((text: string) => {
    clearTimeout(timer.current);
    setMsg({ text, n: Date.now() });
    timer.current = setTimeout(() => setMsg(null), 3600);
  }, []);
  useEffect(() => () => clearTimeout(timer.current), []);
  return (
    <ToastCtx.Provider value={say}>
      {children}
      <div className="toast-region" role="status" aria-live="polite">
        {msg ? (
          <Badge key={msg.n} variant="inverse">
            {msg.text}
          </Badge>
        ) : null}
      </div>
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);

export async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const t = document.createElement("textarea");
      t.value = text;
      t.style.position = "fixed";
      t.style.opacity = "0";
      document.body.appendChild(t);
      t.select();
      document.execCommand("copy");
      t.remove();
      return true;
    } catch {
      return false;
    }
  }
}
export const sleep = (ms: number) =>
  new Promise<void>((r) => setTimeout(r, ms));
