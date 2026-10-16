import { describe, expect, it } from 'vitest'
import { reserveSchema } from './schemas'

describe('reserveSchema', () => {
  it('trims the name and the email', () => {
    const result = reserveSchema.safeParse({ name: '  Ada ', email: ' ada@example.com ' })

    expect(result.data).toEqual({ name: 'Ada', email: 'ada@example.com' })
  })

  it.each([
    ['empty name', { name: '', email: 'ada@example.com' }],
    ['blank name', { name: '   ', email: 'ada@example.com' }],
    ['name over the limit', { name: 'x'.repeat(101), email: 'ada@example.com' }],
    ['malformed email', { name: 'Ada', email: 'not-an-email' }],
    ['missing email', { name: 'Ada', email: '' }],
  ])('rejects %s', (_label, input) => {
    expect(reserveSchema.safeParse(input).success).toBe(false)
  })
})
