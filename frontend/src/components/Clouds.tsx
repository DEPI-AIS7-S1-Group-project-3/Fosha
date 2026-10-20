import React from 'react';

export const Clouds: React.FC = () => {
  return (
    <div className="clouds" aria-hidden="true">
      <svg
        className="cloud"
        style={{ top: '14vh', animationDuration: '210s', animationDelay: '-30s' }}
        viewBox="0 0 150 60"
        width="150"
      >
        <path d="M20 50c-14 0-18-16-6-21-2-14 16-22 26-12 6-16 34-18 40 0 14-6 30 2 28 16 14 2 14 17 0 17z" />
      </svg>
      <svg
        className="cloud"
        style={{ top: '26vh', width: '120px', animationDuration: '260s', animationDelay: '-90s' }}
        viewBox="0 0 150 60"
      >
        <path d="M20 50c-14 0-18-16-6-21-2-14 16-22 26-12 6-16 34-18 40 0 14-6 30 2 28 16 14 2 14 17 0 17z" />
      </svg>
    </div>
  );
};
