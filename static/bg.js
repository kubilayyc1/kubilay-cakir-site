(function () {
  const canvas = document.getElementById("bg-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let w, h, orbs, particles, leaves, raf, leafImg;
  const reduced =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  leafImg = new Image();
  leafImg.src =
    canvas.getAttribute("data-leaf") ||
    "/static/img/cannabis-leaf-clean.png";

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  }

  function makeOrbs() {
    const s = Math.min(w, h);
    orbs = [
      { x: w * 0.2, y: h * 0.18, r: s * 0.38, a: 0.2, vx: 0.06, vy: 0.04, hue: "gold" },
      { x: w * 0.82, y: h * 0.72, r: s * 0.32, a: 0.16, vx: -0.05, vy: -0.03, hue: "amber" },
      { x: w * 0.55, y: h * 0.4, r: s * 0.22, a: 0.1, vx: 0.03, vy: -0.04, hue: "soft" },
      { x: w * 0.1, y: h * 0.75, r: s * 0.2, a: 0.09, vx: 0.04, vy: -0.02, hue: "gold" },
    ];
  }

  function makeParticles() {
    const n = reduced ? 16 : Math.min(70, Math.floor((w * h) / 16000));
    particles = Array.from({ length: n }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 1.8 + 0.35,
      vx: (Math.random() - 0.5) * (reduced ? 0.07 : 0.22),
      vy: (Math.random() - 0.5) * (reduced ? 0.07 : 0.22),
      a: Math.random() * 0.5 + 0.15,
      pulse: Math.random() * Math.PI * 2,
    }));
  }

  function makeLeaves() {
    const base = Math.min(w, h);
    leaves = [
      { x: w * 0.78, y: h * 0.46, s: base * 1.25, r: -0.22, vr: reduced ? 0 : 0.0004, a: 0.85 },
      { x: w * 0.14, y: h * 0.72, s: base * 0.75, r: 0.42, vr: reduced ? 0 : -0.00035, a: 0.55 },
      { x: w * 0.5, y: h * 0.12, s: base * 0.42, r: 0.12, vr: reduced ? 0 : 0.00045, a: 0.35 },
    ];
  }

  function drawLeaf(L) {
    if (!leafImg.complete || !leafImg.naturalWidth) return;
    ctx.save();
    ctx.translate(L.x, L.y);
    ctx.rotate(L.r);
    ctx.globalAlpha = L.a;
    ctx.drawImage(leafImg, -L.s / 2, -L.s / 2, L.s, L.s);
    ctx.restore();
  }

  function tick() {
    // dark luxury background (keep this look)
    const g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, "#07060a");
    g.addColorStop(0.45, "#0c0a0f");
    g.addColorStop(1, "#050407");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);

    for (const o of orbs) {
      if (!reduced) {
        o.x += o.vx;
        o.y += o.vy;
        if (o.x < -o.r || o.x > w + o.r) o.vx *= -1;
        if (o.y < -o.r || o.y > h + o.r) o.vy *= -1;
      }
      const rg = ctx.createRadialGradient(o.x, o.y, 0, o.x, o.y, o.r);
      if (o.hue === "amber") {
        rg.addColorStop(0, `rgba(180,120,40,${o.a})`);
        rg.addColorStop(0.5, `rgba(120,70,20,${o.a * 0.35})`);
      } else if (o.hue === "soft") {
        rg.addColorStop(0, `rgba(232,212,139,${o.a * 0.7})`);
        rg.addColorStop(0.5, `rgba(201,162,39,${o.a * 0.25})`);
      } else {
        rg.addColorStop(0, `rgba(212,175,55,${o.a})`);
        rg.addColorStop(0.45, `rgba(138,112,32,${o.a * 0.35})`);
      }
      rg.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = rg;
      ctx.beginPath();
      ctx.arc(o.x, o.y, o.r, 0, Math.PI * 2);
      ctx.fill();
    }

    for (const p of particles) {
      p.x += p.vx;
      p.y += p.vy;
      p.pulse += 0.02;
      if (p.x < 0) p.x = w;
      if (p.x > w) p.x = 0;
      if (p.y < 0) p.y = h;
      if (p.y > h) p.y = 0;
      const alpha = p.a * (0.7 + 0.3 * Math.sin(p.pulse));
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(232, 212, 139, ${alpha})`;
      ctx.fill();
    }

    if (!reduced) {
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < Math.min(i + 8, particles.length); j++) {
          const a = particles[i], b = particles[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const d = Math.hypot(dx, dy);
          if (d < 110) {
            ctx.strokeStyle = `rgba(201,162,39,${0.08 * (1 - d / 110)})`;
            ctx.lineWidth = 0.7;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }
    }

    // cannabis ON TOP of the dark background (no white plate)
    for (const L of leaves) {
      if (!reduced) L.r += L.vr;
      drawLeaf(L);
    }

    raf = requestAnimationFrame(tick);
  }

  function start() {
    resize();
    makeOrbs();
    makeParticles();
    makeLeaves();
    cancelAnimationFrame(raf);
    tick();
  }

  leafImg.onload = start;
  leafImg.onerror = start;
  window.addEventListener("resize", () => {
    resize();
    makeOrbs();
    makeParticles();
    makeLeaves();
  });
  if (leafImg.complete) start();
})();
