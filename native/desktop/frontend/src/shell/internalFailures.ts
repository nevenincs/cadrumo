const INTERNAL_FAILURE = "cadrumo-internal-failure";
let pending = false;
let listeners = 0;

export function notifyInternalFailure(): void {
  pending = listeners === 0;
  window.dispatchEvent(new Event(INTERNAL_FAILURE));
}

export function observeInternalFailures(listener: () => void): () => void {
  listeners++;
  window.addEventListener(INTERNAL_FAILURE, listener);
  if (pending) {
    pending = false;
    listener();
  }
  return () => {
    listeners--;
    window.removeEventListener(INTERNAL_FAILURE, listener);
  };
}
