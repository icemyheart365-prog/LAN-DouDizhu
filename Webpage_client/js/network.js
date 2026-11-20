
class GameNetwork {
    constructor() {
        this.socket = null;
        this.onMessage = null;
        this.onDisconnect = null;
    }

    connect(address) {
        return new Promise((resolve, reject) => {
            this.socket = new WebSocket(`ws://${address}:8766`);

            this.socket.onopen = () => resolve();

            this.socket.onerror = () => {
                reject(new Error(i18n.t("login.connectionError")));
            };

            this.socket.onmessage = event => {
                let message;

                try {
                    message = JSON.parse(event.data);
                } catch {
                    return;
                }

                this.onMessage?.(message);
            };

            this.socket.onclose = () => {
                this.onDisconnect?.();
            };
        });
    }

    send(message) {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            throw new Error(i18n.t("error.serverDisconnected"));
        }

        this.socket.send(JSON.stringify(message));
    }

    join(nickname) {
        this.send({ type: "join", nickname });
    }

    ready(value) {
        this.send({ type: "ready", ready: value });
    }

    startGame() {
        this.send({ type: "start_game" });
    }

    close() {
        this.socket?.close();
    }
}
