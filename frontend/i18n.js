// UI strings for the traveller app (index.html) and the insights dashboard (dashboard.html),
// plus Arabic names for the data the backend returns (regions, categories, places).
window.I18N = {
  en: {
    brand: "Fosha", brand_alt: "- فسحه",
    tagline: "Your Egypt, your way",
    orbit: "YOUR EGYPT, YOUR WAY",
    nav_plan: "Plan", nav_trip: "My trip", new_trip: "New trip",
    hero_1: "Where to", hero_2: "next?",
    hero_sub: "Tell me where you're going, for how long and what you love. I'll plan your fosha day by day.",
    placeholder: "e.g. 3 days in Cairo, I love history and museums",
    placeholder_chat: "Reply or ask for another trip…",
    send: "Send",
    chips: [
      { label: "3 days in Cairo", msg: "I have 3 days in Cairo and I love history and museums", region: "Cairo" },
      { label: "Temples of Luxor", msg: "2 days in Luxor, I love temples, I'm a tourist", region: "Luxor" },
      { label: "Aswan & the Nile", msg: "3 days in Aswan, temples and the Nile", region: "Aswan" },
      { label: "Weekend in Alex", msg: "A weekend in Alexandria starting Friday", region: "Alexandria" },
    ],
    globe_hint: "Tap a landmark to start there",
    globe_prefill: "3 days in {region}",
    ai: "Fosha", you: "You",
    thinking: ["Searching attractions…", "Checking opening hours…", "Mapping the route…", "Writing your plan…"],
    how_many_days: "How many days?", which_region: "Where to?",
    day_options: [["1 day", "1 day"], ["2 days", "2 days"], ["3 days", "3 days"], ["5 days", "5 days"]],
    try_instead: "Try one of these",
    error_title: "That didn't work",
    error_body: "I couldn't finish your request. Your current plan is unchanged.",
    retry: "Try again",
    api_down: "The assistant isn't responding right now. Your saved plan is safe.",
    offline: "You're offline. You can still open your saved plan.",
    demo_badge: "Demo mode",
    disclaimer: "Plans are suggestions. Confirm tickets and hours with official venues.",
    cached: "instant · from cache",
    full_reply: "Read the full write-up",
    open_plan: "Open day-by-day plan",
    plan_ready: "Your plan is ready",
    days_in: "{n} days in {place}", one_day_in: "A day in {place}",
    day: "Day", days_unit: "days", stops_unit: "stops",
    close: "Close",
    prices_for: "Prices for",
    foreigner: "Visitors", egyptian: "Egyptians",
    on_site: "on site",
    travel: "{m} min by car", wait: "+{m} min until it opens",
    hours_ok: "Hours listed", hours_check: "Check hours",
    free: "Free / not recorded", egp: "EGP",
    good_to_know: "Good to know",
    not_included: "Not included",
    source: "Official page", verified: "verified {d}",
    route_note: "Schematic route · not to scale",
    print: "Print plan",
    trip_total: "Whole trip",
    no_plan_title: "No trip yet",
    no_plan_body: "Ask for a trip and your day-by-day plan will appear here.",
    start: "Plan a trip",
    hrs: "h", mins: "m",
    // dashboard
    dash_title: "Insights",
    dash_sub: "What travellers ask Fosha, and how fast it answers.",
    r7: "7 days", r30: "30 days", rall: "All time", refresh: "Refresh",
    dash_orbit: "QUERIES • LAST {n} DAYS • ",
    dash_orbit_all: "QUERIES • ALL TIME • ",
    k_queries: "queries", k_cache: "Cache hit rate", k_resp: "Avg. response", k_lang: "Arabic share",
    k_planned: "{n} itineraries planned",
    vs_prev: "vs previous period", no_prev: "no previous period",
    destinations: "Most requested destinations", destinations_sub: "Where travellers asked to go",
    lang_dist: "Language distribution", lang_dist_sub: "Share of queries",
    regions: "Most popular regions", regions_sub: "Regions of the places planned",
    attractions: "Popular attractions", attractions_sub: "Most often placed in an itinerary",
    t_name: "Attraction", t_region: "Region", t_category: "Category", t_count: "Plans",
    english: "English", arabic: "Arabic",
    no_data_title: "No questions yet",
    no_data_body: "Numbers appear once travellers start chatting. For a demo, run: uv run python -m api.seed",
    open_app: "Open Fosha",
    load_error: "Couldn't load analytics.",
  },
  ar: {
    brand: "فسحه", brand_alt: "- Fosha",
    tagline: "مصر على مزاجك",
    orbit: "مصر على مزاجك",
    nav_plan: "خطّط", nav_trip: "رحلتي", new_trip: "رحلة جديدة",
    hero_1: "رايح", hero_2: "فين؟",
    hero_sub: "قولّي رايح فين، قد إيه، وبتحب إيه. وأنا أرتّب لك فسحتك يوم بيوم.",
    placeholder: "مثلًا: ٣ أيام في القاهرة وبحب التاريخ والمتاحف",
    placeholder_chat: "رُد أو اطلب رحلة تانية…",
    send: "إرسال",
    chips: [
      { label: "٣ أيام في القاهرة", msg: "ثلاثة أيام في القاهرة وأحب التاريخ والمتاحف", region: "Cairo" },
      { label: "معابد الأقصر", msg: "يومين في الأقصر وأحب المعابد", region: "Luxor" },
      { label: "أسوان والنيل", msg: "ثلاثة أيام في أسوان، معابد والنيل", region: "Aswan" },
      { label: "ويك إند في إسكندرية", msg: "عطلة نهاية الأسبوع في الإسكندرية تبدأ الجمعة", region: "Alexandria" },
    ],
    globe_hint: "دوس على أي معلم وابدأ منه",
    globe_prefill: "٣ أيام في {region}",
    ai: "فسحه", you: "أنت",
    thinking: ["بندوّر على الأماكن…", "بنراجع مواعيد الفتح…", "بنرسم المسار…", "بنكتب برنامجك…"],
    how_many_days: "كام يوم؟", which_region: "رايح فين؟",
    day_options: [["يوم واحد", "يوم واحد"], ["يومين", "يومين"], ["٣ أيام", "3 أيام"], ["٥ أيام", "5 أيام"]],
    try_instead: "جرّب واحدة من دول",
    error_title: "حصلت مشكلة",
    error_body: "معرفتش أكمّل طلبك. برنامجك الحالي زي ما هو.",
    retry: "حاول تاني",
    api_down: "المساعد مش بيرد دلوقتي. برنامجك المحفوظ في أمان.",
    offline: "أنت مش متصل. تقدر تفتح برنامجك المحفوظ.",
    demo_badge: "وضع تجريبي",
    disclaimer: "البرامج اقتراحات. اتأكد من التذاكر والمواعيد من الجهات الرسمية.",
    cached: "فوري · من الذاكرة",
    full_reply: "اقرا الرد كامل",
    open_plan: "افتح البرنامج يوم بيوم",
    plan_ready: "برنامجك جاهز",
    days_in: "{n} أيام في {place}", one_day_in: "يوم في {place}",
    day: "اليوم", days_unit: "أيام", stops_unit: "محطات",
    close: "إغلاق",
    prices_for: "الأسعار لـ",
    foreigner: "الزوار", egyptian: "المصريين",
    on_site: "في الأماكن",
    travel: "{m} دقيقة بالعربية", wait: "+{m} دقيقة لحد ما يفتح",
    hours_ok: "المواعيد معلنة", hours_check: "راجع المواعيد",
    free: "مجاني / غير مسجل", egp: "جنيه",
    good_to_know: "معلومة تهمّك",
    not_included: "مش ضمن البرنامج",
    source: "الصفحة الرسمية", verified: "آخر تحقق {d}",
    route_note: "مسار توضيحي · مش بمقياس رسم",
    print: "اطبع البرنامج",
    trip_total: "الرحلة كلها",
    no_plan_title: "لسه مفيش رحلة",
    no_plan_body: "اطلب رحلة وبرنامجك يوم بيوم هيظهر هنا.",
    start: "خطّط رحلة",
    hrs: "س", mins: "د",
    dash_title: "المؤشرات",
    dash_sub: "المسافرين بيسألوا فسحه عن إيه، وبترد بسرعة قد إيه.",
    r7: "٧ أيام", r30: "٣٠ يوم", rall: "كل الفترات", refresh: "تحديث",
    dash_orbit: "سؤال • آخر {n} يوم • ",
    dash_orbit_all: "سؤال • كل الفترات • ",
    k_queries: "سؤال", k_cache: "الإجابة من الذاكرة", k_resp: "متوسط زمن الرد", k_lang: "نسبة العربي",
    k_planned: "{n} برنامج اتعمل",
    vs_prev: "مقارنة بالفترة اللي فاتت", no_prev: "مفيش فترة سابقة",
    destinations: "أكثر الوجهات طلبًا", destinations_sub: "الأماكن اللي المسافرين سألوا عنها",
    lang_dist: "توزيع اللغات", lang_dist_sub: "نسبة الأسئلة",
    regions: "أكثر المناطق شعبية", regions_sub: "مناطق الأماكن اللي اتخططت",
    attractions: "أشهر المعالم", attractions_sub: "الأكثر ظهورًا في البرامج",
    t_name: "المعلم", t_region: "المنطقة", t_category: "النوع", t_count: "برامج",
    english: "الإنجليزية", arabic: "العربية",
    no_data_title: "لسه مفيش أسئلة",
    no_data_body: "الأرقام بتظهر لما المسافرين يبدأوا يسألوا. للعرض التجريبي شغّل: uv run python -m api.seed",
    open_app: "افتح فسحه",
    load_error: "معرفتش أحمّل الإحصائيات.",
  },
};

window.AR_NAMES = {
  regions: {
    "Cairo": "القاهرة", "Giza": "الجيزة", "Greater Cairo": "القاهرة الكبرى", "Luxor": "الأقصر",
    "Aswan": "أسوان", "Alexandria": "الإسكندرية", "South Sinai": "جنوب سيناء", "Red Sea": "البحر الأحمر",
    "Matrouh": "مطروح", "New Valley": "الوادي الجديد", "Dahab": "دهب",
  },
  categories: {
    "Museum": "متحف", "Archaeological Site": "موقع أثري", "Temple": "معبد", "Fortress": "قلعة",
    "Cultural Center": "مركز ثقافي", "National Park": "محمية طبيعية", "Monastery": "دير",
    "Aquarium": "أحواض مائية", "Island / Beach": "جزيرة / شاطئ", "Historic Oasis": "واحة تاريخية",
  },
  places: {
    1: "المتحف المصري", 2: "المتحف القومي للحضارة المصرية", 3: "المتحف القبطي", 4: "متحف الفن الإسلامي",
    5: "أهرامات الجيزة / الهرم الأكبر", 6: "سقارة", 7: "دهشور", 8: "السرابيوم بسقارة", 9: "معبد الكرنك",
    10: "معبد الأقصر", 11: "وادي الملوك", 12: "معبد حتشبسوت", 13: "متحف التحنيط", 14: "الدير البحري",
    15: "متحف النوبة", 16: "معبد فيلة", 17: "أبو سمبل", 18: "معبد كوم أمبو", 19: "معبد إدفو",
    20: "متحف التمساح", 21: "قلعة قايتباي", 22: "مكتبة الإسكندرية", 23: "مقابر كوم الشقافة",
    24: "محمية رأس محمد", 25: "دير سانت كاترين", 26: "أكواريوم الغردقة الكبير", 27: "جزيرة الجفتون (محمية)",
    28: "قلعة شالي وواحة سيوة", 29: "معبد الوحي (معبد آمون)", 30: "محمية الصحراء البيضاء",
  },
  weekdays: { mon: "الاثنين", tue: "الثلاثاء", wed: "الأربعاء", thu: "الخميس", fri: "الجمعة", sat: "السبت", sun: "الأحد" },
};

// Shared helpers for both pages.
window.Fosha = (() => {
  const store = {
    get(key, fallback) { try { const v = localStorage.getItem("fosha." + key); return v ? JSON.parse(v) : fallback; } catch { return fallback; } },
    set(key, value) { try { localStorage.setItem("fosha." + key, JSON.stringify(value)); } catch { /* storage blocked */ } },
  };
  let lang = store.get("lang", (navigator.language || "en").startsWith("ar") ? "ar" : "en");
  const t = (key, vars = {}) => {
    const s = I18N[lang][key] ?? I18N.en[key] ?? key;
    return typeof s === "string" ? s.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "") : s;
  };
  const isAr = () => lang === "ar";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (n, opts) => new Intl.NumberFormat(isAr() ? "ar-EG" : "en-US", opts).format(n);
  const region = (r) => (isAr() && AR_NAMES.regions[r]) || r;
  const category = (c) => (isAr() && AR_NAMES.categories[c]) || c;
  const place = (p) => (isAr() && AR_NAMES.places[p.attraction_id ?? p.id]) || p.name;
  const weekday = (w) => (w ? (isAr() ? AR_NAMES.weekdays[w] : w[0].toUpperCase() + w.slice(1)) : "");
  const duration = (min) => {
    const h = Math.floor(min / 60), m = min % 60;
    return `${h ? num(h) + t("hrs") : ""}${h && m ? " " : ""}${m ? num(m) + t("mins") : ""}`;
  };
  function setLang(next) {
    lang = next;
    store.set("lang", lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = isAr() ? "rtl" : "ltr";
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
    document.querySelectorAll("[data-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  }
  return { store, t, isAr, esc, num, region, category, place, weekday, duration, setLang, get lang() { return lang; } };
})();
