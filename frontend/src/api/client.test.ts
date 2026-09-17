import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, createProject } from './client'

describe('request() error parsing', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('extracts a readable message from FastAPI native validation-error responses', async () => {
    // Found live against the real backend: a Pydantic field_validator
    // failure (e.g. ProjectCreate's slug pattern) never goes through
    // app/core/errors.py's ReproxError handler, so it returns FastAPI's
    // own {"detail": [...]} shape, not {"error": {...}}. Before this fix,
    // every one of these fell through to a useless "Request failed with
    // status 422" with the real reason silently discarded.
    const fastApiBody = {
      detail: [
        {
          type: 'value_error',
          loc: ['body', 'slug'],
          msg: 'Value error, slug must be lowercase alphanumeric segments separated by hyphens',
        },
      ],
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: () => Promise.resolve(fastApiBody),
      })
    )

    await expect(createProject({ name: 'Test', slug: 'Not A Valid Slug!' })).rejects.toMatchObject({
      message: 'slug: Value error, slug must be lowercase alphanumeric segments separated by hyphens',
    })
  })

  it('still extracts the message from the app-level {error:{...}} shape (ReproxError handler)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: () =>
          Promise.resolve({ error: { code: 'conflict', message: "a project with slug 'x' already exists", details: {} } }),
      })
    )

    await expect(createProject({ name: 'Test', slug: 'x' })).rejects.toMatchObject({
      message: "a project with slug 'x' already exists",
    })
  })

  it('falls back to a generic message when the error body is neither shape', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.resolve({}),
      })
    )

    await expect(createProject({ name: 'Test', slug: 'x' })).rejects.toBeInstanceOf(ApiError)
    await expect(createProject({ name: 'Test', slug: 'x' })).rejects.toMatchObject({
      message: 'Request failed with status 500',
    })
  })
})
