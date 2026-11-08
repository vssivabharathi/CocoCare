#!/usr/bin/env python3
"""
CocoCare Stage 3 — baseline ML experiments
==========================================

Input:
  ml/data/coconut_health/stage3/data/cococare_stage3_outputs/
      stage3_combined_scenarios.csv

Default output (beside this script):
  stage3_ml_baseline_outputs/
      tables/ figures/ models/ reports/

Tasks:
  1) Current-day classification: day-t inputs -> day-t rule-derived stress label
  2) Next-day prediction: day-t inputs -> day-(t+1) rule-derived stress label

Feature groups:
  A. weather_baseline: weather + ET0
  B. scenario_aware: weather + ET0 + scenario
  C. intervention_aware: weather + ET0 + scenario + day-t irrigation litres

Evaluation:
  - Date-grouped random 70/15/15 exploratory benchmark.
  - Model selection uses validation macro-F1, then validation balanced accuracy.
  - Selected pipeline is refit on train+validation and evaluated on test.
  - Chronological split is reported separately as a temporal diagnostic.
  - Permutation importance is calculated on validation data, not test data.

Research limitation:
  water_stress_rule_derived is produced by the same provisional simulation
  whose scenarios are being compared. Results measure reproduction of
  simulated labels, not field-validated coconut stress prediction or proof
  of irrigation efficacy.

Important feature caveats:
  - Intervention-aware uses the irrigation volume recorded on input day t.
    It is only operationally available if that volume is already known when
    the prediction is made.
  - In the model-triggered scenario, irrigation volume is computed from
    simulated depletion. This creates a strong mechanistic relationship
    with the simulated target; treat this feature group as an exploratory
    ablation, not independent predictive evidence.
  - Current-day intervention-aware classification is especially descriptive:
    same-day irrigation may be an action taken after a stress decision.

Run from this directory:
  python stage3_baseline_ml.py

Optional:
  python stage3_baseline_ml.py --data /path/to/stage3_combined_scenarios.csv
  python stage3_baseline_ml.py --output /path/to/output_folder
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier


SEED = 42
DATE_COL = "date"
SCENARIO_COL = "scenario"
TARGET_COL = "water_stress_rule_derived"
CLASSES = ["low", "moderate", "high"]

WEATHER_FEATURES = [
    "rainfall_mm",
    "tmax_c",
    "tmin_c",
    "solar_radiation_mj_m2_day",
    "relative_humidity_pct",
    "wind_speed_m_s",
    "et0_mm_day",
]
IRRIGATION_FEATURE = "irrigation_litres_per_palm_simulated"

EXPECTED_SCENARIOS = {
    "weather_only",
    "tnau_guided_irrigation",
    "model_triggered_irrigation",
}

FEATURE_GROUPS = {
    "weather_baseline": {
        "numeric": WEATHER_FEATURES,
        "categorical": [],
    },
    "scenario_aware": {
        "numeric": WEATHER_FEATURES,
        "categorical": [SCENARIO_COL],
    },
    "intervention_aware": {
        "numeric": WEATHER_FEATURES + [IRRIGATION_FEATURE],
        "categorical": [SCENARIO_COL],
    },
}

EXCLUDED_FEATURES = {
    "effective_rainfall_mm_modelled": "Derived water-balance intermediate",
    "runoff_mm_modelled": "Derived water-balance intermediate",
    "irrigation_mm_simulated": "Duplicate transformation of irrigation litres under assumed wetted area",
    "actual_et_mm_day_modelled": "Downstream water-balance output",
    "drainage_mm_modelled": "Downstream water-balance output",
    "soil_water_storage_mm_modelled": "Direct state used to derive stress label",
    "depletion_fraction_modelled": "Direct variable used to derive stress label",
    "depletion_before_irrigation_fraction_modelled": "Direct trigger variable used by model-triggered policy",
    "soil_moisture_vwc_pct_simulated": "Simulated state derived from storage",
    "recommended_action_simulated": "Action derived from target label",
    TARGET_COL: "Prediction target; never an input feature",
    "soil_temperature_c": "Intentionally unmodelled and entirely missing",
    "simulated_palm_age_months": "Simulation clock/metadata; no independent age variation",
    "weather_source": "Source metadata",
    "weather_source_url": "Source metadata",
    "soil_temperature_status": "Status metadata",
    "model_status": "Status metadata",
    "stress_label_status": "Status metadata",
    "location": "Constant metadata",
    "latitude": "Constant metadata",
    "longitude": "Constant metadata",
    "variety": "Constant metadata",
    "data_class": "Metadata",
}


def parse_args():
    script_dir = Path(__file__).resolve().parent
    # Find the CocoCare repository root by locating its top-level ml/ folder.
    # This also allows --data to be used when testing the script elsewhere.
    candidates = [script_dir, *script_dir.parents]
    repo_root = next(
        (parent for parent in candidates if (parent / "ml").is_dir()),
        script_dir,
    )
    default_data = (
        repo_root
        / "ml/data/coconut_health/stage3/data/cococare_stage3_outputs/"
          "stage3_combined_scenarios.csv"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", default=str(default_data),
        help="Path to stage3_combined_scenarios.csv",
    )
    parser.add_argument(
        "--output",
        default=str(script_dir / "stage3_ml_baseline_outputs"),
        help="Output folder; defaults to a folder beside this script",
    )
    parser.add_argument(
        "--permutation-repeats", type=int, default=10,
        help="Permutation importance repeats on validation data; use 0 to skip",
    )
    return parser.parse_args()


def create_output_dirs(root: Path):
    result = {"root": root}
    for name in ["tables", "figures", "models", "reports"]:
        result[name] = root / name
        result[name].mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    return result


def load_and_validate(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Stage 3 combined dataset not found: {path}\n"
            "Pass the correct file using --data."
        )
    df = pd.read_csv(path)
    required = [
        DATE_COL, SCENARIO_COL, TARGET_COL,
        *WEATHER_FEATURES, IRRIGATION_FEATURE,
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Required columns missing: {missing}")

    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="raise").dt.normalize()
    df = df.sort_values([SCENARIO_COL, DATE_COL]).reset_index(drop=True)

    if df.duplicated([DATE_COL, SCENARIO_COL]).any():
        raise ValueError("Duplicate date-scenario records found.")

    found_scenarios = set(df[SCENARIO_COL].dropna().unique())
    if found_scenarios != EXPECTED_SCENARIOS:
        raise ValueError(
            f"Expected exactly {sorted(EXPECTED_SCENARIOS)}, "
            f"found {sorted(found_scenarios)}."
        )

    per_date = df.groupby(DATE_COL)[SCENARIO_COL].nunique()
    if not (per_date == 3).all():
        raise ValueError("Every date must have exactly three scenario records.")

    for scenario, part in df.groupby(SCENARIO_COL):
        dates = part[DATE_COL].sort_values()
        if dates.duplicated().any():
            raise ValueError(f"Duplicate dates in scenario {scenario}.")
        if not (dates.diff().dropna() == pd.Timedelta(days=1)).all():
            raise ValueError(
                f"Non-consecutive dates in {scenario}; next-day target alignment "
                "cannot be assumed."
            )

    # Same weather must be used for all three scenarios on each date.
    for col in WEATHER_FEATURES:
        wide = df.pivot(index=DATE_COL, columns=SCENARIO_COL, values=col)
        values = wide[list(sorted(EXPECTED_SCENARIOS))].to_numpy(dtype=float)
        if not np.allclose(values, values[:, [0]], equal_nan=True):
            raise ValueError(f"Weather differs across scenarios for {col}.")

    for col in WEATHER_FEATURES + [IRRIGATION_FEATURE]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df[WEATHER_FEATURES].isna().any().any():
        raise ValueError("Required weather feature values contain missing data.")
    if df[IRRIGATION_FEATURE].isna().any():
        raise ValueError("Irrigation feature contains missing values.")
    if df[TARGET_COL].isna().any():
        raise ValueError("Target labels contain missing values.")
    unexpected = set(df[TARGET_COL].unique()) - set(CLASSES)
    if unexpected:
        raise ValueError(f"Unexpected target labels: {sorted(unexpected)}")

    return df


def prepare_objectives(df: pd.DataFrame):
    data = df.sort_values([SCENARIO_COL, DATE_COL]).copy()
    data["target_current"] = data[TARGET_COL]
    data["target_date_current"] = data[DATE_COL]

    grouped = data.groupby(SCENARIO_COL, sort=False)
    data["target_next_day"] = grouped[TARGET_COL].shift(-1)
    data["target_date_next"] = grouped[DATE_COL].shift(-1)

    valid = data["target_date_next"].notna()
    delta = data.loc[valid, "target_date_next"] - data.loc[valid, DATE_COL]
    if not (delta == pd.Timedelta(days=1)).all():
        raise ValueError("Next-day target is not exactly one calendar day ahead.")

    return {
        "current_day": (data.copy(), "target_current", "target_date_current"),
        "next_day": (
            data.loc[valid].copy(), "target_next_day", "target_date_next"
        ),
    }


def grouped_random_split(data: pd.DataFrame, target_date_col: str):
    """70/15/15 split with every scenario for a target date kept together."""
    data = data.reset_index(drop=True)
    train_idx, temp_idx = next(
        GroupShuffleSplit(
            n_splits=1, test_size=0.30, random_state=SEED
        ).split(data, groups=data[target_date_col])
    )
    train = data.iloc[train_idx].copy()
    temp = data.iloc[temp_idx].copy()

    val_idx, test_idx = next(
        GroupShuffleSplit(
            n_splits=1, test_size=0.50, random_state=SEED + 1
        ).split(temp, groups=temp[target_date_col])
    )
    return train, temp.iloc[val_idx].copy(), temp.iloc[test_idx].copy()


def chronological_split(data: pd.DataFrame, target_date_col: str):
    data = data.sort_values(target_date_col).copy()
    unique_dates = np.sort(data[target_date_col].unique())
    n = len(unique_dates)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)
    train_dates = set(unique_dates[:train_end])
    val_dates = set(unique_dates[train_end:val_end])
    test_dates = set(unique_dates[val_end:])
    return (
        data[data[target_date_col].isin(train_dates)].copy(),
        data[data[target_date_col].isin(val_dates)].copy(),
        data[data[target_date_col].isin(test_dates)].copy(),
    )


def validate_splits(splits, date_col):
    date_sets = [set(part[date_col].unique()) for part in splits]
    for i in range(3):
        for j in range(i + 1, 3):
            if date_sets[i] & date_sets[j]:
                raise AssertionError("Target-date overlap between partitions.")
    for part in splits:
        counts = part.groupby(date_col)[SCENARIO_COL].nunique()
        if not (counts == 3).all():
            raise AssertionError("A target date is missing one or more scenarios.")


def make_preprocessor(numeric, categorical, scale):
    num_steps = [("imputer", SimpleImputer(strategy="median"))]
    if scale:
        num_steps.append(("scaler", StandardScaler()))
    numeric_pipe = Pipeline(num_steps)
    transformers = [("numeric", numeric_pipe, numeric)]
    if categorical:
        cat_pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ])
        transformers.append(("categorical", cat_pipe, categorical))
    return ColumnTransformer(transformers, remainder="drop")


def build_model_zoo(numeric, categorical):
    def pipe(estimator, scale=False):
        return Pipeline([
            ("preprocess", make_preprocessor(numeric, categorical, scale)),
            ("model", estimator),
        ])
    return {
        "Dummy_MostFrequent": pipe(DummyClassifier(strategy="most_frequent")),
        "LogisticRegression": pipe(LogisticRegression(
            max_iter=3000, class_weight="balanced", random_state=SEED
        ), scale=True),
        "DecisionTree": pipe(DecisionTreeClassifier(
            class_weight="balanced", min_samples_leaf=5, random_state=SEED
        )),
        "RandomForest": pipe(RandomForestClassifier(
            n_estimators=400, class_weight="balanced", min_samples_leaf=2,
            max_features="sqrt", n_jobs=-1, random_state=SEED
        )),
        "ExtraTrees": pipe(ExtraTreesClassifier(
            n_estimators=400, class_weight="balanced", min_samples_leaf=2,
            max_features="sqrt", n_jobs=-1, random_state=SEED
        )),
        "SVM_RBF": pipe(SVC(
            kernel="rbf", C=1.0, class_weight="balanced",
            random_state=SEED
        ), scale=True),
        "GradientBoosting": pipe(GradientBoostingClassifier(random_state=SEED)),
    }


def metrics(y_true, y_pred):
    return {
        "records": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(
            y_true, y_pred
        )),
        "macro_precision": float(precision_score(
            y_true, y_pred, labels=CLASSES, average="macro", zero_division=0
        )),
        "macro_recall": float(recall_score(
            y_true, y_pred, labels=CLASSES, average="macro", zero_division=0
        )),
        "macro_f1": float(f1_score(
            y_true, y_pred, labels=CLASSES, average="macro", zero_division=0
        )),
        "weighted_f1": float(f1_score(
            y_true, y_pred, average="weighted", zero_division=0
        )),
    }


def class_coverage(y):
    present = set(pd.Series(y).dropna().unique())
    return {
        "present_classes": "|".join(c for c in CLASSES if c in present),
        "missing_classes": "|".join(c for c in CLASSES if c not in present),
    }


def write_split_diagnostics(splits, target, date_col, objective, track, path):
    rows = []
    for split_name, part in zip(["train", "validation", "test"], splits):
        counts = part[target].value_counts().reindex(CLASSES, fill_value=0)
        rows.append({
            "objective": objective,
            "track": track,
            "split": split_name,
            "records": len(part),
            "unique_target_dates": part[date_col].nunique(),
            "first_target_date": str(part[date_col].min().date()),
            "last_target_date": str(part[date_col].max().date()),
            **class_coverage(part[target]),
            **{f"class_{c}": int(counts[c]) for c in CLASSES},
        })
    pd.DataFrame(rows).to_csv(path, index=False)


def save_distribution(splits, target, path, title):
    counts = pd.DataFrame({
        name: part[target].value_counts().reindex(CLASSES, fill_value=0)
        for name, part in zip(["Train", "Validation", "Test"], splits)
    }).T
    counts.to_csv(path.with_suffix(".csv"))
    ax = counts.plot(kind="bar", figsize=(8, 5))
    ax.set_title(title)
    ax.set_xlabel("Partition")
    ax.set_ylabel("Records")
    ax.grid(axis="y", alpha=0.25)
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(path, dpi=250, bbox_inches="tight")
    plt.close()


def save_confusion(y_true, y_pred, path, title):
    cm = confusion_matrix(y_true, y_pred, labels=CLASSES)
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    ConfusionMatrixDisplay(cm, display_labels=CLASSES).plot(
        ax=ax, cmap="Blues", colorbar=False, values_format="d"
    )
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=250, bbox_inches="tight")
    plt.close(fig)


def run_random_track(objective, data, target, target_date, dirs, repeats):
    splits = grouped_random_split(data, target_date)
    train, val, test = splits
    validate_splits(splits, target_date)

    write_split_diagnostics(
        splits, target, target_date, objective, "date_grouped_random",
        dirs["tables"] / f"{objective}_random_split_diagnostics.csv"
    )
    save_distribution(
        splits, target,
        dirs["figures"] / f"{objective}_random_class_distribution.png",
        f"{objective}: date-grouped random split"
    )

    validation_rows, selected_rows = [], []

    for group_name, spec in FEATURE_GROUPS.items():
        numeric = spec["numeric"]
        categorical = spec["categorical"]
        features = numeric + categorical
        candidates = []

        for model_name, estimator in build_model_zoo(numeric, categorical).items():
            fitted = clone(estimator)
            fitted.fit(train[features], train[target])
            pred = fitted.predict(val[features])
            score = metrics(val[target], pred)
            row = {
                "objective": objective,
                "track": "date_grouped_random_exploratory",
                "feature_group": group_name,
                "model": model_name,
                "features": "|".join(features),
                **{f"validation_{k}": v for k, v in score.items()},
                "validation_" + "present_classes": class_coverage(val[target])["present_classes"],
                "validation_" + "missing_classes": class_coverage(val[target])["missing_classes"],
            }
            validation_rows.append(row)
            candidates.append((
                model_name, estimator, score["macro_f1"],
                score["balanced_accuracy"]
            ))

        best_name, best_estimator, best_f1, best_balanced = max(
            candidates, key=lambda x: (x[2], x[3])
        )

        train_val = pd.concat([train, val]).sort_values(target_date)
        final_model = clone(best_estimator)
        final_model.fit(train_val[features], train_val[target])
        test_pred = final_model.predict(test[features])
        test_score = metrics(test[target], test_pred)

        prefix = f"{objective}_random_{group_name}_{best_name}"
        save_confusion(
            test[target], test_pred,
            dirs["figures"] / f"{prefix}_test_confusion_matrix.png",
            f"{prefix}: held-out test"
        )
        report = classification_report(
            test[target], test_pred, labels=CLASSES,
            output_dict=True, zero_division=0
        )
        pd.DataFrame(report).T.to_csv(
            dirs["reports"] / f"{prefix}_test_classification_report.csv"
        )

        joblib.dump({
            "model": final_model,
            "model_name": best_name,
            "features": features,
            "numeric_features": numeric,
            "categorical_features": categorical,
            "classes": CLASSES,
            "objective": objective,
            "feature_group": group_name,
            "selection_metric": "validation_macro_f1",
            "validation_macro_f1": best_f1,
            "random_state": SEED,
            "target_note": "Simulated/rule-derived; not field ground truth.",
            "feature_note": (
                "Intervention-aware irrigation litres are day-t quantities. "
                "For model-triggered irrigation they are coupled to simulated "
                "depletion and must be interpreted as an exploratory ablation."
            ),
        }, dirs["models"] / f"{prefix}.joblib")

        selected_row = {
            "objective": objective,
            "track": "date_grouped_random_exploratory",
            "feature_group": group_name,
            "selected_model": best_name,
            "selection_metric": "validation_macro_f1",
            "validation_macro_f1": best_f1,
            "validation_balanced_accuracy": best_balanced,
            **{f"test_{k}": v for k, v in test_score.items()},
            "test_" + "present_classes": class_coverage(test[target])["present_classes"],
            "test_" + "missing_classes": class_coverage(test[target])["missing_classes"],
        }
        selected_rows.append(selected_row)

        # Importance is estimated on validation, not the held-out test set.
        if repeats > 0:
            try:
                perm = permutation_importance(
                    final_model, val[features], val[target],
                    scoring="f1_macro", n_repeats=repeats,
                    random_state=SEED, n_jobs=-1
                )
                imp = pd.DataFrame({
                    "feature": features,
                    "importance_mean": perm.importances_mean,
                    "importance_std": perm.importances_std,
                }).sort_values("importance_mean", ascending=False)
                imp.to_csv(
                    dirs["tables"] / f"{prefix}_validation_permutation_importance.csv",
                    index=False
                )
                top = imp.head(15).sort_values("importance_mean")
                fig, ax = plt.subplots(figsize=(9, 6))
                ax.barh(
                    top["feature"], top["importance_mean"],
                    xerr=top["importance_std"]
                )
                ax.set_xlabel("Decrease in validation macro-F1 after permutation")
                ax.set_title(f"{prefix}: validation permutation importance")
                ax.grid(axis="x", alpha=0.25)
                fig.tight_layout()
                fig.savefig(
                    dirs["figures"] / f"{prefix}_validation_permutation_importance.png",
                    dpi=250, bbox_inches="tight"
                )
                plt.close(fig)
            except Exception as exc:
                (dirs["reports"] / f"{prefix}_permutation_warning.txt").write_text(
                    str(exc), encoding="utf-8"
                )

    pd.DataFrame(validation_rows).to_csv(
        dirs["tables"] / f"{objective}_random_validation_model_comparison.csv",
        index=False
    )
    pd.DataFrame(selected_rows).to_csv(
        dirs["tables"] / f"{objective}_random_selected_test_results.csv",
        index=False
    )
    return validation_rows, selected_rows


def run_chronological_track(objective, data, target, target_date, dirs):
    splits = chronological_split(data, target_date)
    train, val, test = splits
    validate_splits(splits, target_date)

    write_split_diagnostics(
        splits, target, target_date, objective, "chronological_diagnostic",
        dirs["tables"] / f"{objective}_chronological_split_diagnostics.csv"
    )
    save_distribution(
        splits, target,
        dirs["figures"] / f"{objective}_chronological_class_distribution.png",
        f"{objective}: chronological diagnostic"
    )

    rows = []
    # Predeclared reference models only; no chronological validation-based
    # selection is performed because class coverage may be incomplete.
    spec = FEATURE_GROUPS["weather_baseline"]
    features = spec["numeric"]
    zoo = build_model_zoo(features, [])
    for model_name in ["Dummy_MostFrequent", "RandomForest"]:
        model = clone(zoo[model_name])
        model.fit(train[features], train[target])
        for split_name, part in [("validation", val), ("test", test)]:
            pred = model.predict(part[features])
            rows.append({
                "objective": objective,
                "track": "chronological_diagnostic_only",
                "feature_group": "weather_baseline",
                "model": model_name,
                "split": split_name,
                **class_coverage(part[target]),
                **metrics(part[target], pred),
            })
            if split_name == "test":
                save_confusion(
                    part[target], pred,
                    dirs["figures"] / (
                        f"{objective}_chronological_{model_name}_test_confusion_matrix.png"
                    ),
                    f"{objective}: chronological {model_name} test diagnostic"
                )

    pd.DataFrame(rows).to_csv(
        dirs["tables"] / f"{objective}_chronological_diagnostic_metrics.csv",
        index=False
    )
    return rows


def main():
    args = parse_args()
    data_path = Path(args.data).expanduser().resolve()
    output_root = Path(args.output).expanduser().resolve()
    dirs = create_output_dirs(output_root)

    print("=" * 78)
    print("COCOCARE STAGE 3 — BASELINE ML")
    print("=" * 78)
    print("Dataset:", data_path)

    df = load_and_validate(data_path)
    print("Validated dataset:", df.shape)
    print("Date range:", df[DATE_COL].min().date(), "to", df[DATE_COL].max().date())
    print("Rows per scenario:")
    print(df[SCENARIO_COL].value_counts().to_string())
    print("\nRule-derived labels by scenario:")
    print(pd.crosstab(df[SCENARIO_COL], df[TARGET_COL]).to_string())

    audit = {
        "dataset": str(data_path),
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "unique_dates": int(df[DATE_COL].nunique()),
        "date_start": str(df[DATE_COL].min().date()),
        "date_end": str(df[DATE_COL].max().date()),
        "scenario_counts": {
            str(k): int(v) for k, v in df[SCENARIO_COL].value_counts().items()
        },
        "label_counts_by_scenario": {
            str(s): {str(k): int(v) for k, v in part[TARGET_COL].value_counts().items()}
            for s, part in df.groupby(SCENARIO_COL)
        },
        "missing_values": {
            str(k): int(v) for k, v in df.isna().sum().items() if v > 0
        },
        "interpretation": "Simulated rule-derived labels; not field ground truth.",
    }
    (dirs["reports"] / "dataset_audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )

    feature_rows = []
    for group, spec in FEATURE_GROUPS.items():
        for feature in spec["numeric"]:
            note = "day-t weather input"
            if feature == IRRIGATION_FEATURE:
                note = (
                    "day-t simulated irrigation volume; must be known at prediction time; "
                    "mechanistically coupled to model-triggered scenario"
                )
            feature_rows.append({
                "feature_group": group, "feature": feature,
                "feature_type": "numeric", "note": note
            })
        for feature in spec["categorical"]:
            feature_rows.append({
                "feature_group": group, "feature": feature,
                "feature_type": "categorical_one_hot",
                "note": "scenario identity known in the simulation"
            })
    pd.DataFrame(feature_rows).to_csv(
        dirs["tables"] / "stage3_feature_manifest.csv", index=False
    )
    (dirs["reports"] / "excluded_features_and_reasons.json").write_text(
        json.dumps(EXCLUDED_FEATURES, indent=2), encoding="utf-8"
    )

    objectives = prepare_objectives(df)
    all_val, all_selected, all_chrono = [], [], []

    for objective, (data, target, target_date) in objectives.items():
        print(f"\n--- {objective.upper()} ---")
        print("Rows:", len(data), "| target dates:", data[target_date].nunique())
        print("Target distribution:")
        print(data[target].value_counts().reindex(CLASSES, fill_value=0).to_string())

        val_rows, selected_rows = run_random_track(
            objective, data, target, target_date, dirs,
            max(0, args.permutation_repeats)
        )
        chrono_rows = run_chronological_track(
            objective, data, target, target_date, dirs
        )
        all_val.extend(val_rows)
        all_selected.extend(selected_rows)
        all_chrono.extend(chrono_rows)

    pd.DataFrame(all_val).to_csv(
        dirs["tables"] / "all_random_validation_model_comparisons.csv",
        index=False
    )
    pd.DataFrame(all_selected).to_csv(
        dirs["tables"] / "all_random_selected_test_results.csv",
        index=False
    )
    pd.DataFrame(all_chrono).to_csv(
        dirs["tables"] / "all_chronological_diagnostic_metrics.csv",
        index=False
    )

    metadata = {
        "project": "CocoCare",
        "stage": "Stage 3",
        "dataset": str(data_path),
        "output_directory": str(output_root),
        "random_state": SEED,
        "objectives": ["current_day", "next_day"],
        "scenarios": sorted(EXPECTED_SCENARIOS),
        "feature_groups": FEATURE_GROUPS,
        "random_evaluation": (
            "Date-grouped exploratory 70/15/15. Candidate selection by validation "
            "macro-F1 then validation balanced accuracy. Selected model refit on "
            "train+validation and evaluated on held-out test."
        ),
        "chronological_evaluation": (
            "Separate temporal diagnostic using weather-baseline Dummy and "
            "Random Forest; no model selection from chronological validation."
        ),
        "target_limitation": (
            "water_stress_rule_derived is produced by the simulation and is not "
            "independent field-observed ground truth."
        ),
        "intervention_feature_limitation": (
            "Irrigation litres are day-t simulated intervention. In the "
            "model-triggered scenario this feature is calculated from simulated "
            "depletion and is mechanistically coupled to the target."
        ),
        "permutation_importance": "Computed on validation data, not held-out test data.",
    }
    (dirs["reports"] / "experiment_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    print("\nCompleted Stage 3 baseline ML.")
    print("Outputs:", output_root)
    print("Validation comparison:",
          dirs["tables"] / "all_random_validation_model_comparisons.csv")
    print("Selected held-out test results:",
          dirs["tables"] / "all_random_selected_test_results.csv")
    

if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=FutureWarning)
    main()
