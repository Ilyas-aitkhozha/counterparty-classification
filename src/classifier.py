import json
import re
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

def load_categories(path: str | Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


#приводим к нижнему регистру, выкидываем мусорные символы
def preprocess(text: str):
    text = str(text).lower()
    text = re.sub(r"[^\w\sа-яёa-z0-9]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


#keyword/regex baseline по categories.json
class KeywordClassifier:
    def __init__(self, categories: dict):
        self.categories = categories
        self._rules: list[tuple[str, str, list[re.Pattern]]] = []
        for code, info in categories.items():
            patterns = [self._compile_keyword(kw) for kw in info["keywords"]]
            self._rules.append((code, info["name"], patterns))

    #ключевые слова это стемы, поэтому матчим с привязкой к началу слова
    @staticmethod
    def _compile_keyword(kw: str):
        stem = re.escape(kw.lower().strip())
        return re.compile(rf"(?<![^\W\d_]){stem}", re.IGNORECASE)

    def predict_one(self, text: str) -> tuple[Optional[str], Optional[str], float]:
        text_lower = preprocess(text)
        scores: dict[str, int] = {}
        for code, name, patterns in self._rules:
            hits = sum(1 for p in patterns if p.search(text_lower))
            if hits > 0:
                scores[code] = hits

        if not scores:
            return None, None, 0.0

        best_code = max(scores, key=scores.__getitem__)
        best_hits = scores[best_code]
        total_hits = sum(scores.values())
        confidence = best_hits / total_hits

        best_name = self.categories[best_code]["name"]
        return best_code, best_name, round(confidence, 4)

    def predict(self, texts: list[str]):
        results = [self.predict_one(t) for t in texts]
        codes, names, confs = zip(*results)
        return pd.DataFrame({
            "pred_code": codes,
            "pred_name": names,
            "confidence": confs,
        })


#TF-IDF (word + char n-grams) + LogReg, обучается на авторазметке baseline'а
class MLClassifier:
    THRESHOLD = 0.40

    def __init__(self, categories: Optional[dict] = None):
        self.pipeline: Optional[Pipeline] = None
        self.le = LabelEncoder()
        self.classes_: Optional[np.ndarray] = None
        self.code2name: dict = (
            {c: info["name"] for c, info in categories.items()}
            if categories else {}
        )

    def _build_pipeline(self):
        from sklearn.pipeline import FeatureUnion

        word_tfidf = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            min_df=2,
            max_features=30_000,
            sublinear_tf=True,
        )
        char_tfidf = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=3,
            max_features=30_000,
            sublinear_tf=True,
        )
        features = FeatureUnion([("word", word_tfidf), ("char", char_tfidf)])

        clf = LogisticRegression(
            C=5.0,
            max_iter=1000,
            solver="lbfgs",
        )
        return Pipeline([("features", features), ("clf", clf)])

    def fit(self, texts: list[str], labels: list[str]) -> "MLClassifier":
        processed = [preprocess(t) for t in texts]
        self.le.fit(labels)
        y = self.le.transform(labels)
        self.classes_ = self.le.classes_

        self.pipeline = self._build_pipeline()
        self.pipeline.fit(processed, y)
        return self

    def predict_proba_raw(self, texts: list[str]) -> np.ndarray:
        processed = [preprocess(t) for t in texts]
        return self.pipeline.predict_proba(processed)

    def predict(self, texts: list[str]) -> pd.DataFrame:
        proba = self.predict_proba_raw(texts)
        idx = np.argmax(proba, axis=1)
        confs = proba[np.arange(len(texts)), idx]
        codes = self.le.inverse_transform(idx)

        return pd.DataFrame({
            "pred_code": codes,
            "pred_name": [self.code2name.get(c) for c in codes],
            "confidence": np.round(confs, 4),
            "needs_review": confs < self.THRESHOLD,
        })

    def save(self, path: str | Path):
        import pickle
        with open(path, "wb") as f:
            pickle.dump({"pipeline": self.pipeline, "le": self.le}, f)

    @classmethod
    def load(cls, path: str | Path) -> "MLClassifier":
        import pickle
        obj = cls()
        with open(path, "rb") as f:
            data = pickle.load(f)
        obj.pipeline = data["pipeline"]
        obj.le = data["le"]
        obj.classes_ = obj.le.classes_
        return obj


#готовим обучающую выборку: размечаем transactions.csv baseline'ом
def build_training_data(
    transactions_path: str | Path,
    categories: dict,
    min_confidence: float = 0.5,
    unambiguous_only: bool = True,
) -> pd.DataFrame:
    df = pd.read_csv(transactions_path)
    kw_clf = KeywordClassifier(categories)
    preds = kw_clf.predict(df["description"].tolist())

    df = df.copy()
    #коды строго строкой, иначе '01.11'/'19.20' ломаются через float
    df["category_code"] = preds["pred_code"].astype("string")
    df["confidence"] = preds["confidence"]

    df = df.dropna(subset=["category_code"])
    #берём только однозначные строки, чтобы ML не заучивал конфликты baseline'а
    if unambiguous_only:
        df = df[df["confidence"] >= 1.0]
    else:
        df = df[df["confidence"] >= min_confidence]

    return df[["description", "category_code"]].reset_index(drop=True)