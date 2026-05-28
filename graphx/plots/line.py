def line_plot(axes, df, x_col, y_col, **kwargs):
    color = kwargs.pop("color", "#1f77b4")
    axes.plot(df[x_col], df[y_col], color=color, marker="o", markersize=3, **kwargs)


def scatter_plot(axes, df, x_col, y_col, **kwargs):
    color = kwargs.pop("color", "#1f77b4")
    axes.scatter(df[x_col], df[y_col], c=color, alpha=0.7, **kwargs)
