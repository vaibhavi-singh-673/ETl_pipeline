# RetailMart Analytics — Data Engineering Submission

## Run From the VS Code Terminal

The commands below are for the VS Code PowerShell terminal. Run them from the
repository root: `C:\Users\vaibhavi\Desktop\data_pipeline`.

### 1. Create the MySQL schema

Skip this step if the `retailmart` database and tables already exist.

```powershell
Get-Content .\mysql\schema.sql -Raw | mysql -u root -p
```

The project uses the existing MySQL tables as the source for MySQL mode. Check
that the source tables contain rows before continuing:

```powershell
mysql -u retailmart_user -p -D retailmart -e "SHOW TABLES;"
```

The ETL also supports CSV mode directly, so MySQL is not required for a local
pipeline test.

### 2. Prepare Python and environment variables

```powershell
python -m venv .\venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\etl\requirements.txt
```

Set the following values in `etl/.env`:

```env
GCP_PROJECT_ID=retailmart-analytics-508414
BQ_DATASET=retailmart_raw
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=retailmart
MYSQL_USER=retailmart_user
MYSQL_PASSWORD=your_mysql_password
BQ_LOCATION=US
LOG_LEVEL=INFO
```

The MySQL user must have access to the `retailmart` database. BigQuery access
requires Application Default Credentials:

```powershell
gcloud auth application-default login
gcloud config set project retailmart-analytics-508414
```

### 3. Run the ETL

Run from the repository root:

```powershell
python .\etl\etl.py --source mysql
```

For a local CSV test without MySQL:

```powershell
python .\etl\etl.py --source csv --data-dir .\sample_data
```

The ETL creates or reuses the `retailmart_raw` BigQuery dataset, extracts all
eight source tables, validates keys and calculations, and loads the raw tables.

### 4. Build the BigQuery warehouse

The SQL files contain the configured project ID and dataset names. Run them in
this order from the repository root:

```powershell
bq query --use_legacy_sql=false (Get-Content .\bigquery\schema.sql -Raw)
bq query --use_legacy_sql=false (Get-Content .\bigquery\build_warehouse.sql -Raw)
bq query --use_legacy_sql=false (Get-Content .\bigquery\procedures.sql -Raw)
```

`build_warehouse.sql` recreates the `retailmart_dw` dataset and populates the
dimensions and facts from `retailmart_raw`. Run it before creating the stored
procedures.

### 5. Test the stored procedures

```powershell
bq query --use_legacy_sql=false "CALL \`retailmart-analytics-508414.retailmart_dw.sp_sales_metrics\`(DATE('2024-01-01'), DATE('2024-12-31'));"

bq query --use_legacy_sql=false "CALL \`retailmart-analytics-508414.retailmart_dw.sp_returns_analysis\`(DATE('2024-01-01'), DATE('2024-12-31'));"
```

### Troubleshooting

- `Access denied for user 'retailmart_user'`: reset the MySQL user's password
	and grant it access to `retailmart`, then use the same password in `etl/.env`.
- `Could not automatically determine credentials`: run
	`gcloud auth application-default login`.
- `Table ... not found`: run the ETL successfully before running the warehouse
	SQL files.
- If PowerShell blocks virtual-environment activation, run
	`Set-ExecutionPolicy -Scope Process Bypass` and activate again.

## Deliverables
- `mysql/schema.sql` — normalized operational schema.
- `diagrams/retailmart_er.png` — ER diagram (if generated); `retailmart_er.mmd` is the Mermaid source and `retailmart_er.html` is a browser-renderable copy.
- `etl/etl.py` — pandas + MySQL + BigQuery ETL with validation and logging.
- `etl/requirements.txt` — Python dependencies.
- `bigquery/schema.sql` — dimensional warehouse DDL.
- `bigquery/build_warehouse.sql` — source-to-star transformation.
- `bigquery/procedures.sql` — `sp_sales_metrics` and `sp_returns_analysis`.
- `docs/PROJECT_NOTES.md` — assumptions, validation results and run instructions.

## Architecture
MySQL/CSV source → Python pandas validation/transformation → BigQuery raw/source-shaped tables → BigQuery star schema → stored procedures/dashboard.

## Key design choice
The operational schema stays normalized, while the analytical warehouse is denormalized around facts for query performance and dashboard usability.
