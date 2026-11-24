/* ============================================================
   VoiceOS — Siri-style waveform visual (one authored motion moment)
   Vertical bars with varying heights, smooth sine animation,
   voice gradient (cyan → blue → violet → magenta) on glass capsule.
   ============================================================ */

(function () {
  const canvas = document.getElementById("waveform");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;

  // Voice gradient palette
  const colors = ["#00e5ff", "#0066ff", "#8b00ff", "#ff00cc"];

  let width = 0;
  let height = 0;
  let bars = [];
  let t = 0;
  let rafId;

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    width = rect.width;
    height = rect.height;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";

    // Bar layout: 28 bars, spaced evenly across width
    const barCount = 28;
    const barWidth = 6;
    const barGap = 8;
    const totalWidth = barCount * barWidth + (barCount - 1) * barGap;
    const startX = (width - totalWidth) / 2;

    bars = [];
    for (let i = 0; i < barCount; i++) {
      bars.push({
        x: startX + i * (barWidth + barGap),
        w: barWidth,
        baseHeight: height * 0.35,
        phase: (i / barCount) * Math.PI * 2,
        amp: 0.5 + Math.random() * 0.5,
        speed: 0.015 + Math.random() * 0.02,
      });
    }
  }

  function draw() {
    t += 0.02;

    ctx.clearRect(0, 0, width, height);

    // Glass capsule background
    const capsule = ctx.createLinearGradient(0, 0, 0, height);
    capsule.addColorStop(0, "rgba(255, 255, 255, 0.06)");
    capsule.addColorStop(0.5, "rgba(255, 255, 255, 0.03)");
    capsule.addColorStop(1, "rgba(255, 255, 255, 0.06)");

    ctx.fillStyle = capsule;
    ctx.beginPath();
    ctx.roundRect(0, 0, width, height, height / 2);
    ctx.fill();

    ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(0, 0, width, height, height / 2);
    ctx.stroke();

    // Draw bars
    const centerY = height / 2;
    const maxBarHeight = height * 0.75;

    bars.forEach((bar) => {
      const phase = Math.sin(t + bar.phase) * 0.5 + 0.5;
      const barHeight = bar.baseHeight * (0.4 + phase * 0.6 * bar.amp);
      const barTop = centerY - barHeight / 2;

      // Color by position across the gradient
      const colorIndex = Math.floor((bar.x / width) * colors.length);
      const color = colors[Math.min(colorIndex, colors.length - 1)];

      // Glass bar with glow
      ctx.fillStyle = color;
      ctx.shadowColor = color;
      ctx.shadowBlur = barHeight > height * 0.5 ? 16 : 8;
      ctx.fillRect(bar.x, barTop, bar.w, barHeight);
      ctx.shadowBlur = 0;

      // Inner highlight (clear glass edge)
      ctx.fillStyle = "rgba(255, 255, 255, 0.2)";
      ctx.fillRect(bar.x, barTop, bar.w * 0.35, barHeight);
    });

    rafId = requestAnimationFrame(draw);
  }

  window.addEventListener("resize", resize);
  resize();
  draw();

  // Pause when tab hidden
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      cancelAnimationFrame(rafId);
    } else {
      draw();
    }
  });
})();