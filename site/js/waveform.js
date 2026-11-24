/* ============================================================
   VoiceOS — Waveform visual (gradient confined to this canvas per DESIGN.md)
   ============================================================ */

(function () {
  const canvas = document.getElementById("waveform");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.parentElement.getBoundingClientRect();
  const size = Math.round(rect.width);

  canvas.width = size * dpr;
  canvas.height = size * dpr;
  ctx.scale(dpr, dpr);
  canvas.style.width = size + "px";
  canvas.style.height = size + "px";

  const cx = size / 2;
  const cy = size / 2;
  const baseRadius = size / 2 - 24;
  const barCount = 72;
  const barWidth = 3;
  const barGap = 3;

  // Gradient voice palette — cyan → blue → violet → magenta
  const colors = ["#00e5ff", "#0066ff", "#8b00ff", "#ff00cc"];

  let t = 0;
  let rafId;

  function lerp(a, b, k) {
    return a + (b - a) * k;
  }

  function draw() {
    t += 0.025;
    ctx.clearRect(0, 0, size, size);

    // Outer decorative glow (soft, behind bars)
    const glow = ctx.createRadialGradient(cx, cy, size * 0.1, cx, cy, size * 0.45);
    glow.addColorStop(0, "rgba(0, 229, 255, 0.12)");
    glow.addColorStop(1, "rgba(0, 229, 255, 0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(cx, cy, size * 0.42, 0, Math.PI * 2);
    ctx.fill();

    for (let i = 0; i < barCount; i++) {
      const angle = (i / barCount) * Math.PI * 2;
      const phase = Math.sin(t + i * 0.18) * 0.5 + 0.5;
      const height = 20 + phase * (baseRadius * 0.55);
      const color = colors[Math.floor((i / barCount) * colors.length)];

      const x1 = cx + Math.cos(angle) * (baseRadius - height);
      const y1 = cy + Math.sin(angle) * (baseRadius - height);
      const x2 = cx + Math.cos(angle) * baseRadius;
      const y2 = cy + Math.sin(angle) * baseRadius;

      ctx.save();
      ctx.translate((x1 + x2) / 2, (y1 + y2) / 2);
      ctx.rotate(angle);
      ctx.fillStyle = color;
      ctx.shadowColor = color;
      ctx.shadowBlur = 14;
      ctx.fillRect(-barWidth / 2, -height / 2, barWidth, height);
      ctx.restore();
    }

    rafId = requestAnimationFrame(draw);
  }

  draw();

  // Pause when tab hidden (respect battery/lifecycle)
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      cancelAnimationFrame(rafId);
    } else {
      draw();
    }
  });
})();