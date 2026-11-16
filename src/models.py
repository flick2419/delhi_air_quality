import os
import json
import pandas as pd
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.svm import SVR
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def evaluate_predictions(y_true, y_pred, model_name):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    print(f"[{model_name}] MAE: {mae:.2f} | RMSE: {rmse:.2f} | R²: {r2:.2f}")
    return {"model": model_name, "MAE": mae, "RMSE": rmse, "R2": r2}

def run_models():
    train_path = "data/processed/train.csv"
    test_path = "data/processed/test.csv"
    
    if not os.path.exists(train_path) or not os.path.exists(test_path):
        print("Split data not found. Run split_validate.py first.")
        return
        
    train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)
    
    # Select feature columns (excluding timestamps, station names, target)
    feature_cols = [col for col in train_df.columns if col not in ['timestamp', 'station', 'pm25_next_day', 'aqi_category']]
    
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

    os.makedirs("data/processed", exist_ok=True)
    predictions.to_csv("data/processed/predictions.csv", index=False)
    with open("data/processed/results.json", "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)
    print("Saved predictions to data/processed/predictions.csv")
    print("Saved metrics to data/processed/results.json")
    
    print("Model training and baseline evaluation complete.")

if __name__ == "__main__":
    run_models()