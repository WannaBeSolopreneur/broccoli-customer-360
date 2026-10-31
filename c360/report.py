"""Write the run report and charts from real build outputs."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import config, er_report, quality, semantic  # noqa: E402
from .style import BLUE, MID, NAVY  # noqa: E402
from .warehouse import q  # noqa: E402

plt.rcParams.update({"font.size": 16, "text.color": NAVY, "axes.labelcolor": NAVY,
                     "xtick.color": NAVY, "ytick.color": NAVY, "axes.edgecolor": NAVY,
                     "font.family": "DejaVu Sans"})


def lead_booking_compare() -> list[dict]:
    """Lead to booking rate three ways, per tenant:
    by the job's lead id only, with entity resolution, and the hidden truth."""
    er_report.load_truth()
    return q("""
    WITH lt AS (
        SELECT l.tenant_id AS tenant_id, l.external_lead_id AS external_lead_id, l.received_at AS received_at,
               t.person_id AS person_id, l.booked_within_14d AS er_booked, l.booked_by_ref_only AS ref_booked
        FROM marts.fct_leads AS l
        INNER JOIN er.truth AS t ON t.record_key = concat(l.tenant_id, '|leads:', l.lead_row_id)
    ),
    jt AS (
        SELECT j.tenant_id AS tenant_id, t.person_id AS person_id, j.created_on AS created_on
        FROM marts.fct_jobs AS j INNER JOIN er.truth AS t ON t.record_key = concat(j.tenant_id, '|jobs:', j.job_id)
    ),
    truth AS (
        SELECT lt.tenant_id AS tenant_id, lt.external_lead_id AS external_lead_id,
               countIf(jt.created_on >= lt.received_at AND jt.created_on < lt.received_at + INTERVAL 14 DAY) > 0 AS true_booked
        FROM lt LEFT JOIN jt ON jt.tenant_id = lt.tenant_id AND jt.person_id = lt.person_id
        GROUP BY lt.tenant_id, lt.external_lead_id
    )
    SELECT lt.tenant_id AS tenant_id, count() AS leads,
           round(avg(lt.ref_booked), 4) AS by_lead_id_only,
           round(avg(lt.er_booked), 4) AS with_entity_resolution,
           round(avg(tr.true_booked), 4) AS ground_truth
    FROM lt INNER JOIN truth AS tr ON tr.tenant_id = lt.tenant_id AND tr.external_lead_id = lt.external_lead_id
    GROUP BY lt.tenant_id ORDER BY lt.tenant_id""")


def chart_lead_booking(rows: list[dict], path):
    """Horizontal bars, one group per tenant, so ten tenants stay readable."""
    names = {t["tenant_id"]: t["name"].split(" (")[0] for t in config.TENANTS}
    rows = sorted(rows, key=lambda r: float(r["with_entity_resolution"]))
    fig, ax = plt.subplots(figsize=(13, 11), dpi=150)
    height = 0.27
    ys = range(len(rows))
    series = [("by_lead_id_only", "Lead id only", "#D6E4F2"),
              ("with_entity_resolution", "With entity resolution", BLUE),
              ("ground_truth", "Hidden ground truth", NAVY)]
    for i, (key, label, color) in enumerate(series):
        vals = [float(r[key]) * 100 for r in rows]
        bars = ax.barh([y + (1 - i) * height for y in ys], vals, height, label=label, color=color, edgecolor=NAVY)
        for b, v in zip(bars, vals):
            ax.text(v + 0.6, b.get_y() + b.get_height() / 2, f"{v:.0f}%", va="center", fontsize=12, color=NAVY)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([names[r["tenant_id"]] for r in rows], fontsize=14)
    ax.set_xlabel("% of leads booked within 14 days")
    ax.set_xlim(0, max(float(r["ground_truth"]) for r in rows) * 100 + 12)
    ax.set_title("Lead to booking rate, 10 contractors (synthetic data)", fontsize=20, color=NAVY, pad=14)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="lower right", fontsize=13)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def chart_er(ablation: list[dict], path):
    labels = ["Phone only", "+ Email", "+ System ids", "+ Fuzzy name\nand address"]
    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=150)
    width = 0.38
    xs = list(range(len(ablation)))
    for i, (key, label, color) in enumerate([("precision", "Precision", NAVY), ("recall", "Recall", BLUE)]):
        vals = [a[key] * 100 for a in ablation]
        bars = ax.bar([x + (i - 0.5) * width for x in xs], vals, width, label=label, color=color, edgecolor=NAVY)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.3, f"{v:.1f}%", ha="center", fontsize=13, color=NAVY)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    low = min(min(a["precision"], a["recall"]) for a in ablation) * 100
    ax.set_ylim(max(0, low - 8), 106)
    ax.set_ylabel("Pairwise score")
    ax.set_title("Entity resolution: each rule layer vs ground truth", fontsize=20, color=NAVY, pad=14)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left", ncol=2)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def run() -> dict:
    img = config.DOCS / "img"
    img.mkdir(parents=True, exist_ok=True)
    er_res = er_report.run()
    qual = quality.run()
    compare = lead_booking_compare()
    chart_lead_booking(compare, img / "lead_booking.png")
    chart_er(er_res["ablation"], img / "entity_resolution.png")
    metrics = {name: semantic.query(name, by=["tenant_id"]) for name in semantic.metrics()}
    bench = q("SELECT * FROM benchmarks.metric_benchmarks ORDER BY metric")
    out = {"entity_resolution": er_res["final"], "ablation": er_res["ablation"],
           "quality": qual["summary"], "lead_booking_compare": compare,
           "metrics_by_tenant": metrics, "benchmarks": bench}
    (config.REPORTS / "summary.json").write_text(json.dumps(out, indent=2, default=str))
    return out


def main():
    out = run()
    f = out["entity_resolution"]
    s = out["quality"]
    print(f"entity resolution: precision {f['precision']:.4f}, recall {f['recall']:.4f}, f1 {f['f1']:.4f}")
    print(f"quality: {s['passed']}/{s['total']} checks passed, {s['warnings']} warnings, {s['errors']} errors")
    for r in out["lead_booking_compare"]:
        print(f"lead to booking {r['tenant_id']}: id only {float(r['by_lead_id_only']):.1%}, "
              f"with ER {float(r['with_entity_resolution']):.1%}, truth {float(r['ground_truth']):.1%}")
    print("charts: docs/img/lead_booking.png, docs/img/entity_resolution.png")


if __name__ == "__main__":
    main()
