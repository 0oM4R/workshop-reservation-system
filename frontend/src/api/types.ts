/** A workshop as listed by `GET /api/workshops`. */
export interface Workshop {
  id: number
  title: string
  description: string
  starts_at: string
  capacity: number
  remaining: number
}

/** The seat held after `POST /api/workshops/{id}/reservations`. */
export interface Reservation {
  id: number
  workshop_id: number
  name: string
  remaining: number
}

/** The answer to a cancellation, the same whether or not a seat was held. */
export interface CancelResult {
  message: string
}

/** One `GET /api/events` message: a workshop's remaining seats changed. */
export interface SeatsChanged {
  workshop_id: number
  remaining: number
}

/** How `GET /api/workshops/search` ranks: by shared words, by meaning, or both combined. */
export type SearchMode = 'hybrid' | 'keyword' | 'semantic'
