import { useCallback, useEffect, useState } from "react";
import { apiUrl } from "./api";

const ROLES = [
  { id: "faculty", label: "Faculty" },
  { id: "student", label: "Students" },
  { id: "alumni", label: "Alumni" },
  { id: "all", label: "All users" },
];

function Bar({ value, max, label }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="metric-bar">
      <div className="metric-bar-label">{label}</div>
      <div className="metric-bar-track">
        <div className="metric-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="metric-bar-value">{value}</div>
    </div>
  );
}

export function Dashboard({ withAuthHeaders }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [segment, setSegment] = useState("faculty");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(apiUrl("/api/analytics/dashboard"), {
        headers: withAuthHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e?.message || "Failed to load metrics");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [withAuthHeaders]);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const roleData = data?.by_role?.[segment] || {};
  const global = data?.global || {};
  const maxChats = Math.max(
    1,
    ...ROLES.map((r) => data?.by_role?.[r.id]?.chat_requests || 0)
  );
  const maxHandoffRate = 1;

  return (
    <section className="dashboard-card">
      <header className="dashboard-header">
        <div>
          <h1>Service insights</h1>
          <p className="dashboard-sub">
            Live metrics by audience. Refreshes every 15s. {data?.uptime_note || ""}
          </p>
        </div>
        <button type="button" className="btn-refresh" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Refresh now"}
        </button>
      </header>

      <div className="segment-tabs" role="tablist" aria-label="Audience segment">
        {ROLES.map((r) => (
          <button
            key={r.id}
            type="button"
            role="tab"
            aria-selected={segment === r.id}
            className={segment === r.id ? "tab active" : "tab"}
            onClick={() => setSegment(r.id)}
          >
            {r.label}
          </button>
        ))}
      </div>

      {error && <p className="dashboard-error">{error}</p>}

      {data && (
        <>
          <div className="dashboard-grid">
            <article className="tile">
              <h3>Segment: {ROLES.find((x) => x.id === segment)?.label}</h3>
              <dl className="tile-stats">
                <div>
                  <dt>Chat requests</dt>
                  <dd>{roleData.chat_requests ?? 0}</dd>
                </div>
                <div>
                  <dt>Handoff rate</dt>
                  <dd>{((roleData.handoff_rate || 0) * 100).toFixed(1)}%</dd>
                </div>
                <div>
                  <dt>Handoffs</dt>
                  <dd>{roleData.handoff_count ?? 0}</dd>
                </div>
                <div>
                  <dt>Chat latency p50 / p95</dt>
                  <dd>
                    {roleData.latency_p50_ms ?? 0} / {roleData.latency_p95_ms ?? 0} ms
                  </dd>
                </div>
              </dl>
              <p className="tile-hint">
                Chat timings reflect full streamed responses for this audience bucket.
              </p>
            </article>

            <article className="tile">
              <h3>Global traffic</h3>
              <dl className="tile-stats">
                <div>
                  <dt>HTTP requests</dt>
                  <dd>{global.http_requests ?? 0}</dd>
                </div>
                <div>
                  <dt>4xx / 5xx</dt>
                  <dd>
                    {global.http_4xx ?? 0} / {global.http_5xx ?? 0}
                  </dd>
                </div>
                <div>
                  <dt>HTTP error rate</dt>
                  <dd>{((global.http_error_rate || 0) * 100).toFixed(2)}%</dd>
                </div>
                <div>
                  <dt>API latency p50 / p95</dt>
                  <dd>
                    {global.latency_p50_ms ?? 0} / {global.latency_p95_ms ?? 0} ms
                  </dd>
                </div>
              </dl>
            </article>
          </div>

          <div className="chart-block">
            <h3>Chats by audience (volume)</h3>
            {ROLES.map((r) => (
              <Bar
                key={r.id}
                label={r.label}
                value={data.by_role?.[r.id]?.chat_requests || 0}
                max={maxChats}
              />
            ))}
          </div>

          <div className="chart-block">
            <h3>Handoff rate by audience</h3>
            {ROLES.map((r) => (
              <Bar
                key={r.id}
                label={r.label}
                value={Math.round((data.by_role?.[r.id]?.handoff_rate || 0) * 100)}
                max={maxHandoffRate * 100}
              />
            ))}
          </div>

          <p className="dashboard-meta">
            Generated {data.generated_at}. Faculty / Student / Alumni / All reflect configured roles on
            chat requests; upgrade ingest metadata (`role_access`) to tune retrieval per cohort.
          </p>
        </>
      )}
    </section>
  );
}
