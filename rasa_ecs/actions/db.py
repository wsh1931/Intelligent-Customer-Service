# pip install pymysql sqlacodegen
import subprocess
import urllib.parse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 创建数据库引擎
db_host = "localhost"
db_port = 3306
db_name = "rasa_ecs"
db_user_name = "root"
db_password = "@Uuwusihao1931"

# 对用户名和密码进行URL编码以处理特殊字符
encoded_user_name = urllib.parse.quote_plus(db_user_name)
encoded_password = urllib.parse.quote_plus(db_password)
url = f"mysql+pymysql://{encoded_user_name}:{encoded_password}@{db_host}:{db_port}/{db_name}?charset=utf8"

# 验证URL格式
print(f"Database URL: {url}")

# 配置会话工厂
engine = create_engine(url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def export_db_table_class():
    """将数据库表映射为Python类"""
    output_path = "db_table_class.py"

    cmd = ["python", "-m", "sqlacodegen", url]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode == 0:  # 检查命令是否成功执行
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result.stdout)
        print(f"数据库表类已成功生成到 {output_path}")
    else:
        print(f"生成失败: {result.stderr}")


if __name__ == "__main__":
    export_db_table_class()
