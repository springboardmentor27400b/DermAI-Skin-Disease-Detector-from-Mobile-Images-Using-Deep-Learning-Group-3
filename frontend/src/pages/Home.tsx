import { Link } from "react-router-dom";
import Disclaimer from "../components/Disclaimer";
import HeroPreview from "../components/HeroPreview";
import Icon, { Logo } from "../components/Icon";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";

const NAV = [["About", "#about"], ["How it works", "#how"], ["Conditions", "#conditions"], ["Tips", "#tips"]] as const;

const STEPS = [
  { t: "Capture", d: "Take a photo with your phone or choose one from your gallery, with built-in crop and rotate." },
  { t: "Check the image", d: "DermAI checks sharpness, lighting and contrast straight away so you can retake unclear photos." },
  { t: "Analyse & keep a case", d: "Lesion boundaries are outlined automatically and saved to a private case with top screening insights." },
  { t: "Share with a clinician", d: "Verified clinicians can review cases, compare photos over time and export PDF, JSON or CSV reports." },
];

const CONDITIONS = [
  ["Melanoma", "A serious skin cancer that starts in pigment cells. Finding it early makes a big difference."],
  ["Basal cell carcinoma", "The most common skin cancer. It usually grows slowly and rarely spreads, but it needs treatment."],
  ["Squamous cell carcinoma", "A common skin cancer that can grow quickly and spread if left untreated. Bowen's disease is an early form."],
  ["Actinic keratosis", "A rough, scaly patch caused by years of sun exposure. Some can progress to skin cancer."],
  ["Melanocytic nevus", "A common mole. Most are harmless, but any change in size, shape or colour is worth checking."],
  ["Seborrheic keratosis", "A common, harmless, waxy or \"stuck-on\" growth that becomes more frequent with age."],
] as const;

const TIPS = [
  "Use soft, natural light. Avoid flash and strong shadows.",
  "Hold the phone steady and tap to focus on the spot.",
  "Keep the spot in the centre with some surrounding skin visible.",
  "Place a ruler or coin beside it so size can be judged.",
  "Take photos from the same distance and angle each time.",
  "Turn off beauty filters and skin smoothing.",
];

const ABCDE = [
  ["A", "Asymmetry", "One half looks different from the other."],
  ["B", "Border", "Edges are ragged, notched or blurred."],
  ["C", "Colour", "Several shades, or uneven colour."],
  ["D", "Diameter", "Wider than about 6 mm (a pencil eraser)."],
  ["E", "Evolving", "Changing in size, shape, colour, or it bleeds or itches."],
] as const;

const WHO = [
  { role: "patient", t: "Patients", d: "Check photo quality, keep a private case history and prepare clear summaries for a clinician." },
  { role: "dermatologist", t: "Clinicians", d: "Review submitted cases, compare images over time, add clinical notes and export reports." },
  { role: "researcher", t: "Researchers", d: "Work with opted-in, de-identified cases, lesion overlays and image-quality metadata." },
] as const;

const TRUST = [
  ["scan", "Instant Quality Check", "Guided focus & lighting"],
  ["lock", "Private by Design", "Encrypted case history"],
  ["shieldPlus", "Clinical Triage Aid", "Insights, not a diagnosis"],
] as const;

export default function Home() {
  const { user } = useAuth();
  useTheme("home");
  const cta = user ? { to: "/dashboard", label: "Open Dashboard" } : { to: "/welcome?mode=signup", label: "Start a Skin Scan" };

  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-30 border-b border-line/80 bg-white/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-5 py-3.5">
          <Link to="/" className="flex items-center gap-2.5">
            <Logo size={36} />
            <span className="leading-tight">
              <span className="block font-display text-xl font-bold tracking-tight text-ink">
                Derm<span className="text-[#237A57]">AI</span>
              </span>
              <span className="block text-[11px] font-medium text-mute">Smart Skin Screening</span>
            </span>
          </Link>
          <nav aria-label="Site" className="mx-auto hidden gap-7 text-sm font-medium md:flex">
            <Link to="/" className="nav-link">Home</Link>
            {NAV.map(([l, h]) => <a key={h} href={h} className="nav-link">{l}</a>)}
          </nav>
          <Link to={user ? "/dashboard" : "/welcome"} className="ml-auto rounded-full border border-ink/70 px-5 py-1.5 text-sm font-medium text-ink transition hover:bg-ink hover:text-white md:ml-0">
            {user ? "Dashboard" : "Sign in"}
          </Link>
        </div>
        <nav aria-label="Sections" className="flex gap-5 overflow-x-auto px-5 pb-2.5 text-sm md:hidden">
          {NAV.map(([l, h]) => <a key={h} href={h} className="shrink-0 text-mute">{l}</a>)}
        </nav>
      </header>

      <main>
        {/* Full-bleed atmospheric hero matching mockup */}
        <section className="relative overflow-hidden border-b border-line/60 bg-gradient-to-br from-white via-[#F7FBF8] to-[#E6F3EC]">
          <div className="pointer-events-none absolute -right-24 top-1/2 h-[520px] w-[520px] -translate-y-1/2 rounded-full bg-[#CDE8DA]/45 blur-3xl" />
          <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-5 py-14 md:py-20 lg:grid-cols-[1.05fr_0.95fr] lg:py-24">
            <div>
              {/* Eyebrow badge preserved verbatim */}
              <p className="inline-flex items-center gap-2 rounded-full bg-accent-soft px-4 py-1.5 text-[11px] font-bold uppercase tracking-wider text-accent-dark">
                <Icon name="spark" size={13} />AI-assisted skin health
              </p>
              <h1 className="mt-6 font-display text-5xl font-bold leading-[1.06] tracking-tight text-[#10261E] sm:text-6xl">
                Clarity for <span className="text-[#1F6E4E]">Every Spot</span>
                <br />on Your Skin
              </h1>
              <p className="mt-6 max-w-lg text-base leading-relaxed text-mute sm:text-lg">
                Upload a clear photo in seconds. DermAI evaluates image quality and highlights visual risk signals so you can have more informed conversations with a dermatologist.
              </p>
              <div className="mt-8 flex flex-wrap gap-3.5">
                <Link
                  to={cta.to}
                  className="group inline-flex items-center gap-2.5 rounded-full bg-[#0F3629] px-7 py-3.5 text-sm font-semibold text-white transition duration-200 hover:bg-[#0B281E] hover:shadow-lg motion-safe:hover:-translate-y-0.5"
                >
                  {cta.label}
                  <Icon name="arrow" size={16} className="transition-transform group-hover:translate-x-0.5" />
                </Link>
                <a
                  href="#how"
                  className="inline-flex items-center gap-2 rounded-full border border-ink/60 bg-white/80 px-7 py-3.5 text-sm font-semibold text-ink transition duration-200 hover:border-accent hover:bg-white hover:shadow-sm motion-safe:hover:-translate-y-0.5"
                >
                  Explore How It Works
                </a>
              </div>
              <ul className="mt-11 grid max-w-xl gap-5 sm:grid-cols-3">
                {TRUST.map(([icon, title, desc]) => (
                  <li key={title} className="group flex items-start gap-2.5">
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-soft/80 text-accent transition-colors duration-200 group-hover:bg-accent group-hover:text-white">
                      <Icon name={icon} size={16} />
                    </span>
                    <span className="text-sm leading-tight">
                      <span className="block font-semibold text-ink">{title}</span>
                      <span className="text-xs text-mute">{desc}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <HeroPreview />
          </div>
        </section>

        <section id="about" className="mx-auto max-w-6xl px-5 py-20">
          <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Built for the whole care journey</h2>
          <p className="mt-3 max-w-2xl text-mute">
            DermAI is a screening and research support tool. It helps people take better skin photos, keeps them organised in cases, and gives clinicians and researchers a clear record to work from. It does not replace a medical examination.
          </p>
          <ul className="mt-8 grid gap-4 md:grid-cols-3">
            {WHO.map((w) => (
              <li key={w.role} className="lift rounded-2xl border border-line bg-white p-6">
                <h3 className="font-display text-xl font-bold">{w.t}</h3>
                <p className="mt-2 text-sm text-mute">{w.d}</p>
                <Link to={`/welcome?role=${w.role}&mode=signup`} className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-accent hover:underline">
                  Join as {w.t.toLowerCase().replace(/s$/, "")}<Icon name="arrow" size={14} />
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <section id="how" className="bg-white py-20">
          <div className="mx-auto max-w-6xl px-5">
            <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">How it works</h2>
            <ol className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map((s, i) => (
                <li key={s.t} className="lift group rounded-2xl border border-transparent bg-canvas p-6">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-sm font-bold text-white transition-transform duration-200 group-hover:scale-110">{i + 1}</span>
                  <h3 className="mt-4 font-semibold">{s.t}</h3>
                  <p className="mt-1 text-sm text-mute">{s.d}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="conditions" className="mx-auto max-w-6xl px-5 py-20">
          <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Conditions DermAI evaluates</h2>
          <p className="mt-3 max-w-2xl text-mute">
            These six categories come from PAD-UFES-20, a clinical dataset of smartphone skin photos. The descriptions are general information only. Only a clinician can diagnose a skin condition.
          </p>
          <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {CONDITIONS.map(([t, d]) => (
              <li key={t} className="lift rounded-2xl border border-line bg-white p-5">
                <h3 className="font-semibold">{t}</h3>
                <p className="mt-1 text-sm text-mute">{d}</p>
              </li>
            ))}
          </ul>
        </section>

        <section id="tips" className="bg-white py-20">
          <div className="mx-auto grid max-w-6xl gap-12 px-5 lg:grid-cols-2">
            <div>
              <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Tips for a good photo</h2>
              <ul className="mt-6 space-y-3">
                {TIPS.map((t) => (
                  <li key={t} className="group -mx-2 flex gap-3 rounded-lg px-2 py-1 text-sm transition-colors hover:bg-accent-soft/60">
                    <Icon name="check" size={18} className="mt-0.5 shrink-0 text-accent transition-transform group-hover:scale-110" />
                    {t}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">When to see a doctor</h2>
              <p className="mt-3 text-sm text-mute">See a clinician promptly about any spot that matches the ABCDE signs, or that bleeds, itches or does not heal.</p>
              <dl className="mt-5 divide-y divide-line rounded-2xl border border-line">
                {ABCDE.map(([l, t, d]) => (
                  <div key={l} className="flex gap-4 px-4 py-3 transition-colors hover:bg-accent-soft/50">
                    <dt className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent-soft font-display text-sm font-bold text-accent-dark">{l}</dt>
                    <dd className="text-sm"><span className="font-semibold">{t}.</span> <span className="text-mute">{d}</span></dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-5 py-20">
          <div className="rounded-[28px] bg-[#0F3629] px-8 py-12 text-center text-white md:py-16">
            <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Start with one clear photo.</h2>
            <p className="mx-auto mt-3 max-w-md text-white/80">Create a free account and check your image quality in seconds.</p>
            <Link to={cta.to} className="mt-7 inline-flex items-center gap-2 rounded-full bg-white px-7 py-3 text-sm font-semibold text-[#0F3629] transition duration-200 hover:bg-accent-soft hover:shadow-lg motion-safe:hover:-translate-y-0.5">
              {cta.label}
              <Icon name="arrow" size={16} />
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-line bg-white">
        <div className="mx-auto max-w-6xl px-5 py-8">
          <Disclaimer />
          <p className="mt-3 text-xs text-mute">© 2026 DermAI · Research project</p>
        </div>
      </footer>
    </div>
  );
}
