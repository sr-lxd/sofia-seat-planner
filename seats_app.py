"""早期单文件版本的遗留入口，保留原有命令行用法。

这个文件原本自带一份排座代码，在应用改成蓝图结构后就与 templates/ 不匹配了：
模板里的 url_for 指向 seats.* 端点，而本文件用 @app.route 注册的是顶层端点，
直接运行会报 BuildError。

现在改为指向真正的应用（seats_bp/routes.py），两种启动方式等价：

    python app.py
    python seats_app.py

新项目请直接使用 app.py。
"""
import os

from app import app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("SEATS_PORT", "5039")), debug=False)
