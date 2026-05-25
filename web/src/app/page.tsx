import { messages } from "@/lib/i18n";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-2xl font-bold">{messages.appTitle}</h1>
      <p className="mt-4 text-slate-600">{messages.bootstrapWelcome}</p>
      <p className="mt-2 text-sm text-slate-400">{messages.phaseStub}</p>
    </main>
  );
}
