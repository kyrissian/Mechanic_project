"""Tests for the ProductionConfig database settings."""
import config


def test_production_engine_options_enable_pre_ping():
    """Production must verify connections before use.

    Neon suspends idle databases after about 5 minutes and drops the
    connections that were open. pool_pre_ping makes SQLAlchemy test each
    pooled connection first and replace a dead one, so the first request
    after an idle stretch doesn't fail.
    """
    assert config.ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS == {
        "pool_pre_ping": True
    }
