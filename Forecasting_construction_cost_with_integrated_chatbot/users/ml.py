"""Train, persist and serve the construction cost models.

The models learn material and labour cost per sq.ft from project attributes
only. Total_Cost in the dataset is effectively Material_Cost + Labor_Cost, so
those columns must not be used as inputs. Predicting a per-sq.ft rate also
lets estimates scale with area beyond the range seen in training.
"""
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from matplotlib.figure import Figure
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

try:
    from xgboost import XGBRegressor
except ImportError:  # not installed on Vercel, to fit its size limit
    XGBRegressor = None

DATASET_PATH = Path(settings.MEDIA_ROOT) / 'construction_cost_dataset.csv'
ARTIFACT_NAME = 'ml_artifacts/cost_model.joblib'
PLOT_NAMES = {'actual_vs_pred': 'plots/actual_vs_pred.png', 'error': 'plots/error.png', 'feature': 'plots/feature.png'}

PLOT_BACKGROUND, PLOT_TEXT, PLOT_GRID = '#10151d', '#cbd6e2', '#3a4656'
PLOT_CYAN, PLOT_ORANGE = '#58dcec', '#ff8a1f'

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


def _store(name, data):
    if default_storage.exists(name):
        default_storage.delete(name)
    default_storage.save(name, ContentFile(data))


def _themed_axes():
    """A figure and axes matching the site's dark theme."""
    fig = Figure(facecolor=PLOT_BACKGROUND)
    ax = fig.subplots()
    ax.set_facecolor(PLOT_BACKGROUND)
    ax.tick_params(colors=PLOT_TEXT)
    for spine in ax.spines.values():
        spine.set_color(PLOT_GRID)
    return fig, ax


def _label(ax, title, xlabel='', ylabel=''):
    ax.set_title(title, color=PLOT_TEXT)
    ax.set_xlabel(xlabel, color=PLOT_TEXT)
    ax.set_ylabel(ylabel, color=PLOT_TEXT)


def _store_figure(key, fig):
    buffer = BytesIO()
    fig.savefig(buffer, format='png', bbox_inches='tight', dpi=130, facecolor=fig.get_facecolor())
    _store(PLOT_NAMES[key], buffer.getvalue())


def _save_plots(y_test, predicted, feature_names, importances):
    fig, ax = _themed_axes()
    ax.scatter(y_test, predicted, s=8, alpha=0.5, color=PLOT_CYAN)
    ax.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], color=PLOT_ORANGE, linewidth=1)
    _label(ax, 'Actual vs Predicted', 'Actual (₹)', 'Predicted (₹)')
    ax.xaxis.get_offset_text().set_color(PLOT_TEXT)
    ax.yaxis.get_offset_text().set_color(PLOT_TEXT)
    _store_figure('actual_vs_pred', fig)

    fig, ax = _themed_axes()
    ax.hist(y_test - predicted, bins=30, color=PLOT_CYAN)
    _label(ax, 'Error Distribution', 'Error (₹)', 'Projects')
    _store_figure('error', fig)

    fig, ax = _themed_axes()
    ax.barh(feature_names, importances, color=PLOT_ORANGE)
    _label(ax, 'Feature Importance', 'Importance')
    _store_figure('feature', fig)


def plot_urls():
    """Plot addresses, versioned so browsers fetch new images after retraining."""
    version = int(default_storage.get_modified_time(ARTIFACT_NAME).timestamp())
    return {key: f'{default_storage.url(name)}?v={version}' for key, name in PLOT_NAMES.items()}


def train_models():
    """Train both models, keep the better one, and return its bundle."""
    df = load_dataset()
    train, test = train_test_split(df, test_size=0.3, random_state=42)
    candidates = {
        'rf': ('Random Forest', RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)),
    }
    if XGBRegressor is not None:
        candidates['xgb'] = ('XGBoost', XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.08, random_state=42))
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
        'trained_at': timezone.localtime().strftime('%d %b %Y, %H:%M'),
        'rows': len(df),
        'area_range': (int(df['Area_sqft'].min()), int(df['Area_sqft'].max())),
        'max_floors': int(df['Floors'].max()),
        'metrics': {
            key: {k: float(r[k]) for k in ('train_r2', 'test_r2', 'mae', 'mape')}
            for key, r in results.items()
        },
    }
    buffer = BytesIO()
    joblib.dump(bundle, buffer)
    _store(ARTIFACT_NAME, buffer.getvalue())
    return bundle


def trained_bundle():
    """The saved bundle, or None if nothing has been trained yet."""
    if not default_storage.exists(ARTIFACT_NAME):
        return None
    modified = default_storage.get_modified_time(ARTIFACT_NAME)
    if _cached['mtime'] != modified:
        with default_storage.open(ARTIFACT_NAME) as stored:
            _cached.update(mtime=modified, bundle=joblib.load(BytesIO(stored.read())))
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
