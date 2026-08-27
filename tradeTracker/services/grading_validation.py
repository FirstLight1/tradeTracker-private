from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from typing import Any, Iterable, Literal, overload

from tradeTracker.CONSTANTS import CENT


class ValidationError(ValueError):
    def __init__(self, errors: dict[str, str] | list[str] | str):
        if isinstance(errors, dict):
            self.errors = errors
            messages = list(errors.values())
        else:
            messages = [errors] if isinstance(errors, str) else errors
            self.errors = {"_form": "; ".join(messages)}
        super().__init__("; ".join(messages))


def normalize_text(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValidationError({field: f"{field} is required"})
        return None
    if not isinstance(value, str):
        raise ValidationError({field: f"{field} must be text"})
    normalized = " ".join(value.split())
    if not normalized:
        if required:
            raise ValidationError({field: f"{field} is required"})
        return None
    return normalized


@overload
def decimal_value(
    value: Any,
    field: str,
    *,
    nullable: Literal[False] = False,
    maximum: Decimal | None = None,
    decimal_places: int | None = None,
) -> Decimal: ...


@overload
def decimal_value(
    value: Any,
    field: str,
    *,
    nullable: Literal[True],
    maximum: Decimal | None = None,
    decimal_places: int | None = None,
) -> Decimal | None: ...


def decimal_value(
    value: Any,
    field: str,
    *,
    nullable: bool = False,
    maximum: Decimal | None = None,
    decimal_places: int | None = None,
) -> Decimal | None:
    if value is None:
        if nullable:
            return None
        raise ValidationError({field: f"{field} is required"})
    if isinstance(value, bool):
        raise ValidationError({field: f"{field} must be a number"})
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValidationError({field: f"{field} must be a number"}) from None
    if not result.is_finite():
        raise ValidationError({field: f"{field} must be finite"})
    if result < 0:
        raise ValidationError({field: f"{field} cannot be negative"})
    if maximum is not None and result > maximum:
        raise ValidationError({field: f"{field} cannot exceed {maximum}"})
    if decimal_places is not None:
        quantum = Decimal(1).scaleb(-decimal_places)
        try:
            quantized = result.quantize(quantum)
        except InvalidOperation:
            raise ValidationError(
                {field: f"{field} is outside the supported numeric range"}
            ) from None
        if result != quantized:
            raise ValidationError(
                {field: f"{field} can have at most {decimal_places} decimal places"}
            )
    return result


@overload
def money(value: Any, field: str, *, nullable: Literal[False] = False) -> Decimal: ...


@overload
def money(value: Any, field: str, *, nullable: Literal[True]) -> Decimal | None: ...


def money(value: Any, field: str, *, nullable: bool = False) -> Decimal | None:
    return decimal_value(value, field, nullable=nullable, decimal_places=2)


def grade_number(value: Any, field: str = "grade_numeric") -> Decimal | None:
    return decimal_value(value, field, nullable=True, maximum=Decimal("10"))


def normalize_date(value: Any, field: str, *, required: bool = False) -> str | None:
    if value is None or value == "":
        if required:
            raise ValidationError({field: f"{field} is required"})
        return None
    if isinstance(value, datetime):
        parsed: date | datetime = value
    elif isinstance(value, date):
        parsed = value
    elif isinstance(value, str):
        candidate = value.strip()
        if len(candidate) == 10:
            try:
                parsed = date.fromisoformat(candidate)
            except ValueError:
                raise ValidationError({field: f"{field} must be a valid ISO date"}) from None
        else:
            try:
                parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            except ValueError:
                raise ValidationError({field: f"{field} must be a valid ISO date"}) from None
    else:
        raise ValidationError({field: f"{field} must be a valid ISO date"})
    return parsed.isoformat()


def _chronology_value(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.combine(date.fromisoformat(value), datetime.min.time())
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def validate_chronology(submitted_at: str, returned_at: str) -> None:
    if _chronology_value(returned_at) < _chronology_value(submitted_at):
        raise ValidationError({"returned_at": "Returned date cannot be before submitted date"})


def allocate_largest_remainder(total: Decimal, weights: Iterable[Decimal]) -> list[Decimal]:
    total = Decimal(total)
    weight_list = [Decimal(weight) for weight in weights]
    try:
        valid_total = total.is_finite() and total >= 0 and total == total.quantize(CENT)
    except InvalidOperation:
        valid_total = False
    if not valid_total:
        raise ValidationError("allocation total must be nonnegative whole cents")
    if not weight_list:
        return []
    if any(not weight.is_finite() or weight < 0 for weight in weight_list):
        raise ValidationError("allocation weights must be finite and nonnegative")
    weight_total = sum(weight_list, Decimal("0"))
    if weight_total == 0:
        weight_list = [Decimal("1")] * len(weight_list)
        weight_total = Decimal(len(weight_list))
    exact = [total * weight / weight_total for weight in weight_list]
    allocated = [value.quantize(CENT, rounding=ROUND_DOWN) for value in exact]
    remaining = int((total - sum(allocated, Decimal("0"))) / CENT)
    order = sorted(
        range(len(exact)),
        key=lambda index: (exact[index] - allocated[index], -index),
        reverse=True,
    )
    for index in order[:remaining]:
        allocated[index] += CENT
    return allocated


def rounded_money(value: Decimal) -> Decimal:
    try:
        return value.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValidationError("Money value is outside the supported numeric range") from None
