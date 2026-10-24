import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000,
})

// Request interceptor for correlation IDs
api.interceptors.request.use((config) => {
  const requestId = crypto.randomUUID()
  config.headers['X-Request-ID'] = requestId
  return config
})

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Server responded with error status
      const message = error.response.data?.detail?.error || error.response.data?.message || error.message
      return Promise.reject(new Error(message))
    } else if (error.request) {
      // Network error
      return Promise.reject(new Error('Network error - please check your connection'))
    } else {
      // Other error
      return Promise.reject(new Error(error.message))
    }
  }
)

export const chatAPI = {
  sendMessage: (message, conversationId, portfolioContext) =>
    api.post('/chat', {
      message,
      conversation_id: conversationId,
      portfolio_context: portfolioContext,
    }),

  getConversation: (conversationId) =>
    api.get(`/conversations/${conversationId}`),

  deleteConversation: (conversationId) =>
    api.delete(`/conversations/${conversationId}`),
}

export const portfolioAPI = {
  analyze: (holdings, investmentHorizon = 'medium', riskProfile = 'moderate') =>
    api.post('/portfolio/analyze', {
      holdings,
      investment_horizon: investmentHorizon,
      risk_profile: riskProfile,
    }),
}

export const screeningAPI = {
  run: (filters, maxResults = 20) =>
    api.post('/screening/run', {
      filters,
      max_results: maxResults,
    }),
}

export const researchAPI = {
  run: (ticker, companyName, includeQuantData, investmentHorizon = 'medium', riskProfile = 'moderate') =>
    api.post('/research/run', {
      ticker,
      company_name: companyName,
      include_quant_data: includeQuantData,
      investment_horizon: investmentHorizon,
      risk_profile: riskProfile,
    }),
}

export const healthAPI = {
  check: () => api.get('/health'),
  ready: () => api.get('/ready'),
}

export default api