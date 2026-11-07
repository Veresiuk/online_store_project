from online_store.config import Settings

NAMES = ("STORE_API_BASE_URL", "STORE_BATCH_TIMEOUT", "STORE_MAX_CONCURRENCY", "STORE_RETRY_ATTEMPTS")


def test_defaults(monkeypatch):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    s = Settings.from_env()
    assert (s.max_concurrency, s.retry_attempts, s.batch_timeout) == (5, 3, 10.0)


def test_settings_from_environment(monkeypatch):
    monkeypatch.setenv("STORE_MAX_CONCURRENCY", "2")
    monkeypatch.setenv("STORE_RETRY_ATTEMPTS", "4")
    monkeypatch.setenv("STORE_BATCH_TIMEOUT", "1.5")
    s = Settings.from_env()
    assert (s.max_concurrency, s.retry_attempts, s.batch_timeout) == (2, 4, 1.5)
