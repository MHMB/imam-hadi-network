/**
 * Persian number, money, and Jalali date formatters.
 *
 * Stored values are western digits; rendered values default to Persian digits.
 * Money values are in **million toman** (numeric(18,3) in DB).
 */

const PERSIAN_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"] as const;

export function toPersianDigits(input: string | number): string {
  return String(input).replace(/[0-9]/g, (d) => PERSIAN_DIGITS[Number(d)]);
}

/** "5.5 million toman" → `۵٫۵ میلیون تومان`. */
export function fmtMoneyMT(amountMillionToman: number): string {
  const fmt = new Intl.NumberFormat("fa-IR", {
    maximumFractionDigits: 3,
  });
  return `${fmt.format(amountMillionToman)} میلیون تومان`;
}

/** Raw toman, with thousands separator — used in tooltips. */
export function fmtMoneyToman(amountMillionToman: number): string {
  const raw = Math.round(amountMillionToman * 1_000_000);
  const fmt = new Intl.NumberFormat("fa-IR");
  return `${fmt.format(raw)} تومان`;
}

/** `۱۴۰۴/۰۶/۱۵` from a triple. */
export function fmtJalaliDate(year: number, month: number, day: number): string {
  const pad = (n: number) => toPersianDigits(String(n).padStart(2, "0"));
  return `${toPersianDigits(year)}/${pad(month)}/${pad(day)}`;
}

/** Real phone or null.  ~700 auto-created persons carry synthetic
 * placeholder phones (`+0__<hash>`) — those must never reach the screen. */
export function displayPhone(phone: string): string | null {
  if (!phone || phone.startsWith("+0__")) return null;
  return toPersianDigits(phone);
}
