# Third-Party Notices / 第三方声明

This project is MIT-licensed (see [LICENSE](LICENSE)). It ships or depends on the third-party
software below, each under its own license. All of them are permissive; none is copyleft.
CI fails if a GPL/AGPL/LGPL/SSPL package appears in the runtime image (`scripts/check_licenses.py`).

本项目采用 MIT 许可证。下列第三方软件各自适用其许可证，均为宽松许可，无传染性（copyleft）许可证。

## Vendored in this repository / 仓库内随附

| Component | Version | License | Files |
| :--- | :--- | :--- | :--- |
| [Swagger UI](https://github.com/swagger-api/swagger-ui) (`swagger-ui-dist`) | 5.33.1 | Apache-2.0 | `static/vendor/swagger-ui-5.33.1/` — `LICENSE`, `NOTICE`, and `swagger-ui-bundle.js.LICENSE.txt` for the libraries bundled inside it (React, DOMPurify, Immutable, etc.: MIT / BSD / Apache-2.0) |

The vendored files are byte-identical to the npm release `swagger-ui-dist@5.33.1`.
Served at `/docs`, so the license files are also served next to them.

## Runtime dependencies (Docker image) / 运行时依赖

Pinned in `requirements.txt`.

| Package | License |
| :--- | :--- |
| Flask, Werkzeug, Jinja2, MarkupSafe, itsdangerous, click | BSD-3-Clause |
| blinker | MIT |
| Flask-Limiter, limits | MIT |
| gunicorn | MIT |
| qrcode | BSD |
| python-barcode | MIT |
| Pillow | MIT-CMU (HPND) |
| Deprecated | MIT |
| wrapt | BSD-2-Clause |
| ordered-set | MIT |
| packaging | Apache-2.0 OR BSD-2-Clause |
| typing-extensions | PSF-2.0 |

`python-barcode` bundles the **DejaVu Sans Mono** font (Bitstream Vera license / public domain
changes) to draw the text under barcodes. The font may be redistributed; its copyright notice is
embedded in the font file.

Images produced by this service carry no license restrictions from these libraries.
本服务生成的图片不受上述库的许可证约束。

## Trademarks / 商标

- **QR Code** is a registered trademark of DENSO WAVE INCORPORATED. / QR Code 是 DENSO WAVE INCORPORATED 的注册商标。
- **Swagger** is a trademark of SmartBear Software, Inc. This project uses Swagger UI under its license and is not affiliated with or endorsed by SmartBear.
- **OpenAPI** is a trademark of The Linux Foundation (OpenAPI Initiative). This project is not affiliated with it.
