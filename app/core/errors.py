"""Domain errors."""


class NotFound(Exception):
    pass


class DuplicateDocument(Exception):
    def __init__(self, existing_id: str):
        super().__init__("duplicate document")
        self.existing_id = existing_id


class AuthError(Exception):
    pass
