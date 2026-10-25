# QR Code & Barcode Generation Service / 二维码与条形码生成服务

A lightweight, Dockerized microservice for generating QR codes (optimized for printing) and Barcodes (Code128). Built with Python Flask and designed for offline deployment.

一个基于 Python Flask 和 Docker 构建的轻量级微服务，用于生成二维码（打印优化）和条形码（Code128）。支持离线部署。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

## Features / 功能

- **Offline Ready**: Fully containerized, no internet connection required after build. / **完全离线**: 容器化部署，构建后无需联网。
- **Print Optimized**: QR codes are generated with minimal whitespace (border=1) to save paper. / **打印优化**: 二维码使用最小边框设计，最大化利用纸张空间。
- **Dual Support**: Generates both QR Codes and Code128 Barcodes. / **双重支持**: 支持生成二维码和 Code128 条形码。
- **Simple API**: Easy-to-use HTTP GET endpoints. / **简单API**: 使用 HTTP GET 请求即可调用。
- **Production Ready**: Includes logging, error handling, input validation, and security headers. / **生产就绪**: 包含日志、错误处理、输入验证和安全响应头。
- **Health Monitoring**: Built-in health check endpoint for container orchestration. / **健康监控**: 内置健康检查端点，支持容器编排。
- **API Documentation**: Interactive Swagger UI at `/docs`, OpenAPI 3.0 spec at `/apispec.json` (source: `openapi.json`). / **API文档**: 交互式Swagger UI文档位于 `/docs`，OpenAPI 3.0 规格位于 `/apispec.json`（源文件 `openapi.json`）。
- **Rate Limiting**: Built-in rate limiting to prevent abuse (100 requests/minute globally, 50/minute per endpoint). / **速率限制**: 内置速率限制防止滥用（全局100请求/分钟，单端点50/分钟）。
- **Metrics Endpoint**: Performance and config metrics at `/metrics`. / **指标端点**: 性能和配置指标位于 `/metrics`。
- **Developer Tools**: Makefile for common tasks, pre-commit hooks, and comprehensive testing. / **开发工具**: Makefile简化常用命令，pre-commit钩子，完整测试套件。

## Requirements / 环境要求

### For Docker Deployment / Docker 部署
- Docker 20.10+
- Docker Compose (optional / 可选)

### For Local Development / 本地开发
- Python 3.12+ (3.13 recommended, same as the Docker image / 推荐 3.13，与 Docker 镜像一致)
- pip 23.0+

## Quick Start / 快速开始

### Method 1: Docker (Recommended / 推荐)

#### 1. Build the Image / 构建镜像

```bash
docker build -t qr-service .
```

#### 2. Run the Service / 启动服务

**Default Port / 默认端口 (8505 on the host, 8080 inside the container / 宿主机 8505，容器内 8080):**
```bash
docker run -d -p 8505:8080 --name qr-service qr-service
```

**Custom Port / 自定义端口 (e.g., 9090):**
```bash
docker run -d -p 9090:9090 -e PORT=9090 --name qr-service-custom qr-service
```

#### 3. Verify Service is Running / 验证服务运行

```bash
curl http://localhost:8505/health
# Expected output: OK
```

### Method 2: Docker Compose

The compose file runs the `qr-service:stable` image on the external Docker network `qrnetwork`,
published on host port `8505` (override with `QR_HOST_PORT`, e.g. `127.0.0.1:8505` to listen on localhost only).

compose 文件使用 `qr-service:stable` 镜像，接入外部 Docker 网络 `qrnetwork`，默认映射到宿主机 `8505` 端口（可通过 `QR_HOST_PORT` 修改，例如设为 `127.0.0.1:8505` 只监听本机）。

```bash
docker network create qrnetwork   # first time only / 仅首次
docker build -t qr-service:stable .
docker compose up -d
```

Recommended for stable local operations and controlled redeploy:

```bash
# Build a versioned image, update stable tag, and deploy
make docker-deploy

# Redeploy using current stable tag (no rebuild)
make docker-redeploy

# Rollback to a previous versioned tag
make docker-rollback TAG=20260406-120000

# Check running status and image details
make docker-status

# Safe cleanup: only dangling images
make docker-prune-dangling
```

### Method 3: Local Python

```bash
# Install dependencies / 安装依赖
pip install --require-hashes -r requirements.txt

# Run the service / 运行服务
PORT=8505 python main.py

# Or with gunicorn / 或使用 gunicorn
gunicorn --bind 0.0.0.0:8505 main:app
```

## Usage / 使用方法

Access the service via HTTP request from your browser, command line, or application.
通过浏览器、命令行或您的应用程序发送 HTTP 请求。

### API Documentation / API文档

Interactive Swagger UI is available at:
交互式Swagger UI文档位于：

```
http://localhost:8505/docs
```

### Health Check / 健康检查

```bash
curl http://localhost:8505/health
```

### Metrics / 指标

Get service metrics and configuration:
获取服务指标和配置：

```bash
curl http://localhost:8505/metrics
```

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.4",
  "config": {
    "max_content_length": 1000,
    "rate_limit": "100 per minute",
    "allowed_types": ["qrcode", "barcode"]
  }
}
```

### Generate QR Code (Default) / 生成二维码 (默认)

```http
GET http://localhost:8505/generate?content=<YOUR_CONTENT>
```

**Example / 示例:**

```bash
# Simple text / 简单文本
curl "http://localhost:8505/generate?content=Hello World" > qrcode.png

# Order ID / 订单号
curl "http://localhost:8505/generate?content=ORD-2023-001" > qrcode.png

# URL / 网址
curl "http://localhost:8505/generate?content=https://example.com" > qrcode.png

# Explicit type / 显式指定类型
curl "http://localhost:8505/generate?content=Hello&type=qrcode" > qrcode.png
```

### Generate Barcode / 生成条形码

```http
GET http://localhost:8505/generate?content=<YOUR_CONTENT>&type=barcode
```

**Example / 示例:**

```bash
# Alphanumeric content (Code128) / 字母数字内容
curl "http://localhost:8505/generate?content=ABC123&type=barcode" > barcode.png

# Numbers only / 仅数字
curl "http://localhost:8505/generate?content=123456789&type=barcode" > barcode.png
```

## API Reference / API 参考

### `GET /generate`

Generate a QR code or barcode image.

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `content` | `string` | **Yes** | - | The text/data to encode (max 1000 chars). Must be alphanumeric for barcodes. |
| `type` | `string` | No | `qrcode` | `qrcode` for QR Code, `barcode` for Code128. Case-insensitive. |

**Response:**
- **Success (200)**: PNG image file
- **Error (400)**: Invalid input (missing content, too long, invalid type, etc.)
- **Error (500)**: Internal server error

**Input Validation / 输入验证:**
- Content length: 1-1000 characters
- Barcode content: Must be alphanumeric (letters and numbers only)
- QR code content: Any text
- Type: Must be `qrcode` or `barcode`

### `GET /health`

Health check endpoint for monitoring and container orchestration.

**Response:**
- **Success (200)**: `OK`

## Developer Tools / 开发工具

### Makefile Commands / Makefile命令

This project includes a Makefile to simplify common development tasks:
本项目包含Makefile来简化常见开发任务：

```bash
# Show all available commands / 显示所有可用命令
make help

# Setup development environment / 设置开发环境
make init                  # Create venv and install deps
make install-dev           # Install development dependencies

# Testing / 测试
make test                  # Run tests
make coverage              # Run tests with coverage report

# Code Quality / 代码质量
make lint                  # Run linting checks
make format                # Format code with black
make type-check            # Run type checking
make security              # Run security checks
make qa                    # Run all QA checks

# Docker / Docker操作
make docker-build          # Build Docker image
make docker-run            # Run Docker container
make docker-stop           # Stop Docker container
make docker-logs           # View container logs
make docker-deploy         # Build versioned image + stable deploy
make docker-redeploy       # Redeploy from stable image only
make docker-rollback TAG=xxx # Rollback to a historical tag
make docker-status         # Show container and image status
make docker-images         # List repository images
make docker-prune-dangling # Remove dangling images safely

# Utilities / 工具
make clean                 # Clean up generated files
make ci                    # Run CI pipeline locally
make release               # Prepare for release

# All-in-one / 一键执行
make all                   # Clean, install, QA, Docker build
```

### Manual Testing / 手动测试

```bash
# Install development dependencies / 安装开发依赖
pip install --require-hashes -r requirements-dev.txt

# Run all tests / 运行所有测试
pytest

# Run with coverage / 运行测试并生成覆盖率报告
pytest --cov=main --cov-report=html

# View coverage report / 查看覆盖率报告
open htmlcov/index.html
```

### Code Quality Checks / 代码质量检查

```bash
# Or use Makefile (recommended) / 或使用Makefile（推荐）
make qa

# Manual commands / 手动命令：
black main.py tests/        # Format code
flake8 main.py tests/       # Lint
mypy main.py                # Type check
bandit -r main.py           # Security scan
```

## Deployment / 部署

Since this is a Dockerized application, you can deploy it to any server with Docker installed.
由于这是一个 Docker化应用，您可以将其部署到任何安装了 Docker 的服务器上。

### Save for Offline Transfer / 离线传输

```bash
# Save image / 保存镜像
docker save -o qr-service.tar qr-service

# Transfer to target server / 传输到目标服务器
scp qr-service.tar user@server:/path/

# Load image on target server / 在目标服务器加载镜像
docker load -i qr-service.tar
```

### Production Deployment Tips / 生产部署建议

1. **Use Environment Variables / 使用环境变量**
   ```bash
   docker run -d \
     -p 8505:8080 \
     -e PORT=8080 \
     -e DEBUG=false \
     --name qr-service \
     qr-service
   ```

2. **Resource Limits / 资源限制**
   ```bash
   docker run -d \
     -p 8505:8080 \
     --memory="256m" \
     --cpus="0.5" \
     --name qr-service \
     qr-service
   ```

3. **Restart Policy / 重启策略**
   ```bash
   docker run -d \
     -p 8505:8080 \
     --restart unless-stopped \
     --name qr-service \
     qr-service
   ```

4. **Health Check / 健康检查**
   - The Docker image includes a built-in health check
   - Check container health: `docker ps` (look for health status)

## Troubleshooting / 故障排查

### Service not responding / 服务无响应

```bash
# Check if container is running / 检查容器是否运行
docker ps

# Check container logs / 查看容器日志
docker logs qr-service

# Check container health / 检查容器健康状态
docker inspect qr-service | grep -A 10 Health
```

### Port already in use / 端口已被占用

```bash
# Use a different port / 使用其他端口
docker run -d -p 9090:8080 -e PORT=8080 --name qr-service qr-service

# Or stop the conflicting service / 或停止冲突的服务
lsof -ti:8505 | xargs kill -9
```

### "Barcode content must contain only ASCII characters" error / 条形码内容必须为 ASCII 字符

Barcodes (Code128) support ASCII characters only (max 64), including `-`, `.`, `@`, `#`, `_`, `/`. Non-ASCII text such as Chinese must use a QR code instead.

条形码（Code128）仅支持 ASCII 字符（最多 64 个），包括 `-`、`.`、`@`、`#`、`_`、`/` 等。中文等非 ASCII 内容请使用二维码。

```bash
# Wrong / 错误
curl "http://localhost:8505/generate?content=Hello世界&type=barcode"

# Correct / 正确
curl "http://localhost:8505/generate?content=ABC-123&type=barcode"
```

### "Content exceeds maximum length" error / 内容超过最大长度错误

Maximum content length is 1000 characters. Reduce your input.

最大内容长度为 1000 字符。请减少输入内容。

### Image quality issues / 图像质量问题

QR codes use `box_size=10` and `border=1` for print optimization. To customize:
1. Modify `QR_BOX_SIZE` and `QR_BORDER_SIZE` in `main.py`
2. Rebuild the Docker image

二维码使用 `box_size=10` 和 `border=1` 进行打印优化。要自定义：
1. 修改 `main.py` 中的 `QR_BOX_SIZE` 和 `QR_BORDER_SIZE`
2. 重新构建 Docker 镜像

## Security / 安全性

- **Input validation**: Content length and type validation
- **Security headers**: X-Content-Type-Options, X-Frame-Options, CSP
- **Non-root user**: Docker container runs as non-root user
- **No secrets**: No hardcoded credentials or API keys
- **Log privacy**: Logs record type, length and status only, never the encoded content or query string / 日志只记录类型、长度和状态，不记录编码内容和查询参数

## Dependency Management / 依赖管理

- `requirements.txt` / `requirements-dev.txt` are hash-pinned lock files generated from `requirements*.in` by `make lock`; installs use `--require-hashes`. / 锁定文件由 `make lock` 从 `requirements*.in` 生成，带哈希校验。
- **14-day cooldown / 14 天冷却期**: new locks only accept releases at least 14 days old, so a freshly published (possibly compromised) package version is not picked up. Security fixes are the only exception. / 只采用发布满 14 天的版本，降低新发布恶意版本的风险；仅安全修复例外。
- The Docker base image, GitHub Actions and pre-commit hooks are pinned by digest / commit SHA. / 基础镜像、Actions、pre-commit 钩子均按 digest/SHA 固定。
- Dependabot proposes weekly updates with the same cooldown; CI runs `pip-audit` and Trivy on every push. / Dependabot 每周按同样冷却期提更新，CI 每次推送都运行 pip-audit 和 Trivy。

## Configuration / 配置

Environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PORT` | `8080` | Port the app listens on (inside the container; map it to a host port such as `8505`) |
| `DEBUG` | `False` | Enable Flask debug mode (not for production) |
| `RATE_LIMIT_ENABLED` | `true` | Set to `false` to disable rate limiting (e.g. trusted internal network) |
| `RATE_LIMIT` | `100 per minute` | Global limit per client IP |
| `GENERATE_RATE_LIMIT` | `50 per minute` | Limit per client IP on `/generate` |
| `PROXY_COUNT` | `0` | Number of reverse proxies in front of the app (`1` for a Cloudflare Tunnel or a single nginx). Trusts their `X-Forwarded-For` / `X-Forwarded-Proto`, so rate limits count real client IPs. Only set it when the port is reachable through those proxies alone |
| `SWAGGER_HOST` | *(empty)* | Public host for the OpenAPI `servers` list, e.g. `qr.example.com`. Empty = no servers list, so Swagger UI calls the same scheme and host the docs page was opened on |
| `SWAGGER_SCHEMES` | `https,http` | Protocols listed for `SWAGGER_HOST` (first is the default); ignored when `SWAGGER_HOST` is empty |

Rate limits are stored in memory, so each gunicorn worker counts separately. Behind a reverse proxy (Cloudflare Tunnel, nginx), every request arrives from the proxy's address and all clients would share one limit: set `PROXY_COUNT=1` and bind the port to localhost (`QR_HOST_PORT=127.0.0.1:8505`) so only the proxy can reach it.

速率限制保存在内存中，每个 gunicorn worker 独立计数。部署在反向代理（Cloudflare Tunnel、nginx）后时，所有请求都来自代理地址，所有客户端会共用一个额度：请设置 `PROXY_COUNT=1`，并把端口只绑定到本机（`QR_HOST_PORT=127.0.0.1:8505`），确保只有代理能访问。

Example `.env` next to `docker-compose.yml` (not committed) / 示例 `.env`（不提交）:

```bash
QR_HOST_PORT=127.0.0.1:8505
PROXY_COUNT=1
```

## Performance / 性能

- **Response time**: ~50-200ms per request (depends on content size)
- **Memory usage**: ~50-100MB
- **Concurrency**: Supports multiple workers with gunicorn

## Contributing / 贡献

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献指南。

## Changelog / 更新日志

See [CHANGELOG.md](CHANGELOG.md) for version history.

查看 [CHANGELOG.md](CHANGELOG.md) 了解版本历史。

## License / 许可证

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
Third-party components (Swagger UI, Python packages, the bundled font) and trademarks are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。第三方组件与商标说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

QR Code is a registered trademark of DENSO WAVE INCORPORATED. / QR Code 是 DENSO WAVE INCORPORATED 的注册商标。

## Support / 支持

For issues and feature requests, please create an issue on GitHub.

如有问题或功能请求，请在 GitHub 上创建 issue。

---

Made with ❤️ using Flask, qrcode, and python-barcode
