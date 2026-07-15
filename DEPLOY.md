# 部署指南：从桌面软件到网站

本文档说明如何将取证平台从桌面软件部署为公网可访问的网站。

## 总体架构

桌面版和网页版共用同一套后端代码，通过 `RUN_MODE` 环境变量切换模式：

| 模式 | RUN_MODE | 认证 | 适用场景 |
|------|----------|------|----------|
| 桌面版 | `desktop` | 无需认证 | 本地 Windows 使用 |
| 网页版 | `web` | JWT 登录 | 公网部署 |

## 你需要做的事（按顺序）

### 1. 购买服务器

推荐配置：
- 2 核 CPU / 4GB 内存 / 40GB 硬盘（最低）
- 操作系统：Ubuntu 22.04 或 CentOS 8+
- 国内用户推荐阿里云、腾讯云（速度更快，但需要备案）
- 海外用户推荐 Vultr、DigitalOcean、AWS Lightsail

### 2. 购买域名 + 备案（国内必做）

- 域名注册：阿里云万网、腾讯云 DNSPod 均可
- **ICP 备案**：国内服务器必须备案，阿里云/腾讯云有在线备案流程，约 15-20 个工作日
- 如果是海外服务器，不需要备案，直接解析域名即可

### 3. 配置 DNS

将域名 A 记录指向服务器 IP：

```
your-domain.com  →  A  →  你的服务器公网IP
```

### 4. 安装 Docker（服务器上）

```bash
# Ubuntu
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER

# 安装 docker-compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 5. 部署项目

```bash
# 克隆代码
git clone https://github.com/rain-foece/Integration_project.git
cd Integration_project

# 修改 JWT 密钥（重要！）
# 编辑 docker-compose.yml，把 JWT_SECRET 改成随机字符串
# 生成随机密钥：openssl rand -hex 32

# 启动
docker-compose up -d
```

### 6. 配置 Nginx 反向代理

```bash
# 安装 Nginx
sudo apt install nginx -y

# 复制配置文件
sudo cp nginx.conf /etc/nginx/sites-available/forensics
sudo sed -i 's/your-domain.com/你的域名/g' /etc/nginx/sites-available/forensics
sudo ln -s /etc/nginx/sites-available/forensics /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 7. 配置 SSL 证书（HTTPS）

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx -y

# 自动配置 HTTPS
sudo certbot --nginx -d 你的域名
```

完成后访问 `https://你的域名` 即可使用。

## 快速测试（不需要域名的本地测试）

```bash
# 切换到 web 模式启动
set RUN_MODE=web
set JWT_SECRET=test-secret-key
C:\Python314\python.exe -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

然后用浏览器访问 `http://localhost:8000/login.html` 注册账号后使用。

## 环境变量说明

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RUN_MODE` | `desktop` | 运行模式：`desktop` 或 `web` |
| `JWT_SECRET` | 见 config.py | JWT 签名密钥，生产环境必须修改 |
| `JWT_ALGORITHM` | `HS256` | JWT 签名算法 |
| `JWT_EXPIRE_HOURS` | `24` | 登录过期时间（小时） |
| `LOG_LEVEL` | `INFO` | 日志级别 |

## 注意事项

- 网页版部署后，**16 个工具中只有 10 个纯 Python 内置工具可用**，6 个外部工具（Volatility、Fiddler 等）需要服务器上安装对应 EXE
- 外部工具仅支持 Windows，如果部署在 Linux 服务器上则无法使用
- 建议在国内服务器部署时开启 HTTPS，避免数据传输被劫持
- 数据库文件 `forensics.db` 需要定期备份