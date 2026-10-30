type SavePicker = (options: {
  suggestedName: string;
  startIn: "downloads";
  types: { description: string; accept: Record<string, string[]> }[];
}) => Promise<{
  createWritable(): Promise<{
    write(text: string): Promise<void>;
    close(): Promise<void>;
    abort(): Promise<void>;
  }>;
}>;

/** Browser development uses the browser's picker; the host owns native exports.
 * `fileType` names the kind of file in the picker's type list, in the
 * person's language. */
export async function saveLogs(text: string, fileType: string): Promise<void> {
  const suggestedName = `cadrumo-session-${Date.now()}.log`;
  const picker = (window as Window & { showSaveFilePicker?: SavePicker })
    .showSaveFilePicker;
  if (picker) {
    const file = await picker.call(window, {
      suggestedName,
      startIn: "downloads",
      types: [
        { description: fileType, accept: { "text/plain": [".log", ".txt"] } },
      ],
    });
    const stream = await file.createWritable();
    try {
      await stream.write(text);
      await stream.close();
    } catch (error) {
      await stream.abort().catch(() => {});
      throw error;
    }
    return;
  }
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/plain;charset=utf-8" }),
  );
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = suggestedName;
    link.click();
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
