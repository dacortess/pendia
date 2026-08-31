"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useGroups } from "@/lib/groups-context";
import {
  getObligation,
  updateObligation,
  deactivateObligation,
  listMembers,
  listCategories,
  listPaymentMethods,
  type Obligation,
  type Member,
  type Category,
  type PaymentMethod,
  type ObligationCreateInput,
  type ObligationUpdateInput,
  ApiError,
} from "@/lib/api-client";
import {
  PERIODICITY_LABELS,
  formatAmount,
  formatDueDate,
} from "@/lib/obligation-format";
import ObligationForm from "@/components/ObligationForm";
import type { ObligationFormValues } from "@/components/ObligationForm";

export default function ObligationDetailPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { currentGroup } = useGroups();

  const obligationId = Number(searchParams.get("id"));

  const [obligation, setObligation] = useState<Obligation | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [editing, setEditing] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);

  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const canModify =
    currentGroup?.my_role === "owner" || currentGroup?.my_role === "admin";

  useEffect(() => {
    if (!currentGroup || !obligationId) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function load() {
      try {
        const [obligationData, membersData, categoriesData, paymentMethodsData] = await Promise.all([
          getObligation(currentGroup!.id, obligationId),
          listMembers(currentGroup!.id),
          listCategories(currentGroup!.id),
          listPaymentMethods(currentGroup!.id),
        ]);
        if (!cancelled) {
          setObligation(obligationData);
          setMembers(membersData);
          setCategories(categoriesData);
          setPaymentMethods(paymentMethodsData);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 404) {
            setLoadError("OBLIGATION_NOT_FOUND");
          } else {
            setLoadError("No se pudo cargar la obligación.");
          }
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [currentGroup, obligationId]);

  async function handleUpdate(data: ObligationCreateInput | ObligationUpdateInput) {
    const input = data as ObligationUpdateInput;
    if (!currentGroup || !obligation) return;
    setUpdating(true);
    setUpdateError(null);
    try {
      const updated = await updateObligation(
        currentGroup.id,
        obligation.id,
        input
      );
      setObligation(updated);
      setEditing(false);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "FORBIDDEN_NOT_ADMIN") {
          setUpdateError("No tienes permisos para editar obligaciones.");
        } else if (err.status === 404) {
          setLoadError("OBLIGATION_NOT_FOUND");
        } else {
          setUpdateError("No se pudo actualizar la obligación. Intenta de nuevo.");
        }
      } else {
        setUpdateError("No se pudo actualizar la obligación. Intenta de nuevo.");
      }
    } finally {
      setUpdating(false);
    }
  }

  async function handleDelete() {
    if (!currentGroup || !obligation) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deactivateObligation(currentGroup.id, obligation.id);
      router.push("/obligations");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "FORBIDDEN_NOT_ADMIN") {
          setDeleteError("No tienes permisos para eliminar obligaciones.");
        } else if (err.status === 404) {
          router.push("/obligations");
        } else {
          setDeleteError("No se pudo eliminar la obligación. Intenta de nuevo.");
        }
      } else {
        setDeleteError("No se pudo eliminar la obligación. Intenta de nuevo.");
      }
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <p className="text-gray-500 text-center py-12">Cargando...</p>
    );
  }

  if (loadError === "OBLIGATION_NOT_FOUND") {
    return (
      <div className="max-w-md mx-auto mt-12">
        <div className="bg-white rounded-lg shadow-md p-8 text-center">
          <p className="text-gray-600 mb-4">Obligación no encontrada.</p>
          <Link
            href="/obligations"
            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            ← Volver a Obligaciones
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

  if (!obligation) return null;

  if (editing) {
    const initialValues: ObligationFormValues = {
      name: obligation.name,
      provider_name: obligation.provider_name ?? "",
      notes: obligation.notes ?? "",
      currency: obligation.currency,
      expected_amount_cents: obligation.expected_amount_cents,
      is_variable_amount: obligation.is_variable_amount,
      is_subscription: obligation.is_subscription,
      auto_debit: obligation.auto_debit,
      is_essential: obligation.is_essential,
      periodicity: obligation.periodicity,
      due_day: obligation.due_day,
      due_month: obligation.due_month,
      start_date: obligation.start_date,
      end_date: obligation.end_date ?? "",
      responsible_user_id: obligation.responsible_user_id,
      category_id: obligation.category_id,
      payment_method_id: obligation.payment_method_id,
    };

    return (
      <div>
        <div className="mb-6">
          <Link
            href="/obligations"
            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            ← Volver a Obligaciones
          </Link>
        </div>
        <h1 className="text-xl font-bold text-gray-800 mb-4">
          Editar obligación
        </h1>
        <ObligationForm
          mode="edit"
          initialValues={initialValues}
          onSubmit={handleUpdate}
          onCancel={() => {
            setEditing(false);
            setUpdateError(null);
          }}
          submitLabel="Guardar cambios"
          error={updateError}
          submitting={updating}
          members={members}
          categories={categories}
          paymentMethods={paymentMethods}
        />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <Link
          href="/obligations"
          className="text-blue-600 hover:text-blue-800 text-sm font-medium"
        >
          ← Volver a Obligaciones
        </Link>
      </div>

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-800">
          {obligation.name}
        </h1>
        {canModify && (
          <div className="flex gap-2">
            <button
              onClick={() => {
                setEditing(true);
                setUpdateError(null);
              }}
              className="bg-blue-600 text-white rounded px-4 py-2 text-sm hover:bg-blue-700"
            >
              Editar
            </button>
            <button
              onClick={() => {
                setConfirmingDelete(true);
                setDeleteError(null);
              }}
              className="border border-red-300 text-red-700 rounded px-4 py-2 text-sm hover:bg-red-50"
            >
              Eliminar
            </button>
          </div>
        )}
      </div>

      {confirmingDelete && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-700 text-sm mb-3">
            ¿Eliminar esta obligación? No podrás deshacer esta acción.
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="bg-red-600 text-white rounded px-4 py-2 text-sm hover:bg-red-700 disabled:opacity-50"
            >
              {deleting ? "Eliminando..." : "Confirmar"}
            </button>
            <button
              onClick={() => setConfirmingDelete(false)}
              disabled={deleting}
              className="border border-gray-300 text-gray-700 rounded px-4 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              Cancelar
            </button>
          </div>
          {deleteError && (
            <p className="text-red-600 text-xs mt-2">{deleteError}</p>
          )}
        </div>
      )}

      <div className="bg-white rounded-lg shadow-md p-6">
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="font-medium text-gray-500">Proveedor</dt>
            <dd className="mt-1 text-gray-800">
              {obligation.provider_name || "—"}
            </dd>
          </div>

          <div>
            <dt className="font-medium text-gray-500">Monto esperado</dt>
            <dd className="mt-1 text-gray-800">
              {formatAmount(obligation.expected_amount_cents, obligation.currency)}{" "}
              <span className="text-gray-500">({obligation.currency})</span>
            </dd>
          </div>

          <div>
            <dt className="font-medium text-gray-500">Periodicidad</dt>
            <dd className="mt-1 text-gray-800">
              {PERIODICITY_LABELS[obligation.periodicity] ?? obligation.periodicity}
            </dd>
          </div>

          <div>
            <dt className="font-medium text-gray-500">Vencimiento</dt>
            <dd className="mt-1 text-gray-800">{formatDueDate(obligation)}</dd>
          </div>

          <div>
            <dt className="font-medium text-gray-500">Fecha de inicio</dt>
            <dd className="mt-1 text-gray-800">{obligation.start_date}</dd>
          </div>

          <div>
            <dt className="font-medium text-gray-500">Fecha de fin</dt>
            <dd className="mt-1 text-gray-800">
              {obligation.end_date || "Sin fecha de fin"}
            </dd>
          </div>

          <div className="md:col-span-2">
            <dt className="font-medium text-gray-500">Notas</dt>
            <dd className="mt-1 text-gray-800">
              {obligation.notes || "—"}
            </dd>
          </div>
        </dl>

        <div className="mt-6 flex flex-wrap gap-3">
          <span
            className={
              "inline-block text-xs font-medium px-2 py-0.5 rounded " +
              (obligation.is_variable_amount
                ? "bg-blue-100 text-blue-800"
                : "bg-gray-100 text-gray-600")
            }
          >
            Variable: {obligation.is_variable_amount ? "Sí" : "No"}
          </span>
          <span
            className={
              "inline-block text-xs font-medium px-2 py-0.5 rounded " +
              (obligation.is_subscription
                ? "bg-purple-100 text-purple-800"
                : "bg-gray-100 text-gray-600")
            }
          >
            Suscripción: {obligation.is_subscription ? "Sí" : "No"}
          </span>
          <span
            className={
              "inline-block text-xs font-medium px-2 py-0.5 rounded " +
              (obligation.auto_debit
                ? "bg-green-100 text-green-800"
                : "bg-gray-100 text-gray-600")
            }
          >
            Débito automático: {obligation.auto_debit ? "Sí" : "No"}
          </span>
          <span
            className={
              "inline-block text-xs font-medium px-2 py-0.5 rounded " +
              (obligation.is_essential
                ? "bg-yellow-100 text-yellow-800"
                : "bg-gray-100 text-gray-600")
            }
          >
            Esencial: {obligation.is_essential ? "Sí" : "No"}
          </span>
        </div>
      </div>
    </div>
  );
}
