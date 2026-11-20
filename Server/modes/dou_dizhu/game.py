
import random
from typing import Any


SUITS = ("♠", "♥", "♣", "♦")
RANKS = (
    "3", "4", "5", "6", "7", "8", "9",
    "10", "J", "Q", "K", "A", "2"
)


class DouDiZhuGame:
    """Server-side Dou Dizhu game state."""

    def __init__(self, config: dict[str, Any], player_ids: list[str]):
        game_config = config["game"]

        expected_players = game_config["player_count"]
        if len(player_ids) != expected_players:
            raise ValueError(
                f"Expected {expected_players} players, got {len(player_ids)}."
            )

        self.player_ids = list(player_ids)
        self.hands: dict[str, list[str]] = {}
        self.bottom_cards: list[str] = []
        self.landlord_id: str | None = None
        self.current_turn: str | None = None
        self.status = "waiting"

        self._deal(game_config)

    @staticmethod
    def create_deck(game_config: dict[str, Any]) -> list[str]:
        deck = [
            f"{suit}{rank}"
            for suit in SUITS
            for rank in RANKS
        ]

        if game_config["joker_enabled"]:
            deck.extend(("小王", "大王"))

        return deck * game_config["deck_count"]

    def _deal(self, game_config: dict[str, Any]) -> None:
        deck = self.create_deck(game_config)
        random.shuffle(deck)

        cards_per_player = game_config["cards_per_player"]
        bottom_count = game_config["bottom_cards"]

        self.hands = {
            player_id: deck[
                index * cards_per_player:
                (index + 1) * cards_per_player
            ]
            for index, player_id in enumerate(self.player_ids)
        }

        self.bottom_cards = deck[
            cards_per_player * len(self.player_ids):
            cards_per_player * len(self.player_ids) + bottom_count
        ]

        self.status = "dealt"

    def player_view(self, player_id: str) -> dict[str, Any]:
        """Return only this player's private hand and public information."""
        if player_id not in self.hands:
            raise ValueError("Unknown player.")

        return {
            "self": {
                "id": player_id,
                "cards": list(self.hands[player_id]),
            },
            "opponents": [
                {
                    "id": opponent_id,
                    "card_count": len(self.hands[opponent_id]),
                }
                for opponent_id in self.player_ids
                if opponent_id != player_id
            ],
            "status": self.status,
        }
