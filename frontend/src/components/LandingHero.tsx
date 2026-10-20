import React from 'react';
import { Language } from '../types';
import { translate, I18N } from '../i18n';

interface LandingHeroProps {
  lang: Language;
  onOpenChatWithQuery: (query: string) => void;
}

export const LandingHero: React.FC<LandingHeroProps> = ({
  lang,
  onOpenChatWithQuery,
}) => {
  const chips = I18N[lang].chips;

  const handleInputFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    onOpenChatWithQuery(e.target.value);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onOpenChatWithQuery(e.target.value);
  };

  return (
    <>
      <section className="hero-copy">
        <h1 className="hero-title">
          <span>{translate('hero_1', lang)}</span>
          <span>{translate('hero_2', lang)}</span>
        </h1>
        <p className="hero-sub">{translate('hero_sub', lang)}</p>
      </section>

      <div className="landing-composer-wrap">
        <div className="landing-composer">
          <input
            type="text"
            placeholder={translate('placeholder', lang)}
            onFocus={handleInputFocus}
            onChange={handleInputChange}
            aria-label="Trip planning prompt"
          />
          <button
            type="button"
            className="send-btn"
            onClick={() => onOpenChatWithQuery('')}
            aria-label="Start chat"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </button>
        </div>

        <div className="landing-chips">
          {chips.map((chip, i) => (
            <button
              key={i}
              type="button"
              className="chip"
              onClick={() => onOpenChatWithQuery(chip.msg)}
            >
              {chip.label}
            </button>
          ))}
        </div>

        <div className="globe-hint">{translate('globe_hint', lang)}</div>
      </div>
    </>
  );
};
