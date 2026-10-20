import React, { useState, useEffect } from 'react';
import { Language, ChatMessage, ChatResponse } from './types';
import { Header } from './components/Header';
import { Clouds } from './components/Clouds';
import { GlobeCanvas } from './components/GlobeCanvas';
import { LandingHero } from './components/LandingHero';
import { ChatModal } from './components/ChatModal';
import { TripSheet } from './components/TripSheet';
import { DashboardView } from './components/DashboardView';
import { translate, I18N } from './i18n';

export const App: React.FC = () => {
  const [lang, setLang] = useState<Language>(() => {
    return (localStorage.getItem('fosha_lang') as Language) || 'en';
  });

  const isDashboardRoute = window.location.pathname === '/dashboard';

  const [isChatOpen, setIsChatOpen] = useState(false);
  const [isTripSheetOpen, setIsTripSheetOpen] = useState(false);
  const [landingInputValue, setLandingInputValue] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      const saved = localStorage.getItem('fosha_chat_msgs');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [plan, setPlan] = useState<ChatResponse | null>(() => {
    try {
      const saved = localStorage.getItem('fosha_plan');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [busy, setBusy] = useState(false);
  const [targetGlobeRegion, setTargetGlobeRegion] = useState<string | null>(null);
  const [pendingClarificationPrompt, setPendingClarificationPrompt] = useState<string | null>(null);

  useEffect(() => {
    localStorage.setItem('fosha_lang', lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    document.title = lang === 'ar' ? 'فسحه - Fosha' : 'Fosha - فسحه';
  }, [lang]);

  useEffect(() => {
    try {
      localStorage.setItem('fosha_chat_msgs', JSON.stringify(messages));
    } catch {
      // ignore storage errors
    }
  }, [messages]);

  useEffect(() => {
    try {
      if (plan) {
        localStorage.setItem('fosha_plan', JSON.stringify(plan));
      } else {
        localStorage.removeItem('fosha_plan');
      }
    } catch {
      // ignore storage errors
    }
  }, [plan]);

  // Synchronize body.sheet-open class for half-world / half-itinerary layout
  useEffect(() => {
    if (isTripSheetOpen) {
      document.body.classList.add('sheet-open');
    } else {
      document.body.classList.remove('sheet-open');
    }
    return () => {
      document.body.classList.remove('sheet-open');
    };
  }, [isTripSheetOpen]);

  const handleSendMessage = async (text: string, fromLanding = false) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;

    const userMsg: ChatMessage = {
      id: String(Date.now()),
      role: 'user',
      text: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);
    setBusy(true);

    const fullMessage = pendingClarificationPrompt ? `${pendingClarificationPrompt}. ${trimmed}` : trimmed;

    try {
      const res = await fetch('/api/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: fullMessage }),
      });

      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data: ChatResponse = await res.json();

      if (!data.ok) throw new Error(data.error || 'Request failed');

      const aiMsg: ChatMessage = {
        id: String(Date.now() + 1),
        role: 'ai',
        text: data.reply,
        result: data,
      };

      setMessages((prev) => [...prev, aiMsg]);

      if (data.status === 'needs_clarification') {
        setPendingClarificationPrompt(fullMessage);
        // The plan is NOT full: POP UP the chatbot modal to clarify with the user
        setIsChatOpen(true);
      } else {
        setPendingClarificationPrompt(null);
      }

      if (data.status === 'planned' && data.itinerary) {
        setPlan(data);
        if (data.intent?.region) {
          setTargetGlobeRegion(data.intent.region);
        }
        // If sent from landing or plan is complete:
        // Close modal and reveal the iconic half-world half-itinerary sheet!
        if (fromLanding) {
          setIsChatOpen(false);
          setIsTripSheetOpen(true);
        }
      } else if (data.status !== 'planned' && fromLanding) {
        // Any non-full result from landing pops up the chatbot
        setIsChatOpen(true);
      }
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: String(Date.now() + 1),
        role: 'error',
        text: String(err?.message || err),
      };
      setMessages((prev) => [...prev, errorMsg]);
      if (fromLanding) {
        setIsChatOpen(true);
      }
    } finally {
      setBusy(false);
      setLandingInputValue('');
    }
  };

  const handleLandingSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!landingInputValue.trim()) return;
    handleSendMessage(landingInputValue, true);
  };

  const handleGlobePick = (region: string) => {
    setTargetGlobeRegion(region);
    const prompt = lang === 'ar' ? `رحلة ٣ أيام في ${region}` : `3 days in ${region}`;
    handleSendMessage(prompt, true);
  };

  const handleChipClick = (msg: string) => {
    handleSendMessage(msg, true);
  };

  const handleNewTrip = () => {
    setMessages([]);
    setPlan(null);
    setPendingClarificationPrompt(null);
    setTargetGlobeRegion(null);
    setIsTripSheetOpen(false);
    setIsChatOpen(false);
    setLandingInputValue('');
  };

  const handleOpenPlan = () => {
    setIsTripSheetOpen(false);
  };

  const handleOpenTripSheetFromModal = () => {
    setIsChatOpen(false);
    setIsTripSheetOpen(true);
  };

  return (
    <div className="app-root">
      <Clouds />

      <Header
        lang={lang}
        onSetLang={setLang}
        onOpenPlan={handleOpenPlan}
        onOpenTripSheet={() => setIsTripSheetOpen(true)}
        onNewTrip={handleNewTrip}
        hasTrip={!!plan}
        isTripSheetOpen={isTripSheetOpen}
      />

      {isDashboardRoute ? (
        <DashboardView lang={lang} />
      ) : (
        <>
          <LandingHero lang={lang} />

          <GlobeCanvas
            lang={lang}
            busy={busy}
            onPick={handleGlobePick}
            targetRegion={targetGlobeRegion}
          >
            {/* Sitting ON the Globe: Composer and Prompt Chips */}
            <form className="on-globe composer" onSubmit={handleLandingSubmit} autoComplete="off">
              <input
                id="input"
                maxLength={2000}
                aria-label="Trip planning prompt"
                placeholder={translate('placeholder', lang)}
                value={landingInputValue}
                onChange={(e) => setLandingInputValue(e.target.value)}
              />
              <button type="submit" className="send" aria-label="Send" disabled={busy}>
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

            <div className="on-globe globe-extras">
              <div className="chips">
                {I18N[lang].chips.map((chip, i) => (
                  <button
                    key={i}
                    type="button"
                    className="chip"
                    onClick={() => handleChipClick(chip.msg)}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
              <p className="globe-hint">{translate('globe_hint', lang)}</p>
            </div>
          </GlobeCanvas>

          {/* Half-World Half-Itinerary Sheet */}
          <TripSheet
            isOpen={isTripSheetOpen}
            onClose={() => setIsTripSheetOpen(false)}
            lang={lang}
            plan={plan}
            onOpenChat={() => setIsChatOpen(true)}
          />

          {/* Scrim backdrop when sheet is open on smaller devices */}
          <div
            className="scrim"
            onClick={() => setIsTripSheetOpen(false)}
            aria-hidden="true"
          />

          {/* Dedicated Chatbot Popup Modal (Opens when plan needs clarification or user requests chat) */}
          <ChatModal
            isOpen={isChatOpen}
            onClose={() => setIsChatOpen(false)}
            lang={lang}
            messages={messages}
            busy={busy}
            onSendMessage={(msg) => handleSendMessage(msg, false)}
            onOpenTripSheet={handleOpenTripSheetFromModal}
            onNewTrip={handleNewTrip}
          />
        </>
      )}
    </div>
  );
};
