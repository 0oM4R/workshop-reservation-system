import axios from 'axios'

const REQUEST_TIMEOUT_MS = 10_000
export const api = axios.create({ baseURL: '/api', timeout: REQUEST_TIMEOUT_MS })
