import numpy as np


def surface_3d(axes, df, x_col, y_col, **kwargs):
    cmap = kwargs.pop("cmap", "viridis")
    # Pivot if possible; otherwise scatter in 3D
    try:
        pivot = df.pivot_table(index=x_col, columns=y_col, aggfunc="size", fill_value=0)
        X = pivot.columns.values.astype(float)
        Y = pivot.index.values.astype(float)
        X, Y = np.meshgrid(X, Y)
        Z = pivot.values
        axes.plot_surface(X, Y, Z, cmap=cmap, **kwargs)
    except Exception:
        x = df[x_col].values
        y = df[y_col].values
        z = np.zeros_like(x) if df.shape[1] < 3 else df.iloc[:, 2].values
        axes.scatter(x, y, z, **kwargs)
    axes.set_xlabel(x_col)
    axes.set_ylabel(y_col)


def contour(axes, df, x_col, y_col, **kwargs):
    cmap = kwargs.pop("cmap", "viridis")
    try:
        pivot = df.pivot_table(index=x_col, columns=y_col, aggfunc="size", fill_value=0)
        X = pivot.columns.values.astype(float)
        Y = pivot.index.values.astype(float)
        X, Y = np.meshgrid(X, Y)
        Z = pivot.values
        axes.contourf(X, Y, Z, cmap=cmap, **kwargs)
    except Exception:
        x = df[x_col].values
        y = df[y_col].values
        axes.tricontourf(x, y, np.arange(len(x)), cmap=cmap, **kwargs)
    axes.set_xlabel(x_col)
    axes.set_ylabel(y_col)
