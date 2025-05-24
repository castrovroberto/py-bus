import type { HistoricalQuery, HistoricalDataResponse } from '../models'; // Adjusted path

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'; // Fallback for local dev

interface TokenResponse {
  access_token: string;
  token_type: string;
}

// --- Token Management ---
const getToken = (): string | null => {
  return localStorage.getItem('accessToken');
};

const setToken = (token: string): void => {
  localStorage.setItem('accessToken', token);
};

const removeToken = (): void => {
  localStorage.removeItem('accessToken');
};

// --- API Call Wrappers ---

/**
 * Performs a login request to the API.
 * @param formData - URLSearchParams containing username and password.
 * @returns Promise<TokenResponse>
 */
export const loginUser = async (formData: URLSearchParams): Promise<TokenResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: "Login failed, server error." }));
    throw new Error(errorData.detail || "Login failed");
  }
  const data: TokenResponse = await response.json();
  setToken(data.access_token);
  return data;
};

/**
 * Fetches historical data from the API.
 * Requires a valid JWT token to be stored.
 * @param query - The historical data query parameters.
 * @returns Promise<any> // Replace 'any' with a proper response type model
 */
export const getHistoricalData = async (query: HistoricalQuery): Promise<HistoricalDataResponse> => {
  const token = getToken();
  if (!token) {
    throw new Error("Authentication token not found. Please login.");
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/data/historical`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(query),
  });

  if (!response.ok) {
    if (response.status === 401) {
      removeToken(); // Token might be invalid or expired
      throw new Error("Unauthorized or session expired. Please login again.");
    }
    const errorData = await response.json().catch(() => ({ detail: "Failed to fetch historical data." }));
    throw new Error(errorData.detail || "Failed to fetch historical data");
  }
  return response.json();
};

export const logoutUser = (): void => {
  removeToken();
  // Additional cleanup if needed (e.g., clear user state in context)
};

// Helper to check if user is authenticated (basic check)
export const isAuthenticated = (): boolean => !!getToken();

// You might want to define types for API responses, e.g.:
// interface HistoricalDataApiResponse { /* ... structure ... */ }
// And use it: export const getHistoricalData = async (query: HistoricalQuery): Promise<HistoricalDataApiResponse> => { ... }

// Also, models like HistoricalQuery might be shared with the backend or defined here.
// For now, assuming HistoricalQuery is available (e.g., from a shared models directory or duplicated).
// If not, define it here:
/*
export interface HistoricalQuery {
  start_time: string; // ISO datetime string
  end_time: string;   // ISO datetime string
  measurement?: string;
  device_name?: string;
  slave_id?: string;
  register_type?: string;
  address?: string;
  tags?: Record<string, string>;
}
*/ 