"use client";

import { useState } from "react";
import { useGroups } from "@/lib/groups-context";

export default function DashboardPage() {
  const { groups, currentGroup, loading, createGroup } = useGroups();

  if (loading) {
    return (
      <p className="text-gray-500 text-center py-12">Cargando grupos...</p>
    );
  }

  if (groups.length === 0) {
    return <EmptyState createGroup={createGroup} />;
  }

  return (
    <div className="max-w-md mx-auto mt-12">
      <div className="bg-white rounded-lg shadow-md p-8 text-center">
        <h2 className="text-xl font-bold mb-2">
          Bienvenido a {currentGroup?.name}
        </h2>
        <span className="inline-block bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-0.5 rounded">
          {currentGroup?.my_role}
        </span>
      </div>
    </div>
  );
}

function EmptyState({
  createGroup,
}: {
  createGroup: (name: string) => Promise<import("@/lib/groups-context").Group>;
}) {
  const { error } = useGroups();
  const [groupName, setGroupName] = useState("");
  const [creating, setCreating] = useState(false);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = groupName.trim();
    if (!trimmed) return;

    setCreating(true);
    try {
      await createGroup(trimmed);
      setGroupName("");
    } catch {
      // error is set in context
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="max-w-md mx-auto mt-12">
      <div className="bg-white rounded-lg shadow-md p-8 text-center">
        <h2 className="text-xl font-bold mb-2">Crea tu primer grupo</h2>
        <p className="text-gray-600 mb-6">
          Crea un grupo familiar para empezar a gestionar pagos y obligaciones
          juntos.
        </p>
        <form onSubmit={handleCreate} noValidate>
          <div className="mb-4">
            <label
              htmlFor="group-name"
              className="block text-sm font-medium text-gray-700 mb-1 text-left"
            >
              Nombre del grupo
            </label>
            <input
              id="group-name"
              type="text"
              maxLength={200}
              value={groupName}
              onChange={(e) => setGroupName(e.target.value)}
              placeholder="Ej: Familia García"
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
            />
          </div>
          {error && (
              <div className="bg-red-50 text-red-700 text-sm rounded p-2 mb-4">
                {error}
              </div>
            )}
          <button
            type="submit"
            disabled={creating || !groupName.trim()}
            className="w-full bg-blue-600 text-white rounded py-2 text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {creating ? "Creando..." : "Crear grupo"}
          </button>
        </form>
      </div>
    </div>
  );
}
