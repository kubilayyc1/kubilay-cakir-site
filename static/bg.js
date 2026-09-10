(function () {
  const canvas = document.getElementById("bg-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let w, h, particles, raf, photo;
  const reduced =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  photo = new Image();
  photo.src =
    canvas.getAttribute("data-bg") || "/static/img/bg-photo.jpg";

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  }

  function drawCoverImage(img) {
    if (!img.complete || !img.naturalWidth) return false;
    const iw = img.naturalWidth;
    const ih = img.naturalHeight;
    const scale = Math.max(w / iw, h / ih);
    const dw = iw * scale;
    const dh = ih * scale;
    // bias upward a bit so faces stay in frame on wide screens
    const dx = (w - dw) / 2;
    const dy = (h - dh) * 0.25;
    ctx.drawImage(img, dx, dy, dw, dh);
    return true;
  }

  function makeParticles() {
    const n = reduced ? 10 : Math.min(45, Math.floor((w * h) / 22000));
    particles = Array.from({ length: n }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 1.5 + 0.3,
      vx: (Math.random() - 0.5) * (reduced ? 0.05 : 0.15),
      vy: (Math.random() - 0.5) * (reduced ? 0.05 : 0.15),
      a: Math.random() * 0.35 + 0.1,
      pulse: Math.random() * Math.PI * 2,
    }));
  }

  function tick() {
    ctx.fillStyle = "#050407";
    ctx.fillRect(0, 0, w, h);

    const ok = drawCoverImage(photo);
    if (!ok) {
      // fallback dark while loading
      const g = ctx.createLinearGradient(0, 0, w, h);
      g.addColorStop(0, "#07060a");
      g.addColorStop(1, "#050407");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
    }

    // dark scrim for readability (stronger at top for title)
    const scrim = ctx.createLinearGradient(0, 0, 0, h);
    scrim.addColorStop(0, "rgba(5,4,7,0.72)");
    scrim.addColorStop(0.45, "rgba(5,4,7,0.45)");
    scrim.addColorStop(1, "rgba(5,4,7,0.78)");
    ctx.fillStyle = scrim;
    ctx.fillRect(0, 0, w, h);

    // soft vignette
    const vig = ctx.createRadialGradient(w * 0.5, h * 0.45, h * 0.15, w * 0.5, h * 0.5, Math.max(w, h) * 0.75);
    vig.addColorStop(0, "rgba(0,0,0,0)");
    vig.addColorStop(1, "rgba(0,0,0,0.55)");
    ctx.fillStyle = vig;
    ctx.fillRect(0, 0, w, h);

    for (const p of particles) {
      p.x += p.vx;
      p.y += p.vy;
      p.pulse += 0.02;
      if (p.x < 0) p.x = w;
      if (p.x > w) p.x = 0;
      if (p.y < 0) p.y = h;
      if (p.y > h) p.y = 0;
      const alpha = p.a * (0.65 + 0.35 * Math.sin(p.pulse));
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(232, 212, 139, ${alpha})`;
      ctx.fill();
    }

    raf = requestAnimationFrame(tick);
  }

  function start() {
    resize();
    makeParticles();
    cancelAnimationFrame(raf);
    tick();
  }

  photo.onload = start;
  photo.onerror = start;
  window.addEventListener("resize", () => {
    resize();
    makeParticles();
  });
  if (photo.complete) start();
})();
