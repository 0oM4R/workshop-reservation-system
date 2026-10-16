import { expect, it } from 'vitest'
import { api } from './client'

it('limits API requests to ten seconds', () => {
  expect(api.defaults.timeout).toBe(10_000)
})
