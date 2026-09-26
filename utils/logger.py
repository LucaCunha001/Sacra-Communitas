import logging
from pathlib import Path


def setup_logging(level: str = "INFO") -> None:
	root_logger = logging.getLogger()
	root_logger.setLevel(logging.DEBUG)
	root_logger.handlers.clear()

	formatter = logging.Formatter(
		"[%(asctime)s] %(levelname)s %(name)s: %(message)s",
		datefmt="%Y-%m-%d %H:%M:%S",
	)

	console_handler = logging.StreamHandler()
	console_handler.setLevel(level)
	console_handler.setFormatter(formatter)
	root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
	return logging.getLogger(name)
