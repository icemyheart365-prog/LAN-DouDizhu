
import random
from collections import Counter
from typing import Any


SUITS = ("♠", "♥", "♣", "♦")
RANKS = ("3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2")
VALUES = {rank: i + 3 for i, rank in enumerate(RANKS)}
VALUES.update({"小王": 16, "大王": 17})


class GameRuleError(ValueError):
    pass


class DouDiZhuGame:
    def __init__(self, config: dict[str, Any], player_ids: list[str]):
        if len(player_ids) != 3 or len(set(player_ids)) != 3:
            raise ValueError("Exactly three unique players are required.")

        self.config = config
        self.mode = config["game"].get("landlord_mode", "rob")
        self.player_ids = list(player_ids)

        self.hands = {}
        self.bottom_cards = []
        self.status = "bidding"

        self.landlord_id = None
        self.current_turn = None
        self.first_bidder = None

        self.bid_index = 0
        self.bid_order = []
        self.rob_history = []
        self.highest_bidder = None
        self.highest_bid = 0

        self.last_play = None
        self.last_non_pass_player = None
        self.pass_count = 0
        self.play_history = []

        self.winner = None
        self.winning_team = None
        self.end_reason = None

        # Reserved for a future doubling/betting phase.
        self.doubling_available = False
        self.multiplier = 1

        self.deal()

    @staticmethod
    def create_deck():
        return [
            f"{suit}{rank}"
            for suit in SUITS
            for rank in RANKS
        ] + ["小王", "大王"]

    @staticmethod
    def rank(card):
        if card in ("小王", "大王"):
            return VALUES[card]
        if len(card) < 2 or card[0] not in SUITS:
            raise GameRuleError(f"Invalid card: {card}")
        rank = card[1:]
        if rank not in VALUES:
            raise GameRuleError(f"Invalid card: {card}")
        return VALUES[rank]

    @classmethod
    def sort_key(cls, card):
        if card in ("小王", "大王"):
            return (cls.rank(card), 4)
        return (cls.rank(card), SUITS.index(card[0]))

    def deal(self):
        deck = self.create_deck()

        if len(deck) != 54 or len(set(deck)) != 54:
            raise RuntimeError("Invalid deck: expected 54 unique cards.")

        random.SystemRandom().shuffle(deck)

        self.hands = {
            player: sorted(deck[i * 17:(i + 1) * 17], key=self.sort_key)
            for i, player in enumerate(self.player_ids)
        }
        self.bottom_cards = deck[51:]

        all_cards = [
            card for hand in self.hands.values() for card in hand
        ] + self.bottom_cards

        if len(all_cards) != 54 or Counter(all_cards) != Counter(deck):
            raise RuntimeError("Deal integrity check failed.")

        self.first_bidder = random.choice(self.player_ids)
        start = self.player_ids.index(self.first_bidder)
        self.bid_order = self.player_ids[start:] + self.player_ids[:start]
        self.bid_index = 0
        self.rob_history = []
        self.highest_bidder = None
        self.highest_bid = 0
        self.landlord_id = None
        self.current_turn = None
        self.last_play = None
        self.last_non_pass_player = None
        self.pass_count = 0
        self.winner = None
        self.winning_team = None
        self.end_reason = None
        self.status = "bidding"

    def bid(self, player_id, choice):
        if self.status != "bidding":
            raise GameRuleError("Not in the bidding phase.")

        if self.bid_index >= 3:
            raise GameRuleError("Bidding has already finished.")

        expected = self.bid_order[self.bid_index]
        if player_id != expected:
            raise GameRuleError("It is not your turn to bid.")

        if self.mode == "rob":
            if not isinstance(choice, bool):
                raise GameRuleError("Rob choice must be true or false.")
            if choice:
                self.highest_bidder = player_id
                self.highest_bid = 1

        elif self.mode == "classic":
            if isinstance(choice, bool) or choice not in (0, 1, 2, 3):
                raise GameRuleError("Bid must be 0, 1, 2, or 3.")
            if choice and choice <= self.highest_bid:
                raise GameRuleError("Your bid must exceed the current bid.")
            if choice:
                self.highest_bid = choice
                self.highest_bidder = player_id
        else:
            raise GameRuleError("Unsupported landlord mode.")

        self.rob_history.append({
            "player_id": player_id,
            "choice": choice,
        })
        self.bid_index += 1

        finished = self.bid_index == 3

        if self.mode == "classic" and self.highest_bid == 3:
            finished = True

        if finished:
            if self.highest_bidder is None:
                self.status = "redeal"
                return {"type": "redeal_required"}

            self.set_landlord(self.highest_bidder)
            return {"type": "landlord_selected"}

        return {"type": "bid_accepted"}

    def set_landlord(self, player_id):
        self.landlord_id = player_id
        self.hands[player_id] = sorted(
            self.hands[player_id] + self.bottom_cards,
            key=self.sort_key,
        )
        self.current_turn = player_id
        self.status = "playing"

    @classmethod
    def classify(cls, cards):
        if not isinstance(cards, list) or not cards:
            return None
        if len(cards) != len(set(cards)):
            return None

        try:
            values = sorted(cls.rank(card) for card in cards)
        except (GameRuleError, TypeError):
            return None

        counts = Counter(values)
        groups = sorted(counts.values(), reverse=True)
        unique = sorted(counts)
        n = len(cards)

        def result(kind, main, length=n):
            return {"kind": kind, "main": main, "length": length}

        if n == 1:
            return result("single", values[0])

        if n == 2 and values == [16, 17]:
            return result("rocket", 17)

        if groups == [2] and n == 2:
            return result("pair", unique[0])

        if groups == [3] and n == 3:
            return result("triple", unique[0])

        if groups == [4] and n == 4:
            return result("bomb", unique[0])

        if groups == [3, 1] and n == 4:
            return result("triple_single", max(v for v, c in counts.items() if c == 3))

        if groups == [3, 2] and n == 5:
            return result("triple_pair", max(v for v, c in counts.items() if c == 3))

        # Straight: at least five consecutive ranks; 2 and jokers excluded.
        if n >= 5 and len(unique) == n and max(unique) <= 14:
            if max(unique) - min(unique) == n - 1:
                return result("straight", max(unique))

        # Consecutive pairs.
        if n >= 6 and n % 2 == 0 and groups == [2] * (n // 2):
            if max(unique) <= 14 and len(unique) >= 3:
                if max(unique) - min(unique) == len(unique) - 1:
                    return result("pair_straight", max(unique))

        # Consecutive triples (airplane without wings).
        if n >= 6 and n % 3 == 0 and groups == [3] * (n // 3):
            if max(unique) <= 14 and len(unique) >= 2:
                if max(unique) - min(unique) == len(unique) - 1:
                    return result("airplane", max(unique))

        # Four with two single cards.
        if n == 6 and groups == [4, 1, 1]:
            return result("four_two_single", max(v for v, c in counts.items() if c == 4))

        # Four with two pairs.
        if n == 8 and groups == [4, 2, 2]:
            return result("four_two_pair", max(v for v, c in counts.items() if c == 4))

        return None

    @staticmethod
    def beats(candidate, previous):
        if candidate["kind"] == "rocket":
            return previous["kind"] != "rocket"

        if previous["kind"] == "rocket":
            return False

        if candidate["kind"] == "bomb" and previous["kind"] != "bomb":
            return True

        if previous["kind"] == "bomb" and candidate["kind"] != "bomb":
            return False

        return (
            candidate["kind"] == previous["kind"]
            and candidate["length"] == previous["length"]
            and candidate["main"] > previous["main"]
        )

    def play(self, player_id, cards):
        if self.status != "playing":
            raise GameRuleError("Game is not in the playing phase.")

        if player_id != self.current_turn:
            raise GameRuleError("It is not your turn.")

        if not isinstance(cards, list) or not cards:
            raise GameRuleError("Select cards to play.")

        hand = self.hands[player_id]

        if len(cards) != len(set(cards)):
            raise GameRuleError("Duplicate selected cards.")

        if any(card not in hand for card in cards):
            raise GameRuleError("You do not own all selected cards.")

        combo = self.classify(cards)
        if combo is None:
            raise GameRuleError("Invalid card combination.")

        if self.last_play is not None and self.last_non_pass_player != player_id:
            if not self.beats(combo, self.last_play["combo"]):
                raise GameRuleError("Your cards do not beat the previous play.")

        for card in cards:
            hand.remove(card)

        self.last_play = {
            "player_id": player_id,
            "cards": list(cards),
            "combo": combo,
        }
        self.last_non_pass_player = player_id
        self.pass_count = 0
        self.play_history.append(self.last_play)

        if not hand:
            self.status = "finished"
            self.winner = player_id
            self.winning_team = (
                "landlord" if player_id == self.landlord_id else "farmers"
            )
            return {"type": "game_over"}

        self.current_turn = self.next_player(player_id)
        return {"type": "played"}

    def pass_turn(self, player_id):
        if self.status != "playing":
            raise GameRuleError("Game is not in the playing phase.")

        if player_id != self.current_turn:
            raise GameRuleError("It is not your turn.")

        if self.last_play is None or self.last_non_pass_player == player_id:
            raise GameRuleError("You cannot pass when leading.")

        self.pass_count += 1

        if self.pass_count == 2:
            self.current_turn = self.last_non_pass_player
            self.last_play = None
            self.last_non_pass_player = None
            self.pass_count = 0
            return {"type": "trick_cleared"}

        self.current_turn = self.next_player(player_id)
        return {"type": "passed"}

    def next_player(self, player_id):
        index = self.player_ids.index(player_id)
        return self.player_ids[(index + 1) % 3]

    def force_end(self):
        """Terminate an active game without declaring a winner."""
        if self.status not in ("bidding", "playing"):
            raise GameRuleError(
                "The game can only be force-ended during an active game."
            )

        self.status = "finished"
        self.winner = None
        self.winning_team = None
        self.end_reason = "host_terminated"

        return {
            "type": "game_terminated",
            "reason": self.end_reason,
        }

    def player_view(self, player_id):
        if player_id not in self.hands:
            raise ValueError("Unknown player.")

        return {
            "self": {
                "id": player_id,
                "cards": list(self.hands[player_id]),
            },
            "players": [
                {
                    "id": pid,
                    "card_count": len(self.hands[pid]),
                    "is_landlord": pid == self.landlord_id,
                }
                for pid in self.player_ids
            ],
            "status": self.status,
            "landlord_id": self.landlord_id,
            "current_turn": self.current_turn,
            "first_bidder": self.first_bidder,
            "bid_order": list(self.bid_order),
            "bid_index": self.bid_index,
            "highest_bid": self.highest_bid,
            "highest_bidder": self.highest_bidder,
            "bottom_cards": (
                list(self.bottom_cards)
                if player_id == self.landlord_id else []
            ),
            "last_play": self.last_play,
            "last_non_pass_player": self.last_non_pass_player,
            "pass_count": self.pass_count,
            "winner": self.winner,
            "winning_team": self.winning_team,
            "end_reason": self.end_reason,
            "multiplier": self.multiplier,
            "doubling_available": self.doubling_available,
        }
