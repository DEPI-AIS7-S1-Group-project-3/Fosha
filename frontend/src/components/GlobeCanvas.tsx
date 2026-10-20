import React, { useEffect, useRef } from 'react';
import { Language } from '../types';
import { translate } from '../i18n';

const R = 500;
const INK = 'var(--ink)';
const WHITE = 'var(--white)';
const CORAL = 'var(--coral)';
const AZURE = 'var(--azure)';
const WALL = 'var(--wall)';

const crenels = (x: number, y: number, w: number, size = 14) => {
  let d = '';
  for (let cx = x; cx < x + w - 1; cx += size * 2) d += `M${cx} ${y}h${size}v${-size}h${-size}Z`;
  return `<path d="${d}" fill="${WHITE}"/>`;
};

const palm = (x: number, h: number, lean = 0) => `
  <path d="M${x} 0 C${x + lean * 0.3} ${-h * 0.4} ${x + lean * 0.7} ${-h * 0.75} ${x + lean} ${-h}" fill="none" stroke-width="7"/>
  <path transform="translate(${x + lean} ${-h})" fill="var(--palm)" d="M0 0 C-30 -14 -58 -2 -66 18 C-44 4 -20 2 0 0 C-14 -30 -44 -38 -60 -30 C-36 -22 -14 -14 0 0 C10 -32 40 -40 58 -30 C34 -24 14 -14 0 0 C26 -12 54 -2 64 18 C42 6 22 2 0 0Z"/>`;

const LANDMARKS = [
  {
    region: 'Alexandria',
    svg: `
      <rect x="-118" y="-95" width="34" height="95" fill="${WHITE}"/>${crenels(-118, -95, 34, 9)}
      <rect x="84" y="-95" width="34" height="95" fill="${WHITE}"/>${crenels(84, -95, 34, 9)}
      <rect x="-90" y="-70" width="180" height="70" fill="${WALL}"/>${crenels(-90, -70, 180, 12)}
      <rect x="-42" y="-150" width="84" height="80" fill="${WHITE}"/>${crenels(-42, -150, 84, 12)}
      <path d="M-14 0V-34a14 14 0 0 1 28 0V0Z" fill="${AZURE}"/>
      <rect x="-8" y="-128" width="16" height="26" fill="${INK}" stroke="none"/>`,
  },
  {
    region: 'Cairo',
    svg: `
      <path d="M-120 0 L-35 -165 L50 0Z" fill="${WHITE}"/><path d="M-35 -165 L50 0 L5 0Z" fill="${CORAL}"/>
      <path d="M30 0 L82 -100 L134 0Z" fill="${WHITE}"/><path d="M82 -100 L134 0 L104 0Z" fill="${CORAL}"/>`,
  },
  {
    region: 'Cairo',
    svg: `
      <rect x="-120" y="-105" width="48" height="105" fill="${WALL}"/>
      <rect x="-108" y="-88" width="10" height="16" fill="${WHITE}"/><rect x="-92" y="-88" width="10" height="16" fill="${WHITE}"/>
      <rect x="-108" y="-56" width="10" height="16" fill="${WHITE}"/><rect x="-92" y="-56" width="10" height="16" fill="${WHITE}"/>
      <rect x="-60" y="-70" width="100" height="70" fill="${WHITE}"/>
      <path d="M-50 -70 A40 40 0 0 1 30 -70Z" fill="${CORAL}"/>
      <path d="M-24 0V-30a14 14 0 0 1 28 0V0Z" fill="${AZURE}"/>
      <rect x="56" y="-190" width="24" height="190" fill="${WALL}"/>
      <rect x="50" y="-138" width="36" height="10" fill="${WHITE}"/><rect x="50" y="-82" width="36" height="10" fill="${WHITE}"/>
      <path d="M56 -190 L68 -222 L80 -190Z" fill="${CORAL}"/>`,
  },
  {
    region: 'South Sinai',
    svg: `
      <path d="M-125 0 L-45 -165 L5 -95 L48 -140 L125 0Z" fill="${CORAL}"/>
      <path d="M-45 -165 L-22 -118 L-45 -110 L-65 -124Z" fill="${WHITE}"/>
      <rect x="-60" y="-55" width="86" height="55" fill="${WHITE}"/>${crenels(-60, -55, 86, 8)}
      <rect x="-28" y="-92" width="22" height="37" fill="${WHITE}"/>
      <path d="M-17 -112 V-96 M-24 -105 H-10" fill="none" stroke-width="4"/>`,
  },
  {
    region: 'Red Sea',
    svg: `
      <path d="M-30 0 V-128" fill="none" stroke-width="6"/>
      <path d="M-115 -112 Q-30 -190 55 -112 Q34 -104 13 -112 Q-9 -104 -30 -112 Q-51 -104 -72 -112 Q-94 -104 -115 -112Z" fill="${CORAL}"/>
      <path d="M-72 -112 Q-52 -170 -30 -150 Q-8 -170 13 -112" fill="none" stroke-width="4"/>
      <path d="M45 -70 C65 -95 100 -95 116 -70 C100 -45 65 -45 45 -70Z" fill="${AZURE}"/>
      <path d="M116 -70 L138 -86 V-54Z" fill="${AZURE}"/><circle cx="62" cy="-72" r="4" fill="${INK}" stroke="none"/>`,
  },
  {
    region: 'Luxor',
    svg: `
      <path d="M-160 0 L-154 -175 L-146 -192 L-138 -175 L-132 0Z" fill="${WHITE}"/>
      <path d="M-115 0 L-104 -140 L-42 -140 L-32 0Z" fill="${WALL}"/>
      <path d="M32 0 L42 -140 L104 -140 L115 0Z" fill="${WALL}"/>
      <rect x="-32" y="-96" width="64" height="96" fill="${WHITE}"/>
      <rect x="-38" y="-108" width="76" height="14" fill="${CORAL}"/>
      <rect x="-15" y="-64" width="30" height="64" fill="${AZURE}"/>
      <path d="M-92 -112 H-56 M-90 -84 H-58 M54 -112 H90 M56 -84 H88" fill="none" stroke-width="4"/>`,
  },
  {
    region: 'Aswan',
    svg: `
      <path d="M-95 -6 H95 L70 22 H-70Z" fill="${CORAL}"/>
      <path d="M0 -6 V-215" fill="none" stroke-width="6"/>
      <path d="M2 -212 L104 -30 L-62 -30Z" fill="${WHITE}"/>
      <path d="M-130 44 q16 -12 32 0 t32 0 M40 50 q16 -12 32 0 t32 0" fill="none" stroke="${WHITE}" stroke-width="5"/>`,
  },
  {
    region: 'Aswan',
    svg: `
      <rect x="-118" y="-80" width="96" height="80" fill="${WHITE}"/>
      <path d="M-118 -80 A48 34 0 0 1 -22 -80Z" fill="${AZURE}"/>
      <path d="M-84 0V-40a14 14 0 0 1 28 0V0Z" fill="${CORAL}"/>
      <path d="M-110 -16 l8 -10 l8 10 l8 -10 l8 10 M-48 -16 l8 -10 l8 10 l8 -10" fill="none" stroke-width="3"/>
      <rect x="0" y="-62" width="110" height="62" fill="${WALL}"/>
      <path d="M0 -62 A55 28 0 0 1 110 -62Z" fill="${WHITE}"/>
      <rect x="44" y="-38" width="22" height="38" fill="${AZURE}"/>`,
  },
  {
    region: 'New Valley',
    svg: `
      <path d="M-40 0 C-30 -40 -46 -72 -30 -96 H18 C32 -72 18 -40 28 0Z" fill="${WHITE}"/>
      <path d="M-86 -94 C-86 -150 72 -150 72 -94 C40 -82 -50 -82 -86 -94Z" fill="${WHITE}"/>
      <path d="M50 0 C56 -46 108 -52 120 0Z" fill="${WHITE}"/>
      <path d="M-130 0 C-110 -26 -84 -26 -64 0Z" fill="${WALL}"/>`,
  },
  {
    region: 'Matrouh',
    svg: `${palm(-80, 150, -24)}${palm(10, 190, 10)}${palm(90, 130, 26)}
      <path d="M-125 0 C-80 -30 -30 -30 0 0 C30 -26 80 -26 125 0Z" fill="${WALL}"/>`,
  },
];

const STEP = 360 / LANDMARKS.length;
const ARC = 452;
const SPREAD = (30 * Math.PI) / 180;

interface GlobeCanvasProps {
  lang: Language;
  busy: boolean;
  onPick: (region: string) => void;
  targetRegion?: string | null;
  children?: React.ReactNode;
}

export const GlobeCanvas: React.FC<GlobeCanvasProps> = ({
  lang,
  busy,
  onPick,
  targetRegion,
  children,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const turnRef = useRef<SVGGElement | null>(null);
  const textPathRef = useRef<SVGTextPathElement | null>(null);
  const angleRef = useRef<number>(-STEP);
  const targetRef = useRef<number | null>(null);
  const velocityRef = useRef<number>(0);
  const busyRef = useRef<boolean>(busy);

  busyRef.current = busy;

  useEffect(() => {
    if (!targetRegion) {
      targetRef.current = null;
      return;
    }
    const idx = LANDMARKS.findIndex((lm) => lm.region === targetRegion);
    if (idx >= 0) {
      targetRef.current = -idx * STEP;
      velocityRef.current = 0;
    }
  }, [targetRegion]);

  useEffect(() => {
    let animId: number;
    let lastTime = performance.now();

    const loop = (now: number) => {
      const dt = Math.min(0.05, (now - lastTime) / 1000);
      lastTime = now;

      if (targetRef.current != null && !busyRef.current) {
        const diff = ((targetRef.current - angleRef.current + 540) % 360) - 180;
        angleRef.current += diff * (1 - Math.exp(-dt * 2.2));
      } else {
        const speed = busyRef.current ? 16 : 2.2;
        angleRef.current += (speed + velocityRef.current) * dt;
      }
      velocityRef.current *= Math.exp(-dt * 2.2);

      if (turnRef.current) {
        turnRef.current.setAttribute('transform', `rotate(${angleRef.current.toFixed(3)})`);
      }
      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, []);

  const handlePointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    const svg = e.currentTarget;
    svg.setPointerCapture(e.pointerId);
    targetRef.current = null;

    let lastX = e.clientX;
    let moved = 0;
    let lastT = performance.now();

    const handlePointerMove = (ev: PointerEvent) => {
      const dx = ev.clientX - lastX;
      const now = performance.now();
      const scale = 360 / (Math.PI * svg.getBoundingClientRect().width * 0.8);
      angleRef.current += dx * scale;
      velocityRef.current = (dx * scale) / Math.max(0.008, (now - lastT) / 1000);
      velocityRef.current = Math.max(-400, Math.min(400, velocityRef.current));
      moved += Math.abs(dx);
      lastX = ev.clientX;
      lastT = now;
    };

    const handlePointerUp = (ev: PointerEvent) => {
      svg.removeEventListener('pointermove', handlePointerMove);
      svg.removeEventListener('pointerup', handlePointerUp);
      svg.removeEventListener('pointercancel', handlePointerUp);

      if (moved < 6) {
        velocityRef.current = 0;
        const hit = document.elementsFromPoint(ev.clientX, ev.clientY).find((el) =>
          el.closest?.('.landmark')
        );
        const lm = hit?.closest('.landmark') as HTMLElement | null;
        if (lm?.dataset.region) {
          onPick(lm.dataset.region);
        }
      }
    };

    svg.addEventListener('pointermove', handlePointerMove);
    svg.addEventListener('pointerup', handlePointerUp);
    svg.addEventListener('pointercancel', handlePointerUp);
  };

  const isAr = lang === 'ar';
  const ribbonText = translate('orbit', lang);
  const ribbonFont = isAr ? 'Lalezar' : 'Changa One';
  const ribbonSize = isAr ? 50 : 38;

  return (
    <div className="globe-wrap" ref={containerRef}>
      <svg
        className="globe-svg"
        viewBox="-640 -700 1280 1280"
        role="img"
        aria-label="Interactive Globe"
        onPointerDown={handlePointerDown}
      >
        <defs>
          <path
            id="react-arc-path"
            d={`M${-ARC * Math.sin(SPREAD)},${-ARC * Math.cos(SPREAD)} A${ARC},${ARC} 0 0,1 ${ARC * Math.sin(SPREAD)},${-ARC * Math.cos(SPREAD)}`}
          />
        </defs>
        <circle r={R} fill="var(--azure)" />
        <text
          fill="var(--white)"
          textAnchor="middle"
          fontFamily={ribbonFont}
          fontSize={ribbonSize}
          letterSpacing="1"
        >
          <textPath href="#react-arc-path" startOffset="50%" ref={textPathRef}>
            {ribbonText}
          </textPath>
        </text>
        <g ref={turnRef} className="globe-turn">
          <g
            className="globe-rim"
            stroke="var(--ink)"
            strokeWidth="5"
            strokeLinejoin="round"
            strokeLinecap="round"
          >
            {LANDMARKS.map((lm, i) => (
              <g
                key={i}
                className="landmark"
                transform={`rotate(${i * STEP}) translate(0 ${-R + 4})`}
                data-region={lm.region}
                role="button"
                tabIndex={0}
                style={{ cursor: 'pointer' }}
                dangerouslySetInnerHTML={{
                  __html: `<rect x="-140" y="-230" width="280" height="250" fill="transparent" stroke="none"/>${lm.svg}`,
                }}
              />
            ))}
          </g>
        </g>
      </svg>
      {children}
    </div>
  );
};
