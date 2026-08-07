import { useEffect, useState } from "react";
import { Table2, GitCompare, Loader2, PlusCircle, MinusCircle } from "lucide-react";
import { tokens, fonts } from "../lib/theme";
import {
  listDocuments,
  getSpreadsheetTables,
  compareSpreadsheets,
  ApiError,
  type DocumentResponse,
  type SpreadsheetTable,
  type SpreadsheetComparisonResponse,
} from "../lib/api";

function DataTable({ headers, rows }: { headers: string[]; rows: (string | number | null)[][] }) {
  return (
    <div className="overflow-x-auto" style={{ border: `1px solid ${tokens.border}` }}>
      <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: tokens.paper, borderBottom: `1px solid ${tokens.border}` }}>
            {headers.map((h, i) => (
              <th key={i} className="text-left px-3 py-2 text-xs" style={{ fontFamily: fonts.mono, color: tokens.muted }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ borderBottom: `1px solid ${tokens.border}` }}>
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2 whitespace-nowrap" style={{ color: tokens.ink }}>
                  {cell === null || cell === "" ? <span style={{ color: tokens.muted }}>—</span> : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SpreadsheetAnalysisPanel() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Preview
  const [previewId, setPreviewId] = useState("");
  const [previewTables, setPreviewTables] = useState<SpreadsheetTable[] | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // Compare
  const [compareId, setCompareId] = useState("");
  const [comparison, setComparison] = useState<SpreadsheetComparisonResponse | null>(null);
  const [comparing, setComparing] = useState(false);

  const isSpreadsheet = (d: DocumentResponse) => d.doc_type === "xlsx" || d.doc_type === "csv";

  useEffect(() => {
    listDocuments()
      .then((docs) => setDocuments(docs.filter((d) => isSpreadsheet(d) && d.status === "ready")))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load documents."))
      .finally(() => setLoadingDocs(false));
  }, []);

  const spreadsheetDocs = documents.filter((d) => !d.is_superseded);
  // Only spreadsheets that ARE a replacement of something have a
  // previous version to compare against — matches the backend's
  // "supersedes_id is None" rejection.
  const comparableDocs = spreadsheetDocs.filter((d) => d.supersedes_id !== null);

  async function handlePreview() {
    if (!previewId) return;
    setPreviewLoading(true);
    setError(null);
    setPreviewTables(null);
    try {
      setPreviewTables(await getSpreadsheetTables(previewId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load this spreadsheet.");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleCompare() {
    if (!compareId) return;
    setComparing(true);
    setError(null);
    setComparison(null);
    try {
      setComparison(await compareSpreadsheets(compareId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Comparison failed.");
    } finally {
      setComparing(false);
    }
  }

  return (
    <div className="space-y-10">
      {error && (
        <div
          className="text-sm px-3 py-2.5"
          style={{ background: "#FBEAEA", border: "1px solid #E3B4B4", color: "#8A2C2C" }}
          role="alert"
        >
          {error}
        </div>
      )}

      {/* --- Preview --- */}
      <div>
        <h3 className="text-sm font-medium mb-2 flex items-center gap-2" style={{ color: tokens.ink }}>
          <Table2 size={16} /> Preview a spreadsheet
        </h3>
        <div className="flex flex-wrap gap-3 mb-4">
          <select
            value={previewId}
            onChange={(e) => setPreviewId(e.target.value)}
            disabled={loadingDocs}
            className="px-3 py-2 text-sm outline-none flex-1 min-w-[240px]"
            style={{ background: tokens.surface, border: `1px solid ${tokens.border}`, color: tokens.ink }}
          >
            <option value="">{loadingDocs ? "Loading…" : "Select a spreadsheet…"}</option>
            {spreadsheetDocs.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title} (v{d.version})
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={handlePreview}
            disabled={!previewId || previewLoading}
            className="cursor-pointer inline-flex items-center gap-2 px-5 py-2.5 text-sm disabled:opacity-60 disabled:cursor-not-allowed"
            style={{ background: tokens.moss, color: "#fff" }}
          >
            {previewLoading ? <Loader2 size={16} className="animate-spin" /> : <Table2 size={16} />}
            Preview
          </button>
        </div>

        {previewTables && (
          <div className="space-y-6">
            {previewTables.length === 0 ? (
              <p className="text-sm" style={{ color: tokens.muted }}>No readable tables found.</p>
            ) : (
              previewTables.map((t) => (
                <div key={t.id}>
                  <p className="text-xs mb-2" style={{ fontFamily: fonts.mono, color: tokens.muted }}>
                    {t.sheet_name} — {t.row_count} row{t.row_count !== 1 ? "s" : ""}
                  </p>
                  <DataTable headers={t.headers} rows={t.rows.slice(0, 20)} />
                  {t.rows.length > 20 && (
                    <p className="text-xs mt-1" style={{ color: tokens.muted }}>
                      Showing first 20 of {t.rows.length} rows.
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* --- Compare --- */}
      <div>
        <h3 className="text-sm font-medium mb-2 flex items-center gap-2" style={{ color: tokens.ink }}>
          <GitCompare size={16} /> Compare against the previous version
        </h3>
        <p className="text-xs mb-3" style={{ color: tokens.muted }}>
          Only spreadsheets uploaded via "Replace" on the Documents tab have a previous version to compare against.
        </p>
        <div className="flex flex-wrap gap-3 mb-4">
          <select
            value={compareId}
            onChange={(e) => setCompareId(e.target.value)}
            disabled={loadingDocs}
            className="px-3 py-2 text-sm outline-none flex-1 min-w-[240px]"
            style={{ background: tokens.surface, border: `1px solid ${tokens.border}`, color: tokens.ink }}
          >
            <option value="">
              {loadingDocs ? "Loading…" : comparableDocs.length === 0 ? "No replaced spreadsheets yet" : "Select a spreadsheet…"}
            </option>
            {comparableDocs.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title} (v{d.version})
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleCompare}
            disabled={!compareId || comparing}
            className="cursor-pointer inline-flex items-center gap-2 px-5 py-2.5 text-sm disabled:opacity-60 disabled:cursor-not-allowed"
            style={{ background: tokens.moss, color: "#fff" }}
          >
            {comparing ? <Loader2 size={16} className="animate-spin" /> : <GitCompare size={16} />}
            Compare
          </button>
        </div>

        {comparison && (
          <div>
            <div className="p-4 mb-4" style={{ background: tokens.surface, border: `1px solid ${tokens.border}` }}>
              <p className="text-sm" style={{ color: tokens.ink }}>{comparison.summary}</p>
            </div>

            {(comparison.sheets_added.length > 0 || comparison.sheets_removed.length > 0) && (
              <div className="flex flex-wrap gap-2 mb-4">
                {comparison.sheets_added.map((s) => (
                  <span key={s} className="inline-flex items-center gap-1 text-xs px-2 py-1" style={{ fontFamily: fonts.mono, background: tokens.amberSoft, color: tokens.mossDeep, border: `1px solid ${tokens.moss}` }}>
                    <PlusCircle size={12} /> New sheet: {s}
                  </span>
                ))}
                {comparison.sheets_removed.map((s) => (
                  <span key={s} className="inline-flex items-center gap-1 text-xs px-2 py-1" style={{ fontFamily: fonts.mono, background: "#FBEAEA", color: "#8A2C2C", border: "1px solid #E3B4B4" }}>
                    <MinusCircle size={12} /> Removed sheet: {s}
                  </span>
                ))}
              </div>
            )}

            <div className="space-y-6">
              {comparison.sheet_comparisons.map((c) => (
                <div key={c.sheet_name}>
                  <p className="text-sm font-medium mb-2" style={{ color: tokens.ink }}>{c.sheet_name}</p>

                  {(c.columns_added.length > 0 || c.columns_removed.length > 0) && (
                    <div className="flex flex-wrap gap-2 mb-3">
                      {c.columns_added.map((col) => (
                        <span key={col} className="text-xs px-2 py-0.5" style={{ fontFamily: fonts.mono, background: tokens.amberSoft, color: tokens.mossDeep }}>
                          +{col}
                        </span>
                      ))}
                      {c.columns_removed.map((col) => (
                        <span key={col} className="text-xs px-2 py-0.5" style={{ fontFamily: fonts.mono, background: "#FBEAEA", color: "#8A2C2C" }}>
                          -{col}
                        </span>
                      ))}
                    </div>
                  )}

                  {c.rows_added.length === 0 && c.rows_removed.length === 0 ? (
                    <p className="text-xs" style={{ color: tokens.muted }}>No row-level changes.</p>
                  ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      {c.rows_removed.length > 0 && (
                        <div>
                          <p className="text-xs mb-1" style={{ fontFamily: fonts.mono, color: "#8A2C2C" }}>
                            Removed ({c.rows_removed.length})
                          </p>
                          <DataTable headers={c.headers} rows={c.rows_removed} />
                        </div>
                      )}
                      {c.rows_added.length > 0 && (
                        <div>
                          <p className="text-xs mb-1" style={{ fontFamily: fonts.mono, color: tokens.mossDeep }}>
                            Added ({c.rows_added.length})
                          </p>
                          <DataTable headers={c.headers} rows={c.rows_added} />
                        </div>
                      )}
                    </div>
                  )}
                  {c.truncated && (
                    <p className="text-xs mt-2" style={{ color: tokens.muted }}>
                      Showing a capped number of differences for this sheet.
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
