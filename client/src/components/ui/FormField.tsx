import styles from "./FormField.module.css";
import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";

interface FieldProps {
  label: string;
  error?: string;
  hint?: string;
}

interface InputFieldProps extends FieldProps, InputHTMLAttributes<HTMLInputElement> {}
interface TextareaFieldProps extends FieldProps, TextareaHTMLAttributes<HTMLTextAreaElement> {
  rows?: number;
}
interface SelectFieldProps extends FieldProps {
  options: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
}

export function InputField({ label, error, hint, ...props }: InputFieldProps) {
  return (
    <div className={styles.field}>
      <label className={styles.label}>{label}</label>
      <input {...props} className={[styles.input, error ? styles.err : ""].join(" ")} />
      {hint && !error && <p className={styles.hint}>{hint}</p>}
      {error && <p className={styles.error}>{error}</p>}
    </div>
  );
}

export function TextareaField({ label, error, hint, rows = 4, ...props }: TextareaFieldProps) {
  return (
    <div className={styles.field}>
      <label className={styles.label}>{label}</label>
      <textarea {...props} rows={rows} className={[styles.input, styles.textarea, error ? styles.err : ""].join(" ")} />
      {hint && !error && <p className={styles.hint}>{hint}</p>}
      {error && <p className={styles.error}>{error}</p>}
    </div>
  );
}

export function SelectField({ label, error, hint, options, value, onChange }: SelectFieldProps) {
  return (
    <div className={styles.field}>
      <label className={styles.label}>{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={[styles.input, error ? styles.err : ""].join(" ")}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {hint && !error && <p className={styles.hint}>{hint}</p>}
      {error && <p className={styles.error}>{error}</p>}
    </div>
  );
}
