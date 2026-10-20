/* The Fosha globe: DESIGN.md's azure sphere rising from the bottom of the page,
   with Egyptian landmarks standing on its rim and a white display headline
   curving along its top edge. It turns slowly, spins faster while the assistant is thinking,
   can be dragged, and swings a region's landmark to the top on request.

   FoshaGlobe.create(container, { onPick(region) }) ->
     { focus(region), release(), busy(bool), setText(str, fontFamily) } */
(() => {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const R = 500;                       // globe radius in SVG units
  const INK = "var(--ink)", WHITE = "var(--white)", CORAL = "var(--coral)", AZURE = "var(--azure)", WALL = "var(--wall)";

  const crenels = (x, y, w, size = 14) => {
    let d = "";
    for (let cx = x; cx < x + w - 1; cx += size * 2) d += `M${cx} ${y}h${size}v${-size}h${-size}Z`;
    return `<path d="${d}" fill="${WHITE}"/>`;
  };
  const palm = (x, h, lean = 0) => `
    <path d="M${x} 0 C${x + lean * 0.3} ${-h * 0.4} ${x + lean * 0.7} ${-h * 0.75} ${x + lean} ${-h}" fill="none" stroke-width="7"/>
    <path transform="translate(${x + lean} ${-h})" fill="var(--palm)" d="M0 0 C-30 -14 -58 -2 -66 18 C-44 4 -20 2 0 0 C-14 -30 -44 -38 -60 -30 C-36 -22 -14 -14 0 0 C10 -32 40 -40 58 -30 C34 -24 14 -14 0 0 C26 -12 54 -2 64 18 C42 6 22 2 0 0Z"/>`;

  // Each landmark stands on y=0 (the rim) and grows upwards (negative y).
  const LANDMARKS = [
    { region: "Alexandria", svg: `
      <rect x="-118" y="-95" width="34" height="95" fill="${WHITE}"/>${crenels(-118, -95, 34, 9)}
      <rect x="84" y="-95" width="34" height="95" fill="${WHITE}"/>${crenels(84, -95, 34, 9)}
      <rect x="-90" y="-70" width="180" height="70" fill="${WALL}"/>${crenels(-90, -70, 180, 12)}
      <rect x="-42" y="-150" width="84" height="80" fill="${WHITE}"/>${crenels(-42, -150, 84, 12)}
      <path d="M-14 0V-34a14 14 0 0 1 28 0V0Z" fill="${AZURE}"/>
      <rect x="-8" y="-128" width="16" height="26" fill="${INK}" stroke="none"/>` },
    { region: "Cairo", svg: `
      <path d="M-120 0 L-35 -165 L50 0Z" fill="${WHITE}"/><path d="M-35 -165 L50 0 L5 0Z" fill="${CORAL}"/>
      <path d="M30 0 L82 -100 L134 0Z" fill="${WHITE}"/><path d="M82 -100 L134 0 L104 0Z" fill="${CORAL}"/>` },
    { region: "Cairo", svg: `
      <rect x="-120" y="-105" width="48" height="105" fill="${WALL}"/>
      <rect x="-108" y="-88" width="10" height="16" fill="${WHITE}"/><rect x="-92" y="-88" width="10" height="16" fill="${WHITE}"/>
      <rect x="-108" y="-56" width="10" height="16" fill="${WHITE}"/><rect x="-92" y="-56" width="10" height="16" fill="${WHITE}"/>
      <rect x="-60" y="-70" width="100" height="70" fill="${WHITE}"/>
      <path d="M-50 -70 A40 40 0 0 1 30 -70Z" fill="${CORAL}"/>
      <path d="M-24 0V-30a14 14 0 0 1 28 0V0Z" fill="${AZURE}"/>
      <rect x="56" y="-190" width="24" height="190" fill="${WALL}"/>
      <rect x="50" y="-138" width="36" height="10" fill="${WHITE}"/><rect x="50" y="-82" width="36" height="10" fill="${WHITE}"/>
      <path d="M56 -190 L68 -222 L80 -190Z" fill="${CORAL}"/>` },
    { region: "South Sinai", svg: `
      <path d="M-125 0 L-45 -165 L5 -95 L48 -140 L125 0Z" fill="${CORAL}"/>
      <path d="M-45 -165 L-22 -118 L-45 -110 L-65 -124Z" fill="${WHITE}"/>
      <rect x="-60" y="-55" width="86" height="55" fill="${WHITE}"/>${crenels(-60, -55, 86, 8)}
      <rect x="-28" y="-92" width="22" height="37" fill="${WHITE}"/>
      <path d="M-17 -112 V-96 M-24 -105 H-10" fill="none" stroke-width="4"/>` },
    { region: "Red Sea", svg: `
      <path d="M-30 0 V-128" fill="none" stroke-width="6"/>
      <path d="M-115 -112 Q-30 -190 55 -112 Q34 -104 13 -112 Q-9 -104 -30 -112 Q-51 -104 -72 -112 Q-94 -104 -115 -112Z" fill="${CORAL}"/>
      <path d="M-72 -112 Q-52 -170 -30 -150 Q-8 -170 13 -112" fill="none" stroke-width="4"/>
      <path d="M45 -70 C65 -95 100 -95 116 -70 C100 -45 65 -45 45 -70Z" fill="${AZURE}"/>
      <path d="M116 -70 L138 -86 V-54Z" fill="${AZURE}"/><circle cx="62" cy="-72" r="4" fill="${INK}" stroke="none"/>` },
    { region: "Luxor", svg: `
      <path d="M-160 0 L-154 -175 L-146 -192 L-138 -175 L-132 0Z" fill="${WHITE}"/>
      <path d="M-115 0 L-104 -140 L-42 -140 L-32 0Z" fill="${WALL}"/>
      <path d="M32 0 L42 -140 L104 -140 L115 0Z" fill="${WALL}"/>
      <rect x="-32" y="-96" width="64" height="96" fill="${WHITE}"/>
      <rect x="-38" y="-108" width="76" height="14" fill="${CORAL}"/>
      <rect x="-15" y="-64" width="30" height="64" fill="${AZURE}"/>
      <path d="M-92 -112 H-56 M-90 -84 H-58 M54 -112 H90 M56 -84 H88" fill="none" stroke-width="4"/>` },
    { region: "Aswan", svg: `
      <path d="M-95 -6 H95 L70 22 H-70Z" fill="${CORAL}"/>
      <path d="M0 -6 V-215" fill="none" stroke-width="6"/>
      <path d="M2 -212 L104 -30 L-62 -30Z" fill="${WHITE}"/>
      <path d="M-130 44 q16 -12 32 0 t32 0 M40 50 q16 -12 32 0 t32 0" fill="none" stroke="${WHITE}" stroke-width="5"/>` },
    { region: "Aswan", svg: `
      <rect x="-118" y="-80" width="96" height="80" fill="${WHITE}"/>
      <path d="M-118 -80 A48 34 0 0 1 -22 -80Z" fill="${AZURE}"/>
      <path d="M-84 0V-40a14 14 0 0 1 28 0V0Z" fill="${CORAL}"/>
      <path d="M-110 -16 l8 -10 l8 10 l8 -10 l8 10 M-48 -16 l8 -10 l8 10 l8 -10" fill="none" stroke-width="3"/>
      <rect x="0" y="-62" width="110" height="62" fill="${WALL}"/>
      <path d="M0 -62 A55 28 0 0 1 110 -62Z" fill="${WHITE}"/>
      <rect x="44" y="-38" width="22" height="38" fill="${AZURE}"/>` },
    { region: "New Valley", svg: `
      <path d="M-40 0 C-30 -40 -46 -72 -30 -96 H18 C32 -72 18 -40 28 0Z" fill="${WHITE}"/>
      <path d="M-86 -94 C-86 -150 72 -150 72 -94 C40 -82 -50 -82 -86 -94Z" fill="${WHITE}"/>
      <path d="M50 0 C56 -46 108 -52 120 0Z" fill="${WHITE}"/>
      <path d="M-130 0 C-110 -26 -84 -26 -64 0Z" fill="${WALL}"/>` },
    { region: "Matrouh", svg: `${palm(-80, 150, -24)}${palm(10, 190, 10)}${palm(90, 130, 26)}
      <path d="M-125 0 C-80 -30 -30 -30 0 0 C30 -26 80 -26 125 0Z" fill="${WALL}"/>` },
  ];
  const STEP = 360 / LANDMARKS.length;
  const ARC = 452;                     // radius of the curved headline's baseline
  const SPREAD = (30 * Math.PI) / 180; // headline spans ±30° so it clears the input below

  function create(container, opts = {}) {
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    container.innerHTML = `
      <svg class="globe-svg" viewBox="-640 -700 1280 1280" aria-hidden="false" role="img">
        <defs><path id="arc-path" d="M${-ARC * Math.sin(SPREAD)},${-ARC * Math.cos(SPREAD)} A${ARC},${ARC} 0 0,1 ${ARC * Math.sin(SPREAD)},${-ARC * Math.cos(SPREAD)}"/></defs>
        <circle class="globe-body" r="${R}" fill="var(--azure)"/>
        <text class="globe-arc" fill="var(--white)" text-anchor="middle"><textPath href="#arc-path" startOffset="50%"></textPath></text>
        <g class="globe-turn">
          <g class="globe-rim" stroke="var(--ink)" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"></g>
        </g>
      </svg>`;
    const svg = container.querySelector("svg");
    const turn = svg.querySelector(".globe-turn");
    const rim = svg.querySelector(".globe-rim");
    const textPath = svg.querySelector("textPath");

    LANDMARKS.forEach((lm, i) => {
      const g = document.createElementNS(NS, "g");
      g.setAttribute("transform", `rotate(${i * STEP}) translate(0 ${-R + 4})`);
      g.setAttribute("class", "landmark");
      g.setAttribute("tabindex", "0");
      g.setAttribute("role", "button");
      g.dataset.region = lm.region;
      g.innerHTML = `<rect x="-140" y="-230" width="280" height="250" fill="transparent" stroke="none"/>${lm.svg}`;
      rim.appendChild(g);
    });

    let angle = -STEP;               // start with the pyramids facing up
    let velocity = 0;                 // extra spin from dragging (deg/s)
    let target = null;
    let busy = false;
    const BASE = reduced ? 0 : 5;     // deg/s
    const BUSY = reduced ? 0 : 45;

    function frame(now) {
      const dt = Math.min(0.05, (now - (frame.last || now)) / 1000);
      frame.last = now;
      if (target != null && !busy) {
        const diff = ((target - angle + 540) % 360) - 180;
        angle += diff * (1 - Math.exp(-dt * 5));
      } else {
        angle += ((busy ? BUSY : BASE) + velocity) * dt;
      }
      velocity *= Math.exp(-dt * 1.6);
      turn.setAttribute("transform", `rotate(${angle.toFixed(3)})`);
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);

    // Drag to spin. A press that barely moves counts as a click on a landmark.
    let drag = null;
    svg.addEventListener("pointerdown", (e) => {
      drag = { x: e.clientX, last: e.clientX, t: performance.now(), moved: 0 };
      svg.setPointerCapture(e.pointerId);
      target = null;
    });
    svg.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const dx = e.clientX - drag.last, now = performance.now();
      const scale = 360 / (Math.PI * svg.getBoundingClientRect().width * 0.8);
      angle += dx * scale;
      velocity = (dx * scale) / Math.max(0.008, (now - drag.t) / 1000);
      velocity = Math.max(-400, Math.min(400, velocity));
      drag.moved += Math.abs(dx);
      drag.last = e.clientX;
      drag.t = now;
    });
    const end = (e) => {
      if (!drag) return;
      if (drag.moved < 6) {
        velocity = 0;
        const hit = document.elementsFromPoint(e.clientX, e.clientY).find((el) => el.closest?.(".landmark"));
        const lm = hit?.closest(".landmark");
        if (lm && opts.onPick) { focus(lm.dataset.region); opts.onPick(lm.dataset.region); }
      }
      drag = null;
    };
    svg.addEventListener("pointerup", end);
    svg.addEventListener("pointercancel", () => { drag = null; });
    svg.addEventListener("keydown", (e) => {
      const lm = e.target.closest(".landmark");
      if (lm && (e.key === "Enter" || e.key === " ") && opts.onPick) { e.preventDefault(); focus(lm.dataset.region); opts.onPick(lm.dataset.region); }
    });

    function focus(region) {
      const i = LANDMARKS.findIndex((lm) => lm.region === region);
      if (i < 0) return;
      target = -i * STEP;
      velocity = 0;
    }
    return {
      focus,
      release() { target = null; },
      busy(on) { busy = !!on; if (on) target = null; },
      setText(text, family, size = 38) {
        textPath.textContent = text;
        textPath.parentNode.setAttribute("font-family", family);
        textPath.parentNode.setAttribute("font-size", size);
      },
      setLabels(labeler) {
        rim.querySelectorAll(".landmark").forEach((g) => g.setAttribute("aria-label", labeler(g.dataset.region)));
      },
    };
  }

  window.FoshaGlobe = { create };
})();
