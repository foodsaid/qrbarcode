# QR Code & Barcode Generation Service / 二维码与条形码生成服务

A lightweight, Dockerized microservice for generating QR codes (optimized for printing) and Barcodes (Code128). Built with Python Flask and designed for offline deployment.

一个基于 Python Flask 和 Docker 构建的轻量级微服务，用于生成二维码（打印优化）和条形码（Code128）。支持离线部署。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)

## Features / 功能

- **Offline Ready**: Fully containerized, no internet connection required after build. / **完全离线**: 容器化部署，构建后无需联网。
- **Print Optimized**: QR codes are generated with minimal whitespace (border=1) to save paper. / **打印优化**: 二维码使用最小边框设计，最大化利用纸张空间。
- **Dual Support**: Generates both QR Codes and Code128 Barcodes. / **双重支持**: 支持生成二维码和 Code128 条形码。
- **Simple API**: Easy-to-use HTTP GET endpoints. / **简单API**: 使用 HTTP GET 请求即可调用。
- **Production Ready**: Includes logging, error handling, input validation, and security headers. / **生产就绪**: 包含日志、错误处理、输入验证和安全响应头。
- **Health Monitoring**: Built-in health check endpoint for container orchestration. / **健康监控**: 内置健康检查端点，支持容器编排。
- **API Documentation**: Interactive Swagger UI at `/docs` endpoint. / **API文档**: 交互式Swagger UI文档位于 `/docs` 端点。
- **Rate Limiting**: Built-in rate limiting to prevent abuse (100 requests/minute globally, 50/minute per endpoint). / **速率限制**: 内置速率限制防止滥用（全局100请求/分钟，单端点50/分钟）。
- **Metrics Endpoint**: Performance and config metrics at `/metrics`. / **指标端点**: 性能和配置指标位于 `/metrics`。
- **Developer Tools**: Makefile for common tasks, pre-commit hooks, and comprehensive testing. / **开发工具**: Makefile简化常用命令，pre-commit钩子，完整测试套件。

## Requirements / 环境要求

### For Docker Deployment / Docker 部署
- Docker 20.10+
- Docker Compose (optional / 可选)

### For Local Development / 本地开发
- Python 3.13+
- pip 23.0+

## Quick Start / 快速开始

### Method 1: Docker (Recommended / 推荐)

#### 1. Build the Image / 构建镜像

```bash
docker build -t qr-service .
```

#### 2. Run the Service / 启动服务

**Default Port / 默认端口 (8080):**
```bash
docker run -d -p 8080:8080 --name qr-service qr-service
```

**Custom Port / 自定义端口 (e.g., 9090):**
```bash
docker run -d -p 9090:9090 -e PORT=9090 --name qr-service-custom qr-service
```

#### 3. Verify Service is Running / 验证服务运行

```bash
curl http://localhost:8080/health
# Expected output: OK
```

### Method 2: Docker Compose

```bash
docker-compose up -d
```

### Method 3: Local Python

```bash
# Install dependencies / 安装依赖
pip install -r requirements.txt

# Run the service / 运行服务
python main.py

# Or with gunicorn / 或使用 gunicorn
gunicorn --bind 0.0.0.0:8080 main:app
```

## Usage / 使用方法

Access the service via HTTP request from your browser, command line, or application.
通过浏览器、命令行或您的应用程序发送 HTTP 请求。

### API Documentation / API文档

Interactive Swagger UI is available at:
交互式Swagger UI文档位于：

```
http://localhost:8080/docs
```

### Health Check / 健康检查

```bash
curl http://localhost:8080/health
```

### Metrics / 指标

Get service metrics and configuration:
获取服务指标和配置：

```bash
curl http://localhost:8080/metrics
```

**Response:**
```json
{
  "status": "healthy",
  "version": "0.0.6",
  "config": {
    "max_content_length": 1000,
    "rate_limit": "100 per minute",
    "allowed_types": ["qrcode", "barcode"]
  }
}
```

### Generate QR Code (Default) / 生成二维码 (默认)

```http
GET http://localhost:8080/generate?content=<YOUR_CONTENT>
```

**Example / 示例:**

```bash
# Simple text / 简单文本
curl "http://localhost:8080/generate?content=Hello World" > qrcode.png

# Order ID / 订单号
curl "http://localhost:8080/generate?content=ORD-2023-001" > qrcode.png

# URL / 网址
curl "http://localhost:8080/generate?content=https://example.com" > qrcode.png

# Explicit type / 显式指定类型
curl "http://localhost:8080/generate?content=Hello&type=qrcode" > qrcode.png
```

### Generate Barcode / 生成条形码

```http
GET http://localhost:8080/generate?content=<YOUR_CONTENT>&type=barcode
```

**Example / 示例:**

```bash
# Alphanumeric content (Code128) / 字母数字内容
curl "http://localhost:8080/generate?content=ABC123&type=barcode" > barcode.png

# Numbers only / 仅数字
curl "http://localhost:8080/generate?content=123456789&type=barcode" > barcode.png
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
pip install -r requirements-dev.txt

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
     -p 8080:8080 \
     -e PORT=8080 \
     -e DEBUG=false \
     --name qr-service \
     qr-service
   ```

2. **Resource Limits / 资源限制**
   ```bash
   docker run -d \
     -p 8080:8080 \
     --memory="256m" \
     --cpus="0.5" \
     --name qr-service \
     qr-service
   ```

3. **Restart Policy / 重启策略**
   ```bash
   docker run -d \
     -p 8080:8080 \
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
lsof -ti:8080 | xargs kill -9
```

### "Barcode content must be alphanumeric" error / 条形码内容必须是字母数字错误

Barcodes (Code128) only support alphanumeric characters. Remove special characters like `-`, `_`, spaces, etc.

条形码（Code128）仅支持字母和数字。请移除特殊字符如 `-`、`_`、空格等。

```bash
# Wrong / 错误
curl "http://localhost:8080/generate?content=ABC-123&type=barcode"

# Correct / 正确
curl "http://localhost:8080/generate?content=ABC123&type=barcode"
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
- **Logging**: All requests and errors are logged

## Configuration / 配置

Environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PORT` | `8080` | Server port |
| `DEBUG` | `False` | Enable Flask debug mode (not for production) |

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

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## Support / 支持

For issues and feature requests, please create an issue on GitHub.

如有问题或功能请求，请在 GitHub 上创建 issue。

---

Made with ❤️ using Flask, qrcode, and python-barcode
