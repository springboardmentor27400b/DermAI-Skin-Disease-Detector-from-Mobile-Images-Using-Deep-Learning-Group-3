/** Mirror of backend/app/core/permissions.py (the API is the real gatekeeper; this only drives what we draw).
 *  "image_id" is a display-only key: the id always travels with the data but is shown to some roles only. */
import type { Role, User } from "./types";

type Cap = "create_case" | "create_for_patient" | "upload_image" | "view_history" | "compare" | "add_notes" | "manage_users";

const CAPS: Record<Role, Cap[]> = {
  patient: ["create_case", "upload_image", "view_history"],
  dermatologist: ["create_case", "upload_image", "view_history", "compare", "add_notes"],
  researcher: ["view_history", "compare"],
  ml_engineer: ["view_history", "compare"],
  admin: ["view_history", "manage_users"],
};

export function can(user: User | null | undefined, cap: Cap): boolean {
  if (!user) return false;
  if (cap === "create_for_patient") return user.role === "dermatologist" && user.is_verified;
  return CAPS[user.role].includes(cap);
}

const set = (...f: string[]) => new Set(f);
const QUALITY = ["quality_label", "blur_score", "brightness", "contrast", "quality_issues"];

export const CASE_FIELDS: Record<Role, Set<string>> = {
  patient: set("case_code", "created_at", "body_location", "patient_age", "patient_gender", "medical_history", "known_allergies"),
  dermatologist: set("case_code", "created_at", "body_location", "patient_age", "patient_gender", "medical_history", "known_allergies", "clinical_notes", "owner_name"),
  researcher: set("case_code", "created_at", "body_location"),
  ml_engineer: set("case_code", "created_at"),
  admin: set("case_code", "created_at"),
};

export const IMAGE_FIELDS: Record<Role, Set<string>> = {
  patient: set("capture_date", "body_location", "analysis_status", "prediction_result", "quality_label", "quality_issues", "created_at", "lesion_info"),
  dermatologist: set("image_id", "capture_date", "body_location", "image_source", "analysis_status", "model_version", "prediction_result", "created_at", "file_format", "width", "original_filename", "lesion_info", ...QUALITY),
  researcher: set("image_id", "capture_date", "body_location", "image_source", "analysis_status", "model_version", "prediction_result", "created_at", "lesion_info", ...QUALITY),
  ml_engineer: set("image_id", "image_source", "analysis_status", "model_version", "prediction_result", "created_at", "file_format", "width", "lesion_info", ...QUALITY),
  admin: set("image_source", "analysis_status", "model_version", "created_at"),
};

export const showCase = (u: User | null | undefined, f: string) => !!u && CASE_FIELDS[u.role].has(f);
export const showImage = (u: User | null | undefined, f: string) => !!u && IMAGE_FIELDS[u.role].has(f);
export const canViewFiles = (u: User | null | undefined) => !!u && u.role !== "admin";

