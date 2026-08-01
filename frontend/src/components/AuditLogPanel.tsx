import { useEffect, useState } from "react";
import { ShieldAlert, Loader2, ChevronLeft, ChevronRight } from "lucide-react";
import { tokens, fonts } from "../lib/theme";
import { getAuditLogs, getAuditLogActions, ApiError, type AuditLogEntry } from "../lib/api";

const PAGE_SIZE = 50;

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString();
}

// Rough visual grouping so a scan of the table reads faster — failed
// sign-ins and provider outages stand out in red, everything else
// stays neutral. Not exhaustive; unmatched actions just render plain.
function actionColor(action: string): string {
  if (action.includes("failed") || action.includes("outage")) return "#8A2C2C";
  if (action.includes("signin_success") || action.includes("uploaded")) return tokens.mossDeep;
  return tokens.ink;
}

export default function AuditLogPanel() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [actionFilter, setActionFilter] = useState("");
  const [emailFilter, setEmailFilter] = useState("");
  const [availableActions, setAvailableActions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAuditLogActions()
      .then(setAvailableActions)
      .catch(() => {
        /* non-critical — filter dropdown just stays empty if this fails */
      });
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getAuditLogs({
      limit: PAGE_SIZE,
      offset,
      action: actionFilter || undefined,
      userEmail: emailFilter || undefined,
    })
      .then((page) => {
        setEntries(page.items);
        setTotal(page.total);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load audit logs."))
      .finally(() => setLoading(false));
  }, [offset, actionFilter, emailFilter]);

  function handleFilterChange(setter: (v: string) => void, value: string) {
    setter(value);
    setOffset(0); // any filter change resets to the first page
  }

  const canGoPrev = offset > 0;
  const canGoNext = offset + PAGE_SIZE < total;

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <ShieldAlert size={16} style={{ color: tokens.moss }} />
        <p className="text-sm" style={{ color: tokens.inkSoft }}>
          Every sign-in, upload, query, and gap-detection run across the organisation.
        </p>
      </div>

      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={actionFilter}
          onChange={(e) => handleFilterChange(setActionFilter, e.target.value)}
          className="px-3 py-2 text-sm outline-none"
          style={{ background: tokens.surface, border: `1px solid ${tokens.border}`, color: tokens.ink, fontFamily: fonts.mono }}
        >
          <option value="">All actions</option>
          {availableActions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>

        <input
          type="text"
          value={emailFilter}
          onChange={(e) => handleFilterChange(setEmailFilter, e.target.value)}
          placeholder="Filter by user email…"
          className="px-3 py-2 text-sm outline-none flex-1 min-w-[200px]"
          style={{ background: tokens.surface, border: `1px solid ${tokens.border}`, color: tokens.ink }}
        />
      </div>

      {error && (
        <div
          className="text-sm px-3 py-2.5 mb-4"
          style={{ background: "#FBEAEA", border: "1px solid #E3B4B4", color: "#8A2C2C" }}
          role="alert"
        >
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-sm py-6" style={{ color: tokens.muted }}>
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      ) : entries.length === 0 ? (
        <p className="text-sm py-6" style={{ color: tokens.muted }}>
          No audit log entries match these filters.
        </p>
      ) : (
        <div className="overflow-x-auto" style={{ border: `1px solid ${tokens.border}` }}>
          <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${tokens.border}`, background: tokens.paper }}>
                {["Time", "Action", "User", "Detail", "IP"].map((h) => (
                  <th
                    key={h}
                    className="text-left px-3 py-2 text-xs uppercase tracking-wider"
                    style={{ fontFamily: fonts.mono, color: tokens.muted, letterSpacing: "0.06em" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} style={{ borderBottom: `1px solid ${tokens.border}` }}>
                  <td className="px-3 py-2 whitespace-nowrap" style={{ fontFamily: fonts.mono, color: tokens.muted }}>
                    {formatTimestamp(e.created_at)}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap" style={{ fontFamily: fonts.mono, color: actionColor(e.action) }}>
                    {e.action}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap" style={{ color: tokens.ink }}>
                    {e.user_email ?? <span style={{ color: tokens.muted }}>—</span>}
                  </td>
                  <td className="px-3 py-2 max-w-md truncate" style={{ color: tokens.inkSoft }} title={e.detail ?? ""}>
                    {e.detail ?? "—"}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap" style={{ fontFamily: fonts.mono, color: tokens.muted }}>
                    {e.ip_address ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between mt-4">
        <p className="text-xs" style={{ color: tokens.muted }}>
          {total > 0 ? `Showing ${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} of ${total}` : ""}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!canGoPrev}
            onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
            className="cursor-pointer inline-flex items-center gap-1 px-3 py-1.5 text-sm disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ border: `1px solid ${tokens.border}`, color: tokens.inkSoft }}
          >
            <ChevronLeft size={14} /> Prev
          </button>
          <button
            type="button"
            disabled={!canGoNext}
            onClick={() => setOffset((o) => o + PAGE_SIZE)}
            className="cursor-pointer inline-flex items-center gap-1 px-3 py-1.5 text-sm disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ border: `1px solid ${tokens.border}`, color: tokens.inkSoft }}
          >
            Next <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
