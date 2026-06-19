import importlib

import pytest

import src.config as config_module


def test_config_defaults(monkeypatch):
    monkeypatch.delenv("SCHEDULE_INTERVAL", raising=False)
    monkeypatch.delenv("CONTROL_TOKEN", raising=False)
    monkeypatch.delenv("LOKI_URL", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)

    module = importlib.reload(config_module)
    assert module.Config.SCHEDULE_INTERVAL == 10
    assert module.Config.CONTROL_TOKEN is None
    assert module.Config.LOKI_URL is None
    assert module.Config.LOG_LEVEL == "INFO"


def test_config_invalid_schedule_interval_raises(monkeypatch):
    monkeypatch.setenv("SCHEDULE_INTERVAL", "not-a-number")

    with pytest.raises(ValueError, match="positive integer"):
        importlib.reload(config_module)


@pytest.mark.parametrize("value", ["0", "-1"])
def test_config_non_positive_schedule_interval_raises(monkeypatch, value):
    monkeypatch.setenv("SCHEDULE_INTERVAL", value)

    with pytest.raises(ValueError, match="positive integer"):
        importlib.reload(config_module)
