/* Fosha traveller app. No build step, no framework.
   Talks to api/server.py:  POST /api/v1/chat {message}  ·  GET /api/v1/health */
(() => {
  "use strict";
  const { store, t, esc, num, region, category, place, weekday, duration } = Fosha;
  const $ = (s, r = document) => r.querySelector(s);
  const body = document.body;
  const input = $("#input");
  const chatModal = $("#chat-modal");
  const chatInput = $("#chat-input");
  const chatComposer = $("#chat-composer");
  const chatSend = $("#chat-send");
  const sendBtn = $("#send");

  function openChat(open = true) {
    if (chatModal) {
      chatModal.hidden = !open;
      body.classList.toggle("chat-open", open);
      if (open) {
        scrollToEnd();
        setTimeout(() => chatInput && chatInput.focus(), 60);
      }
    }
  }

  const state = {
    messages: store.get("messages", []),   // {role: "user"|"ai"|"error", text, result?}
    plan: store.get("plan", null),         // last result with status "planned"
    pending: store.get("pending", null),   // message waiting for a missing detail
    visitor: store.get("visitor", "foreigner"),
    dayIdx: 0,
    expanded: new Set(),
    busy: false,
    lastSent: null,
  };
  const save = () => {
    store.set("messages", state.messages.slice(-40));
    store.set("plan", state.plan);
    store.set("pending", state.pending);
  };

  // ---------- Globe ----------
  const globe = FoshaGlobe.create($("#globe"), {
    onPick(r) {
      const prefill = t("globe_prefill", { region: region(r) });
      openChat(true);
      if (chatInput) {
        chatInput.value = prefill;
        chatInput.focus();
        chatInput.setSelectionRange(chatInput.value.length, chatInput.value.length);
      }
    },
  });
  function paintGlobeText() {
    const ar = Fosha.isAr();
    globe.setText(t("orbit"), ar ? "Almarai" : "Changa One", ar ? 40 : 38);
    globe.setLabels((r) => region(r));
  }

  // ---------- Small render helpers ----------
  const arrow = `<svg class="arrow" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h15M13 5l7 7-7 7" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

  function md(text) {
    const lines = esc(text).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").split("\n");
    let html = "", list = false;
    for (const raw of lines) {
      const line = raw.trim();
      const item = line.match(/^[-*•]\s+(.*)/);
      if (item) { if (!list) { html += "<ul>"; list = true; } html += `<li>${item[1]}</li>`; continue; }
      if (list) { html += "</ul>"; list = false; }
      if (line) html += `<p>${line}</p>`;
    }
    return html + (list ? "</ul>" : "");
  }
  const intro = (text) => text.split(/\n\s*\n|\n(?=\s*[-*•]|\s*\*\*)/)[0];

  const planTitle = (plan) => {
    const days = plan.itinerary.days;
    const areas = [...new Set(days.map((d) => region(d.area)))].join(Fosha.isAr() ? " و" : " & ");
    return days.length === 1 ? t("one_day_in", { place: areas }) : t("days_in", { n: num(days.length), place: areas });
  };
  const price = (s) => (state.visitor === "egyptian" ? s.price_egyptian_egp : s.price_foreigner_egp) || 0;
  const money = (n) => (n ? `${num(n)} ${t("egp")}` : t("free"));
  const totals = (stops) => ({ min: stops.reduce((a, s) => a + s.duration_min, 0), egp: stops.reduce((a, s) => a + price(s), 0) });

  // ---------- Conversation ----------
  const REGION_CHOICES = ["Cairo", "Luxor", "Aswan", "Alexandria", "Red Sea", "South Sinai"];

  function quickReplies(result) {
    if (result.status === "needs_clarification") {
      const missing = result.missing || [];
      const groups = [];
      if (missing.includes("days")) {
        groups.push({ label: t("how_many_days"), items: t("day_options").map(([label, msg]) => ({ label, msg })) });
      }
      if (missing.includes("region")) {
        groups.push({ label: t("which_region"), items: REGION_CHOICES.map((r) => ({ label: region(r), msg: region(r), region: r })) });
      }
      if (!result.intent?.budget) {
        groups.push({ label: t("budget_label"), items: t("budget_options").map(([label, msg]) => ({ label, msg })) });
      }
      if (!result.intent?.travelers) {
        groups.push({ label: t("travelers_label"), items: t("travelers_options").map(([label, msg]) => ({ label, msg })) });
      }
      return groups.length ? { groups } : null;
    }
    if (["unsupported_region", "out_of_scope", "no_results"].includes(result.status)) {
      return { groups: [{ label: t("try_instead"), items: t("chips").map((c) => ({ label: c.label, msg: c.msg, region: c.region, fresh: true })) }] };
    }
    return null;
  }

  function renderMessage(m, isLast) {
    if (m.role === "user") return `<div class="msg user">${esc(m.text)}</div>`;
    if (m.role === "error") {
      return `<div class="msg ai"><div class="who">${esc(t("ai"))}</div><div class="error">
        <strong>${esc(t("error_title"))}</strong>${esc(t("error_body"))}
        ${isLast ? `<div><button type="button" class="btn" data-retry>${esc(t("retry"))}</button></div>` : ""}</div></div>`;
    }
    const r = m.result || {};
    let inner;
    if (r.status === "planned" && r.itinerary) {
      const days = r.itinerary.days.map((d) => `<li><b>${esc(t("day"))} ${num(d.day)}</b>
        <div><b>${esc(region(d.area))}</b><br><span>${d.stops.map((s) => esc(place(s))).join(" · ")}</span></div></li>`).join("");
      const recs = r.itinerary.recommendations || {};
      const hotels = recs.hotels || [];
      const transport = recs.transport || [];
      const recsSummary = (hotels.length || transport.length)
        ? `<div class="plan-recs-summary"><span>🏨 ${esc(hotels[0]?.area || t("recs_hotels"))}</span> · <span>🚗 ${esc(transport[0]?.mode || t("recs_transport"))}</span></div>`
        : "";
      inner = `<div class="text">${md(intro(m.text))}</div>
        <div class="plan-card"><div class="eyebrow">${esc(t("plan_ready"))}</div><h3>${esc(planTitle(r))}</h3>
          <ol class="plan-days">${days}</ol>
          ${recsSummary}
          <button type="button" class="btn" data-open-sheet>${esc(t("open_plan"))} ${arrow}</button></div>
        <details class="full"><summary>${esc(t("full_reply"))}</summary><div class="text">${md(m.text)}</div></details>`;
    } else {
      inner = `<div class="text">${md(m.text)}</div>`;
      const q = isLast ? quickReplies(r) : null;
      if (q && q.groups) {
        inner += `<div class="quick-groups">${q.groups.map((g) =>
          `<div class="quick"><span class="quick-label">${esc(g.label)}</span>
            <div class="quick-chips">${g.items.map((it) =>
              `<button type="button" data-quick="${esc(it.msg)}" data-label="${esc(it.label)}" ${it.fresh ? "data-fresh" : ""} ${it.region ? `data-region="${it.region}"` : ""}>${esc(it.label)}</button>`).join("")}
            </div></div>`).join("")}</div>`;
      }
    }
    const meta = r.cached ? `<div class="meta">⚡ ${esc(t("cached"))}</div>` : "";
    return `<div class="msg ai"><div class="who">${esc(t("ai"))}</div>${inner}${meta}</div>`;
  }

  function renderThread() {
    const chatting = state.messages.length > 0;
    body.classList.toggle("chatting", chatting);
    $("#new-trip").hidden = !chatting;
    const chatNewTrip = $("#chat-new-trip");
    if (chatNewTrip) chatNewTrip.hidden = !chatting;
    input.placeholder = t("placeholder");
    if (chatInput) chatInput.placeholder = t("placeholder_chat");
    $("#thread").innerHTML = state.messages.map((m, i) => renderMessage(m, i === state.messages.length - 1)).join("");
  }
  const scrollToEnd = () => { const c = $("#conversation"); if (c) c.scrollTop = c.scrollHeight; };

  let stepTimer;
  function showThinking() {
    const el = document.createElement("div");
    el.className = "msg ai";
    el.id = "thinking";
    el.innerHTML = `<div class="who">${esc(t("ai"))}</div><div class="thinking-row"><span class="dots"><i></i><i></i><i></i></span><span class="step"></span></div>`;
    $("#thread").append(el);
    let i = 0;
    const step = () => {
      const s = $(".step", el);
      s.textContent = t("thinking")[Math.min(i++, 3)];
      s.style.animation = "none"; void s.offsetWidth; s.style.animation = "";
    };
    step();
    stepTimer = setInterval(step, 1100);
    globe.busy(true);
    scrollToEnd();
  }
  function hideThinking() { clearInterval(stepTimer); $("#thinking")?.remove(); globe.busy(false); }

  async function send(display, { message = display, fresh = false } = {}) {
    display = display.trim();
    if (!display || state.busy) return;
    if (fresh) state.pending = null;
    const full = state.pending ? `${state.pending}. ${message}` : message;
    state.busy = true;
    sendBtn.disabled = true;
    if (chatSend) chatSend.disabled = true;
    if (state.messages.at(-1)?.role === "error") state.messages.pop();
    else state.messages.push({ role: "user", text: display });
    state.lastSent = { display, message, full };
    renderThread();
    showThinking();
    try {
      const res = await fetch("/api/v1/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: full }) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "error");
      state.messages.push({ role: "ai", text: data.reply, result: data });
      state.pending = data.status === "needs_clarification" ? full : null;
      if (data.status === "planned") {
        state.plan = data;
        state.dayIdx = 0;
        state.expanded.clear();
        if (data.intent?.visitor_type) { state.visitor = data.intent.visitor_type; store.set("visitor", state.visitor); }
      }
      if (data.intent?.region) globe.focus(data.intent.region);
      banner(null);
    } catch (err) {
      state.messages.push({ role: "error", text: String(err.message || err) });
      if (/fetch|network/i.test(String(err))) banner("api_down");
    } finally {
      hideThinking();
      state.busy = false;
      sendBtn.disabled = false;
      if (chatSend) chatSend.disabled = false;
      save();
      renderThread();
      renderSheet();
      scrollToEnd();
      if (state.messages.at(-1)?.result?.status === "planned" && innerWidth > 900) setTimeout(() => openSheet(true), 450);
      setTimeout(() => globe.release(), 4000);
    }
  }

  // ---------- Trip sheet ----------
  function routeMap(day) {
    const pts = day.stops.filter((s) => s.lat != null);
    if (!pts.length) return "";
    const W = 480, H = 230, P = 34;
    const lats = pts.map((s) => s.lat), lons = pts.map((s) => s.lon);
    const span = Math.max(Math.max(...lats) - Math.min(...lats), Math.max(...lons) - Math.min(...lons), 0.02);
    const cLat = (Math.max(...lats) + Math.min(...lats)) / 2, cLon = (Math.max(...lons) + Math.min(...lons)) / 2;
    const k = Math.min(W - 2 * P, H - 2 * P) / span;
    const xy = (lat, lon) => [W / 2 + (lon - cLon) * k, H / 2 - (lat - cLat) * k];
    const NILE = { "Greater Cairo": 31.23, "Luxor": 32.63, "Aswan": 32.89 };
    let nile = "";
    if (NILE[day.area] != null) {
      const x = xy(cLat, NILE[day.area])[0];
      if (x > -30 && x < W + 30) nile = `<path d="M${x} -10 C${x - 30} ${H * .35} ${x + 30} ${H * .65} ${x} ${H + 10}" stroke="var(--azure)" stroke-width="20" fill="none"/>`;
    }
    const c = pts.map((s) => xy(s.lat, s.lon));
    const d = c.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(t("route_note"))}">
      <path d="M0 ${H * .3}H${W}M0 ${H * .72}H${W}M${W * .22} 0V${H}M${W * .6} 0V${H}" stroke="#fff" stroke-width="6"/>
      ${nile}
      <path d="${d}" fill="none" stroke="var(--ink)" stroke-width="3" stroke-dasharray="2 8" stroke-linecap="round"/>
      ${c.map(([x, y], i) => `<circle cx="${x}" cy="${y}" r="15" fill="var(--azure)" stroke="var(--ink)" stroke-width="2.5"/>
        <text x="${x}" y="${y + 5}" text-anchor="middle" font-family="Changa One" font-size="15" fill="#fff">${num(i + 1)}</text>`).join("")}
    </svg><div class="note">${esc(t("route_note"))}</div>`;
  }

  function renderSheet() {
    const sb = $("#sheet-body"), foot = $("#sheet-foot");
    const top = `<div class="sheet-top"><span class="eyebrow">${esc(t("nav_trip"))}</span><button type="button" class="close" data-close-sheet aria-label="${esc(t("close"))}">×</button></div>`;
    if (!state.plan) {
      sb.innerHTML = `${top}<div class="sheet-empty"><div class="orb"></div><h3>${esc(t("no_plan_title"))}</h3><p>${esc(t("no_plan_body"))}</p>
        <button type="button" class="btn" data-close-sheet data-focus>${esc(t("start"))} ${arrow}</button></div>`;
      foot.hidden = true;
      return;
    }
    foot.hidden = false;
    const plan = state.plan, days = plan.itinerary.days;
    state.dayIdx = Math.min(state.dayIdx, days.length - 1);
    const day = days[state.dayIdx];
    const intent = plan.intent || {};
    const dayTot = totals(day.stops);
    const trip = totals(days.flatMap((d) => d.stops));

    const stops = day.stops.map((s, i) => {
      const key = `${state.dayIdx}-${i}`, open = state.expanded.has(key);
      const leg = i > 0 && s.travel_from_previous_min
        ? `<li class="leg" style="--i:${i}">${esc(t("travel", { m: num(s.travel_from_previous_min) }))}${s.wait_min ? ` · ${esc(t("wait", { m: num(s.wait_min) }))}` : ""}</li>` : "";
      const notes = [s.hours_note, s.place_note].filter(Boolean).map((n) => `<p>ⓘ ${esc(n)}</p>`).join("");
      return `${leg}<li class="stop" style="--i:${i}" aria-expanded="${open}">
        <button type="button" class="stop-btn" data-stop="${key}" aria-expanded="${open}">
          <span class="stop-time">${s.start}</span><span class="stop-num">${num(i + 1)}</span>
          <span><span class="stop-name">${esc(place(s))}</span>
            <span class="stop-meta" style="display:block">${esc(category(s.category))} · ${duration(s.duration_min)} · ${esc(money(price(s)))}</span>
            <span class="badge ${s.hours_confidence === "listed" ? "ok" : "check"}">${esc(t(s.hours_confidence === "listed" ? "hours_ok" : "hours_check"))}</span></span>
          <svg class="chev" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></svg>
        </button>
        <div class="stop-more"><div><p>${esc(s.description)}</p>${notes}
          <p class="src"><a href="${esc(s.source_url)}" target="_blank" rel="noopener">${esc(t("source"))} ↗</a> · ${esc(t("verified", { d: s.last_verified }))} · ${s.start}–${s.end}</p></div></div>
      </li>`;
    }).join("");

    const tips = [...day.warnings, ...day.notes, ...plan.itinerary.warnings,
      ...plan.itinerary.unscheduled.map((u) => `${t("not_included")}: ${Fosha.isAr() ? AR_NAMES.places[u.attraction_id] || u.name : u.name} — ${u.reason}`)];

    const recs = plan.itinerary.recommendations || {};
    const hotels = recs.hotels || [];
    const transport = recs.transport || [];
    const recsHtml = (hotels.length || transport.length) ? `
      <div class="recs-card">
        <div class="recs-badge">${esc(t("recs_badge"))}</div>
        ${hotels.length ? `
          <div class="recs-group">
            <h4>🏨 ${esc(t("recs_hotels"))}</h4>
            <ul>${hotels.map((h) => `<li><strong>${esc(h.area)}:</strong> ${esc(h.desc)}</li>`).join("")}</ul>
          </div>` : ""}
        ${transport.length ? `
          <div class="recs-group">
            <h4>🚗 ${esc(t("recs_transport"))}</h4>
            <ul>${transport.map((tr) => `<li><strong>${esc(tr.mode)}:</strong> ${esc(tr.desc)}</li>`).join("")}</ul>
          </div>` : ""}
      </div>` : "";

    sb.innerHTML = `${top}
      <h2 class="trip-title">${esc(planTitle(plan))}</h2>
      <div class="trip-meta">
        ${(intent.interests || []).map((x) => `<span>#${esc(x)}</span>`).join("")}
        <span class="visitor-toggle"><span>${esc(t("prices_for"))}</span>
          <button type="button" class="text-btn" data-visitor="foreigner" aria-pressed="${state.visitor === "foreigner"}">${esc(t("foreigner"))}</button>
          <button type="button" class="text-btn" data-visitor="egyptian" aria-pressed="${state.visitor === "egyptian"}">${esc(t("egyptian"))}</button></span>
      </div>
      <div class="day-tabs" role="tablist">${days.map((d, i) => `<button type="button" role="tab" class="text-btn" data-day="${i}" aria-selected="${i === state.dayIdx}">${esc(t("day"))} ${num(d.day)}</button>`).join("")}</div>
      <div class="day-head"><h3>${esc(region(day.area))}${day.weekday ? ` · ${esc(weekday(day.weekday))}` : ""}</h3>
        <span>${duration(dayTot.min)} ${esc(t("on_site"))} · ${esc(money(dayTot.egp))}</span></div>
      <div class="route">${routeMap(day)}</div>
      <ol class="stops">${stops}</ol>
      ${recsHtml}
      ${tips.length ? `<div class="know"><h4>${esc(t("good_to_know"))}</h4><ul>${tips.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>` : ""}`;
    foot.innerHTML = `<span><strong>${esc(t("trip_total"))}</strong> · ${duration(trip.min)} ${esc(t("on_site"))} · ${esc(money(trip.egp))}</span>
      <button type="button" class="btn" data-print>${esc(t("print"))}</button>`;
  }

  function openSheet(open) {
    body.classList.toggle("sheet-open", open);
    $("#sheet").setAttribute("aria-hidden", String(!open));
    $("#nav-plan").toggleAttribute("aria-current", !open);
    $("#nav-trip").toggleAttribute("aria-current", open);
    if (!open) { $("#nav-plan").setAttribute("aria-current", "page"); $("#nav-trip").removeAttribute("aria-current"); }
    else { $("#nav-trip").setAttribute("aria-current", "page"); $("#nav-plan").removeAttribute("aria-current"); }
  }

  // ---------- Banner ----------
  function banner(key) {
    const b = $("#banner");
    b.hidden = !key;
    if (key) b.textContent = t(key);
  }

  // ---------- Language ----------
  function applyLang(lang) {
    Fosha.setLang(lang);
    $("#chips").innerHTML = t("chips").map((c) => `<button type="button" class="chip" data-quick="${esc(c.msg)}" data-label="${esc(c.msg)}" data-region="${c.region}" data-fresh>${esc(c.label)}</button>`).join("");
    paintGlobeText();
    renderThread();
    renderSheet();
  }

  // ---------- Events ----------
  document.addEventListener("click", (e) => {
    const el = e.target.closest("button, a");
    if (!el) {
      if (e.target.id === "chat-backdrop") openChat(false);
      return;
    }
    if (el.dataset.lang) applyLang(el.dataset.lang);
    else if (el.dataset.quick) {
      openChat(true);
      send(el.dataset.label, { message: el.dataset.quick, fresh: el.hasAttribute("data-fresh") });
    }
    else if (el.id === "chat-close" || el.hasAttribute("data-close-chat")) {
      openChat(false);
    }
    else if (el.hasAttribute("data-open-sheet") || el.id === "nav-trip") {
      renderSheet(); openSheet(true);
    }
    else if (el.hasAttribute("data-close-sheet")) {
      openSheet(false);
    }
    else if (el.id === "nav-plan") {
      openChat(true);
    }
    else if (el.dataset.day) {
      state.dayIdx = +el.dataset.day; renderSheet(); $("#sheet-body").scrollTop = 0;
    }
    else if (el.dataset.stop) {
      const k = el.dataset.stop;
      state.expanded.has(k) ? state.expanded.delete(k) : state.expanded.add(k);
      const li = el.closest(".stop"), open = state.expanded.has(k);
      li.setAttribute("aria-expanded", open); el.setAttribute("aria-expanded", open);
    }
    else if (el.dataset.visitor) {
      state.visitor = el.dataset.visitor; store.set("visitor", state.visitor); renderSheet();
    }
    else if (el.hasAttribute("data-retry") && state.lastSent) {
      send(state.lastSent.display, { message: state.lastSent.message });
    }
    else if (el.hasAttribute("data-print")) window.print();
    else if (el.id === "new-trip" || el.id === "chat-new-trip") {
      state.messages = []; state.pending = null;
      save(); openSheet(false); renderThread(); globe.release();
      if (chatInput) chatInput.value = "";
      input.value = "";
      openChat(false); input.focus();
    }
  });

  document.addEventListener("mouseover", (e) => {
    const chip = e.target.closest("[data-region]");
    if (chip && !state.busy) globe.focus(chip.dataset.region);
  });
  document.addEventListener("mouseout", (e) => {
    if (e.target.closest("[data-region]") && !e.relatedTarget?.closest?.("[data-region]")) globe.release();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (body.classList.contains("sheet-open")) openSheet(false);
      else if (chatModal && !chatModal.hidden) openChat(false);
    }
  });

  // Typing into landing input opens the separate chatbot view immediately
  input.addEventListener("focus", () => {
    if (input.value.trim()) {
      const v = input.value;
      input.value = "";
      openChat(true);
      if (chatInput) {
        chatInput.value = v;
        chatInput.focus();
        chatInput.setSelectionRange(v.length, v.length);
      }
    }
  });
  input.addEventListener("input", () => {
    const v = input.value;
    input.value = "";
    openChat(true);
    if (chatInput) {
      chatInput.value = v;
      chatInput.focus();
      chatInput.setSelectionRange(v.length, v.length);
    }
  });

  $("#composer").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    input.value = "";
    openChat(true);
    if (text) send(text);
  });

  if (chatComposer) {
    chatComposer.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = chatInput.value.trim();
      chatInput.value = "";
      if (text) send(text);
    });
  }
  addEventListener("offline", () => banner("offline"));
  addEventListener("online", () => banner(null));

  fetch("/api/v1/health").then((r) => r.json()).then((h) => { $("#demo-badge").hidden = !h.demo; }).catch(() => banner("api_down"));
  if (!navigator.onLine) banner("offline");

  applyLang(Fosha.lang);
  openSheet(false);
  if (state.messages.length) requestAnimationFrame(scrollToEnd);
})();
