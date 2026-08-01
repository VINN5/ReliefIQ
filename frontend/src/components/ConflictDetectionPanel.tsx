import { useEffect, useState } from "react";
import { AlertTriangle, Loader2, ShieldCheck } from "lucide-react";
import { tokens, fonts } from "../lib/theme";
import { listDocuments, analyzeConflicts, ApiError, type DocumentResponse, type ConflictAnalysisResponse } from "../lib/api";

function ConfidenceBar({ confidence }: { confidence: number }) {
  const color = confidence >= 75 ? "#8A2C2C" : confidence >= 50 ? "#7A5A1E" : tokens.muted;
  return (
    <div className="flex items-center gap-2">
      <div className="w-24 h-1.5" style={{ background: tokens.border }}>
        <div style={{ width: `${confidence}%`, height: "100%", background: color }} />
      </div>
      <span className="text-xs" style={{ fontFamily: fonts.mono, color }}>
        {confidence}%
      </span>
    </div>
  );
}

export default function ConflictDetectionPanel() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ConflictAnalysisResponse | null>(null);

  useEffect(() => {
    listDocuments()
      .then((docs) => setDocuments(docs.filter((d) => !d.is_superseded && d.status === "ready")))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load documents."))
      .finally(() => setLoadingDocs(false));
  }, []);

  async function handleAnalyze() {
    if (!selectedId) return;
    setAnalyzing(true);
    setError(null);
    setResult(null);
    try {
      const analysis = await analyzeConflicts(selectedId);
      setResult(analysis);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Analysis failed. Is the backend running?");
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <div>
      <p className="text-sm mb-4" style={{ color: tokens.inkSoft }}>
        Pick a document to check for contradictory guidance elsewhere in your knowledge base —
        e.g. one policy permitting something another prohibits.
      </p>

      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          disabled={loadingDocs}
          className="px-3 py-2 text-sm outline-none flex-1 min-w-[240px]"
          style={{ background: tokens.surface, border: `1px solid ${tokens.border}`, color: tokens.ink }}
        >
          <option value="">{loadingDocs ? "Loading documents…" : "Select a document…"}</option>
          {documents.map((d) => (
            <option key={d.id} value={d.id}>
              {d.title} (v{d.version})
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={handleAnalyze}
          disabled={!selectedId || analyzing}
          className="cursor-pointer inline-flex items-center gap-2 px-5 py-2.5 text-sm disabled:opacity-60 disabled:cursor-not-allowed"
          style={{ background: tokens.moss, color: "#fff" }}
        >
          {analyzing ? <Loader2 size={16} className="animate-spin" /> : <AlertTriangle size={16} />}
          {analyzing ? "Analyzing…" : "Check for conflicts"}
        </button>
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

      {result && !error && (
        <div className="mt-2">
          <div className="p-4 mb-4" style={{ background: tokens.surface, border: `1px solid ${tokens.border}` }}>
            <p className="text-sm" style={{ color: tokens.ink }}>{result.summary}</p>
          </div>

          {result.items.length === 0 ? (
            <div className="flex items-center gap-2 text-sm py-4" style={{ color: tokens.mossDeep }}>
              <ShieldCheck size={16} /> No potential conflicts found.
            </div>
          ) : (
            <div className="space-y-4">
              {result.items.map((item, i) => (
                <div key={i} className="p-4" style={{ background: "#FFF7ED", border: "1px solid #F0C888" }}>
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <span className="inline-flex items-center gap-1.5 text-xs" style={{ fontFamily: fonts.mono, color: "#7A5A1E" }}>
                      <AlertTriangle size={12} /> Potential conflict
                    </span>
                    <ConfidenceBar confidence={item.confidence} />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
                    <div className="p-3" style={{ background: tokens.paper, border: `1px solid ${tokens.border}` }}>
                      <p className="text-xs mb-1" style={{ fontFamily: fonts.mono, color: tokens.muted }}>
                        {result.document_title}{item.target_page != null ? `, p.${item.target_page}` : ""}
                      </p>
                      <p className="text-sm" style={{ color: tokens.ink }}>{item.target_excerpt}</p>
                    </div>
                    <div className="p-3" style={{ background: tokens.paper, border: `1px solid ${tokens.border}` }}>
                      <p className="text-xs mb-1" style={{ fontFamily: fonts.mono, color: tokens.muted }}>
                        {item.other_document_title}{item.other_page != null ? `, p.${item.other_page}` : ""}
                      </p>
                      <p className="text-sm" style={{ color: tokens.ink }}>{item.other_excerpt}</p>
                    </div>
                  </div>

                  <p className="text-xs" style={{ color: tokens.inkSoft }}>{item.explanation}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
