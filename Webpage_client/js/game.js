
function renderLobby(message, myNickname) {
    const container = document.getElementById("players");
    container.replaceChildren();

    document.getElementById("player-count").textContent =
        `${message.players.length} / ${message.required_players} 人`;

    for (let i = 0; i < message.required_players; i++) {
        const player = message.players[i];
        const slot = document.createElement("article");
        slot.className = "player-slot";

        if (player) {
            const name = document.createElement("strong");
            name.textContent =
                player.nickname + (player.nickname === myNickname ? " (我)" : "");

            const state = document.createElement("span");
            state.className = player.ready ? "ready" : "waiting";
            state.textContent = player.ready ? "● 已准备" : "● 未准备";

            slot.append(name, state);
        } else {
            slot.classList.add("empty");
            slot.textContent = "等待玩家加入";
        }

        container.appendChild(slot);
    }

    const me = message.players.find(p => p.nickname === myNickname);
    const button = document.getElementById("ready-button");

    button.disabled = !me || message.players.length !== message.required_players;
    button.textContent = me?.ready ? "取消准备" : "准备";
}

function renderGame(state) {
    document.getElementById("game-message").textContent = "游戏开始！";
    document.getElementById("opponent-info").textContent =
        state.opponents.map(
            player => `${player.id.slice(0, 6)}：${player.card_count} 张牌`
        ).join("　 |　 ");

    const hand = document.getElementById("hand");
    hand.replaceChildren();

    for (const card of state.self.cards) {
        const element = document.createElement("div");
        element.className = "card";

        if (card.startsWith("♥") || card.startsWith("♦")) {
            element.classList.add("red");
        }

        const rank = document.createElement("span");
        rank.textContent = card;

        const suit = document.createElement("span");
        suit.textContent = card.slice(0, 1);

        element.append(rank, suit);
        hand.appendChild(element);
    }

    document.getElementById("ready-button").disabled = true;
    document.getElementById("ready-button").textContent = "游戏进行中";
}
