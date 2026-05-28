import numpy as np
import pandas as pd


_ALLOWED_NAMES = {
    "np": np,
    "log": np.log,
    "log10": np.log10,
    "log2": np.log2,
    "exp": np.exp,
    "sqrt": np.sqrt,
    "abs": np.abs,
    "pow": np.power,
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "arcsin": np.arcsin,
    "arccos": np.arccos,
    "arctan": np.arctan,
    "pi": np.pi,
    "e": np.e,
}


def evaluate(df: pd.DataFrame, expression: str) -> pd.Series:
    """Safely evaluate an expression using dataframe columns and numpy functions.

    Example expressions:
      - "col_A + col_B"
      - "log(col_A)"
      - "col_A ** 2 + col_B * 3"
      - "sqrt(abs(col_A))"
      - "exp(col_A) / (1 + exp(col_A))"
    """
    ns = dict(_ALLOWED_NAMES)
    # Expose each column as a numpy array
    for col in df.columns:
        safe_name = _sanitize(col)
        ns[safe_name] = df[col].values
        # Also expose the original name if it's a valid identifier
        if col.isidentifier() and col not in ns:
            ns[col] = df[col].values

    # Replace column names with sanitized versions in expression
    sanitized_expr = expression
    for col in sorted(df.columns, key=len, reverse=True):
        if col in sanitized_expr:
            safe = _sanitize(col)
            sanitized_expr = sanitized_expr.replace(col, safe)

    try:
        result = eval(sanitized_expr, {"__builtins__": {}}, ns)
    except Exception as e:
        raise ValueError(f"Expression error: {e}") from e

    if isinstance(result, pd.Series):
        return result
    if isinstance(result, np.ndarray):
        return pd.Series(result, index=df.index)
    if isinstance(result, (int, float, np.number)):
        return pd.Series(result, index=df.index)
    raise ValueError(f"Expression returned unsupported type: {type(result)}")


def _sanitize(name: str) -> str:
    """Convert a column name to a valid Python identifier."""
    safe = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    if safe[0].isdigit():
        safe = "_" + safe
    if not safe:
        safe = "_col"
    return safe


def evaluate_rowwise(df: pd.DataFrame, expression: str) -> pd.DataFrame:
    """Evaluate an expression row-wise across columns.

    Each row's numeric columns are exposed as a vector `r`.
    The expression should use `r` (a numpy array of row values) and the result
    is stored as a new column. Returns the updated dataframe.

    Example expressions:
      - "np.mean(r)"       -> column with mean of each row
      - "np.std(r)"        -> column with std of each row
      - "r[0] + r[1]"      -> column with sum of first two numeric columns
      - "np.sum(r)"        -> column with sum of each row
      - "r.max() - r.min()" -> column with range of each row
    """
    ns = dict(_ALLOWED_NAMES)
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if not numeric_cols:
        raise ValueError("No numeric columns in dataframe.")

    results = []
    for idx in df.index:
        r = df.loc[idx, numeric_cols].values.astype(float)
        ns["r"] = r
        try:
            val = eval(expression, {"__builtins__": {}}, ns)
        except Exception as e:
            raise ValueError(f"Expression error at row {idx}: {e}") from e
        results.append(float(val))

    return pd.Series(results, index=df.index)
