export const LOCATIONS = ["face", "scalp", "neck", "chest", "back", "abdomen", "upper arm", "forearm", "hand", "thigh", "lower leg", "foot", "other"];
export const IMAGE_SOURCES = [
  { value: "camera", label: "Camera" },
  { value: "gallery", label: "Gallery" },
  { value: "dataset", label: "Dataset" },
];
export const imageCode = (id: number) => `IMG-${String(id).padStart(6, "0")}`;
export function describePrediction(p: Record<string, unknown> | null | undefined): string {
  if (!p) return "Not analysed yet";
  const label = p.label_name ?? p.label ?? p.predicted_class;
  const conf = typeof p.confidence === "number" ? ` (${(p.confidence * 100).toFixed(0)}%)` : "";
  const low = p.low_confidence ? " · low confidence" : "";
  return label ? `${String(label)}${conf}${low}` : "Available";
}

