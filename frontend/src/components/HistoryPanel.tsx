import { useEffect, useState } from "react";
import { History, Loader2, AlertTriangle } from "lucide-react";
import { tokens, fonts } from "../lib/theme";
import { getQueryHistory, ApiError, type QueryHistoryItem } from "../lib/api";

const CONFIDENCE_STYLES = {
  high: { bg: tokens.amberSoft, border: tokens.moss, text: tokens.mossDeep, label: "High confidence" },
  medium: { bg: tokens.amberSoft, border: tokens.amber, text: "#7A5A1E", label: "Medium confidence" },
  low: { bg: "#FBEAEA", border: "#E3B4B4", text: "#8A2C2C", label: "Low confidence" },
};

const PROVIDER_LABELS: Record<string, string> = {
  gemini: "Gemini",
  openai: "OpenAI",
  anthropic: "Claude",
  groq: "Groq",
};

function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider.charAt(0).toUpperCase() + provider.slice(1);
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString();
}

export default function HistoryPanel() {
  const [items, setItems] = useState<QueryHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getQueryHistory()
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load history."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm" style={{ color: tokens.muted }}>
        <Loader2 size={16} className="animate-spin" /> Loading your history…
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="text-sm px-3 py-2.5"
        style={{ background: "#FBEAEA", border: "1px solid #E3B4B4", color: "#8A2C2C" }}
        role="alert"
      >
        {error}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <p className="text-sm" style={{ color: tokens.muted }}>
        You haven't asked any questions yet — questions you ask will show up here.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {items.map((item) => (
        <div key={item.id} className="p-5" style={{ background: tokens.surface, border: `1px solid ${tokens.border}` }}>
          <div className="flex items-center justify-between gap-3 mb-2">
            <p className="text-sm font-medium" style={{ color: tokens.ink }}>{item.question}</p>
            <span
              className="text-xs shrink-0"
              style={{ fontFamily: fonts.mono, color: tokens.muted }}
            >
              {formatTimestamp(item.created_at)}
            </span>
          </div>

          <p className="text-sm leading-relaxed mb-3" style={{ color: tokens.inkSoft }}>
            {item.answer}
          </p>

          {item.citations.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 mb-3">
              {item.citations.map((c) => (
                <span
                  key={c.number}
                  className="inline-flex items-center gap-1 px-2 py-0.5 text-xs"
                  style={{ fontFamily: fonts.mono, background: tokens.amberSoft, color: "#7A5A1E", border: `1px solid ${tokens.amber}` }}
                >
                  [{c.number}] {c.document_title}
                  {c.page_number != null ? `, p.${c.page_number}` : ""}
                </span>
              ))}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <span
              className="inline-block text-xs px-2 py-1"
              style={{
                fontFamily: fonts.mono,
                background: CONFIDENCE_STYLES[item.confidence].bg,
                color: CONFIDENCE_STYLES[item.confidence].text,
                border: `1px solid ${CONFIDENCE_STYLES[item.confidence].border}`,
              }}
            >
              {CONFIDENCE_STYLES[item.confidence].label}
            </span>
            {item.provider_used && (
              <span
                className="inline-flex items-center gap-1.5 text-xs px-2 py-1"
                style={{ fontFamily: fonts.mono, background: tokens.paper, color: tokens.ink, border: `1px solid ${tokens.border}` }}
              >
                via {providerLabel(item.provider_used)}
              </span>
            )}
          </div>

          {item.needs_escalation && (
            <div
              className="mt-3 p-3 flex gap-2"
              style={{ background: "#FFF7ED", border: "1px solid #F0C888" }}
            >
              <AlertTriangle size={14} style={{ color: "#7A5A1E", flexShrink: 0, marginTop: 2 }} />
              <div>
                <p className="text-xs font-medium" style={{ color: "#7A5A1E" }}>
                  This answer needed human review
                </p>
                {item.escalation_contacts.length > 0 && (
                  <p className="text-xs mt-0.5" style={{ fontFamily: fonts.mono, color: tokens.muted }}>
                    {item.escalation_contacts.join(", ")}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
