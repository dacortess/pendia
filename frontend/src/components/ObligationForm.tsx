"use client";

import { useState } from "react";
import type {
  ObligationCreateInput,
  ObligationUpdateInput,
} from "@/lib/api-client";

export interface ObligationFormValues {
  name: string;
  provider_name: string;
  notes: string;
  currency: "COP" | "USD";
  expected_amount_cents: number;
  is_variable_amount: boolean;
  is_subscription: boolean;
  auto_debit: boolean;
  is_essential: boolean;
  periodicity: "MONTHLY" | "BIMONTHLY" | "QUARTERLY" | "SEMIANNUAL" | "ANNUAL";
  due_day: number;
  due_month: number | null;
  start_date: string;
  end_date: string | null;
}

interface ObligationFormProps {
  mode: "create" | "edit";
  initialValues?: ObligationFormValues;
  onSubmit: (
    data: ObligationCreateInput | ObligationUpdateInput
  ) => Promise<void>;
  onCancel?: () => void;
  submitLabel: string;
  error?: string | null;
  submitting?: boolean;
}

const DEFAULT_VALUES: ObligationFormValues = {
  name: "",
  provider_name: "",
  notes: "",
  currency: "COP",
  expected_amount_cents: 0,
  is_variable_amount: false,
  is_subscription: false,
  auto_debit: false,
  is_essential: true,
  periodicity: "MONTHLY",
  due_day: 1,
  due_month: null,
  start_date: "",
  end_date: "",
};

export default function ObligationForm({
  mode,
  initialValues,
  onSubmit,
  onCancel,
  submitLabel,
  error,
  submitting = false,
}: ObligationFormProps) {
  const defaults = initialValues ?? DEFAULT_VALUES;
  const [form, setForm] = useState<ObligationFormValues>(defaults);
  const [monto, setMonto] = useState(
    initialValues
      ? (initialValues.expected_amount_cents / 100).toString()
      : ""
  );
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  function updateField<K extends keyof ObligationFormValues>(
    key: K,
    value: ObligationFormValues[K]
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setFormErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  function validate(): boolean {
    const errors: Record<string, string> = {};

    if (!form.name.trim()) {
      errors.name = "El nombre es obligatorio.";
    } else if (form.name.length > 200) {
      errors.name = "El nombre no puede tener más de 200 caracteres.";
    }

    if (form.due_day < 1 || form.due_day > 31) {
      errors.due_day = "El día debe estar entre 1 y 31.";
    }

    if (form.periodicity === "ANNUAL") {
      if (
        form.due_month == null ||
        form.due_month < 1 ||
        form.due_month > 12
      ) {
        errors.due_month = "El mes es obligatorio para periodicidad anual.";
      }
    }

    if (mode === "create" && !form.start_date) {
      errors.start_date = "La fecha de inicio es obligatoria.";
    }

    if (form.end_date && form.start_date && form.end_date < form.start_date) {
      errors.end_date = "La fecha de fin debe ser igual o posterior a la de inicio.";
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    if (mode === "create") {
      const data: ObligationCreateInput = {
        name: form.name,
        currency: form.currency,
        expected_amount_cents: Math.round((parseFloat(monto) || 0) * 100),
        is_variable_amount: form.is_variable_amount,
        is_subscription: form.is_subscription,
        auto_debit: form.auto_debit,
        is_essential: form.is_essential,
        periodicity: form.periodicity,
        due_day: form.due_day,
        start_date: form.start_date,
        due_month: form.periodicity === "ANNUAL" ? form.due_month : null,
        end_date: form.end_date || undefined,
        provider_name: form.provider_name || undefined,
        notes: form.notes || undefined,
      };
      await onSubmit(data);
    } else {
      const data: ObligationUpdateInput = {
        name: form.name,
        currency: form.currency,
        expected_amount_cents: Math.round((parseFloat(monto) || 0) * 100),
        is_variable_amount: form.is_variable_amount,
        is_subscription: form.is_subscription,
        auto_debit: form.auto_debit,
        is_essential: form.is_essential,
        periodicity: form.periodicity,
        due_day: form.due_day,
        due_month: form.periodicity === "ANNUAL" ? form.due_month : null,
        start_date: form.start_date,
        end_date: form.end_date || null,
        provider_name: form.provider_name || null,
        notes: form.notes || null,
      };
      await onSubmit(data);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="bg-white rounded-lg shadow-md p-6 mb-6"
    >
      {error && (
        <div className="bg-red-50 text-red-700 text-sm rounded p-2 mb-4">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label
            htmlFor="nombre"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Nombre *
          </label>
          <input
            id="nombre"
            type="text"
            maxLength={200}
            value={form.name}
            onChange={(e) => updateField("name", e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
          {formErrors.name && (
            <p className="text-red-600 text-xs mt-1">{formErrors.name}</p>
          )}
        </div>

        <div>
          <label
            htmlFor="proveedor"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Proveedor
          </label>
          <input
            id="proveedor"
            type="text"
            value={form.provider_name ?? ""}
            onChange={(e) =>
              updateField("provider_name", e.target.value || "")
            }
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label
            htmlFor="moneda"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Moneda
          </label>
          <select
            id="moneda"
            value={form.currency}
            onChange={(e) =>
              updateField("currency", e.target.value as "COP" | "USD")
            }
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          >
            <option value="COP">COP</option>
            <option value="USD">USD</option>
          </select>
        </div>

        <div>
          <label
            htmlFor="monto-input"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Monto esperado
          </label>
          <input
            id="monto-input"
            type="number"
            min="0"
            step="0.01"
            value={monto}
            onChange={(e) => setMonto(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label
            htmlFor="periodicidad"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Periodicidad
          </label>
          <select
            id="periodicidad"
            value={form.periodicity}
            onChange={(e) =>
              updateField(
                "periodicity",
                e.target.value as ObligationFormValues["periodicity"]
              )
            }
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          >
            <option value="MONTHLY">Mensual</option>
            <option value="BIMONTHLY">Bimestral</option>
            <option value="QUARTERLY">Trimestral</option>
            <option value="SEMIANNUAL">Semestral</option>
            <option value="ANNUAL">Anual</option>
          </select>
        </div>

        <div>
          <label
            htmlFor="dia-vencimiento"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Día de vencimiento *
          </label>
          <input
            id="dia-vencimiento"
            type="number"
            min="1"
            max="31"
            value={form.due_day}
            onChange={(e) =>
              updateField("due_day", parseInt(e.target.value, 10) || 1)
            }
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
          {formErrors.due_day && (
            <p className="text-red-600 text-xs mt-1">{formErrors.due_day}</p>
          )}
        </div>

        {form.periodicity === "ANNUAL" && (
          <div>
            <label
              htmlFor="mes-vencimiento"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Mes de vencimiento *
            </label>
            <input
              id="mes-vencimiento"
              type="number"
              min="1"
              max="12"
              value={form.due_month ?? ""}
              onChange={(e) =>
                updateField(
                  "due_month",
                  parseInt(e.target.value, 10) || null
                )
              }
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
            />
            {formErrors.due_month && (
              <p className="text-red-600 text-xs mt-1">
                {formErrors.due_month}
              </p>
            )}
          </div>
        )}

        <div>
          <label
            htmlFor="fecha-inicio"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Fecha de inicio {mode === "create" ? "*" : ""}
          </label>
          <input
            id="fecha-inicio"
            type="date"
            value={form.start_date}
            onChange={(e) => updateField("start_date", e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
          {formErrors.start_date && (
            <p className="text-red-600 text-xs mt-1">
              {formErrors.start_date}
            </p>
          )}
        </div>

        <div>
          <label
            htmlFor="fecha-fin"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Fecha de fin
          </label>
          <input
            id="fecha-fin"
            type="date"
            value={form.end_date ?? ""}
            onChange={(e) => updateField("end_date", e.target.value || null)}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
          {formErrors.end_date && (
            <p className="text-red-600 text-xs mt-1">{formErrors.end_date}</p>
          )}
        </div>

        <div className="md:col-span-2">
          <label
            htmlFor="notas"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Notas
          </label>
          <textarea
            id="notas"
            value={form.notes ?? ""}
            onChange={(e) => updateField("notes", e.target.value || "")}
            rows={2}
            className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
          />
        </div>

        <div className="flex flex-wrap gap-4 md:col-span-2">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={form.is_variable_amount}
              onChange={(e) =>
                updateField("is_variable_amount", e.target.checked)
              }
              className="rounded"
            />
            Es variable
          </label>

          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={form.is_subscription}
              onChange={(e) =>
                updateField("is_subscription", e.target.checked)
              }
              className="rounded"
            />
            Es suscripción
          </label>

          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={form.auto_debit}
              onChange={(e) => updateField("auto_debit", e.target.checked)}
              className="rounded"
            />
            Débito automático
          </label>

          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={form.is_essential}
              onChange={(e) => updateField("is_essential", e.target.checked)}
              className="rounded"
            />
            Es esencial
          </label>
        </div>
      </div>

      <div className="mt-4 flex justify-end gap-2">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="border border-gray-300 text-gray-700 rounded px-4 py-2 text-sm hover:bg-gray-50"
          >
            Cancelar
          </button>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="bg-blue-600 text-white rounded px-4 py-2 text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? "Guardando..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
