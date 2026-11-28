import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { QualityBadge } from "../components/QualityMeters";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { can, showCase, showImage } from "../lib/permissions";
import type { CaseSummary } from "../lib/types";

export default function Cases() {
  const { user } = useAuth();
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  useEffect(() => { api<CaseSummary[]>("/cases").then(setCases); }, []);
  if (!user) return null;

  const cols: { h: string; cell: (c: CaseSummary) => React.ReactNode }[] = [
    { h: "Case ID", cell: (c) => <Link className="font-semibold text-accent underline" to={`/cases/${c.id}`}>{c.case_code}</Link> },
    ...(showCase(user, "owner_name") ? [{ h: "Submitted by", cell: (c: CaseSummary) => c.owner_name ?? "—" }] : []),
    ...(showCase(user, "body_location") ? [{ h: "Body location", cell: (c: CaseSummary) => c.body_location ?? "—" }] : []),
    ...(showCase(user, "patient_age") ? [{ h: "Age", cell: (c: CaseSummary) => <span className="tabular-nums">{c.patient_age ?? "—"}</span> }] : []),
    { h: "Images", cell: (c) => <span className="tabular-nums">{c.image_count}</span> },
    ...(showImage(user, "quality_label") ? [{ h: "Latest quality", cell: (c: CaseSummary) => <QualityBadge label={c.latest_quality} /> }] : []),
    { h: "Status", cell: (c) => <span className="capitalize">{c.latest_status?.replace("_", " ") ?? "—"}</span> },
    { h: "Created", cell: (c) => <span className="tabular-nums">{c.created_at ? new Date(c.created_at).toLocaleDateString() : "—"}</span> },
  ];

  return (
    <div>
      <div className="mb-5 flex items-center justify-between"><h1 className="h-page">Cases</h1>{can(user, "create_case") && <Link to="/cases/new" className="btn-primary">New case</Link>}</div>
      {user.role === "admin" && <p className="mb-4 text-sm text-mute">Operational view for auditing and support. Clinical details and images are not shown.</p>}
      {(user.role === "researcher" || user.role === "ml_engineer") && <p className="mb-4 text-sm text-mute">De-identified cases from patients who opted in to research use.</p>}
      {cases === null ? <p className="text-mute">Loading…</p> : cases.length === 0 ? <div className="panel p-8 text-center text-mute">No cases to show.</div> : (
        <div className="panel overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line text-mute"><tr>{cols.map((c) => <th key={c.h} className="px-4 py-2 font-medium">{c.h}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {cases.map((c) => <tr key={c.id} className="hover:bg-canvas">{cols.map((col) => <td key={col.h} className="px-4 py-2">{col.cell(c)}</td>)}</tr>)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

