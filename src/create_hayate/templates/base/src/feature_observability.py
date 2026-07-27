"""Safe cross-runtime request correlation and structured access logging."""

import logging

from hayate import Hayate
from hayate.middleware import RequestIdFilter, logger, request_id

request_log = logging.getLogger("$project_name.request")
request_log.setLevel(logging.INFO)
request_log.propagate = False

_handler = logging.StreamHandler()
_handler.addFilter(RequestIdFilter())
_handler.setFormatter(logging.Formatter("%(message)s"))
request_log.addHandler(_handler)


def register(app: Hayate) -> None:
    """Register observability before identity and every optional feature."""
    app.use(request_id())
    app.use(logger(request_log, structured=True))
