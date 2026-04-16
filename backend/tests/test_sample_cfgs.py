import unittest

from backend.app.sample_cfgs import BOOKLET_SEQUENCE, sample_cfg


class SampleCfgBookletSequenceTests(unittest.TestCase):
    def test_booklet_sequence_inserts_2025_cal_a_v2_after_vip_9(self):
        sequence_ids = [booklet["id"] for booklet in BOOKLET_SEQUENCE]

        self.assertEqual(
            sequence_ids[:6],
            [
                "BK-2025A-1",
                "BK-2025B-2",
                "BK-2025B-1",
                "BK-VIP-9",
                "BK-2025A-2",
                "BK-VIP-8",
            ],
        )

    def test_type_1_global_booklets_keep_new_sequence(self):
        cfg = sample_cfg(1)
        sequence_ids = [booklet["id"] for booklet in cfg["content"]["global_booklets"]]

        self.assertEqual(sequence_ids[3:6], ["BK-VIP-9", "BK-2025A-2", "BK-VIP-8"])


if __name__ == "__main__":
    unittest.main()
