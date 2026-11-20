const network = new GameNetwork();

let nickname = "";
let joined = false;
let landlordMode = "rob";
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

    renderGame(state, playerNames, landlordMode, sendGameAction);
}

document.getElementById("login-form").addEventListener("submit", async event => {
    event.preventDefault();

    const address = document.getElementById("server-address").value.trim();
    nickname = document.getElementById("nickname").value.trim();

    const error = document.getElementById("login-error");
    error.textContent = "";

    if (!address || !nickname) {
        error.textContent = "请填写服务器地址和昵称。";
        return;
    }

    try {
        setStatus("连接中", false);

        await network.connect(address);

        network.join(nickname);
        joined = true;

        loginScreen.classList.add("hidden");
        gameScreen.classList.remove("hidden");
        setStatus("已连接", true);

        document.getElementById("game-message").textContent =
            "正在加入房间……";

    } catch (exception) {
        error.textContent = exception.message;
        setStatus("连接失败", false);
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
            document.getElementById("game-message").textContent =
                `欢迎，${message.nickname}！等待其他玩家……`;
            break;

        case "lobby":
            updatePlayerNames(message.players);
            renderLobby(message, nickname);

            document.getElementById("game-message").textContent =
                message.players.length === message.required_players
                    ? "三名玩家已到齐，请准备。"
                    : "等待其他玩家加入……";
            break;

        case "game_started":
            showGameState(message.state);
            break;

        case "game_state":
            showGameState(message.state);
            break;

        case "game_notice":
            document.getElementById("game-message").textContent =
                message.message;
            break;

        case "error":
            document.getElementById("game-error").textContent =
                message.message;
            break;

        case "pong":
            console.log("Server pong");
            break;
    }
};

network.onDisconnect = () => {
    joined = false;
    setStatus("连接断开", false);

    document.getElementById("game-error").textContent =
        "与服务器的连接已断开。";
};

document.getElementById("ready-button").addEventListener("click", () => {
    const button = document.getElementById("ready-button");

    try {
        network.ready(button.textContent !== "取消准备");
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
            "请先选择一首本地音乐。";
        return;
    }

    try {
        await music.play();
    } catch (error) {
        document.getElementById("game-error").textContent =
            "音乐播放失败：" + error.message;
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