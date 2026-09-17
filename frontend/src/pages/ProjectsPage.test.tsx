import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ProjectsPage } from './ProjectsPage'

// Real accessibility bug found live (Playwright + axe-shaped manual
// check): the Name/Slug/Description inputs relied on `placeholder` only,
// with no <label>/aria-label - not reliably announced by screen readers,
// and the placeholder itself disappears once text is entered. Fixed by
// adding <label htmlFor=...> to each field.
describe('ProjectsPage accessibility', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('associates a real label with the Name, Slug, and Description fields', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ items: [], total: 0, limit: 20, offset: 0 }) })
    )

    render(<ProjectsPage />)

    expect(screen.getByLabelText(/^name$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^slug$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^description$/i)).toBeInTheDocument()
  })
})
