import argparse
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import SessionLocal, POSTransaction, init_db


def load_pos(csv_path: str):
    init_db()
    df = pd.read_csv(csv_path)
    db = SessionLocal()

    loaded  = 0
    skipped = 0

    for _, row in df.iterrows():
        # order_id + product_id combination unique గా treat చేస్తున్నాం
        unique_key = f"{row['order_id']}_{row['product_id']}"
        exists = db.query(POSTransaction).filter_by(
            invoice_number=unique_key
        ).first()
        if exists:
            skipped += 1
            continue

        txn = POSTransaction(
            order_id        = str(row["order_id"]),
            invoice_number  = unique_key,
            store_id        = str(row["store_id"]),
            order_date      = str(row["order_date"]),
            order_time      = str(row["order_time"]),
            customer_number = "",
            gmv             = float(row.get("total_amount", 0)),
            dep_name        = str(row.get("brand_name", "")),
            sub_category    = "",
            salesperson_id  = "",
        )
        db.add(txn)
        loaded += 1

    db.commit()
    db.close()
    print(f"✅ POS loaded: {loaded} new, {skipped} skipped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    args = parser.parse_args()
    load_pos(args.csv)