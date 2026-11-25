import React, { useState } from 'react'
import { apiPost } from '../api'

export function TargetResult({ metric, unit }) {
  if (metric?.target == null) return null
  const format = n => n.toLocaleString('es-CL', {maximumFractionDigits: 3})
  return <p className="small">Objetivo {format(metric.target)} {unit} · Obtenido {format(metric.actual)} {unit} · {metric.within ? 'Dentro del margen' : 'Fuera del margen'}</p>
}

export default function AgentTargets({ project, onSaved }) {
  const saved = project.agent_targets || {}
  const [draft, setDraft] = useState(() => ({
    painted_percent: saved.painted_percent ?? '', percent_tolerance: saved.percent_tolerance ?? 1,
    circle_count: saved.circle_count ?? '', circle_tolerance: saved.circle_tolerance ?? 2,
  }))
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  function input(key, label, min, max, step, required = false) {
    return <label className="field"><span>{label}</span>
      <input type="number" value={draft[key]} min={min} max={max} step={step} required={required}
        placeholder={required ? undefined : 'Sin objetivo'} onChange={e => {
          setDraft({...draft, [key]:e.target.value}); setMessage('')
        }}/>
    </label>
  }
  async function save(e) {
    e.preventDefault()
    setBusy(true); setMessage('')
    try {
      const values = Object.fromEntries(Object.entries(draft).map(([k,v]) => [k,v === '' ? null : Number(v)]))
      const targets = await apiPost('/api/projects/'+encodeURIComponent(project.project_id)+'/agent-targets', values)
      onSaved(project.project_id, targets)
      setMessage('Objetivos guardados para las próximas propuestas.')
    } catch (e) {
      setMessage(e.status === 404 ? 'Comprueba que el proyecto existe y el motor está actualizado.' : e.message)
    } finally { setBusy(false) }
  }
  return <section className="settings-section">
    <header><h2>Objetivos del agente</h2><small>{project.name}</small></header>
    <form onSubmit={save} className="settings-section">
      <fieldset className="settings-box" disabled={busy}><legend>Cobertura</legend><div className="settings-pair">
        {input('painted_percent','Superficie pintada por imagen (%)',0.000001,100,'any')}
        {input('percent_tolerance','Margen (± puntos porcentuales)',0,100,'any',true)}
      </div></fieldset>
      <fieldset className="settings-box" disabled={busy}><legend>Recuento</legend><div className="settings-pair">
        {input('circle_count','Círculos por imagen',1,200,1)}
        {input('circle_tolerance','Margen (± círculos)',0,200,1,true)}
      </div></fieldset>
      <p className="small">La cobertura suma fibra, halo y fondo sobre el campo útil, excluido el pie instrumental. Deja vacío el objetivo que prefieras omitir.</p>
      <button type="submit" disabled={busy} className="primary settings-save">{busy ? 'Guardando…' : 'Guardar objetivos'}</button>
    </form>
    {message && <p role="status" className="small">{message}</p>}
  </section>
}
