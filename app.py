"""Sofia 座位分配系统 —— 本机启动入口。

只监听本机回环地址 127.0.0.1，局域网内其他设备无法访问。

启动：
    python app.py

环境变量：
    SEATS_PORT        监听端口，默认 5039
    SEATS_SECRET_KEY  会话密钥；不设置时每次启动随机生成
"""
import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from flask import Flask

HOST = "127.0.0.1"
DEFAULT_PORT = "5039"

project_dir = Path(__file__).resolve().parent

# 按文件路径加载本目录下的包，而不是靠 import seats_bp。
# 目录名取决于仓库克隆成什么名字，用包名导入会在改名后失效。
_spec = spec_from_file_location(
    "seats_bp",
    project_dir / "__init__.py",
    submodule_search_locations=[str(project_dir)],
)
_package = module_from_spec(_spec)
sys.modules["seats_bp"] = _package
_spec.loader.exec_module(_package)


def create_app():
    app = Flask(__name__)
    # 不设置时用每次启动随机的密钥：重启会让已有会话失效，教室场景下无影响。
    app.secret_key = os.environ.get("SEATS_SECRET_KEY") or os.urandom(32)
    app.register_blueprint(_package.seats_bp, url_prefix="/seats")
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=HOST, port=int(os.environ.get("SEATS_PORT", DEFAULT_PORT)), debug=False)
