#полная логика очистки здесь (что б не заполнять фулл Eda)
import re
from pathlib import Path
import pandas as pd


# алго РК
_W1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
_W2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
def iin_checksum_valid(num: str):
    """
    Двухпроходный алгоритм:
      1) sum(d[i] * W1[i]) % 11; если != 10 значит сравниваем с 12-й цифрой.
      2) если == 10, пересчёт с весами W2; если снова 10 то невалиден.
    """
    if not isinstance(num, str) or not re.fullmatch(r"\d{12}", num):
        return False
    d = [int(c) for c in num]
    control = sum(d[i] * _W1[i] for i in range(11)) % 11
    if control == 10:
        control = sum(d[i] * _W2[i] for i in range(11)) % 11
        if control == 10:
            return False
    return control == d[11]


#нормализация идентификаторов
_CHAR_FIX = str.maketrans({"I": "1", "l": "1", "O": "0", "o": "0"})

def normalize_id(raw):
    if pd.isna(raw):
        return None
    s = str(raw).strip().translate(_CHAR_FIX)
    s = re.sub(r"[\s\-]", "", s)
    return s


def normalize_ids(df: pd.DataFrame):
    #Добавляет sender_id_clean или receiver_id_clean
    out = df.copy()
    out["sender_id_clean"] = out["sender_id"].map(normalize_id)
    out["receiver_id_clean"] = out["receiver_id"].map(normalize_id)
    return out

def _id_is_valid(s):
    return isinstance(s, str) and re.fullmatch(r"\d{12}", s) is not None and iin_checksum_valid(s)
    
#записываем флаги отдельно в колонки
def validate_ids(df: pd.DataFrame):
    out = df.copy()
    out["sender_valid"] = out["sender_id_clean"].map(_id_is_valid)
    out["receiver_valid"] = out["receiver_id_clean"].map(_id_is_valid)
    return out



#Нормализируем даты
def normalize_date(raw):
    if pd.isna(raw):
        return None
    s = str(raw).strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)#yyyy-mm-dd
    if m:
        y, mo, d = m.groups()
    else:
        m = re.fullmatch(r"(\d{4})/(\d{2})/(\d{2})", s)#yyyy/mm/dd
        if m:
            y, mo, d = m.groups()
        else:
            m = re.fullmatch(r"(\d{2})[./](\d{2})[./](\d{4})", s)#dd/mm/yyyy или dd.mm.yyy
            if m:
                d, mo, y = m.groups()
            else:
                return None
    try:
        ts = pd.Timestamp(year=int(y), month=int(mo), day=int(d))
    except (ValueError, OverflowError):
        return None
    return ts.strftime("%Y-%m-%d")


def normalize_dates(df: pd.DataFrame):
    out = df.copy()
    out["date_clean"] = out["date"].map(normalize_date)
    return out



#очистка дубликатов
_DEDUP_KEYS = ["sender_id", "receiver_id", "date", "amount_kzt","description", "doc_type"]

def drop_exact_duplicates(df: pd.DataFrame):
    return df.drop_duplicates(subset=_DEDUP_KEYS, keep="first").reset_index(drop=True)



#загрузка данных, полный пайплайн
def load_raw(path: str | Path = "data/transactions.csv"):
    return pd.read_csv(path, dtype=str)


def clean_transactions(path: str | Path = "data/transactions.csv"):
#полный pipeline очистки и приведения типов
    df = load_raw(path)
    df = drop_exact_duplicates(df)
    df = normalize_ids(df)
    df = validate_ids(df)
    df = normalize_dates(df)
    df["amount_kzt"] = pd.to_numeric(df["amount_kzt"], errors="coerce")
    df["date_clean"] = pd.to_datetime(df["date_clean"], errors="coerce")
    df["description"] = df["description"].fillna("").str.strip()
    return df


def build_before_after_table(raw: pd.DataFrame, clean: pd.DataFrame):
    raw_id_cells = pd.concat([raw["sender_id"], raw["receiver_id"]])
    raw_valid_share = raw_id_cells.map(_id_is_valid).mean()

    clean_id_cells = pd.concat([clean.loc[clean["sender_valid"], "sender_id_clean"],
clean.loc[clean["receiver_valid"], "receiver_id_clean"],])
    
    total_clean_cells = len(clean) * 2
    clean_valid_share = len(clean_id_cells) / total_clean_cells
    rows = [
        ("Строк всего", len(raw), len(clean)),
        ("Уникальных операций: ", "-",len(clean)),
        ("Доля валидных ID (контр. сумма РК)", f"{raw_valid_share:.1%}", f"{clean_valid_share:.1%}",),
        ("Пропуски в дате",f"{raw['date'].isna().mean():.1%}",f"{clean['date_clean'].isna().mean():.1%}",),
        ("Пропуски в description",f"{raw['description'].isna().mean():.1%}",f"{(clean['description'] == '').mean():.1%}",),
    ]
    return pd.DataFrame(rows, columns=["Метрика", "Было", "Стало"])

if __name__ == "__main__": 
    raw = load_raw() 
    clean = clean_transactions() 
    print(build_before_after_table(raw, clean).to_string(index=False))