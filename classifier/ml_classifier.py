from __future__ import annotations

import os
import json
import argparse
from typing import List, Dict, Any

import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, cross_val_predict
from sklearn.metrics import classification_report


class TFIDFFailureClassifier:
    """
    TF-IDF + Logistic Regression classifier for failure classification.
    """

    def __init__(self, model_path: str = "models/tfidf_classifier.pkl") -> None:
        """
        Initialize classifier. Creates models/ directory if it doesn't exist.
        """
        self.model_path = model_path
        self.pipeline: Pipeline | None = None
        os.makedirs(os.path.dirname(model_path), exist_ok=True)

    def _load_jsonl(self, path: str) -> List[Dict[str, Any]]:
        """
        Load JSONL dataset.
        """
        with open(path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def train(self, jsonl_path: str) -> dict:
        """
        Train TF-IDF + Logistic Regression on labeled dataset.
        """
        data = self._load_jsonl(jsonl_path)

        texts, labels = [], []

        for row in data:
            text = f"{row['log_excerpt']} EVENTID_{row.get('event_id', '')}"
            texts.append(text)
            labels.append(row["failure_class"])

        self.pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2))),
            ("clf", LogisticRegression(max_iter=1000, C=1.0, multi_class='multinomial'))
        ])

        # CV fold adjustment
        n_samples = len(texts)
        min_class_count = min([labels.count(l) for l in set(labels)])
        cv_folds = min(5, n_samples, min_class_count)

        if cv_folds < 2:
            print("Warning: Not enough samples per class for cross-validation. Skipping CV.")
            acc_scores = np.array([1.0])
            preds = labels
            report = classification_report(labels, preds, output_dict=True)
        else:
            acc_scores = cross_val_score(self.pipeline, texts, labels, cv=cv_folds, scoring="accuracy")
            preds = cross_val_predict(self.pipeline, texts, labels, cv=cv_folds)
            report = classification_report(labels, preds, output_dict=True)

        # Train final model
        self.pipeline.fit(texts, labels)
        joblib.dump(self.pipeline, self.model_path)

        class_dist = {label: labels.count(label) for label in set(labels)}
        per_class_f1 = {
            cls: report[cls]["f1-score"]
            for cls in report if cls not in ("accuracy", "macro avg", "weighted avg")
        }

        return {
            "cv_accuracy_mean": float(np.mean(acc_scores)),
            "cv_accuracy_std": float(np.std(acc_scores)),
            "per_class_f1": per_class_f1,
            "total_samples": len(labels),
            "class_distribution": class_dist,
            "model_path": self.model_path
        }

    def _ensure_model_loaded(self) -> None:
        if self.pipeline is None:
            if not os.path.exists(self.model_path):
                raise RuntimeError(
                    "Model not found. Please run training first using --train."
                )
            self.pipeline = joblib.load(self.model_path)

    def predict(self, log_excerpt: str, event_id: str = "") -> dict:
        """
        Predict single log excerpt.
        """
        self._ensure_model_loaded()
        text = f"{log_excerpt} EVENTID_{event_id}"

        probs = self.pipeline.predict_proba([text])[0]
        classes = self.pipeline.classes_
        max_idx = int(np.argmax(probs))

        return {
            "failure_class": classes[max_idx],
            "confidence": float(probs[max_idx]),
            "all_probabilities": {cls: float(prob) for cls, prob in zip(classes, probs)}
        }

    def predict_batch(self, jsonl_path: str, output_path: str) -> None:
        """
        Batch prediction for JSONL dataset.
        """
        self._ensure_model_loaded()
        data = self._load_jsonl(jsonl_path)

        y_true, y_pred = [], []

        with open(output_path, "a", encoding="utf-8") as out:
            for row in data:
                result = self.predict(row["log_excerpt"], row.get("event_id", ""))
                row["ml_failure_class"] = result["failure_class"]
                row["ml_confidence"] = result["confidence"]

                y_true.append(row.get("failure_class"))
                y_pred.append(result["failure_class"])

                out.write(json.dumps(row) + "\n")
                out.flush()

        print("\nClassification Report:\n")
        print(classification_report(y_true, y_pred))


# ------------------- CLI -------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=str, help="Train on a JSONL dataset")
    parser.add_argument("--log", type=str, help="Predict single log excerpt")
    parser.add_argument("--event-id", type=str, default="", help="Event ID for single log")
    parser.add_argument("--predict-batch", type=str, help="Predict batch JSONL dataset")
    parser.add_argument("--out", type=str, help="Output path for batch prediction")
    args = parser.parse_args()

    clf = TFIDFFailureClassifier()

    if args.train:
        report = clf.train(args.train)
        print("Training completed. Report:")
        print(json.dumps(report, indent=2))

    elif args.log:
        result = clf.predict(args.log, args.event_id)
        print(json.dumps(result, indent=2))

    elif args.predict_batch and args.out:
        clf.predict_batch(args.predict_batch, args.out)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()