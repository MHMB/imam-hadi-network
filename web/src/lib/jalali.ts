/**
 * Client-side Jalali "today" helpers.
 *
 * Time-aware UI (overdue badges, the circulation chart's red bars) must
 * distinguish past-due from merely-scheduled. The schedule data extends
 * more than a year past today — e.g. a loan written in اسفند repays well
 * into the next year — so "unpaid" alone says nothing about lateness.
 *
 * Uses the browser clock (the admins' local time), converted via
 * jalaali-js — the same library the imports page already uses.
 */

import jalaali from "jalaali-js";

export type JalaliTriple = { jy: number; jm: number; jd: number };

export function todayJalali(): JalaliTriple {
  const now = new Date();
  return jalaali.toJalaali(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

/** Is the Jalali (year, month) strictly after today's month? */
export function isFutureMonth(year: number, month: number, today: JalaliTriple): boolean {
  return year > today.jy || (year === today.jy && month > today.jm);
}

/** Is the Jalali (year, month, day) due date strictly before today? */
export function isPastDue(year: number, month: number, day: number, today: JalaliTriple): boolean {
  if (year !== today.jy) return year < today.jy;
  if (month !== today.jm) return month < today.jm;
  return day < today.jd;
}
