import { describe, expect, it } from "vitest";

import { fmtJalaliDate, fmtMoneyMT, fmtMoneyToman, toPersianDigits } from "@/lib/format";

describe("toPersianDigits", () => {
  it("maps western digits to Persian", () => {
    expect(toPersianDigits("123")).toBe("۱۲۳");
    expect(toPersianDigits(0)).toBe("۰");
  });

  it("leaves non-digits untouched", () => {
    expect(toPersianDigits("a1b2")).toBe("a۱b۲");
  });
});

describe("fmtMoneyMT", () => {
  it("formats integer millions", () => {
    expect(fmtMoneyMT(20)).toMatch(/میلیون تومان$/);
    expect(fmtMoneyMT(20)).toContain("۲۰");
  });

  it("preserves fractional millions", () => {
    const out = fmtMoneyMT(5.5);
    expect(out).toContain("۵");
    expect(out).toMatch(/میلیون تومان$/);
  });
});

describe("fmtMoneyToman", () => {
  it("expands millions to raw toman", () => {
    expect(fmtMoneyToman(5)).toContain("۵٬۰۰۰٬۰۰۰");
  });
});

describe("fmtJalaliDate", () => {
  it("zero-pads month/day and Persianizes digits", () => {
    expect(fmtJalaliDate(1404, 6, 15)).toBe("۱۴۰۴/۰۶/۱۵");
  });
});
