import type { UseFetchOptions } from 'nuxt/app'

/**
 * API composable for communicating with the FastAPI backend.
 * Wraps Nuxt's $fetch with the correct base URL and default headers.
 *
 * For MVP (no auth), requests are sent without JWT headers.
 * Auth headers can be added here in future milestones.
 */
export function useApi() {
  const config = useRuntimeConfig()
  const baseURL = config.public.backendUrl as string

  /**
   * Fetch data from the backend with JSON:API defaults.
   */
  async function get<T>(url: string, opts?: UseFetchOptions<T>): Promise<T> {
    return $fetch<T>(url, {
      baseURL,
      headers: {
        Accept: 'application/vnd.api+json',
      },
      ...opts,
    })
  }

  /**
   * POST data to the backend with JSON:API defaults (where applicable).
   */
  async function post<T>(
    url: string,
    body?: unknown,
    opts?: UseFetchOptions<T>,
  ): Promise<T> {
    return $fetch<T>(url, {
      baseURL,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body,
      ...opts,
    })
  }

  /**
   * PUT data to the backend.
   */
  async function put<T>(
    url: string,
    body?: unknown,
    opts?: UseFetchOptions<T>,
  ): Promise<T> {
    return $fetch<T>(url, {
      baseURL,
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body,
      ...opts,
    })
  }

  /**
   * DELETE a resource from the backend.
   */
  async function del<T>(url: string, opts?: UseFetchOptions<T>): Promise<T> {
    return $fetch<T>(url, {
      baseURL,
      method: 'DELETE',
      ...opts,
    })
  }

  return { get, post, put, del, baseURL }
}
