
const network = new GameNetwork();

let nickname = "";
let joined = false;

const loginScreen = document.getElementById("login-screen");
const gameScreen = document.getElementById("game-screen");
const statusElement = document.getElementById("connection-status");

function setStatus(text, online) {
    statusElement.textContent = text;
    statusElement.className = `status ${online ? "online" : "offline"}`;
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
            console.log("Server:", message);
            break;

        case "joined":
            document.getElementById("game-message").textContent =
                `欢迎，${message.nickname}！等待其他玩家……`;
            break;

        case "lobby":
            renderLobby(message, nickname);
            document.getElementById("game-message").textContent =
                message.players.length === message.required_players
                    ? "三名玩家已到齐，请准备。"
                    : "等待其他玩家加入……";
            break;

        case "game_started":
            renderGame(message.state);
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
    network.ready(button.textContent !== "取消准备");
});

document.getElementById("leave-button").addEventListener("click", () => {
    network.close();
    location.reload();
});
