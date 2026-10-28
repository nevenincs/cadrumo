import { Channel } from "@tauri-apps/api/core";
import type { ChannelRawFrame, SedeViewDelivery } from "../ipc/contract";
import type { HostCall } from "./hostCall";
import { sedeViewReader, type SedeViewPort } from "./sedeView";

function isRawFrame(delivery: SedeViewDelivery): delivery is ChannelRawFrame {
  return (
    typeof delivery === "object" &&
    delivery !== null &&
    typeof (delivery as Partial<ChannelRawFrame>).raw_frame === "string"
  );
}

/** The Sede view port over the desktop host's `sede_view_*` commands. */
export function tauriSedeView(call: HostCall): SedeViewPort {
  return {
    async open(size, listener) {
      const messages = new Channel<SedeViewDelivery>();
      const reader = sedeViewReader((event) => {
        listener(event);
        if (event.kind === "ended") messages.onmessage = () => undefined;
      });
      // An image's bytes arrive as a named frame the host holds; taking it
      // is asynchronous, so every delivery waits for the one before it and
      // the reader still sees them in order. A frame that cannot be taken
      // becomes empty bytes: the image is then credited without being drawn.
      let delivered: Promise<void> = Promise.resolve();
      messages.onmessage = (delivery) => {
        const resolved = isRawFrame(delivery)
          ? call("shell_channel_frame", { frame: delivery.raw_frame }).catch(
              () => new ArrayBuffer(0),
            )
          : delivery;
        delivered = delivered.then(async () => reader.accept(await resolved));
      };

      let opened: { view: number };
      try {
        opened = await call("sede_view_open", { ...size, messages });
      } catch (error) {
        messages.onmessage = () => undefined;
        throw error;
      }
      const id = opened.view;
      reader.open(id);

      return {
        input: (event) =>
          call("sede_view_input", { view: id, event }).then(() => undefined),
        navigate: (verb) =>
          call("sede_view_navigate", { view: id, verb }).then(() => undefined),
        resize: ({ cssWidth, cssHeight, scale }) =>
          call("sede_view_resize", {
            view: id,
            cssWidth,
            cssHeight,
            scale,
          }).then(() => undefined),
        credit: () =>
          call("sede_view_credit", { view: id }).then(() => undefined),
        dialog: (dialogId, accept, promptText) =>
          call("sede_view_dialog", {
            view: id,
            dialogId,
            accept,
            ...(promptText === undefined ? {} : { promptText }),
          }).then(() => undefined),
        downloadAnswer: (transferId, save) =>
          call("sede_view_download_answer", { view: id, transferId, save }),
        fileChooserAnswer: (chooserId, choose) =>
          call("sede_view_file_chooser_answer", {
            view: id,
            chooserId,
            choose,
          }),
        openExternal: () =>
          call("sede_view_open_external", { view: id }).then(() => undefined),
        close: () =>
          call("sede_view_close", { view: id }).then(() => undefined),
      };
    },
  };
}
