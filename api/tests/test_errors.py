from app.errors import persian_numbers


def test_persian_numbers_trims_and_localises() -> None:
    assert persian_numbers("مانده (1.833)") == "مانده (۱٫۸۳۳)"
    assert persian_numbers("0.800 میلیون") == "۰٫۸ میلیون"
    assert persian_numbers("10.000 قسط") == "۱۰ قسط"
    assert persian_numbers("تاریخ 1405/12/31.") == "تاریخ ۱۴۰۵/۱۲/۳۱."
