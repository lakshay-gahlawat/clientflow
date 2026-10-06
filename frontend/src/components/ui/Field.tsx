import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

interface FieldWrapperProps {
  label: string;
  htmlFor: string;
  error?: string;
  required?: boolean;
}

function FieldWrapper({ label, htmlFor, error, required, children }: FieldWrapperProps & { children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium text-ink">
        {label}
        {required && <span className="text-status-lost"> *</span>}
      </label>
      {children}
      {error && (
        <p className="mt-1 text-sm text-status-lost" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

const fieldClasses =
  "w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink placeholder:text-ink/40 focus:border-brand disabled:cursor-not-allowed disabled:bg-canvas disabled:text-ink/50";

interface InputFieldProps extends InputHTMLAttributes<HTMLInputElement>, FieldWrapperProps {}

export const InputField = forwardRef<HTMLInputElement, InputFieldProps>(
  ({ label, htmlFor, error, required, className, ...props }, ref) => (
    <FieldWrapper label={label} htmlFor={htmlFor} error={error} required={required}>
      <input
        ref={ref}
        id={htmlFor}
        className={cn(fieldClasses, error && "border-status-lost", className)}
        aria-invalid={!!error}
        {...props}
      />
    </FieldWrapper>
  )
);
InputField.displayName = "InputField";

interface TextareaFieldProps extends TextareaHTMLAttributes<HTMLTextAreaElement>, FieldWrapperProps {}

export const TextareaField = forwardRef<HTMLTextAreaElement, TextareaFieldProps>(
  ({ label, htmlFor, error, required, className, ...props }, ref) => (
    <FieldWrapper label={label} htmlFor={htmlFor} error={error} required={required}>
      <textarea
        ref={ref}
        id={htmlFor}
        className={cn(fieldClasses, "min-h-[80px] resize-y", error && "border-status-lost", className)}
        aria-invalid={!!error}
        {...props}
      />
    </FieldWrapper>
  )
);
TextareaField.displayName = "TextareaField";

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement>, FieldWrapperProps {}

export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(
  ({ label, htmlFor, error, required, className, children, ...props }, ref) => (
    <FieldWrapper label={label} htmlFor={htmlFor} error={error} required={required}>
      <select
        ref={ref}
        id={htmlFor}
        className={cn(fieldClasses, "bg-white", error && "border-status-lost", className)}
        aria-invalid={!!error}
        {...props}
      >
        {children}
      </select>
    </FieldWrapper>
  )
);
SelectField.displayName = "SelectField";
