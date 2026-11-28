import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_case_or_404, get_current_user
from app.db.session import get_db
from app.models import User
from app.services import report as rpt
from app.services.audit import log_action

log = logging.getLogger("dermai.reports")
router = APIRouter(prefix="/cases", tags=["reports"])
MEDIA = {"pdf": "application/pdf", "json": "application/json", "csv": "text/csv; charset=utf-8"}


@router.get("/{case_id}/report")
def case_report(case_id: int, request: Request, format: Literal["pdf", "json", "csv"] = "pdf", image_id: int | None = Query(None),
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """AI-assisted analysis report for a case (or one image of it). Contents follow the caller's role."""
    case = get_case_or_404(case_id, db, user)
    if image_id is not None and image_id not in {i.id for i in case.images}:
        raise HTTPException(404, "Image not found in this case.")
    data = rpt.build_report(case, user, image_id)
    try:
        body = {"pdf": lambda: rpt.to_pdf(data, case, user), "json": lambda: rpt.to_json(data), "csv": lambda: rpt.to_csv(data)}[format]()
    except ImportError:
        raise HTTPException(503, "PDF reports need the 'reportlab' package on the server. Run: pip install reportlab, then restart the API.")
    except Exception:
        log.exception("report generation failed for case %s", case_id)
        raise HTTPException(500, "The report could not be generated. The server log has the details.")
    log_action(db, "report.generate", user, f"case:{case.id}", f"format={format}", request)
    return Response(body, media_type=MEDIA[format], headers={"Content-Disposition": f'attachment; filename="DermAI-{case.case_code}.{format}"'})

