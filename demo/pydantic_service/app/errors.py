"""Maps pydantic validation errors to the stable codes our public API returns."""
from pydantic import ValidationError

_API_CODES = {
    "value_error.missing": "required",
    "type_error.integer": "not_integer",
    "value_error.any_str.min_length": "too_short",
    "value_error.number.not_ge": "too_small",
    "value_error.str.regex": "bad_format",
}


def api_errors(exc: ValidationError) -> list:
    """Return ['<field path>:<api code>', ...] for a validation error."""
    out = []
    for err in exc.errors():
        path = ".".join(str(p) for p in err["loc"])
        out.append(f"{path}:{_API_CODES.get(err['type'], 'invalid')}")
    return out
