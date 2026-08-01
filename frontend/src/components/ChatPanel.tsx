import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowUp, AlertTriangle, Sparkles, User, Menu } from "lucide-react";
import { tokens, fonts } from "../lib/theme";
import {
  askQuestion,
  getConversationMessages,
  deleteConversation,
  ApiError,
  type ConversationMessage,
} from "../lib/api";
import ConversationSidebar from "./ConversationSidebar";

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

// Small round avatar — the one signature touch that distinguishes this
// from a flat form: every turn reads as "someone asked, something
// answered" the way a real chat does, not just stacked cards.
function Avatar({ kind }: { kind: "user" | "assistant" }) {
  const isUser = kind === "user";
  return (
    <div
      className="shrink-0 flex items-center justify-center"
      style={{
        width: 28,
        height: 28,
        borderRadius: "50%",
        background: isUser ? tokens.ink : tokens.moss,
        color: "#fff",
      }}
    >
      {isUser ? <User size={14} /> : <Sparkles size={14} />}
    </div>
  );
}

function QuestionBubble({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-3 mb-3 justify-end">
      <div
        className="max-w-[85%] sm:max-w-[75%] px-4 py-2.5 text-sm"
        style={{ background: tokens.ink, color: "#fff", borderRadius: "14px 14px 4px 14px" }}
      >
        {text}
      </div>
      <Avatar kind="user" />
    </div>
  );
}

function AnswerBubble({ message }: { message: ConversationMessage }) {
  return (
    <div className="flex items-start gap-3 mb-8">
      <Avatar kind="assistant" />
      <div
        className="max-w-[90%] sm:max-w-[80%] px-4 py-3.5"
        style={{ background: tokens.surface, border: `1px solid ${tokens.border}`, borderRadius: "4px 14px 14px 14px" }}
      >
        <p className="text-sm leading-relaxed mb-3" style={{ color: tokens.ink }}>
          {message.answer}
        </p>

        {message.citations.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 mb-3">
            {message.citations.map((c) => (
              <span
                key={c.number}
                className="inline-flex items-center gap-1 px-2 py-0.5 text-xs"
                style={{ fontFamily: fonts.mono, background: tokens.amberSoft, color: "#7A5A1E", border: `1px solid ${tokens.amber}`, borderRadius: 4 }}
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
              background: CONFIDENCE_STYLES[message.confidence].bg,
              color: CONFIDENCE_STYLES[message.confidence].text,
              border: `1px solid ${CONFIDENCE_STYLES[message.confidence].border}`,
              borderRadius: 4,
            }}
          >
            {CONFIDENCE_STYLES[message.confidence].label}
          </span>
          {message.provider_used && (
            <span
              className="inline-flex items-center gap-1.5 text-xs px-2 py-1"
              style={{ fontFamily: fonts.mono, background: tokens.paper, color: tokens.ink, border: `1px solid ${tokens.border}`, borderRadius: 4 }}
            >
              via {providerLabel(message.provider_used)}
            </span>
          )}
        </div>

        {message.needs_escalation && (
          <div className="mt-3 p-3 flex gap-2" style={{ background: "#FFF7ED", border: "1px solid #F0C888", borderRadius: 8 }}>
            <AlertTriangle size={14} style={{ color: "#7A5A1E", flexShrink: 0, marginTop: 2 }} />
            <div>
              <p className="text-xs font-medium" style={{ color: "#7A5A1E" }}>
                This answer needs human review
              </p>
              {message.escalation_reason && (
                <p className="text-xs mt-0.5" style={{ color: tokens.inkSoft }}>
                  {message.escalation_reason}
                </p>
              )}
              {message.escalation_contacts.length > 0 && (
                <p className="text-xs mt-0.5" style={{ fontFamily: fonts.mono, color: tokens.muted }}>
                  {message.escalation_contacts.join(", ")}
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Three-dot pulse shown in place of the answer while a request is in
// flight — reassures the person something is happening without
// stealing attention the way a big spinner would.
function TypingIndicator() {
  return (
    <div className="flex items-start gap-3 mb-8">
      <Avatar kind="assistant" />
      <div
        className="flex items-center gap-1.5 px-4 py-3.5"
        style={{ background: tokens.surface, border: `1px solid ${tokens.border}`, borderRadius: "4px 14px 14px 14px" }}
      >
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="inline-block animate-bounce"
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: tokens.muted,
              animationDelay: `${i * 0.15}s`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

export default function ChatPanel() {
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [loadingThread, setLoadingThread] = useState(false);
  const [question, setQuestion] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshSignal, setRefreshSignal] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, asking]);

  function handleNewChat() {
    setActiveConversationId(null);
    setMessages([]);
    setError(null);
    setSidebarOpen(false); // no-op on desktop, closes the mobile drawer
  }

  function handleSelectConversation(id: string) {
    setActiveConversationId(id);
    setError(null);
    setLoadingThread(true);
    setSidebarOpen(false); // no-op on desktop, closes the mobile drawer
    getConversationMessages(id)
      .then(setMessages)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load this conversation."))
      .finally(() => setLoadingThread(false));
  }

  async function handleDeleteConversation(id: string) {
    // Native confirm is intentionally simple here rather than a custom
    // modal — deleting a conversation is destructive and irreversible
    // (cascades to all its messages server-side), so a blocking,
    // impossible-to-misclick confirmation is the right trade-off over
    // a nicer-looking dismissible dialog.
    const confirmed = window.confirm(
      "Delete this conversation? This can't be undone."
    );
    if (!confirmed) return;

    try {
      await deleteConversation(id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't delete this conversation.");
      return;
    }

    // If the conversation being deleted is the one currently open,
    // reset to a fresh "new chat" state rather than leaving the thread
    // showing messages that no longer exist server-side.
    if (id === activeConversationId) {
      handleNewChat();
    }
    setRefreshSignal((n) => n + 1);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;

    setAsking(true);
    setError(null);
    setQuestion("");
    setPendingQuestion(trimmed);
    try {
      const result = await askQuestion(trimmed, {
        conversationId: activeConversationId ?? undefined,
      });

      const isFirstMessageOfNewConversation = activeConversationId === null;
      if (isFirstMessageOfNewConversation) {
        setActiveConversationId(result.conversation_id);
        setRefreshSignal((n) => n + 1);
      }

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          question: trimmed,
          answer: result.answer,
          confidence: result.confidence,
          provider_used: result.provider_used,
          citations: result.citations,
          needs_escalation: result.needs_escalation,
          escalation_reason: result.escalation_reason,
          escalation_contacts: result.escalation_contacts,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't reach the server. Is the backend running?");
      setQuestion(trimmed); // restore the question so it isn't lost on failure
    } finally {
      setAsking(false);
      setPendingQuestion(null);
    }
  }

  return (
    <div
      className="flex relative"
      style={{ height: "70vh", border: `1px solid ${tokens.border}`, borderRadius: 12, overflow: "hidden" }}
    >
      {/* Mobile-only backdrop — clicking it closes the drawer. Hidden
          entirely at md+, where the sidebar is a normal static column. */}
      {sidebarOpen && (
        <div
          className="absolute inset-0 z-20 md:hidden"
          style={{ background: "rgba(0,0,0,0.35)" }}
          onClick={() => setSidebarOpen(false)}
          aria-hidden
        />
      )}

      {/* Sidebar: an absolutely-positioned slide-out drawer on mobile
          (confined to this panel, not the whole viewport — this chat
          view is embedded inside the dashboard, not a full page), and
          a normal static column at md+ and up. Both states are plain
          Tailwind classes (no inline transform) so the md: breakpoint
          can cleanly override the mobile transform via the cascade. */}
      <div
        className={`absolute md:static inset-y-0 left-0 z-30 h-full transition-transform duration-200 md:translate-x-0 ${
          sidebarOpen ? "translate-x-0 shadow-xl" : "-translate-x-full"
        }`}
      >
        <ConversationSidebar
          activeConversationId={activeConversationId}
          onSelectConversation={handleSelectConversation}
          onNewChat={handleNewChat}
          onDeleteConversation={handleDeleteConversation}
          refreshSignal={refreshSignal}
        />
      </div>

      <div className="flex-1 flex flex-col min-w-0" style={{ background: tokens.paper }}>
        {/* Mobile-only top bar with the drawer toggle — the sidebar has
            no other visible entry point once closed on a small screen. */}
        <div
          className="md:hidden flex items-center gap-3 px-4 h-12 shrink-0"
          style={{ borderBottom: `1px solid ${tokens.border}` }}
        >
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="cursor-pointer p-1.5"
            style={{ color: tokens.inkSoft }}
            aria-label="Open conversation list"
          >
            <Menu size={20} />
          </button>
          <span className="text-sm truncate" style={{ color: tokens.muted }}>
            Chat
          </span>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
          {loadingThread && (
            <div className="flex items-center gap-2 text-sm" style={{ color: tokens.muted }}>
              Loading conversation…
            </div>
          )}

          {!loadingThread && messages.length === 0 && !asking && (
            <div className="h-full flex flex-col items-center justify-center text-center px-8">
              <div
                className="flex items-center justify-center mb-3"
                style={{ width: 40, height: 40, borderRadius: "50%", background: tokens.amberSoft, color: tokens.mossDeep }}
              >
                <Sparkles size={18} />
              </div>
              <p className="text-sm" style={{ color: tokens.muted }}>
                Ask a question below to start a new conversation.
              </p>
            </div>
          )}

          {!loadingThread &&
            messages.map((m) => (
              <div key={m.id}>
                <QuestionBubble text={m.question} />
                <AnswerBubble message={m} />
              </div>
            ))}

          {asking && pendingQuestion && <QuestionBubble text={pendingQuestion} />}
          {asking && <TypingIndicator />}
        </div>

        {error && (
          <div
            className="mx-6 mb-3 text-sm px-3 py-2.5"
            style={{ background: "#FBEAEA", border: "1px solid #E3B4B4", color: "#8A2C2C", borderRadius: 8 }}
            role="alert"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex items-center gap-2 p-4" style={{ borderTop: `1px solid ${tokens.border}` }}>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question…"
            disabled={asking}
            className="flex-1 px-4 py-2.5 text-sm outline-none transition-shadow duration-150"
            style={{
              background: tokens.surface,
              border: `1px solid ${tokens.border}`,
              color: tokens.ink,
              borderRadius: 999,
            }}
            onFocus={(e) => (e.currentTarget.style.boxShadow = `0 0 0 3px ${tokens.amberSoft}`)}
            onBlur={(e) => (e.currentTarget.style.boxShadow = "none")}
          />
          <button
            type="submit"
            disabled={asking || !question.trim()}
            className="cursor-pointer flex items-center justify-center shrink-0 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150"
            style={{ background: tokens.moss, color: "#fff", width: 40, height: 40, borderRadius: "50%" }}
            aria-label="Send question"
          >
            <ArrowUp size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
