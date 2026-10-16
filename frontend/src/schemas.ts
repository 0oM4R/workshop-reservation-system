import { z } from 'zod'

const NAME_MAX_LENGTH = 100

/** Mirrors the server's rules, only to give feedback before a request is sent. */
export const reserveSchema = z.object({
  name: z.string().trim().min(1, 'Enter your name').max(NAME_MAX_LENGTH, 'Name is too long'),
  email: z.string().trim().pipe(z.email('Enter a valid email address')),
})

export type ReserveValues = z.output<typeof reserveSchema>
