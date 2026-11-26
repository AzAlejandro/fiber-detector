import React, { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api'

export default function AgentModelSetting() {
  const [settings, setSettings] = useState(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    let active = true
    apiGet('/api/agent/model').then(value => {
      if (active) setSettings(value)
    }).catch(() => {
      if (active) setMessage('No se pudo cargar el modelo del agente.')
    })
    return () => { active = false }
  }, [])

  async function changeModel(model) {
    setSaving(true)
    setMessage('Guardando…')
    try {
      setSettings(await apiPost('/api/agent/model', { model }))
      setMessage('Modelo guardado para los próximos agentes.')
    } catch {
      setMessage('No se pudo guardar el modelo. Vuelve a intentarlo.')
    } finally {
      setSaving(false)
    }
  }

  return <div>
    <label className="settings-zoom">
      <strong>Modelo para nuevos agentes</strong>
      <select disabled={!settings || saving} value={settings?.model || ''}
        onChange={event => changeModel(event.target.value)}>
        {settings ? Object.entries(settings.options).map(([id, name]) =>
          <option key={id} value={id}>{name}{id === settings.default ? ' (predeterminado)' : ''}</option>
        ) : <option value="">—</option>}
      </select>
    </label>
    <small role="status">{message}</small>
  </div>
}
