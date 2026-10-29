import { describe, expect, it } from "vitest";

import { buildFlow, type FlowLenderInput } from "./loan-flow";

const TODAY = { jy: 1405, jm: 8, jd: 7 }; // ۷ آبان ۱۴۰۵
const inst = (m: number, amount: number, paid: boolean) => ({ y: 1405, m, d: 1, amount, paid });

// The whiteboard example: 3 + 2 + 2 = 7, seven 1-unit installments.
const WHITEBOARD: FlowLenderInput[] = [
  {
    id: 1,
    name: "ساجد",
    amount: 3,
    installments: [inst(7, 1, true), inst(8, 1, true), inst(9, 1, false)],
  },
  { id: 2, name: "حسین", amount: 2, installments: [inst(8, 1, false), inst(10, 1, false)] },
  { id: 3, name: "محمدحسین", amount: 2, installments: [inst(7, 1, false), inst(11, 1, false)] },
];

describe("buildFlow", () => {
  it("buckets installments by month, oldest first, with status and days", () => {
    const f = buildFlow(WHITEBOARD, TODAY);
    expect(f.months.map((m) => `${m.jm}:${m.state}:${m.days}`)).toEqual([
      "7:late:36", // مهر: محمدحسین's unpaid one is late
      "8:late:6", // آبان: حسین's is late
      "9:next:24",
      "10:next:54",
      "11:next:84",
    ]);
  });

  it("splits each lender's money into paid / late / remaining", () => {
    const [sajed, hosein] = buildFlow(WHITEBOARD, TODAY).groups;
    expect([sajed.paid, sajed.late, sajed.remaining]).toEqual([2, 0, 1]);
    expect([hosein.paid, hosein.late, hosein.remaining]).toEqual([0, 1, 2]);
  });

  it("puts the today line between the last due month and the first future one", () => {
    const f = buildFlow(WHITEBOARD, TODAY);
    const aban = f.months[1];
    const azar = f.months[2];
    expect(f.todayY).toBeGreaterThan(aban.y + aban.h);
    expect(f.todayY).toBeLessThan(azar.y);
  });

  it("folds lenders beyond the top six into one «سایر» group", () => {
    const many: FlowLenderInput[] = Array.from({ length: 10 }, (_, i) => ({
      id: i + 1,
      name: `L${i + 1}`,
      amount: 10 - i,
      installments: [inst(9, 10 - i, false)],
    }));
    const f = buildFlow(many, TODAY);
    expect(f.groups).toHaveLength(7);
    const others = f.groups[6];
    expect([others.name, others.members, others.amount]).toEqual(["سایر", 4, 4 + 3 + 2 + 1]);
    // every unit of money still flows out: one band per (group, status) in the single month
    expect(f.outflows).toHaveLength(7);
  });
});
