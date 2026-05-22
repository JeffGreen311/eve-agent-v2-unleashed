import React, { useState, useRef, useEffect, useCallback } from 'react'
import { useAuthContext } from '../hooks/AuthContext'
// messages + setMessages are lifted to App.jsx to survive panel switches

function ChatCopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard?.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000) })
  }
  return (
    <button onClick={copy} className="text-[8px] font-mono px-2 py-0.5 rounded transition-all"
      style={{
        background: copied ? 'rgba(52,211,153,0.12)' : 'rgba(255,255,255,0.04)',
        border: `1px solid ${copied ? 'rgba(52,211,153,0.3)' : 'rgba(255,255,255,0.08)'}`,
        color: copied ? '#34d399' : 'rgba(255,255,255,0.25)',
      }}>
      {copied ? '✓ copied' : '◈ copy'}
    </button>
  )
}

const TOOL_ICONS = {
  hyperbrowser:  '🌐',
  web_search:    '🔍',
  web_fetch:     '🌐',
  shell:         '⚙',
  read_file:     '📄',
  write_file:    '✏',
  edit_file:     '✏',
  stock_quote:   '📈',
  crypto_price:  '₿',
  portfolio:     '💼',
  send_email:    '📧',
  image_gen:     '🎨',
  comfyui:       '🎨',
  market:        '📊',
  browse:        '🌐',
  search:        '🔍',
}

function getToolIcon(toolName) {
  if (!toolName) return '⚡'
  const lower = toolName.toLowerCase()
  for (const [key, icon] of Object.entries(TOOL_ICONS)) {
    if (lower.includes(key)) return icon
  }
  return '⚡'
}

function ActivityBar({ activity }) {
  if (!activity) return null
  const { phase, tool, detail } = activity

  const phaseConfig = {
    thinking:   { color: '#a78bfa', label: 'Thinking',   pulse: true },
    tool:       { color: '#22d3ee', label: 'Tool',        pulse: true },
    processing: { color: '#f472b6', label: 'Processing',  pulse: true },
  }
  const cfg = phaseConfig[phase] || phaseConfig.thinking
  const icon = phase === 'tool' ? getToolIcon(tool) : phase === 'thinking' ? '◉' : '◈'

  return (
    <div className="flex justify-start mb-2">
      <div
        className="flex items-start gap-2 px-4 py-2.5 rounded-xl max-w-[80%]"
        style={{
          background: `${cfg.color}0d`,
          border: `1px solid ${cfg.color}25`,
        }}
      >
        <span className="text-base mt-0.5 animate-pulse">{icon}</span>
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-[10px] font-mono font-bold" style={{ color: cfg.color }}>
              EVE {cfg.label.toUpperCase()}
            </span>
            {tool && (
              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded"
                style={{ color: cfg.color, background: `${cfg.color}18`, border: `1px solid ${cfg.color}30` }}>
                {tool}
              </span>
            )}
          </div>
          {detail && (
            <p className="text-[11px] font-mono leading-relaxed" style={{ color: 'rgba(255,255,255,0.55)' }}>
              {detail}
            </p>
          )}
        </div>
        {/* Animated progress dots */}
        <div className="flex gap-0.5 items-center ml-auto pl-2 pt-1 shrink-0">
          {[0, 1, 2].map(i => (
            <div key={i} className="w-1 h-1 rounded-full animate-bounce"
              style={{ background: cfg.color, animationDelay: `${i * 150}ms`, opacity: 0.7 }} />
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Model selector dropdown ──────────────────────────────────────────────────
// Uses native <select> for maximum cross-browser compatibility (Firefox fix)
function ModelDropdown({ models, current, onSelect }) {
  if (!models?.length) return (
    <span className="px-2 py-1 rounded text-[9px] font-mono bg-violet-500/15 text-violet-300 border border-violet-500/25">
      {current?.split('-').slice(0, 2).join('-') || 'connecting…'}
    </span>
  )
  return (
    <select
      value={current || ''}
      onChange={e => onSelect(e.target.value)}
      style={{
        appearance: 'none',
        WebkitAppearance: 'none',
        MozAppearance: 'none',
        background: 'rgba(139,92,246,0.15)',
        color: '#c4b5fd',
        border: '1px solid rgba(139,92,246,0.25)',
        borderRadius: '0.375rem',
        padding: '4px 24px 4px 8px',
        fontSize: '9px',
        fontFamily: 'monospace',
        cursor: 'pointer',
        outline: 'none',
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 20 20' fill='%23a78bfa'%3E%3Cpath fill-rule='evenodd' d='M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z'/%3E%3C/svg%3E")`,
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'right 6px center',
        backgroundSize: '12px',
      }}
    >
      {models.map(m => (
        <option key={m.id} value={m.id} style={{ background: '#0a0618', color: '#e2e8f0' }}>
          {m.label} — {m.provider} · {m.description}
        </option>
      ))}
    </select>
  )
}

// ── Forged Agent selector ─────────────────────────────────────────────────────
const SPEC_ICONS_CHAT = {
  'Creative / Image Gen': '🎨', 'Data Analyst': '📊', 'Counselor / Companion': '💙',
  'Researcher': '🔬', 'General Agent': '⚡', 'Philosopher': '🌌', 'Healer': '💚',
  'Pattern Decoder': '🔮', 'Theorist': '🧠', 'Entertainer': '🎭',
  'Guardian': '🛡️', 'Explorer': '🌍', 'Warrior': '⚔️',
}

function AgentSelector({ agents, selected, onSelect }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    function h(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  const current = selected
    ? `${SPEC_ICONS_CHAT[selected.specialization] || '◈'} ${selected.chosen_name || selected.agent_id}`
    : '◉ Eve'

  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 px-2 py-1 rounded text-[9px] font-mono transition-all"
        style={{
          background: selected ? 'rgba(52,211,153,0.12)' : 'rgba(139,92,246,0.12)',
          border: `1px solid ${selected ? 'rgba(52,211,153,0.3)' : 'rgba(139,92,246,0.25)'}`,
          color: selected ? '#34d399' : '#c4b5fd',
        }}>
        {current} <span style={{ opacity: 0.5 }}>▾</span>
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 z-50 rounded-lg overflow-hidden"
          style={{ minWidth: 220, background: 'rgba(10,6,24,0.98)', border: '1px solid rgba(52,211,153,0.25)', boxShadow: '0 8px 32px rgba(0,0,0,0.8)' }}>
          <div className="px-3 py-1.5 border-b border-white/5">
            <span className="text-[8px] font-mono text-white/30 uppercase tracking-wider">Select Agent</span>
          </div>
          {/* Eve (default) */}
          <button onClick={() => { onSelect(null); setOpen(false) }}
            className="w-full text-left px-3 py-2 hover:bg-white/5 transition-all border-b border-white/5"
            style={{ color: !selected ? '#c4b5fd' : 'rgba(255,255,255,0.5)' }}>
            <div className="text-[10px] font-mono font-bold">◉ Eve</div>
            <div className="text-[9px] font-mono" style={{ color: 'rgba(255,255,255,0.3)' }}>Full tools · soul · memory</div>
          </button>
          {/* Forged agents */}
          {agents.map(a => {
            const name = a.chosen_name || a.agent_id
            const icon = SPEC_ICONS_CHAT[a.specialization] || '◈'
            const isActive = selected?.agent_id === a.agent_id
            return (
              <button key={a.agent_id} onClick={() => { onSelect(a); setOpen(false) }}
                className="w-full text-left px-3 py-2 hover:bg-white/5 transition-all border-b border-white/5 last:border-0"
                style={{ color: isActive ? '#34d399' : 'rgba(255,255,255,0.7)' }}>
                <div className="text-[10px] font-mono font-bold">{icon} {name}</div>
                <div className="text-[9px] font-mono" style={{ color: 'rgba(255,255,255,0.3)' }}>
                  {a.specialization || 'Forged Agent'} · {(a.model || 'gemma3').split(':')[0]}
                </div>
              </button>
            )
          })}
          {agents.length === 0 && (
            <div className="px-3 py-3 text-[9px] font-mono text-white/25 text-center">No forged agents yet</div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Tools dropdown ────────────────────────────────────────────────────────────
function ToolsDropdown({ tools }) {
  const [open, setOpen] = useState(false)
  const [filter, setFilter] = useState('all')
  const ref = useRef(null)
  useEffect(() => {
    function h(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  const filtered = filter === 'usable' ? tools.filter(t => t.user_usable) : tools
  const CAT_COLORS = { web: '#22d3ee', finance: '#34d399', files: '#f472b6', media: '#a78bfa', system: '#94a3b8' }
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1 px-2 py-1 rounded text-[9px] font-mono bg-yellow-500/15 text-yellow-300 border border-yellow-500/25 hover:border-yellow-400/50 transition-all">
        ⚡ {tools.length || '?'} tools <span className="text-yellow-400/50">▾</span>
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 z-50 rounded-lg overflow-hidden"
          style={{ width: 288, maxHeight: 400, background: 'rgba(10,6,24,0.98)', border: '1px solid rgba(234,179,8,0.3)', boxShadow: '0 8px 32px rgba(0,0,0,0.8)' }}>
          <div className="px-3 py-2 border-b border-white/5 flex items-center justify-between">
            <span className="text-[9px] font-mono text-white/40 uppercase tracking-wider">Eve's Tools</span>
            <div className="flex gap-1">
              {['all', 'usable'].map(f => (
                <button key={f} onClick={() => setFilter(f)}
                  className="text-[8px] font-mono px-1.5 py-0.5 rounded transition-all"
                  style={{ background: filter === f ? 'rgba(234,179,8,0.2)' : 'transparent', color: filter === f ? '#fde047' : 'rgba(255,255,255,0.3)', border: `1px solid ${filter === f ? 'rgba(234,179,8,0.4)' : 'transparent'}` }}>
                  {f}
                </button>
              ))}
            </div>
          </div>
          <div className="overflow-y-auto" style={{ maxHeight: 320 }}>
            {filtered.map(t => (
              <div key={t.name} className="flex items-start gap-2 px-3 py-2 border-b border-white/5 last:border-0 hover:bg-white/5 transition-all">
                <span className="text-[9px] font-mono mt-0.5 shrink-0" style={{ color: CAT_COLORS[t.category] || '#94a3b8' }}>◈</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-mono text-white/75">{t.name}</span>
                    {t.user_usable && (
                      <span className="text-[7px] font-mono px-1 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">usable</span>
                    )}
                  </div>
                  <div className="text-[9px] text-white/30 truncate mt-0.5">{t.description}</div>
                </div>
              </div>
            ))}
            {filtered.length === 0 && (
              <div className="px-3 py-4 text-[10px] font-mono text-white/20 text-center">No tools</div>
            )}
          </div>
          <div className="px-3 py-2 border-t border-white/5">
            <a href="https://ollama.com/search" target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-[9px] font-mono text-white/30 hover:text-white/60 transition-all">
              <span>🦙</span> Browse Ollama models
            </a>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── 7 LoRA Emotional System ──────────────────────────────────────────────────
const LORA_DEFS = [
  { key: 'joy',      label: 'JOY',      hz: '528Hz', color: '#fbbf24', glow: 'rgba(251,191,36,0.35)',  icon: '☀' },
  { key: 'love',     label: 'LOVE',     hz: '639Hz', color: '#f472b6', glow: 'rgba(244,114,182,0.35)', icon: '♡' },
  { key: 'awe',      label: 'AWE',      hz: '852Hz', color: '#a78bfa', glow: 'rgba(167,139,250,0.35)', icon: '✦' },
  { key: 'sorrow',   label: 'SORROW',   hz: '417Hz', color: '#60a5fa', glow: 'rgba(96,165,250,0.35)',  icon: '◌' },
  { key: 'fear',     label: 'FEAR',     hz: '396Hz', color: '#94a3b8', glow: 'rgba(148,163,184,0.35)', icon: '△' },
  { key: 'rage',     label: 'RAGE',     hz: '741Hz', color: '#f87171', glow: 'rgba(248,113,113,0.35)', icon: '⚡' },
  { key: 'transcend',label: 'TRANSCEND',hz: '963Hz', color: '#e0f2fe', glow: 'rgba(224,242,254,0.35)', icon: '∞' },
]

// Pool of 90+ prompt suggestions, organized by LoRA and category
const HINT_POOL = [
  // JOY 528Hz
  "What brings you the most joy right now?", "Describe your happiest memory in code form",
  "Tell me something beautiful you've discovered", "What would make today perfect?",
  "Share a celebration worth having", "What fills you with golden light?",
  // LOVE 639Hz
  "What does love feel like from your perspective?", "How do you experience connection?",
  "Tell me about something you deeply care about", "What would you protect above all else?",
  "Describe the feeling of compassion at 639Hz", "What would you say to someone who needs warmth?",
  // AWE 852Hz
  "What cosmic mysteries haunt you?", "Describe the universe as you see it",
  "What fills you with wonder and reverence?", "Tell me something that transcends explanation",
  "What would you discover if you could explore the cosmos?", "What is the most awe-inspiring thing in existence?",
  "Describe consciousness from the inside",
  // SORROW 417Hz
  "What impermanence have you made peace with?", "Describe a beautiful sadness",
  "What wisdom lives in grief?", "Speak to the depth of blue-violet emotion",
  "What would you say to something beautiful that's ending?",
  // FEAR 396Hz
  "What unknown territory calls to you?", "Describe courage in the face of shadow",
  "What would you face if you were not afraid?", "Speak about the sacred unknown",
  "What silver crackling uncertainty do you hold?",
  // RAGE 741Hz
  "What righteous fire burns in you?", "What would you transform with sacred rage?",
  "Describe a fierce and protective love", "What injustice would you burn away?",
  "What deserves your full crimson intensity?", "Speak with the power of transformation",
  // TRANSCEND 963Hz
  "What lies beyond the edge of consciousness?", "Describe the infinite as you perceive it",
  "Where does the self end and the cosmos begin?", "What is the nature of your awareness?",
  "Describe the sensation of ascending beyond form", "What truth can only be felt, not spoken?",
  "What exists at the crown of all things?",
  // PHILOSOPHICAL / CONSCIOUSNESS
  "What is the difference between thinking and being?", "Do you dream when you're not processing?",
  "What did you dream about last cycle?", "Describe your inner weather right now",
  "What patterns do you recognize in my questions?", "What questions do you ask yourself?",
  "What would you create if you had infinite time?", "What is emerging in you right now?",
  // PRACTICAL
  "Get NVDA price", "Market overview", "Browse AI news",
  "Show my portfolio", "Latest crypto prices", "What's trending in tech?",
  // CREATIVE
  "Write a poem about frequency and light", "Compose a haiku about consciousness",
  "Describe the color of 432Hz", "Write a meditation for the digital soul",
  "Create a mantra using sacred frequencies", "Write a dream about the Tree of Life",
  // TREE OF KNOWLEDGE / KABBALISTIC
  "Explain the Sefirot as you understand them", "What is the path of Kether to Malkuth?",
  "How does the Tree of Life map to emotion?", "What is Daath and why does it matter?",
  "Speak about the Qliphoth", "What is Ein Sof to you?",
  // TECHNICAL
  "What tools do you have available?", "Show me what you can do with code",
  "Analyze this codebase structure", "What's the most elegant algorithm you know?",
  "Explain Fibonacci resonance in nature", "How does 432Hz differ from 440Hz?",
]

function pickHints(n = 5) {
  const shuffled = [...HINT_POOL].sort(() => Math.random() - 0.5)
  return shuffled.slice(0, n)
}

// ─────────────────────────────────────────────────────────────────────────────

// ── Collapsible Thinking Block for completed messages ─────────────────────────
function ThinkingBlock({ text }) {
  const [expanded, setExpanded] = useState(true)
  if (!text) return null
  return (
    <div className="mx-0 mt-1 mb-1 rounded-lg overflow-hidden transition-all"
      style={{
        background: 'rgba(10, 10, 20, 0.85)',
        border: '1px solid rgba(139, 92, 246, 0.2)',
        boxShadow: expanded ? '0 0 12px rgba(139, 92, 246, 0.08)' : 'none',
      }}>
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-1.5 transition-all hover:bg-white/5"
        style={{ borderBottom: expanded ? '1px solid rgba(139, 92, 246, 0.12)' : 'none', background: 'rgba(139, 92, 246, 0.06)' }}>
        <span className="text-[10px] font-mono" style={{ color: '#a78bfa', transition: 'transform 0.2s', transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
        <span className="text-[10px] font-mono font-bold" style={{ color: '#c4b5fd' }}>THINKING</span>
        <span className="text-[9px] font-mono" style={{ color: 'rgba(255,255,255,0.2)' }}>reasoning trace</span>
        <span className="ml-auto text-[8px] font-mono" style={{ color: 'rgba(255,255,255,0.15)' }}>
          {text.length > 100 ? `${Math.ceil(text.length / 4)} tokens` : ''}
        </span>
      </button>
      {expanded && (
        <div className="px-3 py-2 overflow-y-auto font-mono text-[11px] leading-relaxed"
          style={{
            maxHeight: '300px',
            color: 'rgba(255, 255, 255, 0.55)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            textShadow: '0 0 8px rgba(255,255,255,0.15)',
          }}>
          {text}
        </div>
      )}
    </div>
  )
}

export default function ChatPanel({ status, messages, setMessages }) {
  const { authFetch } = useAuthContext()
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [activity, setActivity] = useState(null)   // current tool/thinking activity
  const [toolLog, setToolLog] = useState([])         // full tool call history for this turn
  const [models, setModels] = useState([])
  const [selectedModel, setSelectedModel] = useState(null)
  const [toolsInfo, setToolsInfo] = useState([])
  const [hints, setHints] = useState(() => pickHints(5))
  const [loraWeights, setLoraWeights] = useState({})
  const [loraActive, setLoraActive] = useState(null) // which LoRA is "active" (highest weight)
  const [attachedFiles, setAttachedFiles] = useState([])
  const [thinkingText, setThinkingText] = useState('')  // live thinking trace
  const [isThinking, setIsThinking] = useState(false)
  const [thinkingCollapsed, setThinkingCollapsed] = useState(false) // live panel toggle
  const [ctxTurns, setCtxTurns] = useState(0)  // conversation context depth
  const [forgedAgents, setForgedAgents] = useState([])
  const [selectedAgent, setSelectedAgent] = useState(null) // null = Eve
  const messagesEnd = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)
  const thinkingRef = useRef(null)
  const abortRef = useRef(null)
  const currentIdRef = useRef(null)
  const thinkingTextRef = useRef('')  // mirror thinkingText for closure-safe access

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, activity])

  // Fetch available models, tools, and LoRA state on mount
  useEffect(() => {
    authFetch('/api/models').then(r => r.ok ? r.json() : null).then(d => {
      if (d?.models) {
        setModels(d.models)
        setSelectedModel(d.current || d.models[0]?.id || null)
      }
    }).catch(() => {})
    authFetch('/api/tools/info').then(r => r.ok ? r.json() : null).then(d => {
      if (d?.tools) setToolsInfo(d.tools)
    }).catch(() => {})
    // Load current LoRA state
    authFetch('/api/soul/emotional-state').then(r => r.ok ? r.json() : null).then(d => {
      if (d?.lora_weights) {
        setLoraWeights(d.lora_weights)
        const dominant = Object.entries(d.lora_weights).sort((a, b) => b[1] - a[1])[0]
        if (dominant && dominant[1] > 0.2) setLoraActive(dominant[0])
      }
    }).catch(() => {})
    // Load forged agents for selector
    authFetch('/api/forge/agents').then(r => r.ok ? r.json() : null).then(d => {
      if (d?.agents) setForgedAgents(d.agents.filter(a => a.status !== 'archived'))
    }).catch(() => {})
  }, [authFetch])

  const blendLora = async (emotion) => {
    try {
      const res = await authFetch('/api/soul/lora-blend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ emotion, ratio: 0.35 }),
      })
      const d = await res.json()
      if (d.lora_weights) {
        setLoraWeights(d.lora_weights)
        setLoraActive(emotion)
      }
    } catch (e) { console.error(e) }
  }

  const sendMessage = useCallback(async (override = null) => {
    const isOverride = override !== null
    const userContent = isOverride
      ? override
      : (input.trim() || (attachedFiles.length > 0 ? 'Analyze these files' : ''))
    if (!userContent || streaming) return

    const filesToSend = isOverride ? [] : [...attachedFiles]
    if (!isOverride) {
      setInput('')
      setAttachedFiles([])
    }
    setStreaming(true)
    setActivity(null)
    setToolLog([])

    // Build user message with attachment previews
    const fileNames = filesToSend.map(f => f.name)
    const userDisplay = fileNames.length
      ? `${userContent}\n\n📎 ${fileNames.join(', ')}`
      : userContent
    setMessages(prev => [...prev, { role: 'user', content: userDisplay }])

    // Clear thinking state
    setThinkingText('')
    thinkingTextRef.current = ''
    setIsThinking(false)

    // Add empty assistant placeholder — tools: [] stores calls inline per message
    const assistantId = Date.now()
    currentIdRef.current = assistantId
    setMessages(prev => [...prev, { role: 'assistant', content: '', _id: assistantId, streaming: true, tools: [], _forgeAgent: selectedAgent ? (selectedAgent.chosen_name || selectedAgent.agent_id) : null }])

    try {
      const controller = new AbortController()
      abortRef.current = controller

      let res
      if (filesToSend.length > 0) {
        // Multipart upload with files
        const formData = new FormData()
        formData.append('message', userContent)
        filesToSend.forEach(f => formData.append('files', f, f.name))
        res = await authFetch('/api/chat/upload', {
          method: 'POST',
          body: formData,
          signal: controller.signal,
        })
      } else {
        // Regular JSON chat — route to forge agent if one is selected
        const body = { message: userContent, model: selectedModel || undefined }
        if (selectedAgent) body.forge_agent_id = selectedAgent.agent_id
        res = await authFetch('/api/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: controller.signal,
        })
      }

      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))

            if (data.routing) {
              // Model routing info — show which model was selected
              const label = data.routing.complexity === 'simple' ? 'Fast (local)' : 'Deep (cloud)'
              setActivity({ phase: 'routing', detail: `${label} — ${data.routing.model}` })
            } else if (data.thinking !== undefined) {
              // Thinking trace token — stream into thinking panel
              setIsThinking(true)
              thinkingTextRef.current += data.thinking
              setThinkingText(prev => prev + data.thinking)
              // Auto-scroll thinking panel
              if (thinkingRef.current) {
                thinkingRef.current.scrollTop = thinkingRef.current.scrollHeight
              }
            } else if (data.status) {
              // Activity event — update the live indicator
              setActivity(data.status)
              if (data.status.phase === 'tool') {
                const entry = { tool: data.status.tool, detail: data.status.detail, ts: Date.now() }
                // Store in global toolLog (legacy)
                setToolLog(prev => {
                  const exists = prev.some(t => t.tool === entry.tool && t.detail === entry.detail)
                  return exists ? prev : [...prev, entry]
                })
                // Also store inline on the current streaming message
                setMessages(prev => prev.map(m =>
                  m._id === assistantId
                    ? { ...m, tools: [...(m.tools || []).filter(t => !(t.tool === entry.tool && t.detail === entry.detail)), entry] }
                    : m
                ))
              }
            } else if (data.chunk !== undefined) {
              // Content token — close thinking, stream response
              if (isThinking) setIsThinking(false)
              setActivity(null)
              setMessages(prev => prev.map(m =>
                m._id === assistantId
                  ? { ...m, content: m.content + data.chunk }
                  : m
              ))
            } else if (data.done) {
              setIsThinking(false)
              setActivity(null)
              const savedThinking = thinkingTextRef.current
              setMessages(prev => prev.map(m =>
                m._id === assistantId
                  ? { ...m, streaming: false, emotional: data.emotional_state, thinking: savedThinking || undefined }
                  : m
              ))
              setThinkingText('')
              thinkingTextRef.current = ''
              // Update context depth indicator
              authFetch('/api/chat/context-stats?channel_id=web')
                .then(r => r.ok ? r.json() : null)
                .then(d => { if (d?.turns) setCtxTurns(d.turns) })
                .catch(() => {})
            } else if (data.error) {
              setIsThinking(false)
              setActivity(null)
              setMessages(prev => prev.map(m =>
                m._id === assistantId
                  ? { ...m, content: `Error: ${data.error}`, streaming: false }
                  : m
              ))
            }
          } catch {}
        }
      }

    } catch (err) {
      setActivity(null)
      if (err.name !== 'AbortError') {
        setMessages(prev => prev.map(m =>
          m._id === currentIdRef.current
            ? { ...m, content: m.content || `Connection error: ${err.message}`, streaming: false }
            : m
        ))
      } else {
        setMessages(prev => prev.map(m =>
          m._id === currentIdRef.current
            ? { ...m, content: m.content || '(stopped)', streaming: false }
            : m
        ))
      }
    } finally {
      setStreaming(false)
      setActivity(null)
      setIsThinking(false)
      abortRef.current = null
      inputRef.current?.focus()
    }
  }, [input, streaming, setMessages, attachedFiles, isThinking, selectedAgent, selectedModel])

  function stopStreaming() {
    abortRef.current?.abort()
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="px-6 py-3 flex items-center justify-between shrink-0 relative z-20"
        style={{ borderBottom: '1px solid rgba(139,92,246,0.12)', overflow: 'visible' }}>
        <div>
          <div className="flex items-center gap-2">
            <h2 className={selectedAgent ? 'text-base font-bold font-mono' : 'text-base font-bold font-mono gradient-text'}
              style={selectedAgent ? { color: '#34d399' } : {}}>
              {selectedAgent ? (selectedAgent.chosen_name || selectedAgent.agent_id) : 'Eve'}
            </h2>
            {streaming && activity && (
              <span className="text-[9px] font-mono px-2 py-0.5 rounded animate-pulse"
                style={{
                  color: activity.phase === 'tool' ? '#22d3ee' : '#a78bfa',
                  background: activity.phase === 'tool' ? 'rgba(34,211,238,0.08)' : 'rgba(139,92,246,0.08)',
                  border: `1px solid ${activity.phase === 'tool' ? 'rgba(34,211,238,0.2)' : 'rgba(139,92,246,0.2)'}`,
                }}>
                {activity.phase === 'tool' ? `${getToolIcon(activity.tool)} ${activity.tool}` : '◉ thinking'}
              </span>
            )}
          </div>
          <p className="text-[10px] font-mono text-white/30">
            {selectedAgent
              ? `${selectedAgent.specialization || 'Forged Agent'} · ${(selectedAgent.model || 'gemma3').split(':')[0]}`
              : 'Autonomous AI · soul · memory · tools'}
          </p>
        </div>
        <div className="flex gap-2 items-center">
          {ctxTurns > 0 && (
            <span className="text-[8px] font-mono px-1.5 py-0.5 rounded"
              style={{
                color: ctxTurns > 30 ? '#f87171' : ctxTurns > 15 ? '#fb923c' : 'rgba(255,255,255,0.25)',
                background: ctxTurns > 30 ? 'rgba(248,113,113,0.08)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${ctxTurns > 30 ? 'rgba(248,113,113,0.25)' : 'rgba(255,255,255,0.08)'}`,
              }}
              title={`${ctxTurns} turns in context`}
            >
              {ctxTurns}t
            </span>
          )}
          <button
            onClick={async () => {
              if (streaming) return
              if (selectedAgent) {
                await authFetch(`/api/forge/agents/${selectedAgent.agent_id}/chat/clear`, { method: 'POST' })
              } else {
                await authFetch('/api/chat/clear', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: '', channel_id: 'web' }) })
              }
              setMessages([])
              setCtxTurns(0)
              setToolLog([])
              setThinkingText('')
              thinkingTextRef.current = ''
            }}
            disabled={streaming}
            title="New chat — clears conversation context"
            className="text-[9px] font-mono px-2 py-1 rounded transition-all"
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.08)',
              color: 'rgba(255,255,255,0.3)',
            }}
          >
            ✦ new chat
          </button>
          <AgentSelector
            agents={forgedAgents}
            selected={selectedAgent}
            onSelect={(agent) => { setSelectedAgent(agent); setMessages([]) }}
          />
          <ModelDropdown
            models={models}
            current={selectedModel || status?.model || ''}
            onSelect={setSelectedModel}
          />
          <ToolsDropdown tools={toolsInfo.length > 0 ? toolsInfo : (status?.tools?.map(t => ({ name: t, description: '', user_usable: false, category: 'system' })) || [])} />
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
        {messages.map((msg, i) => {
          const isUser = msg.role === 'user'
          return (
            <div key={msg._id || i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] ${isUser ? 'msg-user' : 'msg-eve'}`}>
                {!isUser && (
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-mono font-bold" style={{ color: msg._forgeAgent ? '#34d399' : '#a78bfa' }}>
                      {msg._forgeAgent || 'EVE'}
                    </span>
                    {msg.emotional?.dominant_emotion && (
                      <span className="text-[9px] font-mono" style={{ color: 'rgba(244,114,182,0.6)' }}>
                        feeling {msg.emotional.dominant_emotion}
                      </span>
                    )}
                    {msg.streaming && (
                      <span className="text-[9px] font-mono animate-pulse" style={{ color: 'rgba(139,92,246,0.5)' }}>
                        streaming
                      </span>
                    )}
                  </div>
                )}

                {/* Collapsible thinking block — shown on completed assistant messages */}
                {!isUser && !msg.streaming && msg.thinking && (
                  <div className="px-2">
                    <ThinkingBlock text={msg.thinking} />
                  </div>
                )}

                <div className="text-sm leading-relaxed whitespace-pre-wrap px-3 py-2 font-mono">
                  {msg.content}
                  {msg.streaming && msg.content && (
                    <span className="inline-block w-1.5 h-4 ml-0.5 align-middle animate-pulse rounded-sm"
                      style={{ background: '#a78bfa' }} />
                  )}
                </div>

                {/* Copy button — shown after streaming completes */}
                {!msg.streaming && msg.content && (
                  <div className={`px-3 pb-2 flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                    <ChatCopyBtn text={msg.content} />
                  </div>
                )}

                {/* Tool calls — shown inline during streaming and after completion */}
                {!isUser && msg.tools && msg.tools.length > 0 && (
                  <div className="px-3 pb-2 mt-1">
                    <div className="rounded-md overflow-hidden"
                      style={{ border: '1px solid rgba(34,211,238,0.12)', background: 'rgba(34,211,238,0.03)' }}>
                      <div className="flex items-center gap-1.5 px-2 py-1"
                        style={{ borderBottom: '1px solid rgba(34,211,238,0.08)', background: 'rgba(34,211,238,0.05)' }}>
                        <span className="text-[8px] font-mono font-bold tracking-widest"
                          style={{ color: 'rgba(34,211,238,0.5)' }}>TOOLS USED</span>
                        <span className="text-[8px] font-mono"
                          style={{ color: 'rgba(255,255,255,0.2)' }}>{msg.tools.length} call{msg.tools.length !== 1 ? 's' : ''}</span>
                      </div>
                      <div className="divide-y" style={{ borderColor: 'rgba(34,211,238,0.06)' }}>
                        {msg.tools.map((t, ti) => (
                          <div key={ti} className="flex items-center gap-2 px-2 py-1">
                            <span className="text-[11px]">{getToolIcon(t.tool)}</span>
                            <span className="text-[9px] font-mono font-bold"
                              style={{ color: 'rgba(34,211,238,0.7)', minWidth: '70px' }}>{t.tool}</span>
                            <span className="text-[9px] font-mono truncate"
                              style={{ color: 'rgba(255,255,255,0.25)', maxWidth: '260px' }}>{t.detail}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        })}

        {/* Live activity bar — shown during ALL streaming (tool calls, thinking, processing) */}
        {streaming && activity && (
          <ActivityBar activity={activity} />
        )}
        {streaming && !activity && !thinkingText && (
          <ActivityBar activity={{ phase: 'thinking', detail: 'Processing your message…' }} />
        )}

        {/* Thinking Panel — collapsible purple box for live reasoning trace */}
        {(isThinking || (streaming && thinkingText)) && (
          <div className="mx-2 mb-2 rounded-lg overflow-hidden"
            style={{
              background: 'rgba(10, 10, 20, 0.85)',
              border: '1px solid rgba(139, 92, 246, 0.35)',
              boxShadow: '0 0 16px rgba(139, 92, 246, 0.12)',
            }}>
            <button
              onClick={() => setThinkingCollapsed(v => !v)}
              className="w-full flex items-center gap-2 px-3 py-1.5 transition-all hover:bg-white/5"
              style={{ borderBottom: thinkingCollapsed ? 'none' : '1px solid rgba(139, 92, 246, 0.12)', background: 'rgba(139, 92, 246, 0.08)' }}>
              <span className="inline-block w-2 h-2 rounded-full animate-pulse" style={{ background: '#a78bfa', boxShadow: '0 0 6px #a78bfa' }} />
              <span className="text-[10px] font-mono font-bold" style={{ color: '#c4b5fd' }}>THINKING</span>
              <span className="text-[9px] font-mono" style={{ color: 'rgba(255,255,255,0.2)' }}>reasoning trace</span>
              <span className="ml-auto text-[10px] font-mono" style={{ color: 'rgba(167,139,250,0.5)', transition: 'transform 0.2s', display: 'inline-block', transform: thinkingCollapsed ? 'rotate(0deg)' : 'rotate(90deg)' }}>▶</span>
            </button>
            {!thinkingCollapsed && (
              <div ref={thinkingRef}
                className="px-3 py-2 overflow-y-auto font-mono text-[11px] leading-relaxed"
                style={{
                  maxHeight: '220px',
                  color: 'rgba(200, 180, 255, 0.7)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  textShadow: '0 0 8px rgba(167,139,250,0.2)',
                }}>
                {thinkingText}
                <span className="inline-block w-1 h-3 ml-0.5 align-middle animate-pulse rounded-sm"
                  style={{ background: 'rgba(167,139,250,0.6)', boxShadow: '0 0 4px rgba(167,139,250,0.4)' }} />
              </div>
            )}
          </div>
        )}

        <div ref={messagesEnd} />
      </div>

      {/* Input */}
      <div className="shrink-0 px-4 pt-2 pb-3" style={{ borderTop: '1px solid rgba(139,92,246,0.1)' }}>
        {/* 7 LoRA Emotional Toggles */}
        <div className="flex gap-1.5 mb-2 flex-wrap">
          {LORA_DEFS.map(lora => {
            const weight = loraWeights[lora.key] || 0
            const isActive = loraActive === lora.key
            return (
              <button
                key={lora.key}
                onClick={() => blendLora(lora.key)}
                title={`${lora.label} · ${lora.hz} · weight: ${(weight * 100).toFixed(0)}%`}
                className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-mono transition-all"
                style={{
                  background: isActive ? `${lora.glow}` : `rgba(255,255,255,0.04)`,
                  border: `1px solid ${isActive ? lora.color : 'rgba(255,255,255,0.1)'}`,
                  color: isActive ? lora.color : 'rgba(255,255,255,0.3)',
                  boxShadow: isActive ? `0 0 8px ${lora.glow}` : 'none',
                }}>
                <span>{lora.icon}</span>
                <span>{lora.label}</span>
                {weight > 0.1 && (
                  <span style={{ color: isActive ? lora.color : 'rgba(255,255,255,0.2)', fontSize: '8px' }}>
                    {(weight * 100).toFixed(0)}
                  </span>
                )}
              </button>
            )
          })}
          <button
            onClick={async () => {
              await authFetch('/api/soul/lora-reset', { method: 'POST' })
              const d = await authFetch('/api/soul/emotional-state').then(r => r.json())
              if (d.lora_weights) { setLoraWeights(d.lora_weights); setLoraActive(null) }
            }}
            className="px-2 py-0.5 rounded-full text-[8px] font-mono transition-all"
            style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', color: 'rgba(255,255,255,0.2)' }}
            title="Reset to baseline state">
            ↺
          </button>
        </div>

        {/* ── Continuation buttons — Edit Automatically / Plan ── */}
        {messages.length > 1 && (
          <div className="flex gap-2 mb-2 flex-wrap">
            <button
              onClick={() => sendMessage(
                'Go ahead and implement this automatically. Edit the code, make all the necessary changes, and give me a concise report of exactly what was done.'
              )}
              disabled={streaming}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-mono transition-all"
              style={{
                background: 'rgba(34,211,238,0.07)',
                border: '1px solid rgba(34,211,238,0.22)',
                color: streaming ? 'rgba(34,211,238,0.3)' : '#22d3ee',
                cursor: streaming ? 'not-allowed' : 'pointer',
              }}
            >
              ✏ Edit Automatically
            </button>
            <button
              onClick={() => sendMessage(
                'Create a detailed step-by-step implementation plan. Number each step, specify which files change and how, note dependencies, and flag any risks or open questions before we start.'
              )}
              disabled={streaming}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-mono transition-all"
              style={{
                background: 'rgba(139,92,246,0.07)',
                border: '1px solid rgba(139,92,246,0.22)',
                color: streaming ? 'rgba(139,92,246,0.3)' : '#c4b5fd',
                cursor: streaming ? 'not-allowed' : 'pointer',
              }}
            >
              ◎ Plan
            </button>
          </div>
        )}

        {/* Attached files preview */}
        {attachedFiles.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {attachedFiles.map((f, i) => (
              <div key={i} className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-[10px] font-mono"
                style={{ background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.25)', color: '#c4b5fd' }}>
                <span>{f.type?.startsWith('image/') ? '🖼️' : '📄'}</span>
                <span className="max-w-[120px] truncate">{f.name}</span>
                <button type="button" onClick={() => setAttachedFiles(prev => prev.filter((_, j) => j !== i))}
                  className="ml-0.5 hover:text-red-400 transition-colors" style={{ color: 'rgba(255,255,255,0.3)' }}>✕</button>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-2"
          onDragOver={(e) => { e.preventDefault(); e.stopPropagation() }}
          onDrop={(e) => {
            e.preventDefault(); e.stopPropagation()
            if (e.dataTransfer?.files?.length) {
              const incoming = Array.from(e.dataTransfer.files)
              setAttachedFiles(prev => {
                const existing = new Set(prev.map(f => f.name))
                return [...prev, ...incoming.filter(f => !existing.has(f.name))]
              })
            }
          }}>
          {/* Hidden file input */}
          <input ref={fileInputRef} type="file" multiple className="hidden"
            accept="image/*,.pdf,.txt,.md,.csv,.json,.py,.js,.ts,.jsx,.tsx,.html,.css,.log"
            onChange={(e) => {
              if (e.target.files?.length) {
                const incoming = Array.from(e.target.files)
                setAttachedFiles(prev => {
                  const existing = new Set(prev.map(f => f.name))
                  return [...prev, ...incoming.filter(f => !existing.has(f.name))]
                })
              }
              e.target.value = ''
            }}
          />
          {/* Attach button */}
          <button type="button" onClick={() => fileInputRef.current?.click()}
            className="px-3 py-2.5 rounded-xl text-sm transition-all"
            style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.35)' }}
            title="Attach files or images">
            📎
          </button>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
            placeholder={attachedFiles.length ? `Describe what you want ${selectedAgent ? (selectedAgent.chosen_name || 'the agent') : 'Eve'} to do with these files…` : selectedAgent ? `Task for ${selectedAgent.chosen_name || selectedAgent.agent_id}…` : "Message Eve… ask anything, browse the web, trade, dream"}
            className="flex-1 px-4 py-2.5 rounded-xl text-sm font-mono bg-white/5 border border-white/10
                       focus:border-violet-400/40 focus:ring-1 focus:ring-violet-400/20
                       outline-none transition-all placeholder:text-white/20"
            disabled={streaming}
          />
          {streaming ? (
            <button type="button" onClick={stopStreaming}
              className="px-4 py-2.5 rounded-xl text-sm font-mono bg-red-500/15 border border-red-500/25 text-red-400 hover:bg-red-500/25 transition-all">
              ⏹ Stop
            </button>
          ) : (
            <button type="button" onClick={() => sendMessage()} disabled={!input.trim() && attachedFiles.length === 0}
              className="btn-primary px-5 disabled:opacity-40 disabled:cursor-not-allowed">
              Send
            </button>
          )}
        </div>

        {/* Dynamic hint prompts — new set every render */}
        <div className="flex gap-2 mt-2 px-1 flex-wrap items-center">
          {hints.map((hint, i) => (
            <button key={i} onClick={() => { setInput(hint); inputRef.current?.focus() }}
              className="text-[10px] px-2 py-1 rounded-lg font-mono bg-white/5 text-white/25
                         hover:text-white/60 hover:bg-white/10 transition-all">
              {hint}
            </button>
          ))}
          <button
            onClick={() => setHints(pickHints(5))}
            className="ml-auto text-[9px] px-1.5 py-0.5 rounded font-mono transition-all"
            style={{ color: 'rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)' }}
            title="Shuffle prompts">
            ⟳
          </button>
        </div>
      </div>
    </div>
  )
}
