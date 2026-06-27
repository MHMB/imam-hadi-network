/**
 * Persian (fa-IR) string catalog — single source of truth for UI copy.
 *
 * All visible UI text routes through this map.  No English in the rendered
 * DOM (DESIGN.md §6.4).  The canonical glossary is DESIGN.md §6.5; mirrored
 * below so devs see the Persian term next to the key without context-switching.
 *
 * Convention: keys are English camelCase identifiers.  Values are Persian.
 */
export const messages = {
  // --- App-level ---
  appTitle: "داشبورد شبکه قرض‌الحسنه امام هادی",
  appDescription: "نمایش وضعیت قرض‌ها، افراد و موضوعات",

  // --- Navigation (DESIGN §6.5 bottom-nav) ---
  navHome: "خانه",
  navPeople: "افراد",
  navLoans: "قرض‌ها",
  navTopics: "موضوعات",
  navAdmin: "مدیریت",

  // --- Generic states ---
  loading: "در حال بارگذاری...",
  empty: "موردی یافت نشد",
  error: "خطا در دریافت اطلاعات",
  retry: "تلاش دوباره",
  search: "جستجو",
  searchPlaceholder: "جستجو در نام، شماره تماس...",
  allYears: "همه سال‌ها",
  allStatuses: "همه وضعیت‌ها",
  allSeverities: "همه سطوح",
  allCategories: "همه دسته‌ها",

  // --- Person concepts ---
  person: "شخص",
  fullName: "نام و نام خانوادگی",
  phone: "شماره تماس",
  messenger: "پیامرسان",
  verified: "تأییدشده",
  guarantorMain: "ضامن اصلی",
  guarantorSecondary2: "ضامن دوم",
  guarantorSecondary3: "ضامن سوم",
  guarantorSecondary4: "ضامن چهارم",
  guarantorLoan: "ضامن قرض",

  // --- Loan concepts ---
  loan: "قرض",
  loanNumber: "شمارهٔ قرض",
  channelNumber: "شمارهٔ کانال",
  borrower: "قرض‌گیرنده",
  borrowers: "قرض‌گیرندگان",
  lender: "قرض‌دهنده",
  lenders: "قرض‌دهندگان",
  liaison: "رابط",
  topic: "موضوع",
  loanTotal: "مبلغ کل",
  amountLent: "مبلغ قرض‌داده‌شده",
  amountBorrowed: "مبلغ قرض‌گرفته‌شده",
  paid: "پرداخت‌شده",
  remaining: "مانده",
  receivableBalance: "مانده طلبکاری",
  debtBalance: "مانده بدهی",
  netCapital: "سرمایه نزد صندوق",

  // --- Installment concepts ---
  installment: "قسط",
  installments: "اقساط",
  amount: "مبلغ",
  repaidTo: "بازپرداخت به",
  loanLenders: "قرض‌دهندگان",
  dueDate: "تاریخ سررسید",
  dayOfMonth: "روز ماه",
  overdue: "معوق",
  active: "فعال",
  settled: "تسویه‌شده",
  pending: "در انتظار",

  // --- Year + months ---
  year: "سال",
  monthFarvardin: "فروردین",
  monthOrdibehesht: "اردیبهشت",
  monthKhordad: "خرداد",
  monthTir: "تیر",
  monthMordad: "مرداد",
  monthShahrivar: "شهریور",
  monthMehr: "مهر",
  monthAban: "آبان",
  monthAzar: "آذر",
  monthDey: "دی",
  monthBahman: "بهمن",
  monthEsfand: "اسفند",

  // --- KPI cards (Home page) ---
  kpiPersonsTotal: "تعداد افراد",
  kpiLoansActive: "قرض‌های فعال",
  kpiOutstandingTotal: "مجموع مانده",
  kpiOverdue: "تعداد اقساط معوق",
  kpiByYear: "بر اساس سال",
  kpiLoanCount: "تعداد قرض",
  kpiLoansTotal: "مجموع قرض‌ها",
  topicsRepayment: "بازپرداخت",
  topicShare: "سهم (تعداد قرض)",
  sortedBy: "مرتب‌سازی بر اساس",
  statusLabel: "وضعیت",
  dueWithin: "سررسید تا",
  days: "روز",
  allItems: "همه موارد",
  severityLabel: "شدت",
  nationalCode: "کد ملی",
  guarantors: "ضامن‌ها",
  guarantorRoleMain: "اصلی",
  guarantorRole2: "دوم",
  guarantorRole3: "سوم",
  guarantorRole4: "چهارم",
  profileBorrowed: "قرض گرفته",
  profileLent: "قرض داده",
  profileRepaid: "بازپرداخت‌شده",
  profileReturned: "بازگشته",
  profileDebtRemaining: "مانده بدهی",
  profileReceivableRemaining: "مانده طلب",
  profileBalance: "تراز با صندوق",
  profileBalanceHint: "طلبکاری − بدهی",
  profileLoans: "قرض‌ها",
  profileLoansBorrowed: "گرفته‌شده",
  profileLoansLent: "داده‌شده",
  profileUpcoming: "اقساط پیش رو",
  itemsCount: "مورد",
  andMore: "مورد دیگر",
  homeCirculation: "گردش مالی ماهانه",
  homeCirculationHint: "مجموع اقساط سررسیدشدهٔ هر ماه — پرداخت‌شده در برابر مانده",
  homeBorrowedByYear: "مبلغ قرض‌ها بر اساس سال",
  homeTopicDistribution: "توزیع موضوعی قرض‌ها",

  // --- Admin / import ---
  adminLanding: "مدیریت",
  adminImports: "بارگذاری‌های اکسل",
  adminIssues: "کیفیت داده",
  adminOverdue: "اقساط معوق",
  adminAnalytics: "تحلیل ماهانه",
  daysOverdue: "روز تاخیر",
  monthlyDueCount: "اقساط سررسیدشده در ماه",
  monthlyDueTotal: "مجموع مبلغ سررسید",
  monthlyPaid: "پرداخت‌شده",
  monthlyUnpaid: "پرداخت‌نشده",
  monthlyPaymentRate: "نرخ پرداخت",
  monthlyNewLoans: "قرض‌های ثبت‌شده در ماه",
  monthlyNewLoansTotal: "مجموع قرض‌های ثبت‌شده",
  monthlyTopBorrowers: "بزرگ‌ترین قرض‌گیرندگان",
  monthlyTopLenders: "بزرگ‌ترین قرض‌دهندگان",
  monthlyTopHint: "بر اساس اقساط سررسید این ماه",
  monthlyByTopic: "توزیع موضوعی قرض‌های ماه",
  monthlyDueByDay: "اقساط سررسیدشده در روزهای ماه",
  reimportFromExcel: "بارگذاری مجدد از اکسل",
  uploadExcel: "انتخاب فایل اکسل",
  uploadDropHere: "فایل‌های .xlsm را اینجا رها کنید یا کلیک کنید",
  uploadHint: "می‌توانید چند فایل را با هم بارگذاری کنید.",
  uploadInProgress: "در حال بارگذاری...",
  uploadStarted: "بارگذاری شروع شد",
  uploadFailed: "بارگذاری ناموفق بود",
  importStatusPending: "در صف",
  importStatusRunning: "در حال پردازش",
  importStatusSuccess: "موفق",
  importStatusFailed: "ناموفق",

  // --- Issue categories + severities ---
  severityError: "خطا",
  severityWarning: "هشدار",
  severityInfo: "اطلاع‌رسانی",
  categoryBrokenRef: "ارجاع شکسته",
  categoryTotalMismatch: "ناسازگاری مبالغ",
  categoryUnresolvedPerson: "شخص ناشناس",
  categoryUnknownTopic: "موضوع نامعلوم",
  categoryDuplicatePhone: "شماره تماس تکراری",
  categoryBadDay: "روز نامعتبر",
  categoryColorAnomaly: "رنگ نامعلوم",
  categoryUnknownPhoneFormat: "قالب شماره نامعلوم",
  categoryOrphanRow: "ردیف یتیم",
  categoryMissingDay: "روز جا افتاده",
  categoryMissingAmount: "مبلغ جا افتاده",
} as const;

export type MessageKey = keyof typeof messages;

/** Convenience helper so callers can write `t("navHome")` instead of indexing. */
export function t(key: MessageKey): string {
  return messages[key];
}

/** Maps the 12 Jalali month numbers (1..12) to their Persian names. */
export const JALALI_MONTHS: readonly string[] = [
  messages.monthFarvardin,
  messages.monthOrdibehesht,
  messages.monthKhordad,
  messages.monthTir,
  messages.monthMordad,
  messages.monthShahrivar,
  messages.monthMehr,
  messages.monthAban,
  messages.monthAzar,
  messages.monthDey,
  messages.monthBahman,
  messages.monthEsfand,
] as const;

/** Map enum-style severity strings to Persian labels. */
export function severityLabel(s: "error" | "warning" | "info"): string {
  return {
    error: messages.severityError,
    warning: messages.severityWarning,
    info: messages.severityInfo,
  }[s];
}

/** Map enum-style category strings to Persian labels. */
export function categoryLabel(c: string): string {
  const map: Record<string, string> = {
    broken_ref: messages.categoryBrokenRef,
    total_mismatch: messages.categoryTotalMismatch,
    unresolved_person: messages.categoryUnresolvedPerson,
    unknown_topic: messages.categoryUnknownTopic,
    duplicate_phone: messages.categoryDuplicatePhone,
    bad_day: messages.categoryBadDay,
    color_anomaly: messages.categoryColorAnomaly,
    unknown_phone_format: messages.categoryUnknownPhoneFormat,
    orphan_row: messages.categoryOrphanRow,
    missing_day: messages.categoryMissingDay,
    missing_amount: messages.categoryMissingAmount,
  };
  return map[c] ?? c;
}
