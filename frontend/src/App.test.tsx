import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'

// Real bug found live: no catch-all route existed, so any unmatched
// path rendered a genuinely blank page (react-router renders nothing
// when no <Route> matches). Fixed by adding a `*` -> NotFoundPage route
// in App.tsx.
describe('App routing', () => {
  it('renders a real NotFound page for an unmatched route instead of a blank page', () => {
    render(
      <MemoryRouter initialEntries={['/this-route-does-not-exist']}>
        <App />
      </MemoryRouter>
    )
    expect(screen.getByText(/page not found/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to dashboard/i })).toHaveAttribute('href', '/')
  })

  it('renders the dashboard route without crashing', () => {
    // DashboardPage calls the real fetch-based API client on mount;
    // stub fetch so this stays a pure routing test, not an API test.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500, json: () => Promise.resolve({}) }))
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    )
    expect(screen.getAllByText('REPROX').length).toBeGreaterThan(0)
    vi.unstubAllGlobals()
  })
})
