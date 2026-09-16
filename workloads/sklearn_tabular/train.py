"""Reference workload for Experiment.workload_type == "sklearn_tabular".

Contract expected by app.sandbox.runner.SandboxRunner:
  - Reads a CSV dataset from /workload/data.csv and hyperparameters from
    /workload/config.json (both mounted read-only).
  - Writes /output/metrics.json and /output/model.joblib (mounted
    read-write) - the only writable location in the sandboxed container.

NOT executed in the development session that authored this file - no
Docker daemon was available there. See docs/EXECUTION_SANDBOX.md.
"""

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

WORKLOAD_DIR = Path("/workload")
OUTPUT_DIR = Path("/output")


def main() -> None:
    config = json.loads((WORKLOAD_DIR / "config.json").read_text())
    data = pd.read_csv(WORKLOAD_DIR / "data.csv")

    target_column = config["target_column"]
    X = data.drop(columns=[target_column])
    y = data[target_column]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.get("test_size", 0.2), random_state=config.get("seed")
    )

    model = LogisticRegression(C=config.get("C", 1.0), random_state=config.get("seed"))
    model.fit(X_train, y_train)

    accuracy = accuracy_score(y_test, model.predict(X_test))

    joblib.dump(model, OUTPUT_DIR / "model.joblib")
    (OUTPUT_DIR / "metrics.json").write_text(json.dumps({"accuracy": accuracy}))


if __name__ == "__main__":
    main()
