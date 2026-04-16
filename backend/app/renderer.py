from __future__ import annotations

import base64
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List
import math
import re
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .plan_engine import DAYS_ES, PlanModel, iter_weeks_monday_to_sunday


def _format_day(d: date) -> str:
    return d.strftime("%d/%m/%Y")


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


def _booklet_order(cfg: Dict[str, Any], model: PlanModel) -> List[str]:
    plan_type = int(cfg["meta"]["plan_type"])
    if plan_type == 1:
        return [b["name"] for b in cfg.get("content", {}).get("global_booklets", [])]

    out: List[str] = []
    seen = set()
    subjects = cfg.get("content", {}).get("subjects", {})
    for _, booklets in subjects.items():
        for b in booklets:
            name = b.get("name")
            if name and name not in seen:
                seen.add(name)
                out.append(name)

    if out:
        return out

    for day in model.days:
        for b in day.blocks:
            if b.booklet_name not in seen:
                seen.add(b.booklet_name)
                out.append(b.booklet_name)
    return out


def _booklets_reached_order(model: PlanModel, fallback_order: List[str]) -> List[str]:
    reached_seen = set()
    reached_in_time_order: List[str] = []
    for day in model.days:
        for b in day.blocks:
            if b.booklet_name not in reached_seen:
                reached_seen.add(b.booklet_name)
                reached_in_time_order.append(b.booklet_name)

    if not reached_in_time_order:
        return []

    # Mantiene el orden oficial de cuadernillos, filtrando solo los alcanzados.
    if fallback_order:
        ordered = [name for name in fallback_order if name in reached_seen]
        if ordered:
            return ordered

    return reached_in_time_order


def _booklet_color_map(cfg: Dict[str, Any], model: PlanModel) -> Dict[str, str]:
    booklet_names = _booklet_order(cfg, model)
    palette = cfg.get("style", {}).get("palette", []) or ["#A8D8FF"]
    return {name: palette[i % len(palette)] for i, name in enumerate(booklet_names)}


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


def _legend_text_color(booklet_color: str) -> str:
    value = (booklet_color or "").strip().lower()
    if value in {"#ffffff", "#fff", "#f8fafc"}:
        return "#111827"
    return booklet_color


SUBJECT_STYLE_MAP = {
    "matematicas": {"label": "Matemáticas", "emoji": "🧮", "color": "#D62828"},
    "lectura critica": {"label": "Lectura Crítica", "emoji": "📖", "color": "#7B2CBF"},
    "sociales y ciudadanas": {"label": "Sociales y Ciudadanas", "emoji": "🌎", "color": "#E67E22"},
    "ciencias naturales": {"label": "Ciencias Naturales", "emoji": "🌿", "color": "#2E8B57"},
    "ingles": {"label": "Inglés", "emoji": "🇺🇸", "color": "#D4A017"},
}


def _subject_style(subject: str) -> Dict[str, str]:
    key = _norm_key(subject)
    return SUBJECT_STYLE_MAP.get(
        key,
        {
            "label": subject,
            "emoji": "📘",
            "color": "#1D3557",
        },
    )


def _session_for_block(subject: str, start_q: int) -> int:
    s = _norm_key(subject)
    if s == "lectura critica":
        return 1
    if s == "ingles":
        return 2
    if s == "matematicas":
        return 1 if start_q <= 25 else 2
    if s == "sociales y ciudadanas":
        return 1 if start_q >= 67 else 2
    if s == "ciencias naturales":
        return 1 if start_q >= 92 else 2
    return 1


def _load_logo_data_uri(template_dir: Path) -> str | None:
    images_dir = template_dir / "images"
    candidates = [
        images_dir / "logo-icfes-material.png",
        images_dir / "logo-icfes-material.jpg",
        images_dir / "logo-icfes-material.jpeg",
        images_dir / "logo-icfes-material.webp",
        images_dir / "logo-icfes-material.svg",
    ]
    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".svg":
            svg_text = path.read_text(encoding="utf-8")
            return f"data:image/svg+xml;utf8,{quote(svg_text)}"
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix)
        if not mime:
            continue
        raw = path.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{b64}"
    return None


def _daily_questions_text(cfg: Dict[str, Any]) -> str:
    plan_type = int(cfg.get("meta", {}).get("plan_type", 0))
    intensity = cfg.get("intensity", {})
    if plan_type == 2:
        per_subject_base = intensity.get("per_subject_base_q", {})
        if isinstance(per_subject_base, dict) and per_subject_base:
            ordered_subjects = [
                "Matemáticas",
                "Lectura Crítica",
                "Sociales y Ciudadanas",
                "Ciencias Naturales",
                "Inglés",
            ]
            items = [f"{s}: {per_subject_base[s]}" for s in ordered_subjects if s in per_subject_base]
            # Si llegan materias adicionales, las agrega al final.
            for s, q in per_subject_base.items():
                if s not in ordered_subjects:
                    items.append(f"{s}: {q}")
            return "Por materia - " + ", ".join(items)
    mode = intensity.get("mode")
    if mode == "fixed":
        return str(intensity.get("fixed_q", "-"))
    if mode == "by_weekday":
        by_wd = intensity.get("by_weekday_q", {})
        values = []
        for wd in range(7):
            v = by_wd.get(str(wd))
            if v is not None:
                values.append(f"{DAYS_ES[wd].capitalize()}: {v}")
        return ", ".join(values) if values else "Variable por día"
    return "Variable"


def _plan_type_info(cfg: Dict[str, Any]) -> Dict[str, str]:
    plan_type = int(cfg.get("meta", {}).get("plan_type", 0))
    if plan_type == 1:
        return {
            "code": "A",
            "name": "Lineal",
            "description": "Sigues el orden normal de los cuadernillos y avanzas de forma lineal y continua.",
            "ideal": "Ideal si quieres un camino simple.",
        }
    if plan_type == 2:
        return {
            "code": "B",
            "name": "Por Materias",
            "description": "Trabajas todas las materias y cada una avanza de forma independiente.",
            "ideal": "Ideal si quieres practicar todas las materias cada día.",
        }
    return {
        "code": "C",
        "name": "Monomateria",
        "description": "Trabajas una sola materia por día sin mezclar materias en el mismo día.",
        "ideal": "Ideal si prefieres enfoque total por sesión.",
    }


def _active_days_text(cfg: Dict[str, Any]) -> str:
    plan_type = int(cfg.get("meta", {}).get("plan_type", 0))
    if plan_type == 3:
        assignments = cfg.get("assignments", {}).get("subject_by_weekday", {})
        if isinstance(assignments, dict) and assignments:
            parts: List[str] = []
            for wd in range(7):
                subj = assignments.get(str(wd))
                if not isinstance(subj, str) or not subj.strip():
                    continue
                parts.append(f"{DAYS_ES[wd].capitalize()}: {subj.strip()}")
            if parts:
                return ", ".join(parts)

    if plan_type == 2:
        mult_map = cfg.get("intensity", {}).get("multiplier_by_weekday", {})
        if isinstance(mult_map, dict) and mult_map:
            parts: List[str] = []
            for wd in range(7):
                mult = mult_map.get(str(wd))
                if mult is None:
                    continue
                try:
                    mult_num = float(mult)
                    mult_text = f"{mult_num:g}"
                except (TypeError, ValueError):
                    mult_text = str(mult)
                parts.append(f"{DAYS_ES[wd].capitalize()} x{mult_text}")
            if parts:
                return ", ".join(parts)

    active_weekdays = cfg.get("calendar_rules", {}).get("active_weekdays", [])
    active_days_labels = ", ".join([DAYS_ES[int(i)].capitalize() for i in active_weekdays if 0 <= int(i) <= 6])
    return active_days_labels or "No definido"


def _subjects_to_reinforce(cfg: Dict[str, Any]) -> tuple[str, bool]:
    focus_subjects = cfg.get("extras", {}).get("focus_subjects", [])
    if isinstance(focus_subjects, list) and focus_subjects:
        normalized_focus = []
        for item in focus_subjects:
            if not isinstance(item, str):
                continue
            key = _norm_key(item)
            key_plain = "".join(ch for ch in key if ch.isalnum() or ch.isspace()).strip()
            if key_plain in {"ninguna", "ninguno", "no"}:
                return "Decidiste darle la misma intensidad a todas 😊", True
            normalized_focus.append(item.strip())
        if normalized_focus:
            return ", ".join(normalized_focus), False

    plan_type = int(cfg.get("meta", {}).get("plan_type", 0))
    if plan_type == 2:
        per_subject_base = cfg.get("intensity", {}).get("per_subject_base_q", {})
        items = [s for s, q in per_subject_base.items() if int(q) > 0]
        value = ", ".join(items) if items else "General"
        return value, False
    if plan_type == 3:
        assignments = cfg.get("assignments", {}).get("subject_by_weekday", {})
        seen = set()
        out: List[str] = []
        for _, subj in assignments.items():
            if not isinstance(subj, str):
                continue
            if _norm_key(subj) == "descanso":
                continue
            if subj not in seen:
                seen.add(subj)
                out.append(subj)
        value = ", ".join(out) if out else "General"
        return value, False
    subjects = list(cfg.get("content", {}).get("subjects", {}).keys())
    value = ", ".join(subjects) if subjects else "General"
    return value, False


def render_plan_html(cfg: Dict[str, Any], model: PlanModel) -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("plan.html")
    logo_src = _load_logo_data_uri(template_dir)

    start = date.fromisoformat(cfg["date_range"]["start"])
    end = date.fromisoformat(cfg["date_range"]["end"])
    booklet_color_map = _booklet_color_map(cfg, model)

    day_map = {d.day: d for d in model.days}
    last_questions_day = max((d.day for d in model.days if d.blocks), default=None)
    render_end = start - timedelta(days=1)
    if last_questions_day is not None:
        render_end = last_questions_day + timedelta(days=(6 - last_questions_day.weekday()))
    weeks: List[Dict[str, Any]] = []

    week_idx = 1
    for week in iter_weeks_monday_to_sunday(start, render_end):
        cells = []
        for day in week:
            if day < start or day > end:
                cells.append({"empty": True})
                continue

            pd = day_map.get(day)
            if pd is None:
                cells.append(
                    {
                        "empty": False,
                        "day": _format_day(day),
                        "is_rest": True,
                        "blocks": [],
                        "notes": ["Descanso"],
                    }
                )
                continue

            rendered_blocks = []
            for b in pd.blocks:
                booklet_color = _to_css_color(booklet_color_map.get(b.booklet_name, "#A8D8FF"))
                subj_style = _subject_style(b.subject)
                session_n = _session_for_block(b.subject, int(b.start_q))
                booklet_display = b.booklet_name.replace("Versión #", "Versión\u00A0#")
                qty_display = f"{b.qty} preguntas ({b.start_q}\u2011{b.end_q})"
                rendered_blocks.append(
                    {
                        "subject": subj_style["label"],
                        "booklet_name": b.booklet_name,
                        "booklet_display": booklet_display,
                        "session_label": f"Sesión #{session_n}",
                        "start_q": b.start_q,
                        "end_q": b.end_q,
                        "qty": b.qty,
                        "qty_display": qty_display,
                        "booklet_color": booklet_color,
                        "subject_color": subj_style["color"],
                        "subject_bg_color": _with_alpha(subj_style["color"], 0.12),
                        "subject_border_color": _with_alpha(subj_style["color"], 0.55),
                        "subject_emoji": subj_style["emoji"],
                    }
                )

            cells.append(
                {
                    "empty": False,
                    "day": _format_day(day),
                    "is_rest": pd.is_rest,
                    "blocks": rendered_blocks,
                    "notes": pd.notes,
                }
            )

        weeks.append(
            {
                "index": week_idx,
                "label": _format_day(week[0]),
                "cells": cells,
            }
        )
        week_idx += 1

    legend = []
    full_booklet_order = _booklet_order(cfg, model)
    reached_booklets = _booklets_reached_order(model, full_booklet_order)
    for idx, booklet_name in enumerate(reached_booklets, start=1):
        color = _to_css_color(booklet_color_map.get(booklet_name, "#A8D8FF"))
        legend.append(
            {
                "order": idx,
                "booklet_name": booklet_name,
                "color": color,
                "text_color": _legend_text_color(color),
                "bg_color": _with_alpha(color, 0.12),
                "border_color": _with_alpha(color, 0.40),
            }
        )
    legend_columns: List[List[Dict[str, Any]]] = []
    if legend:
        col_count = 3
        rows_per_col = math.ceil(len(legend) / col_count)
        for col_idx in range(col_count):
            start_idx = col_idx * rows_per_col
            end_idx = start_idx + rows_per_col
            legend_columns.append(legend[start_idx:end_idx])

    subject_legend = [
        SUBJECT_STYLE_MAP["matematicas"],
        SUBJECT_STYLE_MAP["lectura critica"],
        SUBJECT_STYLE_MAP["sociales y ciudadanas"],
        SUBJECT_STYLE_MAP["ciencias naturales"],
        SUBJECT_STYLE_MAP["ingles"],
    ]

    subjects_reinforce_text, subjects_reinforce_none = _subjects_to_reinforce(cfg)
    type_info = _plan_type_info(cfg)
    intro = {
        "student_name": model.meta.get("student_name", "Estudiante"),
        "start_label": _format_day(start),
        "plan_type": f"{type_info['code']} - {type_info['name']}",
        "plan_type_code": type_info["code"],
        "plan_type_name": type_info["name"],
        "plan_type_description": type_info["description"],
        "plan_type_ideal": type_info["ideal"],
        "daily_questions": _daily_questions_text(cfg),
        "active_days": _active_days_text(cfg),
        "subjects_reinforce": subjects_reinforce_text,
        "subjects_reinforce_none": subjects_reinforce_none,
    }

    return template.render(
        cfg=cfg,
        meta=model.meta,
        intro=intro,
        logo_src=logo_src,
        is_type_b=int(cfg.get("meta", {}).get("plan_type", 0)) == 2,
        days_es=DAYS_ES,
        weeks=weeks,
        legend=legend,
        legend_columns=legend_columns,
        subject_legend=subject_legend,
        generated_label=f"{_format_day(start)} - {_format_day(end)}",
    )
