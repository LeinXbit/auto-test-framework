import logging
import os
from datetime import datetime

def get_logger(name="auto_test"):
    """
    获取日志记录器（单例模式）
    :param name:
    :return:
    """

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 防止重复添加 Handler（单例保护）
    if logger.handlers:
        return logger

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 文件输出
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),"logs")
    os.makedirs(log_dir, exist_ok=True)    #自动创建 logs/ 目录

    log_file = os.path.join(
        log_dir,
        f"{datetime.now().strftime('%Y-%m-%d')}.log"
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # 统一格式
    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s",
                                  datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # 绑定到记录器
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger