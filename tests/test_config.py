"""Tests for configuration loading."""

import pytest

from bambuddy_mcp.config import Config


@pytest.fixture(autouse=True)
def clear_transport_env(monkeypatch):
    for name in (
        "BAMBUDDY_MCP_TRANSPORT",
        "BAMBUDDY_MCP_HOST",
        "BAMBUDDY_MCP_PORT",
        "BAMBUDDY_MCP_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


def test_config_from_env_defaults(monkeypatch):
    """Test default values when env vars not set."""
    monkeypatch.delenv("BAMBUDDY_URL", raising=False)
    monkeypatch.delenv("BAMBUDDY_API_KEY", raising=False)
    monkeypatch.delenv("BAMBUDDY_DIRECT_MODE", raising=False)
    monkeypatch.delenv("BAMBUDDY_CENSOR_ACCESS_CODE", raising=False)
    monkeypatch.delenv("BAMBUDDY_CENSOR_SERIAL", raising=False)
    monkeypatch.delenv("BAMBUDDY_CENSOR_MODEL_FILENAME", raising=False)

    config = Config.from_env()

    assert config.base_url == "http://localhost:8000"
    assert config.api_key == ""
    assert config.direct_mode is False
    assert config.censor_access_code is True
    assert config.censor_serial is True
    assert config.censor_model_filename is False
    assert config.transport == "stdio"
    assert config.host == "127.0.0.1"
    assert config.port == 8000


def test_config_from_env_custom(monkeypatch):
    """Test custom values from env vars."""
    monkeypatch.setenv("BAMBUDDY_URL", "http://custom:9000")
    monkeypatch.setenv("BAMBUDDY_API_KEY", "secret")
    monkeypatch.setenv("BAMBUDDY_DIRECT_MODE", "true")
    monkeypatch.setenv("BAMBUDDY_CENSOR_ACCESS_CODE", "false")
    monkeypatch.setenv("BAMBUDDY_CENSOR_SERIAL", "false")
    monkeypatch.setenv("BAMBUDDY_CENSOR_MODEL_FILENAME", "true")

    config = Config.from_env()

    assert config.base_url == "http://custom:9000"
    assert config.api_key == "secret"
    assert config.direct_mode is True
    assert config.censor_access_code is False
    assert config.censor_serial is False
    assert config.censor_model_filename is True


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("no", False),
        ("", False),
    ],
)
def test_direct_mode_parsing(monkeypatch, value, expected):
    """Test various truthy/falsy values for direct mode."""
    monkeypatch.setenv("BAMBUDDY_DIRECT_MODE", value)
    assert Config.from_env().direct_mode is expected


def test_http_configuration(monkeypatch):
    monkeypatch.setenv("BAMBUDDY_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("BAMBUDDY_MCP_TOKEN", "separate-mcp-secret")
    monkeypatch.setenv("BAMBUDDY_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("BAMBUDDY_MCP_PORT", "9000")
    config = Config.from_env()
    assert config.transport == "streamable-http"
    assert config.auth_token == "separate-mcp-secret"
    assert config.host == "0.0.0.0"
    assert config.port == 9000


def test_http_requires_token(monkeypatch):
    monkeypatch.setenv("BAMBUDDY_MCP_TRANSPORT", "streamable-http")
    with pytest.raises(ValueError, match="BAMBUDDY_MCP_TOKEN"):
        Config.from_env()


@pytest.mark.parametrize("port", ["0", "65536", "invalid"])
def test_invalid_port(monkeypatch, port):
    monkeypatch.setenv("BAMBUDDY_MCP_PORT", port)
    with pytest.raises(ValueError):
        Config.from_env()


def test_invalid_transport(monkeypatch):
    monkeypatch.setenv("BAMBUDDY_MCP_TRANSPORT", "invalid")
    with pytest.raises(ValueError, match="BAMBUDDY_MCP_TRANSPORT"):
        Config.from_env()
