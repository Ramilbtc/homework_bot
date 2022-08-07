class APIUnexpectedHTTPStatus(Exception):
    """Исключение при ответе сервера отличным от 200."""

    pass


class APIRequestError(Exception):
    """Исключение в запросе API."""

    pass


class HomeworkListEmptyError(Exception):
    """Исключение при запросе пустого списка домашних работ."""

    pass


class HomeworkStatusError(Exception):
    """Исключение в статусе домашних работ."""

    pass
