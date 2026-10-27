import {
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  type ClipboardEvent,
  type KeyboardEvent,
  type MouseEvent,
  type Ref,
} from "react";
import { IS_MAC } from "@/shared/chords";
import type { SedeViewInput } from "../../ipc/contract";
import { sedeViewSize, type SedeViewSize } from "../../shell/sedeView";
import {
  clickCount,
  keyPlan,
  modifiersOf,
  pasteSteps,
  pointerButton,
  viewPoint,
  wheelDelta,
  type KeyPlan,
} from "./browserModel";
import type { DrawnImage } from "./useSedeView";

export type SurfaceHandle = {
  /** Draws an image; settles when it is drawn or dropped. A newer image
   * wins over one still being decoded. */
  draw(image: DrawnImage): Promise<void>;
  /** Wipes what was drawn. */
  clear(): void;
  element(): HTMLElement | null;
};

type Props = {
  ref?: Ref<SurfaceHandle>;
  /** False while the page is put aside: images are credited, not drawn. */
  shown: boolean;
  /** Whether the person's input reaches the page. */
  enabled: boolean;
  label: string;
  /** The shell's own chords, which never reach the page. */
  isShellChord: (event: globalThis.KeyboardEvent) => boolean;
  onSize: (size: SedeViewSize) => void;
  onInput: (event: SedeViewInput) => void;
};

type Held = { index: number; count: number };

/**
 * The page's canvas. It draws the images the view sends from bytes in memory
 * and turns the person's pointer, wheel, keys and paste into the view's input,
 * in CSS pixels of the page. It takes the keys only while it has focus, as a
 * terminal does: the shell's own chords are the only keys it lets by.
 */
export function BrowserSurface({
  ref,
  shown,
  enabled,
  label,
  isShellChord,
  onSize,
  onInput,
}: Props) {
  const wrapper = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  // The page's own size in CSS pixels, from the last image it sent; until
  // then the size the view was asked for.
  const viewport = useRef<{ width: number; height: number } | null>(null);
  const asked = useRef<{ width: number; height: number } | null>(null);
  const newest = useRef(0);
  // The newest image that arrived while the page was put aside.
  const aside = useRef<DrawnImage | null>(null);
  const pressed = useRef<Held | null>(null);
  const keys = useRef(new Map<string, KeyPlan>());
  const hover = useRef<{ x: number; y: number; modifiers: number } | null>(
    null,
  );
  const frame = useRef(0);
  const live = useRef({ shown, enabled, isShellChord, onSize, onInput });
  live.current = { shown, enabled, isShellChord, onSize, onInput };

  const pointAt = useCallback((at: { clientX: number; clientY: number }) => {
    const target = canvas.current;
    const page = viewport.current ?? asked.current;
    if (!target || !page) return null;
    return viewPoint(
      { x: at.clientX, y: at.clientY },
      target.getBoundingClientRect(),
      page,
    );
  }, []);

  const paint = useCallback(async (image: DrawnImage, ticket: number) => {
    if (!image.bytes) return;
    let bitmap: ImageBitmap;
    try {
      bitmap = await createImageBitmap(
        new Blob([image.bytes], { type: "image/jpeg" }),
      );
    } catch {
      return;
    }
    const target = canvas.current;
    // A newer image came while this one decoded, or the page went away.
    if (!target || ticket !== newest.current) {
      bitmap.close();
      return;
    }
    if (target.width !== bitmap.width || target.height !== bitmap.height) {
      target.width = bitmap.width;
      target.height = bitmap.height;
    }
    target.getContext("2d", { alpha: false })?.drawImage(bitmap, 0, 0);
    bitmap.close();
    viewport.current = { width: image.css_width, height: image.css_height };
  }, []);

  useImperativeHandle(
    ref,
    () => ({
      async draw(image) {
        newest.current += 1;
        if (!live.current.shown) {
          aside.current = image;
          return;
        }
        await paint(image, newest.current);
      },
      clear() {
        newest.current += 1;
        aside.current = null;
        viewport.current = null;
        const target = canvas.current;
        target
          ?.getContext("2d", { alpha: false })
          ?.clearRect(0, 0, target.width, target.height);
      },
      element: () => wrapper.current,
    }),
    [paint],
  );

  // Put back in view, the page shows the newest image it was sent meanwhile.
  useEffect(() => {
    const image = aside.current;
    if (!shown || !image) return;
    aside.current = null;
    newest.current += 1;
    void paint(image, newest.current);
  }, [shown, paint]);

  // The panel's size, in whole CSS pixels, once it has room.
  useEffect(() => {
    const element = wrapper.current;
    if (!element) return;
    const measure = () => {
      const size = sedeViewSize(
        element.getBoundingClientRect(),
        window.devicePixelRatio,
      );
      if (!size) return;
      asked.current = { width: size.cssWidth, height: size.cssHeight };
      live.current.onSize(size);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    measure();
    return () => observer.disconnect();
  }, []);

  const send = useCallback((event: SedeViewInput) => {
    if (live.current.enabled) live.current.onInput(event);
  }, []);

  // Moves are sent at most once for each frame drawn; a press or a release
  // sends the move before it, so the order the person made them in holds.
  const flushHover = useCallback(() => {
    cancelAnimationFrame(frame.current);
    frame.current = 0;
    const at = hover.current;
    hover.current = null;
    if (!at) return;
    send({
      type: "pointer",
      action: "move",
      x: at.x,
      y: at.y,
      button: "none",
      click_count: 0,
      modifiers: at.modifiers,
    });
  }, [send]);

  const moved = useCallback(
    (event: globalThis.MouseEvent) => {
      const point = pointAt(event);
      if (!point) return;
      hover.current = { ...point, modifiers: modifiersOf(event) };
      if (!frame.current)
        frame.current = requestAnimationFrame(() => {
          frame.current = 0;
          flushHover();
        });
    },
    [pointAt, flushHover],
  );

  const released = useCallback(
    (event: globalThis.MouseEvent) => {
      const held = pressed.current;
      if (!held || event.button !== held.index) return;
      pressed.current = null;
      flushHover();
      const point = pointAt(event);
      const button = pointerButton(held.index);
      if (!point || !button) return;
      send({
        type: "pointer",
        action: "up",
        x: point.x,
        y: point.y,
        button,
        click_count: held.count,
        modifiers: modifiersOf(event),
      });
    },
    [pointAt, flushHover, send],
  );

  // A drag goes on outside the panel, and a release is seen wherever it is.
  useEffect(() => {
    const drag = (event: globalThis.MouseEvent) => {
      if (pressed.current) moved(event);
    };
    window.addEventListener("mousemove", drag);
    window.addEventListener("mouseup", released);
    return () => {
      window.removeEventListener("mousemove", drag);
      window.removeEventListener("mouseup", released);
      cancelAnimationFrame(frame.current);
    };
  }, [moved, released]);

  useEffect(() => {
    const element = wrapper.current;
    if (!element) return;
    const turned = (event: WheelEvent) => {
      // The wheel belongs to the page, not to the shell's scrolling or zoom.
      event.preventDefault();
      const page = viewport.current ?? asked.current;
      const point = pointAt(event);
      if (!page || !point) return;
      const delta = wheelDelta(event, page);
      if (delta.x === 0 && delta.y === 0) return;
      flushHover();
      send({
        type: "wheel",
        x: point.x,
        y: point.y,
        delta_x: delta.x,
        delta_y: delta.y,
        modifiers: modifiersOf(event),
      });
    };
    element.addEventListener("wheel", turned, { passive: false });
    return () => element.removeEventListener("wheel", turned);
  }, [pointAt, flushHover, send]);

  const pressKey = (event: KeyboardEvent) => {
    if (live.current.isShellChord(event.nativeEvent)) return;
    // The paste event that follows carries the text; the key is not sent.
    if (
      (event.ctrlKey || event.metaKey) &&
      !event.altKey &&
      !event.shiftKey &&
      event.key.toLowerCase() === "v"
    )
      return;
    const plan = keyPlan(
      {
        key: event.key,
        code: event.code,
        altKey: event.altKey,
        ctrlKey: event.ctrlKey,
        metaKey: event.metaKey,
        shiftKey: event.shiftKey,
        isComposing: event.nativeEvent.isComposing,
        altGraph: event.getModifierState("AltGraph"),
      },
      IS_MAC,
    );
    if (!plan) return;
    // Tab, space, the arrows and the function keys are the page's too.
    event.preventDefault();
    event.stopPropagation();
    if (!live.current.enabled) return;
    keys.current.set(event.code || event.key, plan);
    send({
      type: "key",
      action: "down",
      key: plan.key,
      code: plan.code,
      modifiers: plan.modifiers,
    });
    if (plan.text !== null) send({ type: "text", text: plan.text });
  };

  const releaseKey = (event: KeyboardEvent) => {
    const id = event.code || event.key;
    const plan = keys.current.get(id);
    if (!plan) return;
    keys.current.delete(id);
    event.preventDefault();
    event.stopPropagation();
    send({
      type: "key",
      action: "up",
      key: plan.key,
      code: plan.code,
      modifiers: modifiersOf(event, event.getModifierState("AltGraph")),
    });
  };

  // Focus leaving lets go of what was held, so no key stays down in the page.
  const letGo = () => {
    for (const plan of keys.current.values())
      send({
        type: "key",
        action: "up",
        key: plan.key,
        code: plan.code,
        modifiers: 0,
      });
    keys.current.clear();
  };

  const pressMouse = (event: MouseEvent) => {
    event.preventDefault();
    wrapper.current?.focus({ preventScroll: true });
    const button = pointerButton(event.button);
    const point = pointAt(event);
    if (!button || !point || !live.current.enabled) return;
    flushHover();
    const count = clickCount(event.detail);
    pressed.current = { index: event.button, count };
    send({
      type: "pointer",
      action: "down",
      x: point.x,
      y: point.y,
      button,
      click_count: count,
      modifiers: modifiersOf(event),
    });
  };

  const paste = (event: ClipboardEvent) => {
    event.preventDefault();
    if (!live.current.enabled) return;
    for (const step of pasteSteps(event.clipboardData.getData("text/plain"))) {
      if (step.type === "text") send({ type: "text", text: step.text });
      else
        for (const action of ["down", "up"] as const)
          send({
            type: "key",
            action,
            key: "Enter",
            code: "Enter",
            modifiers: 0,
          });
    }
  };

  return (
    <div
      ref={wrapper}
      tabIndex={0}
      role="group"
      aria-label={label}
      data-browser-surface=""
      className="relative min-h-0 flex-1 cursor-default overflow-hidden bg-card select-none focus-visible:-outline-offset-2"
      onKeyDown={pressKey}
      onKeyUp={releaseKey}
      onBlur={letGo}
      onMouseDown={pressMouse}
      onMouseMove={(event) => {
        if (!pressed.current) moved(event.nativeEvent);
      }}
      onContextMenu={(event) => event.preventDefault()}
      onPaste={paste}
    >
      <canvas
        ref={canvas}
        aria-hidden="true"
        className="absolute inset-0 size-full"
      />
    </div>
  );
}
