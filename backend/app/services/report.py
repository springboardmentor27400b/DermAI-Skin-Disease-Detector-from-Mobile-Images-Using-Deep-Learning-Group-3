"""Analysis reports (PDF / JSON / CSV). Built from the same role-shaped views the API returns, so a report never
contains a field the requesting role may not see. States clearly that the output is AI-assisted and not a diagnosis."""
import csv
import io
import json
from datetime import datetime, timezone

from app.core.permissions import IMAGE_FIELDS, can_view_files
from app.inference.classifier import DISCLAIMER
from app.models import Case, ImageRecord, User
from app.services.views import case_view

NOT_AVAILABLE = "Not available in this version"


def _summary(img: dict) -> str:
    parts = []
    q = img.get("quality_label")
    if q:
        parts.append(f"Image quality was rated {q}.")
    li = img.get("lesion_info")
    if li:
        parts.append(f"A lesion was located covering about {li['area_fraction'] * 100:.0f}% of the photo." if li.get("found") else "A lesion could not be located automatically.")
    pr = img.get("prediction_result")
    if pr:
        parts.append(f"The AI model estimates the image is most similar to {pr['label_name']} ({pr['confidence'] * 100:.0f}% confidence)"
                     + ("; confidence is low, so extra caution is advised." if pr.get("low_confidence") else "."))
        parts.append("This is not a diagnosis. A qualified clinician should evaluate any skin concern.")
    elif img.get("analysis_status") == "rejected_quality":
        parts.append("The image was rejected for quality and not analysed; please retake it.")
    elif img.get("analysis_status") == "pending":
        parts.append("No AI analysis has been run on this image yet.")
    return " ".join(parts)


def build_report(case: Case, user: User, image_id: int | None = None) -> dict:
    cv = case_view(case, user).model_dump(mode="json")
    images = [i for i in cv["images"] if image_id in (None, i["id"])]
    show_id = user.role in ("dermatologist", "researcher", "ml_engineer")      # docs/role_permissions.md: Image ID column
    out_images = []
    for i in images:
        pr = i.get("prediction_result")
        out_images.append({
            "image_id": f"IMG-{i['id']:06d}" if show_id else None,
            "capture_date": i.get("capture_date"), "recorded_at": i.get("created_at"), "body_location": i.get("body_location"),
            "image_source": i.get("image_source"), "analysis_status": i.get("analysis_status"),
            "image_quality": {"label": i.get("quality_label"), "sharpness": i.get("blur_score"), "brightness": i.get("brightness"),
                              "contrast": i.get("contrast"), "issues": i.get("quality_issues")},
            "detected_lesion": i.get("lesion_info"),
            "predicted_condition": pr["label_name"] if pr else None,
            "confidence": pr["confidence"] if pr else None,
            "top_n_predictions": pr["top_n"] if pr else None,
            "low_confidence": pr["low_confidence"] if pr else None,
            "caveats": pr["caveats"] if pr else None,
            "risk_category": ((pr or {}).get("risk") or {}).get("category") or NOT_AVAILABLE,
            "risk_recommendation": ((pr or {}).get("risk") or {}).get("recommendation"),
            "explainability_visualization": (f"{pr['explain']['method']} attention map for {pr['label_name']}" if pr and pr.get("explain") else NOT_AVAILABLE),
            "attention_in_lesion": ((pr or {}).get("explain") or {}).get("attention_in_lesion"),
            "explanation_stability": ((pr or {}).get("explain") or {}).get("stability"),
            "model_version": (pr or {}).get("model", {}).get("version") if pr and "model_version" in IMAGE_FIELDS[user.role] else None,
            "analysis_timestamp": pr["analysed_at"] if pr else None,
            "summary": _summary(i),
            "_id": i["id"],
        })
    case_fields = {k: (_ts(cv.get(k)) if k == "created_at" else cv.get(k)) for k in ("case_code", "created_at", "owner_name", "patient_age", "patient_gender", "body_location",
                                          "medical_history", "known_allergies") if cv.get(k) is not None}
    return {"report_type": "DermAI AI-assisted analysis report", "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "case": case_fields, "images": out_images, "disclaimer": DISCLAIMER}


def _ts(v):
    return str(v)[:16].replace("T", " ") + " UTC" if v else v


def public(report: dict) -> dict:
    return {**report, "images": [{k: v for k, v in i.items() if k != "_id"} for i in report["images"]]}


def to_json(report: dict) -> bytes:
    return json.dumps(public(report), indent=2, default=str).encode()


def to_csv(report: dict) -> bytes:
    rows = []
    for i in public(report)["images"]:
        q, lesion = i["image_quality"], i["detected_lesion"] or {}
        rows.append({"case_code": report["case"].get("case_code"), "image_id": i["image_id"], "capture_date": i["capture_date"],
                     "analysis_status": i["analysis_status"], "quality": q["label"], "quality_issues": "; ".join(q["issues"] or []),
                     "lesion_found": lesion.get("found"), "lesion_area_fraction": lesion.get("area_fraction"),
                     "predicted_condition": i["predicted_condition"], "confidence": i["confidence"], "low_confidence": i["low_confidence"],
                     "top_n": "; ".join(f"{t['name']} {t['probability']:.3f}" for t in (i["top_n_predictions"] or [])),
                     "risk_category": i["risk_category"], "explainability": i["explainability_visualization"], "attention_in_lesion": i["attention_in_lesion"], "explanation_stability": i["explanation_stability"], "model_version": i["model_version"], "analysis_timestamp": i["analysis_timestamp"],
                     "summary": i["summary"], "disclaimer": DISCLAIMER})
    if not rows:
        rows = [{"case_code": report["case"].get("case_code"), "disclaimer": DISCLAIMER}]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")          # BOM so Excel opens it as UTF-8


def _thumb(path: str | None, side: int = 220):
    from PIL import Image, ImageOps
    if not path:
        return None
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((side * 2, side * 2))
            b = io.BytesIO(); im.save(b, format="JPEG", quality=85); b.seek(0)
            return b
    except OSError:
        return None


def to_pdf(report: dict, case: Case, user: User) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=18, alignment=0, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=body, fontSize=8, textColor=colors.HexColor("#555555"))
    box = ParagraphStyle("box", parent=body, backColor=colors.HexColor("#FFF4D6"), borderPadding=6, spaceBefore=6, spaceAfter=8)
    esc = lambda v: str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"DermAI report {report['case'].get('case_code', '')}", author="DermAI")
    s = [Paragraph("DermAI analysis report", h1),
         Paragraph(f"Generated {_ts(report['generated_at'])}", small),
         Paragraph("<b>AI-assisted analysis for screening and research. This is not a medical diagnosis.</b> Please have any skin concern assessed by a qualified clinician.", box)]
    rows = [[k.replace("_", " ").capitalize(), esc(v)] for k, v in report["case"].items()]
    if rows:
        t = Table(rows, colWidths=[45 * mm, 120 * mm])
        t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD"))]))
        s += [Paragraph("Case", h2), t]
    recs = {r.id: r for r in case.images}
    files = can_view_files(user)
    for n, img in enumerate(report["images"], 1):
        block = [Paragraph(f"Image {n}" + (f" ({img['image_id']})" if img["image_id"] else ""), h2)]
        if files and img["_id"] in recs:
            r = recs[img["_id"]]
            cells = []
            for cap, path in (("Original", r.stored_path), ("Preprocessed", r.processed_path), ("Lesion detection", r.lesion_path), ("Attention map", r.cam_path), ("Saliency map", r.saliency_path)):
                th = _thumb(path)
                if th:
                    cells.append([RLImage(th, width=40 * mm, height=40 * mm, kind="proportional"), Paragraph(cap, small)])
            if cells:
                gt = Table([[c[0] for c in cells], [c[1] for c in cells]], colWidths=[min(56 * mm, 170 * mm / len(cells))] * len(cells))
                gt.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")])); block.append(gt)
        q = img["image_quality"]; les = img["detected_lesion"] or {}
        facts = [["Analysis status", esc(img["analysis_status"] or "-")], ["Capture date", esc(img["capture_date"] or "-")],
                 ["Body location", esc(img["body_location"] or "-")],
                 ["Image quality", esc(q["label"] or "not shown") + ("  (" + "; ".join(q["issues"]) + ")" if q["issues"] else "")],
                 ["Detected lesion", ("located, about %.0f%% of the photo%s" % (les["area_fraction"] * 100, f", {les['lesion_count']} spots" if les.get("lesion_count", 1) > 1 else "")) if les.get("found") else ("not located" if les else "-")],
                 ["Predicted condition", esc(f"{img['predicted_condition']} ({img['confidence'] * 100:.0f}% confidence)" + (", low confidence" if img["low_confidence"] else "")) if img["predicted_condition"] else "-"],
                 ["Risk category", esc(img["risk_category"]) + (" - " + esc(img["risk_recommendation"]) if img["risk_recommendation"] else "")],
                 ["Explainability", esc(img["explainability_visualization"]) + (f" ({img['attention_in_lesion'] * 100:.0f}% of the attention fell inside the detected lesion)" if img["attention_in_lesion"] is not None else "")],
                 ["Model version", esc(img["model_version"] or "-")], ["Analysis time", esc(_ts(img["analysis_timestamp"]) or "-")]]
        ft = Table([[a, Paragraph(b, body)] for a, b in facts], colWidths=[40 * mm, 125 * mm])
        ft.setStyle(TableStyle([("FONTSIZE", (0, 0), (0, -1), 9), ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD"))]))
        block += [Spacer(1, 4), ft]
        if img["top_n_predictions"]:
            tt = Table([["Top predictions", "Probability"]] + [[esc(p["name"]), f"{p['probability'] * 100:.1f}%"] for p in img["top_n_predictions"]], colWidths=[100 * mm, 30 * mm])
            tt.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF3F1")), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC"))]))
            block += [Spacer(1, 6), tt]
        if img["caveats"]:
            block += [Spacer(1, 4)] + [Paragraph("• " + esc(c), small) for c in img["caveats"]]
        block += [Spacer(1, 6), Paragraph("<b>Summary.</b> " + esc(img["summary"]), body)]
        s.extend(block)
    if not report["images"]:
        s.append(Paragraph("This case has no analysed images.", body))
    s += [Spacer(1, 10), Paragraph(esc(report["disclaimer"]), small)]
    doc.build(s)
    return buf.getvalue()

