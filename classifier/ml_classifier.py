# ml_classifier.py
import argparse
import json
import os
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

# -----------------------------
# Classifier
# -----------------------------
class MLClassifier:
    def __init__(self):
        self.pipeline = None
        self.vectorizer = TfidfVectorizer()
        self.model = LogisticRegression(max_iter=500)
        self.history = {"train_accuracy": [], "val_accuracy": [], "test_accuracy": []}

    # Train the model
    def train(self, train_file):
        # Load data
        logs, labels = [], []
        with open(train_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                obj = json.loads(line)
                logs.append(obj['log_excerpt'])
                labels.append(obj['failure_class'])

        # Split into train/val/test
        X_train, X_temp, y_train, y_temp = train_test_split(logs, labels, test_size=0.4, random_state=42, stratify=labels)
        X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp)

        # Vectorize
        X_train_vec = self.vectorizer.fit_transform(X_train)
        X_val_vec = self.vectorizer.transform(X_val)
        X_test_vec = self.vectorizer.transform(X_test)

        # Train
        self.model.fit(X_train_vec, y_train)

        # Save pipeline
        self.pipeline = (self.vectorizer, self.model)

        # Evaluate
        train_acc = accuracy_score(y_train, self.model.predict(X_train_vec))
        val_acc = accuracy_score(y_val, self.model.predict(X_val_vec))
        test_acc = accuracy_score(y_test, self.model.predict(X_test_vec))

        self.history["train_accuracy"].append(train_acc)
        self.history["val_accuracy"].append(val_acc)
        self.history["test_accuracy"].append(test_acc)

        # Metrics
        y_pred = self.model.predict(X_test_vec)
        metrics = {
            "validation_accuracy": val_acc,
            "test_accuracy": test_acc,
            "classification_report": classification_report(y_test, y_pred, output_dict=True, zero_division=0),
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist()
        }

        # Save results folder
        os.makedirs("results", exist_ok=True)
        with open("results/metrics.json", "w") as f:
            json.dump(metrics, f, indent=4)

        # Plot accuracies
        self.plot_accuracy(train_acc, val_acc, test_acc)

        # Plot confusion matrix
        self.plot_confusion_matrix(metrics["confusion_matrix"], labels=list(set(labels)))

        print("Training completed. Metrics saved in 'results/metrics.json'.")
        print("Accuracy plot and confusion matrix saved in 'results/' folder.")

    # Predict a single log
    def predict_log(self, log_text):
        if not self.pipeline:
            raise Exception("Model not trained yet.")
        vectorizer, model = self.pipeline
        vec = vectorizer.transform([log_text])
        return model.predict(vec)[0]

    # Plot accuracy bar chart
    def plot_accuracy(self, train_acc, val_acc, test_acc):
        plt.figure(figsize=(8,6))
        plt.bar(['Train', 'Validation', 'Test'], [train_acc, val_acc, test_acc], color=['blue', 'orange', 'green'])
        plt.ylim(0, 1)
        plt.ylabel("Accuracy")
        plt.title("Accuracy after training")
        plt.savefig("results/accuracy_plot.png")
        plt.close()

    # Plot confusion matrix heatmap
    def plot_confusion_matrix(self, cm, labels):
        plt.figure(figsize=(8,6))
        sns.heatmap(np.array(cm), annot=True, fmt='d', xticklabels=labels, yticklabels=labels, cmap="Blues")
        plt.xlabel("Predicted")
        plt.ylabel("Actual")
        plt.title("Confusion Matrix")
        plt.savefig("results/confusion_matrix.png")
        plt.close()

# -----------------------------
# Main function
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="Train or predict failure logs")
    parser.add_argument("--train", help="Path to training JSONL file")
    parser.add_argument("--log", help="Single log string to predict")
    args = parser.parse_args()

    clf = MLClassifier()

    if args.train:
        clf.train(args.train)

    if args.log:
        try:
            prediction = clf.predict_log(args.log)
            print(f"Predicted failure class: {prediction}")
        except Exception as e:
            print("Error:", str(e))

# -----------------------------
if __name__ == "__main__":
    main()