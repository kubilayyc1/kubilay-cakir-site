(function () {
  function toast(msg, bad) {
    const host = document.getElementById("toast-host");
    if (!host || !msg) return;
    const el = document.createElement("div");
    el.className = "toast" + (bad ? " bad" : "");
    el.textContent = msg;
    host.appendChild(el);
    setTimeout(() => {
      el.classList.add("out");
      setTimeout(() => el.remove(), 260);
    }, 2800);
  }
  window.KCToast = toast;

  const toggle = document.getElementById("nav-toggle");
  const nav = document.getElementById("site-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Menüyü kapat" : "Menüyü aç");
    });
    nav.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => {
        nav.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  const copyBtn = document.getElementById("copy-iban");
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const raw = copyBtn.getAttribute("data-iban") || "";
      try {
        await navigator.clipboard.writeText(raw);
        copyBtn.classList.add("copied");
        copyBtn.textContent = "Kopyalandı";
        toast("IBAN kopyalandı");
        setTimeout(() => {
          copyBtn.classList.remove("copied");
          copyBtn.textContent = "Kopyala";
        }, 1800);
      } catch (_) {
        toast("Kopyalanamadı — manuel seçin", true);
      }
    });
  }
})();
