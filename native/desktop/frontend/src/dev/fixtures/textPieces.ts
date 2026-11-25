/** The length of each streamed piece of text. */
const PIECE = 8;

/** `text` in pieces of a few characters, whole characters each. */
export const pieces = (text: string) => {
  const out: string[] = [];
  const characters = [...text];
  for (let at = 0; at < characters.length; at += PIECE)
    out.push(characters.slice(at, at + PIECE).join(""));
  return out;
};
