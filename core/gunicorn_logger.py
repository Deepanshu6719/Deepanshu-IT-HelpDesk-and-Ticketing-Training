import logging

from gunicorn.glogging import Logger

from core.logging import configure_logging


class JSONGunicornLogger(Logger):
    def setup(self, cfg):
        super().setup(cfg)

        configure_logging()

        self.error_log = logging.getLogger("gunicorn.error")

        self.access_log = logging.getLogger("gunicorn.access")
