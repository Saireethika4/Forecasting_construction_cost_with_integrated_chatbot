"""Train, persist and serve the construction cost models.

The models learn material and labour cost per sq.ft from project attributes
only. Total_Cost in the dataset is effectively Material_Cost + Labor_Cost, so
those columns must not be used as inputs. Predicting a per-sq.ft rate also
lets estimates scale with area beyond the range seen in training.
"""
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from matplotlib.figure import Figure
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

DATASET_PATH = Path(settings.MEDIA_ROOT) / 'construction_cost_dataset.csv'
ARTIFACT_PATH = Path(settings.BASE_DIR) / 'ml_artifacts' / 'cost_model.joblib'
PLOTS_DIR = Path(settings.BASE_DIR) / 'static' / 'plots'

CATEGORICAL = ['City', 'Material_Quality', 'Building_Type']
FEATURES = ['Area_sqft', 'Floors'] + CATEGORICAL

_cached = {'mtime': None, 'bundle': None}


@lru_cache(maxsize=1)
def load_dataset():
    return pd.read_csv(DATASET_PATH)


def form_options():
    df = load_dataset()
    return {
        'city_states': dict(sorted(zip(df['City'], df['State']))),
        'qualities': ['Low', 'Medium', 'High'],
        'types': sorted(df['Building_Type'].unique()),
    }


def _pipeline(regressor):
    encoder = ColumnTransformer(
        [('categories', OneHotEncoder(handle_unknown='ignore'), CATEGORICAL)],
        remainder='passthrough',
    )
    return Pipeline([('encode', encoder), ('model', regressor)])


def _targets(df):
    return np.column_stack([df['Material_Cost'] / df['Area_sqft'], df['Labor_Cost'] / df['Area_sqft']])


def _total(pipeline, df):
    return pipeline.predict(df[FEATURES]).sum(axis=1) * df['Area_sqft'].to_numpy()


def _save_plots(y_test, predicted, feature_names, importances):
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    fig = Figure()
    ax = fig.subplots()
    ax.scatter(y_test, predicted, s=8, alpha=0.5)
    ax.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], color='gray', linewidth=1)
    ax.set(xlabel='Actual (₹)', ylabel='Predicted (₹)', title='Actual vs Predicted')
    fig.savefig(PLOTS_DIR / 'actual_vs_pred.png', bbox_inches='tight')

    fig = Figure()
    ax = fig.subplots()
    ax.hist(y_test - predicted, bins=30)
    ax.set(xlabel='Error (₹)', ylabel='Projects', title='Error Distribution')
    fig.savefig(PLOTS_DIR / 'error.png', bbox_inches='tight')

    fig = Figure()
    ax = fig.subplots()
    ax.barh(feature_names, importances)
    ax.set(xlabel='Importance', title='Feature Importance')
    fig.savefig(PLOTS_DIR / 'feature.png', bbox_inches='tight')


def train_models():
    """Train both models, keep the better one, and return its bundle."""
    df = load_dataset()
    train, test = train_test_split(df, test_size=0.3, random_state=42)
    candidates = {
        'rf': ('Random Forest', RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)),
        'xgb': ('XGBoost', XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.08, random_state=42)),
    }
    results = {}
    for key, (label, regressor) in candidates.items():
        pipeline = _pipeline(regressor)
        pipeline.fit(train[FEATURES], _targets(train))
        test_pred = _total(pipeline, test)
        results[key] = {
            'label': label,
            'pipeline': pipeline,
            'test_pred': test_pred,
            'train_r2': r2_score(train['Total_Cost'], _total(pipeline, train)),
            'test_r2': r2_score(test['Total_Cost'], test_pred),
            'mae': mean_absolute_error(test['Total_Cost'], test_pred),
            'mape': mean_absolute_percentage_error(test['Total_Cost'], test_pred) * 100,
        }

    best = min(results.values(), key=lambda r: r['mae'])
    y_test = test['Total_Cost'].to_numpy()
    names = [n.split('__')[-1] for n in best['pipeline'].named_steps['encode'].get_feature_names_out()]
    _save_plots(y_test, best['test_pred'], names, best['pipeline'].named_steps['model'].feature_importances_)

    bundle = {
        'pipeline': best['pipeline'],
        'model_label': best['label'],
        # 95% of held-out projects were within this percentage of the actual cost
        'error_p95': float(np.percentile(np.abs(y_test - best['test_pred']) / y_test * 100, 95)),
        'trained_at': datetime.now().strftime('%d %b %Y, %H:%M'),
        'rows': len(df),
        'area_range': (int(df['Area_sqft'].min()), int(df['Area_sqft'].max())),
        'max_floors': int(df['Floors'].max()),
        'metrics': {
            key: {k: float(r[k]) for k in ('train_r2', 'test_r2', 'mae', 'mape')}
            for key, r in results.items()
        },
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = ARTIFACT_PATH.with_suffix('.tmp')
    joblib.dump(bundle, temp_path)
    temp_path.replace(ARTIFACT_PATH)
    return bundle


def trained_bundle():
    """The saved bundle, or None if nothing has been trained yet."""
    if not ARTIFACT_PATH.exists():
        return None
    mtime = ARTIFACT_PATH.stat().st_mtime
    if _cached['mtime'] != mtime:
        _cached.update(mtime=mtime, bundle=joblib.load(ARTIFACT_PATH))
    return _cached['bundle']


def predict_cost(area, floors, city, quality, building_type):
    bundle = trained_bundle() or train_models()
    row = pd.DataFrame([{
        'Area_sqft': area, 'Floors': floors, 'City': city,
        'Material_Quality': quality, 'Building_Type': building_type,
    }])
    material_rate, labour_rate = bundle['pipeline'].predict(row[FEATURES])[0]
    material, labour = float(material_rate) * area, float(labour_rate) * area

    low, high = bundle['area_range']
    warning = None
    if not low <= area <= high or floors > bundle['max_floors']:
        warning = (f'Training data covers {low:,}–{high:,} sq.ft and up to {bundle["max_floors"]} floors, '
                   'so this estimate is an extrapolation.')
    return {
        'material': material,
        'labour': labour,
        'total': material + labour,
        'error_p95': bundle['error_p95'],
        'model_label': bundle['model_label'],
        'warning': warning,
    }
