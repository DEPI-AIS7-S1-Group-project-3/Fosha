import React, { useState, useEffect, useRef } from 'react';
import { Language, ChatMessage, ChatResponse } from '../types';
import { translate, I18N, AR_NAMES, formatNumber } from '../i18n';
import { ReplyText } from './ReplyText';

interface ChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  lang: Language;
  messages: ChatMessage[];
  busy: boolean;
  onSendMessage: (text: string) => void;
  onOpenTripSheet: () => void;
  onNewTrip: () => void;
  initialQuery?: string;
}

export const ChatModal: React.FC<ChatModalProps> = ({
  isOpen,
  onClose,
  lang,
  messages,
  busy,
  onSendMessage,
  onOpenTripSheet,
  onNewTrip,
  initialQuery = '',
}) => {
  const [inputVal, setInputVal] = useState(initialQuery);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (initialQuery) {
      setInputVal(initialQuery);
    }
  }, [initialQuery]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
    }
  }, [isOpen]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, busy]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputVal.trim();
    if (!trimmed || busy) return;
    onSendMessage(trimmed);
    setInputVal('');
  };

  const handleChipClick = (msg: string) => {
    if (busy) return;
    onSendMessage(msg);
  };

  const isAr = lang === 'ar';

  const renderClarificationChips = (res: ChatResponse) => {
    const missing = res.missing || [];
    const intent = res.intent || { task: 'plan_trip', language: lang, search_query: '', interests: [] };
    const groups: Array<{ label: string; items: Array<{ label: string; msg: string }> }> = [];

    if (missing.includes('days')) {
      groups.push({
        label: translate('how_many_days', lang),
        items: I18N[lang].day_options,
      });
    }

    // Only regions that fit the trip length (the backend decides, so text and buttons agree).
    if (missing.includes('region')) {
      const regionNames = res.suggested_regions?.length
        ? res.suggested_regions
        : ['Cairo', 'Luxor', 'Aswan', 'Alexandria', 'South Sinai', 'Red Sea'];
      groups.push({
        label: translate('which_region', lang),
        items: regionNames.map((r) => ({
          label: isAr ? AR_NAMES.regions[r] || r : r,
          msg: isAr ? AR_NAMES.regions[r] || r : r,
        })),
      });
    }

    // Budget and group size only shape hotel/transport tips, which need 2+ days.
    const multiDay = !intent.days || intent.days >= 2;

    if (multiDay && !intent.budget) {
      groups.push({
        label: translate('budget_label', lang),
        items: I18N[lang].budget_options,
      });
    }

    if (multiDay && !intent.travelers) {
      groups.push({
        label: translate('travelers_label', lang),
        items: I18N[lang].travelers_options,
      });
    }

    if (!groups.length) return null;

    return (
      <div className="quick-groups">
        {groups.map((grp, gi) => (
          <div key={gi}>
            <div className="quick-group-label">{grp.label}</div>
            <div className="quick-chips">
              {grp.items.map((item, ii) => (
                <button
                  key={ii}
                  type="button"
                  className="quick-chip"
                  onClick={() => handleChipClick(item.msg)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderPlanCard = (res: ChatResponse) => {
    if (!res.itinerary) return null;
    const days = res.itinerary.days;
    const recs = res.itinerary.recommendations || { hotels: [], transport: [] };
    const hotelArea = recs.hotels?.[0]?.area;
    const transportMode = recs.transport?.[0]?.mode;

    return (
      <div className="plan-card">
        <div className="eyebrow">{translate('plan_ready', lang)}</div>
        <h3 className="plan-card-title">
          {days.length === 1
            ? translate('one_day_in', lang, { place: isAr ? AR_NAMES.regions[days[0].area] || days[0].area_ar || days[0].area : days[0].area })
            : translate('days_in', lang, {
                n: formatNumber(days.length, lang),
                place: isAr ? AR_NAMES.regions[days[0].area] || days[0].area_ar || days[0].area : days[0].area,
              })}
        </h3>

        <ul className="plan-days">
          {days.map((d, i) => (
            <li key={i}>
              <b>{translate('day', lang)} {formatNumber(d.day, lang)}: </b>
              <span>{d.stops.map((s) => isAr ? AR_NAMES.places[s.attraction_id] || s.name_ar || s.name : s.name).join(' · ')}</span>
            </li>
          ))}
        </ul>

        {(hotelArea || transportMode) && (
          <div className="plan-recs-summary">
            {hotelArea && <span>🏨 {hotelArea}</span>}
            {transportMode && <span>🚗 {transportMode}</span>}
          </div>
        )}

        <button
          type="button"
          className="btn"
          onClick={onOpenTripSheet}
          style={{ width: '100%', justifyContent: 'center' }}
        >
          <span>{translate('open_plan', lang)}</span>
          <span className="arrow">→</span>
        </button>
      </div>
    );
  };

  return (
    <div className="chat-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="chat-modal-dialog"
        onClick={(e) => e.stopPropagation()}
        dir={isAr ? 'rtl' : 'ltr'}
      >
        <header className="chat-modal-header">
          <div className="chat-header-info">
            <div className="chat-avatar" aria-hidden="true">🐪</div>
            <div>
              <h3 className="chat-title">{translate('chat_title', lang)}</h3>
              <div className="chat-status">
                <span className="status-dot" />
                <span>{translate('chat_status', lang)}</span>
              </div>
            </div>
          </div>

          <div className="chat-header-actions">
            {messages.length > 0 && (
              <button
                type="button"
                className="chat-new-trip"
                onClick={onNewTrip}
              >
                {translate('new_trip', lang)}
              </button>
            )}
            <button
              type="button"
              className="chat-close-btn"
              onClick={onClose}
              aria-label={translate('close', lang)}
            >
              ×
            </button>
          </div>
        </header>

        <div className="chat-modal-body" ref={scrollRef}>
          <div className="thread">
            {messages.length === 0 && (
              <div className="msg ai">
                <div className="who">{translate('ai', lang)}</div>
                <div className="text">{translate('hero_sub', lang)}</div>
                <div className="quick-groups" style={{ marginTop: '16px' }}>
                  <div className="quick-group-label">{translate('try_instead', lang)}</div>
                  <div className="quick-chips">
                    {I18N[lang].chips.map((c, i) => (
                      <button
                        key={i}
                        type="button"
                        className="quick-chip"
                        onClick={() => handleChipClick(c.msg)}
                      >
                        {c.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {messages.map((m, idx) => (
              <div key={m.id || idx} className={`msg ${m.role}`}>
                {m.role !== 'user' && <div className="who">{translate('ai', lang)}</div>}
                {m.role === 'user' ? <div className="text">{m.text}</div> : <ReplyText text={m.text} />}

                {m.result?.status === 'needs_clarification' && idx === messages.length - 1 && (
                  renderClarificationChips(m.result)
                )}

                {m.result?.status === 'planned' && (
                  renderPlanCard(m.result)
                )}
              </div>
            ))}

            {busy && (
              <div className="msg ai">
                <div className="who">{translate('ai', lang)}</div>
                <div className="thinking-row">
                  <span className="dots">
                    <i /><i /><i />
                  </span>
                  <span>{I18N[lang].thinking[0]}</span>
                </div>
              </div>
            )}
          </div>
        </div>

        <footer className="chat-modal-footer">
          <form className="chat-composer" onSubmit={handleSubmit} autoComplete="off">
            <input
              ref={inputRef}
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder={translate('placeholder_chat', lang)}
              disabled={busy}
              aria-label="Chat input"
            />
            <button
              type="submit"
              className="send"
              disabled={busy || !inputVal.trim()}
              aria-label={translate('send', lang)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M4 12h15M13 5l7 7-7 7"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </form>
          <div className="chat-footer-note">
            <span>{translate('disclaimer', lang)}</span>
          </div>
        </footer>
      </div>
    </div>
  );
};
