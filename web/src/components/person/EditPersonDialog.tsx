"use client";

import { useState } from "react";

import {
  Button,
  Dialog,
  Field,
  FormError,
  Select,
  TextInput,
  Textarea,
} from "@/components/ui/form";
import { PLATFORMS, platformLabel } from "@/components/ui/PlatformIcon";
import { ApiError, type Platform, type PersonDetailResponse, api } from "@/lib/api/client";
import { messages } from "@/lib/i18n";
import { useWrite } from "@/lib/query/hooks";

type Contact = { platform: Platform; handle: string; is_default: boolean };

const lines = (text: string) =>
  text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

const realPhone = (phone: string) => (phone.startsWith("+0__") ? "" : phone);

/** Profile editor: name, phone (required), national code, bank details, contacts with one default. */
export function EditPersonDialog({
  open,
  onClose,
  detail,
}: {
  open: boolean;
  onClose: () => void;
  detail: PersonDetailResponse;
}) {
  const p = detail.person;
  const [name, setName] = useState(p.full_name);
  const [phone, setPhone] = useState(realPhone(p.phone));
  const [bank, setBank] = useState(detail.profile.bank_account ?? "");
  const [ids, setIds] = useState({
    first_name: detail.profile.first_name ?? "",
    last_name: detail.profile.last_name ?? "",
    national_code: p.national_code ?? "",
    card_numbers: detail.profile.card_numbers.join("\n"),
    ibans: detail.profile.ibans.join("\n"),
  });
  const [contacts, setContacts] = useState<Contact[]>(detail.profile.contacts);
  const save = useWrite(() =>
    api.updatePerson(p.id, {
      full_name: name,
      phone,
      bank_account: bank || null,
      first_name: ids.first_name || null,
      last_name: ids.last_name || null,
      national_code: ids.national_code || null,
      card_numbers: lines(ids.card_numbers),
      ibans: lines(ids.ibans),
      contacts: contacts.filter((c) => c.handle.trim()),
    }),
  );
  const err = save.error instanceof ApiError ? save.error : null;

  const setContact = (i: number, patch: Partial<Contact>) =>
    setContacts((cs) =>
      cs.map((c, j) =>
        j === i ? { ...c, ...patch } : patch.is_default ? { ...c, is_default: false } : c,
      ),
    );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={messages.editProfile}
      footer={
        <>
          <Button onClick={onClose}>{messages.cancel}</Button>
          <Button
            variant="primary"
            disabled={save.isPending || !phone.trim() || !name.trim()}
            onClick={() => save.mutate(undefined, { onSuccess: onClose })}
          >
            {save.isPending ? messages.saving : messages.save}
          </Button>
        </>
      }
    >
      <Field label={messages.fullName} required error={err?.fields.full_name}>
        {(a) => <TextInput {...a} value={name} onChange={(e) => setName(e.target.value)} />}
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        {(
          [
            ["first_name", messages.firstName, false],
            ["last_name", messages.lastName, false],
            ["national_code", messages.nationalCode, true],
          ] as const
        ).map(([key, label, digits]) => (
          <Field key={key} label={label} error={err?.fields[key]}>
            {(a) => (
              <TextInput
                {...a}
                dir={digits ? "ltr" : undefined}
                inputMode={digits ? "numeric" : undefined}
                value={ids[key]}
                onChange={(e) => setIds((s) => ({ ...s, [key]: e.target.value }))}
                className={digits ? "text-start" : undefined}
              />
            )}
          </Field>
        ))}
      </div>
      {(
        [
          ["card_numbers", messages.cardNumber, "6037…"],
          ["ibans", messages.iban, "IR…"],
        ] as const
      ).map(([key, label, placeholder]) => (
        <Field key={key} label={label} hint={messages.onePerLine} error={err?.fields[key]}>
          {(a) => (
            <Textarea
              {...a}
              dir="ltr"
              rows={2}
              placeholder={placeholder}
              value={ids[key]}
              onChange={(e) => setIds((s) => ({ ...s, [key]: e.target.value }))}
              className="text-start"
            />
          )}
        </Field>
      ))}
      <Field label={messages.phone} required hint={messages.phoneHint} error={err?.fields.phone}>
        {(a) => (
          <TextInput
            {...a}
            dir="ltr"
            inputMode="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="text-start"
          />
        )}
      </Field>
      <Field label={messages.bankAccount} error={err?.fields.bank_account}>
        {(a) => (
          <TextInput
            {...a}
            dir="ltr"
            value={bank}
            onChange={(e) => setBank(e.target.value)}
            className="text-start"
          />
        )}
      </Field>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-slate-700">{messages.contacts}</legend>
        {contacts.map((c, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <Select
              aria-label={messages.platform}
              value={c.platform}
              onChange={(e) => setContact(i, { platform: e.target.value as Platform })}
              className="w-32"
            >
              {PLATFORMS.filter((x) => x !== "in_person").map((x) => (
                <option key={x} value={x}>
                  {platformLabel(x)}
                </option>
              ))}
            </Select>
            <TextInput
              aria-label={messages.contactHandle}
              placeholder={messages.contactHandle}
              dir="ltr"
              value={c.handle}
              onChange={(e) => setContact(i, { handle: e.target.value })}
              className="min-w-0 flex-1 text-start"
            />
            <label className="inline-flex items-center gap-1.5 text-sm text-slate-700">
              <input
                type="radio"
                name="default-contact"
                checked={c.is_default}
                onChange={() => setContact(i, { is_default: true })}
              />
              {messages.contactDefault}
            </label>
            <Button
              aria-label={messages.remove}
              onClick={() => setContacts((cs) => cs.filter((_, j) => j !== i))}
              className="w-10 px-0"
            >
              ×
            </Button>
          </div>
        ))}
        {err?.fields.contacts && (
          <p className="text-xs text-overdue" role="alert">
            {err.fields.contacts}
          </p>
        )}
        <Button
          onClick={() =>
            setContacts((cs) => [
              ...cs,
              { platform: "bale", handle: "", is_default: cs.length === 0 },
            ])
          }
        >
          + {messages.addContact}
        </Button>
      </fieldset>
      <FormError message={err && Object.keys(err.fields).length === 0 ? err.message : undefined} />
    </Dialog>
  );
}
