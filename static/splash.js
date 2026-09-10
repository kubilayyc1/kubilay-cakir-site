(function () {
  const COOKIE = "kc_welcome_splash";
  const MAX_AGE = 60 * 60 * 24; // ~24h

  function getCookie(name) {
    const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : "";
  }
  function setCookie(name, value, maxAge) {
    document.cookie =
      name +
      "=" +
      encodeURIComponent(value) +
      "; path=/; max-age=" +
      maxAge +
      "; SameSite=Lax";
  }

  const root = document.getElementById("welcome-splash");
  if (!root) return;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const seen =
    getCookie(COOKIE) === "1" ||
    (function () {
      try {
        return sessionStorage.getItem(COOKIE) === "1";
      } catch (_) {
        return false;
      }
    })();

  if (seen) {
    root.remove();
    return;
  }

  root.hidden = false;
  root.setAttribute("aria-hidden", "false");
  document.documentElement.classList.add("splash-active");

  const canvas = document.getElementById("splash-canvas");
  let raf = 0;
  let start = performance.now();
  const duration = reduced ? 600 : 2800;

  function markSeen() {
    setCookie(COOKIE, "1", MAX_AGE);
    try {
      sessionStorage.setItem(COOKIE, "1");
    } catch (_) {}
  }

  function dismiss() {
    cancelAnimationFrame(raf);
    root.classList.add("is-hiding");
    markSeen();
    document.documentElement.classList.remove("splash-active");
    setTimeout(() => {
      root.remove();
    }, reduced ? 220 : 950);
  }

  const skip = document.getElementById("splash-skip");
  if (skip) skip.addEventListener("click", dismiss);

  if (canvas && canvas.getContext && !reduced) {
    const ctx = canvas.getContext("2d");
    const particles = [];
    const lines = [];

    function resize() {
      canvas.width = window.innerWidth * devicePixelRatio;
      canvas.height = window.innerHeight * devicePixelRatio;
      canvas.style.width = window.innerWidth + "px";
      canvas.style.height = window.innerHeight + "px";
      ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    }
    resize();
    window.addEventListener("resize", resize, { passive: true });

    for (let i = 0; i < 36; i++) {
      particles.push({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        r: 0.6 + Math.random() * 1.6,
        vx: (Math.random() - 0.5) * 0.18,
        vy: -0.05 - Math.random() * 0.2,
        a: 0.15 + Math.random() * 0.45,
      });
    }
    for (let i = 0; i < 5; i++) {
      lines.push({
        y: (window.innerHeight * (0.25 + i * 0.12)) | 0,
        phase: Math.random() * Math.PI * 2,
        amp: 8 + Math.random() * 14,
      });
    }

    function frame(now) {
      const w = window.innerWidth;
      const h = window.innerHeight;
      ctx.clearRect(0, 0, w, h);

      // soft vignette glow
      const g = ctx.createRadialGradient(w / 2, h * 0.42, 20, w / 2, h * 0.42, Math.max(w, h) * 0.55);
      g.addColorStop(0, "rgba(201,162,39,0.08)");
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);

      ctx.strokeStyle = "rgba(232,212,139,0.12)";
      ctx.lineWidth = 1;
      lines.forEach((ln, i) => {
        ctx.beginPath();
        const mid = w / 2;
        const span = Math.min(280, w * 0.35);
        const y =
          ln.y +
          Math.sin(now / 1800 + ln.phase) * ln.amp * 0.15;
        ctx.moveTo(mid - span, y);
        ctx.quadraticCurveTo(
          mid,
          y + Math.sin(now / 1400 + i) * 4,
          mid + span,
          y
        );
        ctx.stroke();
      });

      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.y < -10) {
          p.y = h + 10;
          p.x = Math.random() * w;
        }
        ctx.beginPath();
        ctx.fillStyle = "rgba(232,212,139," + p.a + ")";
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      });

      if (now - start < duration) {
        raf = requestAnimationFrame(frame);
      } else {
        dismiss();
      }
    }
    raf = requestAnimationFrame(frame);
  } else {
    setTimeout(dismiss, duration);
  }
})();
