import React, { useState, useEffect } from 'react';
import { Language, AnalyticsSummary } from '../types';
import { translate, formatNumber } from '../i18n';

interface DashboardViewProps {
  lang: Language;
}

export const DashboardView: React.FC<DashboardViewProps> = ({ lang }) => {
  const [periodDays, setPeriodDays] = useState<number>(7);
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    fetch(`/api/v1/analytics?days=${periodDays}`)
      .then((res) => res.json())
      .then((json: AnalyticsSummary) => {
        if (isMounted) {
          setData(json);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch analytics', err);
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [periodDays]);

  const isAr = lang === 'ar';

  return (
    <div className="dashboard-page" dir={isAr ? 'rtl' : 'ltr'}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ margin: '0 0 6px', fontSize: '32px' }}>{translate('dash_title', lang)}</h1>
          <p style={{ margin: 0, color: '#555' }}>{translate('dash_sub', lang)}</p>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          {[
            { days: 7, label: translate('r7', lang) },
            { days: 30, label: translate('r30', lang) },
            { days: 0, label: translate('rall', lang) },
          ].map((item) => (
            <button
              key={item.days}
              type="button"
              className={`text-btn ${periodDays === item.days ? 'active' : ''}`}
              style={{
                border: '1.5px solid var(--ink)',
                background: periodDays === item.days ? 'var(--ink)' : 'var(--white)',
                color: periodDays === item.days ? 'var(--sky)' : 'var(--ink)',
              }}
              onClick={() => setPeriodDays(item.days)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div style={{ padding: '60px 0', textAlign: 'center', fontSize: '18px' }}>
          {translate('thinking', lang)[0]}
        </div>
      )}

      {!loading && data && (
        <>
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">{translate('k_queries', lang)}</div>
              <div className="kpi-val">{formatNumber(data.total_queries, lang)}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">{translate('k_planned', lang, { n: '' })}</div>
              <div className="kpi-val">{formatNumber(data.planned_count, lang)}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">{translate('k_cache', lang)}</div>
              <div className="kpi-val">{formatNumber(Math.round((data.cache_hit_rate || 0) * 100), lang)}%</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">{translate('k_resp', lang)}</div>
              <div className="kpi-val">{formatNumber(Math.round(data.avg_response_ms || 0), lang)} ms</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">{translate('k_lang', lang)}</div>
              <div className="kpi-val">{formatNumber(Math.round((data.arabic_ratio || 0) * 100), lang)}%</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px', marginTop: '24px' }}>
            <div style={{ background: 'var(--white)', border: '2px solid var(--ink)', padding: '20px', borderRadius: '6px' }}>
              <h3 style={{ margin: '0 0 16px' }}>{translate('destinations', lang)}</h3>
              {data.top_destinations?.length === 0 ? (
                <p style={{ color: '#777' }}>{translate('no_data_title', lang)}</p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {data.top_destinations?.map((d, i) => (
                    <li key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #eee' }}>
                      <strong>{d.name}</strong>
                      <span>{formatNumber(d.count, lang)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div style={{ background: 'var(--white)', border: '2px solid var(--ink)', padding: '20px', borderRadius: '6px' }}>
              <h3 style={{ margin: '0 0 16px' }}>{translate('attractions', lang)}</h3>
              {data.top_attractions?.length === 0 ? (
                <p style={{ color: '#777' }}>{translate('no_data_title', lang)}</p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {data.top_attractions?.map((a, i) => (
                    <li key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #eee' }}>
                      <span>{a.name} ({a.region})</span>
                      <strong>{formatNumber(a.count, lang)}</strong>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
