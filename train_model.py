import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


STANDARD_COLUMNS = {
    "followers_count",
    "following_count",
    "media_count",
    "has_profile_pic",
    "bio_length",
    "username_length",
    "digit_count_in_username",
    "label",
}

ALIASES = {
    "userFollowerCount": "followers_count",
    "userFollowingCount": "following_count",
    "userMediaCount": "media_count",
    "userHasProfilPic": "has_profile_pic",
    "userBiographyLength": "bio_length",
    "usernameLength": "username_length",
    "usernameDigitCount": "digit_count_in_username",
    "isFake": "label",
}

FEATURE_COLUMNS = [
    "followers_count",
    "following_count",
    "media_count",
    "has_profile_pic",
    "bio_length",
    "username_length",
    "digit_count_in_username",
    "followers_following_ratio",
]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {col: ALIASES[col] for col in df.columns if col in ALIASES}
    df = df.rename(columns=renamed)

    if "bio" in df.columns and "bio_length" not in df.columns:
        df["bio_length"] = df["bio"].fillna("").astype(str).str.len()

    if "username" in df.columns:
        if "username_length" not in df.columns:
            df["username_length"] = df["username"].fillna("").astype(str).str.len()
        if "digit_count_in_username" not in df.columns:
            df["digit_count_in_username"] = (
                df["username"].fillna("").astype(str).str.count(r"\\d")
            )

    return df


def add_ratio_feature(df: pd.DataFrame) -> pd.DataFrame:
    followers = pd.to_numeric(df["followers_count"], errors="coerce")
    following = pd.to_numeric(df["following_count"], errors="coerce")
    df["followers_following_ratio"] = followers / (following + 1.0)
    return df


def validate_columns(df: pd.DataFrame) -> None:
    missing = STANDARD_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Train fake account model.")
    parser.add_argument(
        "--data",
        default=str(base_dir / "data" / "instagram_dataset.csv"),
        help="Path to CSV dataset.",
    )
    parser.add_argument(
        "--model-out",
        default=str(base_dir / "model" / "account_model.pkl"),
        help="Path to save trained model.",
    )
    parser.add_argument(
        "--metrics-out",
        default=str(base_dir / "model" / "metrics.json"),
        help="Path to save evaluation metrics as JSON.",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.data)
    df = normalize_columns(df)
    validate_columns(df)
    df = add_ratio_feature(df)

    X = df[FEATURE_COLUMNS]
    y = pd.to_numeric(df["label"], errors="coerce")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=200,
                    random_state=42,
                    class_weight="balanced",
                ),
            ),
        ]
    )

    pipeline.fit(X_train, y_train)
    predictions = pipeline.predict(X_test)

    metrics = {
        "accuracy": accuracy_score(y_test, predictions),
        "precision": precision_score(y_test, predictions, zero_division=0),
        "recall": recall_score(y_test, predictions, zero_division=0),
        "f1": f1_score(y_test, predictions, zero_division=0),
    }

    print("Evaluation metrics:")
    for name, value in metrics.items():
        print(f"  {name}: {value:.4f}")

    model_path = Path(args.model_out)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": pipeline, "feature_columns": FEATURE_COLUMNS},
        model_path,
    )
    print(f"Model saved to: {model_path}")

    metrics_path = Path(args.metrics_out)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)
    print(f"Metrics saved to: {metrics_path}")


if __name__ == "__main__":
    main()
