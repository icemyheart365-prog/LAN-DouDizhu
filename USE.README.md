# LAN-DouDizhu 启动指南

## 1. 启动后端（Python WebSocket Server）

在 WSL Ubuntu 终端 1 中执行：

```bash
cd /mnt/d/Git/LAN-DouDizhu/Server
source ../.venv/bin/activate
python3 web_server.py
```

默认 WebSocket 端口：`8766`

## 2. 启动前端（Web Client）

打开另一个 WSL Ubuntu 终端 2，执行：

```bash
cd /mnt/d/Git/LAN-DouDizhu/Webpage_client
python3 -m http.server 8080 --bind 0.0.0.0
```

默认网页端口：`8080`

## 3. 打开游戏

在浏览器访问：

```text
http://localhost:8080
```

局域网内其他设备访问：

```text
http://<服务器电脑的局域网IP>:8080
```

进入游戏后，在服务器地址栏填写服务器电脑的局域网 IP，昵称填写自己的游戏昵称。

## 4. 关闭服务

分别在两个终端按：

```text
Ctrl + C
```

即可停止对应服务。

---

**注意：** 后端和前端需要同时运行。局域网其他设备需要能够访问服务器电脑的 TCP `8080` 和 `8766` 端口。
