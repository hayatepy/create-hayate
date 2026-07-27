"""Autoescaping Jinja renderer for :mod:`hayate_htmx.templates`."""

from __future__ import annotations

from collections.abc import Mapping
from os import PathLike

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape


class TemplateNotFoundError(LookupError):
    """A named page or fragment template could not be loaded."""

    def __init__(self, template_name: str) -> None:
        self.template_name = template_name
        super().__init__(f"template not found: {template_name}")


class JinjaRenderer:
    """Render named files from a directory with HTML autoescaping enabled."""

    def __init__(
        self,
        directory: str | PathLike[str],
        *,
        enable_async: bool = False,
    ) -> None:
        self.environment = Environment(
            loader=FileSystemLoader(directory),
            autoescape=select_autoescape(
                enabled_extensions=("html", "htm", "xml"),
                default_for_string=True,
                default=True,
            ),
            enable_async=enable_async,
        )

    async def render(
        self,
        template_name: str,
        context: Mapping[str, object],
    ) -> str:
        """Render one template and normalize Jinja's missing-template error."""
        try:
            template = self.environment.get_template(template_name)
            if self.environment.is_async:
                return await template.render_async(context)
            return template.render(context)
        except TemplateNotFound as exc:
            missing_name = exc.name if isinstance(exc.name, str) else template_name
            raise TemplateNotFoundError(missing_name) from exc
