export type Role = "patient" | "dermatologist" | "researcher" | "ml_engineer" | "admin";
export interface User {
  id: number; email: string; full_name: string; role: Role; is_active: boolean; is_verified: boolean; created_at: string;
  age: number | null; gender: string | null; medical_history: string | null; known_allergies: string | null;
  institution: string | null; license_number: string | null; specialization: string | null;
  research_area: string | null; orcid: string | null; research_consent: boolean;
}
type N<T> = T | null | undefined;
export interface LesionInfo { found: boolean; bbox: number[] | null; area_fraction: number; contrast_ratio: number; solidity: number; lesion_count: number; hair_fraction?: number; other_boxes: number[][]; method: string }
export type RiskKey = "low" | "moderate" | "high" | "review";
export interface Risk { key: RiskKey; category: string; recommendation: string; p_malignant: number; reasons: string[]; protocol: string }
export interface Explain { method: string; target: string; attention_in_lesion?: number | null; lesion_share_of_crop?: number | null; stability?: number | null }
export interface Prediction {
  label: string; label_name: string; confidence: number; top_n: { label: string; name: string; probability: number }[];
  low_confidence: boolean; caveats: string[]; model: { version: string; arch?: string }; analysed_at: string; disclaimer: string;
  risk?: Risk | null; explain?: Explain | null; saliency?: { method: string; target: string } | null;
}
export interface Notice { key: string; level: "informational" | "low" | "medium" | "high"; title: string; message: string; case_id: number; case_code: string; image_id: number | null; created_at: string | null; read: boolean }
export interface ModelVersion {
  version: string; arch: string | null; trained_at: string | null; dataset: string | null; preprocessing: string | null; macro_f1: number | null;
  balanced_accuracy: number | null; macro_auc: number | null; ece: number | null; final_model: boolean | null; members: string[] | null;
  explainability: boolean; risk_protocol: boolean; active: boolean;
  training?: { best_epoch?: number | null; folds_sha256?: string | null; n_train?: number | null; epochs?: number | null; lr?: number | null; batch?: number | null; imbalance?: string | null; aug?: string | null; weight_decay?: number | null; seed?: number | null };
}
export interface ActiveModel {
  available: boolean; version?: string; arch?: string; trained_at?: string; dataset?: string; explainability_available?: boolean;
  members?: { arch: string; weight: number }[] | null;
  evaluation?: { macro_f1: number; balanced_accuracy: number; macro_auc_ovr: number; accuracy: number; mcc: number; ece: number; source?: string } | null;
  risk_protocol?: { protocol: string; target_sensitivity: number; high_specificity: number; t_low: number; t_high: number } | null;
}
/** Fields a role may not see arrive empty (null); see lib/permissions.ts. */
export interface ImageRec {
  id: number; case_id: number; original_filename?: N<string>; image_source?: N<string>; capture_date?: N<string>;
  body_location?: N<string>; file_format?: N<string>; file_size_bytes?: N<number>; width?: N<number>; height?: N<number>;
  quality_label?: N<"good" | "acceptable" | "poor">; blur_score?: N<number>; brightness?: N<number>; contrast?: N<number>;
  quality_issues?: N<string[]>; analysis_status?: N<string>; model_version?: N<string>;
  prediction_result?: N<Record<string, unknown>>; lesion_info?: N<LesionInfo>; created_at?: N<string>;
}
export interface HistoryItem extends ImageRec { case_code: string; owner_name?: N<string> }
export interface CaseSummary {
  id: number; case_code: string; created_at?: N<string>; owner_name?: N<string>; body_location?: N<string>;
  patient_age?: N<number>; patient_gender?: N<string>; image_count: number; latest_quality?: N<string>; latest_status?: N<string>;
}
export interface Note { id: number; case_id: number; author_id: number; author_name: string; author_role: Role; text: string; created_at: string }
export interface CaseDetail {
  id: number; case_code: string; created_at?: N<string>; owner_name?: N<string>; patient_age?: N<number>; patient_gender?: N<string>;
  medical_history?: N<string>; known_allergies?: N<string>; clinical_notes?: N<string>; body_location?: N<string>;
  images: ImageRec[]; notes: Note[];
  permissions: { edit: boolean; delete: boolean; upload: boolean; add_notes: boolean };
}
export interface PatientBrief { id: number; full_name: string; email: string; age: number | null; gender: string | null; medical_history: string | null; known_allergies: string | null }
export interface QualityCheck {
  label: "good" | "acceptable" | "poor"; blur_score: number; brightness: number; contrast: number;
  issues: string[]; width: number; height: number; acceptable_for_analysis: boolean;
}
export interface Stats { total_cases: number; total_images: number; breakdowns: Record<string, Record<string, number>> }
export interface AuditLog { id: number; user_id: number | null; action: string; resource: string | null; detail: string | null; ip_address: string | null; created_at: string }

