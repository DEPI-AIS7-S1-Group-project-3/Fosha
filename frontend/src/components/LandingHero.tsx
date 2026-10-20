import React from 'react';
import { Language } from '../types';
import { translate } from '../i18n';

interface LandingHeroProps {
  lang: Language;
}

export const LandingHero: React.FC<LandingHeroProps> = ({ lang }) => {
  return (
    <section className="hero-copy">
      <h1 className="hero-title">
        <span className="l1">{translate('hero_1', lang)}</span>
        <span className="l2">{translate('hero_2', lang)}</span>
      </h1>
      <p className="hero-sub">{translate('hero_sub', lang)}</p>
    </section>
  );
};
