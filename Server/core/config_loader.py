
import ipaddress
import json
from pathlib import Path


class ConfigError(Exception):
    """Raised when the server configuration is invalid."""


def load_config(config_path: Path) -> dict:
    if not config_path.is_file():
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        with config_path.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"Invalid JSON in {config_path}: "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise ConfigError(
            f"Cannot read {config_path}: {exc}"
        ) from exc

    if not isinstance(config, dict):
        raise ConfigError("Configuration root must be a JSON object.")

    return config


def validate_global_config(config: dict) -> None:
    server = config.get("server")

    if not isinstance(server, dict):
        raise ConfigError("'server' must be an object.")

    host = server.get("host")

    if not isinstance(host, str) or not host:
        raise ConfigError("'server.host' must be a non-empty IPv4 address.")

    try:
        ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError as exc:
        raise ConfigError(
            f"Invalid IPv4 address in 'server.host': {host!r}"
        ) from exc

    # TCP port
    port = server.get("port")

    if isinstance(port, bool) or not isinstance(port, int):
        raise ConfigError("'server.port' must be an integer.")

    if not 1 <= port <= 65535:
        raise ConfigError("'server.port' must be between 1 and 65535.")

    # WebSocket port
    websocket_port = server.get("websocket_port")

    if isinstance(websocket_port, bool) or not isinstance(websocket_port, int):
        raise ConfigError("'server.websocket_port' must be an integer.")

    if not 1 <= websocket_port <= 65535:
        raise ConfigError(
            "'server.websocket_port' must be between 1 and 65535."
        )

    if port == websocket_port:
        raise ConfigError(
            "TCP and WebSocket ports must be different."
        )

    # Game configuration
    game = config.get("game")

    if not isinstance(game, dict):
        raise ConfigError("'game' must be an object.")

    mode = game.get("mode")

    if not isinstance(mode, str) or not mode.strip():
        raise ConfigError("'game.mode' must be a non-empty string.")
    start_requirements = game.get("start_requirements")

    if not isinstance(start_requirements, dict):
        raise ConfigError(
            "'game.start_requirements' must be an object."
        )

    for key in ("require_full_room", "require_all_ready"):
        if not isinstance(start_requirements.get(key), bool):
            raise ConfigError(
                f"'game.start_requirements.{key}' must be a boolean."
            )
