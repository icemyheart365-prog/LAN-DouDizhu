const network = new GameNetwork();

let nickname = "";
let joined = false;
let landlordMode = "rob";
let hostId = null;
const playerNames = {};

const loginScreen = document.getElementById("login-screen");
const gameScreen = document.getElementById("game-screen");
const statusElement = document.getElementById("connection-status");

function setStatus(text, online) {
    statusElement.textContent = text;
    statusElement.className = `status ${online ? "online" : "offline"}`;
}

function sendGameAction(message) {
    try {
        document.getElementById("game-error").textContent = "";
        network.send(message);
    } catch (error) {
        document.getElementById("game-error").textContent = error.message;
    }
}

function updatePlayerNames(players) {
    for (const player of players || []) {
        playerNames[player.id] = player.nickname;
    }
}

function showGameState(state) {
    if (!state) return;

    renderGame(
        { ...state, host_id: hostId },
        playerNames,
        landlordMode,
        sendGameAction
    );
}

function returnToLogin(message) {
    joined = false;

    loginScreen.classList.remove("hidden");
    gameScreen.classList.add("hidden");

    setStatus(i18n.t("status.disconnected"), false);

    document.getElementById("login-error").textContent =
        message || i18n.t("error.serverDisconnected");

    document.getElementById("game-error").textContent = "";
    document.getElementById("game-message").textContent = "";
    document.getElementById("players").replaceChildren();
    document.getElementById("hand").replaceChildren();
    document.getElementById("action-controls").replaceChildren();
    document.getElementById("opponent-info").textContent = "";

    hostId = null;

    for (const id of Object.keys(playerNames)) {
        delete playerNames[id];
    }
}

document.getElementById("login-form").addEventListener("submit", async event => {
    event.preventDefault();

    const address = document.getElementById("server-address").value.trim();
    nickname = document.getElementById("nickname").value.trim();

    const error = document.getElementById("login-error");
    error.textContent = "";

    if (!address || !nickname) {
        error.textContent = i18n.t("login.fillRequired");
        return;
    }

    try {
        setStatus(i18n.t("status.connecting"), false);

        await network.connect(address);

        network.join(nickname);

        setStatus(i18n.t("status.joining"), false);
        error.textContent = i18n.t("login.validating");

    } catch (exception) {
        error.textContent = exception.message;
        setStatus(i18n.t("status.connectionFailed"), false);
        network.close();
    }
});

network.onMessage = message => {
    switch (message.type) {
        case "server_hello":
            landlordMode = message.landlord_mode || "rob";
            console.log("Server:", message);
            break;

        case "joined":
            joined = true;

            loginScreen.classList.add("hidden");
            gameScreen.classList.remove("hidden");

            setStatus(i18n.t("status.connected"), true);

            document.getElementById("game-message").textContent =
                i18n.t("room.welcome", { nickname: message.nickname });
            break;

        case "lobby": {
            hostId = message.host_id;
            updatePlayerNames(message.players);
            renderLobby(message, nickname);

            const players = message.players || [];

            const roomFull =
                players.length === message.required_players;

            const allReady =
                players.length > 0 &&
                players.every(player => player.ready);

            let statusMessage;

            if (message.notice) {
                statusMessage = message.notice;
            } else if (
                roomFull &&
                allReady
            ) {
                statusMessage = i18n.t("room.allReady");
            } else if (
                allReady &&
                !roomFull
            ) {
                statusMessage = i18n.t("room.waitingForPlayersAfterReady");
            } else if (roomFull) {
                statusMessage = i18n.t("room.playersArrived");
            } else {
                statusMessage = i18n.t("room.waiting");
            }

            document.getElementById("game-message").textContent =
                statusMessage;
            break;
        }

        case "game_started":
            showGameState(message.state);
            break;

        case "game_state":
            showGameState(message.state);
            break;

        case "room_closed":
            returnToLogin(
                message.message || i18n.t("room.closed")
            );
            break;

        case "game_notice":
            document.getElementById("game-message").textContent =
                message.message;
            break;

        case "error":
            if (!joined) {
                document.getElementById("login-error").textContent =
                    message.message;

                setStatus(i18n.t("status.joinFailed"), false);
                network.close();
            } else {
                document.getElementById("game-error").textContent =
                    message.message;
            }
            break;

        case "pong":
            console.log("Server pong");
            break;
    }
};

network.onDisconnect = () => {
    if (!joined) return;

    returnToLogin(i18n.t("room.disconnected"));
};

document.getElementById("ready-button").addEventListener("click", () => {
    const button = document.getElementById("ready-button");

    try {
        if (button.textContent === i18n.t("game.forceEnd")) {
            if (!window.confirm(
                i18n.t("game.confirmForceEnd")
            )) {
                return;
            }

            network.send({ type: "force_end" });
            return;
        }

        network.ready(button.textContent !== i18n.t("room.cancelReady"));
    } catch (error) {
        document.getElementById("game-error").textContent = error.message;
    }
});

document.getElementById("start-button").addEventListener("click", () => {
    try {
        document.getElementById("game-error").textContent = "";
        network.startGame();
    } catch (error) {
        document.getElementById("game-error").textContent = error.message;
    }
});

document.getElementById("leave-button").addEventListener("click", () => {
    network.close();
    location.reload();
});

// Local music controls
const music = document.getElementById("game-music");
const musicFile = document.getElementById("music-file");

music.volume = 0.35;

musicFile.addEventListener("change", () => {
    const file = musicFile.files[0];
    if (!file) return;

    if (music.dataset.objectUrl) {
        URL.revokeObjectURL(music.dataset.objectUrl);
    }

    const url = URL.createObjectURL(file);
    music.dataset.objectUrl = url;
    music.src = url;
    music.load();
});

document.getElementById("music-play").addEventListener("click", async () => {
    if (!music.src) {
        document.getElementById("game-error").textContent =
            i18n.t("music.selectFirst");
        return;
    }

    try {
        await music.play();
    } catch (error) {
        document.getElementById("game-error").textContent =
            i18n.t("music.playFailed", { error: error.message });
    }
});

document.getElementById("music-pause").addEventListener("click", () => {
    music.pause();
});

document.getElementById("music-volume").addEventListener("input", event => {
    music.volume = Number(event.target.value);
});

window.addEventListener("beforeunload", () => {
    if (music.dataset.objectUrl) {
        URL.revokeObjectURL(music.dataset.objectUrl);
    }
});
