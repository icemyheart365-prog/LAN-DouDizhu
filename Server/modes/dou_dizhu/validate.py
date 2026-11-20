from typing import Any


class ModeConfigError(Exception):
    """Raised when game-specific configuration is invalid."""


def _require_integer(
    config: dict[str, Any],
    field: str,
    minimum: int
) -> int:
    value = config.get(field)

    if isinstance(value, bool) or not isinstance(value, int):
        raise ModeConfigError(
            f"'game.{field}' must be an integer."
        )

    if value < minimum:
        raise ModeConfigError(
            f"'game.{field}' must be at least {minimum}; got {value}."
        )

    return value


def validate(config: dict[str, Any], manifest: dict[str, Any]) -> None:
    game = config.get("game")

    if not isinstance(game, dict):
        raise ModeConfigError("'game' must be an object.")

    player_count = _require_integer(game, "player_count", 1)

    constraints = manifest["player_count"]
    minimum = constraints["minimum"]
    maximum = constraints["maximum"]

    if not minimum <= player_count <= maximum:
        raise ModeConfigError(
            f"'game.player_count' must be between "
            f"{minimum} and {maximum}; got {player_count}."
        )

    landlord_mode = game.get("landlord_mode")
    allowed_modes = manifest["landlord_modes"]

    if landlord_mode not in allowed_modes:
        raise ModeConfigError(
            f"Invalid 'game.landlord_mode': {landlord_mode!r}. "
            f"Allowed values: {allowed_modes}."
        )

    deck_count = _require_integer(game, "deck_count", 1)

    if deck_count != 1:
        raise ModeConfigError(
            f"'game.deck_count' must be 1; got {deck_count}."
        )

    if game.get("joker_enabled") is not True:
        raise ModeConfigError(
            "'game.joker_enabled' must be true for standard Dou Dizhu."
        )

    cards_per_player = _require_integer(
        game, "cards_per_player", 1
    )
    bottom_cards = _require_integer(
        game, "bottom_cards", 0
    )

    if cards_per_player != 17:
        raise ModeConfigError(
            f"'game.cards_per_player' must be 17; got {cards_per_player}."
        )

    if bottom_cards != 3:
        raise ModeConfigError(
            f"'game.bottom_cards' must be 3; got {bottom_cards}."
        )

    total_cards = cards_per_player * player_count + bottom_cards

    if total_cards != 54:
        raise ModeConfigError(
            f"Card distribution must use 54 cards; got {total_cards}."
        )
