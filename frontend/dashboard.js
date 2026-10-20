/* Fosha Insights. Reads GET /api/v1/analytics?days=N (0 = all time). */
(() => {
  "use strict";
  const { store, t, esc, num, region, category, place } = Fosha;
  const $ = (s) => document.querySelector(s);
  const state = { range: store.get("range", 7), data: null };
  const COLORS = ["var(--azure)", "var(--coral)", "var(--ink)"];

  const pct = (x) => Math.round(x * 100);
  function trend(cur, prev, { kind = "rel", invert = false } = {}) {
    if (prev == null) return `<div class="trend">${esc(t("no_prev"))}</div>`;
    let diff, label;
    if (kind === "pp") { diff = (cur - prev) * 100; label = `${diff >= 0 ? "+" : ""}${num(diff, { maximumFractionDigits: 1 })} pp`; }
    else if (kind === "s") { diff = (cur - prev) / 1000; label = `${diff >= 0 ? "+" : ""}${num(diff, { maximumFractionDigits: 1 })}s`; }
    else { diff = prev ? ((cur - prev) / prev) * 100 : 0; label = `${diff >= 0 ? "+" : ""}${num(diff, { maximumFractionDigits: 1 })}%`; }
    const good = invert ? diff <= 0 : diff >= 0;
    return `<div class="trend ${good ? "good" : "bad"}">${diff >= 0 ? "▲" : "▼"} <b>${label}</b> ${esc(t("vs_prev"))}</div>`;
  }

  function countUp(el, to, { decimals = 0, suffix = "" } = {}) {
    const start = performance.now(), dur = 900;
    const tick = (now) => {
      const p = Math.min(1, (now - start) / dur), eased = 1 - Math.pow(1 - p, 3);
      el.innerHTML = num(to * eased, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  function orb(cur, prev) {
    const orbit = state.range ? t("dash_orbit", { n: num(state.range) }) : t("dash_orbit_all");
    const ar = Fosha.isAr();
    return `<div class="orb">
      <svg viewBox="-220 -220 440 440" aria-hidden="true">
        <defs><path id="orb-path" d="M0,-182 A182,182 0 1,1 0,182 A182,182 0 1,1 0,-182"/></defs>
        <circle r="215" fill="var(--azure)"/>
        <g><animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="60s" repeatCount="indefinite"/><text fill="var(--white)" text-anchor="middle" font-family="${ar ? "Lalezar" : "Changa One"}" font-size="${ar ? 24 : 21}" letter-spacing="2">
          <textPath href="#orb-path" startOffset="50%">${esc(orbit.repeat(ar ? 5 : 4))}</textPath></text></g>
      </svg>
      <div class="orb-center"><div class="big" data-count="${cur.total_queries}">0</div>
        <div class="unit">${esc(t("k_queries"))}</div>
        <div class="orb-planned">${esc(t("k_planned", { n: num(cur.planned) }))}</div>
        ${trend(cur.total_queries, prev?.total_queries)}</div></div>`;
  }

  function bars(items) {
    const max = Math.max(1, ...items.map((x) => x.count));
    return `<div class="bars">${items.map((x, i) => `<div class="bar-row"><span>${esc(region(x.name))}</span>
      <div class="bar-track"><div class="bar-fill" data-w="${(x.count / max) * 100}" style="background:${i === 0 ? COLORS[0] : i === 1 ? COLORS[1] : COLORS[2]}"></div></div>
      <span class="n">${num(x.count)}</span></div>`).join("")}</div>`;
  }

  function donut(en, ar) {
    const total = en + ar || 1, r = 76, c = 2 * Math.PI * r;
    return `<div class="donut"><svg viewBox="0 0 200 200" role="img" aria-label="${esc(t("lang_dist"))}">
        <circle cx="100" cy="100" r="${r}" fill="none" stroke="var(--coral)" stroke-width="30"/>
        <circle class="arc" cx="100" cy="100" r="${r}" fill="none" stroke="var(--azure)" stroke-width="30"
          stroke-dasharray="0 ${c}" data-dash="${(en / total) * c} ${c}" transform="rotate(-90 100 100)"/>
        <text x="100" y="108" text-anchor="middle" font-family="Changa One" font-size="30" fill="var(--ink)">${num(en + ar)}</text></svg>
      <div class="legend">
        <div class="row"><i style="background:var(--azure)"></i>${esc(t("english"))}</div><div class="pct">${num(pct(en / total))}%</div>
        <div class="row"><i style="background:var(--coral)"></i>${esc(t("arabic"))}</div><div class="pct">${num(pct(ar / total))}%</div>
      </div></div>`;
  }

  function columns(items) {
    const max = Math.max(1, ...items.map((x) => x.count));
    return `<div class="cols">${items.map((x, i) => `<div class="col"><span class="n">${num(x.count)}</span>
      <div class="b" data-h="${(x.count / max) * 82}" style="background:${COLORS[i % 3]}"></div></div>`).join("")}</div>
      <div class="col-labels">${items.map((x) => `<span title="${esc(region(x.name))}">${esc(region(x.name))}</span>`).join("")}</div>`;
  }

  function table(items) {
    const max = Math.max(1, ...items.map((x) => x.count));
    return `<table><thead><tr><th>#</th><th>${esc(t("t_name"))}</th><th>${esc(t("t_region"))}</th><th>${esc(t("t_category"))}</th><th class="num">${esc(t("t_count"))}</th></tr></thead>
      <tbody>${items.map((a, i) => `<tr><td class="rank">${num(i + 1)}</td><td class="name">${esc(place(a))}</td><td>${esc(region(a.region))}</td>
        <td>${esc(category(a.category))}</td><td class="num"><span class="mini" style="width:${(a.count / max) * 60}px"></span>${num(a.count)}</td></tr>`).join("")}</tbody></table>`;
  }

  function render() {
    const root = $("#dash");
    const data = state.data;
    if (!data) return;
    const cur = data.current, prev = data.previous;
    if (!cur.total_queries) {
      root.innerHTML = `<div class="empty"><div class="orb-sm"></div><h2>${esc(t("no_data_title"))}</h2>
        <p>${esc(t("no_data_body")).replace("uv run python -m api.seed", "<code>uv run python -m api.seed</code>")}</p>
        <a class="btn" href="/">${esc(t("open_app"))}</a></div>`;
      return;
    }
    const total = cur.total_queries, arShare = cur.languages.ar / total;
    const prevAr = prev && prev.total_queries ? prev.languages.ar / prev.total_queries : null;
    root.innerHTML = `
      <section class="hero">
        <div><h1>${esc(t("dash_title"))}</h1><p class="sub">${esc(t("dash_sub"))}</p>
          <div class="stats">
            <div class="stat"><div class="label">${esc(t("k_cache"))}</div><div class="value" data-count="${pct(cur.cache_hit_rate)}" data-suffix="<small>%</small>">0</div>${trend(cur.cache_hit_rate, prev?.cache_hit_rate, { kind: "pp" })}</div>
            <div class="stat"><div class="label">${esc(t("k_resp"))}</div><div class="value" data-count="${cur.avg_response_ms / 1000}" data-decimals="1" data-suffix="<small>s</small>">0</div>${trend(cur.avg_response_ms, prev?.avg_response_ms, { kind: "s", invert: true })}</div>
            <div class="stat"><div class="label">${esc(t("k_lang"))}</div><div class="value" data-count="${pct(arShare)}" data-suffix="<small>%</small>">0</div>${trend(arShare, prevAr, { kind: "pp" })}</div>
          </div></div>
        ${orb(cur, prev)}
      </section>
      <section class="panels">
        <article class="panel span-7" style="--i:0"><h2>${esc(t("destinations"))}</h2><p class="psub">${esc(t("destinations_sub"))}</p>${bars(data.destinations)}</article>
        <article class="panel span-5" style="--i:1"><h2>${esc(t("lang_dist"))}</h2><p class="psub">${esc(t("lang_dist_sub"))}</p>${donut(cur.languages.en, cur.languages.ar)}</article>
        <article class="panel span-5" style="--i:2"><h2>${esc(t("regions"))}</h2><p class="psub">${esc(t("regions_sub"))}</p>${columns(data.regions)}</article>
        <article class="panel span-7" style="--i:3"><h2>${esc(t("attractions"))}</h2><p class="psub">${esc(t("attractions_sub"))}</p>${table(data.attractions)}</article>
      </section>`;
    root.querySelectorAll("[data-count]").forEach((el) => countUp(el, +el.dataset.count, { decimals: +(el.dataset.decimals || 0), suffix: el.dataset.suffix || "" }));
    requestAnimationFrame(() => requestAnimationFrame(() => {
      root.querySelectorAll(".bar-fill").forEach((el) => { el.style.width = el.dataset.w + "%"; });
      root.querySelectorAll(".col .b").forEach((el) => { el.style.height = el.dataset.h + "%"; });
      root.querySelectorAll(".arc").forEach((el) => el.setAttribute("stroke-dasharray", el.dataset.dash));
    }));
  }

  async function load() {
    document.querySelectorAll("[data-range]").forEach((b) => b.setAttribute("aria-pressed", String(+b.dataset.range === state.range)));
    if (!state.data) $("#dash").innerHTML = `<div class="skeleton" style="height:340px;margin-bottom:20px"></div><div class="skeleton" style="height:300px"></div>`;
    try {
      const res = await fetch(`/api/v1/analytics?days=${state.range}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      state.data = await res.json();
      render();
    } catch (err) {
      $("#dash").innerHTML = `<div class="failed"><h2>${esc(t("load_error"))}</h2><p>${esc(String(err.message || err))}</p>
        <button type="button" class="btn" id="retry">${esc(t("refresh"))}</button></div>`;
    }
  }

  document.addEventListener("click", (e) => {
    const el = e.target.closest("button");
    if (!el) return;
    if (el.dataset.lang) { Fosha.setLang(el.dataset.lang); document.title = `${t("brand")} · ${t("dash_title")}`; render(); }
    else if (el.dataset.range != null) { state.range = +el.dataset.range; store.set("range", state.range); load(); }
    else if (el.id === "refresh" || el.id === "retry") load();
  });

  Fosha.setLang(Fosha.lang);
  document.title = `${t("brand")} · ${t("dash_title")}`;
  load();
})();
