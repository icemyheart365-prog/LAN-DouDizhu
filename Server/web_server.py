import asyncio
import json
import sys
import uuid
from pathlib import Path

from websockets.asyncio.server import serve

from core.config_loader import load_config, validate_global_config
from core.mode_loader import load_mode
from modes.dou_dizhu.game import DouDiZhuGame, GameRuleError

BASE_DIR = Path(__file__).resolve().parent


class WebRoom:
    def __init__(self, config):
        self.config = config
        self.max_players = config["game"]["player_count"]
        self.players = {}
        self.host_id = None
        self.game = None
        self.lock = asyncio.Lock()
        self.closed = False

    async def send(self, client, message):
        await client.send(json.dumps(message, ensure_ascii=False))

    async def broadcast_lobby(self, notice=None):
        if self.closed:
            return

        message = {
            "type": "lobby",
            "host_id": self.host_id,
            "players": [
                {
                    "id": player["id"],
                    "nickname": player["nickname"],
                    "ready": player["ready"],
                    "is_host": player["id"] == self.host_id,
                }
                for player in self.players.values()
            ],
            "required_players": self.max_players,
            "start_requirements": self.config["game"]["start_requirements"],
        }

        if notice:
            message["notice"] = notice

        await asyncio.gather(
            *(
                self.send(client, message)
                for client in list(self.players)
            ),
            return_exceptions=True,
        )

    async def broadcast_game(self, event=None):
        if self.game is None or self.closed:
            return

        for connection, player in list(self.players.items()):
            try:
                state = self.game.player_view(player["id"])
                state["host_id"] = self.host_id

                await self.send(connection, {
                    "type": "game_state",
                    "event": event,
                    "is_host": player["id"] == self.host_id,
                    "state": state,
                })
            except Exception as exc:
                print(f"[WS] Failed to update player: {exc}")

    async def send_event(self, event, params=None):
        if self.closed:
            return

        await asyncio.gather(
            *(
                self.send(client, {
                    "type": "game_notice",
                    "event": event,
                    "params": params or {},
                })
                for client in list(self.players)
            ),
            return_exceptions=True,
        )

    def reset_to_lobby(self):
        """Clear the current game and require every remaining player to ready up."""
        self.game = None

        for player in self.players.values():
            player["ready"] = False

    async def start_game(self):
        if self.closed:
            return

        player_ids = [
            player["id"] for player in self.players.values()
        ]
        self.game = DouDiZhuGame(self.config, player_ids)

        await self.broadcast_game("game_started")
        print("[GAME] New game dealt. 54-card integrity verified.")

    async def handle_bid(self, player_id, message):
        choice = message.get("choice")

        try:
            result = self.game.bid(player_id, choice)
        except GameRuleError as exc:
            return {"type": "error", "message": str(exc)}

        if result["type"] == "redeal_required":
            await self.send_event("no_landlord")
            await self.start_game()
            return None

        if result["type"] == "landlord_selected":
            await self.send_event("landlord_selected")
            await self.broadcast_game("landlord_selected")
            return None

        await self.broadcast_game("bid_accepted")
        return None

    async def handle_play(self, player_id, message):
        cards = message.get("cards")

        try:
            result = self.game.play(player_id, cards)
        except GameRuleError as exc:
            return {"type": "error", "message": str(exc)}

        if result["type"] == "game_over":
            winning_team = self.game.winning_team
            await self.broadcast_game("game_over")
            await self.send_event(
                "game_over",
                {"team": winning_team}
            )

            self.reset_to_lobby()
            await self.broadcast_lobby({
                "event": "round_finished"
            })
            return None

        await self.broadcast_game("played")
        return None

    async def handle_pass(self, player_id):
        try:
            result = self.game.pass_turn(player_id)
        except GameRuleError as exc:
            return {"type": "error", "message": str(exc)}

        await self.broadcast_game(result["type"])
        return None

    async def handle(self, client, message):
        if not isinstance(message, dict):
            await self.send(client, {
                "type": "error",
                "message": "Expected a JSON object.",
            })
            return

        action = message.get("type")

        async with self.lock:
            if self.closed:
                if action == "join":
                    # Reopen the room for a new session.
                    self.closed = False
                    self.host_id = None
                    self.game = None
                    self.players.clear()

                    print("[ROOM] Closed room reopened.")

                else:
                    await self.send(client, {
                        "type": "error",
                        "message": "This room has been closed.",
                    })
                    return

            if action == "join":
                if client in self.players:
                    await self.send(client, {
                        "type": "error",
                        "message": "Already joined.",
                    })
                    return

                if self.game is not None:
                    await self.send(client, {
                        "type": "error",
                        "message": "Game already started.",
                    })
                    return

                if len(self.players) >= self.max_players:
                    await self.send(client, {
                        "type": "error",
                        "message": "Room is full.",
                    })
                    return

                nickname = message.get("nickname")
                if (
                    not isinstance(nickname, str)
                    or not nickname.strip()
                    or len(nickname.strip()) > 20
                ):
                    await self.send(client, {
                        "type": "error",
                        "message": "Nickname must be 1-20 characters.",
                    })
                    return

                nickname = nickname.strip()
                if any(
                    player["nickname"] == nickname
                    for player in self.players.values()
                ):
                    await self.send(client, {
                        "type": "error",
                        "message": "Nickname already taken.",
                    })
                    return

                self.players[client] = {
                    "id": uuid.uuid4().hex,
                    "nickname": nickname,
                    "ready": False,
                }

                if self.host_id is None:
                    self.host_id = self.players[client]["id"]

                await self.send(client, {
                    "type": "joined",
                    "nickname": nickname,
                    "player_id": self.players[client]["id"],
                })
                await self.broadcast_lobby()
                return

            if action == "ping":
                await self.send(client, {"type": "pong"})
                return

            if client not in self.players:
                await self.send(client, {
                    "type": "error",
                    "message": "Join the room first.",
                })
                return

            player_id = self.players[client]["id"]

            if action == "ready":
                if self.game is not None:
                    await self.send(client, {
                        "type": "error",
                        "message": "Game already started.",
                    })
                    return

                self.players[client]["ready"] = message.get("ready") is True
                await self.broadcast_lobby()
                return

            if action == "start_game":
                if player_id != self.host_id:
                    await self.send(client, {
                        "type": "error",
                        "message": "Only the room host can start the game.",
                    })
                    return

                if self.game is not None:
                    await self.send(client, {
                        "type": "error",
                        "message": "Game already started.",
                    })
                    return

                requirements = self.config["game"]["start_requirements"]

                if (
                    requirements["require_full_room"]
                    and len(self.players) != self.max_players
                ):
                    await self.send(client, {
                        "type": "error",
                        "message": "The room is not full.",
                    })
                    return

                if (
                    requirements["require_all_ready"]
                    and not all(
                        player["ready"]
                        for player in self.players.values()
                    )
                ):
                    await self.send(client, {
                        "type": "error",
                        "message": "Not all players are ready.",
                    })
                    return

                await self.start_game()
                return

            if action == "force_end":
                if player_id != self.host_id:
                    await self.send(client, {
                        "type": "error",
                        "message": "Only the room host can force-end the game.",
                    })
                    return

                if self.game is None:
                    await self.send(client, {
                        "type": "error",
                        "message": "The game has not started.",
                    })
                    return

                try:
                    result = self.game.force_end()
                except GameRuleError as exc:
                    await self.send(client, {
                        "type": "error",
                        "message": str(exc),
                    })
                    return

                await self.broadcast_game(result["type"])
                await self.send_event("host_force_ended")

                self.reset_to_lobby()
                await self.broadcast_lobby({
                    "event": "host_terminated"
                })
                return

            if self.game is None:
                await self.send(client, {
                    "type": "error",
                    "message": "The game has not started.",
                })
                return

            if action == "bid":
                error = await self.handle_bid(player_id, message)
            elif action == "play":
                error = await self.handle_play(player_id, message)
            elif action == "pass":
                error = await self.handle_pass(player_id)
            else:
                error = {
                    "type": "error",
                    "message": f"Unknown action: {action}",
                }

            if error is not None:
                await self.send(client, error)

    async def disconnect(self, client):
        clients_to_close = []
        room_was_closed = False

        async with self.lock:
            player = self.players.pop(client, None)

            # Ignore duplicate disconnect callbacks and unjoined connections.
            if player is None:
                return

            print(f"[ROOM] {player['nickname']} disconnected.")

            if player["id"] == self.host_id:
                # The host is permanent. Never transfer ownership.
                self.closed = True
                self.game = None
                clients_to_close = list(self.players)
                self.players.clear()
                room_was_closed = True
                print("[ROOM] Host disconnected. Room closed.")

            else:
                # A regular player's departure invalidates the current game.
                self.reset_to_lobby()
                await self.broadcast_lobby({
                    "event": "player_left",
                    "params": {
                        "nickname": player["nickname"]
                    }
                })

        # Notify and close other sockets only after releasing the room lock.
        if room_was_closed:
            await asyncio.gather(
                *(
                    self.send(client_to_close, {
                        "type": "room_closed",
                        "message": "房主已离开，房间已关闭。",
                    })
                    for client_to_close in clients_to_close
                ),
                return_exceptions=True,
            )

            await asyncio.gather(
                *(
                    client_to_close.close(
                        code=1001,
                        reason="Room host disconnected",
                    )
                    for client_to_close in clients_to_close
                ),
                return_exceptions=True,
            )


async def main():
    config = load_config(BASE_DIR / "config.json")
    validate_global_config(config)

    mode = load_mode(BASE_DIR / "modes", config["game"]["mode"])
    mode["validator"].validate(config, mode["manifest"])

    room = WebRoom(config)
    host = config["server"]["host"]
    port = config["server"]["websocket_port"]

    async def handler(connection):
        print(f"[WS] Connected: {connection.remote_address}")
        try:
            await room.send(connection, {
                "type": "server_hello",
                "protocol": "websocket-json",
                "mode": config["game"]["mode"],
                "landlord_mode": config["game"].get("landlord_mode", "rob"),
                "player_count": config["game"]["player_count"],
            })

            async for raw_message in connection:
                try:
                    message = json.loads(raw_message)
                    await room.handle(connection, message)
                except json.JSONDecodeError:
                    await room.send(connection, {
                        "type": "error",
                        "message": "Invalid JSON.",
                    })

        finally:
            await room.disconnect(connection)
            print(f"[WS] Disconnected: {connection.remote_address}")

    print(f"[WS] LAN-DouDizhu WebSocket server: {host}:{port}")

    async with serve(handler, host, port):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[WS] Server stopped.")
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        sys.exit(1)
