import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  FileStack,
  Search,
  ShieldCheck,
  Users,
  ClipboardList,
  Radio,
  Lock,
  History,
  MapPinned,
  ArrowRight,
  CheckCircle2,
  Menu,
  X,
  type LucideIcon,
} from "lucide-react";
import { tokens, fontImport } from "../lib/theme";
import { getToken } from "../lib/api";

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div
      className="inline-flex items-center gap-2 text-xs tracking-widest uppercase mb-4"
      style={{ fontFamily: "'IBM Plex Mono', monospace", color: tokens.moss, letterSpacing: "0.14em" }}
    >
      <span className="w-4 h-px" style={{ background: tokens.moss }} />
      {children}
    </div>
  );
}

function CitationTag({ children }: { children: ReactNode }) {
  return (
    <span
      className="inline-block px-2 py-0.5 text-xs align-middle"
      style={{
        fontFamily: "'IBM Plex Mono', monospace",
        background: tokens.amberSoft,
        color: "#7A5A1E",
        border: `1px solid ${tokens.amber}`,
      }}
    >
      {children}
    </span>
  );
}

function HeroDemo() {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      className="relative rounded-sm p-6 sm:p-8"
      style={{ background: tokens.surface, border: `1px solid ${tokens.border}` }}
    >
      <div className="flex items-center gap-2 mb-6">
        <div className="w-2 h-2 rounded-full" style={{ background: tokens.moss }} />
        <span
          className="text-xs uppercase tracking-wider"
          style={{ fontFamily: "'IBM Plex Mono', monospace", color: tokens.muted, letterSpacing: "0.1em" }}
        >
          Field query &middot; WASH Programme
        </span>
      </div>

      <p
        className="text-base sm:text-lg mb-6"
        style={{ color: tokens.ink, fontFamily: "'IBM Plex Sans', sans-serif" }}
      >
        "What's the process for registering flood-affected households before
        we distribute emergency kits?"
      </p>

      <div className="h-px w-full mb-6" style={{ background: tokens.border }} />

      <p
        className="text-sm sm:text-base leading-relaxed mb-2"
        style={{ color: tokens.inkSoft, fontFamily: "'IBM Plex Sans', sans-serif" }}
      >
        Households must be registered using the standard intake form and
        cross-checked against the community vulnerability list before any
        distribution begins.{" "}
        <span
          className="cursor-pointer underline decoration-dotted underline-offset-4"
          style={{ textDecorationColor: tokens.amber }}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        >
          Head-of-household verification is required for all registrations
        </span>
        , and a witness signature is needed where ID documents are
        unavailable.
      </p>

      <div
        className="mt-5 flex flex-wrap items-center gap-2 transition-opacity duration-200"
        style={{ opacity: hovered ? 1 : 0.85 }}
      >
        <CitationTag>SOP-WASH 4.2 &sect; 3.1, p.12</CitationTag>
        <CitationTag>Donor Guideline ECHO-2025, p.4</CitationTag>
        <span className="text-xs" style={{ color: tokens.muted, fontFamily: "'IBM Plex Mono', monospace" }}>
          98% source match
        </span>
      </div>
    </div>
  );
}

function RoleCard({
  icon: Icon,
  title,
  need,
  questions,
}: {
  icon: LucideIcon;
  title: string;
  need: string;
  questions: string[];
}) {
  return (
    <div
      className="p-6 h-full flex flex-col"
      style={{ background: tokens.surface, border: `1px solid ${tokens.border}` }}
    >
      <Icon size={22} strokeWidth={1.5} style={{ color: tokens.moss }} />
      <h3
        className="mt-4 text-lg"
        style={{ fontFamily: "'Space Grotesk', sans-serif", color: tokens.ink }}
      >
        {title}
      </h3>
      <p className="mt-2 text-sm leading-relaxed" style={{ color: tokens.muted }}>
        {need}
      </p>
      <div className="mt-4 pt-4 flex-1" style={{ borderTop: `1px solid ${tokens.border}` }}>
        <ul className="space-y-2">
          {questions.map((q) => (
            <li
              key={q}
              className="text-sm leading-snug"
              style={{ color: tokens.inkSoft, fontFamily: "'IBM Plex Mono', monospace", fontSize: "0.8rem" }}
            >
              &ldquo;{q}&rdquo;
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function TrustItem({
  icon: Icon,
  title,
  body,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
}) {
  return (
    <div className="flex gap-4">
      <div className="shrink-0 mt-0.5">
        <Icon size={18} strokeWidth={1.5} style={{ color: tokens.amber }} />
      </div>
      <div>
        <h4 className="text-sm font-medium mb-1" style={{ color: tokens.ink, fontFamily: "'Space Grotesk', sans-serif" }}>
          {title}
        </h4>
        <p className="text-sm leading-relaxed" style={{ color: tokens.muted }}>
          {body}
        </p>
      </div>
    </div>
  );
}

export default function ReliefIQLanding() {
  const [menuOpen, setMenuOpen] = useState(false);
  const isSignedIn = Boolean(getToken());
  return (
    <div style={{ background: tokens.paper, fontFamily: "'IBM Plex Sans', sans-serif" }} className="min-h-screen w-full">
      <style>{`
        ${fontImport}
        @media (prefers-reduced-motion: reduce) {
          * { transition: none !important; animation: none !important; }
        }
      `}</style>

      {/* Nav */}
      <header
        className="sticky top-0 z-10 backdrop-blur"
        style={{ background: "rgba(240,242,236,0.9)", borderBottom: `1px solid ${tokens.border}` }}
      >
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MapPinned size={20} strokeWidth={1.75} style={{ color: tokens.mossDeep }} />
            <span
              className="text-lg"
              style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, color: tokens.ink }}
            >
              ReliefIQ
            </span>
          </div>
          <nav className="hidden sm:flex items-center gap-8 text-sm" style={{ color: tokens.inkSoft }}>
            <a href="#how" className="hover:opacity-70 cursor-pointer">How it works</a>
            <a href="#roles" className="hover:opacity-70 cursor-pointer">Built for your team</a>
            <a href="#trust" className="hover:opacity-70 cursor-pointer">Security &amp; governance</a>
          </nav>
          <div className="flex items-center gap-2 sm:gap-3">
            {isSignedIn ? (
              <Link
                to="/dashboard"
                className="cursor-pointer text-sm px-3 sm:px-4 py-2 transition-colors duration-200"
                style={{ background: tokens.moss, color: "#fff" }}
              >
                Dashboard
              </Link>
            ) : (
              <>
                <Link
                  to="/signin"
                  className="hidden sm:inline-flex cursor-pointer text-sm px-3 py-2 hover:opacity-70"
                  style={{ color: tokens.inkSoft }}
                >
                  Sign in
                </Link>
                <Link
                  to="/signup"
                  className="cursor-pointer text-sm px-3 sm:px-4 py-2 transition-colors duration-200"
                  style={{ background: tokens.moss, color: "#fff" }}
                >
                  Sign up
                </Link>
              </>
            )}
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              aria-label={menuOpen ? "Close menu" : "Open menu"}
              className="sm:hidden cursor-pointer p-2 -mr-2"
              style={{ color: tokens.ink }}
            >
              {menuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
        {menuOpen && (
          <div
            className="sm:hidden px-6 py-4 flex flex-col gap-4 text-sm"
            style={{ borderTop: `1px solid ${tokens.border}`, color: tokens.inkSoft, background: tokens.paper }}
          >
            <a href="#how" onClick={() => setMenuOpen(false)} className="cursor-pointer">How it works</a>
            <a href="#roles" onClick={() => setMenuOpen(false)} className="cursor-pointer">Built for your team</a>
            <a href="#trust" onClick={() => setMenuOpen(false)} className="cursor-pointer">Security &amp; governance</a>
            {!isSignedIn && (
              <Link to="/signin" onClick={() => setMenuOpen(false)} className="cursor-pointer" style={{ color: tokens.mossDeep }}>
                Sign in
              </Link>
            )}
          </div>
        )}
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-16 pb-20 grid lg:grid-cols-2 gap-12 items-center">
        <div>
          <SectionLabel>Retrieval-grounded answers</SectionLabel>
          <h1
            className="text-4xl sm:text-5xl leading-[1.08]"
            style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, color: tokens.ink }}
          >
            The answer is in your SOPs.
            <br />
            <span style={{ color: tokens.mossDeep }}>ReliefIQ finds it in seconds.</span>
          </h1>
          <p className="mt-6 text-base sm:text-lg leading-relaxed max-w-lg" style={{ color: tokens.inkSoft }}>
            Field officers, program managers and operations teams get
            answers grounded in your organisation's own manuals, donor
            guidelines and SOPs, with every response traceable to its
            source document and page.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <button
              className="cursor-pointer inline-flex items-center gap-2 px-5 py-3 text-sm transition-transform duration-200 hover:translate-x-0.5"
              style={{ background: tokens.moss, color: "#fff" }}
            >
              Request a pilot <ArrowRight size={16} />
            </button>
            <a
              href="#how"
              className="cursor-pointer text-sm underline underline-offset-4"
              style={{ color: tokens.inkSoft, textDecorationColor: tokens.border }}
            >
              See how it works
            </a>
          </div>
          <div className="mt-10 flex items-center gap-6 text-xs" style={{ color: tokens.muted, fontFamily: "'IBM Plex Mono', monospace" }}>
            <span className="inline-flex items-center gap-1.5"><CheckCircle2 size={14} /> Runs on your approved sources only</span>
          </div>
        </div>
        <HeroDemo />
      </section>

      {/* Problem */}
      <section className="border-y" style={{ borderColor: tokens.border, background: tokens.surface }}>
        <div className="max-w-6xl mx-auto px-6 py-16 grid sm:grid-cols-3 gap-10">
          <div>
            <p className="text-4xl" style={{ fontFamily: "'Space Grotesk', sans-serif", color: tokens.mossDeep, fontWeight: 600 }}>
              200+
            </p>
            <p className="mt-2 text-sm" style={{ color: tokens.muted }}>
              pages in a single SOP manual, with the answer buried somewhere on page 140.
            </p>
          </div>
          <div>
            <p className="text-4xl" style={{ fontFamily: "'Space Grotesk', sans-serif", color: tokens.mossDeep, fontWeight: 600 }}>
              1 question
            </p>
            <p className="mt-2 text-sm" style={{ color: tokens.muted }}>
              a field officer can't afford to get wrong during an active emergency response.
            </p>
          </div>
          <div>
            <p className="text-4xl" style={{ fontFamily: "'Space Grotesk', sans-serif", color: tokens.mossDeep, fontWeight: 600 }}>
              0 guessing
            </p>
            <p className="mt-2 text-sm" style={{ color: tokens.muted }}>
              every ReliefIQ answer cites the exact document and page it came from.
            </p>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="max-w-6xl mx-auto px-6 py-20">
        <SectionLabel>How it works</SectionLabel>
        <h2 className="text-3xl mb-12 max-w-xl" style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, color: tokens.ink }}>
          Three steps between a question and a defensible answer.
        </h2>
        <div className="grid sm:grid-cols-3 gap-8">
          {[
            {
              n: "01",
              icon: FileStack,
              title: "Upload your approved sources",
              body: "SOPs, donor guidelines, response manuals and reports go in as-is. Nothing is used to train external models.",
            },
            {
              n: "02",
              icon: Search,
              title: "Ask in plain language",
              body: "Field officers ask the way they'd ask a colleague, with no keyword search and no document names required.",
            },
            {
              n: "03",
              icon: ShieldCheck,
              title: "Get a grounded, cited answer",
              body: "Every answer links back to the exact source and page, so it can be verified before it's acted on.",
            },
          ].map((step) => (
            <div key={step.n}>
              <div
                className="text-xs mb-3"
                style={{ fontFamily: "'IBM Plex Mono', monospace", color: tokens.amber }}
              >
                {step.n}
              </div>
              <step.icon size={20} strokeWidth={1.5} style={{ color: tokens.moss }} />
              <h3 className="mt-3 text-base" style={{ fontFamily: "'Space Grotesk', sans-serif", color: tokens.ink }}>
                {step.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed" style={{ color: tokens.muted }}>
                {step.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Roles */}
      <section id="roles" style={{ background: tokens.surface, borderTop: `1px solid ${tokens.border}`, borderBottom: `1px solid ${tokens.border}` }}>
        <div className="max-w-6xl mx-auto px-6 py-20">
          <SectionLabel>Built for your team</SectionLabel>
          <h2 className="text-3xl mb-12 max-w-xl" style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, color: tokens.ink }}>
            One knowledge base, four very different jobs to do.
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <RoleCard
              icon={Radio}
              title="Field officers"
              need="Need the correct procedure now, not the 200-page PDF it's buried in."
              questions={[
                "What's required before distributing emergency supplies?",
                "Safeguarding steps when working with children?",
              ]}
            />
            <RoleCard
              icon={ClipboardList}
              title="Program managers"
              need="Need to confirm compliance and reporting requirements at a glance."
              questions={[
                "Does this activity comply with donor requirements?",
                "What indicators does this donor require?",
              ]}
            />
            <RoleCard
              icon={Users}
              title="Operations & admin"
              need="Need procurement, logistics and HR policy answered without a help desk ticket."
              questions={[
                "Procurement threshold requiring approval?",
                "Travel policy for field deployments?",
              ]}
            />
            <RoleCard
              icon={History}
              title="Leadership"
              need="Need visibility into where knowledge gaps are slowing teams down."
              questions={[
                "What are staff searching for most?",
                "Where are procedures unclear?",
              ]}
            />
          </div>
        </div>
      </section>

      {/* Trust */}
      <section id="trust" className="max-w-6xl mx-auto px-6 py-20 grid lg:grid-cols-2 gap-12">
        <div>
          <SectionLabel>Security &amp; governance</SectionLabel>
          <h2 className="text-3xl mb-4" style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, color: tokens.ink }}>
            A knowledge tool, not a black box.
          </h2>
          <p className="text-base leading-relaxed max-w-md" style={{ color: tokens.muted }}>
            ReliefIQ is built to survive scrutiny from donors, auditors and
            your own knowledge management team, not just to sound
            confident.
          </p>
        </div>
        <div className="grid sm:grid-cols-2 gap-8">
          <TrustItem icon={Lock} title="Role-based access" body="Field, program and admin roles see only the documents their permissions allow." />
          <TrustItem icon={ShieldCheck} title="Grounded, not generated" body="Answers are drawn from your approved sources: never invented, always cited." />
          <TrustItem icon={History} title="Full audit trail" body="Every question, answer and source is logged for review and reporting." />
          <TrustItem icon={FileStack} title="Your data stays yours" body="Uploaded documents are never used to train external models." />
        </div>
      </section>

      {/* Final CTA */}
      <section style={{ background: tokens.mossDeep }}>
        <div className="max-w-6xl mx-auto px-6 py-16 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <h2 className="text-2xl sm:text-3xl max-w-md" style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, color: "#fff" }}>
            Put your SOPs to work before the next emergency response.
          </h2>
          <button
            className="cursor-pointer inline-flex items-center gap-2 px-6 py-3 text-sm shrink-0 transition-transform duration-200 hover:translate-x-0.5"
            style={{ background: tokens.amber, color: tokens.ink }}
          >
            Request a pilot <ArrowRight size={16} />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="max-w-6xl mx-auto px-6 py-10 flex flex-wrap items-center justify-between gap-4 text-xs" style={{ color: tokens.muted, fontFamily: "'IBM Plex Mono', monospace" }}>
        <span>ReliefIQ: grounded answers for humanitarian teams</span>
        <span>&copy; {new Date().getFullYear()}</span>
      </footer>
    </div>
  );
}
