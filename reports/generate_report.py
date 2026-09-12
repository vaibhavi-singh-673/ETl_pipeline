"""Generate the RetailMart HTML report from live BigQuery procedure results."""

import argparse
import html
import os
import re
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery


REPORT_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = REPORT_DIRECTORY.parent
load_dotenv(REPORT_DIRECTORY.parent / "etl" / ".env")
load_dotenv(PROJECT_ROOT / ".env")

START_MARKER = "<!-- LIVE_REPORT_START -->"
END_MARKER = "<!-- LIVE_REPORT_END -->"


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def query_procedure(
    client: bigquery.Client,
    project: str,
    dataset: str,
    procedure: str,
    start_date: date,
    end_date: date,
):
    query = (
        f"CALL `{project}.{dataset}.{procedure}`("
        f"DATE('{start_date.isoformat()}'), "
        f"DATE('{end_date.isoformat()}'));"
    )
    result = client.query(query).result()
    return [field.name for field in result.schema], list(result)


def format_value(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def render_table(fields, rows) -> str:
    if not rows:
        return '<p class="empty-result">No rows returned for this date range.</p>'

    headers = "".join(
        f"<th>{html.escape(field.replace('_', ' '))}</th>"
        for field in fields
    )
    body = []
    for row in rows:
        cells = "".join(
            f"<td>{html.escape(format_value(row[field]))}</td>"
            for field in fields
        )
        body.append(f"<tr>{cells}</tr>")

    return (
        '<table class="live-table">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody>"
        "</table>"
    )


def render_pie_chart(fields, rows) -> str:
    if "category_name" not in fields or "returned_quantity" not in fields:
        return '<p class="empty-result">No category data available.</p>'

    values = []
    for row in rows:
        amount = row["returned_quantity"] or 0
        values.append((str(row["category_name"]), float(amount)))

    values = [(label, amount) for label, amount in values if amount > 0]
    total = sum(amount for _, amount in values)
    if total == 0:
        return '<p class="empty-result">No returned quantity for this date range.</p>'

    colors = ["#167d7f", "#d95d39", "#c58b2a", "#2b8a62", "#7867a8"]
    segments = []
    start = 0.0
    legend = []
    for index, (label, amount) in enumerate(values):
        end = start + (amount / total * 100)
        color = colors[index % len(colors)]
        segments.append(f"{color} {start:.2f}% {end:.2f}%")
        legend.append(
            f'<li><i style="background:{color}"></i>'
            f"{html.escape(label)} <strong>{amount:,.0f}</strong></li>"
        )
        start = end

    return (
        '<div class="pie-chart" '
        f'style="background: conic-gradient({", ".join(segments)})"></div>'
        f'<ul class="pie-legend">{"".join(legend)}</ul>'
    )


def render_live_section(
    sales_result,
    returns_result,
    start_date: date,
    end_date: date,
) -> str:
    period = f"{start_date.isoformat()} to {end_date.isoformat()}"
    sales_fields, sales_rows = sales_result
    returns_fields, returns_rows = returns_result
    return f"""{START_MARKER}
    <section class="section live-results">
      <div class="section-heading">
        <div>
          <h2>Live BigQuery results</h2>
          <p>Generated from the warehouse for {html.escape(period)}.</p>
        </div>
      </div>
            <div class="live-layout">
                <div class="live-grid">
                    <article class="live-card">
                        <h3>Monthly sales metrics</h3>
                        {render_table(sales_fields, sales_rows)}
                    </article>
                    <article class="live-card">
                        <h3>Returns by category</h3>
                        {render_table(returns_fields, returns_rows)}
                    </article>
                </div>
                <aside class="chart-card">
                    <h3>Returned quantity</h3>
                    <p>Share of returned units by category.</p>
                    {render_pie_chart(returns_fields, returns_rows)}
                </aside>
      </div>
    </section>
    {END_MARKER}"""


def update_report(
    output_path: Path,
    live_section: str,
) -> None:
    report = output_path.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    if not pattern.search(report):
        raise ValueError(
            f"Report markers were not found in {output_path}."
        )
    output_path.write_text(
        pattern.sub(live_section, report, count=1),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a RetailMart HTML report from BigQuery."
    )
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2024-12-31")
    parser.add_argument(
        "--output",
        default=str(REPORT_DIRECTORY / "retailmart_analytics_report.html"),
    )
    parser.add_argument("--project", default=os.getenv("GCP_PROJECT_ID"))
    parser.add_argument(
        "--dataset",
        default=os.getenv("BQ_WAREHOUSE_DATASET", "retailmart_dw"),
    )
    args = parser.parse_args()

    if not args.project or args.project == "[YOUR_PROJECT_ID]":
        raise EnvironmentError(
            "Set GCP_PROJECT_ID in etl/.env or pass --project."
        )

    start_date = parse_date(args.start_date)
    end_date = parse_date(args.end_date)
    if end_date < start_date:
        raise ValueError("--end-date must be on or after --start-date.")

    client = bigquery.Client(project=args.project)
    sales_result = query_procedure(
        client,
        args.project,
        args.dataset,
        "sp_sales_metrics",
        start_date,
        end_date,
    )
    returns_result = query_procedure(
        client,
        args.project,
        args.dataset,
        "sp_returns_analysis",
        start_date,
        end_date,
    )

    update_report(
        Path(args.output),
        render_live_section(
            sales_result,
            returns_result,
            start_date,
            end_date,
        ),
    )
    print(f"Report generated: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
