from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import re
from typing import Any, Dict, List, Tuple

from .sample_cfgs import sample_cfg

WEEKDAY_MAP = {
    "lunes": 0,
    "lun": 0,
    "martes": 1,
    "marte": 1,
    "mar": 1,
    "miercoles": 2,
    "miércoles": 2,
    "miercole": 2,
    "mie": 2,
    "jueves": 3,
    "jue": 3,
    "viernes": 4,
    "vie": 4,
    "sabado": 5,
    "sábado": 5,
    "sab": 5,
    "domingo": 6,
    "dom": 6,
}

SUBJECT_ALIASES = {
    "matematica": "Matemáticas",
    "matematicas": "Matemáticas",
    "matemáticas": "Matemáticas",
    "lectura": "Lectura Crítica",
    "lectura critica": "Lectura Crítica",
    "lectura crítica": "Lectura Crítica",
    "sociales": "Sociales y Ciudadanas",
    "sociales y ciudadanas": "Sociales y Ciudadanas",
    "ciencias": "Ciencias Naturales",
    "cieencias": "Ciencias Naturales",
    "ciencias naturales": "Ciencias Naturales",
    "ingles": "Inglés",
    "inglés": "Inglés",
    "descanso": "Descanso",
}
class RowParseError(ValueError):
    pass


def _norm_text(text: str) -> str:
    return " ".join((text or "").strip().split())


def _norm_key(text: str) -> str:
    t = _norm_text(text).lower()
    t = (
        t.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
    )
    return t


def _parse_date_iso(text: str, field_name: str) -> str:
    value = _norm_text(text)
    if not value:
        raise RowParseError(f"{field_name} está vacío")

    # Regla: entrada siempre en día/mes/año (acepta 1 o 2 dígitos en día/mes).
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue

    raise RowParseError(
        f"{field_name} no tiene fecha válida: '{text}'. Usa formato día/mes/año (ej: 11/2/2026)"
    )


def _looks_like_date_token(text: str) -> bool:
    value = _norm_text(text)
    if not value:
        return False
    return bool(re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", value))


def _parse_int(text: str, field_name: str) -> int:
    value = _norm_text(text).replace(" ", "")
    # Acepta basura de comillas pegadas desde Sheets, p.ej. 40" o "40
    match = re.search(r"-?\d+", value)
    if not match:
        raise RowParseError(f"{field_name} debe ser entero: '{text}'")
    try:
        return int(match.group(0))
    except ValueError as exc:
        raise RowParseError(f"{field_name} debe ser entero: '{text}'") from exc


def _parse_int_or_rest(text: str, field_name: str) -> int:
    key = _norm_key(text)
    key = re.sub(r"[^a-z0-9 ]+", " ", key)
    key = " ".join(key.split())

    if key in {"descanso", "descansar", "rest", "reposo", "sin preguntas"}:
        return 0

    return _parse_int(text, field_name)


def _parse_float(text: str, field_name: str) -> float:
    value = _norm_text(text).lower().replace("x", "").replace("×", "").replace(",", ".").replace(" ", "")
    try:
        return float(value)
    except ValueError as exc:
        raise RowParseError(f"{field_name} debe ser numérico: '{text}'") from exc


def _parse_boolish(text: str, field_name: str) -> bool:
    value = _norm_key(text)
    value = re.sub(r"[^a-z0-9 ]+", "", value)
    value = " ".join(value.split())
    yes = {"si", "s", "true", "1", "igual", "misma", "fijo", "fixed"}
    no = {"no", "n", "false", "0", "variable", "por dia"}

    if value in yes:
        return True
    if value in no:
        return False
    raise RowParseError(f"{field_name} debe ser sí/no, recibido: '{text}'")


def normalize_subject(text: str) -> str:
    raw = _norm_text(text)
    key = _norm_key(raw)
    # Limpia comillas, emojis y símbolos para que "Matemáticas" o 📖 Lectura coincidan.
    key = re.sub(r"[^a-z0-9 ]+", " ", key)
    key = " ".join(key.split())

    if key in SUBJECT_ALIASES:
        return SUBJECT_ALIASES[key]

    # Permite frases mixtas como "lectura critica y ciencias":
    # elige la primera materia reconocida.
    for alias, canonical in sorted(SUBJECT_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", key):
            return canonical

    # Fallback: texto limpio sin adornos comunes.
    cleaned = re.sub(r'^[^A-Za-zÁÉÍÓÚÜáéíóúüÑñ]+', "", raw)
    cleaned = re.sub(r'[^A-Za-zÁÉÍÓÚÜáéíóúüÑñ0-9 ]+$', "", cleaned).strip()
    return cleaned or raw


def _split_weekday_value_line(line: str) -> Tuple[str, str] | None:
    if ":" in line:
        day_part, value_part = line.split(":", 1)
        day_key = _norm_key(day_part)
        if day_key in WEEKDAY_MAP:
            return day_part, value_part

    parts = _norm_text(line).split(" ", 1)
    if len(parts) < 2:
        return None
    day_part = parts[0].strip().strip(".")
    day_key = _norm_key(day_part)
    if day_key not in WEEKDAY_MAP:
        return None
    return day_part, parts[1]


def parse_colors(text: str) -> List[str]:
    emoji_color_map = {
        "🔴": "rojo",
        "🟠": "naranja",
        "🟡": "amarillo",
        "🟢": "verde",
        "🔵": "azul",
        "🟣": "morado",
        "🟤": "cafe",
        "⚫": "negro",
        "⚪": "blanco",
        "🩷": "rosado",
        "💗": "rosado",
        "💖": "rosado",
        "💙": "azul",
        "💚": "verde",
        "💛": "amarillo",
        "🧡": "naranja",
        "💜": "morado",
        "🤎": "cafe",
        "🖤": "negro",
        "🤍": "blanco",
    }

    normalized = text.replace("\xa0", " ")
    emoji_tokens = [emoji_color_map[ch] for ch in normalized if ch in emoji_color_map]
    if emoji_tokens:
        out = emoji_tokens[:10]
        if len(out) < 10:
            base = out[:]
            idx = 0
            while len(out) < 10:
                out.append(base[idx % len(base)])
                idx += 1
        return out

    # Soporta listas numeradas como:
    # 1. #AACC96
    # 2. azul
    base_chunks = [x for x in re.split(r"[\n,]+", normalized) if _norm_text(x)]

    out: List[str] = []
    for chunk in base_chunks:
        token = _norm_text(chunk.strip('"').strip("'"))
        token = re.sub(r"^\d+\s*[\.\)\-:]\s*", "", token)  # quita "1. ", "2) ", etc.
        if not token:
            continue

        # Mantiene colores compuestos como "rojo pastel" en un solo token.
        t = _norm_text(token)
        t = re.sub(r"^[\s\-\u2022•]+", "", t)
        t = re.sub(r"[\s\.;:!]+$", "", t)
        t = re.sub(r"\bcalro\b", "claro", t, flags=re.IGNORECASE)
        if not t:
            continue
        if re.fullmatch(r"\d+[\.\)]?", t):
            continue
        if _norm_key(t) in {"y", "e", "and"}:
            continue
        out.append(t)

    if not out:
        raise RowParseError("No se detectaron colores en la fila")
    if len(out) > 10:
        raise RowParseError("Máximo 10 colores en style.palette")

    # Si llegan menos de 10, repetir patrón cíclico hasta completar 10.
    if len(out) < 10:
        base = out[:]
        idx = 0
        while len(out) < 10:
            out.append(base[idx % len(base)])
            idx += 1

    return out


def parse_weekday_numbers(text: str) -> Dict[str, int]:
    out = {str(i): 0 for i in range(7)}
    found = False
    for raw_line in text.splitlines():
        line = raw_line.strip().strip('"').strip("'").strip("“”")
        if not line:
            continue
        split = _split_weekday_value_line(line)
        if split is None:
            continue
        day_part, value_part = split
        day_key = _norm_key(day_part)
        if day_key not in WEEKDAY_MAP:
            continue
        out[str(WEEKDAY_MAP[day_key])] = _parse_int_or_rest(value_part, f"preguntas para {day_part}")
        found = True

    if not found:
        raise RowParseError("No se pudieron leer cantidades por día (ej: 'Lunes: 30')")
    return out


def parse_active_weekdays_list(text: str) -> List[int]:
    key_all = _norm_key(text)
    key_all = re.sub(r"[^a-z0-9 ]+", " ", key_all)
    key_all = " ".join(key_all.split())
    if any(token in key_all for token in ["todos los dias", "toda la semana", "todos"]):
        return [0, 1, 2, 3, 4, 5, 6]

    out: List[int] = []
    seen = set()
    for token in re.split(r"[,\n;/]+", text):
        key = _norm_key(token)
        if not key:
            continue
        if key in WEEKDAY_MAP:
            wd = WEEKDAY_MAP[key]
            if wd not in seen:
                seen.add(wd)
                out.append(wd)
    if not out:
        raise RowParseError("No se pudieron leer días de estudio (ej: 'Lunes, Miércoles, Viernes')")
    return out


def _infer_active_weekdays_from_cells(cells: List[str], start_idx: int = 0) -> List[int] | None:
    for cell in cells[start_idx:]:
        raw = _norm_text(cell)
        if not raw:
            continue
        if ":" in raw:
            # Probablemente bloque tipo 'Lunes: 30' o similar.
            continue
        try:
            return parse_active_weekdays_list(raw)
        except RowParseError:
            continue
    return None


def parse_multipliers(text: str) -> Dict[str, float]:
    out = {str(i): 1.0 for i in range(7)}
    found = False
    for raw_line in text.splitlines():
        line = raw_line.strip().strip('"').strip("'").strip("“”")
        if not line:
            continue
        split = _split_weekday_value_line(line)
        if split is None:
            continue
        day_part, value_part = split
        day_key = _norm_key(day_part)
        if day_key not in WEEKDAY_MAP:
            continue
        out[str(WEEKDAY_MAP[day_key])] = _parse_float(value_part, f"multiplicador para {day_part}")
        found = True

    if not found:
        raise RowParseError("No se pudieron leer multiplicadores (ej: 'Lunes: x1.5')")
    return out


def parse_weekday_subjects(text: str) -> Dict[str, str]:
    out = {str(i): "Descanso" for i in range(7)}
    found = False
    for raw_line in text.splitlines():
        line = raw_line.strip().strip('"').strip("'").strip("“”")
        if not line:
            continue
        split = _split_weekday_value_line(line)
        if split is None:
            continue
        day_part, value_part = split
        day_key = _norm_key(day_part)
        if day_key not in WEEKDAY_MAP:
            continue
        out[str(WEEKDAY_MAP[day_key])] = normalize_subject(value_part)
        found = True

    if not found:
        raise RowParseError("No se pudieron leer asignaciones por día (ej: 'Lunes: Matemáticas')")
    return out


def parse_weekday_subject_qty(text: str) -> Tuple[Dict[str, str], Dict[str, int]]:
    subject_by_day = {str(i): "Descanso" for i in range(7)}
    qty_by_day = {str(i): 0 for i in range(7)}
    found = False

    for raw_line in text.splitlines():
        line = raw_line.strip().strip('"').strip("'").strip("“”")
        if not line:
            continue
        split = _split_weekday_value_line(line)
        if split is None:
            continue
        day_part, value_part = split
        day_key = _norm_key(day_part)
        if day_key not in WEEKDAY_MAP:
            continue

        value_clean = _norm_text(value_part)
        if not value_clean:
            continue

        qty_match = re.search(r"(-?\d+)\s*$", value_clean)
        if not qty_match:
            # Permite "Jueves: descanso" sin número explícito.
            subject = normalize_subject(value_clean)
            if _norm_key(subject) == "descanso":
                qty = 0
            else:
                raise RowParseError(
                    f"No se pudo leer cantidad en '{line}'. Usa formato tipo: 'Martes: Sociales 30'"
                )
        else:
            qty = int(qty_match.group(1))
            subject_text = _norm_text(value_clean[: qty_match.start()])
            subject = normalize_subject(subject_text) if subject_text else "Descanso"

        wd = WEEKDAY_MAP[day_key]
        subject_by_day[str(wd)] = subject
        qty_by_day[str(wd)] = qty
        found = True

    if not found:
        raise RowParseError(
            "No se pudieron leer asignaciones día-materia-preguntas (ej: 'Martes: Sociales 30')"
        )

    return subject_by_day, qty_by_day


def parse_subject_base_q(text: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            continue
        subject_part, value_part = line.split(":", 1)
        subject = normalize_subject(subject_part)
        if subject == "Descanso":
            continue
        out[subject] = _parse_int(value_part, f"base de {subject}")

    if not out:
        raise RowParseError("No se pudieron leer bases por materia (ej: 'Matemáticas: 20')")
    return out


def _subject_mentions(value_text: str) -> List[str]:
    key = _norm_key(value_text)
    key = re.sub(r"[^a-z0-9 ]+", " ", key)
    key = " ".join(key.split())
    mentions: List[str] = []
    seen = set()
    for alias, canonical in sorted(SUBJECT_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if canonical == "Descanso":
            continue
        if re.search(rf"\b{re.escape(alias)}\b", key) and canonical not in seen:
            seen.add(canonical)
            mentions.append(canonical)
    return mentions


def _validate_single_subject_per_line(text: str, allow_qty_suffix: bool) -> None:
    for raw_line in text.splitlines():
        line = raw_line.strip().strip('"').strip("'").strip("“”")
        if not line:
            continue
        split = _split_weekday_value_line(line)
        if split is None:
            continue
        _, value_part = split
        value_clean = _norm_text(value_part)
        if allow_qty_suffix:
            qty_match = re.search(r"(-?\d+)\s*$", value_clean)
            if qty_match:
                value_clean = _norm_text(value_clean[: qty_match.start()])
        mentions = _subject_mentions(value_clean)
        if len(mentions) > 1:
            raise RowParseError(f"Solo puede haber una materia por día. Línea inválida: '{line}'")


def _extract_cells(row_text: str) -> List[str]:
    raw = row_text.strip()
    if not raw:
        raise RowParseError("row_text está vacío")

    def _cells_from_payload(payload: Any) -> List[str] | None:
        if isinstance(payload, dict) and isinstance(payload.get("cells"), list):
            return [str(c) if c is not None else "" for c in payload["cells"]]
        if isinstance(payload, list):
            return [str(c) if c is not None else "" for c in payload]
        return None

    # Acepta JSON de celdas incluso con prefijos accidentales (ej: "1:47 PM{...}").
    cells: List[str] | None = None
    json_candidates = [raw]
    brace_idx = raw.find("{")
    bracket_idx = raw.find("[")
    if brace_idx > 0:
        json_candidates.append(raw[brace_idx:])
    if bracket_idx > 0:
        json_candidates.append(raw[bracket_idx:])

    for candidate in json_candidates:
        if not candidate or candidate[0] not in "{[":
            continue
        try:
            payload = json.loads(candidate)
            cells = _cells_from_payload(payload)
            if cells is not None:
                break
        except json.JSONDecodeError:
            continue

    if cells is None:
        cells = [c.strip() for c in raw.split("\t")]

    # tolera tabs extra al inicio/fin
    while cells and cells[0] == "":
        cells.pop(0)
    while cells and cells[-1] == "":
        cells.pop()

    if not cells:
        raise RowParseError("No se detectaron celdas en row_text")
    return cells


def _split_labeled_and_unlabeled(cells: List[str]) -> Tuple[Dict[str, str], List[str]]:
    labeled: Dict[str, str] = {}
    unlabeled: List[str] = []

    for cell in cells:
        if not _norm_text(cell):
            continue
        if ":" in cell and "\n" not in cell:
            key, value = cell.split(":", 1)
            key_norm = _norm_key(key)
            if key_norm:
                labeled[key_norm] = value.strip()
                continue
        unlabeled.append(cell)

    return labeled, unlabeled


def _get_value(labeled: Dict[str, str], unlabeled: List[str], aliases: List[str], pos: int, field: str) -> str:
    for alias in aliases:
        if alias in labeled and _norm_text(labeled[alias]):
            return labeled[alias]
    if pos < len(unlabeled) and _norm_text(unlabeled[pos]):
        return unlabeled[pos]
    raise RowParseError(f"Falta campo requerido: {field}")


def _set_common(cfg: Dict[str, Any], labeled: Dict[str, str], unlabeled: List[str]) -> None:
    cfg["meta"]["student_name"] = _get_value(labeled, unlabeled, ["nombre", "apodo", "estudiante"], 0, "nombre")
    cfg["date_range"]["start"] = _parse_date_iso(
        _get_value(labeled, unlabeled, ["fecha inicio", "inicio", "start"], 1, "fecha inicio"),
        "fecha inicio",
    )
    cfg["date_range"]["end"] = _parse_date_iso(
        _get_value(labeled, unlabeled, ["fecha fin", "fin", "end"], 2, "fecha fin"),
        "fecha fin",
    )

    colors_text = _get_value(labeled, unlabeled, ["colores", "palette"], 3, "colores")
    cfg["style"]["palette"] = parse_colors(colors_text)

    focus_text = _get_value(labeled, unlabeled, ["refuerzos", "focus", "focus_subjects"], 4, "refuerzos")
    focus_items = [normalize_subject(x) for x in re.split(r"[,\n]+", focus_text) if _norm_text(x)]
    cfg["extras"]["focus_subjects"] = focus_items


def parse_row_type1(cells: List[str]) -> Dict[str, Any]:
    cfg = deepcopy(sample_cfg(1))
    # Formato compacto esperado desde Claude (preguntas 1..6):
    # 0 nombre/apodo, 1 fecha inicio, 2 fecha fin, 3 misma cantidad (Sí/No)
    # Si Sí: 4 preguntas por día, 5 días a estudiar, 6 refuerzo, 7 colores
    # Si No: 4 días + preguntas por día (bloque), 5 refuerzo, 6 colores
    compact_like = False
    if len(cells) >= 4:
        try:
            compact_like = (
                bool(_norm_text(cells[0]))
                and _looks_like_date_token(_norm_text(cells[1]))
                and _looks_like_date_token(_norm_text(cells[2]))
            )
            if compact_like:
                _parse_boolish(_norm_text(cells[3]), "misma cantidad todos los días")
        except RowParseError:
            compact_like = False

    if compact_like:
        student_name = _norm_text(cells[0])
        start_raw = _norm_text(cells[1])
        end_raw = _norm_text(cells[2])
        same_text = _norm_text(cells[3])

        if not student_name:
            raise RowParseError("Nombre/apodo (pregunta 1) está vacío")

        cfg["meta"]["student_name"] = student_name
        cfg["date_range"]["start"] = _parse_date_iso(start_raw, "fecha inicio")
        cfg["date_range"]["end"] = _parse_date_iso(end_raw, "fecha fin")

        same_everyday = _parse_boolish(same_text, "misma cantidad todos los días")
        if same_everyday:
            # Compatibilidad: algunas respuestas de Tipo 1 llegan con bloque
            # "día: materia" + refuerzo + colores, igual que Tipo 3 compacto.
            # Para Tipo 1 la materia asignada no se usa; solo inferimos qué días
            # están activos y dejamos la cantidad fija por defecto del sample.
            day_block_text = cells[4] if len(cells) > 4 else ""
            focus_text = cells[5] if len(cells) > 5 else ""
            colors_text = cells[6] if len(cells) > 6 else ""
            compact_yes_with_day_block = False
            if len(cells) == 7 and _norm_text(day_block_text):
                try:
                    subject_by_weekday = parse_weekday_subjects(day_block_text)
                    compact_yes_with_day_block = True
                except RowParseError:
                    compact_yes_with_day_block = False

            if compact_yes_with_day_block:
                if not _norm_text(colors_text):
                    raise RowParseError("Pregunta 6 está vacía: colores")

                cfg["intensity"]["mode"] = "fixed"
                cfg["calendar_rules"]["active_weekdays"] = [
                    int(day) for day, subj in subject_by_weekday.items() if _norm_key(str(subj)) != "descanso"
                ]
                cfg["extras"]["focus_subjects"] = [
                    normalize_subject(x) for x in re.split(r"[,\n]+", focus_text) if _norm_text(x)
                ]
                cfg["style"]["palette"] = parse_colors(colors_text)
                return cfg

            fixed_text = _norm_text(cells[4]) if len(cells) > 4 else ""
            selected_days_text = cells[5] if len(cells) > 5 else ""
            focus_text = cells[6] if len(cells) > 6 else ""
            colors_text = cells[7] if len(cells) > 7 else ""

            if not fixed_text:
                raise RowParseError("Pregunta 4.1.1 está vacía: cuántas preguntas por día")
            if not _norm_text(selected_days_text):
                raise RowParseError("Pregunta 4.1.2 está vacía: días de la semana a estudiar")
            if not _norm_text(colors_text):
                raise RowParseError("Pregunta 6 está vacía: colores")

            cfg["intensity"]["mode"] = "fixed"
            cfg["intensity"]["fixed_q"] = _parse_int(fixed_text, "preguntas por día")
            cfg["calendar_rules"]["active_weekdays"] = parse_active_weekdays_list(selected_days_text)
        else:
            by_day_text = cells[4] if len(cells) > 4 else ""
            focus_text = cells[5] if len(cells) > 5 else ""
            colors_text = cells[6] if len(cells) > 6 else ""

            if not _norm_text(by_day_text):
                raise RowParseError("Pregunta 4.2.1 está vacía: días + número de preguntas")
            if not _norm_text(colors_text):
                raise RowParseError("Pregunta 6 está vacía: colores")

            cfg["intensity"]["mode"] = "by_weekday"
            by_weekday_q = parse_weekday_numbers(by_day_text)
            cfg["intensity"]["by_weekday_q"] = by_weekday_q
            cfg["calendar_rules"]["active_weekdays"] = [
                int(day) for day, qty in by_weekday_q.items() if int(qty) > 0
            ]

        cfg["extras"]["focus_subjects"] = [
            normalize_subject(x) for x in re.split(r"[,\n]+", focus_text) if _norm_text(x)
        ]
        cfg["style"]["palette"] = parse_colors(colors_text)
        return cfg

    if len(cells) < 11:
        raise RowParseError(
            "Fila incompleta o mal pegada para Tipo 1: se esperaban al menos 11 celdas (separadas por tab)"
        )

    # Mapeo fijo de Google Sheets para Tipo 1:
    # 0 timestamp, 1 email, 2 telefono, 3 nombre, 4 fecha inicio, 5 fecha fin,
    # 6 misma cantidad? (Sí/No), 7 preguntas/día, 8 bloque por día,
    # 9 refuerzo, 10 colores, 11 días seleccionados (opcional)
    student_name = _norm_text(cells[3])
    start_raw = _norm_text(cells[4])
    end_raw = _norm_text(cells[5])
    same_text = _norm_text(cells[6])
    fixed_text = _norm_text(cells[7])
    by_day_text = cells[8]
    focus_text = cells[9]
    colors_text = cells[10]
    selected_days_text = cells[11] if len(cells) > 11 else ""

    if not student_name:
        raise RowParseError("Nombre estudiante (columna 3) está vacío")

    if not _looks_like_date_token(start_raw):
        raise RowParseError("Parece que pegaste la fila mal: fecha inicio no válida")

    cfg["meta"]["student_name"] = student_name
    try:
        cfg["date_range"]["start"] = _parse_date_iso(start_raw, "fecha inicio")
    except RowParseError as exc:
        raise RowParseError("Parece que pegaste la fila mal: fecha inicio no válida") from exc
    cfg["date_range"]["end"] = _parse_date_iso(end_raw, "fecha fin")
    cfg["extras"]["focus_subjects"] = [normalize_subject(x) for x in re.split(r"[,\n]+", focus_text) if _norm_text(x)]
    cfg["style"]["palette"] = parse_colors(colors_text)

    same_everyday = _parse_boolish(same_text, "misma cantidad todos los días")
    if same_everyday:
        if not fixed_text:
            raise RowParseError("Preguntas por día (columna 7) está vacío y seleccionaste 'Sí'")
        cfg["intensity"]["mode"] = "fixed"
        cfg["intensity"]["fixed_q"] = _parse_int(fixed_text, "preguntas por día")
    else:
        cfg["intensity"]["mode"] = "by_weekday"
        by_weekday_q = parse_weekday_numbers(by_day_text)
        cfg["intensity"]["by_weekday_q"] = by_weekday_q
        cfg["calendar_rules"]["active_weekdays"] = [
            int(day) for day, qty in by_weekday_q.items() if int(qty) > 0
        ]

    if _norm_text(selected_days_text):
        cfg["calendar_rules"]["active_weekdays"] = parse_active_weekdays_list(selected_days_text)

    inferred_days = _infer_active_weekdays_from_cells(cells, start_idx=11)
    if inferred_days:
        cfg["calendar_rules"]["active_weekdays"] = inferred_days

    return cfg


def parse_row_type2(cells: List[str]) -> Dict[str, Any]:
    cfg = deepcopy(sample_cfg(2))

    # Formato compacto esperado desde Claude (preguntas 1..7):
    # 0 nombre, 1 fecha inicio, 2 fecha fin, 3 base por materia, 4 igual todos los días (Sí/No)
    # Si Sí: 5 días a estudiar, 6 refuerzo, 7 colores
    # Si No: 5 multiplicadores por día, 6 refuerzo, 7 colores
    compact_like = False
    if len(cells) >= 5:
        try:
            compact_like = (
                bool(_norm_text(cells[0]))
                and _looks_like_date_token(_norm_text(cells[1]))
                and _looks_like_date_token(_norm_text(cells[2]))
                and bool(_norm_text(cells[3]))
            )
            if compact_like:
                _parse_boolish(_norm_text(cells[4]), "igual todos los días")
        except RowParseError:
            compact_like = False

    if compact_like:
        student_name = _norm_text(cells[0])
        start_raw = _norm_text(cells[1])
        end_raw = _norm_text(cells[2])
        base_text = cells[3]
        same_text = _norm_text(cells[4])
        slot5_text = cells[5] if len(cells) > 5 else ""
        focus_text = cells[6] if len(cells) > 6 else ""
        colors_text = cells[7] if len(cells) > 7 else ""

        if not student_name:
            raise RowParseError("Pregunta 1 está vacía: nombre/apodo")
        if not _norm_text(base_text):
            raise RowParseError("Pregunta 4 está vacía: cantidad base por materia")
        if not _norm_text(colors_text):
            raise RowParseError("Pregunta 7 está vacía: colores")

        cfg["meta"]["student_name"] = student_name
        cfg["date_range"]["start"] = _parse_date_iso(start_raw, "fecha inicio")
        cfg["date_range"]["end"] = _parse_date_iso(end_raw, "fecha fin")
        cfg["intensity"]["per_subject_base_q"] = parse_subject_base_q(base_text)
        cfg["extras"]["focus_subjects"] = [
            normalize_subject(x) for x in re.split(r"[,\n]+", focus_text) if _norm_text(x)
        ]
        cfg["style"]["palette"] = parse_colors(colors_text)

        same_everyday = _parse_boolish(same_text, "igual todos los días")
        if same_everyday:
            cfg["intensity"]["multiplier_by_weekday"] = {str(i): 1.0 for i in range(7)}
            if _norm_text(slot5_text):
                cfg["calendar_rules"]["active_weekdays"] = parse_active_weekdays_list(slot5_text)
            else:
                cfg["calendar_rules"]["active_weekdays"] = [0, 1, 2, 3, 4]
        else:
            if not _norm_text(slot5_text):
                raise RowParseError("Pregunta 5.2 está vacía: multiplicadores por día")
            mult_map = parse_multipliers(slot5_text)
            cfg["intensity"]["multiplier_by_weekday"] = mult_map
            cfg["calendar_rules"]["active_weekdays"] = [
                int(day) for day, mult in mult_map.items() if float(mult) > 0
            ]

        return cfg

    if len(cells) < 11:
        raise RowParseError(
            "Fila incompleta o mal pegada para Tipo 2: se esperaban al menos 11 celdas (separadas por tab)"
        )

    # Mapeo fijo de Google Sheets para Tipo 2:
    # 0 timestamp, 1 email, 2 telefono, 3 nombre, 4 fecha inicio, 5 fecha fin,
    # 6 bases por materia, 7 igual todos los días? (Sí/No),
    # 8 multiplicadores por día, 9 refuerzo, 10 colores
    student_name = _norm_text(cells[3])
    start_raw = _norm_text(cells[4])
    end_raw = _norm_text(cells[5])
    base_text = cells[6]
    same_text = _norm_text(cells[7])
    multipliers_text = cells[8]
    focus_text = cells[9]
    colors_text = cells[10]

    if not student_name:
        raise RowParseError("Nombre estudiante (columna 3) está vacío")
    if not _looks_like_date_token(start_raw):
        raise RowParseError("Parece que pegaste la fila mal: fecha inicio no válida")

    cfg["meta"]["student_name"] = student_name
    try:
        cfg["date_range"]["start"] = _parse_date_iso(start_raw, "fecha inicio")
    except RowParseError as exc:
        raise RowParseError("Parece que pegaste la fila mal: fecha inicio no válida") from exc
    cfg["date_range"]["end"] = _parse_date_iso(end_raw, "fecha fin")
    cfg["extras"]["focus_subjects"] = [normalize_subject(x) for x in re.split(r"[,\n]+", focus_text) if _norm_text(x)]
    cfg["style"]["palette"] = parse_colors(colors_text)
    cfg["intensity"]["per_subject_base_q"] = parse_subject_base_q(base_text)

    same_everyday = _parse_boolish(same_text, "igual todos los días")
    if same_everyday:
        cfg["intensity"]["multiplier_by_weekday"] = {str(i): 1.0 for i in range(7)}
    else:
        mult_map = parse_multipliers(multipliers_text)
        cfg["intensity"]["multiplier_by_weekday"] = mult_map
        # En Tipo 2 sin lista explícita de días, los activos salen de multiplicadores > 0.
        cfg["calendar_rules"]["active_weekdays"] = [
            int(day) for day, mult in mult_map.items() if float(mult) > 0
        ]

    inferred_days = _infer_active_weekdays_from_cells(cells, start_idx=11)
    if inferred_days:
        cfg["calendar_rules"]["active_weekdays"] = inferred_days

    return cfg


def parse_row_type3(cells: List[str]) -> Dict[str, Any]:
    # Formato compacto esperado desde Claude (preguntas 1..7):
    # 0 nombre, 1 fecha inicio, 2 fecha fin, 3 misma cantidad (Sí/No),
    # Si Sí: 4 asignación por día (día: materia), 5 enfoque, 6 colores
    # Si No: 4 asignación por día + cantidad (día: materia cantidad), 5 enfoque, 6 colores
    compact_like = False
    if len(cells) >= 4:
        try:
            compact_like = (
                bool(_norm_text(cells[0]))
                and _looks_like_date_token(_norm_text(cells[1]))
                and _looks_like_date_token(_norm_text(cells[2]))
            )
            if compact_like:
                _parse_boolish(_norm_text(cells[3]), "misma cantidad todos los días")
        except RowParseError:
            compact_like = False

    if compact_like:
        cfg = deepcopy(sample_cfg(3))
        student_name = _norm_text(cells[0])
        start_raw = _norm_text(cells[1])
        end_raw = _norm_text(cells[2])
        same_text = _norm_text(cells[3])
        day_block_text = cells[4] if len(cells) > 4 else ""
        focus_text = cells[5] if len(cells) > 5 else ""
        colors_text = cells[6] if len(cells) > 6 else ""

        if not student_name:
            raise RowParseError("Pregunta 1 está vacía: nombre/apodo")
        if not _norm_text(day_block_text):
            raise RowParseError("Pregunta 5 está vacía: asignación por día")
        if not _norm_text(colors_text):
            raise RowParseError("Pregunta 7 está vacía: colores")

        cfg["meta"]["student_name"] = student_name
        cfg["date_range"]["start"] = _parse_date_iso(start_raw, "fecha inicio")
        cfg["date_range"]["end"] = _parse_date_iso(end_raw, "fecha fin")
        cfg["extras"]["focus_subjects"] = [
            normalize_subject(x) for x in re.split(r"[,\n]+", focus_text) if _norm_text(x)
        ]
        cfg["style"]["palette"] = parse_colors(colors_text)

        same_everyday = _parse_boolish(same_text, "misma cantidad todos los días")
        if same_everyday:
            _validate_single_subject_per_line(day_block_text, allow_qty_suffix=False)
            subject_by_weekday = parse_weekday_subjects(day_block_text)
            cfg["intensity"]["mode"] = "fixed"
            # Si no se pregunta explícitamente la cantidad fija, se usa el default del sample.
            cfg["assignments"]["subject_by_weekday"] = subject_by_weekday
        else:
            _validate_single_subject_per_line(day_block_text, allow_qty_suffix=True)
            cfg["intensity"]["mode"] = "by_weekday"
            subject_by_weekday, by_weekday_q = parse_weekday_subject_qty(day_block_text)
            cfg["assignments"]["subject_by_weekday"] = subject_by_weekday
            cfg["intensity"]["by_weekday_q"] = by_weekday_q

        cfg["calendar_rules"]["active_weekdays"] = [
            int(day) for day, subj in subject_by_weekday.items() if _norm_key(str(subj)) != "descanso"
        ]
        return cfg

    # Mapeo fijo de Google Sheets para Tipo 3 (formulario actual):
    # 0 timestamp, 1 email, 2 telefono, 3 nombre, 4 fecha inicio, 5 fecha fin,
    # 6 misma cantidad?, 7 cantidades por día, 8 preguntas fijas/día,
    # 9 asignación por día, 10 refuerzo, 11 colores
    if len(cells) >= 12 and _looks_like_date_token(_norm_text(cells[4])):
        cfg = deepcopy(sample_cfg(3))

        student_name = _norm_text(cells[3])
        start_raw = _norm_text(cells[4])
        end_raw = _norm_text(cells[5])
        same_text = _norm_text(cells[6])
        by_day_text = cells[7]
        fixed_text = _norm_text(cells[8])
        assign_text = cells[9]
        focus_text = cells[10]
        colors_text = cells[11]

        if not student_name:
            raise RowParseError("Nombre estudiante (columna 3) está vacío")
        if not _looks_like_date_token(start_raw):
            raise RowParseError("Parece que pegaste la fila mal: fecha inicio no válida")

        cfg["meta"]["student_name"] = student_name
        try:
            cfg["date_range"]["start"] = _parse_date_iso(start_raw, "fecha inicio")
        except RowParseError as exc:
            raise RowParseError("Parece que pegaste la fila mal: fecha inicio no válida") from exc
        cfg["date_range"]["end"] = _parse_date_iso(end_raw, "fecha fin")
        cfg["extras"]["focus_subjects"] = [
            normalize_subject(x) for x in re.split(r"[,\n]+", focus_text) if _norm_text(x)
        ]
        cfg["style"]["palette"] = parse_colors(colors_text)

        same_everyday = _parse_boolish(same_text, "misma cantidad todos los días")
        if same_everyday:
            if not fixed_text:
                raise RowParseError("Preguntas por día (columna 8) está vacío y seleccionaste 'Sí'")
            cfg["intensity"]["mode"] = "fixed"
            cfg["intensity"]["fixed_q"] = _parse_int(fixed_text, "preguntas por día")
            subject_by_weekday = parse_weekday_subjects(assign_text)
            cfg["assignments"]["subject_by_weekday"] = subject_by_weekday
        else:
            cfg["intensity"]["mode"] = "by_weekday"
            # Nuevo formulario Tipo 3:
            # 2.b contiene día + materia + preguntas (ej: "Martes: Sociales 30")
            # Mantiene compatibilidad con formato anterior si no viene así.
            try:
                subject_by_weekday, by_weekday_q = parse_weekday_subject_qty(by_day_text)
                cfg["assignments"]["subject_by_weekday"] = subject_by_weekday
                cfg["intensity"]["by_weekday_q"] = by_weekday_q
            except RowParseError:
                cfg["intensity"]["by_weekday_q"] = parse_weekday_numbers(by_day_text)
                subject_by_weekday = parse_weekday_subjects(assign_text)
                cfg["assignments"]["subject_by_weekday"] = subject_by_weekday

        # En Tipo 3, si no hay lista explícita de días, los activos salen de la asignación:
        # todo día distinto de "Descanso".
        cfg["calendar_rules"]["active_weekdays"] = [
            int(day) for day, subj in subject_by_weekday.items() if _norm_key(str(subj)) != "descanso"
        ]

        inferred_days = _infer_active_weekdays_from_cells(cells, start_idx=12)
        if inferred_days:
            cfg["calendar_rules"]["active_weekdays"] = inferred_days

        return cfg

    cfg = deepcopy(sample_cfg(3))
    labeled, unlabeled = _split_labeled_and_unlabeled(cells)
    _set_common(cfg, labeled, unlabeled)

    same_text = _get_value(
        labeled,
        unlabeled,
        ["misma cantidad todos los dias", "igual todos los dias", "intensidad fija"],
        5,
        "modo intensidad tipo 3",
    )
    same_everyday = _parse_boolish(same_text, "misma cantidad todos los días")

    if same_everyday:
        fixed = _parse_int(
            _get_value(labeled, unlabeled, ["preguntas por dia", "fixed_q", "cantidad"], 6, "preguntas por día"),
            "preguntas por día",
        )
        cfg["intensity"]["mode"] = "fixed"
        cfg["intensity"]["fixed_q"] = fixed
    else:
        by_day_text = _get_value(
            labeled,
            unlabeled,
            ["preguntas por dia", "by_weekday_q", "cantidades por dia"],
            6,
            "cantidades por día",
        )
        cfg["intensity"]["mode"] = "by_weekday"
        cfg["intensity"]["by_weekday_q"] = parse_weekday_numbers(by_day_text)

    assign_text = _get_value(
        labeled,
        unlabeled,
        ["asignacion por dia", "subject_by_weekday", "asignaciones"],
        7,
        "asignación por día",
    )
    subject_by_weekday = parse_weekday_subjects(assign_text)
    cfg["assignments"]["subject_by_weekday"] = subject_by_weekday
    cfg["calendar_rules"]["active_weekdays"] = [
        int(day) for day, subj in subject_by_weekday.items() if _norm_key(str(subj)) != "descanso"
    ]

    inferred_days = _infer_active_weekdays_from_cells(cells, start_idx=8)
    if inferred_days:
        cfg["calendar_rules"]["active_weekdays"] = inferred_days

    return cfg


def build_cfg_from_row(plan_type: int, row_text: str) -> Dict[str, Any]:
    cells = _extract_cells(row_text)

    if plan_type == 1:
        return parse_row_type1(cells)
    if plan_type == 2:
        return parse_row_type2(cells)
    if plan_type == 3:
        return parse_row_type3(cells)

    raise RowParseError("plan_type debe ser 1, 2 o 3")
