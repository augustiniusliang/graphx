import numpy as np
import pandas as pd
from graphx.analysis.fitting import linear_regression, poly_fit, exp_fit


def _make_linear_data():
    rng = np.random.default_rng(42)
    x = np.linspace(0, 10, 50)
    y = 2.5 * x + 1.0 + rng.normal(0, 0.5, 50)
    return pd.DataFrame({"x": x, "y": y})


def _make_quadratic_data():
    rng = np.random.default_rng(42)
    x = np.linspace(-5, 5, 60)
    y = 0.5 * x**2 - 3 * x + 2 + rng.normal(0, 2, 60)
    return pd.DataFrame({"x": x, "y": y})


def _make_exp_data():
    rng = np.random.default_rng(42)
    x = np.linspace(0, 4, 50)
    y = 2.0 * np.exp(0.5 * x) + rng.normal(0, 0.3, 50)
    return pd.DataFrame({"x": x, "y": y})


def test_linear_regression_slope():
    df = _make_linear_data()
    result = linear_regression(df, "x", "y")
    assert abs(result["slope"] - 2.5) < 0.15
    assert abs(result["intercept"] - 1.0) < 0.5


def test_linear_regression_keys():
    df = _make_linear_data()
    result = linear_regression(df, "x", "y")
    for key in ("type", "slope", "intercept", "r_value", "p_value", "fitted_fn"):
        assert key in result
    assert callable(result["fitted_fn"])


def test_poly_fit_quadratic():
    df = _make_quadratic_data()
    result = poly_fit(df, "x", "y", degree=2)
    assert len(result["coefficients"]) == 3
    assert result["r_squared"] > 0.8


def test_poly_fit_keys():
    df = _make_quadratic_data()
    result = poly_fit(df, "x", "y", degree=3)
    for key in ("type", "coefficients", "degree", "r_squared", "fitted_fn"):
        assert key in result
    assert result["degree"] == 3


def test_exp_fit():
    df = _make_exp_data()
    result = exp_fit(df, "x", "y")
    assert abs(result["a"] - 2.0) < 0.5
    assert abs(result["b"] - 0.5) < 0.15


def test_fitted_fn_callable():
    df = _make_linear_data()
    for fn in [linear_regression, poly_fit, exp_fit]:
        result = fn(df, "x", "y")
        y_pred = result["fitted_fn"](df["x"].values)
        assert y_pred.shape == df["x"].values.shape
