import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { apiUrl } from "./api";

const ROLE_OPTIONS = [
  { value: "all",     label: "All roles" },
  { value: "student", label: "Student" },
  { value: "faculty", label: "Faculty" },
  { value: "staff",   label: "Staff" },
  { value: "alumni",  label: "Alumni" },
];

function StatusNote({ status }) {
  if (!status) return null;
  return (
    <motion.p
      className={`admin-status-note ${status.ok ? "ok" : "err"}`}
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
    >
      {status.ok ? "✓" : "✗"} {status.message}
    </motion.p>
  );
}

export function AdminPanel({ withAuthHeaders, accentColor }) {
  const accent = accentColor || "#b2945b";

  // ── KB stats ──────────────────────────────────────────────
  const [stats, setStats]               = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const res = await fetch(apiUrl("/api/analytics/kb-stats"), { headers: withAuthHeaders() });
      if (!res.ok) throw new Error();
      setStats(await res.json());
    } catch {
      setStats(null);
    } finally {
      setStatsLoading(false);
    }
  }, [withAuthHeaders]);

  // ── Feedback ──────────────────────────────────────────────
  const [feedback, setFeedback]               = useState([]);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  const loadFeedback = useCallback(async () => {
    setFeedbackLoading(true);
    try {
      const res = await fetch(apiUrl("/api/feedback?limit=15"), { headers: withAuthHeaders() });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setFeedback(data.items || []);
    } catch {
      setFeedback([]);
    } finally {
      setFeedbackLoading(false);
    }
  }, [withAuthHeaders]);

  useEffect(() => {
    loadStats();
    loadFeedback();
  }, [loadStats, loadFeedback]);

  // ── Crawl ─────────────────────────────────────────────────
  const [crawlUrl, setCrawlUrl]               = useState("https://support.oakland.edu");
  const [crawlMax, setCrawlMax]               = useState(50);
  const [crawlRole, setCrawlRole]             = useState("all");
  const [crawlLoading, setCrawlLoading]       = useState(false);
  const [crawlStatus, setCrawlStatus]         = useState(null);

  const handleCrawl = async (e) => {
    e.preventDefault();
    if (!crawlUrl.trim() || crawlLoading) return;
    setCrawlLoading(true);
    setCrawlStatus(null);
    try {
      const res = await fetch(apiUrl("/api/ingest"), {
        method: "POST",
        headers: withAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ urls: [crawlUrl.trim()], crawl: true, max_pages: Number(crawlMax), role_access: crawlRole }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setCrawlStatus({ ok: true, message: `Crawled ${data.ingested_urls?.length ?? 0} pages · ${data.chunks_upserted} chunks added.` });
      loadStats();
    } catch (err) {
      setCrawlStatus({ ok: false, message: err.message || "Crawl failed." });
    } finally {
      setCrawlLoading(false);
    }
  };

  // ── Single URL ────────────────────────────────────────────
  const [urlVal, setUrlVal]           = useState("");
  const [urlRole, setUrlRole]         = useState("all");
  const [urlLoading, setUrlLoading]   = useState(false);
  const [urlStatus, setUrlStatus]     = useState(null);

  const handleUrl = async (e) => {
    e.preventDefault();
    if (!urlVal.trim() || urlLoading) return;
    setUrlLoading(true);
    setUrlStatus(null);
    try {
      const res = await fetch(apiUrl("/api/ingest"), {
        method: "POST",
        headers: withAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ urls: [urlVal.trim()], crawl: false, max_pages: 1, role_access: urlRole }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setUrlStatus({ ok: true, message: `Ingested 1 URL · ${data.chunks_upserted} chunks added.` });
      setUrlVal("");
      loadStats();
    } catch (err) {
      setUrlStatus({ ok: false, message: err.message || "Ingest failed." });
    } finally {
      setUrlLoading(false);
    }
  };

  // ── File upload ───────────────────────────────────────────
  const [uploadFile, setUploadFile]       = useState(null);
  const [uploadRole, setUploadRole]       = useState("all");
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadStatus, setUploadStatus]   = useState(null);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!uploadFile || uploadLoading) return;
    setUploadLoading(true);
    setUploadStatus(null);
    try {
      const form = new FormData();
      form.append("file", uploadFile);
      form.append("role_access", uploadRole);
      const res = await fetch(apiUrl("/api/ingest/upload"), {
        method: "POST",
        headers: withAuthHeaders(),
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setUploadStatus({ ok: true, message: `"${uploadFile.name}" ingested · ${data.chunks_upserted} chunks added.` });
      setUploadFile(null);
      e.target.reset();
      loadStats();
    } catch (err) {
      setUploadStatus({ ok: false, message: err.message || "Upload failed." });
    } finally {
      setUploadLoading(false);
    }
  };

  return (
    <div className="admin-card">
      <div className="admin-top">
        <div>
          <h1 className="admin-h1">Knowledge Base Management</h1>
          <p className="admin-sub">Ingest content, monitor KB health, and review user feedback.</p>
        </div>
        <button
          type="button"
          className="btn-refresh"
          onClick={() => { loadStats(); loadFeedback(); }}
          aria-label="Refresh all panels"
        >
          Refresh all
        </button>
      </div>

      {/* ── KB Stats ── */}
      <section className="admin-section" aria-labelledby="kb-stats-heading">
        <h2 id="kb-stats-heading" className="admin-section-title">Knowledge Base Status</h2>
        {statsLoading ? (
          <p className="admin-loading" aria-live="polite">Loading…</p>
        ) : stats ? (
          <div className="admin-stats-grid">
            <motion.div
              className="admin-stat-tile primary"
              style={{ borderColor: accent }}
              initial={{ opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
            >
              <span className="admin-stat-value" style={{ color: accent }}>
                {stats.total_chunks.toLocaleString()}
              </span>
              <span className="admin-stat-label">Total chunks</span>
            </motion.div>
            {Object.entries(stats.by_role || {}).map(([role, count], i) => (
              <motion.div
                key={role}
                className="admin-stat-tile"
                initial={{ opacity: 0, scale: 0.92 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.05 }}
              >
                <span className="admin-stat-value">{Number(count).toLocaleString()}</span>
                <span className="admin-stat-label">{role} access</span>
              </motion.div>
            ))}
          </div>
        ) : (
          <p className="admin-error">Could not load KB stats — ensure the backend is running.</p>
        )}
      </section>

      {/* ── Crawl ── */}
      <section className="admin-section" aria-labelledby="crawl-heading">
        <h2 id="crawl-heading" className="admin-section-title">Crawl Knowledge Base</h2>
        <p className="admin-section-desc">
          Spider an OU-approved domain (e.g. <code>support.oakland.edu</code>) and ingest all discovered articles.
        </p>
        <form className="admin-form" onSubmit={handleCrawl}>
          <div className="admin-fields">
            <div className="admin-field">
              <label htmlFor="crawl-url">Seed URL</label>
              <input
                id="crawl-url"
                value={crawlUrl}
                onChange={(e) => setCrawlUrl(e.target.value)}
                placeholder="https://support.oakland.edu"
                required
              />
            </div>
            <div className="admin-field admin-field--sm">
              <label htmlFor="crawl-max">Max pages</label>
              <input
                id="crawl-max"
                type="number"
                min={1}
                max={750}
                value={crawlMax}
                onChange={(e) => setCrawlMax(e.target.value)}
              />
            </div>
            <div className="admin-field admin-field--sm">
              <label htmlFor="crawl-role">Role access</label>
              <select id="crawl-role" value={crawlRole} onChange={(e) => setCrawlRole(e.target.value)}>
                {ROLE_OPTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
          </div>
          <button
            type="submit"
            className="admin-action-btn"
            style={{ background: accent }}
            disabled={crawlLoading}
            aria-busy={crawlLoading}
          >
            {crawlLoading ? "Crawling…" : "Start crawl"}
          </button>
          <AnimatePresence><StatusNote status={crawlStatus} /></AnimatePresence>
        </form>
      </section>

      {/* ── Single URL ── */}
      <section className="admin-section" aria-labelledby="url-heading">
        <h2 id="url-heading" className="admin-section-title">Ingest Single URL</h2>
        <form className="admin-form" onSubmit={handleUrl}>
          <div className="admin-fields">
            <div className="admin-field">
              <label htmlFor="url-input">URL</label>
              <input
                id="url-input"
                value={urlVal}
                onChange={(e) => setUrlVal(e.target.value)}
                placeholder="https://support.oakland.edu/article/..."
                required
              />
            </div>
            <div className="admin-field admin-field--sm">
              <label htmlFor="url-role">Role access</label>
              <select id="url-role" value={urlRole} onChange={(e) => setUrlRole(e.target.value)}>
                {ROLE_OPTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
          </div>
          <button
            type="submit"
            className="admin-action-btn"
            style={{ background: accent }}
            disabled={urlLoading || !urlVal.trim()}
            aria-busy={urlLoading}
          >
            {urlLoading ? "Ingesting…" : "Ingest URL"}
          </button>
          <AnimatePresence><StatusNote status={urlStatus} /></AnimatePresence>
        </form>
      </section>

      {/* ── File Upload ── */}
      <section className="admin-section" aria-labelledby="upload-heading">
        <h2 id="upload-heading" className="admin-section-title">Upload Document (PDF / DOCX)</h2>
        <p className="admin-section-desc">Max 50 MB per file. File is processed server-side and not stored long-term.</p>
        <form className="admin-form" onSubmit={handleUpload}>
          <div className="admin-fields">
            <div className="admin-field">
              <label htmlFor="upload-file">File</label>
              <input
                id="upload-file"
                type="file"
                accept=".pdf,.docx"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
              />
            </div>
            <div className="admin-field admin-field--sm">
              <label htmlFor="upload-role">Role access</label>
              <select id="upload-role" value={uploadRole} onChange={(e) => setUploadRole(e.target.value)}>
                {ROLE_OPTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
          </div>
          <button
            type="submit"
            className="admin-action-btn"
            style={{ background: accent }}
            disabled={uploadLoading || !uploadFile}
            aria-busy={uploadLoading}
          >
            {uploadLoading ? "Uploading…" : "Upload & ingest"}
          </button>
          <AnimatePresence><StatusNote status={uploadStatus} /></AnimatePresence>
        </form>
      </section>

      {/* ── Feedback ── */}
      <section className="admin-section" aria-labelledby="feedback-heading">
        <h2 id="feedback-heading" className="admin-section-title">Recent User Feedback</h2>
        {feedbackLoading ? (
          <p className="admin-loading" aria-live="polite">Loading…</p>
        ) : feedback.length === 0 ? (
          <p className="admin-empty">No feedback recorded yet.</p>
        ) : (
          <ul className="feedback-list" aria-label="Recent feedback items">
            {feedback.map((item, i) => (
              <motion.li
                key={i}
                className={`feedback-item ${item.helpful ? "helpful" : "not-helpful"}`}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <span className="feedback-vote" aria-label={item.helpful ? "Helpful" : "Not helpful"}>
                  {item.helpful ? "👍" : "👎"}
                </span>
                <div className="feedback-body">
                  <p className="feedback-query">"{item.query}"</p>
                  <span className="feedback-meta">
                    {item.user_id} · {new Date(item.timestamp).toLocaleString()}
                  </span>
                </div>
              </motion.li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
