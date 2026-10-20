import React, { useState } from 'react';
import { Language, ChatResponse, Stop, HotelRecommendation, TransportRecommendation } from '../types';
import { translate, AR_NAMES, formatNumber } from '../i18n';

interface TripSheetProps {
  isOpen: boolean;
  onClose: () => void;
  lang: Language;
  plan: ChatResponse | null;
  onOpenChat: () => void;
}

export const TripSheet: React.FC<TripSheetProps> = ({
  isOpen,
  onClose,
  lang,
  plan,
  onOpenChat,
}) => {
  const [selectedDayIdx, setSelectedDayIdx] = useState(0);
  const [visitorType, setVisitorType] = useState<'foreigner' | 'egyptian'>('foreigner');
  const [expandedStops, setExpandedStops] = useState<Record<string, boolean>>({});

  const isAr = lang === 'ar';
  const itinerary = plan?.itinerary;

  if (!itinerary || !itinerary.days?.length) {
    return (
      <aside className="sheet" aria-label="Trip" aria-hidden={!isOpen}>
        <div className="sheet-scroll">
          <div className="sheet-top">
            <span className="eyebrow">{translate('nav_trip', lang)}</span>
            <button type="button" className="close" onClick={onClose} aria-label={translate('close', lang)}>
              ×
            </button>
          </div>
          <div style={{ textAlign: 'center', padding: '60px 20px' }}>
            <h3 style={{ font: "400 32px/1 var(--font-display)", margin: "0 0 12px" }}>
              {translate('no_plan_title', lang)}
            </h3>
            <p style={{ color: "var(--ink-soft)", fontSize: "15px" }}>
              {translate('no_plan_body', lang)}
            </p>
          </div>
        </div>
      </aside>
    );
  }

  const days = itinerary.days;
  const currentDay = days[Math.min(selectedDayIdx, days.length - 1)];

  const toggleStop = (key: string) => {
    setExpandedStops((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // null means the source lists no price: show that, and leave it out of totals
  const getStopPrice = (s: Stop): number | null => {
    const raw = visitorType === 'egyptian' ? s.price_egyptian_egp : s.price_foreigner_egp;
    if (raw === null) return null;
    return raw || s.ticket_price_egp || 0;
  };

  const dayTotalMinutes = currentDay.stops.reduce((acc, s) => acc + (s.duration_min || 0), 0);
  const dayTotalEgp = currentDay.stops.reduce((acc, s) => acc + (getStopPrice(s) ?? 0), 0);

  const formatHoursMins = (min: number) => {
    const h = Math.floor(min / 60);
    const m = min % 60;
    return `${h ? `${formatNumber(h, lang)} ${translate('hrs', lang)} ` : ''}${m ? `${formatNumber(m, lang)} ${translate('mins', lang)}` : ''}`.trim() || `0 ${translate('mins', lang)}`;
  };

  const recs = itinerary.recommendations;
  const hotels: HotelRecommendation[] = recs?.hotels || [];
  const transport: TransportRecommendation[] = recs?.transport || [];

  return (
    <aside className="sheet" aria-label="Trip" aria-hidden={!isOpen}>
      <div className="sheet-scroll">
        <div className="sheet-top">
          <span className="eyebrow">{translate('nav_trip', lang)}</span>
          <button type="button" className="close" onClick={onClose} aria-label={translate('close', lang)}>
            ×
          </button>
        </div>

        <h2 className="trip-title">
          {days.length === 1
            ? translate('one_day_in', lang, { place: isAr ? AR_NAMES.regions[days[0].area] || days[0].area_ar || days[0].area : days[0].area })
            : translate('days_in', lang, {
                n: formatNumber(days.length, lang),
                place: isAr ? AR_NAMES.regions[days[0].area] || days[0].area_ar || days[0].area : days[0].area,
              })}
        </h2>

        <div className="trip-meta">
          <span>{translate('prices_for', lang)}:</span>
          <div className="visitor-toggle">
            <button
              type="button"
              className="text-btn"
              aria-pressed={visitorType === 'foreigner'}
              onClick={() => setVisitorType('foreigner')}
            >
              {translate('foreigner', lang)}
            </button>
            <span className="sep" aria-hidden="true" style={{ margin: "0 4px" }} />
            <button
              type="button"
              className="text-btn"
              aria-pressed={visitorType === 'egyptian'}
              onClick={() => setVisitorType('egyptian')}
            >
              {translate('egyptian', lang)}
            </button>
          </div>
        </div>

        <div className="day-tabs">
          {days.map((d, i) => (
            <button
              key={i}
              type="button"
              className="text-btn"
              aria-selected={selectedDayIdx === i}
              onClick={() => setSelectedDayIdx(i)}
            >
              {translate('day', lang)} {formatNumber(d.day, lang)}
            </button>
          ))}
        </div>

        <div className="day-head">
          <h3>
            {isAr ? AR_NAMES.regions[currentDay.area] || currentDay.area_ar || currentDay.area : currentDay.area}
            {currentDay.weekday ? ` · ${isAr ? AR_NAMES.weekdays[currentDay.weekday.toLowerCase()] || currentDay.weekday : currentDay.weekday}` : ''}
          </h3>
          <span>
            {formatHoursMins(dayTotalMinutes)} · {formatNumber(dayTotalEgp, lang)} {translate('egp', lang)}
          </span>
        </div>

        <ul className="stops">
          {currentDay.stops.map((stop, i) => {
            const key = `${selectedDayIdx}-${i}`;
            const isExpanded = expandedStops[key];
            const price = getStopPrice(stop);
            const stopName = isAr ? AR_NAMES.places[stop.attraction_id] || stop.name_ar || stop.name : stop.name;

            return (
              <li key={i} className="stop-card">
                <div className="stop-header" onClick={() => toggleStop(key)} role="button" tabIndex={0}>
                  <div>
                    <div className="stop-name">{stopName}</div>
                    <div className="stop-timing">
                      {stop.start && stop.end ? `${stop.start} - ${stop.end} · ` : ''}
                      {formatNumber(stop.duration_min, lang)} {translate('mins', lang)}
                    </div>
                  </div>
                  <div className="stop-price">
                    {price === null
                      ? translate('no_price', lang)
                      : price > 0 ? `${formatNumber(price, lang)} ${translate('egp', lang)}` : translate('free', lang)}
                  </div>
                </div>

                {isExpanded && (
                  <div className="stop-details">
                    {stop.description && <p style={{ margin: "0 0 8px" }}>{stop.description}</p>}
                    {stop.hours_note && (
                      <div style={{ color: "var(--ink-soft)", fontSize: "13px" }}>
                        🕒 {stop.hours_note}
                      </div>
                    )}
                    {stop.place_note && (
                      <div style={{ color: "var(--ink-soft)", fontSize: "13px" }}>📍 {stop.place_note}</div>
                    )}
                    {stop.source_url && (
                      <a className="stop-source" href={stop.source_url} target="_blank" rel="noopener noreferrer">
                        {translate(stop.from_web ? 'source_web' : 'source', lang)} ↗
                      </a>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>

        {/* Multi-Day Trip Accommodation & Transport Guide Card */}
        {(hotels.length > 0 || transport.length > 0) && (
          <div className="multi-day-card">
            <span className="multi-day-badge">
              {isAr ? 'مختارة لرحلتك' : 'Picked for your trip'}
            </span>
            {(recs?.based_on?.length ?? 0) > 0 && (
              <p className="rec-basis">
                {isAr ? 'على أساس: ' : 'Based on: '}
                {recs!.based_on!.join(' · ')}
              </p>
            )}

            {hotels.length > 0 && (
              <div className="multi-day-section">
                <h4>🏨 {isAr ? 'خيارات الإقامة المقترحة' : 'Suggested Hotel Bases'}</h4>
                <ul>
                  {hotels.map((h, i) => (
                    <li key={i}>
                      <strong>{h.area}:</strong> {h.desc}
                      {h.example && (
                        <span className="rec-example"> {isAr ? 'مثل' : 'e.g.'} {h.example}</span>
                      )}
                      {h.why && h.why.length > 0 && (
                        <span className="rec-why">{h.why.map((w, j) => <span key={j}>✓ {w}</span>)}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {transport.length > 0 && (
              <div className="multi-day-section">
                <h4>🚆 {isAr ? 'خيارات التنقل المقترحة' : 'Suggested Transport Ways'}</h4>
                <ul>
                  {transport.map((t, i) => (
                    <li key={i}>
                      <strong>{t.mode}:</strong> {t.desc}
                      {t.why && t.why.length > 0 && (
                        <span className="rec-why">{t.why.map((w, j) => <span key={j}>✓ {w}</span>)}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="sheet-foot">
        <button type="button" className="sheet-chat-btn" onClick={onOpenChat}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          <span>{isAr ? 'محادثة وتعديل الخطة' : 'Chat & Tweak Trip'}</span>
        </button>
        <button type="button" className="text-btn" onClick={() => window.print()}>
          {translate('print', lang)}
        </button>
      </div>
    </aside>
  );
};
