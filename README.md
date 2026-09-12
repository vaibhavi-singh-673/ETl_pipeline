# RetailMart Analytics - Data Engineering Submission

## Project Overview

RetailMart Analytics is an end-to-end retail data pipeline. It extracts
operational data from MySQL or CSV files, validates and transforms the data
with Python and pandas, loads raw tables into BigQuery, and builds an
analytics-ready warehouse for reporting.

The project covers customers, products, categories, sales transactions, sales
items, vouchers, voucher redemptions, and returns. It includes data-quality
checks, a dimensional warehouse, stored procedures, and database diagrams.

## What This Project Demonstrates

- MySQL schema design with primary keys, foreign keys, constraints, and indexes.
- Python ETL development using pandas, MySQL Connector, and the BigQuery client.
- Validation of duplicate keys, orphan records, and calculated sales totals.
- BigQuery raw tables and a star schema with dimensions and fact tables.
- Business reporting procedures for sales metrics and returns analysis.
- Documentation and visual database modeling with Mermaid and Graphviz.

## Data Flow

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

## Run From the VS Code Terminal

Run these commands in the VS Code PowerShell terminal from the repository root:
`C:\Users\vaibhavi\Desktop\data_pipeline`.

To open the styled ER diagram directly:

```powershell
Start-Process .\diagrams\retailmart_database_diagram.html
```

To generate the project analytics report from live BigQuery results:

```powershell
python .\reports\generate_report.py --start-date 2024-01-01 --end-date 2024-12-31
Start-Process .\reports\retailmart_analytics_report.html
```

The generator calls `sp_sales_metrics` and `sp_returns_analysis` in the
configured BigQuery warehouse and writes the returned rows into the HTML page.
Run it again whenever you want a new reporting period.

### 1. Create or verify the MySQL schema

Run the schema command only when the database is new. If you see
`ERROR 1050 (42S01): Table 'categories' already exists`, the schema is already
created; skip the first command and continue with the user access setup.

```powershell
$mysql = "C:\Program Files\MySQL\MySQL Server 9.7\bin\mysql.exe"
Set-Location "C:\Users\vaibhavi\Desktop\data_pipeline"
Get-Content .\mysql\schema.sql -Raw | & $mysql -u root -p
& $mysql -u retailmart_user -p -D retailmart -e "SHOW TABLES;"
```

If `retailmart_user` returns `ERROR 1045 (28000)`, log in as MySQL root and
create or reset the ETL account. Replace `YOUR_PASSWORD` with the same value
used for `MYSQL_PASSWORD` in `etl/.env`:

```powershell
& $mysql -u root -p -e "CREATE USER IF NOT EXISTS 'retailmart_user'@'localhost' IDENTIFIED BY 'YOUR_PASSWORD'; ALTER USER 'retailmart_user'@'localhost' IDENTIFIED BY 'YOUR_PASSWORD'; GRANT ALL PRIVILEGES ON retailmart.* TO 'retailmart_user'@'localhost'; FLUSH PRIVILEGES;"
& $mysql -u retailmart_user -p -D retailmart -e "SHOW TABLES;"
```

Do not paste the commands with a trailing `)` after the quoted MySQL path.
PowerShell shows `>>` when a quote or command is incomplete; press `Ctrl+C`
and paste the complete block again.

If `mysql` is already on your Windows `PATH`, you can use `mysql` instead of
the `$mysql` variable. If your MySQL installation is in a different folder,
update the `$mysql` path.

The ETL uses the existing MySQL tables as its source. For a local test without
MySQL, use CSV mode in step 3.

### 2. Prepare Python and environment variables

```powershell
python -m venv .\venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\etl\requirements.txt
```

Set these values in `etl/.env`:

```env
GCP_PROJECT_ID=[YOUR_PROJECT_ID]
BQ_DATASET=retailmart_raw
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=retailmart
MYSQL_USER=retailmart_user
MYSQL_PASSWORD=your_mysql_password
BQ_LOCATION=US
LOG_LEVEL=INFO
```

The MySQL user must have access to the `retailmart` database. Authenticate with
Google Application Default Credentials:

```powershell
gcloud auth application-default login
gcloud config set project [YOUR_PROJECT_ID]
```

### 3. Run the ETL

```powershell
python .\etl\etl.py --source mysql
```

For a local CSV test that bypasses MySQL:

```powershell
python .\etl\etl.py --source csv --data-dir .\sample_data
```

The ETL validates keys and calculations, then loads the eight source tables
into the `retailmart_raw` BigQuery dataset.

### 4. Build the BigQuery warehouse

Replace `[YOUR_PROJECT_ID]` in the SQL files with your actual project ID if
needed. Run these commands in order:

```powershell
bq query --use_legacy_sql=false (Get-Content .\bigquery\schema.sql -Raw)
bq query --use_legacy_sql=false (Get-Content .\bigquery\build_warehouse.sql -Raw)
bq query --use_legacy_sql=false (Get-Content .\bigquery\procedures.sql -Raw)
```

The warehouse build recreates `retailmart_dw` and populates its dimensions and
facts from `retailmart_raw`.

### 5. Test the stored procedures

```powershell
bq query --use_legacy_sql=false "CALL \`[YOUR_PROJECT_ID].retailmart_dw.sp_sales_metrics\`(DATE('2024-01-01'), DATE('2024-12-31'));"
bq query --use_legacy_sql=false "CALL \`[YOUR_PROJECT_ID].retailmart_dw.sp_returns_analysis\`(DATE('2024-01-01'), DATE('2024-12-31'));"
```

### Troubleshooting

- For MySQL access denied errors, reset the `retailmart_user` password and
  grant it access to `retailmart`. Use the same password in `etl/.env`.
- For missing Google credentials, run `gcloud auth application-default login`.
- For missing BigQuery tables, run the ETL successfully before the warehouse
  SQL files.
- If PowerShell blocks virtual-environment activation, run
  `Set-ExecutionPolicy -Scope Process Bypass` and activate again.

## Project Notes

The supplied customer data contains 50 records. The ETL does not assume a
fixed row count; it validates keys, relationships, and calculations from the
data it receives.

Validation covers duplicate primary keys, orphan foreign keys, sales-item line
totals compared with `quantity * unit_price`, and transaction totals compared
with the sum of their sales items.

The operational model is normalized. `store_id` is retained on transactions
because the source data does not include a store master table. The warehouse
uses a star schema with date, customer, product, and store dimensions plus
sales, sales-item, and returns facts. Category attributes are flattened into
the product dimension. Revenue uses `fact_sales.net_amount`, and return rate
is returned quantity divided by sold quantity.

## View and Check the ER Diagram

The diagram files are in `diagrams`:

- `retailmart_database_diagram.html` is the easiest version to view. From the repository root:

  ```powershell
  Start-Process .\diagrams\retailmart_database_diagram.html
  ```

- `retailmart_database_diagram.mmd` is the Mermaid source. Install a Mermaid preview
  extension in VS Code, open the file, and use its Mermaid preview command.
- `retailmart_database_diagram.dot` is the Graphviz source. If Graphviz is installed, create
  a PNG with:

  ```powershell
  dot -Tpng .\diagrams\retailmart_database_diagram.dot -o .\diagrams\retailmart_database_diagram.png
  ```

Check the diagram against `mysql/schema.sql`. Every table should be present,
primary keys should be marked `PK`, and foreign-key relationships should match
the constraints in the MySQL schema.

## View the HTML Analytics Report

Open `reports/retailmart_analytics_report.html` to view the project as a
browser-friendly report. It includes the pipeline summary, data-quality checks,
warehouse model, and explanations of both BigQuery procedures.

The report page is a static presentation of the project. Run the BigQuery
procedure commands in the report or in the terminal to retrieve current live
sales and returns results for a selected date range.

## Screenshots

Add screenshots below when presenting the project. Each placeholder describes
the most useful view to capture.

### MySQL Source Database

Show the `retailmart` database and its eight source tables in MySQL Workbench
or the VS Code MySQL terminal.

```text
[Add MySQL schema or SHOW TABLES screenshot here]
```

### ETL Validation and Load

Show the terminal output from `python .\etl\etl.py --source mysql`, including
successful validation and BigQuery loading messages.

```text
[Add ETL execution screenshot here]
```

### BigQuery Warehouse

Show the `retailmart_raw` and `retailmart_dw` datasets, including dimension and
fact tables.

```text
[Add BigQuery warehouse screenshot here]
```

### Analytics Procedures

Show the result of `sp_sales_metrics` or `sp_returns_analysis` in BigQuery.

```text
[Add stored procedure result screenshot here]
```

### Database Relationship Diagram

Show the styled diagram opened with the `Start-Process` command above.

```text
[Add ER diagram screenshot here]
```

### Report Diagram

Show the styled diagram opened with the `Start-Process` command above.

```text
[Add Report diagram screenshot here]
```

## Deliverables

- `mysql/schema.sql` - normalized operational schema.
- `diagrams/retailmart_database_diagram.html` - browser-renderable ER diagram.
- `diagrams/retailmart_database_diagram.mmd` - Mermaid ER diagram source.
- `diagrams/retailmart_database_diagram.dot` - Graphviz ER diagram source.
- `reports/retailmart_analytics_report.html` - browser-renderable analytics report.
- `reports/generate_report.py` - generates the HTML report from live BigQuery data.
- `etl/etl.py` - pandas, MySQL, and BigQuery ETL with validation and logging.
- `etl/requirements.txt` - Python dependencies.
- `bigquery/schema.sql` - dimensional warehouse DDL.
- `bigquery/build_warehouse.sql` - source-to-star transformation.
- `bigquery/procedures.sql` - analytics stored procedures.

## Architecture

MySQL or CSV source -> Python pandas validation and transformation -> BigQuery
raw tables -> BigQuery star schema -> stored procedures and reporting.
