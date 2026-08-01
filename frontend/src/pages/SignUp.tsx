import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MapPinned, ArrowRight, Loader2 } from "lucide-react";
import { tokens, fonts, fontImport } from "../lib/theme";
import { signUp, ApiError } from "../lib/api";

export default function SignUp() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [org, setOrg] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signUp({ full_name: name, organisation: org, email, password });
      navigate("/signin", { state: { justSignedUp: true } });
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 409
            ? "An account with this email already exists."
            : err.message
          : "Couldn't reach the server. Is the backend running?"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{ background: tokens.paper, fontFamily: fonts.body }}
      className="min-h-screen w-full flex flex-col"
    >
      <style>{`
        ${fontImport}
        @media (prefers-reduced-motion: reduce) {
          * { transition: none !important; animation: none !important; }
        }
      `}</style>

      <header
        className="w-full"
        style={{ borderBottom: `1px solid ${tokens.border}` }}
      >
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center">
          <Link to="/" className="flex items-center gap-2 cursor-pointer">
            <MapPinned size={20} strokeWidth={1.75} style={{ color: tokens.mossDeep }} />
            <span
              className="text-lg"
              style={{ fontFamily: fonts.display, fontWeight: 600, color: tokens.ink }}
            >
              ReliefIQ
            </span>
          </Link>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-12 sm:px-6 sm:py-16">
        <div
          className="w-full max-w-sm p-6 sm:p-8"
          style={{ background: tokens.surface, border: `1px solid ${tokens.border}` }}
        >
          <h1
            className="text-2xl mb-2"
            style={{ fontFamily: fonts.display, fontWeight: 600, color: tokens.ink }}
          >
            Create an account
          </h1>
          <p className="text-sm mb-8" style={{ color: tokens.muted }}>
            Set up ReliefIQ for your organisation's field and program teams.
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div
                className="text-sm px-3 py-2.5"
                style={{ background: "#FBEAEA", border: "1px solid #E3B4B4", color: "#8A2C2C" }}
                role="alert"
              >
                {error}
              </div>
            )}
            <div>
              <label
                htmlFor="name"
                className="block text-xs uppercase tracking-wider mb-2"
                style={{ fontFamily: fonts.mono, color: tokens.muted, letterSpacing: "0.08em" }}
              >
                Full name
              </label>
              <input
                id="name"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2.5 text-base outline-none"
                style={{
                  background: tokens.paper,
                  border: `1px solid ${tokens.border}`,
                  color: tokens.ink,
                }}
                placeholder="Jane Wanjiru"
              />
            </div>

            <div>
              <label
                htmlFor="org"
                className="block text-xs uppercase tracking-wider mb-2"
                style={{ fontFamily: fonts.mono, color: tokens.muted, letterSpacing: "0.08em" }}
              >
                Organisation
              </label>
              <input
                id="org"
                type="text"
                required
                value={org}
                onChange={(e) => setOrg(e.target.value)}
                className="w-full px-3 py-2.5 text-base outline-none"
                style={{
                  background: tokens.paper,
                  border: `1px solid ${tokens.border}`,
                  color: tokens.ink,
                }}
                placeholder="Your NGO or agency"
              />
            </div>

            <div>
              <label
                htmlFor="email"
                className="block text-xs uppercase tracking-wider mb-2"
                style={{ fontFamily: fonts.mono, color: tokens.muted, letterSpacing: "0.08em" }}
              >
                Work email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2.5 text-base outline-none"
                style={{
                  background: tokens.paper,
                  border: `1px solid ${tokens.border}`,
                  color: tokens.ink,
                }}
                placeholder="you@organisation.org"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-xs uppercase tracking-wider mb-2"
                style={{ fontFamily: fonts.mono, color: tokens.muted, letterSpacing: "0.08em" }}
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2.5 text-base outline-none"
                style={{
                  background: tokens.paper,
                  border: `1px solid ${tokens.border}`,
                  color: tokens.ink,
                }}
                placeholder="At least 8 characters"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full cursor-pointer inline-flex items-center justify-center gap-2 px-5 py-3 text-sm mt-2 transition-transform duration-200 hover:translate-x-0.5 disabled:opacity-60 disabled:cursor-not-allowed disabled:translate-x-0"
              style={{ background: tokens.moss, color: "#fff" }}
            >
              {loading ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Creating account…
                </>
              ) : (
                <>
                  Create account <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>

          <p className="mt-8 text-sm text-center" style={{ color: tokens.muted }}>
            Already have an account?{" "}
            <Link
              to="/signin"
              className="cursor-pointer underline underline-offset-4"
              style={{ color: tokens.mossDeep, textDecorationColor: tokens.border }}
            >
              Sign in
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
