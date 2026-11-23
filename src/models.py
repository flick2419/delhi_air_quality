import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.svm import SVR
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

try:
    from xgboost import XGBRegressor
except ImportError:
    XGBRegressor = None

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
EXTERNAL_DIR = ROOT / "data" / "external"

def evaluate_predictions(y_true, y_pred, model_name):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    print(f"[{model_name}] MAE: {mae:.2f} | RMSE: {rmse:.2f} | R²: {r2:.2f}")
    return {"model": model_name, "MAE": mae, "RMSE": rmse, "R2": r2}


def save_ridge_shap_plot(ridge_pipe, X_train, feature_cols):
    """Save a global SHAP feature-impact plot for the fitted Ridge model."""
    scaler = ridge_pipe.named_steps["scaler"]
    regressor = ridge_pipe.named_steps["regressor"]
    transformed = scaler.transform(X_train)
    sample = transformed[: min(len(transformed), 2000)]
    explainer = shap.LinearExplainer(regressor, sample)
    shap_values = explainer(sample)

    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(9, 6))
    shap.summary_plot(
        shap_values.values,
        sample,
        feature_names=feature_cols,
        plot_type="bar",
        show=False,
    )
    plt.tight_layout()
    plt.savefig(EXTERNAL_DIR / "shap_summary.png", dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Saved SHAP summary to {EXTERNAL_DIR / 'shap_summary.png'}")


def run_models():
    train_path = PROCESSED_DIR / "train.csv"
    test_path = PROCESSED_DIR / "test.csv"
    
    if not os.path.exists(train_path) or not os.path.exists(test_path):
        print("Split data not found. Run split_validate.py first.")
        return
        
    train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)
    
    # Select feature columns (excluding timestamps, station names, target)
    excluded = {'timestamp', 'station', 'pm25_next_day', 'aqi_category', 'pm25_subindex', 'aqi'}
    feature_cols = [
        col for col in train_df.columns
        if col not in excluded and pd.api.types.is_numeric_dtype(train_df[col])
    ]
    if not feature_cols:
        raise ValueError("No numeric feature columns were found.")
    
    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df['pm25_next_day'].fillna(train_df['pm25_next_day'].median())
    
    X_test = test_df[feature_cols].fillna(0)
    y_test = test_df['pm25_next_day'].fillna(test_df['pm25_next_day'].median())
    
    # 1. Baseline: Naive Persistence (Tomorrow = Today's PM2.5)
    y_persistence = test_df['pm25'].fillna(test_df['pm25'].median())
    results = {}
    predictions = test_df[['timestamp', 'station', 'pm25_next_day']].copy()
    results["Baseline (Persistence)"] = evaluate_predictions(
        y_test, y_persistence, "Baseline (Persistence)"
    )
    predictions["prediction_baseline"] = y_persistence.to_numpy()
    
    # 2. Ridge Regression Pipeline
    ridge_pipe = Pipeline([
        ('scaler', StandardScaler()),
        ('regressor', Ridge(alpha=1.0))
    ])
    ridge_pipe.fit(X_train, y_train)
    y_pred_ridge = ridge_pipe.predict(X_test)
    results["Ridge Regression"] = evaluate_predictions(y_test, y_pred_ridge, "Ridge Regression")
    predictions["prediction_ridge"] = y_pred_ridge
    save_ridge_shap_plot(ridge_pipe, X_train, feature_cols)
    
    # 3. Random Forest
    tree_model = RandomForestRegressor(
        n_estimators=100,
        random_state=42,
        n_jobs=-1,
    )
    tree_model.fit(X_train, y_train)
    y_pred_tree = tree_model.predict(X_test)
    results["Random Forest"] = evaluate_predictions(y_test, y_pred_tree, "Random Forest")
    predictions["prediction_random_forest"] = y_pred_tree

    # 4. Optional Support Vector Regression
    svr_pipe = Pipeline([
        ('scaler', StandardScaler()),
        ('regressor', SVR(C=10.0, epsilon=0.1))
    ])
    svr_pipe.fit(X_train, y_train)
    y_pred_svr = svr_pipe.predict(X_test)
    results["SVR"] = evaluate_predictions(y_test, y_pred_svr, "SVR")
    predictions["prediction_svr"] = y_pred_svr

    # 5. Optional XGBoost
    if XGBRegressor is not None:
        xgb_model = XGBRegressor(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=5,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            objective="reg:squarederror",
        )
        xgb_model.fit(X_train, y_train)
        y_pred_xgb = xgb_model.predict(X_test)
        results["XGBoost"] = evaluate_predictions(y_test, y_pred_xgb, "XGBoost")
        predictions["prediction_xgboost"] = y_pred_xgb

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(PROCESSED_DIR / "predictions.csv", index=False)
    with (PROCESSED_DIR / "results.json").open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)
    print("Saved predictions to data/processed/predictions.csv")
    print("Saved metrics to data/processed/results.json")
    
    print("Model training and baseline evaluation complete.")

if __name__ == "__main__":
    run_models()