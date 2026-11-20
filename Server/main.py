import os
import asyncio
import json
import sys
import uuid
from pathlib import Path

from core.config_loader import ConfigError, load_config, validate_global_config
from core.mode_loader import ModeLoadError, load_mode

BASE_DIR = Path(__file__).resolve().parent


class Room:
    def __init__(self, config):
        self.config = config
        self.max_players = config["game"]["player_count"]
        self.players = {}
        self.game = None
        self.lock = asyncio.Lock()

    async def send(self, writer, message):
        writer.write(
            (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
        )
        await writer.drain()

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

        for writer in list(self.players):
            try:
                await self.send(writer, message)
            except (ConnectionError, OSError):
                pass

    async def handle_message(self, writer, message):
        if not isinstance(message, dict):
            await self.send(writer, {"type": "error", "message": "Expected JSON object."})
            return

        action = message.get("type")

        async with self.lock:
            if action == "join":
                if writer in self.players:
                    await self.send(writer, {"type": "error", "message": "Already joined."})
                    return

                if self.game is not None:
                    await self.send(writer, {"type": "error", "message": "Game already started."})
                    return

                if len(self.players) >= self.max_players:
                    await self.send(writer, {"type": "error", "message": "Room is full."})
                    return

                nickname = message.get("nickname")
                if not isinstance(nickname, str) or not nickname.strip() or len(nickname.strip()) > 20:
                    await self.send(writer, {"type": "error", "message": "Nickname must be 1-20 characters."})
                    return

                nickname = nickname.strip()
                if any(p["nickname"] == nickname for p in self.players.values()):
                    await self.send(writer, {"type": "error", "message": "Nickname already taken."})
                    return

                self.players[writer] = {
                    "id": uuid.uuid4().hex,
                    "nickname": nickname,
                    "ready": False,
                }
                await self.send(writer, {"type": "joined", "nickname": nickname})
                await self.broadcast_lobby()
                return

            if writer not in self.players:
                await self.send(writer, {"type": "error", "message": "Join the room first."})
                return

            if action == "ready":
                if self.game is not None:
                    await self.send(writer, {"type": "error", "message": "Game already started."})
                    return

                self.players[writer]["ready"] = message.get("ready") is True
                await self.broadcast_lobby()

                if (
                    len(self.players) == self.max_players
                    and all(p["ready"] for p in self.players.values())
                ):
                    from modes.dou_dizhu.game import DouDiZhuGame

                    player_ids = [p["id"] for p in self.players.values()]
                    self.game = DouDiZhuGame(self.config, player_ids)

                    for client, player in self.players.items():
                        await self.send(client, {
                            "type": "game_started",
                            "state": self.game.player_view(player["id"]),
                        })
                return

            if action == "ping":
                await self.send(writer, {"type": "pong"})
                return

            await self.send(writer, {"type": "error", "message": "Unknown message type."})

    async def disconnect(self, writer):
        async with self.lock:
            player = self.players.pop(writer, None)
            if player is not None:
                print(f"[ROOM] {player['nickname']} disconnected.")
                self.game = None
                for remaining in self.players.values():
                    remaining["ready"] = False
                await self.broadcast_lobby()


async def handle_client(reader, writer, room):
    peer = writer.get_extra_info("peername")
    print(f"[NETWORK] Connected: {peer}")

    try:
        await room.send(writer, {
            "type": "server_hello",
            "protocol": "jsonl",
            "mode": room.config["game"]["mode"],
        })

        while line := await reader.readline():
            try:
                message = json.loads(line.decode("utf-8"))
                await room.handle_message(writer, message)
            except (json.JSONDecodeError, UnicodeDecodeError):
                await room.send(writer, {
                    "type": "error",
                    "message": "Invalid JSON message.",
                })

    except (ConnectionError, OSError):
        pass
    finally:
        await room.disconnect(writer)
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass
        print(f"[NETWORK] Disconnected: {peer}")


async def start_server(config):
    room = Room(config)
    server_config = config["server"]

    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, room),
        host=server_config["host"],
        port=server_config["port"],
    )

    addresses = ", ".join(str(s.getsockname()) for s in server.sockets)
    print("[SERVER] LAN-DouDizhu started.")
    print(f"[SERVER] Listening: {addresses}")
    print(f"[SERVER] Maximum players: {room.max_players}")
    print("[SERVER] Waiting for players. Press Ctrl+C to stop.")

    async with server:
        await server.serve_forever()


def main():
    # Clear the console for better readability
    os.system("cls" if os.name == "nt" else "clear")

    try:
        config = load_config(BASE_DIR / "config.json")
        validate_global_config(config)

        mode = load_mode(BASE_DIR / "modes", config["game"]["mode"])
        mode["validator"].validate(config, mode["manifest"])

        print(f"[CONFIG] Validated. Mode: {mode['id']}")
        asyncio.run(start_server(config))
        return 0

    except (ConfigError, ModeLoadError, OSError, ValueError) as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[SERVER] Shutdown.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
