# RetailMart Analytics Pipeline

An ETL pipeline that reads RetailMart data from CSV files or MySQL, validates
and transforms it with Python, loads raw tables into BigQuery, and builds a
reporting warehouse with sales and returns procedures.

## Pipeline

```text
MySQL or CSV files
  |
  v
Python ETL: extract, transform, validate
  |
  v
BigQuery raw tables
  |
  v
BigQuery warehouse: dimensions and facts
  |
  v
Stored procedures and reporting
```

## Requirements

- Python 3.10+
- Google Cloud SDK (`gcloud` and `bq`)
- A Google Cloud project with BigQuery enabled
- MySQL Server, only when using MySQL as the source

Authenticate before running BigQuery commands:

```powershell
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

## Setup

From the repository root:

```powershell
python -m venv .\venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\Python_ETL_Pipeline\requirements.txt
```

Create `Python_ETL_Pipeline/.env`:

```env
GCP_PROJECT_ID=YOUR_PROJECT_ID
BQ_DATASET=retailmart_raw
BQ_LOCATION=US
LOG_LEVEL=INFO

# Required for --source mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=retailmart
MYSQL_USER=retailmart_user
MYSQL_PASSWORD=YOUR_MYSQL_PASSWORD
```

## Run the ETL

CSV mode uses the files in `Sample_Data` and does not require MySQL:

```powershell
python .\Python_ETL_Pipeline\etl_pipeline.py --source csv --data-dir .\Sample_Data
```

For MySQL mode, create the schema in
`MySQL_ER_And_Schema/Schema/mysql_schema.sql`, load the source CSV files into
the database, then run:

```powershell
python .\Python_ETL_Pipeline\etl_pipeline.py --source mysql
```

The ETL validates duplicate keys, foreign-key relationships, line totals, and
transaction totals before loading the eight source tables into `retailmart_raw`.

## Build the BigQuery Warehouse

Run the SQL files in this order after the ETL succeeds:

```powershell
bq query --use_legacy_sql=false (Get-Content .\BigQuery_Warehouse\warehouse_schema.sql -Raw)
bq query --use_legacy_sql=false (Get-Content .\BigQuery_Warehouse\build_warehouse.sql -Raw)
bq query --use_legacy_sql=false (Get-Content .\SQL_Procedures\business_analytics_procedures.sql -Raw)
```

This creates the `retailmart_dw` star schema and the procedures
`sp_sales_metrics` and `sp_returns_analysis`.

## Generate the Report

The report reads current results from BigQuery for the requested date range:

```powershell
python .\Report\generate_report.py --start-date 2024-01-01 --end-date 2024-12-31
Start-Process .\Report\retailmart_analytics_report.html
```

## Project Structure

| Path | Purpose |
| --- | --- |
| `Sample_Data/` | CSV source data |
| `Python_ETL_Pipeline/etl_pipeline.py` | Extract, transform, validate, and load |
| `MySQL_ER_And_Schema/Schema/mysql_schema.sql` | MySQL schema |
| `MySQL_ER_And_Schema/ER_Diagram/` | Mermaid, Graphviz, and HTML ER diagrams |
| `BigQuery_Warehouse/` | BigQuery warehouse DDL and build SQL |
| `SQL_Procedures/` | Sales and returns procedures |
| `Report/` | Report generator and generated HTML report |

## Notes

- CSV mode is the quickest way to test the complete pipeline.
- The warehouse uses date, customer, product, and store dimensions with sales,
  sales-item, and returns fact tables.
- `store_id` is retained from the source because no store master table is provided.
