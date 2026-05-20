import sqlite3
from pathlib import Path
import pandas as pd
from cleaning import clean_transactions
_COLS = ["sender_id_clean","receiver_id_clean","date_clean","amount_kzt",
    "description","doc_type","sender_valid","receiver_valid",]
def _project_root():
    return Path(__file__).resolve().parent.parent

def load_to_sqlite(csv_path=None, db_path=None):
    root = _project_root()
    if csv_path is None:
        csv_path = root / "data" / "transactions.csv"
    if db_path is None:
        db_path = root / "data" / "counterparty.db"

    print(f"[db.py] Читаем и чистим {csv_path} ...")
    df = clean_transactions(csv_path)
    df["date_clean"]     = df["date_clean"].dt.strftime("%Y-%m-%d")
    df["sender_valid"]   = df["sender_valid"].astype(int)
    df["receiver_valid"] = df["receiver_valid"].astype(int)
    to_db = df[_COLS].copy()

    print(f"[db.py] Записываем {len(to_db):,} строк в {db_path} ...")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        to_db.to_sql("transactions", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sender   ON transactions(sender_id_clean)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_receiver ON transactions(receiver_id_clean)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date     ON transactions(date_clean)")

    print("[db.py] Готово. База создана.")

def run_query(sql, db_path=None):
    if db_path is None:
        db_path = _project_root() / "data" / "counterparty.db"
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(sql, conn)


if __name__ == "__main__":
    load_to_sqlite()