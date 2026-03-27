import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Modal } from "../../../components/ui/Modal";
import { Button } from "../../../components/ui/Button";
import { InputField, TextareaField, SelectField } from "../../../components/ui/FormField";
import { habitsApi } from "../../../api/habits";

interface Props {
  open: boolean;
  onClose: () => void;
}

const FREQ_OPTIONS = [
  { value: "daily",  label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "custom", label: "Custom" },
];

export function CreateHabitModal({ open, onClose }: Props) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [frequency, setFrequency] = useState("daily");
  const [errors, setErrors] = useState<{ name?: string }>({});

  const mutation = useMutation({
    mutationFn: () => habitsApi.create({ name: name.trim(), description: description.trim() || undefined, frequency }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["habits"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      handleClose();
    },
  });

  function handleClose() {
    setName(""); setDescription(""); setFrequency("daily"); setErrors({});
    onClose();
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) { setErrors({ name: "Name is required" }); return; }
    mutation.mutate();
  }

  return (
    <Modal open={open} onClose={handleClose} title="New Habit">
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <InputField
          label="Name"
          placeholder="e.g. Morning run"
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={errors.name}
          autoFocus
        />
        <TextareaField
          label="Description"
          placeholder="Optional — what does this habit involve?"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
        />
        <SelectField
          label="Frequency"
          options={FREQ_OPTIONS}
          value={frequency}
          onChange={setFrequency}
        />
        <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "flex-end", paddingTop: "var(--space-2)" }}>
          <Button type="button" variant="secondary" onClick={handleClose}>Cancel</Button>
          <Button type="submit" loading={mutation.isPending}>Create Habit</Button>
        </div>
      </form>
    </Modal>
  );
}
