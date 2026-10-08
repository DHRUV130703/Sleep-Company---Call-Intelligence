import shutil

import pytest
from pydantic import ValidationError

from app.config import CONFIG_DIR, IntentRubric, load_business_config


def test_shipped_config_files_are_valid():
    cfg = load_business_config()
    assert len(cfg.scorecard.dimensions) == 10
    assert cfg.intent.bucket_for(81) == "high"
    assert cfg.intent.bucket_for(50) == "moderate"
    assert cfg.intent.bucket_for(0) == "low"
    assert "price" in cfg.intent.objection_types


def _rubric(buckets):
    return {"buckets": buckets, "objection_types": ["price"], "ai_failure_patterns": ["dead_air"]}


def test_overlapping_buckets_are_rejected():
    with pytest.raises(ValidationError, match="overlaps"):
        IntentRubric.model_validate(_rubric({"high": [70, 100], "low": [0, 70]}))


def test_buckets_with_a_gap_are_rejected():
    with pytest.raises(ValidationError, match="cover every score"):
        IntentRubric.model_validate(_rubric({"high": [75, 100], "low": [0, 70]}))


def test_duplicate_scorecard_keys_are_rejected(tmp_path):
    shutil.copy(CONFIG_DIR / "intent_rubric.yaml", tmp_path)
    (tmp_path / "scorecard.yaml").write_text(
        "dimensions:\n  - {key: clarity, label: A}\n  - {key: clarity, label: B}\n"
    )
    with pytest.raises(ValidationError, match="unique"):
        load_business_config(tmp_path)


def test_ai_schema_keeps_fields_named_title():
    from app.contracts import CallAnalysis, json_schema_for

    schema = json_schema_for(CallAnalysis)
    objection = schema["properties"]["objections"]["items"]
    assert "title" in objection["properties"] and "title" in objection["required"]
    assert objection["properties"]["type"]["enum"][0] == "price"  # injected from config
    assert "default" not in str(schema)


def test_default_setup_is_fully_local(monkeypatch):
    from app.config import Settings

    monkeypatch.delenv("TRANSCRIBER", raising=False)
    monkeypatch.delenv("ANALYZER", raising=False)
    s = Settings()
    assert (s.transcriber, s.analyzer) == ("assemblyai", "groq")
