import type { Platform } from "@/lib/api/client";
import { messages } from "@/lib/i18n";

/**
 * Small coloured mark per platform (initial letter in the platform's colour)
 * — recognisable at list size without shipping third-party logo files.
 */
const MARK: Record<Platform, { letter: string; bg: string; label: string }> = {
  telegram: { letter: "ت", bg: "#229ED9", label: "تلگرام" },
  bale: { letter: "ب", bg: "#2E7D32", label: "بله" },
  eitaa: { letter: "ا", bg: "#EF6C00", label: "ایتا" },
  whatsapp: { letter: "و", bg: "#128C7E", label: "واتساپ" },
  rubika: { letter: "ر", bg: "#7B1FA2", label: "روبیکا" },
  phone: { letter: "☎", bg: "#475569", label: "تماس تلفنی" },
  in_person: { letter: "ح", bg: "#334155", label: "حضوری" },
};

export const PLATFORMS = Object.keys(MARK) as Platform[];
export const platformLabel = (p: Platform) => MARK[p].label;

export function PlatformIcon({ platform, size = 20 }: { platform: Platform; size?: number }) {
  const m = MARK[platform];
  return (
    <span
      role="img"
      aria-label={`${messages.platform}: ${m.label}`}
      title={m.label}
      className="inline-flex shrink-0 items-center justify-center rounded-full font-bold text-white"
      style={{ width: size, height: size, background: m.bg, fontSize: size * 0.55 }}
    >
      {m.letter}
    </span>
  );
}
