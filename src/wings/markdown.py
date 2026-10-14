import pandas as pd


def md_table(df: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub-flavored markdown table."""
    rows = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    rows += ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)]
    return "\n".join(rows)
