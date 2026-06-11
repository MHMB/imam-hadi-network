import { describe, expect, it } from "vitest";

import { isFutureMonth, isPastDue, todayJalali } from "./jalali";

const TODAY = { jy: 1405, jm: 3, jd: 21 }; // خرداد ۱۴۰۵

describe("isFutureMonth", () => {
  it("flags months after the current one", () => {
    expect(isFutureMonth(1405, 4, TODAY)).toBe(true); // تیر ۱۴۰۵
    expect(isFutureMonth(1406, 1, TODAY)).toBe(true);
  });

  it("keeps the current and past months non-future", () => {
    expect(isFutureMonth(1405, 3, TODAY)).toBe(false); // the current month itself
    expect(isFutureMonth(1405, 2, TODAY)).toBe(false);
    expect(isFutureMonth(1404, 12, TODAY)).toBe(false);
  });
});

describe("isPastDue", () => {
  it("is true strictly before today", () => {
    expect(isPastDue(1405, 3, 20, TODAY)).toBe(true);
    expect(isPastDue(1404, 12, 29, TODAY)).toBe(true);
    expect(isPastDue(1402, 12, 30, TODAY)).toBe(true); // impossible legacy date still compares
  });

  it("is false today and after", () => {
    expect(isPastDue(1405, 3, 21, TODAY)).toBe(false); // due today ≠ overdue
    expect(isPastDue(1405, 3, 22, TODAY)).toBe(false);
    expect(isPastDue(1406, 1, 1, TODAY)).toBe(false);
  });
});

describe("todayJalali", () => {
  it("returns a sane triple", () => {
    const t = todayJalali();
    expect(t.jy).toBeGreaterThan(1400);
    expect(t.jm).toBeGreaterThanOrEqual(1);
    expect(t.jm).toBeLessThanOrEqual(12);
    expect(t.jd).toBeGreaterThanOrEqual(1);
    expect(t.jd).toBeLessThanOrEqual(31);
  });
});
