from __future__ import annotations

from typing import Any, Dict


BOOKLET_SEQUENCE = [
    {"id": "BK-2025A-1", "name": "2025 Cal A Versión #1"},
    {"id": "BK-2025B-2", "name": "2025 Cal B Versión #2"},
    {"id": "BK-2025B-1", "name": "2025 Cal B Versión #1"},
    {"id": "BK-VIP-9", "name": "SIMULACRO VIP #9"},
    {"id": "BK-2025A-2", "name": "2025 Cal A Versión #2"},
    {"id": "BK-VIP-8", "name": "SIMULACRO VIP #8"},
    {"id": "BK-VIP-7", "name": "SIMULACRO VIP #7"},
    {"id": "BK-VIP-6", "name": "SIMULACRO VIP #6"},
    {"id": "BK-VIP-5", "name": "SIMULACRO VIP #5"},
    {"id": "BK-VIP-4", "name": "SIMULACRO VIP #4"},
    {"id": "BK-VIP-3", "name": "SIMULACRO VIP #3"},
    {"id": "BK-VIP-2", "name": "SIMULACRO VIP #2"},
    {"id": "BK-VIP-1", "name": "SIMULACRO VIP #1"},
]


def _subject_booklets(total_q: int):
    return [{"id": b["id"], "name": b["name"], "total_q": total_q} for b in BOOKLET_SEQUENCE]


def sample_cfg(plan_type: int) -> Dict[str, Any]:
    base = {
        "meta": {
            "schema_version": "1.0",
            "plan_type": plan_type,
            "student_name": "Sara",
            "plan_label": "ICFES 2026",
            "renewal_policy": {"price_cop": 10000},
        },
        "date_range": {
            "start": "2025-12-15",
            "end": "2026-02-28",
            "timezone": "America/Bogota",
        },
        "calendar_rules": {
            "active_weekdays": [0, 1, 2, 3, 4],
            "week_table_order": [0, 1, 2, 3, 4, 5, 6],
        },
        "extras": {
            "focus_subjects": ["Matemáticas"],
            "weekly_extra_q": 30,
            "enabled": True,
        },
        "style": {
            "palette": ["#A8D8FF", "#FFB3B3", "#B8F2C2", "#FFF8A6", "#E8D7C3"],
            "subject_color_map": {},
            "booklet_emoji_map": {},
            "branding": {
                "header_title": "CALENDARIO ICFES 2026",
                "header_subtitle": "Preicfes Material",
            },
            "ui": {
                "checkbox_unchecked": "[]",
                "completed_text": "Cuadernillo COMPLETADO",
            },
        },
    }

    if plan_type == 1:
        base["intensity"] = {
            "mode": "fixed",
            "fixed_q": 30,
            "by_weekday_q": {"0": 30, "1": 30, "2": 30, "3": 30, "4": 30, "5": 0, "6": 0},
            "per_subject_base_q": {},
            "multiplier_by_weekday": {},
        }
        base["assignments"] = {"subject_by_weekday": {}}
        base["content"] = {
            "subjects": {},
            "global_booklets": BOOKLET_SEQUENCE[:],
        }
        return base

    if plan_type == 2:
        base["intensity"] = {
            "mode": "fixed",
            "fixed_q": 0,
            "by_weekday_q": {},
            "per_subject_base_q": {
                "Matemáticas": 20,
                "Lectura Crítica": 15,
                "Sociales y Ciudadanas": 15,
                "Ciencias Naturales": 15,
                "Inglés": 10,
            },
            "multiplier_by_weekday": {"0": 1, "1": 1, "2": 0.5, "3": 1.5, "4": 1, "5": 0, "6": 0},
        }
        base["assignments"] = {"subject_by_weekday": {}}
        base["content"] = {
            "subjects": {
                "Matemáticas": _subject_booklets(50),
                "Lectura Crítica": _subject_booklets(41),
                "Sociales y Ciudadanas": _subject_booklets(50),
                "Ciencias Naturales": _subject_booklets(58),
                "Inglés": _subject_booklets(55),
            },
            "global_booklets": [],
        }
        return base

    base["intensity"] = {
        "mode": "fixed",
        "fixed_q": 30,
        "by_weekday_q": {"0": 30, "1": 25, "2": 30, "3": 0, "4": 35, "5": 0, "6": 0},
        "per_subject_base_q": {},
        "multiplier_by_weekday": {},
    }
    base["assignments"] = {
        "subject_by_weekday": {
            "0": "Matemáticas",
            "1": "Lectura Crítica",
            "2": "Ciencias Naturales",
            "3": "Descanso",
            "4": "Sociales y Ciudadanas",
            "5": "Descanso",
            "6": "Descanso",
        }
    }
    base["content"] = {
        "subjects": {
            "Matemáticas": _subject_booklets(50),
            "Lectura Crítica": _subject_booklets(41),
            "Sociales y Ciudadanas": _subject_booklets(50),
            "Ciencias Naturales": _subject_booklets(58),
            "Inglés": _subject_booklets(55),
        },
        "global_booklets": [],
    }
    return base
