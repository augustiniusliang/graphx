def pie_chart(axes, df, x_col, y_col, **kwargs):
    kwargs.pop("color", None)
    axes.pie(df[y_col], labels=df[x_col].astype(str), autopct="%1.1f%%", **kwargs)


def heatmap(axes, df, x_col, y_col, **kwargs):
    import numpy as np
    pivot = df.pivot_table(index=x_col, columns=y_col, aggfunc="size", fill_value=0)
    if pivot.empty:
        # fallback: use correlation matrix of numeric columns
        pivot = df.select_dtypes(include=[np.number]).corr()
    im = axes.imshow(pivot.values, aspect="auto", cmap=kwargs.pop("cmap", "viridis"))
    axes.set_xticks(range(len(pivot.columns)))
    axes.set_xticklabels(pivot.columns, rotation=45)
    axes.set_yticks(range(len(pivot.index)))
    axes.set_yticklabels(pivot.index)
    return im
