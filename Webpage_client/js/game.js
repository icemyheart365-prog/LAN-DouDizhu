let selectedCards = new Set();

function renderLobby(message, myNickname) {
    selectedCards.clear();

    document.getElementById("hand").replaceChildren();

    const actionArea = document.getElementById("action-controls");
    actionArea.replaceChildren();
    actionArea.classList.add("hidden");

    document.getElementById("opponent-info").textContent = "";
    const container = document.getElementById("players");
    container.replaceChildren();

    document.getElementById("player-count").textContent =
        i18n.t("room.playerCount", {
            count: message.players.length,
            total: message.required_players
        });

    for (let i = 0; i < message.required_players; i++) {
        const player = message.players[i];
        const slot = document.createElement("article");
        slot.className = "player-slot";

        if (player) {
            const name = document.createElement("strong");
            name.textContent =
                player.nickname +
                (player.nickname === myNickname ? ` (${i18n.t("room.me")})` : "") +
                (player.is_host ? ` 👑 ${i18n.t("room.host")}` : "");

            const state = document.createElement("span");
            state.className = player.ready ? "ready" : "waiting";
            state.textContent = player.ready
                ? `● ${i18n.t("room.ready")}`
                : `● ${i18n.t("room.notReady")}`;

            slot.append(name, state);
        } else {
            slot.classList.add("empty");
            slot.textContent = i18n.t("room.waitingForPlayers");
        }

        container.appendChild(slot);
    }

    const me = message.players.find(p => p.nickname === myNickname);
    const readyButton = document.getElementById("ready-button");
    const startButton = document.getElementById("start-button");

    // Players can get ready before the room is full.
    readyButton.disabled = !me;
    readyButton.textContent = me?.ready
        ? i18n.t("room.cancelReady")
        : i18n.t("room.readyButton");
    readyButton.style.background = "";
    readyButton.style.color = "";

    // Only the room host can start the game.
    const isHost = me?.is_host === true;
    startButton.hidden = !isHost;

    const requirements = message.start_requirements || {
        require_full_room: true,
        require_all_ready: true,
    };

    const roomFull =
        message.players.length === message.required_players;

    const allReady =
        message.players.length > 0 &&
        message.players.every(player => player.ready);

    const canStart =
        (!requirements.require_full_room || roomFull) &&
        (!requirements.require_all_ready || allReady);

    startButton.disabled = !isHost || !canStart;

    if (!roomFull && requirements.require_full_room) {
        startButton.textContent = i18n.t("room.waitingForPlayersButton");
    } else if (!allReady && requirements.require_all_ready) {
        startButton.textContent = i18n.t("room.waitingForReadyButton");
    } else {
        startButton.textContent = i18n.t("room.start");
    }
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

    const readyButton = document.getElementById("ready-button");
    const isHost = selfId === state.host_id;

    readyButton.disabled = !isHost;
    readyButton.textContent = isHost
        ? i18n.t("game.forceEnd")
        : i18n.t("game.inProgress");
    readyButton.style.background = isHost ? "#a83232" : "";
    readyButton.style.color = isHost ? "#ffffff" : "";
    document.getElementById("start-button").hidden = true;

    document.getElementById("player-count").textContent =
        i18n.t("game.inProgress");

    const nameOf = id =>
        playerNames[id] || String(id).slice(0, 6);

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
            (player.id === selfId ? ` (${i18n.t("room.me")})` : "") +
            (player.id === state.host_id ? ` 👑 ${i18n.t("room.host")}` : "");

        const info = document.createElement("span");
        info.textContent =
            i18n.t("game.cardCount", { count: player.card_count }) +
            (player.is_landlord ? ` · ${i18n.t("game.landlord")}` : "");

        if (player.id === state.current_turn) {
            info.textContent += ` · ${i18n.t("game.currentTurn")}`;
        }

        slot.append(name, info);
        document.getElementById("players").appendChild(slot);
    }

    const lastPlay = state.last_play;
    const tableText = lastPlay
        ? i18n.t("game.lastPlay", {
            nickname: nameOf(lastPlay.player_id),
            cards: lastPlay.cards.join(" ")
        })
        : i18n.t("game.noPendingPlay");

    document.getElementById("opponent-info").textContent = tableText;

    if (state.status === "finished") {
        const message = document.getElementById("game-message");

        if (state.end_reason === "host_terminated") {
            message.textContent = i18n.t("game.hostForceEnded");
        } else if (state.winner) {
            message.textContent = i18n.t("game.winner", {
                nickname: nameOf(state.winner),
                team: state.winning_team === "landlord"
                    ? i18n.t("game.landlordTeam")
                    : i18n.t("game.farmerTeam")
            });
        } else {
            message.textContent = i18n.t("game.ended");
        }

        selectedCards.clear();
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
                ? i18n.t("game.yourBiddingTurn")
                : i18n.t("game.waitingForBid", {
                    nickname: nameOf(bidder)
                });

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
                    createActionButton(i18n.t("action.noRob"), () =>
                        send({ type: "bid", choice: false })
                    ),
                    createActionButton(i18n.t("action.rob"), () =>
                        send({ type: "bid", choice: true }),
                        "primary-button"
                    )
                );
            } else {
                actionArea.append(
                    createActionButton(i18n.t("action.noBid"), () =>
                        send({ type: "bid", choice: 0 })
                    )
                );

                for (let bid = 1; bid <= 3; bid++) {
                    if (bid > state.highest_bid) {
                        actionArea.append(
                            createActionButton(
                                i18n.t("action.bidPoints", { points: bid }),
                                () => send({ type: "bid", choice: bid }),
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
            i18n.t("game.currentStatus", { status: state.status });
        return;
    }

    const myTurn = state.current_turn === selfId;

    document.getElementById("game-message").textContent =
        myTurn
            ? i18n.t("game.yourPlayingTurn")
            : i18n.t("game.waitingForPlay", {
                nickname: nameOf(state.current_turn)
            });

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
            i18n.t("action.play", { count: selected.length }),
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
                createActionButton(i18n.t("action.pass"), () => {
                    selectedCards.clear();
                    send({ type: "pass" });
                })
            );
        }
    }
}
