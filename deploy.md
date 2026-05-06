# 服务器部署指南

## 服务器信息

- IP: `43.138.164.41`
- 端口: `22`
- 用户: `root`
- 项目路径: `/opt/xinyu-agent/`
- 认证方式: 本地密钥

## 服务架构

Docker Compose 部署，两个容器：

| 容器 | 服务 | 端口映射 |
|------|------|----------|
| `xinyu-agent-server-1` | 应用服务 (uvicorn) | 127.0.0.1:8002 → 8000 |
| `xinyu-agent-chromadb-1` | ChromaDB 向量数据库 | 内部 8000 |

## Git 推送

- 仓库: `https://github.com/acai77777/xinyu-agent.git`
- 主分支: `main`
- Git 根目录: `H:\AI`（注意不是 `H:\AI\心理学agent`）

### 推送到远端

```bash
# 在 H:\AI 目录下执行（git 根目录）
cd H:\AI

# 创建新分支并推送
git checkout -b feature/分支名
git add 心理学agent/server/需要提交的文件
git commit -m "feat: 提交信息"
git push -u origin feature/分支名
```

### 使用代理推送（GitHub 直连不通时）

```bash
# 通过代理推送（替换为实际代理地址和端口）
git -c http.proxy=http://127.0.0.1:7890 -c https.proxy=http://127.0.0.1:7890 push -u origin feature/分支名
```

### 通过服务器 SSH 隧道推送（代理也不好使时）

```bash
# 1. 建立 SSH 隧道（通过服务器中转连 GitHub）
ssh -f -N -L 8443:github.com:443 root@43.138.164.41

# 2. 通过隧道推送
git -c http.sslBackend=openssl -c url."https://127.0.0.1:8443/".insteadOf="https://github.com/" -c http.sslVerify=false push -u origin feature/分支名

# 3. 关闭隧道
taskkill /F /IM ssh.exe
```

### 注意事项

- `server/data/psyqa_*.json` 等大数据文件不要提交到 git
- `server/.env` 等敏感文件不要提交
- `server/data/agent.db` 数据库文件不要提交

## 更新流程

### 1. 上传修改的文件

```bash
# 在本地项目目录 H:\AI\心理学agent 下执行
# 替换 <文件路径> 为实际修改的文件

scp server/文件路径 root@43.138.164.41:/opt/xinyu-agent/server/文件路径
```

示例：

```bash
scp server/agent/loop.py root@43.138.164.41:/opt/xinyu-agent/server/agent/loop.py
scp server/api/routes_chat.py root@43.138.164.41:/opt/xinyu-agent/server/api/routes_chat.py
scp server/db.py root@43.138.164.41:/opt/xinyu-agent/server/db.py
```

新文件也一样：

```bash
scp server/agent/session_strategy.py root@43.138.164.41:/opt/xinyu-agent/server/agent/session_strategy.py
```

### 2. 重新构建并启动

```bash
ssh root@43.138.164.41

cd /opt/xinyu-agent

# 重新构建 server 镜像（--no-cache 可选，完全重建时加上）
docker compose build server

# 重启 server 容器（chromadb 不受影响）
docker compose up -d server
```

### 3. 验证

```bash
# 查看容器状态（等待 health: healthy）
docker compose ps

# 查看最近日志
docker compose logs server --tail 20
```

## 常用运维命令

```bash
# 查看实时日志
docker compose logs -f server

# 重启所有服务
docker compose restart

# 停止所有服务
docker compose down

# 进入 server 容器调试
docker exec -it xinyu-agent-server-1 bash

# 查看数据库
docker exec -it xinyu-agent-server-1 python -c "import sqlite3; print(sqlite3.connect('/app/data/agent.db').execute('SELECT name FROM sqlite_master').fetchall())"
```
