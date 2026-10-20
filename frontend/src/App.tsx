import React, { useState, useEffect } from 'react';
import { Language, ChatMessage, ChatResponse } from './types';
import { Header } from './components/Header';
import { Clouds } from './components/Clouds';
import { GlobeCanvas } from './components/GlobeCanvas';
import { LandingHero } from './components/LandingHero';
import { ChatModal } from './components/ChatModal';
import { TripSheet } from './components/TripSheet';
import { DashboardView } from './components/DashboardView';

export const App: React.FC = () => {
  const [lang, setLang] = useState<Language>(() => {
    return (localStorage.getItem('fosha_lang') as Language) || 'en';
  });
  const [activeView, setActiveView] = useState<'home' | 'dashboard'>('home');
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [isTripSheetOpen, setIsTripSheetOpen] = useState(false);
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
  const [chatInitialQuery, setChatInitialQuery] = useState('');
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
      // storage errors ignored
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
      // storage errors ignored
    }
  }, [plan]);

  const handleOpenChatWithQuery = (query: string) => {
    setChatInitialQuery(query);
    setIsChatOpen(true);
  };

  const handleGlobePick = (region: string) => {
    setTargetGlobeRegion(region);
    const prefix = lang === 'ar' ? `رحلة ٣ أيام في ${region}` : `3 days in ${region}`;
    handleOpenChatWithQuery(prefix);
  };

  const handleSendMessage = async (text: string) => {
    if (busy) return;
    const userMsg: ChatMessage = {
      id: String(Date.now()),
      role: 'user',
      text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setBusy(true);

    const fullMessage = pendingClarificationPrompt ? `${pendingClarificationPrompt}. ${text}` : text;

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
      } else {
        setPendingClarificationPrompt(null);
      }

      if (data.status === 'planned') {
        setPlan(data);
        if (data.intent?.region) {
          setTargetGlobeRegion(data.intent.region);
        }
      }
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: String(Date.now() + 1),
        role: 'error',
        text: String(err?.message || err),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setBusy(false);
    }
  };

  const handleNewTrip = () => {
    setMessages([]);
    setPlan(null);
    setPendingClarificationPrompt(null);
    setChatInitialQuery('');
    setTargetGlobeRegion(null);
    setIsTripSheetOpen(false);
  };

  return (
    <div className={`app-root ${lang === 'ar' ? 'font-almarai' : ''}`}>
      <Clouds />

      <Header
        lang={lang}
        onSetLang={setLang}
        onOpenChat={() => setIsChatOpen(true)}
        onOpenTripSheet={() => setIsTripSheetOpen(true)}
        onNewTrip={handleNewTrip}
        hasTrip={!!plan}
        activeView={activeView}
        onNavigateView={setActiveView}
      />

      {activeView === 'home' ? (
        <>
          <LandingHero
            lang={lang}
            onOpenChatWithQuery={handleOpenChatWithQuery}
          />

          <GlobeCanvas
            lang={lang}
            busy={busy}
            onPick={handleGlobePick}
            targetRegion={targetGlobeRegion}
          />
        </>
      ) : (
        <DashboardView lang={lang} />
      )}

      {/* Dedicated Chat View */}
      <ChatModal
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        lang={lang}
        messages={messages}
        busy={busy}
        onSendMessage={handleSendMessage}
        onOpenTripSheet={() => {
          setIsChatOpen(false);
          setIsTripSheetOpen(true);
        }}
        onNewTrip={handleNewTrip}
        initialQuery={chatInitialQuery}
      />

      {/* Day-by-Day Trip Sheet */}
      <TripSheet
        isOpen={isTripSheetOpen}
        onClose={() => setIsTripSheetOpen(false)}
        lang={lang}
        plan={plan}
      />
    </div>
  );
};
