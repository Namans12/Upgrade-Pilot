"""Maps pydantic validation errors to the stable codes our public API returns."""
from pydantic import ValidationError

_API_CODES = {
    "missing": "required",
    "int_parsing": "not_integer",
    "string_too_short": "too_short",
    "greater_than_equal": "too_small",
    "string_pattern_mismatch": "bad_format",
}


def api_errors(exc: ValidationError) -> list:
    """Return ['<field path>:<api code>', ...] for a validation error."""
    out = []
    for err in exc.errors():
        path = ".".join(str(p) for p in err["loc"])
        out.append(f"{path}:{_API_CODES.get(err['type'], 'invalid')}")
    return out
