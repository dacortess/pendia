"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useGroups } from "@/lib/groups-context";
import { useAuth } from "@/lib/auth-context";
import {
  listObligations,
  listPeriods,
  listPayments,
  registerPayment,
  voidPayment,
  type Obligation,
  type ObligationPeriod,
  type Payment,
  ApiError,
} from "@/lib/api-client";
import { formatAmount } from "@/lib/obligation-format";

function formatDueDate(dueDate: string): string {
  const [y, m, d] = dueDate.split("-");
  return `${d}/${m}/${y}`;
}

export default function PaymentsPage() {
  const { currentGroup } = useGroups();
  const { user } = useAuth();

  const [allPeriods, setAllPeriods] = useState<ObligationPeriod[]>([]);
  const [obligationsMap, setObligationsMap] = useState<
    Map<number, Obligation>
  >(new Map());
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [payingPeriodId, setPayingPeriodId] = useState<number | null>(null);
  const [payError, setPayError] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);

  const [voidingPaymentId, setVoidingPaymentId] = useState<number | null>(null);
  const [voidError, setVoidError] = useState<string | null>(null);
  const [voiding, setVoiding] = useState(false);

  useEffect(() => {
    if (!currentGroup) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function load() {
      try {
        const [obligationsData, periodsData, paymentsData] = await Promise.all([
          listObligations(currentGroup!.id),
          listPeriods(currentGroup!.id),
          listPayments(currentGroup!.id),
        ]);
        if (!cancelled) {
          const map = new Map<number, Obligation>();
          for (const o of obligationsData) {
            map.set(o.id, o);
          }
          setObligationsMap(map);
          setAllPeriods(periodsData);
          setPayments(paymentsData);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setLoadError("No se pudieron cargar los pagos pendientes.");
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [currentGroup]);

  const pendingPeriods = allPeriods
    .filter(
      (p) => p.status !== "PAGADO" && obligationsMap.has(p.obligation_id)
    )
    .sort((a, b) => a.due_date.localeCompare(b.due_date));

  const periodsById = new Map(allPeriods.map((p) => [p.id, p]));

  const sortedPayments = [...payments].sort((a, b) =>
    b.paid_at.localeCompare(a.paid_at)
  );

  function canPay(obligation: Obligation): boolean {
    return (
      currentGroup?.my_role === "owner" ||
      currentGroup?.my_role === "admin" ||
      (obligation.responsible_user_id !== null &&
        obligation.responsible_user_id === user?.id)
    );
  }

  function canVoid(payment: Payment): boolean {
    const period = periodsById.get(payment.obligation_period_id);
    if (!period) return false;
    const obligation = obligationsMap.get(period.obligation_id);
    if (!obligation) return false;
    return (
      currentGroup?.my_role === "owner" ||
      currentGroup?.my_role === "admin" ||
      (obligation.responsible_user_id !== null &&
        obligation.responsible_user_id === user?.id)
    );
  }

  async function handlePay(
    period: ObligationPeriod,
    obligation: Obligation,
    amount: string,
    paidAt: string,
    notes: string,
    receiptUrl: string
  ) {
    if (!currentGroup) return;
    setPaying(true);
    setPayError(null);
    try {
      await registerPayment(currentGroup.id, period.id, {
        amount_cents: Math.round(parseFloat(amount) * 100),
        currency: obligation.currency,
        paid_at: paidAt,
        notes: notes || undefined,
        receipt_url: receiptUrl || undefined,
      });
      setAllPeriods((prev) => prev.filter((p) => p.id !== period.id));
      setPayingPeriodId(null);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "PERIOD_ALREADY_PAID") {
          setAllPeriods((prev) => prev.filter((p) => p.id !== period.id));
          setPayingPeriodId(null);
          setPayError("Este período ya tiene un pago registrado.");
        } else if (err.code === "FORBIDDEN_NOT_RESPONSIBLE") {
          setPayError(
            "No tienes permisos para registrar este pago."
          );
        } else {
          setPayError("No se pudo registrar el pago. Intenta de nuevo.");
        }
      } else {
        setPayError("No se pudo registrar el pago. Intenta de nuevo.");
      }
    } finally {
      setPaying(false);
    }
  }

  async function handleVoid(payment: Payment) {
    if (!currentGroup) return;
    setVoiding(true);
    setVoidError(null);
    try {
      const updated = await voidPayment(currentGroup.id, payment.id);
      setPayments((prev) =>
        prev.map((p) => (p.id === payment.id ? updated : p))
      );
      setVoidingPaymentId(null);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "PAYMENT_ALREADY_VOIDED") {
          setPayments((prev) =>
            prev.map((p) =>
              p.id === payment.id
                ? { ...p, voided_at: new Date().toISOString() }
                : p
            )
          );
          setVoidingPaymentId(null);
          setVoidError("Este pago ya fue anulado.");
        } else if (err.code === "FORBIDDEN_NOT_RESPONSIBLE") {
          setVoidError("No tienes permisos para anular este pago.");
        } else {
          setVoidError("No se pudo anular el pago. Intenta de nuevo.");
        }
      } else {
        setVoidError("No se pudo anular el pago. Intenta de nuevo.");
      }
    } finally {
      setVoiding(false);
    }
  }

  if (loading) {
    return (
      <p className="text-gray-500 text-center py-12">Cargando...</p>
    );
  }

  if (!currentGroup) {
    return (
      <div className="max-w-md mx-auto mt-12">
        <div className="bg-white rounded-lg shadow-md p-8 text-center">
          <p className="text-gray-600 mb-4">
            Primero creá un grupo desde el Dashboard antes de ver pagos.
          </p>
          <Link
            href="/dashboard"
            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            Ir al Dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="max-w-md mx-auto mt-12">
        <div className="bg-red-50 text-red-700 text-sm rounded p-4">
          {loadError}
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-800 mb-6">Pagos</h1>

      {payError && (
        <div className="bg-red-50 text-red-700 text-sm rounded p-4 mb-4">
          {payError}
        </div>
      )}

      {pendingPeriods.length === 0 ? (
        <p className="text-gray-500 text-center py-12">
          No hay pagos pendientes.
        </p>
      ) : (
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-700">
                  Obligación
                </th>
                <th className="text-right px-4 py-3 font-medium text-gray-700">
                  Monto esperado
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">
                  Vencimiento
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">
                  Estado
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-700">
                  Acción
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {pendingPeriods.map((period) => {
                const obligation = obligationsMap.get(period.obligation_id);
                if (!obligation) return null;

                return (
                  <tr key={period.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-800 font-medium">
                      {obligation.name}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-800">
                      {formatAmount(
                        obligation.expected_amount_cents,
                        obligation.currency
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {formatDueDate(period.due_date)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={
                          "inline-block text-xs font-medium px-2 py-0.5 rounded " +
                          (period.status === "VENCIDO"
                            ? "bg-red-100 text-red-800"
                            : "bg-yellow-100 text-yellow-800")
                        }
                      >
                        {period.status === "VENCIDO" ? "Vencido" : "Pendiente"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {canPay(obligation) &&
                        payingPeriodId !== period.id && (
                          <button
                            onClick={() => {
                              setPayingPeriodId(period.id);
                              setPayError(null);
                            }}
                            className="bg-blue-600 text-white rounded px-4 py-2 text-sm hover:bg-blue-700"
                          >
                            Registrar pago
                          </button>
                        )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {payingPeriodId !== null && (() => {
        const period = allPeriods.find((p) => p.id === payingPeriodId);
        if (!period) return null;
        const obligation = obligationsMap.get(period.obligation_id);
        if (!obligation) return null;

        const defaultAmount = (
          obligation.expected_amount_cents / 100
        ).toString();
        const defaultDate = new Date().toISOString().slice(0, 10);

        return (
          <div className="mt-4 bg-white rounded-lg shadow-md p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">
              Registrar pago — {obligation.name}
            </h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const form = e.target as HTMLFormElement;
                const amount = (
                  form.elements.namedItem("amount") as HTMLInputElement
                ).value;
                const paidAt = (
                  form.elements.namedItem("paidAt") as HTMLInputElement
                ).value;
                const notes = (
                  form.elements.namedItem("notes") as HTMLTextAreaElement
                ).value;
                const receiptUrl = (
                  form.elements.namedItem("receiptUrl") as HTMLInputElement
                ).value;
                handlePay(period, obligation, amount, paidAt, notes, receiptUrl);
              }}
              className="space-y-4"
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label
                    htmlFor="amount"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Monto pagado
                  </label>
                  <input
                    type="number"
                    id="amount"
                    name="amount"
                    defaultValue={defaultAmount}
                    step="0.01"
                    required
                    className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Moneda
                  </label>
                  <p className="text-sm text-gray-800 py-2">
                    {obligation.currency}
                  </p>
                </div>
                <div>
                  <label
                    htmlFor="paidAt"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Fecha de pago
                  </label>
                  <input
                    type="date"
                    id="paidAt"
                    name="paidAt"
                    defaultValue={defaultDate}
                    required
                    className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label
                    htmlFor="receiptUrl"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    URL de comprobante (opcional)
                  </label>
                  <input
                    type="text"
                    id="receiptUrl"
                    name="receiptUrl"
                    className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div>
                <label
                  htmlFor="notes"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Notas
                </label>
                <textarea
                  id="notes"
                  name="notes"
                  rows={2}
                  className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                />
              </div>
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={paying}
                  className="bg-blue-600 text-white rounded px-4 py-2 text-sm hover:bg-blue-700 disabled:opacity-50"
                >
                  {paying ? "Registrando..." : "Confirmar pago"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPayingPeriodId(null);
                    setPayError(null);
                  }}
                  disabled={paying}
                  className="border border-gray-300 text-gray-700 rounded px-4 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        );
      })()}

      <h2 className="text-lg font-semibold text-gray-800 mt-8 mb-4">
        Historial de pagos
      </h2>

      {sortedPayments.length === 0 ? (
        <p className="text-gray-500 text-center py-12">
          Aún no hay pagos registrados.
        </p>
      ) : (
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-700">
                  Obligación
                </th>
                <th className="text-right px-4 py-3 font-medium text-gray-700">
                  Monto pagado
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">
                  Fecha de pago
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">
                  Estado
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-700">
                  Acción
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sortedPayments.map((payment) => {
                const period = periodsById.get(payment.obligation_period_id);
                const obligation = period
                  ? obligationsMap.get(period.obligation_id)
                  : undefined;

                return (
                  <tr key={payment.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-800 font-medium">
                      {obligation ? obligation.name : "Obligación eliminada"}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-800">
                      {formatAmount(payment.amount_cents, payment.currency)}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {formatDueDate(payment.paid_at)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={
                          "inline-block text-xs font-medium px-2 py-0.5 rounded " +
                          (payment.voided_at
                            ? "bg-gray-100 text-gray-600"
                            : "bg-green-100 text-green-800")
                        }
                      >
                        {payment.voided_at ? "Anulado" : "Activo"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {!payment.voided_at && canVoid(payment) && (
                        <>
                          {voidingPaymentId !== payment.id ? (
                            <button
                              onClick={() => {
                                setVoidingPaymentId(payment.id);
                                setVoidError(null);
                              }}
                              className="border border-red-300 text-red-700 rounded px-4 py-2 text-sm hover:bg-red-50"
                            >
                              Anular
                            </button>
                          ) : (
                            <div className="inline-flex flex-col items-center gap-2">
                              <p className="text-xs text-gray-600">
                                ¿Anular este pago? El período volverá a quedar
                                pendiente.
                              </p>
                              <div className="inline-flex items-center gap-2">
                                <button
                                  onClick={() => handleVoid(payment)}
                                  disabled={voiding}
                                  className="bg-red-600 text-white rounded px-4 py-2 text-sm hover:bg-red-700 disabled:opacity-50"
                                >
                                  {voiding ? "Anulando..." : "Confirmar"}
                                </button>
                                <button
                                  onClick={() => {
                                    setVoidingPaymentId(null);
                                    setVoidError(null);
                                  }}
                                  disabled={voiding}
                                  className="border border-gray-300 text-gray-700 rounded px-4 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
                                >
                                  Cancelar
                                </button>
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {voidError && (
        <div className="bg-red-50 text-red-700 text-sm rounded p-4 mt-4">
          {voidError}
        </div>
      )}
    </div>
  );
}
