import unittest

from core.timecode import parse_clip_range


class ParseClipRangeTests(unittest.TestCase):
    def test_full_range_is_supported(self):
        self.assertEqual(parse_clip_range("full"), (0.0, 0.0))

    def test_regular_range_still_parses(self):
        self.assertEqual(parse_clip_range("1:00 - 2:00"), (60.0, 120.0))


if __name__ == "__main__":
    unittest.main()
