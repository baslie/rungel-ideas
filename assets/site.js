// Общее для обеих страниц: тема, шапка поверх hero, появление блоков.
(() => {
  const root = document.documentElement, btn = document.getElementById("theme");
  const mq = matchMedia("(prefers-color-scheme: dark)");
  const isDark = () => root.dataset.theme ? root.dataset.theme === "dark" : mq.matches;
  const paint = () => { const d = isDark(); btn.textContent = d ? "☀" : "☾"; btn.setAttribute("aria-label", d ? "Включить светлую тему" : "Включить тёмную тему"); };
  btn.addEventListener("click", () => { const t = isDark() ? "light" : "dark"; root.dataset.theme = t; try { localStorage.setItem("rungel-theme", t); } catch (e) {} paint(); });
  mq.addEventListener?.("change", paint);
  paint();

  // шапка прозрачная, пока под ней hero; дальше — сплошная
  const head = document.querySelector(".site-head"), hero = document.querySelector(".hero");
  if (head && hero && "IntersectionObserver" in window) {
    new IntersectionObserver(([e]) => head.classList.toggle("solid", !e.isIntersecting), { rootMargin: "-64px 0px 0px 0px" }).observe(hero);
  } else head?.classList.add("solid");

  // интро первого экрана: ждём картинку неба, даём секунду посмотреть на коллаж и раскрываем
  if (root.classList.contains("hero-intro")) {
    const open = () => root.classList.remove("hero-intro");
    const img = document.querySelector(".hero.stage .hero-img");
    (img?.decode ? img.decode().catch(() => {}) : Promise.resolve()).then(() => setTimeout(open, 1100));
    setTimeout(open, 4000);
  }

  const els = document.querySelectorAll(".rv");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    }), { rootMargin: "0px 0px -6% 0px" });
    els.forEach(e => io.observe(e));
  } else els.forEach(e => e.classList.add("in"));
})();
