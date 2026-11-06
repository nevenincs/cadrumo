import {
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  type ClipboardEvent,
  type CompositionEvent,
  type FormEvent,
  type KeyboardEvent,
  type MouseEvent,
  type Ref,
} from "react";
import { IS_MAC } from "@/shared/chords";
import type { SedeViewInput } from "../../ipc/sedeViewMessages";
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
  /** False while the page is put aside: an image is kept, not drawn. */
  shown: boolean;
  /** Whether the person's input reaches the page. */
  enabled: boolean;
  label: string;
  /** The shell's own chords, which never reach the page. */
  isShellChord: (event: globalThis.KeyboardEvent) => boolean;
  onSize: (size: SedeViewSize) => void;
  onInput: (event: SedeViewInput) => void;
  onCopy?: () => void;
  onCut?: () => void;
};

type Held = { index: number; count: number; x: number; y: number };

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
  onCopy,
  onCut,
}: Props) {
  const wrapper = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  // A real editable target is needed for the operating system's IME. Its
  // value exists only while composing; committed text never stays in it.
  const input = useRef<HTMLTextAreaElement>(null);
  const composing = useRef(false);
  const compositionTail = useRef<string | null>(null);
  const compositionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
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
  const live = useRef({
    shown,
    enabled,
    isShellChord,
    onSize,
    onInput,
    onCopy,
    onCut,
  });
  live.current = {
    shown,
    enabled,
    isShellChord,
    onSize,
    onInput,
    onCopy,
    onCut,
  };

  const forgetComposition = useCallback(() => {
    composing.current = false;
    compositionTail.current = null;
    if (compositionTimer.current !== null)
      clearTimeout(compositionTimer.current);
    compositionTimer.current = null;
    if (input.current) input.current.value = "";
  }, []);

  useEffect(() => {
    if (!shown || !enabled) forgetComposition();
    return forgetComposition;
  }, [shown, enabled, forgetComposition]);

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
        forgetComposition();
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
    [paint, forgetComposition],
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
      if (pressed.current) {
        pressed.current.x = point.x;
        pressed.current.y = point.y;
      }
      hover.current = { ...point, modifiers: modifiersOf(event) };
      if (!frame.current)
        frame.current = requestAnimationFrame(() => {
          frame.current = 0;
          flushHover();
        });
    },
    [pointAt, flushHover],
  );

  const releaseHeld = useCallback(
    (point?: { x: number; y: number }, modifiers = 0) => {
      const held = pressed.current;
      if (!held) return;
      pressed.current = null;
      flushHover();
      const button = pointerButton(held.index);
      if (!button) return;
      send({
        type: "pointer",
        action: "up",
        x: point?.x ?? held.x,
        y: point?.y ?? held.y,
        button,
        click_count: held.count,
        modifiers,
      });
    },
    [flushHover, send],
  );

  const released = useCallback(
    (event: globalThis.MouseEvent) => {
      if (event.button !== pressed.current?.index) return;
      releaseHeld(pointAt(event) ?? undefined, modifiersOf(event));
    },
    [pointAt, releaseHeld],
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
    // Do not cancel the native edit: it is what starts and updates the IME.
    // 229 also covers the initiating key before compositionstart fires.
    if (
      composing.current ||
      event.nativeEvent.isComposing ||
      event.keyCode === 229
    ) {
      event.stopPropagation();
      return;
    }
    compositionTail.current = null;
    if (live.current.isShellChord(event.nativeEvent)) return;
    // The paste event that follows carries the text; the key is not sent.
    if (
      (event.ctrlKey || event.metaKey) &&
      !event.altKey &&
      !event.shiftKey &&
      event.key.toLowerCase() === "v"
    )
      return;
    if (
      (IS_MAC
        ? event.metaKey && !event.ctrlKey
        : event.ctrlKey && !event.metaKey) &&
      !event.altKey &&
      !event.shiftKey &&
      ["c", "x"].includes(event.key.toLowerCase())
    ) {
      event.preventDefault();
      event.stopPropagation();
      if (live.current.enabled)
        (event.key.toLowerCase() === "c"
          ? live.current.onCopy
          : live.current.onCut)?.();
      return;
    }
    const plan = keyPlan(
      {
        key: event.key,
        code: event.code,
        altKey: event.altKey,
        ctrlKey: event.ctrlKey,
        metaKey: event.metaKey,
        shiftKey: event.shiftKey,
        isComposing: event.nativeEvent.isComposing,
        keyCode: event.keyCode,
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
    if (!plan) {
      if (
        composing.current ||
        event.nativeEvent.isComposing ||
        event.keyCode === 229
      )
        event.stopPropagation();
      return;
    }
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

  // Focus leaving lets go of what was held, even if the native window loses
  // the matching mouseup while a drag is outside it.
  const letGo = useCallback(() => {
    forgetComposition();
    for (const plan of keys.current.values())
      send({
        type: "key",
        action: "up",
        key: plan.key,
        code: plan.code,
        modifiers: 0,
      });
    keys.current.clear();
    releaseHeld();
  }, [releaseHeld, send, forgetComposition]);

  useEffect(() => {
    window.addEventListener("blur", letGo);
    return () => window.removeEventListener("blur", letGo);
  }, [letGo]);

  const pressMouse = (event: MouseEvent) => {
    event.preventDefault();
    input.current?.focus({ preventScroll: true });
    const button = pointerButton(event.button);
    const point = pointAt(event);
    if (!button || !point || !live.current.enabled) return;
    flushHover();
    const count = clickCount(event.detail);
    pressed.current = { index: event.button, count, ...point };
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
    forgetComposition();
    if (!live.current.enabled) return;
    commitText(event.clipboardData.getData("text/plain"));
  };

  const commitText = (text: string) => {
    for (const step of pasteSteps(text)) {
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

  const compositionEnded = (event: CompositionEvent<HTMLTextAreaElement>) => {
    if (!composing.current) {
      event.currentTarget.value = "";
      return;
    }
    composing.current = false;
    const text = event.data;
    event.currentTarget.value = "";
    commitText(text);
    // WebKit can deliver the committed input after compositionend, while
    // Chromium delivers it before. Both must produce just one insertion.
    compositionTail.current = text;
    if (compositionTimer.current !== null)
      clearTimeout(compositionTimer.current);
    compositionTimer.current = setTimeout(() => {
      compositionTail.current = null;
      compositionTimer.current = null;
    }, 0);
  };

  const textEntered = (event: FormEvent<HTMLTextAreaElement>) => {
    const native = event.nativeEvent as InputEvent;
    if (composing.current || native.isComposing) return;
    const text = event.currentTarget.value;
    event.currentTarget.value = "";
    const tail = compositionTail.current;
    compositionTail.current = null;
    if (
      native.inputType === "insertFromComposition" ||
      native.inputType === "insertCompositionText" ||
      (tail !== null && (native.data === tail || text === tail))
    )
      return;
    // Native text input without a key (emoji, dictation, accessibility and
    // keyboard APIs) follows the same bounded text protocol as a commit.
    if (native.inputType?.startsWith("insert"))
      commitText(text || native.data || "");
  };

  const clipboard = (event: ClipboardEvent, action: "copy" | "cut") => {
    event.preventDefault();
    event.stopPropagation();
    if (live.current.enabled && !composing.current)
      (action === "copy" ? live.current.onCopy : live.current.onCut)?.();
  };

  return (
    <div
      ref={wrapper}
      tabIndex={0}
      role="group"
      aria-label={label}
      data-browser-surface=""
      className="relative min-h-0 flex-1 cursor-default overflow-hidden bg-card select-none has-[:focus-visible]:outline-(length:--focus-ring) has-[:focus-visible]:outline-offset-[calc(-1*var(--focus-ring))] has-[:focus-visible]:outline-ring has-[:focus-visible]:outline-solid"
      onKeyDown={pressKey}
      onKeyUp={releaseKey}
      onFocus={(event) => {
        if (event.target === event.currentTarget)
          input.current?.focus({ preventScroll: true });
      }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) letGo();
      }}
      onMouseDown={pressMouse}
      onMouseMove={(event) => {
        if (!pressed.current) moved(event.nativeEvent);
      }}
      onContextMenu={(event) => event.preventDefault()}
      onPaste={paste}
      onCopy={(event) => clipboard(event, "copy")}
      onCut={(event) => clipboard(event, "cut")}
    >
      <canvas
        ref={canvas}
        aria-hidden="true"
        className="absolute inset-0 size-full"
      />
      <textarea
        ref={input}
        tabIndex={-1}
        disabled={!shown || !enabled}
        aria-label={label}
        autoComplete="off"
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        data-browser-input=""
        className="pointer-events-none absolute inset-0 size-full resize-none opacity-0"
        onCompositionStart={() => {
          forgetComposition();
          composing.current = live.current.enabled && live.current.shown;
        }}
        onCompositionEnd={compositionEnded}
        onInput={textEntered}
      />
    </div>
  );
}
