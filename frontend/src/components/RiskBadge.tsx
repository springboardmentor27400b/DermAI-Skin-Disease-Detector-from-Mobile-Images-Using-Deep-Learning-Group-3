import type { Risk } from "../lib/types";

const TONE: Record<Risk["key"], string> = {
  low: "bg-ok-soft text-ok", moderate: "bg-amber-soft text-amber", high: "bg-danger-soft text-danger", review: "bg-accent-soft text-accent-dark",
};

/** Screening category from the AI-assisted analysis. Worded as a risk level to act on, never as a diagnosis. */
export default function RiskBadge({ risk, large = false }: { risk: Risk; large?: boolean }) {
  return <span className={`inline-block rounded font-semibold ${TONE[risk.key]} ${large ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-xs"}`}>{risk.category}</span>;
}

