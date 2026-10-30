/** Simple spring animation for panel open/close (respects reduced motion). */

export function animatePanel(
  el: HTMLElement,
  open: boolean,
  onDone?: () => void,
): void {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced) {
    el.classList.toggle("open", open);
    el.hidden = !open;
    onDone?.();
    return;
  }

  if (open) {
    el.hidden = false;
    el.classList.remove("open");
    requestAnimationFrame(() => {
      el.classList.add("open");
      window.setTimeout(() => onDone?.(), 320);
    });
  } else {
    el.classList.remove("open");
    window.setTimeout(() => {
      el.hidden = true;
      onDone?.();
    }, 280);
  }
}
