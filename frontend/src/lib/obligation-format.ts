import type { Obligation } from "./api-client";

export const PERIODICITY_LABELS: Record<string, string> = {
  MONTHLY: "Mensual",
  BIMONTHLY: "Bimestral",
  QUARTERLY: "Trimestral",
  SEMIANNUAL: "Semestral",
  ANNUAL: "Anual",
};

export function formatAmount(cents: number, currency: string): string {
  const amount = cents / 100;
  const formatted = amount.toLocaleString("es-CO", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
  return currency === "COP" ? `$${formatted}` : `US$${formatted}`;
}

export function formatDueDate(obligation: Obligation): string {
  if (obligation.periodicity === "ANNUAL") {
    return `${obligation.due_day}/${obligation.due_month} de cada año`;
  }
  return `Día ${obligation.due_day} de cada mes`;
}
