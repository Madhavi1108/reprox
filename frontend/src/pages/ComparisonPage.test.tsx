import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ComparisonPage } from './ComparisonPage'

// Real accessibility bug found live during the real-Chrome E2E pass: the
// advanced provenance JSON textareas had a visible <label> with no
// htmlFor/id association at all - not just missing an aria-label (the
// Projects/Experiments forms' earlier gap), but zero programmatic
// association, so getByLabel() couldn't find them and a screen reader
// user would get no announced name for either field. Fixed by adding
// matching htmlFor/id pairs.
describe('ComparisonPage accessibility', () => {
  it('associates real labels with the base/compare run ID fields and the advanced provenance textareas', async () => {
    const user = userEvent.setup()
    render(<ComparisonPage />)

    expect(screen.getByLabelText(/base run id/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/compare run id/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /show advanced provenance payloads/i }))

    expect(screen.getByLabelText(/base provenance json/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/compare provenance json/i)).toBeInTheDocument()
  })
})
