import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_absolute_error
import xgboost as xgb
import joblib
import os

FEATURE_COLS = [
    'Delay_at_entry_min', 'Block_occupied_flag', 'Conflict_flag',
    'Priority_level', 'Train_avg_speed_kmph', 'Max_dwell_time_min',
    'Block_length_km', 'Has_loop_line', 'Loop_capacity',
    'Is_Single_Line', 'Is_Express', 'Is_Freight', 'Is_Passenger', 'Is_UP',
    'Hour_of_Day', 'Is_Peak_Hour', 'Speed_Block_Ratio',
    'Expected_Block_Time', 'Priority_Speed_Score', 'Congestion_Score'
]


def train_models(merged_df, model_dir='models'):
    os.makedirs(model_dir, exist_ok=True)
    df = merged_df.copy()

    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    X = df[FEATURE_COLS]
    y_class = df['Is_Delayed']
    y_reg = df['Delay_at_exit_min']

    X_train, X_test, yc_train, yc_test = train_test_split(X, y_class, test_size=0.2, random_state=42)
    _, _, yr_train, yr_test = train_test_split(X, y_reg, test_size=0.2, random_state=42)

    rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    rf.fit(X_train, yc_train)
    rf_acc = accuracy_score(yc_test, rf.predict(X_test))

    xgb_model = xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42)
    xgb_model.fit(X_train, yr_train)
    xgb_mae = mean_absolute_error(yr_test, xgb_model.predict(X_test))

    joblib.dump(rf, os.path.join(model_dir, 'rf_model.pkl'))
    joblib.dump(xgb_model, os.path.join(model_dir, 'xgb_model.pkl'))

    importances = {}
    for k, v in zip(FEATURE_COLS, rf.feature_importances_):
        importances[str(k)] = round(float(v), 6)

    return {
        'rf_accuracy': round(float(rf_acc * 100), 2),
        'xgb_mae': round(float(xgb_mae), 2),
        'feature_importances': importances,
        'train_size': int(len(X_train)),
        'test_size': int(len(X_test))
    }


def predict_single(train_row, model_dir='models'):
    rf = joblib.load(os.path.join(model_dir, 'rf_model.pkl'))
    xgb_model = joblib.load(os.path.join(model_dir, 'xgb_model.pkl'))

    features = {}
    for col in FEATURE_COLS:
        features[col] = float(train_row.get(col, 0))

    X = pd.DataFrame([features])

    delay_class = int(rf.predict(X)[0])
    delay_proba = rf.predict_proba(X)[0].tolist()
    delay_minutes = float(xgb_model.predict(X)[0])

    return {
        'is_delayed': delay_class,
        'delay_probability': round(max(delay_proba) * 100, 1),
        'predicted_delay_minutes': round(delay_minutes, 1),
        'delay_status': 'Delayed' if delay_class == 1 else 'On Time',
        'confidence': round(max(delay_proba) * 100, 1)
    }


def predict_all(merged_df, model_dir='models'):
    rf = joblib.load(os.path.join(model_dir, 'rf_model.pkl'))
    xgb_model = joblib.load(os.path.join(model_dir, 'xgb_model.pkl'))

    df = merged_df.copy()
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    X = df[FEATURE_COLS]
    df['Predicted_Delayed'] = rf.predict(X)
    df['Predicted_Delay_Min'] = np.round(xgb_model.predict(X), 1)
    df['Delay_Status'] = df['Predicted_Delayed'].map({1: 'Delayed', 0: 'On Time'})

    return df
