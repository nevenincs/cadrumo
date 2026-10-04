import { useRef, type KeyboardEvent } from "react";
import { Icon } from "./Icon";

export type RailItem = {
  id: string;
  icon: string;
  label: string;
  shortcut?: string;
  pressed?: boolean;
  badge?: number;
  onClick: () => void;
};

// Icon-only vertical toolbar: one tab stop, arrow keys move within it.
export function Rail({
  label,
  top,
  bottom,
}: {
  label: string;
  top: RailItem[];
  bottom: RailItem[];
}) {
  const bar = useRef<HTMLElement>(null);

  const move = (event: KeyboardEvent) => {
    if (
      !["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key) ||
      !bar.current
    )
      return;
    event.preventDefault();
    const buttons = [
      ...bar.current.querySelectorAll<HTMLButtonElement>("button"),
    ];
    const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
    let next = at;
    if (event.key === "ArrowDown") next = (at + 1) % buttons.length;
    if (event.key === "ArrowUp")
      next = (at - 1 + buttons.length) % buttons.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = buttons.length - 1;
    buttons.forEach(
      (button, index) => (button.tabIndex = index === next ? 0 : -1),
    );
    buttons[next]?.focus();
  };

  const render = (item: RailItem, first: boolean) => (
    <button
      key={item.id}
      className={`rail-button ${item.pressed ? "is-pressed" : ""}`}
      aria-label={item.label}
      aria-pressed={item.pressed}
      tabIndex={first ? 0 : -1}
      onClick={item.onClick}
      data-tip={item.shortcut ? `${item.label}  ${item.shortcut}` : item.label}
    >
      <Icon name={item.icon} />
      {item.badge ? (
        <span className="rail-badge">
          {item.badge > 99 ? "99+" : item.badge}
        </span>
      ) : null}
    </button>
  );

  return (
    <nav className="rail" aria-label={label} ref={bar} onKeyDown={move}>
      <div className="rail-group">
        {top.map((item, index) => render(item, index === 0))}
      </div>
      <div className="rail-group">
        {bottom.map((item) => render(item, false))}
      </div>
    </nav>
  );
}
