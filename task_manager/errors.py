"""Errors that callers can handle without depending on SQLite internals."""


class ConflictError(Exception):
    """A task changed after the caller's snapshot was loaded."""


class SchemaError(Exception):
    """A database schema is incompatible with this application version."""
