
import asyncio
import json
import sys
import uuid
from pathlib import Path

from websockets.asyncio.server import serve

from core.config_loader import load_config, validate_global_config
from core.mode_loader import load_mode

BASE_DIR = Path(__file__).resolve().parent


class WebRoom:
    def __init__(self, config):
        self.config = config
        self.max_players = config["game"]["player_count"]
        self.players = {}
        self.game = None
        self.lock = asyncio.Lock()

    async def send(self, client, message):
        await client.send(json.dumps(message, ensure_ascii=False))

    async def broadcast_lobby(self):
        message = {
            "type": "lobby",
            "players": [
                {
                    "id": player["id"],
                    "nickname": player["nickname"],
                    "ready": player["ready"],
                }
                for player in self.players.values()
            ],
            "required_players": self.max_players,
        }

        await asyncio.gather(
            *(self.send(client, message) for client in list(self.players)),
            return_exceptions=True,
        )

    async def handle(self, client, message):
        if not isinstance(message, dict):
            await self.send(client, {
                "type": "error",
                "message": "Expected a JSON object.",
            })
            return

        action = message.get("type")

        async with self.lock:
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
                    p["nickname"] == nickname
                    for p in self.players.values()
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

                await self.send(client, {
                    "type": "joined",
                    "nickname": nickname,
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

            if action == "ready":
                if self.game is not None:
                    await self.send(client, {
                        "type": "error",
                        "message": "Game already started.",
                    })
                    return

                self.players[client]["ready"] = message.get("ready") is True
                await self.broadcast_lobby()

                if (
                    len(self.players) == self.max_players
                    and all(p["ready"] for p in self.players.values())
                ):
                    from modes.dou_dizhu.game import DouDiZhuGame

                    player_ids = [
                        p["id"] for p in self.players.values()
                    ]
                    self.game = DouDiZhuGame(self.config, player_ids)

                    for connection, player in self.players.items():
                        await self.send(connection, {
                            "type": "game_started",
                            "state": self.game.player_view(player["id"]),
                        })

    async def disconnect(self, client):
        async with self.lock:
            player = self.players.pop(client, None)

            if player is not None:
                print(f"[ROOM] {player['nickname']} disconnected.")
                self.game = None

                for remaining in self.players.values():
                    remaining["ready"] = False

                await self.broadcast_lobby()


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
