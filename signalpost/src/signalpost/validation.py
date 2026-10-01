"""Validation for Norwegian organisation numbers (organisasjonsnummer)."""

from __future__ import annotations

import re


class OrganisationNumberError(ValueError):
    """Raised when a value is not a valid Norwegian organisation number."""


def normalize_organisation_number(value: object) -> str:
    """Return the nine-digit representation, accepting ordinary display spacing."""

    if isinstance(value, bool) or value is None:
        raise OrganisationNumberError("organisation number must be a string of nine digits")
    text = str(value).strip().replace(" ", "").replace(".", "")
    if not re.fullmatch(r"\d{9}", text):
        raise OrganisationNumberError("organisation number must contain exactly nine digits")
    return text


def validate_organisation_number(value: object) -> str:
    """Validate length, digits, and the official Norwegian modulus-11 check digit."""

    number = normalize_organisation_number(value)
    weights = (3, 2, 7, 6, 5, 4, 3, 2)
    remainder = sum(int(digit) * weight for digit, weight in zip(number[:8], weights)) % 11
    check_digit = 11 - remainder
    if check_digit == 11:
        check_digit = 0
    if check_digit == 10 or check_digit != int(number[-1]):
        raise OrganisationNumberError("organisation number has an invalid modulus-11 check digit")
    return number
