from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, List
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .plan_engine import build_plan_model, cycle_map
from .renderer import SUBJECT_STYLE_MAP, _load_logo_data_uri

SUBJECT_ROWS = [
    {"base": "Matemáticas", "label": "Matemáticas Sesión #1", "questions": 25},
    {"base": "Lectura Crítica", "label": "Lectura Crítica Sesión #1", "questions": 41},
    {"base": "Sociales y Ciudadanas", "label": "Sociales y Ciudadanas Sesión #1", "questions": 25},
    {"base": "Ciencias Naturales", "label": "Ciencias Naturales Sesión #1", "questions": 29},
    {"base": "Sociales y Ciudadanas", "label": "Sociales y Ciudadanas Sesión #2", "questions": 25},
    {"base": "Matemáticas", "label": "Matemáticas Sesión #2", "questions": 25},
    {"base": "Ciencias Naturales", "label": "Ciencias Naturales Sesión #2", "questions": 29},
    {"base": "Inglés", "label": "Inglés Sesión #2", "questions": 55},
]

SUBJECT_ALIASES = {
    "matematicas": "Matemáticas",
    "lectura critica": "Lectura Crítica",
    "sociales y ciudadanas": "Sociales y Ciudadanas",
    "sociales": "Sociales y Ciudadanas",
    "ciencias naturales": "Ciencias Naturales",
    "naturales": "Ciencias Naturales",
    "ingles": "Inglés",
}

DEFAULT_SUBJECT_COLORS = {
    "Matemáticas": SUBJECT_STYLE_MAP["matematicas"]["color"],
    "Lectura Crítica": SUBJECT_STYLE_MAP["lectura critica"]["color"],
    "Sociales y Ciudadanas": SUBJECT_STYLE_MAP["sociales y ciudadanas"]["color"],
    "Ciencias Naturales": SUBJECT_STYLE_MAP["ciencias naturales"]["color"],
    "Inglés": SUBJECT_STYLE_MAP["ingles"]["color"],
}

DEFAULT_SUBJECT_EMOJIS = {
    "Matemáticas": SUBJECT_STYLE_MAP["matematicas"]["emoji"],
    "Lectura Crítica": SUBJECT_STYLE_MAP["lectura critica"]["emoji"],
    "Sociales y Ciudadanas": SUBJECT_STYLE_MAP["sociales y ciudadanas"]["emoji"],
    "Ciencias Naturales": SUBJECT_STYLE_MAP["ciencias naturales"]["emoji"],
    "Inglés": SUBJECT_STYLE_MAP["ingles"]["emoji"],
}


def _norm_key(text: str) -> str:
    t = (text or "").strip().lower()
    t = (
        t.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
    )
    return t


def _to_css_color(color: str) -> str:
    value = (color or "").strip()
    key = _norm_key(value)
    key = re.sub(r"[^a-z0-9# ]+", " ", key)
    key = " ".join(key.split())
    key = re.sub(r"\bcalro\b", "claro", key)
    if key.startswith("#") and len(key) == 7:
        return key

    mapping = {
        "azul": "#1D4ED8",
        "azul pastel": "#A8D8FF",
        "azul claro": "#A8D8FF",
        "celeste": "#87CEEB",
        "cian": "#06B6D4",
        "cyan": "#06B6D4",
        "turquesa": "#06B6D4",
        "verde": "#2E8B57",
        "verde pastel": "#B8F2C2",
        "verde claro": "#B8F2C2",
        "menta": "#98FFB3",
        "aguamarina": "#7FFFD4",
        "rojo": "#D62828",
        "rojo pastel": "#FFB3B3",
        "rojo claro": "#FFB3B3",
        "salmon": "#FA8072",
        "amarillo": "#D4A017",
        "amarillo pastel": "#FFF8A6",
        "dorado": "#D4A017",
        "oro": "#D4A017",
        "gold": "#D4A017",
        "naranja": "#E67E22",
        "naranja pastel": "#FFD1A6",
        "morado": "#7B2CBF",
        "purpura": "#7B2CBF",
        "violeta": "#7B2CBF",
        "morado claro": "#E6D5FF",
        "purpura claro": "#E6D5FF",
        "violeta claro": "#E6D5FF",
        "lavanda": "#E6D5FF",
        "rosado": "#E75480",
        "rosa": "#E75480",
        "rosa pastel": "#FFD6E8",
        "cafe": "#8B5A2B",
        "marron": "#8B5A2B",
        "marronw": "#8B5A2B",
        "gris": "#6B7280",
        "negro": "#111827",
        "blanco": "#F8FAFC",
    }
    return mapping.get(key, value or "#A8D8FF")


def _infer_booklets(cfg: Dict[str, Any]) -> List[str]:
    plan_type = int(cfg.get("meta", {}).get("plan_type", 0))

    if plan_type == 1:
        global_booklets = cfg.get("content", {}).get("global_booklets", [])
        names = [b.get("name") for b in global_booklets if isinstance(b, dict) and b.get("name")]
        return names

    if plan_type in (2, 3):
        subjects = cfg.get("content", {}).get("subjects", {})
        names: List[str] = []
        seen = set()
        if isinstance(subjects, dict):
            for _, booklets in subjects.items():
                if not isinstance(booklets, list):
                    continue
                for b in booklets:
                    if not isinstance(b, dict):
                        continue
                    name = b.get("name")
                    if name and name not in seen:
                        seen.add(name)
                        names.append(name)
        return names

    return []


def _booklet_color_map(cfg: Dict[str, Any], booklets: List[str]) -> Dict[str, str]:
    palette = cfg.get("style", {}).get("palette", [])
    if not palette:
        raise ValueError("style.palette no puede estar vacía")
    raw_map = cycle_map(booklets, palette)
    return {name: _to_css_color(color) for name, color in raw_map.items()}


def _with_alpha(hex_color: str, alpha: float) -> str:
    value = (hex_color or "").strip()
    if not (value.startswith("#") and len(value) == 7):
        return value
    try:
        r = int(value[1:3], 16)
        g = int(value[3:5], 16)
        b = int(value[5:7], 16)
    except ValueError:
        return value
    a = max(0.0, min(1.0, alpha))
    return f"rgba({r}, {g}, {b}, {a:.2f})"


def _infer_reached_booklets(cfg: Dict[str, Any], configured_booklets: List[str]) -> List[str]:
    model = build_plan_model(cfg)
    reached_seen = set()
    reached_in_time_order: List[str] = []
    for day in model.days:
        for block in day.blocks:
            booklet_name = block.booklet_name
            if booklet_name not in reached_seen:
                reached_seen.add(booklet_name)
                reached_in_time_order.append(booklet_name)

    if not reached_seen:
        return []

    ordered = [name for name in configured_booklets if name in reached_seen]
    if ordered:
        return ordered
    return reached_in_time_order


def _subject_cycle_order(cfg: Dict[str, Any]) -> List[str]:
    plan_type = int(cfg.get("meta", {}).get("plan_type", 0))

    if plan_type == 2:
        per_subject_base = cfg.get("intensity", {}).get("per_subject_base_q", {})
        subj_catalog = cfg.get("content", {}).get("subjects", {})
        return [s for s in per_subject_base if s in subj_catalog]

    if plan_type == 3:
        assignments = cfg.get("assignments", {}).get("subject_by_weekday", {})
        out: List[str] = []
        seen = set()
        if isinstance(assignments, dict):
            for _, subj in assignments.items():
                if not isinstance(subj, str):
                    continue
                if _norm_key(subj) == "descanso":
                    continue
                if subj not in seen:
                    seen.add(subj)
                    out.append(subj)
        return out

    # Tipo 1 usa materias fijas del cuadernillo.
    return [
        "Matemáticas",
        "Lectura Crítica",
        "Sociales y Ciudadanas",
        "Ciencias Naturales",
        "Inglés",
    ]


def _resolve_subject_color_map(_: Dict[str, Any]) -> Dict[str, str]:
    # En el plan visual las materias usan un color fijo, no rotativo por cfg.
    return dict(DEFAULT_SUBJECT_COLORS)


def _subject_rows_with_colors(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    base_color_map = _resolve_subject_color_map(cfg)
    rows: List[Dict[str, Any]] = []
    for row in SUBJECT_ROWS:
        rows.append(
            {
                **row,
                "color": base_color_map.get(row["base"], "#DCE9F7"),
                "emoji": DEFAULT_SUBJECT_EMOJIS.get(row["base"], "📘"),
            }
        )
    return rows


def render_progress_html(cfg: Dict[str, Any]) -> str:
    meta = cfg.get("meta", {})

    try:
        start = date.fromisoformat(cfg["date_range"]["start"])
        end = date.fromisoformat(cfg["date_range"]["end"])
    except Exception as exc:
        raise ValueError("Fechas inválidas: usa formato YYYY-MM-DD en date_range.start y date_range.end") from exc

    configured_booklets = _infer_booklets(cfg)
    if not configured_booklets:
        raise ValueError("No se pudieron inferir cuadernillos desde cfg para el Registro de Progreso")
    booklets = _infer_reached_booklets(cfg, configured_booklets)
    if not booklets:
        raise ValueError("No se alcanzan cuadernillos dentro del rango del plan; no hay registro para generar")

    booklet_colors = _booklet_color_map(cfg, booklets)
    rows = _subject_rows_with_colors(cfg)

    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("progress.html")
    logo_src = None
    preferred_logo = template_dir / "images" / "logo-icfes-material.jpg"
    if preferred_logo.exists() and preferred_logo.is_file():
        suffix = preferred_logo.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            import base64
            raw = preferred_logo.read_bytes()
            b64 = base64.b64encode(raw).decode("ascii")
            logo_src = f"data:image/jpeg;base64,{b64}"
    if logo_src is None:
        logo_src = _load_logo_data_uri(template_dir)
    student_name = str(meta.get("student_name", "Estudiante")).strip() or "Estudiante"

    sections = [
        {
            "booklet_name": booklet_name,
            "booklet_color": booklet_colors.get(booklet_name, "#DCE9F7"),
            "booklet_bg_color": _with_alpha(booklet_colors.get(booklet_name, "#DCE9F7"), 0.09),
            "booklet_border_color": _with_alpha(booklet_colors.get(booklet_name, "#DCE9F7"), 0.45),
            "booklet_head_bg_color": _with_alpha(booklet_colors.get(booklet_name, "#DCE9F7"), 0.22),
            "booklet_box_bg_color": _with_alpha(booklet_colors.get(booklet_name, "#DCE9F7"), 0.14),
            "booklet_box_border_color": _with_alpha(booklet_colors.get(booklet_name, "#DCE9F7"), 0.55),
            "rows": rows,
            "total": sum(r["questions"] for r in rows),
        }
        for booklet_name in booklets
    ]

    return template.render(
        meta=meta,
        logo_src=logo_src,
        student_name=student_name,
        title_label=f"Registro de Progreso ICFES 2026 - {student_name}",
        period_label=f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}",
        sections=sections,
    )
