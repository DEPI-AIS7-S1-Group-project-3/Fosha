import React, { useCallback, useEffect, useState } from 'react';
import { AnalyticsSummary, Language, WindowStats } from '../types';
import { AR_NAMES, formatNumber, translate } from '../i18n';

/** Insights page (/dashboard): reads GET /api/v1/analytics, i.e. the real chat log
    (demo seed events are excluded server-side). */
interface DashboardViewProps {
  lang: Language;
}

const RANGES = [
  { days: 7, key: 'r7' as const },
  { days: 30, key: 'r30' as const },
  { days: 0, key: 'rall' as const },
];
const COLORS = ['var(--azure)', 'var(--coral)', 'var(--ink)'];

export const DashboardView: React.FC<DashboardViewProps> = ({ lang }) => {
  const isAr = lang === 'ar';
  const [days, setDays] = useState<number>(30);
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [grown, setGrown] = useState(false); // bars animate from 0 once data arrives

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    setGrown(false);
    fetch(`/api/v1/analytics?days=${days}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json: AnalyticsSummary) => {
        setData(json);
        window.setTimeout(() => setGrown(true), 60); // a timer, not rAF: rAF pauses in background tabs
      })
      .catch((err) => setError(String(err.message || err)))
      .finally(() => setLoading(false));
  }, [days]);

  useEffect(load, [load]);

  const n = (v: number, digits = 0) => formatNumber(Number(v.toFixed(digits)), lang);
  const region = (name: string) => (isAr ? AR_NAMES.regions[name] || name : name);
  const place = (a: AnalyticsSummary['attractions'][number]) =>
    isAr ? AR_NAMES.places[a.id] || a.name_ar || a.name : a.name;
  const category = (c: string) => (isAr ? AR_NAMES.categories[c] || c : c);

  const trend = (cur: number, prev: number | undefined, kind: 'rel' | 'pp' | 's', lowerIsBetter = false) => {
    if (prev === undefined || data?.previous === null) return <div className="trend muted">{translate('no_prev', lang)}</div>;
    let diff: number;
    let label: string;
    if (kind === 'pp') {
      diff = (cur - prev) * 100;
      label = `${diff >= 0 ? '+' : ''}${n(diff, 1)} pp`;
    } else if (kind === 's') {
      diff = (cur - prev) / 1000;
      label = `${diff >= 0 ? '+' : ''}${n(diff, 1)}${translate('seconds', lang)}`;
    } else {
      diff = prev ? ((cur - prev) / prev) * 100 : 0;
      label = `${diff >= 0 ? '+' : ''}${n(diff, 0)}%`;
    }
    const good = lowerIsBetter ? diff <= 0 : diff >= 0;
    return (
      <div className={`trend ${good ? 'good' : 'bad'}`}>
        {diff >= 0 ? '▲' : '▼'} <b>{label}</b> {translate('vs_prev', lang)}
      </div>
    );
  };

  const header = (
    <div className="dash-head">
      <div>
        <h1>{translate('dash_title', lang)}</h1>
        <p className="dash-sub">{translate('dash_sub', lang)}</p>
      </div>
      <div className="dash-tools">
        {RANGES.map((r) => (
          <button key={r.days} type="button" className="text-btn" aria-pressed={days === r.days} onClick={() => setDays(r.days)}>
            {translate(r.key, lang)}
          </button>
        ))}
        <span className="sep" aria-hidden="true" />
        <button type="button" className="text-btn" onClick={load}>{translate('refresh', lang)}</button>
      </div>
    </div>
  );

  if (loading && !data) {
    return (
      <div className="dashboard-page">
        {header}
        <div className="dash-skeleton" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="dashboard-page">
        {header}
        <div className="dash-empty">
          <h2>{translate('load_error', lang)}</h2>
          <p>{error}</p>
          <button type="button" className="btn" onClick={load}>{translate('refresh', lang)}</button>
        </div>
      </div>
    );
  }
  if (!data || !data.current.total_queries) {
    return (
      <div className="dashboard-page">
        {header}
        <div className="dash-empty">
          <div className="dash-empty-orb" />
          <h2>{translate('no_data_title', lang)}</h2>
          <p>{translate('no_data_body', lang)}</p>
          <a className="btn" href="/">{translate('open_app', lang)}</a>
        </div>
      </div>
    );
  }

  const cur: WindowStats = data.current;
  const prev = data.previous ?? undefined;
  const total = cur.total_queries;
  const arShare = cur.languages.ar / total;
  const prevArShare = prev && prev.total_queries ? prev.languages.ar / prev.total_queries : undefined;
  const orbit = days ? translate('dash_orbit', lang, { n: formatNumber(days, lang) }) : translate('dash_orbit_all', lang);
  const maxDest = Math.max(1, ...data.destinations.map((d) => d.count));
  const maxRegion = Math.max(1, ...data.regions.map((d) => d.count));
  const maxPlace = Math.max(1, ...data.attractions.map((d) => d.count));
  const ring = 2 * Math.PI * 76;

  return (
    <div className="dashboard-page">
      {header}

      <section className="dash-hero">
        <div className="dash-orb" aria-label={`${total} ${translate('k_queries', lang)}`}>
          <svg viewBox="-220 -220 440 440" aria-hidden="true">
            <defs>
              <path id="dash-orb-path" d="M0,-182 A182,182 0 1,1 0,182 A182,182 0 1,1 0,-182" />
            </defs>
            <circle r="215" fill="var(--azure)" />
            <g>
              <animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="60s" repeatCount="indefinite" />
              <text fill="var(--white)" textAnchor="middle" fontFamily={isAr ? 'Lalezar' : 'Changa One'} fontSize={isAr ? 24 : 21} letterSpacing="2">
                <textPath href="#dash-orb-path" startOffset="50%">{orbit.repeat(isAr ? 5 : 4)}</textPath>
              </text>
            </g>
          </svg>
          <div className="dash-orb-center">
            <div className="big">{n(total)}</div>
            <div className="unit">{translate('k_queries', lang)}</div>
            <div className="planned">{translate('k_planned', lang, { n: n(cur.planned) })}</div>
            {trend(total, prev?.total_queries, 'rel')}
          </div>
        </div>

        <div className="dash-stats">
          <div className="dash-stat">
            <div className="label">{translate('k_cache', lang)}</div>
            <div className="value">{n(cur.cache_hit_rate * 100)}<small>%</small></div>
            {trend(cur.cache_hit_rate, prev?.cache_hit_rate, 'pp')}
          </div>
          <div className="dash-stat">
            <div className="label">{translate('k_resp', lang)}</div>
            <div className="value">{n(cur.avg_response_ms / 1000, 1)}<small>{translate('seconds', lang)}</small></div>
            {trend(cur.avg_response_ms, prev?.avg_response_ms, 's', true)}
          </div>
          <div className="dash-stat">
            <div className="label">{translate('k_lang', lang)}</div>
            <div className="value">{n(arShare * 100)}<small>%</small></div>
            {trend(arShare, prevArShare, 'pp')}
          </div>
        </div>
      </section>

      <section className="dash-panels">
        <article className="dash-panel span-7">
          <h2>{translate('destinations', lang)}</h2>
          <p className="panel-sub">{translate('destinations_sub', lang)}</p>
          <div className="bars">
            {data.destinations.map((d, i) => (
              <div className="bar-row" key={d.name}>
                <span className="bar-label">{region(d.name)}</span>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: grown ? `${(d.count / maxDest) * 100}%` : 0, background: COLORS[Math.min(i, 2)] }} />
                </div>
                <span className="bar-n">{n(d.count)}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="dash-panel span-5">
          <h2>{translate('lang_dist', lang)}</h2>
          <p className="panel-sub">{translate('lang_dist_sub', lang)}</p>
          <div className="donut">
            <svg viewBox="0 0 200 200" role="img" aria-label={translate('lang_dist', lang)}>
              <circle cx="100" cy="100" r="76" fill="none" stroke="var(--coral)" strokeWidth="30" />
              <circle
                cx="100" cy="100" r="76" fill="none" stroke="var(--azure)" strokeWidth="30" transform="rotate(-90 100 100)"
                strokeDasharray={`${grown ? (cur.languages.en / total) * ring : 0} ${ring}`}
                style={{ transition: 'stroke-dasharray 1.2s var(--ease)' }}
              />
              <text x="100" y="108" textAnchor="middle" fontFamily="Changa One" fontSize="30" fill="var(--ink)">{n(total)}</text>
            </svg>
            <div className="legend">
              <div className="legend-row"><i style={{ background: 'var(--azure)' }} />{translate('english', lang)}</div>
              <div className="legend-pct">{n((cur.languages.en / total) * 100)}%</div>
              <div className="legend-row"><i style={{ background: 'var(--coral)' }} />{translate('arabic', lang)}</div>
              <div className="legend-pct">{n(arShare * 100)}%</div>
            </div>
          </div>
        </article>

        <article className="dash-panel span-5">
          <h2>{translate('regions', lang)}</h2>
          <p className="panel-sub">{translate('regions_sub', lang)}</p>
          <div className="cols">
            {data.regions.map((r, i) => (
              <div className="col" key={r.name}>
                <span className="col-n">{n(r.count)}</span>
                <div className="col-bar" style={{ height: grown ? `${(r.count / maxRegion) * 82}%` : 0, background: COLORS[i % 3] }} />
              </div>
            ))}
          </div>
          <div className="col-labels">
            {data.regions.map((r) => <span key={r.name} title={region(r.name)}>{region(r.name)}</span>)}
          </div>
        </article>

        <article className="dash-panel span-7">
          <h2>{translate('attractions', lang)}</h2>
          <p className="panel-sub">{translate('attractions_sub', lang)}</p>
          <table className="rank-table">
            <thead>
              <tr>
                <th>#</th>
                <th>{translate('t_name', lang)}</th>
                <th>{translate('t_region', lang)}</th>
                <th>{translate('t_category', lang)}</th>
                <th className="num">{translate('t_count', lang)}</th>
              </tr>
            </thead>
            <tbody>
              {data.attractions.map((a, i) => (
                <tr key={a.id}>
                  <td className="rank">{n(i + 1)}</td>
                  <td className="name">{place(a)}</td>
                  <td>{region(a.region)}</td>
                  <td>{category(a.category)}</td>
                  <td className="num"><span className="mini" style={{ width: grown ? `${(a.count / maxPlace) * 56}px` : 0 }} />{n(a.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      </section>
    </div>
  );
};
