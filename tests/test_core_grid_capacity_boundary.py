from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "08_code"))

from core.model import incremental_grid_capacity_mw, resolve_existing_grid_capacity


class CoreGridCapacityBoundaryTests(unittest.TestCase):
    def test_no_ai_solve_defaults_to_raw_base_load_peak(self) -> None:
        base = np.array([3.0, 7.0, 5.0])
        self.assertEqual(resolve_existing_grid_capacity(base, None), 7.0)

    def test_ai_solve_uses_supplied_optimized_no_ai_net_peak(self) -> None:
        base = np.array([3.0, 7.0, 5.0])
        self.assertEqual(resolve_existing_grid_capacity(base, 4.25), 4.25)

    def test_invalid_supplied_capacity_is_rejected(self) -> None:
        base = np.array([3.0, 7.0, 5.0])
        for value in (-1.0, np.nan, np.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_existing_grid_capacity(base, value)

    def test_incremental_capacity_is_positive_net_peak_difference(self) -> None:
        self.assertEqual(incremental_grid_capacity_mw(9.5, 7.0), 2.5)
        self.assertEqual(incremental_grid_capacity_mw(6.0, 7.0), 0.0)

    def test_invalid_grid_peaks_are_rejected(self) -> None:
        for values in ((-1.0, 2.0), (2.0, -1.0), (np.nan, 2.0), (2.0, np.inf)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                incremental_grid_capacity_mw(*values)


if __name__ == "__main__":
    unittest.main()
