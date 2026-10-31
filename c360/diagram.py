"""Draw the architecture diagram as a PNG (docs/img/architecture.png).

A PNG shows up everywhere, including the GitHub phone app.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from . import config  # noqa: E402
from .style import BLUE, LIGHT, NAVY  # noqa: E402


def box(ax, x, y, w, h, text, size=19, fill=BLUE, bold_first=True, dashed=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.6",
                                linewidth=2.2, edgecolor=NAVY, facecolor=fill,
                                linestyle="--" if dashed else "-"))
    lines = text.split("\n")
    if bold_first and len(lines) > 1:
        ax.text(x + w / 2, y + h * 0.66, lines[0], ha="center", va="center", fontsize=size + 2,
                color=NAVY, fontweight="bold")
        ax.text(x + w / 2, y + h * 0.30, "\n".join(lines[1:]), ha="center", va="center",
                fontsize=size - 2, color=NAVY, linespacing=1.3)
    else:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=NAVY,
                fontweight="bold" if bold_first else "normal", linespacing=1.25)


def arrow(ax, x1, y1, x2, y2, dashed=False):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=NAVY, lw=2.6, mutation_scale=26,
                                linestyle="--" if dashed else "-", shrinkA=0, shrinkB=0))


def draw(path=None):
    path = path or (config.DOCS / "img" / "architecture.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(14, 19.5), dpi=110)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 140)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(50, 135, "Customer 360 for contractors", ha="center", fontsize=34,
            color=NAVY, fontweight="bold")
    ax.text(50, 130.5, "All data is synthetic", ha="center", fontsize=22, color=NAVY)

    # Sources
    src = ["Calls\nand texts", "API\nLeads", "Jobs", "Billing", "Support"]
    w, gap, x0 = 16.4, 2.2, 2.5
    centers = []
    for i, s in enumerate(src):
        x = x0 + i * (w + gap)
        box(ax, x, 115, w, 10, s, size=24, bold_first=False)
        centers.append(x + w / 2)
    main_x, main_w = 3, 68
    mid = main_x + main_w / 2
    for c in centers:
        arrow(ax, c, 114.3, mid + (c - 50) * 0.55, 107.3)

    steps = [
        (96, "1. Load into ClickHouse\nclean phones, emails, addresses"),
        (78, "2. Entity resolution\none customer_key per person"),
        (60, "3. Clean tables\ndim_customer + 6 fact tables"),
        (42, "4. Semantic layer\nmetrics.yml: each metric once"),
    ]
    h = 11
    for i, (y, t) in enumerate(steps):
        box(ax, main_x, y, main_w, h, t, size=26)
        if i < len(steps) - 1:
            arrow(ax, mid, y - 0.6, mid, steps[i + 1][0] + h + 0.6)

    # Quality checks run beside every layer.
    qx, qw = 77, 20.5
    box(ax, qx, 45, qw, 59, "", fill=LIGHT, bold_first=False, dashed=True)
    ax.text(qx + qw / 2, 96, "Quality\nchecks", ha="center", va="center", fontsize=27, color=NAVY,
            fontweight="bold", linespacing=1.2)
    ax.text(qx + qw / 2, 68, "freshness\n\ntests\n\nrow counts\n\nalerts", ha="center", va="center",
            fontsize=23, color=NAVY, linespacing=1.15)
    for y, _ in steps:
        arrow(ax, qx - 0.5, y + h / 2, main_x + main_w + 0.8, y + h / 2, dashed=True)

    # Consumers
    cons = [("Dashboards", "own rows only"), ("Benchmarks", "aggregates only"), ("Ask", "people and AI")]
    cw, cgap, cx0 = 30, 3, 2.5
    for i, (title, sub) in enumerate(cons):
        x = cx0 + i * (cw + cgap)
        box(ax, x, 12, cw, 13, f"{title}\n{sub}", size=24)
        arrow(ax, mid + (i - 1) * 14, 41.3, x + cw / 2, 25.8)
    ax.text(50, 4.5, "One command: make all", ha="center", fontsize=24, color=NAVY)
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


if __name__ == "__main__":
    print(draw())
