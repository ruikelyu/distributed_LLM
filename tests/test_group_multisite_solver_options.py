import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "08_code" / "run_group_architecture_core.py"


class TestGroupMultisiteSolverOptions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("group_multisite", SCRIPT)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.module)

    def test_gurobi_options_are_forwarded_from_config(self):
        config = {
            "model": {
                "solver": {
                    "name": "gurobi",
                    "mip_gap": 0.001,
                    "threads": 5,
                    "log_to_console": False,
                }
            }
        }
        self.assertEqual(
            self.module.build_solver_options(config, "gurobi"),
            {"Threads": 5, "MIPGap": 0.001, "LogToConsole": 0},
        )

    def test_solver_name_mismatch_is_rejected(self):
        config = {"model": {"solver": {"name": "gurobi", "threads": 5}}}
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.module.build_solver_options(config, "highs")

    def test_options_are_expanded_into_linopy_solve_kwargs(self):
        class FakeModel:
            def __init__(self):
                self.kwargs = None

            def solve(self, **kwargs):
                self.kwargs = kwargs
                return "ok", "optimal"

        config = {
            "model": {
                "solver": {
                    "name": "gurobi",
                    "mip_gap": 0.001,
                    "threads": 5,
                    "log_to_console": False,
                }
            }
        }
        model = FakeModel()
        result = self.module.solve_with_configured_options(model, config, "gurobi")
        self.assertEqual(result, ("ok", "optimal"))
        self.assertEqual(
            model.kwargs,
            {
                "solver_name": "gurobi",
                "Threads": 5,
                "MIPGap": 0.001,
                "LogToConsole": 0,
                "env": {"Threads": 5},
            },
        )


if __name__ == "__main__":
    unittest.main()
