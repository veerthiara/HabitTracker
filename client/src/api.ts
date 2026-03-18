const configuredBase = import.meta.env.VITE_API_BASE_URL?.trim();

export const apiBaseUrl = configuredBase && configuredBase.length > 0 ? configuredBase : "/api";

export async function fetchBackendRoot() {
  const response = await fetch(`${apiBaseUrl}/`);

  if (!response.ok) {
    throw new Error(`Backend request failed with status ${response.status}`);
  }

  return response.json() as Promise<{ message: string }>;
}
