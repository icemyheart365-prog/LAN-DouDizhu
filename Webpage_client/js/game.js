
let selectedCards = new Set();

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

    button.disabled =
        !me || message.players.length !== message.required_players;
    button.textContent = me?.ready ? "取消准备" : "准备";
}

function createActionButton(text, onClick, className = "secondary-button") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = text;
    button.addEventListener("click", onClick);
    return button;
}

function renderGame(state, playerNames, landlordMode, send) {
    const selfId = state.self.id;
    const actionArea = document.getElementById("action-controls");
    const hand = document.getElementById("hand");
    const players = state.players || [];

    document.getElementById("ready-button").disabled = true;
    document.getElementById("ready-button").textContent = "游戏进行中";

    document.getElementById("player-count").textContent = "游戏进行中";

    const nameOf = id =>
        playerNames[id] || `玩家 ${String(id).slice(0, 6)}`;

    document.getElementById("players").replaceChildren();

    for (const player of players) {
        const slot = document.createElement("article");
        slot.className = "player-slot";

        if (player.id === selfId) {
            slot.classList.add("self-player");
        }

        const name = document.createElement("strong");
        name.textContent =
            nameOf(player.id) +
            (player.id === selfId ? " (我)" : "");

        const info = document.createElement("span");
        info.textContent =
            `${player.card_count} 张牌` +
            (player.is_landlord ? " · 地主" : "");

        if (player.id === state.current_turn) {
            info.textContent += " · 当前回合";
        }

        slot.append(name, info);
        document.getElementById("players").appendChild(slot);
    }

    const lastPlay = state.last_play;
    const tableText = lastPlay
        ? `${nameOf(lastPlay.player_id)} 出牌：${lastPlay.cards.join(" ")}`
        : "当前没有待跟的牌";

    document.getElementById("opponent-info").textContent = tableText;

    if (state.status === "finished") {
        document.getElementById("game-message").textContent =
            `${nameOf(state.winner)} 获胜！获胜阵营：` +
            (state.winning_team === "landlord" ? "地主" : "农民");

        hand.replaceChildren();
        actionArea.replaceChildren();
        actionArea.classList.add("hidden");
        return;
    }

    if (state.status === "bidding") {
        const bidder = state.bid_order[state.bid_index];
        const myTurn = bidder === selfId;

        document.getElementById("game-message").textContent =
            myTurn
                ? "轮到你叫地主了！"
                : `等待 ${nameOf(bidder)} 叫地主……`;

        hand.replaceChildren();

        for (const card of state.self.cards) {
            const element = document.createElement("div");
            element.className = "card";

            if (card.startsWith("♥") || card.startsWith("♦")) {
                element.classList.add("red");
            }

            element.textContent = card;
            hand.appendChild(element);
        }

        actionArea.replaceChildren();
        actionArea.classList.remove("hidden");

        if (myTurn) {
            if (landlordMode === "rob") {
                actionArea.append(
                    createActionButton("不抢地主", () =>
                        send({ type: "bid", choice: false })
                    ),
                    createActionButton("抢地主", () =>
                        send({ type: "bid", choice: true }),
                        "primary-button"
                    )
                );
            } else {
                actionArea.append(
                    createActionButton("不叫", () =>
                        send({ type: "bid", choice: 0 })
                    )
                );

                for (let bid = 1; bid <= 3; bid++) {
                    if (bid > state.highest_bid) {
                        actionArea.append(
                            createActionButton(`${bid} 分`, () =>
                                send({ type: "bid", choice: bid }),
                                "primary-button"
                            )
                        );
                    }
                }
            }
        }

        return;
    }

    if (state.status !== "playing") {
        document.getElementById("game-message").textContent =
            `当前状态：${state.status}`;
        return;
    }

    const myTurn = state.current_turn === selfId;

    document.getElementById("game-message").textContent =
        myTurn ? "轮到你出牌" : `等待 ${nameOf(state.current_turn)} 出牌……`;

    hand.replaceChildren();

    for (const card of state.self.cards) {
        const element = document.createElement("button");
        element.type = "button";
        element.className = "card";
        element.textContent = card;

        if (card.startsWith("♥") || card.startsWith("♦")) {
            element.classList.add("red");
        }

        if (selectedCards.has(card)) {
            element.classList.add("selected");
        }

        element.disabled = !myTurn;

        element.addEventListener("click", () => {
            if (selectedCards.has(card)) {
                selectedCards.delete(card);
            } else {
                selectedCards.add(card);
            }

            renderGame(state, playerNames, landlordMode, send);
        });

        hand.appendChild(element);
    }

    actionArea.replaceChildren();
    actionArea.classList.remove("hidden");

    if (myTurn) {
        const selected = [...selectedCards];

        const playButton = createActionButton(
            `出牌 (${selected.length})`,
            () => {
                if (!selected.length) return;

                send({ type: "play", cards: selected });
                selectedCards.clear();
            },
            "primary-button"
        );

        playButton.disabled = selected.length === 0;
        actionArea.appendChild(playButton);

        const canPass =
            state.last_play !== null &&
            state.last_non_pass_player !== selfId;

        if (canPass) {
            actionArea.appendChild(
                createActionButton("不出 / Pass", () => {
                    selectedCards.clear();
                    send({ type: "pass" });
                })
            );
        }
    }
}
