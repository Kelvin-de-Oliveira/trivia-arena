import logging
import logging.config

# Formato: timestamp  [LEVEL   ]  nome.do.logger: mensagem
_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

LOGGING_CONFIG: dict = {
    "version": 1,
    # False = não desativa loggers criados antes de chamar dictConfig
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": _FORMAT,
            "datefmt": _DATE_FORMAT,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}


def setup_logging() -> None:
    """Aplica a configuração de logging definida em LOGGING_CONFIG."""
    logging.config.dictConfig(LOGGING_CONFIG)