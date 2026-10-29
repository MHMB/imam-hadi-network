/**
 * Layout for the loan-flow view: lenders (right) → borrower (centre) →
 * repayments by due month (left). Pure geometry so it can be tested; the
 * component only draws what this returns. Band thickness ∝ amount.
 *
 * Real loans range from 1 lender / 1 installment to ~110 lenders / ~180
 * installments, so lenders beyond the top 6 fold into one «سایر» group and
 * installments are bucketed by due month.
 */

import { daysFromToday, isPastDue, type JalaliTriple } from "@/lib/jalali";

export type FlowInstallment = {
  y: number;
  m: number;
  d: number;
  amount: number;
  paid: boolean;
};
export type FlowLenderInput = {
  id: number;
  name: string;
  amount: number;
  installments: FlowInstallment[];
};
export type SegStatus = "paid" | "late" | "next";

export type FlowGroup = {
  key: string;
  personId: number | null; // null for the folded «سایر» group
  name: string;
  members: number;
  color: string;
  amount: number;
  paid: number;
  late: number;
  remaining: number;
  y: number;
  h: number;
};
export type FlowMonth = {
  key: string;
  y: number;
  h: number;
  jy: number;
  jm: number;
  amount: number;
  count: number;
  state: SegStatus;
  days: number; // days late (state=late) or days left (state=next)
};
export type FlowBand = { d: string; group: number; status?: SegStatus };

export type FlowLayout = {
  width: number;
  height: number;
  groups: FlowGroup[];
  months: FlowMonth[];
  inflows: FlowBand[];
  outflows: FlowBand[];
  borrower: { x: number; y: number; w: number; h: number };
  todayY: number | null;
};

export const FLOW = {
  width: 1120,
  top: 56,
  lenderX: 860,
  lenderW: 220,
  borrowerX: 470,
  borrowerW: 180,
  monthX: 40,
  monthW: 250,
  borrowerH: 280,
  lenderMinH: 64,
  monthMinH: 44,
  maxGroups: 7,
} as const;

// Distinct hue AND lightness so lenders stay apart without relying on hue alone.
export const LENDER_COLORS = ["#2563EB", "#7C3AED", "#0E7490", "#B45309", "#BE185D", "#4D7C0F"];
const OTHERS_COLOR = "#475569";
const STATUS_ORDER: SegStatus[] = ["paid", "late", "next"];

const band = (x1: number, a0: number, a1: number, x2: number, b0: number, b1: number) => {
  const mx = (x1 + x2) / 2;
  return `M${x1},${a0} C${mx},${a0} ${mx},${b0} ${x2},${b0} L${x2},${b1} C${mx},${b1} ${mx},${a1} ${x1},${a1} Z`;
};

export function buildFlow(lenders: FlowLenderInput[], today: JalaliTriple): FlowLayout {
  // --- lender groups: top 6 by amount, the rest folded into «سایر» ---
  const sorted = [...lenders].sort((a, b) => b.amount - a.amount);
  const fold = sorted.length > FLOW.maxGroups;
  const heads = fold ? sorted.slice(0, FLOW.maxGroups - 1) : sorted;
  const tail = fold ? sorted.slice(FLOW.maxGroups - 1) : [];
  const groupOf = new Map<number, number>();
  const members: FlowLenderInput[][] = heads.map((l, i) => {
    groupOf.set(l.id, i);
    return [l];
  });
  if (tail.length) {
    tail.forEach((l) => groupOf.set(l.id, heads.length));
    members.push(tail);
  }

  const lenderSum = lenders.reduce((acc, l) => acc + l.amount, 0);
  const schedSum = lenders.reduce(
    (acc, l) => acc + l.installments.reduce((s, i) => s + i.amount, 0),
    0,
  );
  const unit = FLOW.borrowerH / Math.max(lenderSum, schedSum, 1e-9);

  let cursor: number = FLOW.top;
  const groups: FlowGroup[] = members.map((ms, gi) => {
    const amount = ms.reduce((acc, l) => acc + l.amount, 0);
    let paid = 0;
    let late = 0;
    let unpaid = 0;
    ms.forEach((l) =>
      l.installments.forEach((i) => {
        if (i.paid) paid += i.amount;
        else {
          unpaid += i.amount;
          if (isPastDue(i.y, i.m, i.d, today)) late += i.amount;
        }
      }),
    );
    const others = gi === heads.length && tail.length > 0;
    const h = Math.max(amount * unit, FLOW.lenderMinH);
    const g: FlowGroup = {
      key: others ? "others" : String(ms[0].id),
      personId: others ? null : ms[0].id,
      name: others ? "سایر" : ms[0].name,
      members: ms.length,
      color: others ? OTHERS_COLOR : LENDER_COLORS[gi % LENDER_COLORS.length],
      amount,
      paid,
      late,
      remaining: unpaid,
      y: cursor,
      h,
    };
    cursor += h + 12;
    return g;
  });
  const lendersBottom = cursor - 12;

  const borrower = {
    x: FLOW.borrowerX,
    y: FLOW.top + 10,
    w: FLOW.borrowerW,
    h: FLOW.borrowerH,
  };

  // --- inflows: lender node (centred) → borrower right edge (stacked) ---
  let bIn = borrower.y;
  const inflows: FlowBand[] = groups.map((g, gi) => {
    const t = g.amount * unit;
    const a0 = g.y + (g.h - t) / 2;
    const d = band(FLOW.lenderX, a0, a0 + t, borrower.x + borrower.w, bIn, bIn + t);
    bIn += t;
    return { d, group: gi };
  });

  // --- months: bucket installments by due (year, month) ---
  type Bucket = {
    jy: number;
    jm: number;
    count: number;
    amount: number;
    firstLate: [number, number, number] | null;
    firstOpen: [number, number, number] | null;
    minDay: number;
    seg: Map<string, number>; // `${group}|${status}` → amount
  };
  const buckets = new Map<string, Bucket>();
  lenders.forEach((l) =>
    l.installments.forEach((i) => {
      const k = `${i.y}-${String(i.m).padStart(2, "0")}`;
      const b =
        buckets.get(k) ??
        ({
          jy: i.y,
          jm: i.m,
          count: 0,
          amount: 0,
          firstLate: null,
          firstOpen: null,
          minDay: 31,
          seg: new Map(),
        } as Bucket);
      const status: SegStatus = i.paid ? "paid" : isPastDue(i.y, i.m, i.d, today) ? "late" : "next";
      b.count += 1;
      b.amount += i.amount;
      b.minDay = Math.min(b.minDay, i.d);
      if (status === "late" && (!b.firstLate || i.d < b.firstLate[2]))
        b.firstLate = [i.y, i.m, i.d];
      if (status === "next" && (!b.firstOpen || i.d < b.firstOpen[2]))
        b.firstOpen = [i.y, i.m, i.d];
      const sk = `${groupOf.get(l.id) ?? 0}|${status}`;
      b.seg.set(sk, (b.seg.get(sk) ?? 0) + i.amount);
      buckets.set(k, b);
    }),
  );
  const ordered = [...buckets.entries()].sort(([a], [b]) => (a < b ? -1 : 1));

  const months: FlowMonth[] = [];
  const outflows: FlowBand[] = [];
  let mCursor: number = FLOW.top;
  let bOut = borrower.y;
  let todayY: number | null = null;
  ordered.forEach(([key, b], idx) => {
    // The today line sits before the first month that is not yet due.
    if (todayY === null && !isPastDue(b.jy, b.jm, b.minDay, today)) {
      if (idx > 0) {
        todayY = mCursor + 4;
        mCursor += 18;
      } else todayY = FLOW.top - 14;
    }
    const t = b.amount * unit;
    const h = Math.max(t, FLOW.monthMinH);
    const state: SegStatus = b.firstLate ? "late" : b.firstOpen ? "next" : "paid";
    const ref = b.firstLate ?? b.firstOpen;
    const days = ref ? Math.abs(daysFromToday(ref[0], ref[1], ref[2], today)) : 0;
    months.push({
      key,
      y: mCursor,
      h,
      jy: b.jy,
      jm: b.jm,
      amount: b.amount,
      count: b.count,
      state,
      days,
    });

    let mOut = mCursor + (h - t) / 2;
    groups.forEach((_, gi) =>
      STATUS_ORDER.forEach((status) => {
        const amt = b.seg.get(`${gi}|${status}`);
        if (!amt) return;
        const tt = amt * unit;
        outflows.push({
          d: band(borrower.x, bOut, bOut + tt, FLOW.monthX + FLOW.monthW, mOut, mOut + tt),
          group: gi,
          status,
        });
        bOut += tt;
        mOut += tt;
      }),
    );
    mCursor += h + 10;
  });
  const monthsBottom = mCursor - 10;

  const height = Math.ceil(
    Math.max(lendersBottom, monthsBottom, borrower.y + borrower.h + 70, todayY ?? 0) + 24,
  );
  return { width: FLOW.width, height, groups, months, inflows, outflows, borrower, todayY };
}
