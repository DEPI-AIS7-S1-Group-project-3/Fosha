import React, { useState, useEffect, useRef } from 'react';
import { Language, ChatMessage, ChatResponse } from '../types';
import { translate, I18N, AR_NAMES, formatNumber } from '../i18n';

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
  const lastMsg = messages[messages.length - 1];

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

    if (missing.includes('region')) {
      const regionNames = ['Cairo', 'Luxor', 'Aswan', 'Alexandria', 'South Sinai', 'Red Sea'];
      groups.push({
        label: translate('which_region', lang),
        items: regionNames.map((r) => ({
          label: isAr ? AR_NAMES.regions[r] || r : r,
          msg: isAr ? AR_NAMES.regions[r] || r : r,
        })),
      });
    }

    if (!intent.budget) {
      groups.push({
        label: translate('budget_label', lang),
        items: I18N[lang].budget_options,
      });
    }

    if (!intent.travelers) {
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
        <div className="plan-card-eyebrow">{translate('plan_ready', lang)}</div>
        <div className="plan-card-title">
          {days.length === 1
            ? translate('one_day_in', lang, { place: days[0].area })
            : translate('days_in', lang, { n: formatNumber(days.length, lang), place: days[0].area })}
        </div>

        <ul className="plan-card-days">
          {days.map((d, i) => (
            <li key={i}>
              <strong>{translate('day', lang)} {formatNumber(d.day, lang)}: </strong>
              <span>{d.stops.map((s) => s.name).join(' · ')}</span>
            </li>
          ))}
        </ul>

        {(hotelArea || transportMode) && (
          <div className="plan-recs-tag">
            {hotelArea && <span>🏨 {hotelArea}</span>}
            {transportMode && <span>🚗 {transportMode}</span>}
          </div>
        )}

        <button
          type="button"
          className="open-sheet-btn"
          onClick={onOpenTripSheet}
        >
          {translate('open_plan', lang)} →
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
                className="chat-action-btn"
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
          {messages.length === 0 && (
            <div className="msg ai">
              <div className="msg-who">{translate('ai', lang)}</div>
              <div>{translate('hero_sub', lang)}</div>
              <div className="quick-groups" style={{ marginTop: '14px' }}>
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
              {m.role !== 'user' && <div className="msg-who">{translate('ai', lang)}</div>}
              <div style={{ whiteSpace: 'pre-wrap' }}>{m.text}</div>

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
              <div className="msg-who">{translate('ai', lang)}</div>
              <div className="thinking-row">
                <span className="dots">
                  <i /><i /><i />
                </span>
                <span>{I18N[lang].thinking[0]}</span>
              </div>
            </div>
          )}
        </div>

        <footer className="chat-modal-footer">
          <form className="chat-composer-box" onSubmit={handleSubmit}>
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
              disabled={busy || !inputVal.trim()}
              aria-label={translate('send', lang)}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </form>
          <div className="chat-footer-disclaimer">{translate('disclaimer', lang)}</div>
        </footer>
      </div>
    </div>
  );
};
