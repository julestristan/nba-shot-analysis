"""Premier modèle : régression logistique vs gradient boosting, évalués sur la saison de validation.

Lancer depuis la racine du projet :  python -m baseline.train
"""
from pathlib import Path

import joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from baseline.preprocessing import CAT_FEATURES, NUM_FEATURES, TARGET, build, load, split

FEATURES = NUM_FEATURES + CAT_FEATURES
MODEL_PATH = Path("baseline/models/hgb.joblib")


def logistic():
    pre = ColumnTransformer([("num", StandardScaler(), NUM_FEATURES),
                             ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES)])
    return make_pipeline(pre, LogisticRegression(max_iter=2000))


def boosting():
    pre = ColumnTransformer([("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                              CAT_FEATURES),
                             ("num", "passthrough", NUM_FEATURES)])
    hgb = HistGradientBoostingClassifier(categorical_features=list(range(len(CAT_FEATURES))),
                                         random_state=42)
    return make_pipeline(pre, hgb)


def evaluate(name, y, p):
    print(f"{name:<22} AUC={roc_auc_score(y, p):.4f}  log-loss={log_loss(y, p):.4f}  "
          f"brier={brier_score_loss(y, p):.4f}")


def main():
    train, valid, test = split(build(load()))
    print(f"train {len(train):,} | validation {len(valid):,} | test (non utilisé) {len(test):,}\n")

    evaluate("Constante (FG% moyen)", valid[TARGET], [train[TARGET].mean()] * len(valid))
    for name, model in [("Logistique", logistic()), ("Gradient boosting", boosting())]:
        model.fit(train[FEATURES], train[TARGET])
        evaluate(name, valid[TARGET], model.predict_proba(valid[FEATURES])[:, 1])

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"\nModèle sauvegardé : {MODEL_PATH}")


if __name__ == "__main__":
    main()
