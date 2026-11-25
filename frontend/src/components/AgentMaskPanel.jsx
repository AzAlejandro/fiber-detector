import React, { useEffect, useRef, useState } from 'react'
import { API_BASE, apiGet, apiPost } from '../api'
import { TargetResult } from './AgentTargets'

export default function AgentMaskPanel({ project, images, imageId, loadImage, loading, getScribble, addToEditor, onDetect }) {
  const available = images.filter(im => project && im.project_ids?.includes(project.project_id))
  const current = available.find(im => im.image_id === imageId)
  const [masks, setMasks] = useState([])
  const [selected, setSelected] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [layer, setLayer] = useState('scribble')
  const dialog = useRef(null)
  const alive = useRef(false)
  const mask = masks.find(m => m.mask_id === selected)
  const base = mask && API_BASE + '/api/agent/scribble-masks/' + mask.mask_id + '/layers/'
  useEffect(() => {
    alive.current = true
    let active = true
    if (current) {
      setBusy(true)
      apiGet('/api/agent/scribble-masks?' + new URLSearchParams({ image_id: imageId, project_id: project.project_id }))
        .then(items => { if (active) { setMasks(items); setSelected(items[0]?.mask_id || '') } })
        .catch(e => { if (active) setError(e.message) })
        .finally(() => { if (active) setBusy(false) })
    }
    return () => { active = false; alive.current = false }
  }, [imageId, project?.project_id, current?.image_id])

  async function generate(automatic) {
    if (!current || busy || loading) return
    setBusy(true)
    setError('')
    try {
      const payload = { project_id: project.project_id, image_id: imageId }
      if (!automatic) payload.scribble_map_b64 = getScribble()
      const result = await apiPost('/api/agent/scribble-masks', payload)
      if (alive.current) {
        setMasks(previous => [result, ...previous])
        setSelected(result.mask_id)
      }
    } catch (e) { if (alive.current) setError(e.message) }
    finally { if (alive.current) setBusy(false) }
  }
  function preview(key) {
    setLayer(key)
    dialog.current?.showModal()
  }
  async function importLabels() {
    setError('')
    setBusy(true)
    try {
      const response = await fetch(base + 'labels')
      if (!response.ok) throw new Error('No se pudieron cargar los trazos.')
      const blob = await response.blob()
      const data = await new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result.split(',')[1])
        reader.onerror = () => reject(new Error('No se pudo leer el scribble guardado.'))
        reader.readAsDataURL(blob)
      })
      if (alive.current) await addToEditor(data)
    } catch (e) { if (alive.current) setError(e.message) }
    finally { if (alive.current) setBusy(false) }
  }
  return <section className="card agent-mask-panel">
    <h2>Obtención de máscara</h2>
    <label className="field"><span>Imagen de {project?.name || 'proyecto'}</span>
      <select disabled={!available.length || busy || loading} value={current?.image_id || ''} onChange={e => loadImage(e.target.value)}>
        <option value="" disabled>Selecciona una imagen</option>
        {available.map(im => <option key={im.image_id} value={im.image_id}>{im.image_name}</option>)}
      </select>
    </label>
    <button disabled={!current || busy || loading} onClick={() => generate(true)}>Proponer trazos por contraste y obtener máscara</button>
    <button className="primary" disabled={!current || busy || loading} onClick={() => generate(false)}>Obtener máscara del scribble del editor</button>
    {(busy || loading) && <span role="status" className="small">Procesando…</span>}
    {error && <span role="alert" className="small">{error}</span>}
    {!!masks.length && <label className="field"><span>Máscara guardada</span>
      <select value={selected} onChange={e => setSelected(e.target.value)}>{masks.map(m =>
        <option key={m.mask_id} value={m.mask_id}>{new Date(m.created_at).toLocaleString()} · {m.source}</option>)}</select>
    </label>}
    {mask && <>
      <div className="agent-mask-previews">{[['scribble', 'Scribble'], ['mascara', 'Máscara binaria']].map(([key, label]) =>
        <button key={key} onClick={() => preview(key)}><img src={base + key} alt="" />{label}</button>)}</div>
      <span className="small">Píxeles marcados · Fibra {mask.counts.fiber} · Halo {mask.counts.halo} · Fondo {mask.counts.background}</span>
      <TargetResult metric={mask.coverage_review} unit="%"/>
      <button disabled={busy || loading} onClick={importLabels}>Añadir trazos al editor en zonas sin pintar</button>
      <button disabled={busy || loading} onClick={() => onDetect(mask)}>Usar en detección de fibras y bordes</button>
      <dialog ref={dialog} className="agent-mask-dialog" aria-label="Revisar el scribble y su máscara">
        <div className="viewer-toolbar"><strong>{current?.image_name}</strong>
          <button aria-pressed={layer === 'scribble'} onClick={() => setLayer('scribble')}>Scribble</button>
          <button aria-pressed={layer === 'mascara'} onClick={() => setLayer('mascara')}>Máscara binaria</button>
          <button onClick={() => dialog.current.close()}>Cerrar</button>
        </div>
        <img src={base + layer} alt={layer === 'scribble' ? 'Trazos sobre la imagen' : 'Máscara binaria de fibra'} />
      </dialog>
    </>}
  </section>
}
