from __future__ import annotations

import re
import unicodedata

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Any, Dict

from .pdf_service import html_to_pdf_bytes
from .plan_engine import build_plan_model, plan_model_to_dict, validate_config
from .progress_renderer import render_progress_html
from .progress_service import generate_progress_pdf_bytes
from .renderer import render_plan_html
from .row_parser import RowParseError, build_cfg_from_row
from .sample_cfgs import sample_cfg


class PlanRequest(BaseModel):
    cfg: Dict[str, Any] = Field(..., description="Configuración completa del plan")


class FromRowRequest(BaseModel):
    plan_type: int = Field(..., description="Tipo de plan (1|2|3)")
    row_text: str = Field(..., description="Fila pegada desde Google Sheets (tab-separated)")


app = FastAPI(title="Preicfes Plan API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


def _safe_filename_part(value: str, fallback: str = "Estudiante") -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9 _.-]+", "", normalized).strip()
    return cleaned or fallback


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/plan/sample/{plan_type}")
def get_sample(plan_type: int) -> Dict[str, Any]:
    if plan_type not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="plan_type debe ser 1, 2 o 3")
    return {"cfg": sample_cfg(plan_type)}


@app.post("/api/plan/preview")
def preview_plan(req: PlanRequest) -> Dict[str, Any]:
    try:
        validate_config(req.cfg)
        model = build_plan_model(req.cfg)
        html = render_plan_html(req.cfg, model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "plan_model": plan_model_to_dict(model),
        "html": html,
    }


@app.post("/api/plan/from_row")
def from_row(req: FromRowRequest) -> Dict[str, Any]:
    if req.plan_type not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="plan_type debe ser 1, 2 o 3")
    try:
        cfg = build_cfg_from_row(req.plan_type, req.row_text)
    except RowParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"cfg": cfg}


@app.post("/api/plan/pdf")
async def generate_pdf(req: PlanRequest) -> Response:
    try:
        validate_config(req.cfg)
        model = build_plan_model(req.cfg)
        html = render_plan_html(req.cfg, model)
        plan_type = int(req.cfg.get("meta", {}).get("plan_type", 0))
        pdf_bytes = await html_to_pdf_bytes(html, landscape=(plan_type != 2))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    raw_student_name = str(req.cfg.get("meta", {}).get("student_name", "Estudiante")).strip()
    student_name = _safe_filename_part(raw_student_name)
    filename = f"Plan de Estudio ICFES {student_name}.pdf"

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@app.post("/api/plan/progress/pdf")
async def generate_progress_pdf(req: PlanRequest) -> Response:
    try:
        validate_config(req.cfg)
        pdf_bytes = await generate_progress_pdf_bytes(req.cfg)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    raw_student_name = str(req.cfg.get("meta", {}).get("student_name", "Estudiante")).strip()
    student_name = _safe_filename_part(raw_student_name)
    filename = f"Registro de Progreso ICFES {student_name}.pdf"

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@app.post("/api/plan/progress/preview")
def preview_progress(req: PlanRequest) -> Dict[str, Any]:
    try:
        validate_config(req.cfg)
        html = render_progress_html(req.cfg)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"html": html}
