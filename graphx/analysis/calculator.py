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
    for col in df.columns:
        safe_name = _sanitize(col)
        ns[safe_name] = df[col].values
        if col.isidentifier() and col not in ns:
            ns[col] = df[col].values

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


def evaluate_cross_sheet(
    sheets: dict[str, pd.DataFrame],
    active_sheet: str,
    expression: str,
) -> pd.Series:
    """Evaluate an expression with cross-sheet column references.

    Syntax:
      - Bare column name -> refers to active sheet
      - SheetName.ColumnName -> refers to another sheet

    Example: "Sheet1.col_A + col_B"   (col_B from active sheet)
    """
    ns = dict(_ALLOWED_NAMES)

    # Expose all columns from all sheets as _sheet_col
    for sheet_name, df in sheets.items():
        base = _sanitize(sheet_name)
        for col in df.columns:
            safe_name = f"_{base}_{_sanitize(col)}"
            ns[safe_name] = df[col].values

    sanitized_expr = expression

    # Replace SheetName.ColumnName patterns first (longest match wins)
    # Handle both raw sheet name (e.g. "Fit Results.col") and sanitized (e.g. "Fit_Results.col")
    for sheet_name in sorted(sheets.keys(), key=len, reverse=True):
        df = sheets[sheet_name]
        base = _sanitize(sheet_name)
        patterns_to_check = [(sheet_name, sheet_name)]
        if base != sheet_name:
            patterns_to_check.append((base, sheet_name))
        for col in sorted(df.columns, key=len, reverse=True):
            for pat_name, real_sheet in patterns_to_check:
                pattern = f"{pat_name}.{col}"
                if pattern in sanitized_expr:
                    safe = f"_{_sanitize(real_sheet)}_{_sanitize(col)}"
                    sanitized_expr = sanitized_expr.replace(pattern, safe)

    # Then replace bare column names (from active sheet only)
    # Use regex with lookahead/lookbehind to avoid matching substrings in
    # already-replaced cross-sheet variable names (e.g. "slope" in "_Fit_Results_slope")
    import re
    active_df = sheets.get(active_sheet)
    if active_df is not None:
        for col in sorted(active_df.columns, key=len, reverse=True):
            safe = f"_{_sanitize(active_sheet)}_{_sanitize(col)}"
            if safe not in ns:
                continue
            pattern = r'(?<![a-zA-Z0-9_])' + re.escape(col) + r'(?![a-zA-Z0-9_])'
            if re.search(pattern, sanitized_expr):
                sanitized_expr = re.sub(pattern, safe, sanitized_expr)

    try:
        result = eval(sanitized_expr, {"__builtins__": {}}, ns)
    except Exception as e:
        raise ValueError(f"Expression error: {e}") from e

    idx = active_df.index if active_df is not None else None
    if isinstance(result, pd.Series):
        return result
    if isinstance(result, np.ndarray):
        if idx is not None and len(result) == len(idx):
            return pd.Series(result, index=idx)
        return pd.Series(result)
    if isinstance(result, (int, float, np.number)):
        if idx is not None:
            return pd.Series(float(result), index=idx)
        return pd.Series([float(result)])
    raise ValueError(f"Expression returned unsupported type: {type(result)}")


def _sanitize(name: str) -> str:
    """Convert a column name to a valid Python identifier."""
    safe = "".join(c if c.isalnum() or c == "_" else "_" for c in str(name))
    if safe and safe[0].isdigit():
        safe = "_" + safe
    if not safe:
        safe = "_col"
    return safe


def evaluate_rowwise(df: pd.DataFrame, expression: str) -> pd.Series:
    """Evaluate an expression row-wise across columns.

    Each row's numeric columns are exposed as a vector `r`.
    The expression should use `r` (a numpy array of row values) and the result
    is stored as a new column.

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
