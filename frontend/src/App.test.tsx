import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('App', () => {
  it('renders the session shell', () => {
    render(<App />)

    expect(screen.getByRole('heading', { name: 'CodeLens' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Start a temporary session' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create session' })).toBeDisabled()
  })
})
