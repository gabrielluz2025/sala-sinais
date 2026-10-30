export function initStarfield(canvas: HTMLCanvasElement): () => void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return () => {};

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let w = 0;
  let h = 0;
  const stars: { x: number; y: number; z: number; s: number }[] = [];

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
    if (stars.length < 120) {
      for (let i = stars.length; i < 120; i++) {
        stars.push({
          x: Math.random() * w,
          y: Math.random() * h,
          z: Math.random(),
          s: Math.random() * 1.5 + 0.3,
        });
      }
    }
  }

  resize();
  window.addEventListener("resize", resize);

  let raf = 0;
  function draw() {
    if (!ctx) return;
    ctx.fillStyle = "#05060f";
    ctx.fillRect(0, 0, w, h);
    const t = Date.now() * 0.00015;
    for (const st of stars) {
      const drift = reduced ? 0 : Math.sin(t + st.z * 10) * 0.3;
      ctx.fillStyle = `rgba(200, 220, 255, ${0.25 + st.z * 0.5})`;
      ctx.beginPath();
      ctx.arc(st.x + drift, st.y + drift * 0.5, st.s, 0, Math.PI * 2);
      ctx.fill();
    }
    raf = requestAnimationFrame(draw);
  }
  draw();

  return () => {
    cancelAnimationFrame(raf);
    window.removeEventListener("resize", resize);
  };
}
