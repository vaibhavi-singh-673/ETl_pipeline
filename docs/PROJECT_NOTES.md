# RetailMart Challenge Notes

## Source-data observations
The supplied README says 200 customer records, but the actual `customers.csv` contains 50 rows. The pipeline does not hard-code expected row counts; it validates keys and relationships from the actual data.

### Integrity checks performed against supplied sample data
- Customer duplicate PKs: 0
- Category duplicate PKs: 0
- Product -> category orphan rows: 0
- Sales item -> transaction orphan rows: 0
- Sales item -> product orphan rows: 0
- Voucher redemption FK orphans: 0
- Return FK orphans: 0
- Sales item line-total mismatches: 0
- Transaction header totals vs. sum of line totals: 0

## Modeling decisions
1. The operational model is normalized to 3NF. Store is represented by `store_id` because the supplied source does not provide a store master table.
2. The warehouse uses a star schema. Category attributes are flattened into `dim_product` to avoid an unnecessary snowflake join.
3. `fact_sales` has transaction grain; `fact_sales_item` has line-item grain; `fact_returns` has return-event grain.
4. Revenue for dashboard reporting is `fact_sales.net_amount`, matching the source calculation concept: gross amount - discount + tax.
5. Return rate is returned quantity / sold quantity. Revenue impact is processed refund amount.
6. BigQuery tables are partitioned by event date and clustered on common filter/grouping keys.

## Run
Run the complete pipeline from the repository root in the VS Code PowerShell
terminal. The copy-paste procedure is maintained in `README_SUBMISSION.md`.

1. Create or verify the MySQL schema and source tables.
2. Install `etl/requirements.txt` in the project virtual environment.
3. Set MySQL and BigQuery values in `etl/.env`.
4. Authenticate with Google Application Default Credentials.
5. Run `python .\etl\etl.py --source mysql`.
6. Run `bigquery/schema.sql`, `bigquery/build_warehouse.sql`, and
   `bigquery/procedures.sql` in that order with the `bq` CLI.

For a local test that bypasses MySQL, run
`python .\etl\etl.py --source csv --data-dir .\sample_data`.
