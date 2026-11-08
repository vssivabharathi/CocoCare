"""
CocoCare Stage 1: Reproducible baseline ML experiments
======================================================

Runs two objectives:
  1. Current-day stress classification: weather through day t -> label at t
  2. Next-day stress prediction: weather through day t -> label at t+1

Runs two evaluation tracks:
  A. Stratified random benchmark (exploratory; may be optimistic due to
     temporal autocorrelation and overlapping rolling windows)
  B. Chronological holdout (temporal diagnostic; class absence in later
     periods is reported and not hidden)

IMPORTANT:
The target water_stress_rule_derived is simulated/rule-derived, not
independently observed ground truth. Results measure reproduction of the
simulation labels, not validated field prediction performance.

Example:
python stage1_baseline_ml.py \
  --data ml/data/coconut_health/stage1/data/cococare_stage1_outputs/stage1_hybrid_dataset.csv

Dependencies:
pandas, numpy, matplotlib, scikit-learn, joblib
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
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier


RANDOM_STATE = 42
LABEL_COLUMN = "water_stress_rule_derived"
DATE_COLUMN = "date"
CLASSES = ["low", "moderate", "high"]

WEATHER_FEATURES = [
    "rainfall_mm",
    "tmax_c",
    "tmin_c",
    "solar_radiation_mj_m2_day",
    "relative_humidity_pct",
    "wind_speed_m_s",
]

# Excluded intentionally:
# - depletion_fraction_modelled: directly related to rule-derived target
# - soil_water_storage_mm_modelled: simulated water-balance state
# - soil_moisture_vwc_pct_simulated: simulated state
# - etc_potential_mm_day_modelled and other water-balance outputs
# - recommended_action_simulated: downstream action derived from stress
# - location/latitude/longitude/variety/palm_age: constant in this file
# - weather_source, URL, scenario, model_status, data_class,
#   stress_label_status: metadata, not predictive measurements


def make_output_dirs(root: Path) -> dict[str, Path]:
    paths = {
        "root": root,
        "tables": root / "tables",
        "figures": root / "figures",
        "models": root / "models",
        "reports": root / "reports",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def build_features(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    df = raw.copy()
    required = [DATE_COLUMN, LABEL_COLUMN] + WEATHER_FEATURES
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Required columns missing from CSV: {missing}")

    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors="raise")
    df = df.sort_values(DATE_COLUMN).drop_duplicates(DATE_COLUMN).reset_index(drop=True)

    # Basic physical/data sanity checks; do not silently modify values.
    if not set(df[LABEL_COLUMN].dropna().unique()).issubset(set(CLASSES)):
        raise ValueError(
            f"Unexpected target labels: {sorted(df[LABEL_COLUMN].dropna().unique())}"
        )

    for col in WEATHER_FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Current-day weather and causal history features.
    engineered = list(WEATHER_FEATURES)

    for col in WEATHER_FEATURES:
        df[f"{col}_lag1"] = df[col].shift(1)
        engineered.append(f"{col}_lag1")

        if col != "rainfall_mm":
            for window in (3, 7, 14):
                name = f"{col}_rolling_mean_{window}d"
                # At day t, this uses observations up to and including day t.
                df[name] = df[col].rolling(window=window, min_periods=window).mean()
                engineered.append(name)

    for window in (3, 7, 14):
        name = f"rainfall_sum_{window}d"
        df[name] = df["rainfall_mm"].rolling(
            window=window, min_periods=window
        ).sum()
        engineered.append(name)

    day = df[DATE_COLUMN].dt.dayofyear
    df["day_sin"] = np.sin(2 * np.pi * day / 365.25)
    df["day_cos"] = np.cos(2 * np.pi * day / 365.25)
    engineered += ["day_sin", "day_cos"]

    # Objective-specific targets and target dates.
    df["target_current"] = df[LABEL_COLUMN]
    df["target_date_current"] = df[DATE_COLUMN]

    df["target_next_day"] = df[LABEL_COLUMN].shift(-1)
    df["target_date_next"] = df[DATE_COLUMN].shift(-1)

    next_day = df["target_date_next"].dt.dayofyear
    df["next_day_sin"] = np.sin(2 * np.pi * next_day / 365.25)
    df["next_day_cos"] = np.cos(2 * np.pi * next_day / 365.25)
    next_features = engineered + ["next_day_sin", "next_day_cos"]

    return df, engineered, next_features


def make_model_zoo() -> dict[str, Pipeline]:
    # Imputation/scaling are fitted inside each pipeline on training data only.
    def pipe(estimator, scale=False):
        steps = [("imputer", SimpleImputer(strategy="median"))]
        if scale:
            steps.append(("scaler", StandardScaler()))
        steps.append(("model", estimator))
        return Pipeline(steps)

    return {
        "Dummy_MostFrequent": pipe(
            DummyClassifier(strategy="most_frequent")
        ),
        "LogisticRegression": pipe(
            LogisticRegression(
                max_iter=3000,
                class_weight="balanced",
                random_state=RANDOM_STATE,
            ),
            scale=True,
        ),
        "DecisionTree": pipe(
            DecisionTreeClassifier(
                class_weight="balanced",
                min_samples_leaf=5,
                random_state=RANDOM_STATE,
            )
        ),
        "RandomForest": pipe(
            RandomForestClassifier(
                n_estimators=400,
                class_weight="balanced",
                min_samples_leaf=2,
                max_features="sqrt",
                n_jobs=-1,
                random_state=RANDOM_STATE,
            )
        ),
        "ExtraTrees": pipe(
            ExtraTreesClassifier(
                n_estimators=400,
                class_weight="balanced",
                min_samples_leaf=2,
                max_features="sqrt",
                n_jobs=-1,
                random_state=RANDOM_STATE,
            )
        ),
        "SVM_RBF": pipe(
            SVC(
                kernel="rbf",
                C=1.0,
                class_weight="balanced",
                probability=True,
                random_state=RANDOM_STATE,
            ),
            scale=True,
        ),
        "GradientBoosting": pipe(
            GradientBoostingClassifier(random_state=RANDOM_STATE)
        ),
    }


def split_random(data: pd.DataFrame, target_col: str):
    # Two-stage stratification: 70% train, 15% validation, 15% test.
    from sklearn.model_selection import train_test_split

    train, temp = train_test_split(
        data,
        test_size=0.30,
        random_state=RANDOM_STATE,
        stratify=data[target_col],
    )
    val, test = train_test_split(
        temp,
        test_size=0.50,
        random_state=RANDOM_STATE,
        stratify=temp[target_col],
    )
    return (
        train.sort_values("target_date").copy(),
        val.sort_values("target_date").copy(),
        test.sort_values("target_date").copy(),
    )


def split_chronological(data: pd.DataFrame):
    data = data.sort_values("target_date").reset_index(drop=True)
    n = len(data)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)
    return (
        data.iloc[:train_end].copy(),
        data.iloc[train_end:val_end].copy(),
        data.iloc[val_end:].copy(),
    )


def metric_row(y_true, y_pred, model_name, objective, track, split_name):
    return {
        "objective": objective,
        "evaluation_track": track,
        "split": split_name,
        "model": model_name,
        "n": len(y_true),
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "macro_precision": precision_score(
            y_true, y_pred, labels=CLASSES, average="macro", zero_division=0
        ),
        "macro_recall": recall_score(
            y_true, y_pred, labels=CLASSES, average="macro", zero_division=0
        ),
        "macro_f1": f1_score(
            y_true, y_pred, labels=CLASSES, average="macro", zero_division=0
        ),
        "weighted_f1": f1_score(
            y_true, y_pred, average="weighted", zero_division=0
        ),
    }


def save_class_distribution(data, target_col, path, title):
    counts = (
        data.groupby(["split", target_col])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=CLASSES, fill_value=0)
    )
    counts.to_csv(path.with_suffix(".csv"))

    ax = counts.plot(kind="bar", figsize=(9, 5))
    ax.set_title(title)
    ax.set_xlabel("Split")
    ax.set_ylabel("Number of records")
    ax.legend(title="Stress class")
    ax.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()


def save_confusion(y_true, y_pred, path, title):
    cm = confusion_matrix(y_true, y_pred, labels=CLASSES)
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    disp = ConfusionMatrixDisplay(cm, display_labels=CLASSES)
    disp.plot(ax=ax, cmap="Blues", colorbar=False, values_format="d")
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()


def save_model_comparison(metrics: pd.DataFrame, path: Path, title: str):
    subset = metrics[
        (metrics["split"] == "test")
    ].copy()
    if subset.empty:
        return
    subset = subset.sort_values("macro_f1", ascending=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(subset["model"], subset["macro_f1"])
    ax.set_xlim(0, 1)
    ax.set_xlabel("Macro F1")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25)
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()


def save_target_timeline(df: pd.DataFrame, path: Path):
    mapping = {"low": 0, "moderate": 1, "high": 2}
    values = df[LABEL_COLUMN].map(mapping)
    fig, ax = plt.subplots(figsize=(13, 4.5))
    ax.step(df[DATE_COLUMN], values, where="mid", linewidth=1.4)
    ax.set_yticks([0, 1, 2], ["Low", "Moderate", "High"])
    ax.set_xlabel("Date")
    ax.set_ylabel("Rule-derived stress class")
    ax.set_title("CocoCare Stage 1: Daily rule-derived stress labels")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_feature_importance(model, X_test, y_test, feature_names, path, title):
    # Permutation importance on held-out data; interpretation remains
    # exploratory, especially when weather features are correlated.
    result = permutation_importance(
        model,
        X_test,
        y_test,
        scoring="f1_macro",
        n_repeats=20,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    imp = pd.DataFrame({
        "feature": feature_names,
        "importance_mean": result.importances_mean,
        "importance_std": result.importances_std,
    }).sort_values("importance_mean", ascending=False)
    imp.to_csv(path.with_suffix(".csv"), index=False)

    top = imp.head(15).sort_values("importance_mean")
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.barh(top["feature"], top["importance_mean"], xerr=top["importance_std"])
    ax.set_xlabel("Decrease in macro F1 after permutation")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def run_experiment(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    target_date_col: str,
    objective: str,
    dirs: dict[str, Path],
):
    usable = df.dropna(
        subset=feature_cols + [target_col, target_date_col]
    ).copy()
    usable = usable.rename(columns={target_date_col: "target_date"})
    usable["target_date"] = pd.to_datetime(usable["target_date"])
    usable[target_col] = usable[target_col].astype(str)

    # Save feature manifest and split diagnostics.
    manifest = pd.DataFrame({
        "feature": feature_cols,
        "feature_group": [
            "base_weather" if f in WEATHER_FEATURES
            else "seasonality" if f in ("day_sin", "day_cos", "next_day_sin", "next_day_cos")
            else "weather_history"
            for f in feature_cols
        ],
    })
    manifest.to_csv(
        dirs["tables"] / f"{objective}_feature_manifest.csv", index=False
    )

    tracks = {
        "stratified_random_exploratory": split_random(usable, target_col),
        "chronological": split_chronological(usable),
    }

    all_metrics = []
    for track, (train, val, test) in tracks.items():
        print(f"\n[{objective} | {track}]")
        print("Rows:", len(train), len(val), len(test))
        for split_name, part in [
            ("train", train), ("validation", val), ("test", test)
        ]:
            print(
                f"{split_name} dates: {part['target_date'].min().date()} "
                f"to {part['target_date'].max().date()}"
            )
            print(
                f"{split_name} classes: "
                f"{part[target_col].value_counts().reindex(CLASSES, fill_value=0).to_dict()}"
            )

        dist = pd.concat([
            train.assign(split="train"),
            val.assign(split="validation"),
            test.assign(split="test"),
        ])
        save_class_distribution(
            dist,
            target_col,
            dirs["figures"] / f"{objective}_{track}_class_distribution.png",
            f"{objective}: {track.replace('_', ' ').title()} class distribution",
        )

        X_train, y_train = train[feature_cols], train[target_col]
        X_val, y_val = val[feature_cols], val[target_col]
        X_test, y_test = test[feature_cols], test[target_col]

        model_results = []
        zoo = make_model_zoo()

        for model_name, estimator in zoo.items():
            fitted = clone(estimator)
            fitted.fit(X_train, y_train)

            # Validation is used for model selection, not test.
            val_pred = fitted.predict(X_val)
            val_score = f1_score(
                y_val, val_pred, labels=CLASSES,
                average="macro", zero_division=0
            )

            # For the exploratory track, select using validation macro F1.
            # For chronological track, validation may lack classes; therefore
            # this is diagnostic only and no "best model" is declared from it.
            test_pred = fitted.predict(X_test)

            row = metric_row(
                y_test, test_pred, model_name, objective, track, "test"
            )
            row["validation_macro_f1"] = val_score
            all_metrics.append(row)
            model_results.append((model_name, fitted, val_score, test_pred))

            report = classification_report(
                y_test,
                test_pred,
                labels=CLASSES,
                target_names=CLASSES,
                output_dict=True,
                zero_division=0,
            )
            pd.DataFrame(report).transpose().to_csv(
                dirs["reports"] /
                f"{objective}_{track}_{model_name}_test_classification_report.csv"
            )

            save_confusion(
                y_test,
                test_pred,
                dirs["figures"] /
                f"{objective}_{track}_{model_name}_confusion_matrix.png",
                f"{objective} | {track} | {model_name}",
            )

        metrics_df = pd.DataFrame([
            r for r in all_metrics
            if r["objective"] == objective and r["evaluation_track"] == track
        ])
        metrics_df.to_csv(
            dirs["tables"] / f"{objective}_{track}_metrics.csv", index=False
        )
        save_model_comparison(
            metrics_df,
            dirs["figures"] / f"{objective}_{track}_model_comparison.png",
            f"{objective}: {track.replace('_', ' ').title()} test macro F1",
        )

        # Save exploratory best model selected on validation only.
        if track == "stratified_random_exploratory":
            best_name, best_model, best_val_score, _ = max(
                model_results, key=lambda item: item[2]
            )
            model_path = dirs["models"] / f"{objective}_{track}_best.joblib"
            joblib.dump({
                "model": best_model,
                "model_name": best_name,
                "features": feature_cols,
                "classes": CLASSES,
                "objective": objective,
                "selection_metric": "validation_macro_f1",
                "validation_macro_f1": best_val_score,
                "random_state": RANDOM_STATE,
            }, model_path)

            # Held-out test permutation importance for the selected model.
            save_feature_importance(
                best_model,
                X_test,
                y_test,
                feature_cols,
                dirs["figures"] /
                f"{objective}_{track}_permutation_importance.png",
                f"{objective}: exploratory best model permutation importance",
            )

        # Save chronological models separately as diagnostics only.
        if track == "chronological":
            for model_name, fitted, _, _ in model_results:
                joblib.dump(
                    {
                        "model": fitted,
                        "model_name": model_name,
                        "features": feature_cols,
                        "classes": CLASSES,
                        "objective": objective,
                        "evaluation_track": "chronological_diagnostic",
                    },
                    dirs["models"] /
                    f"{objective}_chronological_{model_name}.joblib",
                )

    return pd.DataFrame(all_metrics)


def main():
    parser = argparse.ArgumentParser()
    # Resolve the default dataset path relative to this script's location.
    # Script location:
    #   ml/src/mlOnHybridData/stage1/stage1_baseline_ml.py
    # Dataset location:
    #   ml/data/coconut_health/stage1/data/cococare_stage1_outputs/stage1_hybrid_dataset.csv
    default_data_path = (
        Path(__file__).resolve().parents[3]
        / "data/coconut_health/stage1/data/cococare_stage1_outputs/stage1_hybrid_dataset.csv"
    )

    parser.add_argument(
        "--data",
        default=str(default_data_path),
        help="Path to Stage 1 hybrid dataset CSV",
    )
    parser.add_argument(
        "--output",
        default="ml/results/coconut_health/stage1_ml_from_scratch",
        help="Directory for metrics, models, reports and figures",
    )
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {data_path}\n"
            "Pass the correct path using --data."
        )

    dirs = make_output_dirs(Path(args.output))
    raw = pd.read_csv(data_path)
    df, current_features, next_features = build_features(raw)

    print("=" * 72)
    print("COCOCARE STAGE 1 BASELINE ML EXPERIMENTS")
    print("=" * 72)
    print("Source:", data_path)
    print("Raw rows:", len(raw))
    print("Raw columns:", len(raw.columns))
    print("Label status:", raw.get("stress_label_status", pd.Series(["unknown"])).unique())
    print("Target distribution:")
    print(raw[LABEL_COLUMN].value_counts().reindex(CLASSES, fill_value=0))
    print("Current feature count:", len(current_features))
    print("Next-day feature count:", len(next_features))

    # Target timeline figure.
    save_target_timeline(
        df,
        dirs["figures"] / "stage1_target_timeline.png"
    )

    current_metrics = run_experiment(
        df=df,
        feature_cols=current_features,
        target_col="target_current",
        target_date_col="target_date_current",
        objective="current_day",
        dirs=dirs,
    )

    next_metrics = run_experiment(
        df=df,
        feature_cols=next_features,
        target_col="target_next_day",
        target_date_col="target_date_next",
        objective="next_day",
        dirs=dirs,
    )

    combined = pd.concat(
        [current_metrics, next_metrics], ignore_index=True
    )
    combined.to_csv(
        dirs["tables"] / "all_experiment_metrics.csv", index=False
    )

    metadata = {
        "dataset": str(data_path),
        "raw_rows": int(len(raw)),
        "raw_columns": int(len(raw.columns)),
        "current_day_features": current_features,
        "next_day_features": next_features,
        "target": LABEL_COLUMN,
        "target_status": "rule_derived_not_ground_truth",
        "random_state": RANDOM_STATE,
        "warning": (
            "Random stratified benchmark is exploratory and may be optimistic "
            "because daily observations and rolling windows are temporally dependent. "
            "Chronological results are temporal diagnostics; class absence in "
            "validation/test prevents complete evaluation of all classes."
        ),
    }
    (dirs["reports"] / "experiment_metadata.json").write_text(
        json.dumps(metadata, indent=2)
    )

    print("\nCompleted.")
    print("Outputs:", dirs["root"].resolve())
    print("Combined metrics:", (dirs["tables"] / "all_experiment_metrics.csv").resolve())
    print(
        "\nInterpretation warning: these models reproduce simulated/rule-derived "
        "labels. They are not validated against independent field observations."
    )


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    main()
