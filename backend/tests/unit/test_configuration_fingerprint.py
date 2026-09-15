from app.provenance.configuration import capture_configuration_provenance


def test_key_order_permutation_hashes_identically():
    a = capture_configuration_provenance({"learning_rate": 0.001, "batch_size": 64, "model": "logreg"})
    b = capture_configuration_provenance({"model": "logreg", "batch_size": 64, "learning_rate": 0.001})
    assert a.configuration_fingerprint_hash == b.configuration_fingerprint_hash


def test_value_change_produces_different_hash():
    a = capture_configuration_provenance({"learning_rate": 0.001})
    b = capture_configuration_provenance({"learning_rate": 0.01})
    assert a.configuration_fingerprint_hash != b.configuration_fingerprint_hash


def test_nested_config_key_order_invariance():
    a = capture_configuration_provenance({"model": {"type": "rf", "params": {"n_estimators": 100, "max_depth": 5}}})
    b = capture_configuration_provenance({"model": {"params": {"max_depth": 5, "n_estimators": 100}, "type": "rf"}})
    assert a.configuration_fingerprint_hash == b.configuration_fingerprint_hash


def test_raw_config_preserved_verbatim():
    raw = {"z": 1, "a": 2}
    result = capture_configuration_provenance(raw)
    assert result.raw == raw
