"""Shared chart styling. Palette validated with the dataviz skill's CVD/contrast checker."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Arc, Circle, Rectangle  # noqa: E402

RED = "#C8102E"  # Detroit (light surface)
STEEL = "#1F6FB2"  # opponent / against
INK = "#1d1b1a"
MUTED = "#8a8580"
SURFACE = "#fcfcfb"

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#e8e5e1",
        "grid.linewidth": 0.6,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "font.size": 10,
        "lines.linewidth": 2,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
    }
)


def draw_half_rink(ax) -> None:
    """Offensive half of an NHL rink, attacking the net at (89, 0)."""
    line = {"color": "#c9c4be", "lw": 1.2, "fill": False}
    ax.add_patch(Rectangle((0, -42.5), 100, 85, **line))
    ax.plot([25, 25], [-42.5, 42.5], color="#7FA7C4", lw=3, alpha=0.6)  # blue line
    ax.plot([89, 89], [-40.5, 40.5], color=RED, lw=1, alpha=0.5)  # goal line
    ax.add_patch(Arc((89, 0), 12, 12, theta1=90, theta2=270, color=RED, lw=1, alpha=0.5))
    for y in (22, -22):
        ax.add_patch(Circle((69, y), 15, **line))
        ax.add_patch(Circle((69, y), 0.8, color="#c9c4be"))
    ax.add_patch(Rectangle((89, -3), 3.3, 6, color=INK, alpha=0.6))  # net
    ax.set(xlim=(0, 101), ylim=(-43.5, 43.5), aspect="equal", xticks=[], yticks=[])
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
