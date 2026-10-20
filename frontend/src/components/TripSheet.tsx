import React, { useState } from 'react';
import { Language, ChatResponse, Stop } from '../types';
import { translate, AR_NAMES, formatNumber } from '../i18n';

interface TripSheetProps {
  isOpen: boolean;
  onClose: () => void;
  lang: Language;
  plan: ChatResponse | null;
}

export const TripSheet: React.FC<TripSheetProps> = ({
  isOpen,
  onClose,
  lang,
  plan,
}) => {
  const [selectedDayIdx, setSelectedDayIdx] = useState(0);
  const [visitorType, setVisitorType] = useState<'foreigner' | 'egyptian'>('foreigner');
  const [expandedStops, setExpandedStops] = useState<Record<string, boolean>>({});

  if (!isOpen) return null;

  const isAr = lang === 'ar';
  const itinerary = plan?.itinerary;

  if (!itinerary || !itinerary.days?.length) {
    return (
      <div className="sheet-drawer" dir={isAr ? 'rtl' : 'ltr'}>
        <div className="sheet-head">
          <span style={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.1em' }}>
            {translate('nav_trip', lang)}
          </span>
          <button type="button" onClick={onClose} style={{ fontSize: '22px', fontWeight: 700 }}>
            ×
          </button>
        </div>
        <div className="sheet-body" style={{ textAlign: 'center', padding: '60px 20px' }}>
          <h3>{translate('no_plan_title', lang)}</h3>
          <p>{translate('no_plan_body', lang)}</p>
        </div>
      </div>
    );
  }

  const days = itinerary.days;
  const currentDay = days[Math.min(selectedDayIdx, days.length - 1)];

  const toggleStop = (key: string) => {
    setExpandedStops((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const getStopPrice = (s: Stop) => {
    const raw = visitorType === 'egyptian' ? s.price_egyptian_egp : s.price_foreigner_egp;
    return raw || s.ticket_price_egp || 0;
  };

  const dayTotalMinutes = currentDay.stops.reduce((acc, s) => acc + (s.duration_min || 0), 0);
  const dayTotalEgp = currentDay.stops.reduce((acc, s) => acc + getStopPrice(s), 0);

  const tripTotalMinutes = days.flatMap((d) => d.stops).reduce((acc, s) => acc + (s.duration_min || 0), 0);
  const tripTotalEgp = days.flatMap((d) => d.stops).reduce((acc, s) => acc + getStopPrice(s), 0);

  const formatHoursMins = (min: number) => {
    const h = Math.floor(min / 60);
    const m = min % 60;
    return `${h ? `${formatNumber(h, lang)} ${translate('hrs', lang)} ` : ''}${m ? `${formatNumber(m, lang)} ${translate('mins', lang)}` : ''}`.trim() || `0 ${translate('mins', lang)}`;
  };

  const recs = itinerary.recommendations;
  const hotels = recs?.hotels || [];
  const transport = recs?.transport || [];

  return (
    <div className="sheet-drawer" dir={isAr ? 'rtl' : 'ltr'}>
      <div className="sheet-head">
        <span style={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.1em', fontSize: '13px' }}>
          {translate('nav_trip', lang)}
        </span>
        <button
          type="button"
          onClick={onClose}
          style={{ fontSize: '24px', fontWeight: 700, padding: '0 8px' }}
          aria-label={translate('close', lang)}
        >
          ×
        </button>
      </div>

      <div className="sheet-body">
        <h2 className="sheet-title">
          {days.length === 1
            ? translate('one_day_in', lang, { place: isAr ? AR_NAMES.regions[days[0].area] || days[0].area : days[0].area })
            : translate('days_in', lang, {
                n: formatNumber(days.length, lang),
                place: isAr ? AR_NAMES.regions[days[0].area] || days[0].area : days[0].area,
              })}
        </h2>

        <div className="sheet-meta">
          <span>{translate('prices_for', lang)}:</span>
          <div className="visitor-toggle-group">
            <button
              type="button"
              className={`visitor-btn ${visitorType === 'foreigner' ? 'active' : ''}`}
              onClick={() => setVisitorType('foreigner')}
            >
              {translate('foreigner', lang)}
            </button>
            <button
              type="button"
              className={`visitor-btn ${visitorType === 'egyptian' ? 'active' : ''}`}
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
              className={`day-tab ${selectedDayIdx === i ? 'active' : ''}`}
              onClick={() => setSelectedDayIdx(i)}
            >
              {translate('day', lang)} {formatNumber(d.day, lang)}
            </button>
          ))}
        </div>

        <div className="day-summary-row">
          <span>
            {isAr ? AR_NAMES.regions[currentDay.area] || currentDay.area : currentDay.area}
            {currentDay.weekday ? ` · ${isAr ? AR_NAMES.weekdays[currentDay.weekday.toLowerCase()] || currentDay.weekday : currentDay.weekday}` : ''}
          </span>
          <span style={{ fontSize: '13px', color: '#555' }}>
            {formatHoursMins(dayTotalMinutes)} · {formatNumber(dayTotalEgp, lang)} {translate('egp', lang)}
          </span>
        </div>

        {/* Stops list */}
        <ul className="stops-list">
          {currentDay.stops.map((s, idx) => {
            const stopKey = `${selectedDayIdx}-${idx}`;
            const isOpen = !!expandedStops[stopKey];
            const p = getStopPrice(s);

            return (
              <li key={stopKey} className="stop-item">
                <div className="stop-header" onClick={() => toggleStop(stopKey)}>
                  <div className="stop-left">
                    <span className="stop-badge">{formatNumber(idx + 1, lang)}</span>
                    <div>
                      <div className="stop-name-text">
                        {isAr ? AR_NAMES.places[s.attraction_id] || s.name : s.name}
                      </div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '2px' }}>
                        {s.start}–{s.end} · {p ? `${formatNumber(p, lang)} ${translate('egp', lang)}` : translate('free', lang)}
                      </div>
                    </div>
                  </div>
                  <span style={{ fontSize: '14px', transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}>
                    ▼
                  </span>
                </div>

                {isOpen && (
                  <div className="stop-details-body">
                    {s.description && <p style={{ margin: '0 0 8px' }}>{s.description}</p>}
                    {s.hours_note && <p style={{ margin: '0 0 6px', color: '#777' }}>ⓘ {s.hours_note}</p>}
                    {s.source_url && (
                      <p style={{ margin: '6px 0 0', fontSize: '12px' }}>
                        <a href={s.source_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--azure)' }}>
                          {translate('source', lang)} ↗
                        </a>
                      </p>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>

        {/* Multi-Day Recommendations Card */}
        {(hotels.length > 0 || transport.length > 0) && (
          <div className="recs-card">
            <span className="recs-badge">{translate('recs_badge', lang)}</span>
            {hotels.length > 0 && (
              <div className="recs-group">
                <h4>🏨 {translate('recs_hotels', lang)}</h4>
                <ul>
                  {hotels.map((h, i) => (
                    <li key={i}>
                      <strong>{h.area}:</strong> {h.desc}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {transport.length > 0 && (
              <div className="recs-group">
                <h4>🚗 {translate('recs_transport', lang)}</h4>
                <ul>
                  {transport.map((tr, i) => (
                    <li key={i}>
                      <strong>{tr.mode}:</strong> {tr.desc}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Good to know */}
        {(currentDay.warnings?.length > 0 || itinerary.warnings?.length > 0) && (
          <div style={{ marginTop: '20px', background: '#fff9db', border: '1.5px solid var(--ink)', padding: '14px', borderRadius: '6px' }}>
            <h4 style={{ margin: '0 0 8px', fontSize: '14px' }}>{translate('good_to_know', lang)}</h4>
            <ul style={{ margin: 0, paddingInlineStart: '18px', fontSize: '13px' }}>
              {[...currentDay.warnings, ...itinerary.warnings].map((w, i) => (
                <li key={i} style={{ marginBottom: '4px' }}>{w}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="sheet-foot">
        <div>
          <strong>{translate('trip_total', lang)}:</strong> {formatHoursMins(tripTotalMinutes)} · {formatNumber(tripTotalEgp, lang)} {translate('egp', lang)}
        </div>
        <button
          type="button"
          className="print-btn"
          onClick={() => window.print()}
        >
          {translate('print', lang)}
        </button>
      </div>
    </div>
  );
};
