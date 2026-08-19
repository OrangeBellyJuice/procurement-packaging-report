import re
import sys
import duckdb
import pandas as pd
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

MAPPING_PATH = BASE_DIR / "data" / "product_mapping.csv"
EXPORT_FOLDER = BASE_DIR / "data" / "famous_exports" / "shipping_reports"
DATABASE_PATH = BASE_DIR / "database" / "procurement_mart.duckdb"

MAPPING = pd.read_csv(MAPPING_PATH)

results = []

for file in sorted(EXPORT_FOLDER.glob("shipments_by_product_2026_??_??.csv")):

    date_string = re.search(
        r"(\d{4}_\d{2}_\d{2})$",
        file.stem
    ).group(1)

    report_date = pd.to_datetime(
        date_string,
        format="%Y_%m_%d"
    )
    
    shipping_report = (
        pd.read_csv(
            file,
            usecols=['productdescr', 'qnt1']
        )
        .rename(columns={
            'productdescr': 'product',
            'qnt1': 'quantity'
        })
    )

    for rule in MAPPING.itertuples(index=False):
        weight = str(rule.weight).strip()
        label = str(rule.label).strip()
    
        pattern = (
            rf"(?<![\w.])"
            rf"{re.escape(weight)}"
            rf"(?!\w)"
            rf".*{re.escape(label)}\s*$"
        )

        matches = shipping_report["product"].str.contains(
            pattern,
            case=False,
            regex=True,
            na=False
        )

        results.append({
            "product": f"{weight} {label}",
            "weight": weight,
            "label": label,
            "quantity": shipping_report.loc[matches, "quantity"].sum(),
            "date": report_date
        })

summary = pd.DataFrame(results)

with duckdb.connect(DATABASE_PATH) as con:
    con.execute("DROP TABLE IF EXISTS fact_shipment")

    con.execute("""
        CREATE TABLE fact_shipment (
            product VARCHAR NOT NULL,
            weight VARCHAR NOT NULL,
            label VARCHAR NOT NULL,
            quantity BIGINT NOT NULL,
            date DATE NOT NULL
        )
    """)

    for row in summary.itertuples(index=False):
        con.execute(
            """
            INSERT INTO fact_shipment (
                product,
                weight,
                label,
                quantity,
                date
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                row.product,
                row.weight,
                row.label,
                int(row.quantity),
                row.date,
            ],
        )
