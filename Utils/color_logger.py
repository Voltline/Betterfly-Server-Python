import logging
import sys


class Color:
    """定义日志颜色"""
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"


# 自定义日志处理器
class ColorHandler(logging.StreamHandler):
    def emit(self, record):
        log_entry = self.format(record)
        if record.levelno == logging.DEBUG:
            log_entry = f"{Color.BLUE}{log_entry}{Color.BLUE}"
        elif record.levelno == logging.INFO:
            log_entry = f"{Color.GREEN}{log_entry}{Color.END}"
        elif record.levelno == logging.WARNING:
            log_entry = f"{Color.YELLOW}{log_entry}{Color.END}"
        elif record.levelno == logging.ERROR:
            log_entry = f"{Color.RED}{log_entry}{Color.END}"
        sys.stdout.write(log_entry + "\n")
        sys.stdout.flush()


def get_logger(name: str, level=logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 添加自定义处理器
    color_handler = ColorHandler()
    # color_handler.setLevel(level)
    formatter = logging.Formatter("[%(asctime)s] - %(levelname)s - %(message)s")
    color_handler.setFormatter(formatter)
    logger.propagate = False
    logger.handlers.clear()
    logger.addHandler(color_handler)
    return logger
