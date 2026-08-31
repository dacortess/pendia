"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { apiFetch, ApiError } from "./api-client";

const STORAGE_KEY = "currentGroupId";

export interface Group {
  id: number;
  name: string;
  created_by: number;
  created_at: string;
  updated_at: string;
  my_role: string;
}

interface GroupsState {
  groups: Group[];
  currentGroupId: number | null;
  loading: boolean;
  error: string | null;
}

interface GroupsContextValue extends GroupsState {
  currentGroup: Group | null;
  setCurrentGroupId: (id: number) => void;
  createGroup: (name: string) => Promise<Group>;
}

const GroupsContext = createContext<GroupsContextValue | null>(null);

export function GroupProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<GroupsState>({
    groups: [],
    currentGroupId: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function loadGroups() {
      try {
        const groups = await apiFetch<Group[]>("/groups");
        if (cancelled) return;

        const storedId = getStoredGroupId();
        const validId =
          storedId !== null && groups.some((g) => g.id === storedId)
            ? storedId
            : groups.length > 0
              ? groups[0].id
              : null;

        setState({
          groups,
          currentGroupId: validId,
          loading: false,
          error: null,
        });

        if (validId !== null) {
          setStoredGroupId(validId);
        }
      } catch {
        if (cancelled) return;
        setState((prev) => ({
          ...prev,
          loading: false,
          error: "No se pudieron cargar los grupos.",
        }));
      }
    }

    loadGroups();

    return () => {
      cancelled = true;
    };
  }, []);

  const setCurrentGroupId = useCallback((id: number) => {
    setState((prev) => {
      if (!prev.groups.some((g) => g.id === id)) return prev;
      setStoredGroupId(id);
      return { ...prev, currentGroupId: id };
    });
  }, []);

  const createGroup = useCallback(async (name: string): Promise<Group> => {
    setState((prev) => ({ ...prev, error: null }));

    try {
      const group = await apiFetch<Group>("/groups", {
        method: "POST",
        body: JSON.stringify({ name }),
      });

      setState((prev) => {
        const groups = [...prev.groups, group];
        setStoredGroupId(group.id);
        return {
          groups,
          currentGroupId: group.id,
          loading: false,
          error: null,
        };
      });

      return group;
    } catch (err) {
      const message = "No se pudo crear el grupo. Intenta de nuevo.";
      setState((prev) => ({ ...prev, error: message }));
      throw err;
    }
  }, []);

  const currentGroup =
    state.groups.find((g) => g.id === state.currentGroupId) ?? null;

  return (
    <GroupsContext.Provider
      value={{ ...state, currentGroup, setCurrentGroupId, createGroup }}
    >
      {children}
    </GroupsContext.Provider>
  );
}

export function useGroups(): GroupsContextValue {
  const context = useContext(GroupsContext);
  if (!context) {
    throw new Error("useGroups must be used within a GroupProvider");
  }
  return context;
}

function getStoredGroupId(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === null) return null;
    const id = Number(raw);
    return Number.isFinite(id) ? id : null;
  } catch {
    return null;
  }
}

function setStoredGroupId(id: number): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(id));
  } catch {
    // localStorage unavailable — ignore
  }
}
