import runpy
from pathlib import Path

import numpy as np
from sklearn.neural_network import MLPRegressor
from test_source_family_cohort import inputs

from pubburi_recommendation.source_family_cohort import CohortExperiment, load_cohort

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/evaluate_neural_cohort.py"


def test_encoder_uses_fitted_width_and_keeps_unsupported_rows_zero():
    script = runpy.run_path(str(SCRIPT))
    train = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    model = MLPRegressor(**(script["MODEL_SETTINGS"] | {"hidden_layer_sizes": (8, 4, 8)})).fit(
        train, train
    )
    transformed = script["encode"](model, np.array([[0.0, 0.0], [1.0, 0.0]]))
    assert transformed.shape == (2, 4)
    assert np.all(transformed[0] == 0)
    assert np.isfinite(transformed).all()
    assert model.predict(train).shape == train.shape


def test_heldout_facts_cannot_train_network_or_make_oov_evidence(tmp_path):
    spec, manifest, snapshots = inputs(tmp_path)
    _, authorities = load_cohort(spec, manifest, snapshots)
    evaluate = runpy.run_path(str(SCRIPT))["evaluate"]

    observed = evaluate(spec, authorities)
    assert observed["fit_shape"] == [2, 3]
    assert observed["latent_shape"] == [2, 2]
    assert observed["iterations"] > 0
    assert observed["heldout"]["zero_tfidf_rows"] == 0
    assert observed["tfidf_retrieval"]["positive_label_queries"] == 1

    # A completely unseen class changes the held-out judgment, not the fitted weights.
    unsupported_data = spec.model_dump()
    unsupported_data["expected_facts"]["Q3"]["instance_of_ids"] = ["Q999"]
    unsupported_data["retrieval_cases"][0]["relevant_ids"] = []
    unsupported = evaluate(CohortExperiment.model_validate(unsupported_data), authorities)

    assert unsupported["fit_fingerprint"] == observed["fit_fingerprint"]
    assert unsupported["heldout"] == {
        "total_rows": 1,
        "zero_tfidf_rows": 1,
        "zero_neural_rows": 1,
    }
    assert unsupported["reconstruction"]["heldout_supported_rmse"] is None
    rows = unsupported["neural_retrieval"]["cases"][0]["representation_cosine"]
    assert rows == [
        {"source_record_id": "Q1", "score": 0.0},
        {"source_record_id": "Q2", "score": 0.0},
    ]
