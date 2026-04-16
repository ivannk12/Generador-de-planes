from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
import math

# Orden lineal real dentro del cuadernillo (Tipo 1)
BOOKLET_SLOTS: List[Tuple[str, int]] = [
    ("Matemáticas", 25),
    ("Lectura Crítica", 41),
    ("Sociales y Ciudadanas", 25),
    ("Ciencias Naturales", 29),
    ("Sociales y Ciudadanas", 25),
    ("Matemáticas", 25),
    ("Ciencias Naturales", 29),
    ("Inglés", 55),
]

SUBJECT_TOTALS: Dict[str, int] = {}
for subject, qty in BOOKLET_SLOTS:
    SUBJECT_TOTALS[subject] = SUBJECT_TOTALS.get(subject, 0) + qty

DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@dataclass
class SubjectSegment:
    session: int
    subject_local_start: int
    subject_local_end: int
    session_start: int
    session_end: int


def _build_subject_segments() -> Dict[str, List[SubjectSegment]]:
    segments: Dict[str, List[SubjectSegment]] = {}
    subject_local_cursor: Dict[str, int] = {}
    session_cursor = {1: 1, 2: 1}

    for idx, (subject, qty) in enumerate(BOOKLET_SLOTS):
        session = 1 if idx <= 3 else 2
        local_start = subject_local_cursor.get(subject, 1)
        local_end = local_start + qty - 1
        sess_start = session_cursor[session]
        sess_end = sess_start + qty - 1

        segments.setdefault(subject, []).append(
            SubjectSegment(
                session=session,
                subject_local_start=local_start,
                subject_local_end=local_end,
                session_start=sess_start,
                session_end=sess_end,
            )
        )

        subject_local_cursor[subject] = local_end + 1
        session_cursor[session] = sess_end + 1

    return segments


SUBJECT_SEGMENTS = _build_subject_segments()


@dataclass
class DayBlock:
    subject: str
    booklet_name: str
    start_q: int
    end_q: int
    qty: int
    range_scope: str = "subject"


@dataclass
class PlanDay:
    day: date
    weekday: int
    is_rest: bool
    color: Optional[str]
    blocks: List[DayBlock]
    notes: List[str]


@dataclass
class PlanModel:
    meta: Dict[str, Any]
    days: List[PlanDay]


@dataclass
class LinearBookletProgress:
    slot_idx: int = 0
    slot_offset: int = 0
    done_by_subject: Dict[str, int] | None = None

    def __post_init__(self) -> None:
        if self.done_by_subject is None:
            self.done_by_subject = {s: 0 for s in SUBJECT_TOTALS}

    def is_complete(self) -> bool:
        return self.slot_idx >= len(BOOKLET_SLOTS)


@dataclass
class SubjectProgress:
    booklet_idx: int = 0
    pos_in_booklet: int = 0


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def _normalize_subject_progress(cat: List[Dict[str, Any]], progress: SubjectProgress) -> bool:
    while progress.booklet_idx < len(cat):
        total_q = int(cat[progress.booklet_idx]["total_q"])
        if progress.pos_in_booklet >= total_q:
            progress.booklet_idx += 1
            progress.pos_in_booklet = 0
        else:
            break
    return progress.booklet_idx < len(cat)


def _has_pending_questions(
    subjects: List[str],
    subj_catalog: Dict[str, List[Dict[str, Any]]],
    progress_by_subject: Dict[str, SubjectProgress],
) -> bool:
    for subj in subjects:
        cat = subj_catalog.get(subj)
        if not cat:
            continue
        progress = progress_by_subject.setdefault(subj, SubjectProgress())
        if _normalize_subject_progress(cat, progress):
            return True
    return False


def cycle_map(keys: List[str], palette: List[str]) -> Dict[str, str]:
    if not palette:
        raise ValueError("style.palette no puede estar vacía")
    return {k: palette[i % len(palette)] for i, k in enumerate(keys)}


def iter_weeks_monday_to_sunday(start: date, end: date):
    cursor = start
    while cursor <= end:
        monday = cursor - timedelta(days=cursor.weekday())
        yield [monday + timedelta(days=i) for i in range(7)]
        cursor = monday + timedelta(days=7)


def map_subject_local_to_session_ranges(subject: str, local_start: int, local_end: int) -> List[Tuple[int, int, int]]:
    if subject not in SUBJECT_SEGMENTS:
        raise ValueError(f"Materia no soportada para numeración por sesión: {subject}")
    if local_start < 1 or local_end < local_start:
        raise ValueError(f"Rango local inválido para {subject}: {local_start}..{local_end}")
    if local_end > SUBJECT_TOTALS[subject]:
        raise ValueError(
            f"Rango local fuera de límites para {subject}: {local_start}..{local_end} "
            f"(máximo {SUBJECT_TOTALS[subject]})"
        )

    mapped: List[Tuple[int, int, int]] = []
    for segment in SUBJECT_SEGMENTS[subject]:
        overlap_start = max(local_start, segment.subject_local_start)
        overlap_end = min(local_end, segment.subject_local_end)
        if overlap_start > overlap_end:
            continue

        offset = overlap_start - segment.subject_local_start
        session_start = segment.session_start + offset
        session_end = session_start + (overlap_end - overlap_start)
        mapped.append((segment.session, session_start, session_end))

    return mapped


def validate_config(cfg: Dict[str, Any]) -> None:
    if "meta" not in cfg:
        raise ValueError("cfg.meta es obligatorio")
    plan_type = int(cfg["meta"]["plan_type"])
    if plan_type not in (1, 2, 3):
        raise ValueError("meta.plan_type debe ser 1, 2 o 3")

    date_range = cfg.get("date_range", {})
    start_raw = date_range.get("start")
    end_raw = date_range.get("end")
    if not start_raw or not end_raw:
        raise ValueError("date_range.start y date_range.end son obligatorios (YYYY-MM-DD)")
    try:
        start = date.fromisoformat(start_raw)
        end = date.fromisoformat(end_raw)
    except ValueError as exc:
        raise ValueError("Fechas inválidas: usa formato YYYY-MM-DD en date_range.start y date_range.end") from exc
    if start > end:
        raise ValueError("date_range.start no puede ser mayor que date_range.end")

    active_weekdays = cfg["calendar_rules"]["active_weekdays"]
    if any((d < 0 or d > 6) for d in active_weekdays):
        raise ValueError("calendar_rules.active_weekdays solo admite 0..6")

    palette = cfg["style"].get("palette", [])
    if not (1 <= len(palette) <= 10):
        raise ValueError("style.palette debe tener entre 1 y 10 colores")

    if plan_type == 1 and not cfg["content"].get("global_booklets"):
        raise ValueError("content.global_booklets no puede estar vacío para Tipo 1")

    if plan_type == 2:
        if not cfg["intensity"].get("per_subject_base_q"):
            raise ValueError("intensity.per_subject_base_q es obligatorio para Tipo 2")
        if not cfg["intensity"].get("multiplier_by_weekday"):
            raise ValueError("intensity.multiplier_by_weekday es obligatorio para Tipo 2")

    if plan_type == 3 and not cfg.get("assignments", {}).get("subject_by_weekday"):
        raise ValueError("assignments.subject_by_weekday es obligatorio para Tipo 3")


def daily_quota_type1_or_3(cfg: Dict[str, Any], weekday: int) -> int:
    mode = cfg["intensity"]["mode"]
    if mode == "fixed":
        return int(cfg["intensity"]["fixed_q"])
    if mode == "by_weekday":
        return int(cfg["intensity"]["by_weekday_q"].get(str(weekday), 0))
    raise ValueError("intensity.mode debe ser 'fixed' o 'by_weekday'")


def build_plan_model(cfg: Dict[str, Any]) -> PlanModel:
    validate_config(cfg)
    plan_type = int(cfg["meta"]["plan_type"])
    if plan_type == 1:
        return _build_type1(cfg)
    if plan_type == 2:
        return _build_type2(cfg)
    return _build_type3(cfg)


def _build_type1(cfg: Dict[str, Any]) -> PlanModel:
    start = date.fromisoformat(cfg["date_range"]["start"])
    end = date.fromisoformat(cfg["date_range"]["end"])
    active_weekdays = set(cfg["calendar_rules"]["active_weekdays"])

    global_booklets = cfg["content"]["global_booklets"]
    booklet_names = [b["name"] for b in global_booklets]
    booklet_color_map = cycle_map(booklet_names, cfg["style"]["palette"])

    days: List[PlanDay] = []
    booklet_idx = 0
    progress = LinearBookletProgress()

    d = start
    while d <= end and booklet_idx < len(global_booklets):
        wd = d.weekday()
        quota = daily_quota_type1_or_3(cfg, wd)

        if wd not in active_weekdays or quota <= 0:
            days.append(PlanDay(day=d, weekday=wd, is_rest=True, color=None, blocks=[], notes=["Descanso"]))
            d += timedelta(days=1)
            continue

        blocks: List[DayBlock] = []
        notes: List[str] = []
        remaining = quota
        current_booklet_name = global_booklets[booklet_idx]["name"]
        day_color = booklet_color_map[current_booklet_name]

        while remaining > 0 and booklet_idx < len(global_booklets):
            if progress.is_complete():
                notes.append(f"Cuadernillo {current_booklet_name} completado")
                booklet_idx += 1
                if booklet_idx >= len(global_booklets):
                    break
                current_booklet_name = global_booklets[booklet_idx]["name"]
                day_color = booklet_color_map[current_booklet_name]
                progress = LinearBookletProgress()
                notes.append(f"Inicio de cuadernillo {current_booklet_name}")

            if booklet_idx >= len(global_booklets):
                break

            subject, slot_len = BOOKLET_SLOTS[progress.slot_idx]
            slot_remaining = slot_len - progress.slot_offset
            if slot_remaining <= 0:
                progress.slot_idx += 1
                progress.slot_offset = 0
                continue

            take = min(remaining, slot_remaining)

            # Regla innegociable: la numeración se reinicia por sesión.
            if progress.slot_idx <= 3:
                session_before_slot = sum(n for _, n in BOOKLET_SLOTS[: progress.slot_idx])
            else:
                session_before_slot = sum(n for _, n in BOOKLET_SLOTS[4 : progress.slot_idx])

            start_q = session_before_slot + progress.slot_offset + 1
            end_q = start_q + take - 1

            blocks.append(
                DayBlock(
                    subject=subject,
                    booklet_name=current_booklet_name,
                    start_q=start_q,
                    end_q=end_q,
                    qty=take,
                    range_scope="booklet",
                )
            )

            progress.slot_offset += take
            remaining -= take

            if progress.slot_offset >= slot_len:
                progress.slot_idx += 1
                progress.slot_offset = 0

        days.append(PlanDay(day=d, weekday=wd, is_rest=False, color=day_color, blocks=blocks, notes=notes))
        d += timedelta(days=1)

    return PlanModel(meta=cfg["meta"], days=days)


def _build_type2(cfg: Dict[str, Any]) -> PlanModel:
    start = date.fromisoformat(cfg["date_range"]["start"])
    end = date.fromisoformat(cfg["date_range"]["end"])
    active_weekdays = set(cfg["calendar_rules"]["active_weekdays"])

    per_subject_base = cfg["intensity"]["per_subject_base_q"]
    mult_map = cfg["intensity"]["multiplier_by_weekday"]
    subj_catalog = cfg["content"]["subjects"]

    subjects = [s for s in per_subject_base if s in subj_catalog]
    palette = cfg["style"]["palette"]
    subject_color_map = cfg["style"].get("subject_color_map") or cycle_map(subjects, palette)

    progress_by_subject = {s: SubjectProgress() for s in subjects}

    days: List[PlanDay] = []
    d = start
    while d <= end:
        if not _has_pending_questions(subjects, subj_catalog, progress_by_subject):
            break

        wd = d.weekday()

        if wd not in active_weekdays:
            days.append(PlanDay(day=d, weekday=wd, is_rest=True, color=None, blocks=[], notes=["Descanso"]))
            d += timedelta(days=1)
            continue

        mult = float(mult_map.get(str(wd), 1))
        if mult == 0:
            days.append(PlanDay(day=d, weekday=wd, is_rest=True, color=None, blocks=[], notes=["Descanso"]))
            d += timedelta(days=1)
            continue

        blocks: List[DayBlock] = []
        notes: List[str] = []
        active_subjects_today = 0

        for subj in subjects:
            base = int(per_subject_base.get(subj, 0))
            if base <= 0:
                continue

            qty = _round_half_up(base * mult)
            if qty <= 0:
                continue

            cat = subj_catalog[subj]
            p = progress_by_subject[subj]
            remaining = qty
            consumed_today = 0

            while remaining > 0:
                if not _normalize_subject_progress(cat, p):
                    break

                booklet_name = cat[p.booklet_idx]["name"]
                total_q = int(cat[p.booklet_idx]["total_q"])
                local_start = p.pos_in_booklet + 1
                local_end = min(p.pos_in_booklet + remaining, total_q)
                take = local_end - local_start + 1
                if take <= 0:
                    break

                session_ranges = map_subject_local_to_session_ranges(subj, local_start, local_end)
                for _, session_start, session_end in session_ranges:
                    blocks.append(
                        DayBlock(
                            subject=subj,
                            booklet_name=booklet_name,
                            start_q=session_start,
                            end_q=session_end,
                            qty=session_end - session_start + 1,
                            range_scope="booklet",
                        )
                    )

                p.pos_in_booklet += take
                remaining -= take
                consumed_today += take

                if p.pos_in_booklet >= total_q:
                    notes.append(f"{subj}: cuadernillo {booklet_name} completado")

            if consumed_today > 0:
                active_subjects_today += 1

        if not blocks:
            days.append(PlanDay(day=d, weekday=wd, is_rest=True, color=None, blocks=[], notes=["Descanso"]))
            d += timedelta(days=1)
            continue

        if active_subjects_today == 1:
            day_color = subject_color_map.get(blocks[0].subject)
        else:
            day_color = palette[0]

        days.append(PlanDay(day=d, weekday=wd, is_rest=False, color=day_color, blocks=blocks, notes=notes))
        d += timedelta(days=1)

    return PlanModel(meta=cfg["meta"], days=days)


def _build_type3(cfg: Dict[str, Any]) -> PlanModel:
    start = date.fromisoformat(cfg["date_range"]["start"])
    end = date.fromisoformat(cfg["date_range"]["end"])
    active_weekdays = set(cfg["calendar_rules"]["active_weekdays"])

    subj_catalog = cfg["content"]["subjects"]
    assignments = cfg["assignments"]["subject_by_weekday"]

    subjects_used: List[str] = []
    seen: set[str] = set()
    for _, subj in assignments.items():
        if not isinstance(subj, str):
            continue
        subj_norm = subj.strip()
        if subj_norm.lower() == "descanso" or not subj_norm:
            continue
        if subj_norm not in seen:
            seen.add(subj_norm)
            subjects_used.append(subj_norm)

    palette = cfg["style"]["palette"]
    subject_color_map = cfg["style"].get("subject_color_map") or cycle_map(subjects_used, palette)

    progress_by_subject = {s: SubjectProgress() for s in subjects_used}

    # Solo cuenta materias que realmente pueden avanzar con la configuración actual
    # (día activo + cuota positiva + materia válida en el catálogo).
    schedulable_subjects: List[str] = []
    sched_seen: set[str] = set()
    for wd in range(7):
        if wd not in active_weekdays:
            continue
        assigned = assignments.get(str(wd), "Descanso")
        if not isinstance(assigned, str):
            continue
        subj = assigned.strip()
        if not subj or subj.lower() == "descanso" or subj not in subj_catalog:
            continue
        if daily_quota_type1_or_3(cfg, wd) <= 0:
            continue
        if subj not in sched_seen:
            sched_seen.add(subj)
            schedulable_subjects.append(subj)

    days: List[PlanDay] = []
    d = start
    while d <= end:
        if not _has_pending_questions(schedulable_subjects, subj_catalog, progress_by_subject):
            break

        wd = d.weekday()

        if wd not in active_weekdays:
            days.append(PlanDay(day=d, weekday=wd, is_rest=True, color=None, blocks=[], notes=["Descanso"]))
            d += timedelta(days=1)
            continue

        assigned = assignments.get(str(wd), "Descanso")
        if not isinstance(assigned, str) or assigned.strip().lower() == "descanso":
            days.append(PlanDay(day=d, weekday=wd, is_rest=True, color=None, blocks=[], notes=["Descanso"]))
            d += timedelta(days=1)
            continue

        quota = daily_quota_type1_or_3(cfg, wd)
        if quota <= 0:
            days.append(PlanDay(day=d, weekday=wd, is_rest=True, color=None, blocks=[], notes=["Descanso"]))
            d += timedelta(days=1)
            continue

        subj = assigned.strip()
        if subj not in subj_catalog:
            days.append(
                PlanDay(
                    day=d,
                    weekday=wd,
                    is_rest=True,
                    color=None,
                    blocks=[],
                    notes=[f"Descanso (materia inválida: {subj})"],
                )
            )
            d += timedelta(days=1)
            continue

        p = progress_by_subject.setdefault(subj, SubjectProgress())
        cat = subj_catalog[subj]

        if not _normalize_subject_progress(cat, p):
            days.append(
                PlanDay(day=d, weekday=wd, is_rest=True, color=None, blocks=[], notes=[f"{subj}: sin más preguntas"])
            )
            d += timedelta(days=1)
            continue

        blocks = []
        notes: List[str] = []
        remaining = quota

        while remaining > 0:
            if not _normalize_subject_progress(cat, p):
                break

            booklet_name = cat[p.booklet_idx]["name"]
            total_q = int(cat[p.booklet_idx]["total_q"])
            local_start = p.pos_in_booklet + 1
            local_end = min(p.pos_in_booklet + remaining, total_q)
            take = local_end - local_start + 1
            if take <= 0:
                break

            session_ranges = map_subject_local_to_session_ranges(subj, local_start, local_end)
            for _, session_start, session_end in session_ranges:
                blocks.append(
                    DayBlock(
                        subject=subj,
                        booklet_name=booklet_name,
                        start_q=session_start,
                        end_q=session_end,
                        qty=session_end - session_start + 1,
                        range_scope="booklet",
                    )
                )

            p.pos_in_booklet += take
            remaining -= take

            if p.pos_in_booklet >= total_q:
                notes.append(f"{subj}: cuadernillo {booklet_name} completado")

        days.append(
            PlanDay(
                day=d,
                weekday=wd,
                is_rest=False,
                color=subject_color_map.get(subj),
                blocks=blocks,
                notes=notes,
            )
        )
        d += timedelta(days=1)

    return PlanModel(meta=cfg["meta"], days=days)


def plan_model_to_dict(model: PlanModel) -> Dict[str, Any]:
    payload = asdict(model)
    for day in payload["days"]:
        day["day"] = day["day"].isoformat()
    return payload


def demo_session_mapping() -> None:
    lectura = map_subject_local_to_session_ranges("Lectura Crítica", 1, 15)
    sociales = map_subject_local_to_session_ranges("Sociales y Ciudadanas", 20, 35)

    lectura_render = " y ".join([f"sesión {s} {a}..{b}" for s, a, b in lectura])
    sociales_render = " y ".join([f"sesión {s} {a}..{b}" for s, a, b in sociales])

    print(f"Lectura local 1..15 => {lectura_render}")
    print(f"Sociales local 20..35 => {sociales_render}")
