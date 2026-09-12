"""
RetailMart Analytics
MySQL / CSV -> BigQuery ETL Pipeline

Usage
-----

CSV mode:
    python etl_pipeline.py --source csv --data-dir ../Sample_Data

MySQL mode:
    python etl_pipeline.py --source mysql

Required .env variables
-----------------------

GCP_PROJECT_ID=your-gcp-project-id
BQ_DATASET=retailmart_raw

For MySQL mode:
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=retailmart
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=your_mysql_password

Optional:
BQ_LOCATION=US
LOG_LEVEL=INFO

BigQuery authentication
-----------------------

Run once before using BigQuery:

    gcloud auth application-default login

The ETL flow is:

    CSV / MySQL
        |
        v
    Extract
        |
        v
    Pandas transformation
        |
        v
    Data-quality validation
        |
        v
    BigQuery raw layer
        |
        v
    Warehouse transformation / analytics
"""

# ============================================================================
# Imports
# ============================================================================

import argparse
import io
import logging
import os
from pathlib import Path
from typing import Dict

import mysql.connector
import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery


# ============================================================================
# Project paths and environment
# ============================================================================

ETL_DIRECTORY = Path(__file__).resolve().parent
PROJECT_ROOT = ETL_DIRECTORY.parent

# Try .env inside Python_ETL_Pipeline/ first.
# If it doesn't exist, try .env in the project root.
env_loaded = load_dotenv(ETL_DIRECTORY / ".env")

if not env_loaded:
    load_dotenv(PROJECT_ROOT / ".env")


# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

logger = logging.getLogger("retailmart_etl")


# ============================================================================
# Source table configuration
# ============================================================================

TABLES = {
    "categories": {
        "pk": ["category_id"],
        "date_cols": [],
    },

    "products": {
        "pk": ["product_id"],
        "date_cols": [],
    },

    "customers": {
        "pk": ["customer_id"],
        "date_cols": ["registration_date"],
    },

    "sales_transactions": {
        "pk": ["transaction_id"],
        "date_cols": ["transaction_date"],
    },

    "sales_items": {
        "pk": ["item_id"],
        "date_cols": [],
    },

    "vouchers": {
        "pk": ["voucher_id"],
        "date_cols": ["valid_from", "valid_to"],
    },

    "voucher_redemptions": {
        "pk": ["redemption_id"],
        "date_cols": ["redemption_date"],
    },

    "returns": {
        "pk": ["return_id"],
        "date_cols": ["return_date"],
    },
}


# ============================================================================
# Environment validation
# ============================================================================

def validate_environment(source: str) -> None:
    """
    Validate environment variables before starting the ETL.
    """

    required = [
        "GCP_PROJECT_ID",
        "BQ_DATASET",
    ]

    if source == "mysql":
        required.extend(
            [
                "MYSQL_HOST",
                "MYSQL_DATABASE",
                "MYSQL_USER",
                "MYSQL_PASSWORD",
            ]
        )

    missing = [
        variable
        for variable in required
        if not os.getenv(variable)
    ]

    if missing:
        raise EnvironmentError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + ". Check your .env file."
        )

    logger.info("Environment configuration validated.")


# ============================================================================
# CSV extraction
# ============================================================================

def load_csv_tables(data_dir: str) -> Dict[str, pd.DataFrame]:
    """
    Extract all source tables from CSV files.
    """

    path = Path(data_dir)

    if not path.exists():
        raise FileNotFoundError(
            f"Data directory does not exist: {path.resolve()}"
        )

    tables: Dict[str, pd.DataFrame] = {}

    logger.info(
        "Reading CSV files from: %s",
        path.resolve(),
    )

    for table_name in TABLES:

        file_path = path / f"{table_name}.csv"

        if not file_path.exists():
            raise FileNotFoundError(
                f"Required CSV file not found: "
                f"{file_path.resolve()}"
            )

        logger.info(
            "Reading CSV: %s",
            file_path.name,
        )

        df = pd.read_csv(
            file_path,
            keep_default_na=True,
        )

        tables[table_name] = df

        logger.info(
            "Read %d rows from %s",
            len(df),
            file_path.name,
        )

    return tables


# ============================================================================
# MySQL extraction
# ============================================================================

def load_mysql_tables() -> Dict[str, pd.DataFrame]:
    """
    Extract all source tables from MySQL.
    """

    logger.info(
        "Connecting to MySQL database '%s'...",
        os.environ["MYSQL_DATABASE"],
    )

    try:

        connection = mysql.connector.connect(
            host=os.environ["MYSQL_HOST"],
            port=int(
                os.getenv(
                    "MYSQL_PORT",
                    "3306",
                )
            ),
            database=os.environ["MYSQL_DATABASE"],
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
        )

    except mysql.connector.Error as error:

        if getattr(error, "errno", None) == 1045:

            raise ConnectionError(
                "MySQL rejected the configured account "
                f"'{os.environ['MYSQL_USER']}'. "
                "Check MYSQL_USER and MYSQL_PASSWORD "
                "in your .env file."
            ) from error

        raise

    logger.info(
        "Connected to MySQL successfully."
    )

    tables: Dict[str, pd.DataFrame] = {}

    try:

        for table_name in TABLES:

            logger.info(
                "Extracting MySQL table: %s",
                table_name,
            )

            query = f"""
                SELECT *
                FROM `{table_name}`
            """

            df = pd.read_sql(
                query,
                connection,
            )

            tables[table_name] = df

            logger.info(
                "Extracted %d rows from MySQL table %s",
                len(df),
                table_name,
            )

    finally:

        connection.close()

        logger.info(
            "MySQL connection closed."
        )

    return tables


# ============================================================================
# Transformation
# ============================================================================

def transform(
    tables: Dict[str, pd.DataFrame],
) -> Dict[str, pd.DataFrame]:
    """
    Transform source DataFrames into stable types suitable for BigQuery.
    """

    logger.info(
        "Starting transformation..."
    )

    # Work on copies so extraction results are not modified.
    out = {
        table_name: df.copy()
        for table_name, df in tables.items()
    }

    # ------------------------------------------------------------------------
    # Convert date columns
    # ------------------------------------------------------------------------

    for table_name, specification in TABLES.items():

        for column in specification["date_cols"]:

            if column not in out[table_name].columns:
                continue

            out[table_name][column] = (
                pd.to_datetime(
                    out[table_name][column],
                    errors="coerce",
                ).dt.date
            )

    # ------------------------------------------------------------------------
    # Normalize identifier columns
    # ------------------------------------------------------------------------
    #
    # IDs are identifiers rather than measures.
    #
    # For BigQuery raw ingestion we deliberately represent them as STRING.
    # This avoids Arrow UUID/binary inference issues and also makes the raw
    # layer tolerant of future alphanumeric business keys.
    # ------------------------------------------------------------------------

    for table_name, df in out.items():

        for column in df.columns:

            if column.endswith("_id"):

                numeric_values = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

                # If all non-null values are whole numbers, convert them
                # cleanly to strings without ".0".
                if (
                    numeric_values.notna().any()
                    and numeric_values.dropna().mod(1).eq(0).all()
                ):

                    out[table_name][column] = (
                        numeric_values
                        .astype("Int64")
                        .astype("string")
                    )

                else:

                    out[table_name][column] = (
                        df[column]
                        .astype("string")
                    )

    # ------------------------------------------------------------------------
    # Customer phone number
    # ------------------------------------------------------------------------

    if "customers" in out and "phone" in out["customers"].columns:

        phone_numeric = pd.to_numeric(
            out["customers"]["phone"],
            errors="coerce",
        )

        out["customers"]["phone"] = (
            phone_numeric
            .astype("Int64")
            .astype("string")
        )

    # ------------------------------------------------------------------------
    # Boolean columns
    # ------------------------------------------------------------------------

    boolean_columns = [
        ("products", "is_active"),
        ("vouchers", "is_active"),
    ]

    for table_name, column in boolean_columns:

        if (
            table_name not in out
            or column not in out[table_name].columns
        ):
            continue

        values = (
            out[table_name][column]
            .astype("string")
            .str.strip()
            .str.lower()
        )

        out[table_name][column] = values.map(
            {
                "true": True,
                "false": False,
                "1": True,
                "0": False,
                "yes": True,
                "no": False,
                "y": True,
                "n": False,
            }
        ).astype("boolean")

    # ------------------------------------------------------------------------
    # Numeric columns
    # ------------------------------------------------------------------------

    numeric_columns = {
        "products": [
            "unit_price",
            "cost_price",
            "stock_quantity",
        ],

        "sales_transactions": [
            "subtotal",
            "discount_amount",
            "tax_amount",
            "total_amount",
        ],

        "sales_items": [
            "quantity",
            "unit_price",
            "line_total",
        ],

        "vouchers": [
            "discount_value",
        ],

        "voucher_redemptions": [
            "discount_applied",
        ],

        "returns": [
            "return_quantity",
            "refund_amount",
        ],
    }

    for table_name, columns in numeric_columns.items():

        for column in columns:

            if (
                table_name in out
                and column in out[table_name].columns
            ):

                out[table_name][column] = pd.to_numeric(
                    out[table_name][column],
                    errors="coerce",
                )

    logger.info(
        "Transformation completed."
    )

    return out


# ============================================================================
# Validation helpers
# ============================================================================

def validate_required_columns(
    tables: Dict[str, pd.DataFrame],
) -> list[str]:
    """
    Ensure expected tables and primary-key columns exist.
    """

    errors = []

    for table_name, specification in TABLES.items():

        if table_name not in tables:
            errors.append(
                f"Missing table: {table_name}"
            )
            continue

        df = tables[table_name]

        for column in specification["pk"]:

            if column not in df.columns:

                errors.append(
                    f"{table_name} is missing required "
                    f"column '{column}'"
                )

    return errors


# ============================================================================
# Data-quality validation
# ============================================================================

def validate(
    tables: Dict[str, pd.DataFrame],
) -> None:
    """
    Validate:

    1. Required tables and columns
    2. Primary keys
    3. Foreign keys
    4. Sales line totals
    """

    logger.info(
        "Starting data-quality validation..."
    )

    errors = []

    # ------------------------------------------------------------------------
    # Required tables and columns
    # ------------------------------------------------------------------------

    errors.extend(
        validate_required_columns(tables)
    )

    if errors:

        for error in errors:
            logger.error(
                "VALIDATION: %s",
                error,
            )

        raise ValueError(
            f"Validation failed with {len(errors)} issue(s)."
        )

    # ------------------------------------------------------------------------
    # Primary key validation
    # ------------------------------------------------------------------------

    for table_name, specification in TABLES.items():

        df = tables[table_name]

        for primary_key in specification["pk"]:

            if df[primary_key].isna().any():

                errors.append(
                    f"{table_name}.{primary_key} "
                    "contains NULL values"
                )

            if df[primary_key].duplicated().any():

                duplicate_count = int(
                    df[primary_key].duplicated().sum()
                )

                errors.append(
                    f"{table_name}.{primary_key} "
                    f"contains {duplicate_count} duplicate value(s)"
                )

    # ------------------------------------------------------------------------
    # Foreign-key validation
    # ------------------------------------------------------------------------

    foreign_key_checks = [

        (
            "products",
            "category_id",
            "categories",
            "category_id",
        ),

        (
            "sales_transactions",
            "customer_id",
            "customers",
            "customer_id",
        ),

        (
            "sales_items",
            "transaction_id",
            "sales_transactions",
            "transaction_id",
        ),

        (
            "sales_items",
            "product_id",
            "products",
            "product_id",
        ),

        (
            "voucher_redemptions",
            "voucher_id",
            "vouchers",
            "voucher_id",
        ),

        (
            "voucher_redemptions",
            "transaction_id",
            "sales_transactions",
            "transaction_id",
        ),

        (
            "voucher_redemptions",
            "customer_id",
            "customers",
            "customer_id",
        ),

        (
            "returns",
            "transaction_id",
            "sales_transactions",
            "transaction_id",
        ),

        (
            "returns",
            "item_id",
            "sales_items",
            "item_id",
        ),

        (
            "returns",
            "customer_id",
            "customers",
            "customer_id",
        ),

        (
            "returns",
            "product_id",
            "products",
            "product_id",
        ),
    ]

    for (
        child_table,
        child_column,
        parent_table,
        parent_column,
    ) in foreign_key_checks:

        child_values = (
            tables[child_table][child_column]
            .dropna()
            .astype("string")
        )

        parent_values = (
            tables[parent_table][parent_column]
            .dropna()
            .astype("string")
        )

        orphan_mask = ~child_values.isin(
            parent_values
        )

        if orphan_mask.any():

            orphan_count = int(
                orphan_mask.sum()
            )

            errors.append(
                f"{child_table}.{child_column} has "
                f"{orphan_count} orphan value(s) "
                f"referencing "
                f"{parent_table}.{parent_column}"
            )

    # ------------------------------------------------------------------------
    # Sales item calculation validation
    # ------------------------------------------------------------------------

    items = tables["sales_items"]

    required_sales_columns = [
        "quantity",
        "unit_price",
        "line_total",
    ]

    if all(
        column in items.columns
        for column in required_sales_columns
    ):

        calculated_line_total = (
            items["quantity"]
            * items["unit_price"]
        )

        actual_line_total = (
            items["line_total"]
        )

        mismatch_mask = (
            actual_line_total
            .fillna(0)
            .round(2)
            .ne(
                calculated_line_total
                .fillna(0)
                .round(2)
            )
        )

        if mismatch_mask.any():

            mismatch_count = int(
                mismatch_mask.sum()
            )

            errors.append(
                "sales_items.line_total does not equal "
                "quantity * unit_price for "
                f"{mismatch_count} row(s)"
            )

    # ------------------------------------------------------------------------
    # Validation result
    # ------------------------------------------------------------------------

    if errors:

        for error in errors:

            logger.error(
                "VALIDATION: %s",
                error,
            )

        raise ValueError(
            f"Validation failed with {len(errors)} issue(s)."
        )

    logger.info(
        "Validation passed for %d tables.",
        len(tables),
    )


# ============================================================================
# BigQuery schema mapping
# ============================================================================

def pandas_to_bq_schema(
    df: pd.DataFrame,
) -> list:
    """
    Create an explicit BigQuery schema from the transformed DataFrame.

    IDs are STRING in the raw layer.
    Dates are DATE.
    Financial/numeric values use FLOAT64.
    """

    schema = []

    date_columns = {
        "registration_date",
        "transaction_date",
        "valid_from",
        "valid_to",
        "redemption_date",
        "return_date",
    }

    integer_columns = {
        "stock_quantity",
        "quantity",
        "return_quantity",
    }

    boolean_columns = {
        "is_active",
    }

    for column in df.columns:

        dtype = str(
            df[column].dtype
        )

        # ------------------------------------------------------------
        # Identifier columns
        # ------------------------------------------------------------

        if column.endswith("_id"):

            field_type = "STRING"

        # ------------------------------------------------------------
        # Dates
        # ------------------------------------------------------------

        elif column in date_columns:

            field_type = "DATE"

        # ------------------------------------------------------------
        # Booleans
        # ------------------------------------------------------------

        elif column in boolean_columns:

            field_type = "BOOLEAN"

        # ------------------------------------------------------------
        # Whole-number measures
        # ------------------------------------------------------------

        elif column in integer_columns:

            field_type = "INTEGER"

        # ------------------------------------------------------------
        # Numeric measures
        # ------------------------------------------------------------

        elif pd.api.types.is_numeric_dtype(
            df[column]
        ):

            field_type = "FLOAT64"

        # ------------------------------------------------------------
        # Everything else
        # ------------------------------------------------------------

        else:

            field_type = "STRING"

        schema.append(
            bigquery.SchemaField(
                name=column,
                field_type=field_type,
                mode="NULLABLE",
            )
        )

    return schema


# ============================================================================
# BigQuery CSV load
# ============================================================================

def load_bigquery(
    tables: Dict[str, pd.DataFrame],
) -> None:
    """
    Load transformed DataFrames into BigQuery.

    IMPORTANT:
    This implementation intentionally uses BigQuery's CSV file loader
    instead of load_table_from_dataframe().

    That means the ETL does not rely on PyArrow for the DataFrame -> BQ
    conversion and avoids ArrowInvalid conversion errors.
    """

    project = os.environ["GCP_PROJECT_ID"]

    dataset = os.environ["BQ_DATASET"]

    location = os.getenv(
        "BQ_LOCATION",
        "US",
    )

    logger.info(
        "Connecting to BigQuery project: %s",
        project,
    )

    client = bigquery.Client(
        project=project
    )

    dataset_id = f"{project}.{dataset}"

    # ------------------------------------------------------------------------
    # Create dataset
    # ------------------------------------------------------------------------

    dataset_reference = bigquery.Dataset(
        dataset_id
    )

    dataset_reference.location = location

    client.create_dataset(
        dataset_reference,
        exists_ok=True,
    )

    logger.info(
        "BigQuery dataset ready: %s",
        dataset_id,
    )

    # ------------------------------------------------------------------------
    # Load tables
    # ------------------------------------------------------------------------

    for table_name, df in tables.items():

        table_id = (
            f"{project}.{dataset}.{table_name}"
        )

        logger.info(
            "Loading %d rows into %s",
            len(df),
            table_id,
        )

        # ------------------------------------------------------------
        # Copy the DataFrame.
        # ------------------------------------------------------------

        load_df = df.copy()

        # ------------------------------------------------------------
        # Convert dates to ISO strings.
        #
        # BigQuery's CSV loader will convert these to DATE because
        # the schema explicitly declares DATE.
        # ------------------------------------------------------------

        for column in load_df.columns:

            if column in {
                "registration_date",
                "transaction_date",
                "valid_from",
                "valid_to",
                "redemption_date",
                "return_date",
            }:

                load_df[column] = (
                    load_df[column]
                    .apply(
                        lambda value:
                        value.isoformat()
                        if pd.notna(value)
                        else ""
                    )
                )

        # ------------------------------------------------------------
        # Normalize IDs to plain Python strings.
        # ------------------------------------------------------------

        for column in load_df.columns:

            if column.endswith("_id"):

                load_df[column] = (
                    load_df[column]
                    .astype("string")
                    .fillna("")
                )

        # ------------------------------------------------------------
        # Normalize booleans.
        # ------------------------------------------------------------

        for column in load_df.columns:

            if column == "is_active":

                load_df[column] = (
                    load_df[column]
                    .map(
                        lambda value:
                        "TRUE"
                        if value is True
                        else (
                            "FALSE"
                            if value is False
                            else ""
                        )
                    )
                )

        # ------------------------------------------------------------
        # Convert pandas missing values to empty CSV fields.
        # ------------------------------------------------------------

        load_df = load_df.astype(
            object
        ).where(
            pd.notna(load_df),
            ""
        )

        # ------------------------------------------------------------
        # Generate explicit BigQuery schema.
        # ------------------------------------------------------------

        schema = pandas_to_bq_schema(
            df
        )

        # ------------------------------------------------------------
        # Write CSV into memory.
        #
        # No temporary files are required.
        # ------------------------------------------------------------

        csv_buffer = io.StringIO()

        load_df.to_csv(
            csv_buffer,
            index=False,
        )

        csv_bytes = io.BytesIO(
            csv_buffer.getvalue().encode(
                "utf-8"
            )
        )

        # ------------------------------------------------------------
        # BigQuery load configuration.
        # ------------------------------------------------------------

        job_config = bigquery.LoadJobConfig(
            source_format=(
                bigquery.SourceFormat.CSV
            ),

            skip_leading_rows=1,

            schema=schema,

            autodetect=False,

            write_disposition=(
                bigquery.WriteDisposition.WRITE_TRUNCATE
            ),

            allow_quoted_newlines=True,
        )

        # ------------------------------------------------------------
        # Upload to BigQuery.
        # ------------------------------------------------------------

        try:

            load_job = (
                client.load_table_from_file(
                    csv_bytes,
                    table_id,
                    job_config=job_config,
                )
            )

            load_job.result()

        except Exception:

            logger.exception(
                "Failed to load table: %s",
                table_id,
            )

            raise

        # ------------------------------------------------------------
        # Verify destination table.
        # ------------------------------------------------------------

        destination = client.get_table(
            table_id
        )

        logger.info(
            "Loaded %d rows into %s successfully.",
            destination.num_rows,
            table_id,
        )

    logger.info(
        "All %d tables loaded successfully into BigQuery.",
        len(tables),
    )


# ============================================================================
# Main ETL orchestration
# ============================================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "RetailMart MySQL/CSV -> BigQuery ETL"
        )
    )

    parser.add_argument(
        "--source",
        choices=[
            "csv",
            "mysql",
        ],
        default="csv",
        help=(
            "Source system: csv or mysql"
        ),
    )

    parser.add_argument(
        "--data-dir",
        default="../sample_data",
        help=(
            "Directory containing source CSV files"
        ),
    )

    args = parser.parse_args()

    logger.info(
        "Starting RetailMart ETL; source=%s",
        args.source,
    )

    # ------------------------------------------------------------------------
    # 1. Configuration
    # ------------------------------------------------------------------------

    validate_environment(
        args.source
    )

    # ------------------------------------------------------------------------
    # 2. Extract
    # ------------------------------------------------------------------------

    if args.source == "csv":

        logger.info(
            "Extracting data from CSV files..."
        )

        tables = load_csv_tables(
            args.data_dir
        )

    else:

        logger.info(
            "Extracting data from MySQL..."
        )

        tables = load_mysql_tables()

    # ------------------------------------------------------------------------
    # 3. Transform
    # ------------------------------------------------------------------------

    tables = transform(
        tables
    )

    # ------------------------------------------------------------------------
    # 4. Validate
    # ------------------------------------------------------------------------

    validate(
        tables
    )

    # ------------------------------------------------------------------------
    # 5. Load into BigQuery raw layer
    # ------------------------------------------------------------------------

    load_bigquery(
        tables
    )

    # ------------------------------------------------------------------------
    # Complete
    # ------------------------------------------------------------------------

    logger.info(
        "ETL completed successfully."
    )


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    main()