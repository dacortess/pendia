"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useGroups } from "@/lib/groups-context";
import {
  listObligations,
  createObligation,
  type Obligation,
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

export default function ObligationsPage() {
  const { currentGroup, loading: groupsLoading } = useGroups();
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const canCreate =
    currentGroup?.my_role === "owner" || currentGroup?.my_role === "admin";

  useEffect(() => {
    if (!currentGroup) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function load() {
      try {
        const data = await listObligations(currentGroup!.id);
        if (!cancelled) {
          setObligations(data);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setLoadError("No se pudieron cargar las obligaciones.");
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [currentGroup]);

  async function handleCreate(data: ObligationCreateInput | ObligationUpdateInput) {
    const input = data as ObligationCreateInput;
    if (!currentGroup) return;
    setCreating(true);
    setCreateError(null);
    try {
      const created = await createObligation(currentGroup.id, input);
      setObligations((prev) => [...prev, created]);
      setShowForm(false);
    } catch (err) {
      let message = "No se pudo crear la obligación. Intenta de nuevo.";
      if (err instanceof ApiError && err.code === "FORBIDDEN_NOT_ADMIN") {
        message = "No tienes permisos para crear obligaciones.";
      }
      setCreateError(message);
    } finally {
      setCreating(false);
    }
  }

  if (groupsLoading || loading) {
    return (
      <p className="text-gray-500 text-center py-12">Cargando...</p>
    );
  }

  if (!currentGroup) {
    return (
      <div className="max-w-md mx-auto mt-12">
        <div className="bg-white rounded-lg shadow-md p-8 text-center">
          <p className="text-gray-600 mb-4">
            Primero creá un grupo desde el Dashboard antes de agregar obligaciones.
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
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-800">Obligaciones</h1>
        {canCreate && (
          <button
            onClick={() => {
              setShowForm(!showForm);
              setCreateError(null);
            }}
            className="bg-blue-600 text-white rounded px-4 py-2 text-sm hover:bg-blue-700"
          >
            {showForm ? "Cancelar" : "+ Nueva obligación"}
          </button>
        )}
      </div>

      {showForm && (
        <ObligationForm
          mode="create"
          onSubmit={handleCreate}
          submitLabel="Crear obligación"
          error={createError}
          submitting={creating}
        />
      )}

      {obligations.length === 0 ? (
        <p className="text-gray-500 text-center py-12">
          Aún no tienes obligaciones registradas.
        </p>
      ) : (
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-700">
                  Nombre
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">
                  Proveedor
                </th>
                <th className="text-right px-4 py-3 font-medium text-gray-700">
                  Monto esperado
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">
                  Periodicidad
                </th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">
                  Vencimiento
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-700">
                  Esencial
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {obligations.map((o) => (
                <tr key={o.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link
                      href={`/obligations/detail?id=${o.id}`}
                      className="text-blue-600 hover:text-blue-800 font-medium"
                    >
                      {o.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {o.provider_name || "—"}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-800">
                    {formatAmount(o.expected_amount_cents, o.currency)}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {PERIODICITY_LABELS[o.periodicity] ?? o.periodicity}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {formatDueDate(o)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={
                        "inline-block text-xs font-medium px-2 py-0.5 rounded " +
                        (o.is_essential
                          ? "bg-yellow-100 text-yellow-800"
                          : "bg-gray-100 text-gray-600")
                      }
                    >
                      {o.is_essential ? "Sí" : "No"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
