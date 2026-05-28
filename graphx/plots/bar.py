def bar_chart(axes, df, x_col, y_col, **kwargs):
    color = kwargs.pop("color", "#1f77b4")
    axes.bar(df[x_col].astype(str), df[y_col], color=color, **kwargs)
    axes.tick_params(axis="x", rotation=45)


def histogram(axes, df, x_col, y_col=None, **kwargs):
    color = kwargs.pop("color", "#1f77b4")
    bins = kwargs.pop("bins", 10)
    axes.hist(df[x_col].dropna(), bins=bins, color=color, edgecolor="white", **kwargs)
