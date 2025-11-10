import logging
from pathlib import Path
from datetime import datetime

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class LazyFileHandler(logging.Handler):
    def __init__(self, log_dir: Path, level: int = logging.ERROR):
        super().__init__(level)
        self.log_dir = log_dir
        self.file_handler = None
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def emit(self, record):
        if self.file_handler is None:
            self.log_dir.mkdir(exist_ok=True)
            error_log_file = self.log_dir / f"registry_errors_{self.timestamp}.log"
            self.file_handler = logging.FileHandler(error_log_file, encoding="utf-8")
            self.file_handler.setLevel(self.level)
            self.file_handler.setFormatter(self.formatter)
            logging.info(f"Error log file created: {error_log_file}")

        self.file_handler.emit(record)

    def close(self):
        if self.file_handler:
            self.file_handler.close()
        super().close()


def setup_logging(log_dir: Path | None = None, level: int = logging.INFO) -> None:
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / "logs"

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if root_logger.handlers:
        root_logger.handlers.clear()

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    lazy_error_handler = LazyFileHandler(log_dir, level=logging.ERROR)
    lazy_error_handler.setFormatter(formatter)
    root_logger.addHandler(lazy_error_handler)

    logging.info("Logging initialized. Error logs will be created on first error.")
