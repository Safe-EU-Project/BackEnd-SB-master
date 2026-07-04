import logging

logger = logging.getLogger("app_logger")
logger.setLevel(logging.INFO)
logger.propagate = False

file_handler = logging.FileHandler("app.log", mode="a", encoding="utf-8")
console_handler = logging.StreamHandler()

formatter = logging.Formatter(
    fmt="[{asctime}] {levelname}: {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
)

file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.DEBUG)

logger.addHandler(file_handler)
logger.addHandler(console_handler)
