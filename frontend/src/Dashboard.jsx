import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { apiUrl } from "./api";

const SEGMENTS = [
  { id: "faculty", label: "Faculty"   },
  { id: "student", label: "Students"  },
  { id: "alumni",  label: "Alumni"    },
  { id: "all",     label: "All users" },
];

function AnimatedBar({ value, max, label }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="metric-bar">
      <div className="metric-bar-label">{label}</div>
      <div className="metric-bar-track">
        <motion.div
          className="metric-bar-fill"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.65, ease: "easeOut" }}
        />
      </div>
      <div className="metric-bar-value">{value}</div>
    </div>
  );
}

const ROLE_TO_SEGMENT = { student: "student", faculty: "faculty", alumni: "alumni", all: "all" };

export function Dashboard({ withAuthHeaders, audienceRole = "faculty", meta }) {
  const [data, setData]       = useState(null);
  const [error, setError]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [segment, setSegment] = useState(ROLE_TO_SEGMENT[audienceRole] || "faculty");

  useEffect(() => {
    const s = ROLE_TO_SEGMENT[audienceRole];
    if (s) setSegment(s);
  }, [audienceRole]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(apiUrl("/api/analytics/dashboard"), { headers: withAuthHeaders() });
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

  const roleData  = data?.by_role?.[segment] || {};
  const global    = data?.global || {};
  const maxChats  = Math.max(1, ...SEGMENTS.map((r) => data?.by_role?.[r.id]?.chat_requests || 0));
  const accentColor = meta?.primary || "#b2945b";

  return (
    <div className="dashboard-card">
      <div className="dashboard-header">
        <div>
          <h1>Service Insights</h1>
          <p className="dashboard-sub">
            Live metrics by audience — auto-refreshes every 15 s.{" "}
            {data?.uptime_note || ""}
          </p>
        </div>
        <button type="button" className="btn-refresh" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Refresh now"}
        </button>
      </div>

      {/* Segment tabs */}
      <div className="segment-tabs" role="tablist" aria-label="Audience segment">
        {SEGMENTS.map((r) => (
          <button
            key={r.id}
            type="button"
            role="tab"
            aria-selected={segment === r.id}
            className={`tab${segment === r.id ? " active" : ""}`}
            style={segment === r.id ? { background: accentColor, borderColor: accentColor } : {}}
            onClick={() => setSegment(r.id)}
          >
            {r.label}
          </button>
        ))}
      </div>

      {error && <p className="dashboard-error">{error}</p>}

      <AnimatePresence mode="wait">
        {data && (
          <motion.div
            key={segment}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {/* Stat tiles */}
            <div className="dashboard-grid">
              <article className="tile">
                <h3>{SEGMENTS.find((x) => x.id === segment)?.label} stats</h3>
                <div className="tile-stats">
                  <div className="tile-stat">
                    <span className="tile-stat-label">Chat requests</span>
                    <span className="tile-stat-value">{roleData.chat_requests ?? 0}</span>
                  </div>
                  <div className="tile-stat">
                    <span className="tile-stat-label">Handoff rate</span>
                    <span className="tile-stat-value">
                      {((roleData.handoff_rate || 0) * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="tile-stat">
                    <span className="tile-stat-label">Handoffs</span>
                    <span className="tile-stat-value">{roleData.handoff_count ?? 0}</span>
                  </div>
                  <div className="tile-stat">
                    <span className="tile-stat-label">Latency p50 / p95</span>
                    <span className="tile-stat-value" style={{ fontSize: "0.95rem" }}>
                      {roleData.latency_p50_ms ?? 0} / {roleData.latency_p95_ms ?? 0} ms
                    </span>
                  </div>
                </div>
                <p className="tile-hint">Timings reflect full streamed responses for this segment.</p>
              </article>

              <article className="tile">
                <h3>Global traffic</h3>
                <div className="tile-stats">
                  <div className="tile-stat">
                    <span className="tile-stat-label">HTTP requests</span>
                    <span className="tile-stat-value">{global.http_requests ?? 0}</span>
                  </div>
                  <div className="tile-stat">
                    <span className="tile-stat-label">4xx / 5xx</span>
                    <span className="tile-stat-value" style={{ fontSize: "0.95rem" }}>
                      {global.http_4xx ?? 0} / {global.http_5xx ?? 0}
                    </span>
                  </div>
                  <div className="tile-stat">
                    <span className="tile-stat-label">Error rate</span>
                    <span className="tile-stat-value">
                      {((global.http_error_rate || 0) * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className="tile-stat">
                    <span className="tile-stat-label">API latency p50 / p95</span>
                    <span className="tile-stat-value" style={{ fontSize: "0.95rem" }}>
                      {global.latency_p50_ms ?? 0} / {global.latency_p95_ms ?? 0} ms
                    </span>
                  </div>
                </div>
              </article>
            </div>

            {/* Volume chart */}
            <div className="chart-section">
              <p className="chart-title">Chat volume by audience</p>
              {SEGMENTS.map((r) => (
                <AnimatedBar
                  key={r.id}
                  label={r.label}
                  value={data.by_role?.[r.id]?.chat_requests || 0}
                  max={maxChats}
                />
              ))}
            </div>

            {/* Handoff rate chart */}
            <div className="chart-section">
              <p className="chart-title">Handoff rate by audience</p>
              {SEGMENTS.map((r) => (
                <AnimatedBar
                  key={r.id}
                  label={r.label}
                  value={Math.round((data.by_role?.[r.id]?.handoff_rate || 0) * 100)}
                  max={100}
                />
              ))}
            </div>

            <p className="dashboard-meta">
              Generated {data.generated_at}. Role buckets reflect chat requests from
              each audience. Upgrade ingest metadata (role_access) to tune retrieval
              per cohort.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
