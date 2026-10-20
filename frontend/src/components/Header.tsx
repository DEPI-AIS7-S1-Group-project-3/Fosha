import React from 'react';
import { Language } from '../types';
import { translate } from '../i18n';

interface HeaderProps {
  lang: Language;
  onSetLang: (lang: Language) => void;
  onOpenChat: () => void;
  onOpenTripSheet: () => void;
  onNewTrip: () => void;
  hasTrip: boolean;
  activeView: 'home' | 'dashboard';
  onNavigateView: (view: 'home' | 'dashboard') => void;
}

export const Header: React.FC<HeaderProps> = ({
  lang,
  onSetLang,
  onOpenChat,
  onOpenTripSheet,
  onNewTrip,
  hasTrip,
  activeView,
  onNavigateView,
}) => {
  const isAr = lang === 'ar';

  return (
    <header className="site-header">
      <div
        className="wordmark"
        onClick={() => onNavigateView('home')}
        role="button"
        tabIndex={0}
        aria-label="Fosha - فسحه"
      >
        {isAr ? (
          <>
            <span className="wordmark-ar" style={{ fontFamily: "'Almarai', sans-serif", fontSize: '26px', fontWeight: 800 }}>فسحه</span>
            <span className="wordmark-sep">-</span>
            <span className="wordmark-en" style={{ fontSize: '22px' }}>Fosha</span>
          </>
        ) : (
          <>
            <span className="wordmark-en">Fosha</span>
            <span className="wordmark-sep">-</span>
            <span className="wordmark-ar" style={{ fontFamily: "'Almarai', sans-serif", fontSize: '22px', fontWeight: 700 }}>فسحه</span>
          </>
        )}
        <span className="wordmark-dot" aria-hidden="true" />
      </div>

      <nav className="nav" aria-label="Main Navigation">
        <button
          type="button"
          onClick={() => {
            if (activeView !== 'home') onNavigateView('home');
            onOpenChat();
          }}
          aria-current={activeView === 'home' ? 'page' : undefined}
        >
          {translate('nav_plan', lang)}
        </button>
        <button
          type="button"
          onClick={onOpenTripSheet}
        >
          {translate('nav_trip', lang)}
        </button>
        <button
          type="button"
          onClick={() => onNavigateView(activeView === 'home' ? 'dashboard' : 'home')}
        >
          {activeView === 'home' ? translate('dash_title', lang) : translate('open_app', lang)}
        </button>
      </nav>

      <div className="tools">
        {hasTrip && (
          <button type="button" className="text-btn" onClick={onNewTrip}>
            {translate('new_trip', lang)}
          </button>
        )}
        <button
          type="button"
          className="text-btn"
          aria-pressed={lang === 'en'}
          onClick={() => onSetLang('en')}
        >
          EN
        </button>
        <span className="sep" aria-hidden="true" />
        <button
          type="button"
          className="text-btn font-almarai"
          aria-pressed={lang === 'ar'}
          onClick={() => onSetLang('ar')}
          style={{ fontFamily: "'Almarai', sans-serif" }}
        >
          ع
        </button>
      </div>
    </header>
  );
};
