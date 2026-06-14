"""Error hierarchy for okf-tools."""


class OkfError(Exception):
    """Base error for all okf-tools operations."""


class ConceptNotFoundError(OkfError):
    """Raised when a concept_id doesn't map to an existing file."""

    def __init__(self, concept_id: str):
        self.concept_id = concept_id
        super().__init__(f"Concept not found: {concept_id}")


class ValidationError(OkfError):
    """Raised when frontmatter or input fails validation."""

    def __init__(self, errors: "list[str]"):
        self.errors = errors
        super().__init__(f"Validation failed: {'; '.join(errors)}")


class IndexCorruptionError(OkfError):
    """Raised when the vector index is unreadable or corrupted."""

    def __init__(self, path: str = ""):
        self.path = path
        msg = "Index corrupted"
        if path:
            msg += f" at {path}"
        msg += ". Run `okf reindex --full` to rebuild."
        super().__init__(msg)


class BundleAlreadyInitialisedError(OkfError):
    """Raised when okf init is run in an already-initialised directory."""

    def __init__(self):
        super().__init__("Bundle already initialised (.okf/config.json exists)")


class ConfigError(OkfError):
    """Raised when configuration is invalid or unparseable."""

    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Config error in {path}: {reason}")


class ParseError(OkfError):
    """Raised when a concept file cannot be parsed."""

    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Parse error in {path}: {reason}")
