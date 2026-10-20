import React from 'react';
import { ChatResponse, Language, Stop } from '../types';
import { AR_NAMES, formatNumber, localDigits, localRecs, localText, translate } from '../i18n';

/** The printable itinerary. Hidden on screen; when printing it is the only thing on
    the page (see `.print-doc` in index.css), so "Print" gives the whole trip, every
    day and stop, instead of a picture of the window. Only what is in the plan is
    printed (no "not included" list or planner notes), all in the chosen language. */
interface PrintItineraryProps {
  plan: ChatResponse | null;
  lang: Language;
}

export const PrintItinerary: React.FC<PrintItineraryProps> = ({ plan, lang }) => {
  const itinerary = plan?.itinerary;
  if (!itinerary?.days?.length) return null;
  const isAr = lang === 'ar';
  const num = (v: number) => formatNumber(v, lang);
  const area = (d: { area: string; area_ar?: string | null }) => (isAr ? AR_NAMES.regions[d.area] || d.area_ar || d.area : d.area);
  const name = (s: Stop) => (isAr ? AR_NAMES.places[s.attraction_id] || s.name_ar || s.name : s.name);
  const category = (c?: string) => (c ? (isAr ? AR_NAMES.categories[c] || c : c) : '');
  const weekday = (w?: string | null) => (w ? (isAr ? AR_NAMES.weekdays[w] || w : w[0].toUpperCase() + w.slice(1)) : '');
  const price = (v?: number | null) =>
    v === null || v === undefined ? translate('no_price', lang) : v === 0 ? translate('free', lang) : `${num(v)} ${translate('egp', lang)}`;
  const duration = (min: number) => {
    const h = Math.floor(min / 60), m = min % 60;
    return `${h ? `${num(h)} ${translate('hrs', lang)}` : ''}${h && m ? ' ' : ''}${m ? `${num(m)} ${translate('mins', lang)}` : ''}`;
  };
  const days = itinerary.days;
  const areas = Array.from(new Set(days.map(area))).join(isAr ? ' و' : ' & ');
  const title = days.length === 1
    ? translate('one_day_in', lang, { place: areas })
    : translate('days_in', lang, { n: num(days.length), place: areas });
  const recs = localRecs(itinerary, lang);
  const sources = Array.from(new Set(days.flatMap((d) => d.stops.map((s) => s.source_url)).filter(Boolean))) as string[];

  return (
    <article className="print-doc" dir={isAr ? 'rtl' : 'ltr'} aria-hidden="true">
      <header className="print-head">
        <div className="print-brand">{isAr ? 'فسحة' : 'Fosha'}</div>
        <h1>{title}</h1>
        <p className="print-meta">
          {new Date().toLocaleDateString(isAr ? 'ar-EG' : 'en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}
        </p>
      </header>

      {days.map((day) => (
        <section className="print-day" key={day.day}>
          <h2>
            {translate('day', lang)} {num(day.day)} · {area(day)}
            {day.weekday ? ` · ${weekday(day.weekday)}` : ''}
          </h2>
          <table>
            <thead>
              <tr>
                <th>{isAr ? 'الوقت' : 'Time'}</th>
                <th>{isAr ? 'المكان' : 'Place'}</th>
                <th>{isAr ? 'المدة' : 'Duration'}</th>
                <th>{translate('foreigner', lang)}</th>
                <th>{translate('egyptian', lang)}</th>
              </tr>
            </thead>
            <tbody>
              {day.stops.map((s, i) => (
                <React.Fragment key={s.attraction_id}>
                  {i > 0 && s.travel_from_previous_min ? (
                    <tr className="print-leg">
                      <td />
                      <td colSpan={4}>
                        ↓ {isAr ? `حوالي ${num(s.travel_from_previous_min)} دقيقة مواصلات` : `about ${num(s.travel_from_previous_min)} min by car`}
                      </td>
                    </tr>
                  ) : null}
                  <tr>
                    <td className="print-time">{localDigits(`${s.start}–${s.end}`, lang)}</td>
                    <td>
                      <strong>{name(s)}</strong>
                      {s.category ? <span className="print-cat"> · {category(s.category)}</span> : null}
                      {s.description ? <div className="print-desc">{localText(s, 'description', lang)}</div> : null}
                      {s.hours_note ? <div className="print-note">🕒 {localText(s, 'hours_note', lang)}</div> : null}
                      {s.place_note ? <div className="print-note">📍 {localText(s, 'place_note', lang)}</div> : null}
                    </td>
                    <td>{duration(s.duration_min)}</td>
                    <td>{price(s.price_foreigner_egp)}</td>
                    <td>{price(s.price_egyptian_egp)}</td>
                  </tr>
                </React.Fragment>
              ))}
            </tbody>
          </table>
          {day.warnings.length > 0 && (
            <ul className="print-warnings">
              {(lang === 'ar' && day.warnings_ar?.length ? day.warnings_ar : day.warnings).map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
        </section>
      ))}

      {recs && (recs.hotels.length > 0 || recs.transport.length > 0) && (
        <section className="print-recs">
          <h2>{isAr ? 'اختيارات لرحلتك' : 'Picked for your trip'}</h2>
          {recs.hotels.length > 0 && (
            <>
              <h3>{isAr ? 'أماكن الإقامة' : 'Where to stay'}</h3>
              <ul>
                {recs.hotels.map((h, i) => (
                  <li key={i}>
                    <strong>{h.area}</strong>: {h.desc}{h.example ? ` (${isAr ? 'مثل' : 'e.g.'} ${h.example})` : ''}
                    {h.why?.length ? <div className="print-why">✓ {h.why.join(' · ')}</div> : null}
                  </li>
                ))}
              </ul>
            </>
          )}
          {recs.transport.length > 0 && (
            <>
              <h3>{isAr ? 'المواصلات' : 'Getting around'}</h3>
              <ul>
                {recs.transport.map((t, i) => (
                  <li key={i}>
                    <strong>{t.mode}</strong>: {t.desc}
                    {t.why?.length ? <div className="print-why">✓ {t.why.join(' · ')}</div> : null}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      <footer className="print-foot">
        <p>{translate('disclaimer', lang)}</p>
        {sources.length > 0 && <p className="print-sources">{isAr ? 'المصادر: ' : 'Sources: '}{sources.join(' · ')}</p>}
      </footer>
    </article>
  );
};
