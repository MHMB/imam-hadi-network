"use client";

import { useState } from "react";

import { Button, Dialog, Field, FormError, TextInput } from "@/components/ui/form";
import type { PickedPerson } from "@/components/ui/PersonCombobox";
import { ApiError, api } from "@/lib/api/client";
import { messages } from "@/lib/i18n";
import { useWrite } from "@/lib/query/hooks";

/** Quick «عضو جدید»: name + phone (required), then hand the new person back. */
export function NewPersonDialog({
  initialName,
  onClose,
  onCreated,
}: {
  initialName: string;
  onClose: () => void;
  onCreated: (p: PickedPerson) => void;
}) {
  const [name, setName] = useState(initialName);
  const [phone, setPhone] = useState("");
  const create = useWrite(() => api.createPerson({ full_name: name, phone }));
  const err = create.error instanceof ApiError ? create.error : null;
  return (
    <Dialog
      open
      onClose={onClose}
      title={messages.newMember}
      footer={
        <>
          <Button onClick={onClose}>{messages.cancel}</Button>
          <Button
            variant="primary"
            disabled={create.isPending || !name.trim() || !phone.trim()}
            onClick={() =>
              create.mutate(undefined, {
                onSuccess: (r) => onCreated({ id: r.id, full_name: name.trim() }),
              })
            }
          >
            {create.isPending ? messages.saving : messages.save}
          </Button>
        </>
      }
    >
      <Field label={messages.fullName} required error={err?.fields.full_name}>
        {(a) => <TextInput {...a} value={name} onChange={(e) => setName(e.target.value)} />}
      </Field>
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
      <FormError message={err && Object.keys(err.fields).length === 0 ? err.message : undefined} />
    </Dialog>
  );
}
