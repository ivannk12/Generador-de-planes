import unittest

from backend.app.row_parser import RowParseError, build_cfg_from_row


class RowParserType1Tests(unittest.TestCase):
    def test_type1_compact_yes_branch(self):
        cells = [
            "Fernanda",  # 1 nombre/apodo
            "22/2/2026",  # 2 fecha inicio
            "20/7/2026",  # 3 fecha fin
            "Sí",  # 4 misma cantidad?
            "25",  # 4.1.1 preguntas por día
            "Lunes, Miércoles, Viernes",  # 4.1.2 días a estudiar
            "Matemáticas, Lectura",  # 5 refuerzo
            "#A8D8FF,#FFB3B3,#B8F2C2",  # 6 colores
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(1, row_text)

        self.assertEqual(cfg["meta"]["student_name"], "Fernanda")
        self.assertEqual(cfg["date_range"]["start"], "2026-02-22")
        self.assertEqual(cfg["intensity"]["mode"], "fixed")
        self.assertEqual(cfg["intensity"]["fixed_q"], 25)
        self.assertEqual(cfg["calendar_rules"]["active_weekdays"], [0, 2, 4])

    def test_type1_compact_yes_branch_accepts_day_subject_block(self):
        cells = [
            "Sofía",
            "13/4/2026",
            "25/7/2026",
            "Sí",
            "lunes: Lectura Crítica\nmartes: Sociales y Ciudadanas\nmiércoles: Lectura Crítica\njueves: Sociales y Ciudadanas\nviernes: Lectura Crítica\nsábado: Sociales y Ciudadanas\ndomingo: Lectura Crítica",
            "Lectura Crítica, Sociales y Ciudadanas",
            "#FFECF2,#FFDCE8,#FFCCDD,#FABACC,#FFB6CF,#FAE4E2,#F9E0EA,#FCF1F5,#FBE9F3",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(1, row_text)

        self.assertEqual(cfg["meta"]["student_name"], "Sofía")
        self.assertEqual(cfg["intensity"]["mode"], "fixed")
        self.assertEqual(cfg["intensity"]["fixed_q"], 30)
        self.assertEqual(cfg["calendar_rules"]["active_weekdays"], [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(cfg["extras"]["focus_subjects"], ["Lectura Crítica", "Sociales y Ciudadanas"])

    def test_type1_compact_no_branch(self):
        cells = [
            "Fernanda",
            "22/2/2026",
            "20/7/2026",
            "No",
            "lunes 25\nmiércoles: 20\nviernes 15",
            "Matemáticas, Ciencias",
            "rosa,purpura,celeste",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(1, row_text)

        self.assertEqual(cfg["intensity"]["mode"], "by_weekday")
        self.assertEqual(cfg["intensity"]["by_weekday_q"]["0"], 25)
        self.assertEqual(cfg["intensity"]["by_weekday_q"]["2"], 20)
        self.assertEqual(cfg["intensity"]["by_weekday_q"]["4"], 15)
        self.assertEqual(cfg["calendar_rules"]["active_weekdays"], [0, 2, 4])

    def test_type1_parses_ddmmyyyy_dates(self):
        cells = [
            "10/02/2026 20:30:00",  # 0 timestamp
            "test@mail.com",  # 1 email
            "3001234567",  # 2 telefono
            "Sara",  # 3 nombre
            "5/2/2026",  # 4 fecha inicio
            "28/2/2026",  # 5 fecha fin
            "Sí",  # 6 misma cantidad
            "30",  # 7 preguntas al dia
            "Lunes: 30\nMartes: 30",  # 8 bloque por dia (no usado en fixed)
            "Matemáticas, Ciencias",  # 9 refuerzo
            "#A8D8FF, #FFB3B3",  # 10 colores
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(1, row_text)

        self.assertEqual(cfg["meta"]["student_name"], "Sara")
        self.assertEqual(cfg["date_range"]["start"], "2026-02-05")
        self.assertEqual(cfg["date_range"]["end"], "2026-02-28")
        self.assertEqual(cfg["intensity"]["mode"], "fixed")
        self.assertEqual(cfg["intensity"]["fixed_q"], 30)

    def test_type1_detects_wrong_paste_when_phone_in_start_date(self):
        cells = [
            "10/02/2026 20:30:00",
            "test@mail.com",
            "3001234567",
            "Sara",
            "3001234567",  # fecha inicio invalida (telefono)
            "28/2/2026",
            "Sí",
            "30",
            "Lunes: 30\nMartes: 30",
            "Matemáticas, Ciencias",
            "#A8D8FF, #FFB3B3",
        ]
        row_text = "\t".join(cells)

        with self.assertRaises(RowParseError) as ctx:
            build_cfg_from_row(1, row_text)

        self.assertIn("Parece que pegaste la fila mal: fecha inicio no válida", str(ctx.exception))

    def test_type1_requires_minimum_columns(self):
        row_text = "\t".join(["a", "b", "c"])
        with self.assertRaises(RowParseError) as ctx:
            build_cfg_from_row(1, row_text)

        self.assertIn("se esperaban al menos 11 celdas", str(ctx.exception))

    def test_type1_expands_palette_to_10_with_pattern(self):
        cells = [
            "10/02/2026 20:30:00",
            "test@mail.com",
            "3001234567",
            "Sara",
            "5/2/2026",
            "28/2/2026",
            "Sí",
            "30",
            "Lunes: 30\nMartes: 30",
            "Matemáticas, Ciencias",
            "azul, verde, naranja",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(1, row_text)
        palette = cfg["style"]["palette"]
        self.assertEqual(len(palette), 10)
        self.assertEqual(palette, ["azul", "verde", "naranja", "azul", "verde", "naranja", "azul", "verde", "naranja", "azul"])

    def test_type1_accepts_no_with_emoji_and_quoted_weekday_block(self):
        cells = [
            "11/2/2026 20:41:20",
            "ivan@example.com",
            "3168695397",
            "Iván Camilo Gómez",
            "12/2/2026",
            "15/2/2026",
            "No ❌",
            "",
            "\"Lunes: 20\nMartes: 50\nMiércoles: 70\nJueves: 20\nViernes: 10\nSábado: 10\nDomingo: 40\"",
            "Matemáticas",
            "azul, verde, naranja",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(1, row_text)

        self.assertEqual(cfg["intensity"]["mode"], "by_weekday")
        self.assertEqual(cfg["intensity"]["by_weekday_q"]["0"], 20)
        self.assertEqual(cfg["intensity"]["by_weekday_q"]["6"], 40)
        self.assertIn(5, cfg["calendar_rules"]["active_weekdays"])
        self.assertIn(6, cfg["calendar_rules"]["active_weekdays"])

    def test_type1_accepts_descanso_as_zero_in_weekday_block(self):
        cells = [
            "Andrea Paola Morales Vega",
            "9/4/2026",
            "26/7/2026",
            "No",
            "Lunes: Descanso\nMartes: Matemáticas 20\nMiércoles: Matemáticas 20\nJueves: Matemáticas 20\nViernes: Matemáticas 20\nSábado: Matemáticas 20\nDomingo: Descanso",
            "Matemáticas, Ciencias Naturales, Inglés",
            "#2E8B57,#1D4ED8,#D4A017,#E75480,#7B2CBF",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(1, row_text)

        self.assertEqual(cfg["intensity"]["mode"], "by_weekday")
        self.assertEqual(cfg["intensity"]["by_weekday_q"]["0"], 0)
        self.assertEqual(cfg["intensity"]["by_weekday_q"]["1"], 20)
        self.assertEqual(cfg["intensity"]["by_weekday_q"]["5"], 20)
        self.assertEqual(cfg["intensity"]["by_weekday_q"]["6"], 0)
        self.assertEqual(cfg["calendar_rules"]["active_weekdays"], [1, 2, 3, 4, 5])

    def test_type1_accepts_zero_in_weekday_block(self):
        cells = [
            "Andrea Paola Morales Vega",
            "9/4/2026",
            "26/7/2026",
            "No",
            "Lunes: 0\nMartes: 20\nMiércoles: 20\nJueves: 20\nViernes: 20\nSábado: 20\nDomingo: 0",
            "Matemáticas, Ciencias Naturales, Inglés",
            "#2E8B57,#1D4ED8,#D4A017,#E75480,#7B2CBF",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(1, row_text)

        self.assertEqual(cfg["intensity"]["by_weekday_q"]["0"], 0)
        self.assertEqual(cfg["intensity"]["by_weekday_q"]["6"], 0)
        self.assertEqual(cfg["calendar_rules"]["active_weekdays"], [1, 2, 3, 4, 5])


if __name__ == "__main__":
    unittest.main()


class RowParserType2Tests(unittest.TestCase):
    def test_type2_accepts_json_cells_with_prefix_text(self):
        row_text = (
            '1:47 PM{"cells":["Martin Alonso Cogollo Jay","15/2/2026","20/7/2026",'
            '"Matemáticas: 25\\nLectura Crítica: 35\\nSociales y Ciudadanas: 40\\nCiencias Naturales: 40\\nInglés: 35",'
            '"Sí","Martes, Jueves, Sábado, Domingo","Lectura Crítica, Sociales y Ciudadanas, Ciencias Naturales",'
            '"#1D4ED8, #111827, #F8FAFC, #E75480, #D62828"]}'
        )

        cfg = build_cfg_from_row(2, row_text)
        self.assertEqual(cfg["meta"]["student_name"], "Martin Alonso Cogollo Jay")
        self.assertEqual(cfg["intensity"]["multiplier_by_weekday"]["0"], 1.0)
        self.assertEqual(cfg["calendar_rules"]["active_weekdays"], [1, 3, 5, 6])

    def test_type2_compact_yes_branch(self):
        cells = [
            "Kevin",
            "16/2/2026",
            "26/7/2026",
            "Matemáticas: 20\nLectura Crítica: 15\nSociales y Ciudadanas: 10\nCiencias Naturales: 10\nInglés: 10",
            "Sí",
            "Lunes, Martes, Miércoles, Jueves, Viernes, Sábado",
            "Matemáticas, Lectura Crítica",
            "#1D4ED8,#2E8B57,#D62828,#D4A017,#E67E22,#7B2CBF,#111827,#8B5A2B,#C9A84C,#1A3A5C",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(2, row_text)

        self.assertEqual(cfg["meta"]["student_name"], "Kevin")
        self.assertEqual(cfg["date_range"]["start"], "2026-02-16")
        self.assertEqual(cfg["intensity"]["per_subject_base_q"]["Matemáticas"], 20)
        self.assertEqual(cfg["intensity"]["multiplier_by_weekday"]["0"], 1.0)
        self.assertEqual(cfg["calendar_rules"]["active_weekdays"], [0, 1, 2, 3, 4, 5])

    def test_type2_compact_no_branch(self):
        cells = [
            "Kevin",
            "16/2/2026",
            "26/7/2026",
            "Matemáticas: 20\nLectura Crítica: 15\nSociales y Ciudadanas: 10\nCiencias Naturales: 10\nInglés: 10",
            "No",
            "lunes x2\nmartes: x1.5\nmiércoles x1\njueves: x0.5\nviernes x1\nsábado x0\ndomingo x0",
            "Matemáticas, Lectura Crítica",
            "azul,verde,rojo,amarillo,naranja,morado,negro,marron",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(2, row_text)

        self.assertEqual(cfg["intensity"]["multiplier_by_weekday"]["0"], 2.0)
        self.assertEqual(cfg["intensity"]["multiplier_by_weekday"]["1"], 1.5)
        self.assertEqual(cfg["intensity"]["multiplier_by_weekday"]["3"], 0.5)
        self.assertEqual(cfg["calendar_rules"]["active_weekdays"], [0, 1, 2, 3, 4])

    def test_type2_parses_fixed_columns_without_confusing_phone_as_start_date(self):
        cells = [
            "11/2/2026 21:21:07",
            "ivancamilogomezg12@gmail.com",
            "3168695397",
            "Iván Gómez",
            "12/2/2026",
            "15/2/2026",
            "Matemáticas: 20\nLectura Crítica: 10\nSociales y Ciudadanas: 5\nCiencias Naturales: 5\nInglés: 10",
            "No ❌",
            "\"Lunes: x2\nMartes: x2\nMiércoles: x1\"",
            "Matemáticas",
            "azul, verde, naranja",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(2, row_text)

        self.assertEqual(cfg["meta"]["student_name"], "Iván Gómez")
        self.assertEqual(cfg["date_range"]["start"], "2026-02-12")
        self.assertEqual(cfg["date_range"]["end"], "2026-02-15")
        self.assertEqual(cfg["intensity"]["per_subject_base_q"]["Matemáticas"], 20)
        self.assertEqual(cfg["intensity"]["multiplier_by_weekday"]["0"], 2.0)
        self.assertEqual(cfg["intensity"]["multiplier_by_weekday"]["2"], 1.0)


class RowParserType3Tests(unittest.TestCase):
    def test_type3_compact_yes_branch_requires_all_subjects(self):
        cells = [
            "Fernanda",
            "22/2/2026",
            "20/7/2026",
            "Sí",
            "lunes: Matemáticas\nmartes: Lectura Crítica\nmiércoles: Sociales y Ciudadanas\njueves: Ciencias Naturales\nviernes: Inglés\nsábado: Descanso\ndomingo: Descanso",
            "Matemáticas, Lectura Crítica",
            "#1D4ED8,#2E8B57,#D62828,#D4A017,#E67E22",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(3, row_text)
        self.assertEqual(cfg["intensity"]["mode"], "fixed")
        self.assertEqual(cfg["assignments"]["subject_by_weekday"]["0"], "Matemáticas")
        self.assertEqual(cfg["calendar_rules"]["active_weekdays"], [0, 1, 2, 3, 4])

    def test_type3_compact_no_branch_with_qty(self):
        cells = [
            "Fernanda",
            "22/2/2026",
            "20/7/2026",
            "No",
            "lunes: Matemáticas 25\nmartes: Lectura Crítica 20\nmiércoles: Sociales y Ciudadanas 15\njueves: Ciencias Naturales 15\nviernes: Inglés 15\nsábado: Descanso\ndomingo: Descanso",
            "Matemáticas, Ciencias Naturales",
            "rosa,purpura,celeste,marron,verde",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(3, row_text)
        self.assertEqual(cfg["intensity"]["mode"], "by_weekday")
        self.assertEqual(cfg["intensity"]["by_weekday_q"]["0"], 25)
        self.assertEqual(cfg["assignments"]["subject_by_weekday"]["1"], "Lectura Crítica")
        self.assertEqual(cfg["calendar_rules"]["active_weekdays"], [0, 1, 2, 3, 4])

    def test_type3_compact_allows_incomplete_subject_coverage(self):
        cells = [
            "Fernanda",
            "22/2/2026",
            "20/7/2026",
            "Sí",
            "lunes: Matemáticas\nmartes: Lectura Crítica\nmiércoles: Descanso\njueves: Descanso\nviernes: Descanso",
            "Matemáticas",
            "#1D4ED8,#2E8B57,#D62828,#D4A017,#E67E22",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(3, row_text)
        self.assertEqual(cfg["intensity"]["mode"], "fixed")
        self.assertEqual(cfg["assignments"]["subject_by_weekday"]["0"], "Matemáticas")
        self.assertEqual(cfg["assignments"]["subject_by_weekday"]["1"], "Lectura Crítica")
        self.assertEqual(cfg["calendar_rules"]["active_weekdays"], [0, 1])

    def test_type3_accepts_json_cells_payload(self):
        row_json = (
            '{"cells":["15/2/2026 12:14:28","mariafernandatorresmosquera54@gmail.com","3137704051",'
            '"fernanda","22/2/2026","20/7/2026","Si","","25","lunes: Matemáticas\\nmartes: Descanso\\nmiércoles: Sociales y Ciudadanas\\njueves: Descanso\\nviernes: Inglés\\nsábado: Ciencias Naturales",'
            '"🧮 Matemáticas, 📖 Lectura Crítica, 🌎 Sociales y Ciudadanas, 🌿 Ciencias Naturales, 🇺🇸 Inglés",'
            '"rosa,morado,celeste,marron,verde"]}'
        )

        cfg = build_cfg_from_row(3, row_json)
        self.assertEqual(cfg["meta"]["student_name"], "fernanda")
        self.assertEqual(cfg["date_range"]["start"], "2026-02-22")
        self.assertEqual(cfg["assignments"]["subject_by_weekday"]["0"], "Matemáticas")

    def test_type3_accepts_assignments_without_colon_and_day_typos(self):
        cells = [
            "15/2/2026 12:14:28",
            "mariafernandatorresmosquera54@gmail.com",
            "3137704051",
            "fernanda",
            "22/2/2026",
            "20/7/2026",
            "Si",
            "",
            "25",
            "\"lunes matemática\nmarte descanso\nmiércoles sociales\njueves descanso\nviernes ingles\nsábado lectura critica  y cieencias\"",
            "🧮 Matemáticas, 📖 Lectura Crítica, 🌎 Sociales y Ciudadanas, 🌿 Ciencias Naturales, 🇺🇸 Inglés",
            "rosa,purpura,celeste,marronw,verde",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(3, row_text)
        by_day = cfg["assignments"]["subject_by_weekday"]

        self.assertEqual(by_day["0"], "Matemáticas")
        self.assertEqual(by_day["1"], "Descanso")
        self.assertEqual(by_day["2"], "Sociales y Ciudadanas")
        self.assertEqual(by_day["4"], "Inglés")
        self.assertEqual(by_day["5"], "Lectura Crítica")

    def test_type3_accepts_ten_compound_color_names(self):
        cells = [
            "14/2/2026 9:23:00",
            "isabellapc324@gmail.com",
            "316 8695397",
            "Pardo",
            "16/2/2026",
            "26/7/2026",
            "Si",
            "",
            "20",
            "\"Lunes: Lectura Crítica\nMartes: ciencias naturales\nMiércoles: matemáticas\nJueves: sociales\nViernes: inglés\nSábado: descanso\nDomingo: todo\"",
            "🌎 Sociales y Ciudadanas, 🌿 Ciencias Naturales",
            "Rojo pastel, naranja pastel, salmón, amarillo pastel, verde pastel, menta, aguamarina, celeste, rosa pastel, lavanda",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(3, row_text)
        palette = cfg["style"]["palette"]

        self.assertEqual(len(palette), 10)
        self.assertEqual(
            palette,
            [
                "Rojo pastel",
                "naranja pastel",
                "salmón",
                "amarillo pastel",
                "verde pastel",
                "menta",
                "aguamarina",
                "celeste",
                "rosa pastel",
                "lavanda",
            ],
        )

    def test_type3_accepts_clear_color_names_and_trailing_dot(self):
        cells = [
            "14/2/2026 9:41:17",
            "angellymuelascalambas@gmail.com",
            "3215071969",
            "Angelly",
            "15/2/2026",
            "25/7/2026",
            "Si",
            "",
            "25",
            "\"Lunes: ingles\nMartes: lectura crítica\nMiércoles: sociales\nJueves: matemáticas\nViernes: ciencias\nSábado: matemáticas\nDomingo: ciencias\"",
            "🧮 Matemáticas, 📖 Lectura Crítica, 🌿 Ciencias Naturales",
            "Negro, cian, morado claro, rojo claro, verde claro.",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(3, row_text)
        palette = cfg["style"]["palette"]

        self.assertEqual(len(palette), 10)
        self.assertEqual(
            palette,
            [
                "Negro",
                "cian",
                "morado claro",
                "rojo claro",
                "verde claro",
                "Negro",
                "cian",
                "morado claro",
                "rojo claro",
                "verde claro",
            ],
        )

    def test_type3_accepts_common_typo_calro_in_colors(self):
        cells = [
            "14/2/2026 9:41:17",
            "angellymuelascalambas@gmail.com",
            "3215071969",
            "Angelly",
            "15/2/2026",
            "25/7/2026",
            "Si",
            "",
            "25",
            "\"Lunes: ingles\nMartes: lectura crítica\nMiércoles: sociales\nJueves: matemáticas\nViernes: ciencias\nSábado: matemáticas\nDomingo: ciencias\"",
            "🧮 Matemáticas, 📖 Lectura Crítica, 🌿 Ciencias Naturales",
            "Negro, cian, morado calro, rojo calro, verde calro.",
        ]
        row_text = "\t".join(cells)

        cfg = build_cfg_from_row(3, row_text)
        palette = cfg["style"]["palette"]

        self.assertEqual(len(palette), 10)
        self.assertEqual(
            palette,
            [
                "Negro",
                "cian",
                "morado claro",
                "rojo claro",
                "verde claro",
                "Negro",
                "cian",
                "morado claro",
                "rojo claro",
                "verde claro",
            ],
        )
