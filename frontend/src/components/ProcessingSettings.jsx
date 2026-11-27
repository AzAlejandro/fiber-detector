import React, { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api'

const stages = [
  ['Preparación de la máscara', [
    ['smooth', 'Suavizado inicial', 'Reduce el ruido antes de calcular el contraste y buscar círculos.'],
    ['local_background', 'Corrección local del fondo', 'Al desactivarla se usa la intensidad media del campo.'],
  ]],
  ['Detección de fibras y selección de círculos', [
    ['clahe', 'Contraste adaptativo (CLAHE)', 'Realza las diferencias de intensidad por zonas.'],
    ['oriented', 'Realce por orientación', 'Resalta estructuras alargadas en varias direcciones y grosores.'],
    ['alignment', 'Alineamiento', 'Comprueba que la dirección de la fibra concuerde con la del círculo candidato.'],
    ['continuity', 'Continuidad longitudinal', 'Busca evidencia de la misma hebra antes y después del círculo.'],
    ['prune_spurs', 'Poda del esqueleto', 'Elimina ramas terminales cortas al distribuir los círculos.'],
  ]],
]

export default function ProcessingSettings() {
  const [settings, setSettings] = useState(null)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')

  useEffect(() => {
    let current = true
    apiGet('/api/agent/processing-settings').then(result => {
      if (current) setSettings(result)
    }).catch(() => {
      if (current) setStatus('No se pudo cargar la configuración de procesamiento.')
    })
    return () => { current = false }
  }, [])

  async function change(name, value) {
    setBusy(true)
    setStatus('Guardando…')
    try {
      setSettings(await apiPost('/api/agent/processing-settings', { [name]: value }))
      setStatus('Configuración guardada.')
    } catch {
      setStatus('No se pudo guardar el cambio.')
    } finally {
      setBusy(false)
    }
  }

  return <section className="settings-narrow">
    <h2>Filtros y medición</h2>
    <p>Se aplican a las próximas ejecuciones en todos los proyectos.</p>
    {settings && <>
      {stages.map(([title, fields]) => <section className="settings-section" key={title}>
        <h3>{title}</h3>
        <div className="settings-box">{fields.map(([name, label, description]) =>
          <label className="settings-switch" key={name}>
            <span><strong>{label}</strong><small>{description}</small></span>
            <input type="checkbox" aria-label={label} checked={settings[name]} disabled={busy}
              onChange={e => change(name, e.target.checked)} />
          </label>)}</div>
      </section>)}
      <section className="settings-section">
        <h3>Distribución de los círculos</h3>
        <div className="settings-box">
          <label className="settings-switch">
            <span><strong>Muestreo por zonas</strong><small>Reparte los círculos según el área de fibra en la máscara. Las zonas vacías reciben cero.</small></span>
            <input type="checkbox" aria-label="Muestreo por zonas" checked={settings.zoned_sampling} disabled={busy}
              onChange={e => change('zoned_sampling', e.target.checked)} />
          </label>
          {settings.zoned_sampling && <>
            <div className="settings-pair">
              {[['zone_rows', 'Filas'], ['zone_columns', 'Columnas']].map(([name, label]) =>
                <label className="settings-zoom" key={name}>{label}
                  <select aria-label={label} value={settings[name]} disabled={busy} onChange={e => change(name, Number(e.target.value))}>
                    {Array.from({ length: 8 }, (_, i) => <option key={i+1}>{i+1}</option>)}
                  </select>
                </label>)}
            </div>
            <label className="settings-switch">
              <span><strong>Redistribuir cupos sin cubrir</strong><small>Si faltan tramos medibles en una zona, busca en otras. Desactívalo para respetar el cupo de cada zona aunque el total sea menor.</small></span>
              <input type="checkbox" aria-label="Redistribuir cupos sin cubrir" checked={settings.redistribute_zones}
                disabled={busy} onChange={e => change('redistribute_zones', e.target.checked)} />
            </label>
          </>}
        </div>
      </section>
      <section className="settings-section">
        <h3>Medición de diámetros</h3>
        <label className="settings-zoom"><strong>Método para los círculos</strong>
          <select value={settings.diameter_method} disabled={busy} onChange={e => change('diameter_method', e.target.value)}>
            <option value="three_profiles">D · Tres perfiles transversales (predeterminado)</option>
            <option value="legacy">Anterior · Geometría de la máscara</option>
          </select>
        </label>
        <p>Ambos métodos conservan el círculo. D ajusta los extremos cuando los tres cortes coinciden y conserva la medición de la máscara cuando discrepan.</p>
      </section>
    </>}
    <small role="status">{status || (!settings && 'Cargando…')}</small>
  </section>
}
