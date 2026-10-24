import React, { useState, useEffect, useRef } from 'react'
import {
  Send, Bot, User, Loader2, AlertCircle, CheckCircle,
  TrendingUp, TrendingDown, BarChart2, FileText, Settings,
  X, Plus, Minus, Copy, Download, Menu, ChevronDown
} from 'lucide-react'
import { chatAPI, portfolioAPI, screeningAPI, researchAPI, healthAPI } from './api'
import './styles.css'

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [showPortfolio, setShowPortfolio] = useState(false)
  const [portfolioHoldings, setPortfolioHoldings] = useState([{ ticker: '', shares: '', price: '' }])
  const [investmentHorizon, setInvestmentHorizon] = useState('medium')
  const [riskProfile, setRiskProfile] = useState('moderate')
  const [screeningResults, setScreeningResults] = useState(null)
  const [researchResults, setResearchResults] = useState(null)
  const [activeTab, setActiveTab] = useState('chat')
  const [error, setError] = useState(null)
  const [healthStatus, setHealthStatus] = useState(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Check health on mount
  useEffect(() => {
    healthAPI.check()
      .then(res => setHealthStatus(res.data))
      .catch(() => setHealthStatus({ status: 'unhealthy' }))
  }, [])

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = input
    setInput('')
    setIsLoading(true)
    setError(null)

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: userMessage, type: 'text' }])

    try {
      const response = await chatAPI.sendMessage(userMessage, conversationId)
      const { message, conversation_id, message_type, metadata, requires_clarification, clarification_questions, suggested_actions } = response.data

      if (conversation_id && !conversationId) {
        setConversationId(conversation_id)
      }

      // Add assistant message
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: message,
        type: message_type,
        metadata,
        requires_clarification,
        clarification_questions,
        suggested_actions,
      }])

      // Handle special message types
      if (metadata?.classification?.action === 'portfolio_analysis' && !requires_clarification) {
        setShowPortfolio(true)
      }
    } catch (err) {
      setError(err.message)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err.message}`,
        type: 'error',
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handlePortfolioAnalyze = async () => {
    const validHoldings = portfolioHoldings.filter(h => h.ticker && h.shares && h.price)
    if (validHoldings.length === 0) {
      setError('Please add at least one holding')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const holdings = validHoldings.map(h => ({
        ticker: h.ticker.toUpperCase(),
        shares: parseFloat(h.shares),
        avg_purchase_price: parseFloat(h.price),
      }))

      const response = await portfolioAPI.analyze(holdings, investmentHorizon, riskProfile)
      const report = generatePortfolioReport(response.data)
      
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: report,
        type: 'portfolio_analysis',
        metadata: { portfolio_analysis: response.data },
      }])
      setShowPortfolio(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleScreening = async (filters) => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await screeningAPI.run(filters)
      setScreeningResults(response.data)
      setActiveTab('screening')
      
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Found ${response.data.total_returned} stocks matching your criteria.`,
        type: 'screening_result',
        metadata: { screening: response.data },
      }])
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleResearch = async (ticker) => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await researchAPI.run(ticker)
      setResearchResults(response.data)
      setActiveTab('research')
      
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Research completed for ${response.data.company_name} (${ticker}).`,
        type: 'research_report',
        metadata: { research: response.data },
      }])
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const addHolding = () => {
    setPortfolioHoldings([...portfolioHoldings, { ticker: '', shares: '', price: '' }])
  }

  const removeHolding = (index) => {
    if (portfolioHoldings.length > 1) {
      setPortfolioHoldings(portfolioHoldings.filter((_, i) => i !== index))
    }
  }

  const updateHolding = (index, field, value) => {
    setPortfolioHoldings(portfolioHoldings.map((h, i) => 
      i === index ? { ...h, [field]: value } : h
    ))
  }

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
  }

  const downloadReport = (content, filename) => {
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const renderMessage = (msg, index) => {
    const isUser = msg.role === 'user'
    const bubbleClass = isUser ? 'message-user' : 'message-assistant'
    
    let content = (
      <div className="message-bubble" dangerouslySetInnerHTML={{ __html: formatMessage(msg.content) }} />
    )

    if (msg.type === 'portfolio_analysis' && msg.metadata?.portfolio_analysis) {
      content = (
        <div className="report-container">
          <pre className="report-text">{msg.content}</pre>
          <div className="report-actions">
            <button onClick={() => copyToClipboard(msg.content)} className="btn-secondary">
              <Copy size={14} /> Copy
            </button>
            <button onClick={() => downloadReport(msg.content, 'portfolio-analysis.txt')} className="btn-secondary">
              <Download size={14} /> Download
            </button>
          </div>
        </div>
      )
    }

    if (msg.type === 'screening_result' && msg.metadata?.screening) {
      content = (
        <div className="report-container">
          <ScreeningTable data={msg.metadata.screening.stocks} />
        </div>
      )
    }

    if (msg.type === 'research_report' && msg.metadata?.research) {
      content = (
        <div className="report-container">
          <pre className="report-text">{generateResearchReport(msg.metadata.research)}</pre>
          <div className="report-actions">
            <button onClick={() => copyToClipboard(msg.content)} className="btn-secondary">
              <Copy size={14} /> Copy
            </button>
            <button onClick={() => downloadReport(msg.content, `research-${msg.metadata.research.ticker}.txt`)} className="btn-secondary">
              <Download size={14} /> Download
            </button>
          </div>
        </div>
      )
    }

    if (msg.requires_clarification) {
      content = (
        <div>
          <div className="message-bubble" dangerouslySetInnerHTML={{ __html: formatMessage(msg.content) }} />
          <div className="clarification">
            <p><strong>I need more information:</strong></p>
            <ul>
              {msg.clarification_questions?.map((q, i) => <li key={i}>{q}</li>)}
            </ul>
          </div>
        </div>
      )
    }

    return (
      <div key={index} className={`message ${bubbleClass}`}>
        <div className="message-avatar">
          {isUser ? <User size={20} /> : <Bot size={20} />}
        </div>
        <div className="message-content">{content}</div>
      </div>
    )
  }

  const formatMessage = (text) => {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br/>')
      .replace(/•/g, '&#8226;')
  }

  const generatePortfolioReport = (data) => {
    const p = data.portfolio
    let report = `PORTFOLIO ANALYSIS REPORT\n${'='.repeat(50)}\n`
    report += `Generated: ${new Date(p.data_timestamp).toLocaleString()}\n`
    report += `Data Source: ${p.data_source}\n\n`
    report += `Total Invested: ₹${p.total_invested.toLocaleString()}\n`
    if (p.total_market_value) {
      report += `Current Value: ₹${p.total_market_value.toLocaleString()}\n`
      report += `Unrealized P&L: ₹${p.total_unrealized_pnl.toLocaleString()} (${p.total_unrealized_pnl_pct.toFixed(2)}%)\n`
    }
    report += `\nHOLDINGS:\n${'-'.repeat(30)}\n`
    
    p.holdings.forEach(h => {
      report += `\n${h.ticker}:\n`
      report += `  Shares: ${h.shares}\n`
      report += `  Avg Buy: ₹${h.avg_purchase_price}\n`
      report += `  Invested: ₹${h.investment_value().toLocaleString()}\n`
      if (h.price_available) {
        report += `  Current: ₹${h.current_price}\n`
        report += `  Value: ₹${h.market_value.toLocaleString()}\n`
        report += `  P&L: ₹${h.unrealized_pnl.toLocaleString()} (${h.unrealized_pnl_pct.toFixed(2)}%)\n`
        report += `  Weight: ${h.weight_pct.toFixed(2)}%\n`
      } else {
        report += `  Current: N/A\n`
      }
    })
    
    if (data.concentration_analysis) {
      const c = data.concentration_analysis
      report += `\n\nCONCENTRATION:\n${'-'.repeat(30)}\n`
      report += `Top 5: ${c.top_5_concentration_pct}%\n`
      report += `Top 10: ${c.top_10_concentration_pct}%\n`
      report += `HHI: ${c.hhi}\n`
      report += `Level: ${c.concentration_level}\n`
    }
    
    return report
  }

  const generateResearchReport = (data) => {
    let report = `DEEP RESEARCH REPORT\n${'='.repeat(50)}\n`
    report += `Company: ${data.company_name} (${data.ticker})\n`
    report += `Generated: ${new Date(data.research_timestamp).toLocaleString()}\n`
    report += `Model: ${data.model_used}\n\n`
    
    const sections = [
      ['COMPANY OVERVIEW', data.company_overview],
      ['BULL THESIS', data.bull_thesis],
      ['BEAR THESIS', data.bear_thesis],
      ['FINANCIAL STRENGTHS', data.financial_strengths],
      ['RISKS & UNCERTAINTIES', data.risks_and_uncertainties],
    ]
    
    if (data.valuation_observations) {
      sections.push(['VALUATION OBSERVATIONS', data.valuation_observations])
    }
    
    sections.forEach(([title, section]) => {
      report += `\n${title}\n${'-'.repeat(30)}\n`
      report += `Confidence: ${(section.confidence * 100).toFixed(0)}%\n\n`
      report += `${section.content}\n`
    })
    
    return report
  }

  const ScreeningTable = ({ data }) => (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Ticker</th>
            <th>Name</th>
            <th>Sector</th>
            <th>Price</th>
            <th>P/E</th>
            <th>Market Cap</th>
            <th>52W High %</th>
            <th>SMA 50</th>
            <th>SMA 200</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody>
          {data.slice(0, 20).map((stock, i) => (
            <tr key={stock.ticker} onClick={() => handleResearch(stock.ticker)} style={{ cursor: 'pointer' }}>
              <td>{i + 1}</td>
              <td><strong>{stock.ticker}</strong></td>
              <td>{stock.name || '-'}</td>
              <td>{stock.sector || '-'}</td>
              <td>{stock.current_price ? `₹${stock.current_price.toLocaleString()}` : '-'}</td>
              <td>{stock.pe_ratio ? stock.pe_ratio.toFixed(2) : '-'}</td>
              <td>{stock.market_cap ? `₹${(stock.market_cap / 1e7).toFixed(0)}Cr` : '-'}</td>
              <td>{stock.distance_from_52w_high_pct !== null ? `${stock.distance_from_52w_high_pct.toFixed(1)}%` : '-'}</td>
              <td>{stock.price_above_sma_50 !== null ? (stock.price_above_sma_50 ? '✓' : '✗') : '-'}</td>
              <td>{stock.price_above_sma_200 !== null ? (stock.price_above_sma_200 ? '✓' : '✗') : '-'}</td>
              <td><strong>{stock.score.toFixed(1)}</strong></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <TrendingUp size={28} />
            <span>FinancePilot AI</span>
          </div>
          <div className="status-badge" style={{ background: healthStatus?.gemini_configured ? '#10b981' : '#f59e0b' }}>
            {healthStatus?.gemini_configured ? 'AI Ready' : 'AI Limited'}
          </div>
        </div>
        <div className="header-right">
          <button className="icon-btn" onClick={() => setActiveTab('chat')} title="Chat">
            <Bot size={20} />
          </button>
          <button className="icon-btn" onClick={() => setShowPortfolio(true)} title="Portfolio">
            <BarChart2 size={20} />
          </button>
          <button className="icon-btn" onClick={() => handleScreening({})} title="Screening">
            <FileText size={20} />
          </button>
        </div>
      </header>

      <div className="main">
        <aside className="sidebar" style={{ display: activeTab !== 'chat' ? 'block' : 'none' }}>
          <div className="sidebar-tabs">
            <button className={activeTab === 'chat' ? 'active' : ''} onClick={() => setActiveTab('chat')}>
              <Bot size={16} /> Chat
            </button>
            <button className={activeTab === 'screening' ? 'active' : ''} onClick={() => setActiveTab('screening')}>
              <FileText size={16} /> Screening
            </button>
            <button className={activeTab === 'research' ? 'active' : ''} onClick={() => setActiveTab('research')}>
              <TrendingUp size={16} /> Research
            </button>
          </div>
          
          {activeTab === 'screening' && screeningResults && (
            <div className="sidebar-content">
              <h3>Screening Results</h3>
              <ScreeningTable data={screeningResults.stocks} />
            </div>
          )}
          
          {activeTab === 'research' && researchResults && (
            <div className="sidebar-content">
              <h3>Research: {researchResults.company_name}</h3>
              <pre className="report-text">{generateResearchReport(researchResults)}</pre>
            </div>
          )}
        </aside>

        <main className="chat-area">
          {showPortfolio && (
            <div className="portfolio-modal-overlay" onClick={() => setShowPortfolio(false)}>
              <div className="portfolio-modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                  <h2><BarChart2 size={20} /> Portfolio Analysis</h2>
                  <button className="icon-btn" onClick={() => setShowPortfolio(false)}><X size={20} /></button>
                </div>
                <div className="modal-body">
                  <div className="form-group">
                    <label>Investment Horizon</label>
                    <select value={investmentHorizon} onChange={(e) => setInvestmentHorizon(e.target.value)}>
                      <option value="short">Short &lt; 1 year)</option>
                      <option value="medium">Medium (1-3 years)</option>
                    </select>
                      <option value="long">Long &gt; 3 years)</option>
                  </div>
                  <div className="form-group">
                    <label>Risk Profile</label>
                    <select value={riskProfile} onChange={(e) => setRiskProfile(e.target.value)}>
                      <option value="conservative">Conservative</option>
                      <option value="moderate">Moderate</option>
                      <option value="aggressive">Aggressive</option>
                    </select>
                  </div>
                  <h3>Holdings</h3>
                  {portfolioHoldings.map((holding, index) => (
                    <div key={index} className="holding-row">
                      <input
                        placeholder="Ticker (e.g., RELIANCE.NS)"
                        value={holding.ticker}
                        onChange={(e) => updateHolding(index, 'ticker', e.target.value)}
                      />
                      <input
                        type="number"
                        placeholder="Shares"
                        value={holding.shares}
                        onChange={(e) => updateHolding(index, 'shares', e.target.value)}
                        min="0.01"
                        step="0.01"
                      />
                      <input
                        type="number"
                        placeholder="Avg Price (₹)"
                        value={holding.price}
                        onChange={(e) => updateHolding(index, 'price', e.target.value)}
                        min="0.01"
                        step="0.01"
                      />
                      {portfolioHoldings.length > 1 && (
                        <button className="icon-btn danger" onClick={() => removeHolding(index)}>
                          <X size={16} />
                        </button>
                      )}
                    </div>
                  ))}
                  <button className="btn-secondary" onClick={addHolding}>
                    <Plus size={16} /> Add Holding
                  </button>
                  <div className="modal-actions">
                    <button className="btn-secondary" onClick={() => setShowPortfolio(false)}>Cancel</button>
                    <button className="btn-primary" onClick={handlePortfolioAnalyze} disabled={isLoading}>
                      {isLoading ? <Loader2 size={16} className="spin" /> : 'Analyze Portfolio'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="messages" ref={messagesEndRef}>
            {messages.length === 0 && (
              <div className="welcome-message">
                <Bot size={48} className="welcome-icon" />
                <h2>Welcome to FinancePilot AI</h2>
                <p>Your multi-agent financial research assistant for Indian equities</p>
                <div className="suggestions">
                  <button onClick={() => setInput('Explain P/E ratio')}>What is P/E ratio?</button>
                  <button onClick={() => setInput('Analyze my portfolio with 10 RELIANCE.NS at 2450 and 5 TCS.NS at 3800')}>Analyze Portfolio</button>
                  <button onClick={() => setInput('Find stocks with P/E under 15')}>Screen Undervalued Stocks</button>
                  <button onClick={() => setInput('Research TCS.NS')}>Research TCS</button>
                </div>
              </div>
            )}
            {messages.map(renderMessage)}
            <div ref={messagesEndRef} />
          </div>

          {error && (
            <div className="error-banner">
              <AlertCircle size={20} />
              <span>{error}</span>
              <button onClick={() => setError(null)}><X size={16} /></button>
            </div>
          )}

          <form className="input-area" onSubmit={handleSend}>
            <div className="input-wrapper">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask me anything about finance, stocks, or your portfolio..."
                disabled={isLoading}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend(e)}
              />
              <button type="submit" disabled={!input.trim() || isLoading} className="send-btn">
                {isLoading ? <Loader2 size={20} className="spin" /> : <Send size={20} />}
              </button>
            </div>
            <p className="input-hint">
              Try: "Analyze my portfolio: 10 RELIANCE.NS @ 2450, 5 TCS.NS @ 3800" or "Explain P/E ratio"
            </p>
          </form>
        </main>
      </div>
    </div>
  )
}

export default App