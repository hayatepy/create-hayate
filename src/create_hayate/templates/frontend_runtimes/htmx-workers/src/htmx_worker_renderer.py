"""Jinja renderer for the template snapshot attached to a Python Worker."""

from collections.abc import Mapping

from jinja2 import DictLoader, Environment, select_autoescape

from htmx_worker_templates import TEMPLATES


class EmbeddedJinjaRenderer:
    def __init__(self) -> None:
        self.environment = Environment(
            loader=DictLoader(TEMPLATES),
            autoescape=select_autoescape(
                enabled_extensions=("html", "htm", "xml"),
                default_for_string=True,
                default=True,
            ),
        )

    async def render(
        self,
        template_name: str,
        context: Mapping[str, object],
    ) -> str:
        return self.environment.get_template(template_name).render(context)
