import type { Role } from "./types";

export type ThemeKey = "patient" | "clinician" | "research" | "home";
export type EntryRole = "patient" | "dermatologist" | "researcher";

export const ROLE_DEFS: { key: EntryRole; label: string; short: string; noun: string; theme: ThemeKey; headline: string; blurb: string; points: string[] }[] = [
  {
    key: "patient", label: "Patient / General User", short: "Patient", noun: "patient", theme: "patient",
    headline: "Take a calm, careful look at your skin.",
    blurb: "Photograph a skin concern, see if the photo is good enough, and keep every check in one private place.",
    points: ["Take a photo or choose one from your gallery", "Get quality tips before you submit", "Keep a history to see changes over time"],
  },
  {
    key: "dermatologist", label: "Dermatologist / Clinician", short: "Clinician", noun: "clinician", theme: "clinician",
    headline: "Review cases with clarity and context.",
    blurb: "Open submitted cases, compare analyses side by side, and record clinical notes against each one.",
    points: ["Review every submitted case once verified", "Compare analyses across visits", "Add clinical notes to the case record"],
  },
  {
    key: "researcher", label: "Medical Researcher", short: "Researcher", noun: "medical researcher", theme: "research",
    headline: "De-identified image data, traceable end to end.",
    blurb: "Organise de-identified cases with image-quality, source and capture metadata for your studies.",
    points: ["Dataset, camera and gallery image sources", "Quality metrics on every image", "Prediction history and model versions"],
  },
];

export const ACCOUNT_LABEL: Record<Role, string> = {
  patient: "Patient / General User", dermatologist: "Dermatologist / Clinician", researcher: "Medical Researcher",
  ml_engineer: "Data Scientist / ML Engineer", admin: "Administrator",
};

export function themeForRole(role?: Role | null): ThemeKey {
  return role === "patient" ? "patient" : role === "researcher" ? "research" : "clinician";
}

