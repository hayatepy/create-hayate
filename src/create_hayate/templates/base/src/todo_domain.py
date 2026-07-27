"""Todo input rules shared by JSON and hypermedia transports."""


class InvalidTodoTitle(ValueError):
    """A title failed the application-owned input contract."""


def normalize_title(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidTodoTitle("Enter a title before adding the task.")
    normalized = value.strip()
    if len(normalized) > 200:
        raise InvalidTodoTitle("Keep the title to 200 characters or fewer.")
    return normalized
