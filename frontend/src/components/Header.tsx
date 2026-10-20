import React from 'react';
import { Language } from '../types';
import { translate } from '../i18n';

interface HeaderProps {
  lang: Language;
  onSetLang: (lang: Language) => void;
  onOpenPlan: () => void;
  onOpenTripSheet: () => void;
  onNewTrip: () => void;
  hasTrip: boolean;
  isTripSheetOpen: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  lang,
  onSetLang,
  onOpenPlan,
  onOpenTripSheet,
  onNewTrip,
  hasTrip,
  isTripSheetOpen,
}) => {
  const isAr = lang === 'ar';

  return (
    <header className="site-header" style={{ direction: 'ltr' }}>
      <div
        className="wordmark"
        onClick={onOpenPlan}
        role="button"
        tabIndex={0}
        aria-label="Fosha · فسحة"
      >
        {isAr ? (
          <>
            <span className="wordmark-ar">
              فسحة
            </span>
            <span className="wordmark-sep">·</span>
            <span className="wordmark-main">
              Fosha
            </span>
          </>
        ) : (
          <>
            <span className="wordmark-main">Fosha</span>
            <span className="wordmark-sep">·</span>
            <span className="wordmark-ar">
              فسحة
            </span>
          </>
        )}
      </div>

      <nav className="nav" aria-label="Main Navigation">
        <button
          type="button"
          onClick={onOpenPlan}
          aria-current={!isTripSheetOpen ? 'page' : undefined}
        >
          {translate('nav_plan', lang)}
        </button>
        {hasTrip && (
          <button
            type="button"
            onClick={onOpenTripSheet}
            aria-current={isTripSheetOpen ? 'page' : undefined}
          >
            {translate('nav_trip', lang)}
          </button>
        )}
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
          className="text-btn"
          aria-pressed={lang === 'ar'}
          onClick={() => onSetLang('ar')}
        >
          ع
        </button>
      </div>
    </header>
  );
};
