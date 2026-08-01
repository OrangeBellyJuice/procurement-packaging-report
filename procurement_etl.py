import re
import duckdb
import pandas as pd
from datetime import datetime

"""
    1. need to read product_mapping and shipping_report
        - shipping_report: just want 2 columns and make sure data type is valid
    2. need to count up shipped totals by weight and label combinations in product_mapping
        - WARNING: 2.5KG & 5KG weight labels may get over counted 
    3. upload data procurement.duckdb
"""

MAPPING = pd.read_csv('./data/product_mapping.csv')

t = datetime.now()
#timestamp = (
#                f'{t.year}_{"0" + str(t.month) if t.month < 10 else t.month}'
#                f'_{"0" + str(t.day) if t.day < 10 else t.day}'
#)

# HARD CODED FOR NOW FOR DEVELOPMENT
timestamp = '2026_07_16'

FILE = 'shipping_report_' + timestamp + '.csv'

shipping_report = pd.read_csv('./data/famous_exports/' + FILE, usecols=['productdescr', 'qnt1']).rename(columns={'qnt1' : 'quantity'})

shipping_report["productdescr"] = shipping_report["productdescr"].astype('str')
shipping_report["quantity"] = shipping_report["quantity"].astype('int').fillna(0)

results = []

for rule in MAPPING.itertuples(index=False):
    weight = str(rule.weight).strip()
    label = str(rule.label).strip()
    
    pattern = (
        rf"(?<![\d.])"
        rf"{re.escape(weight)}"
        rf"(?!\w)"
        rf".*{re.escape(label)}\s*$"
    )

    matches = shipping_report["productdescr"].str.contains(
        pattern,
        case=False,
        regex=True,
        na=False
    )

    results.append({
        "weight": weight,
        "label": label,
        "quantity": shipping_report.loc[matches, "quantity"].sum()
    })

summary = pd.DataFrame(results)

# print(summary)

with duckdb.connect('./database/procurement_mart.db') as con:
    con.execute("DROP TABLE IF EXISTS fact_shipment")
    con.execute("""
              CREATE TABLE IF NOT EXISTS fact_shipment (
                weight VARCHAR NOT NULL, 
                label VARCHAR NOT NULL, 
                quantity BIGINT NOT NULL, 
                imported_at TIMESTAMP NOT NULL 
                )
                """)

    for row in summary.itertuples(index=False):
        con.execute(
            """
            INSERT INTO fact_shipment (
                weight,
                label,
                quantity,
                imported_at
            )
            VALUES (?, ?, ?, current_timestamp::TIMESTAMP(0))
        """,
        [
            row.weight,
            row.label,
            row.quantity
        ],
    )    

    con.table("fact_shipment").show()

    con.execute("DROP TABLE fact_shipment")
