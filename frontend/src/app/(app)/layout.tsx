"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { GroupProvider, useGroups } from "@/lib/groups-context";

function AppHeader() {
  const { logout } = useAuth();
  const { groups, currentGroup, currentGroupId, setCurrentGroupId } =
    useGroups();

  return (
    <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold text-gray-800">
          Gestor Familiar
        </h1>
        {currentGroup && (
          <>
            {groups.length > 1 ? (
              <select
                value={currentGroupId ?? ""}
                onChange={(e) => {
                  const id = Number(e.target.value);
                  if (Number.isFinite(id)) setCurrentGroupId(id);
                }}
                className="border border-gray-300 rounded px-2 py-1 text-sm"
              >
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            ) : (
              <span className="text-sm text-gray-600">{currentGroup.name}</span>
            )}
          </>
        )}
      </div>
      <button
        onClick={logout}
        className="text-sm text-red-600 hover:text-red-800"
      >
        Cerrar sesión
      </button>
    </header>
  );
}

function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { status } = useAuth();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status === "idle" || status === "loading") {
    return (
      <main className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-500">Cargando...</p>
      </main>
    );
  }

  if (status === "unauthenticated") {
    return (
      <main className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-500">Redirigiendo...</p>
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <GroupProvider>
        <AppHeader />
        <main className="max-w-4xl mx-auto px-4 py-8">{children}</main>
      </GroupProvider>
    </div>
  );
}

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
