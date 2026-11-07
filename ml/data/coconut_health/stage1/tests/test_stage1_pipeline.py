"""End-to-end data-quality tests for the Stage 1 prototype pipeline."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
STAGE_DIR = ROOT / "ml" / "data" / "coconut_health"
SOURCE_OUTPUT = STAGE_DIR / "data" / "cococare_stage1_outputs"
GENERATOR = STAGE_DIR / "cococare_stage1_final_generator.py"
EVALUATOR = STAGE_DIR / "evaluvation " / "cococare_stage1_evaluation.py"


class Stage1PipelineTests(unittest.TestCase):
    def test_frozen_weather_run_is_complete_and_mass_balanced(self):
        """A saved NASA snapshot must reproduce a complete, closed bucket run."""
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "outputs"
            env = os.environ | {
                "COCOCARE_OUTPUT_DIR": str(output_dir),
                "COCOCARE_WEATHER_CSV": str(SOURCE_OUTPUT / "coimbatore_nasa_power_weather.csv"),
                "MPLBACKEND": "Agg",
            }
            subprocess.run([sys.executable, str(GENERATOR)], cwd=STAGE_DIR, env=env, check=True)
            subprocess.run([sys.executable, str(EVALUATOR)], cwd=STAGE_DIR, env=env, check=True)

            dataset = pd.read_csv(output_dir / "stage1_hybrid_dataset.csv")
            self.assertEqual(len(dataset), 365)
            self.assertFalse(dataset["date"].duplicated().any())
            self.assertEqual(int(dataset.isna().sum().sum()), 0)

            taw = 58.5
            previous = dataset["soil_water_storage_mm_modelled"].shift(1)
            reconstructed = (
                previous + dataset["effective_rainfall_mm_modelled"]
                + dataset["irrigation_mm_simulated"]
                - dataset["actual_et_mm_day_modelled"]
                - dataset["drainage_mm_modelled"]
            )
            self.assertLess((dataset["soil_water_storage_mm_modelled"].iloc[1:] - reconstructed.iloc[1:]).abs().max(), 1e-8)
            self.assertTrue((dataset["soil_water_storage_mm_modelled"] <= taw + 1e-8).all())

            summary = json.loads((output_dir / "evaluation_reports" / "evaluation_summary.json").read_text())
            self.assertEqual(summary["dataset_shape"]["source_columns"], len(dataset.columns))
            self.assertEqual(summary["integrity"]["source_missing_cells"], 0)
            checklist = pd.read_csv(output_dir / "evaluation_reports" / "pipeline_checklist.csv")
            self.assertTrue(checklist["passed"].all())


if __name__ == "__main__":
    unittest.main()
