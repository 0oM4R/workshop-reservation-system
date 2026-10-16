import { vi } from 'vitest'

/** Stand-in for the browser's `EventSource`; tests call its handlers by hand. */
export class FakeEventSource {
  static readonly CLOSED = 2
  static instances: FakeEventSource[] = []
  readyState = 0
  onopen: (() => void) | null = null
  onmessage: ((message: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  closed = false

  constructor(public url: string) {
    FakeEventSource.instances.push(this)
  }

  /** The stream opened most recently. */
  static get last(): FakeEventSource {
    const stream = FakeEventSource.instances.at(-1)
    if (!stream) throw new Error('No EventSource has been opened')
    return stream
  }

  close() {
    this.closed = true
  }
}

/** Replace the global `EventSource` with a fresh fake for one test. */
export function installFakeEventSource(): void {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
}
