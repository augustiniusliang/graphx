import numpy as np
from scipy import stats
from scipy.optimize import curve_fit


def _get_row_series(df, row_index):
    """Extract numeric values from a row, skipping non-numeric columns."""
    row = df.iloc[row_index]
    numeric_mask = row.apply(lambda v: np.issubdtype(type(v), np.number))
    values = row[numeric_mask].values.astype(float)
    if len(values) == 0:
        raise ValueError(f"Row {row_index} has no numeric values.")
    x = np.arange(len(values))
    return x, values


# --- Column-wise fitting ---

def linear_regression(df, x_col, y_col):
    x = df[x_col].values
    y = df[y_col].values
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    return {
        "type": "linear",
        "slope": slope,
        "intercept": intercept,
        "r_value": r_value,
        "p_value": p_value,
        "std_err": std_err,
        "fitted_fn": lambda x: slope * x + intercept,
        "direction": "column",
    }


def poly_fit(df, x_col, y_col, degree=2):
    x = df[x_col].values
    y = df[y_col].values
    coeffs = np.polyfit(x, y, degree)
    poly_fn = np.poly1d(coeffs)
    y_pred = poly_fn(x)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0
    return {
        "type": "polynomial",
        "coefficients": coeffs.tolist(),
        "degree": degree,
        "r_squared": r_squared,
        "fitted_fn": poly_fn,
        "direction": "column",
    }


def _exp_model(x, a, b):
    return a * np.exp(b * x)


def exp_fit(df, x_col, y_col):
    x = df[x_col].values
    y = df[y_col].values
    popt, _ = curve_fit(_exp_model, x, y, p0=(1, 0.1), maxfev=10000)
    a, b = popt
    y_pred = _exp_model(x, a, b)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0
    return {
        "type": "exponential",
        "a": a,
        "b": b,
        "r_squared": r_squared,
        "fitted_fn": lambda x: _exp_model(x, a, b),
        "direction": "column",
    }


# --- Row-wise fitting ---

def linear_regression_row(df, row_index):
    x, y = _get_row_series(df, row_index)
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    return {
        "type": "linear",
        "slope": slope,
        "intercept": intercept,
        "r_value": r_value,
        "p_value": p_value,
        "std_err": std_err,
        "fitted_fn": lambda x: slope * x + intercept,
        "direction": "row",
        "row_index": row_index,
    }


def poly_fit_row(df, row_index, degree=2):
    x, y = _get_row_series(df, row_index)
    coeffs = np.polyfit(x, y, degree)
    poly_fn = np.poly1d(coeffs)
    y_pred = poly_fn(x)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0
    return {
        "type": "polynomial",
        "coefficients": coeffs.tolist(),
        "degree": degree,
        "r_squared": r_squared,
        "fitted_fn": poly_fn,
        "direction": "row",
        "row_index": row_index,
    }


def exp_fit_row(df, row_index):
    x, y = _get_row_series(df, row_index)
    popt, _ = curve_fit(_exp_model, x, y, p0=(1, 0.1), maxfev=10000)
    a, b = popt
    y_pred = _exp_model(x, a, b)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0
    return {
        "type": "exponential",
        "a": a,
        "b": b,
        "r_squared": r_squared,
        "fitted_fn": lambda x: _exp_model(x, a, b),
        "direction": "row",
        "row_index": row_index,
    }


# --- Extrapolation ---

def extrapolate(fit_result, x_values):
    """Predict y for given x values using a fitted function."""
    fn = fit_result.get("fitted_fn")
    if fn is None:
        raise ValueError("No fitted function available for extrapolation")
    return [{"x": x, "y": float(fn(x))} for x in x_values]


# --- Summarization (for error bars) ---

def summarize_column(df, col):
    """Compute mean and std of a column, returning a single data point with error bar info."""
    values = df[col].dropna().values.astype(float)
    mean_val = np.mean(values)
    std_val = np.std(values, ddof=1)
    return {
        "type": "summary",
        "label": col,
        "x": col,
        "y": mean_val,
        "yerr": std_val,
        "n": len(values),
        "direction": "column",
    }


def summarize_row(df, row_index):
    """Compute mean and std across a row's numeric columns, returning a single data point with error bar info."""
    _, values = _get_row_series(df, row_index)
    mean_val = np.mean(values)
    std_val = np.std(values, ddof=1)
    row_label = str(df.index[row_index])
    return {
        "type": "summary",
        "label": f"Row {row_label}",
        "x": row_label,
        "y": mean_val,
        "yerr": std_val,
        "n": len(values),
        "direction": "row",
        "row_index": row_index,
    }
