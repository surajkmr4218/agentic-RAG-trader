import { useAuth } from "@clerk/react";
import { useQuery } from "@tanstack/react-query";

const BASE = import.meta.env.VITE_API_BASE_URL as string;

export function useApi() {
  const { getToken } = useAuth();
  return async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
    const token = await getToken();   // re-mint per call; tokens are ~60s
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 
        "Content-Type": "application/json", 
        Authorization: `Bearer ${token}`, 
        ...(init.headers ?? {}) 
        },
    });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    return res.json() as Promise<T>;
  };
}

export interface Me {
  clerk_user_id: string;
  role: "owner" | "public";
  execution_enabled: boolean;
  robinhood_linked: boolean;
}

export function useMe() {
  const api = useApi();
  return useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });  // drives tier + gate
}

