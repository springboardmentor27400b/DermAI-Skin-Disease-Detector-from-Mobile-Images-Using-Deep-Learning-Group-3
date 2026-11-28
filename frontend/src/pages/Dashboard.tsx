import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import ModelPerformance from "../components/ModelPerformance";
import PlatformHealth from "../components/PlatformHealth";
import { QualityBadge } from "../components/QualityMeters";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { can, showCase, showImage } from "../lib/permissions";
import type { CaseSummary, Stats } from "../lib/types";

const INTRO: Record<string, string> = {
  patient: "Your recent skin-image analysis work.",
  dermatologist: "Cases you can review, and your own.",
  researcher: "De-identified cases that patients have chosen to share for research.",
  ml_engineer: "Dataset and model overview across shared, de-identified cases.",
  admin: "Operational overview. Clinical content is not shown to administrators.",
};
const LABEL: Record<string, string> = {
  status: "Analysis status", quality: "Image quality", predicted: "Predicted condition", confidence: "Prediction confidence", risk: "Risk level (AI-assisted)", body_location: "Body location", source: "Image source", model_version: "Model version", users_by_role: "Users by role",
};
const ORDER = ["status", "quality", "predicted", "confidence", "risk", "source", "model_version", "body_location", "users_by_role"];

function Count({ label, value }: { label: string; value: number }) {
  return <div className="panel lift p-4"><div className="text-3xl font-semibold tabular-nums">{value}</div><div className="mt-1 text-sm text-mute">{label}</div></div>;
}

const CONF_ORDER = ["under 50%", "50-70%", "70-90%", "90% or more"];

function Bars({ title, data, fixedOrder }: { title: string; data: Record<string, number>; fixedOrder?: string[] }) {
  const rows = fixedOrder ? fixedOrder.filter((k) => k in data).map((k) => [k, data[k]] as [string, number]) : Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...rows.map(([, n]) => n));
  return (
    <section className="panel p-5">
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      {rows.length === 0 ? <p className="text-sm text-mute">No data yet.</p> : (
        <ul className="space-y-2">
          {rows.map(([k, n]) => (
            <li key={k} className="text-sm">
              <div className="mb-1 flex justify-between"><span className="capitalize">{k.replace(/_/g, " ")}</span><span className="tabular-nums text-mute">{n}</span></div>
              <div className="h-2 rounded-sm bg-canvas"><div className="h-full rounded-sm bg-accent" style={{ width: `${(n / max) * 100}%` }} /></div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  useEffect(() => { api<Stats>("/cases/stats").then(setStats); api<CaseSummary[]>("/cases?limit=5").then(setCases); }, []);
  if (!user) return null;
  const b = stats?.breakdowns ?? {};
  const shared = user.role === "researcher" || user.role === "ml_engineer";

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="h-page">Hello, {user.full_name.split(" ")[0]}</h1><p className="text-mute">{INTRO[user.role]}</p></div>
        {can(user, "create_case") && <Link to="/cases/new" className="btn-primary">New case</Link>}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Count label="Cases" value={stats?.total_cases ?? 0} />
        <Count label="Images" value={stats?.total_images ?? 0} />
        {showImage(user, "quality_label") && <Count label="Good or acceptable quality" value={(b.quality?.good ?? 0) + (b.quality?.acceptable ?? 0)} />}
        {showImage(user, "quality_label") && <Count label="Rejected as poor quality" value={b.quality?.poor ?? 0} />}
        {b.risk && <Count label="Needs clinical review (AI-assisted)" value={(b.risk["High Risk"] ?? 0) + (b.risk["Requires Clinical Review"] ?? 0)} />}
        {user.role === "admin" && <Count label="Registered users" value={Object.values(b.users_by_role ?? {}).reduce((x, y) => x + y, 0)} />}
      </div>

      {shared && stats && stats.total_cases === 0 && (
        <p className="panel p-5 text-sm text-mute">No cases are shared yet. Patients appear here once they choose “Share my de-identified cases for research” in their profile.</p>
      )}

      {user.role === "admin" && <PlatformHealth />}
      {user.role !== "patient" && <ModelPerformance />}

      <div className="grid gap-4 md:grid-cols-2">
        {ORDER.filter((k) => b[k]).map((k) => <Bars key={k} title={LABEL[k]} data={b[k]} fixedOrder={k === "confidence" ? CONF_ORDER : undefined} />)}
      </div>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Recent cases</h2>
        {cases.length === 0 ? (
          <div className="panel p-8 text-center text-mute">No cases yet.{can(user, "create_case") && <> <Link to="/cases/new" className="font-semibold text-accent underline">Start your first one.</Link></>}</div>
        ) : (
          <ul className="panel divide-y divide-line">
            {cases.map((c) => (
              <li key={c.id}><Link to={`/cases/${c.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-canvas">
                <span className="font-semibold tabular-nums">{c.case_code}</span>
                <span className="text-sm text-mute">{[showCase(user, "owner_name") && c.owner_name, showCase(user, "body_location") && (c.body_location ?? "Location not set"), `${c.image_count} image${c.image_count === 1 ? "" : "s"}`].filter(Boolean).join(" · ")}</span>
                <span className="ml-auto">{showImage(user, "quality_label") ? <QualityBadge label={c.latest_quality} /> : <span className="text-xs capitalize text-mute">{c.latest_status?.replace("_", " ")}</span>}</span>
              </Link></li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}