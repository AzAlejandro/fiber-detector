import React, { useEffect, useRef, useState } from 'react'
import { API_BASE, apiGet, apiPost } from '../api'
import { detectCircleContacts, edgeReviewFor } from '../agentEdges.mjs'
import { circleFromDiameter } from '../circleGeometry.mjs'
import { buildGreenMaskLayer } from '../greenMaskLayer'
import { TargetResult } from './AgentTargets'

const fit = { scale: 1, x: 0.5, y: 0.5 }
const names = { foto: 'Foto de trabajo', suavizada: 'Suavizada', fondo: 'Fondo local', contraste: 'Contraste local', mascara: 'Máscara binaria', eje: 'Eje de la máscara', mascara_agente: 'Máscara de agente', mascara_scribble: 'Máscara de scribble' }
const sources = { agente: 'Máscara de agente', scribble: 'Máscara de scribble', ambas: 'Ambas (intersección)' }

export default function AgentMode({ project, images, activeImageId, handIcon, onMeasure, enterEditor, preferredMask }) {
  const available = images.filter(image => !project || image.project_ids?.includes(project.project_id))
  const [choice, setChoice] = useState(activeImageId)
  const [comparison, setComparison] = useState({ primary: 'foto', secondary: 'mascara', opacity: 38 })
  const current = available.find(image => image.image_id === choice) || available[0]
  function stepImage(offset) {
    const index = available.indexOf(current) + offset
    if (available[index]) setChoice(available[index].image_id)
  }
  const support = preferredMask?.project_id === project?.project_id && preferredMask?.image_id === current?.image_id ? preferredMask : null
  return <AgentWorkspace key={current?.image_id || 'empty'} circleGoal={project?.agent_targets?.circle_count} preferredMask={support} enterEditor={enterEditor} image={current} projectId={project?.project_id} handIcon={handIcon} onMeasure={onMeasure} stepImage={stepImage} comparison={comparison} setComparison={setComparison} imagePicker={
    <label className="field"><span>Imagen de {project?.name || 'la biblioteca'}</span>
      <select value={current?.image_id || ''} onChange={e => setChoice(e.target.value)}>
        {available.map(im => <option key={im.image_id} value={im.image_id}>{im.image_name}</option>)}
      </select>
    </label>
  } />
}

function AgentWorkspace({ image, projectId, circleGoal, imagePicker, handIcon, onMeasure, stepImage, comparison, setComparison, enterEditor, preferredMask }) {
  const [history, setHistory] = useState([])
  const [run, setRun] = useState(null)
  const layers = run?.layers || Object.keys(names)
  const primary = layers.includes(comparison.primary) ? comparison.primary : layers[0]
  const secondary = layers.includes(comparison.secondary) && comparison.secondary !== primary ? comparison.secondary : ''
  const [overlay, setOverlay] = useState(true)
  const [showContacts, setShowContacts] = useState(true)
  const [edgeResult, setEdgeResult] = useState(null)
  const [selection, setSelection] = useState(0)
  const [view, setView] = useState(fit)
  const [panning, setPanning] = useState(false)
  const [tool, setTool] = useState('pan')
  const [draft, setDraft] = useState(null)
  const [opacity, setOpacity] = useState(1)
  const drag = useRef(null)
  const stageRef = useRef(null)
  const listRef = useRef(null)
  const editing = useRef(false)
  const [undo, setUndo] = useState([])
  const [redo, setRedo] = useState([])
  const [limit, setLimit] = useState(circleGoal ?? 100)
  const [sigma, setSigma] = useState(10)
  const [threshold, setThreshold] = useState(5)
  const [maskSource, setMaskSource] = useState(preferredMask ? 'scribble' : 'agente')
  const [supports, setSupports] = useState([])
  const [supportId, setSupportId] = useState(preferredMask?.mask_id || '')
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const id = image?.image_id
  function useSavedParameters(saved) {
    setLimit(circleGoal ?? saved?.parameters?.limit ?? 100)
    setSigma(saved?.parameters?.background_sigma ?? 10)
    setThreshold(saved?.parameters?.threshold ?? 5)
  }
  const includeLegacy = projectId === image?.project_ids?.[0]
  useEffect(() => {
    let active = true
    async function load() {
      if (!id) return
      const query = new URLSearchParams({ image_id: id })
      if (projectId) {
        query.set('project_id', projectId)
        query.set('include_legacy', String(includeLegacy))
      }
      const items = await apiGet('/api/agent/runs?' + query)
      const latest = items.length ? await apiGet('/api/agent/runs/' + items[0].run_id) : null
      if (active) { setHistory(items); setRun(latest) }
      const masks = projectId ? await apiGet('/api/agent/scribble-masks?' + new URLSearchParams({image_id: id, project_id: projectId})) : []
      if (active) {
        setSupports(masks)
        const desired = preferredMask?.mask_id || latest?.scribble_mask_id
        setSupportId(masks.find(m => m.mask_id === desired)?.mask_id || masks[0]?.mask_id || '')
        useSavedParameters(latest)
        setMaskSource(masks.length ? preferredMask ? 'scribble' : latest?.mask_source || 'ambas' : 'agente')
      }
    }
    load().catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [id, projectId, includeLegacy])

  async function openRun(runId, startDrawing = false) {
    setBusy(true)
    setError('')
    try {
      const data = runId ? await apiGet('/api/agent/runs/' + runId) : await apiPost('/api/agent/runs', {
        image_id: id, project_id: projectId || '', limit: Number(limit), background_sigma: Number(sigma), threshold: Number(threshold),
        mask_source: maskSource, scribble_mask_id: maskSource === 'agente' ? null : supportId,
        ...(startDrawing ? { circles: [] } : {}),
      })
      if (!runId) setHistory(items => [data, ...items])
      if (runId) {
        useSavedParameters(data)
        setMaskSource(supports.length ? data.mask_source || 'agente' : 'agente')
        setSupportId(supports.find(m => m.mask_id === data.scribble_mask_id)?.mask_id || supports[0]?.mask_id || '')
      }
      setRun(data)
      setUndo([])
      setRedo([])
      setSelection(0)
      setView(fit)
      chooseTool(startDrawing ? 'circle' : 'pan')
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  const circle = run?.circles[selection]
  const review = edgeReviewFor(run, circle)
  async function editCircle(action, geometry) {
    let change = action === 'undo' ? undo.at(-1) : action === 'redo' ? redo.at(-1) : { action, id: circle?.id }
    if (!run || !change || (action !== 'add' && change.id == null) || busy || editing.current) return
    editing.current = true
    setBusy(true)
    setError('')
    try {
      const endpoint = '/api/agent/runs/' + run.run_id + '/circles'
      const restoring = action === 'undo' ? change.action === 'remove' : action === 'redo' && change.action === 'add'
      const index = run.circles.findIndex(c => c.id === change.id)
      const updated = action === 'add' ? await apiPost(endpoint, geometry)
        : await apiPost(endpoint + '/' + change.id + (restoring ? '/restore' : '/remove'), {})
      if (action === 'add') change = { action, id: updated.added_circle_id }
      setRun(updated)
      setUndo(action === 'undo' ? undo.slice(0, -1) : [...undo, change])
      setRedo(action === 'undo' ? [...redo, change] : action === 'redo' ? redo.slice(0, -1) : [])
      const next = Math.max(0, restoring || action === 'add' ? updated.circles.findIndex(c => c.id === change.id) : Math.min(index, updated.circles.length - 1))
      setSelection(next)
      if (restoring && updated.circles[next] && view.scale > 1) focusCircle(updated.circles[next])
    } catch (e) { setError(e.message) }
    finally { editing.current = false; setBusy(false) }
  }
  async function openMeasurements() {
    setBusy(true)
    setError('')
    try { await onMeasure(run, contacts || {}) }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  const url = run && API_BASE + '/api/agent/runs/' + run.run_id
  function displayLayer(layer) {
    return url + '/layers/' + layer + (layer === 'foto' && view.scale <= 1 ? '?overview=true' : '')
  }
  const secondaryUrl = url && secondary ? displayLayer(secondary) : ''
  const maskUrl = secondary.startsWith('mascara') || secondary === 'eje' ? secondaryUrl : ''
  const [maskLayer, setMaskLayer] = useState(null)
  useEffect(() => {
    if (!maskUrl) return
    let active = true
    buildGreenMaskLayer(maskUrl)
      .then(src => { if (active) setMaskLayer({ url: maskUrl, src }) })
      .catch(err => { if (active) setMaskLayer({ url: maskUrl, error: err.message }) })
    return () => { active = false }
  }, [maskUrl])
  const currentMask = maskLayer?.url === maskUrl ? maskLayer : null
  const secondaryLayer = maskUrl ? currentMask?.src : secondaryUrl
  useEffect(() => {
    if (!run?.circles.length) return
    const controller = new AbortController()
    async function detect() {
      const points = await detectCircleContacts(url,run,run.circles,controller.signal)
      if (controller.signal.aborted) return
      setEdgeResult({run, points})
    }
    detect().catch(e => { if (!controller.signal.aborted) setEdgeResult({run, error:e.message}) })
    return () => controller.abort()
  }, [run, url])
  const contacts = edgeResult?.run===run ? edgeResult?.points : null
  useEffect(() => {
    if (enterEditor && run && (!run.circles.length || contacts)) openMeasurements()
  }, [enterEditor, run, contacts])
  const edgeError = edgeResult?.run===run && edgeResult?.error
  const params = run?.parameters
  const viewWidth = run && run.width / view.scale
  const viewHeight = run && run.height / view.scale
  const viewBox = run && [view.x * run.width - viewWidth / 2, view.y * run.height - viewHeight / 2, viewWidth, viewHeight].join(' ')

  function zoomBy(factor) {
    setView(v => ({ ...v, scale: Math.max(0.25, Math.min(64, v.scale * factor)) }))
  }
  useEffect(() => {
    const stage = stageRef.current
    if (!stage || !run) return
    function wheel(e) {
      if ((!e.ctrlKey && !e.metaKey) || !e.deltaY) return
      e.preventDefault()
      if (drag.current) return
      const rect = stage.querySelector('svg').getBoundingClientRect()
      const fitScale = Math.min(rect.width / run.width, rect.height / run.height)
      if (!fitScale) return
      const dx = (e.clientX - rect.left - rect.width / 2) / (fitScale * run.width)
      const dy = (e.clientY - rect.top - rect.height / 2) / (fitScale * run.height)
      setView(v => {
        const scale = Math.max(0.25, Math.min(64, v.scale * (e.deltaY < 0 ? 1.12 : 1 / 1.12)))
        const shift = 1 / v.scale - 1 / scale
        return { scale, x: v.x + dx * shift, y: v.y + dy * shift }
      })
    }
    stage.addEventListener('wheel', wheel, { passive: false })
    return () => stage.removeEventListener('wheel', wheel)
  }, [run])

  function selectCircle(index) {
    if (!run?.circles[index]) return
    setSelection(index)
    if (view.scale > 1) focusCircle(run.circles[index])
  }

  useEffect(() => {
    const list = listRef.current
    const selected = list?.children[selection]
    if (!selected) return
    const bounds = list.getBoundingClientRect()
    const row = selected.getBoundingClientRect()
    if (row.top < bounds.top) list.scrollTop += row.top - bounds.top
    else if (row.bottom > bounds.bottom) list.scrollTop += row.bottom - bounds.bottom
  }, [selection, run])

  useEffect(() => {
    function keyDown(e) {
      if (e.defaultPrevented || e.altKey || e.isComposing || busy || e.target.isContentEditable ||
          e.target.closest?.('input, textarea, select, [role="dialog"], dialog')) return
      const key = e.key.toLowerCase()
      const mod = e.ctrlKey || e.metaKey
      if (drag.current && key !== 'escape') return
      if (mod && (key === 'z' || key === 'y')) {
        if (!e.repeat) editCircle(key === 'y' || e.shiftKey ? 'redo' : 'undo')
      } else if (mod) return
      else if (key === 'pagedown' || key === 'pageup') stepImage(key === 'pagedown' ? 1 : -1)
      else if (!run) {
        if (key !== 'c' || !canStartDrawing) return
        openRun(null, true)
      }
      else if (key === 'delete' || key === 'backspace') {
        if (!e.repeat) editCircle('remove')
      } else if (key === 'arrowright' || key === 'arrowdown') selectCircle(selection + 1)
      else if (key === 'arrowleft' || key === 'arrowup') selectCircle(selection - 1)
      else if (key === 'home' || key === 'end') selectCircle(key === 'home' ? 0 : run.circles.length - 1)
      else if (key === '+' || key === '=') zoomBy(1.2)
      else if (key === '-') zoomBy(1 / 1.2)
      else if (key === '0') setView(fit)
      else if (key === 'f' && circle) focusCircle(circle)
      else if (key === 'v') { if (!e.repeat) setOverlay(value => !value) }
      else if (key === 'c' || key === 'm' || key === 'escape') chooseTool(key === 'c' ? 'circle' : 'pan')
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', keyDown)
    return () => window.removeEventListener('keydown', keyDown)
  })
  function focusCircle(c) {
    const side = Math.max(60, c.radius_px * 10)
    setView({ scale: Math.min(run.width, run.height) / side, x: c.x / run.width, y: c.y / run.height })
  }
  function chooseTool(value) {
    drag.current = null
    setDraft(null)
    setPanning(false)
    setTool(value)
    if (value === 'circle') setOverlay(true)
    stageRef.current?.focus({ preventScroll: true })
  }
  function imagePoint(e) {
    return new DOMPoint(e.clientX, e.clientY).matrixTransform(e.currentTarget.getScreenCTM().inverse())
  }
  function drawnCircle(e, start) {
    const { center, radius } = circleFromDiameter(start, imagePoint(e), run.width, run.parameters.field_height)
    return { ...center, radius_px: radius }
  }
  function startPan(e) {
    if (e.button !== 0 || !e.isPrimary) return
    const svg = e.currentTarget
    stageRef.current.focus({ preventScroll: true })
    if (tool === 'circle') {
      if (busy || editing.current) return
      const {x, y} = imagePoint(e)
      if (x < 0 || y < 0 || x > run.width - 1 || y > run.parameters.field_height - 1) return
      drag.current = { circleStart: { x, y } }
      setDraft({x, y, radius_px: 0})
      svg.setPointerCapture(e.pointerId)
      e.preventDefault()
      return
    }
    const index = e.target.getAttribute('data-circle-index')
    drag.current = { clientX: e.clientX, clientY: e.clientY, view, scale: svg.getScreenCTM().a, index, moved: false }
    svg.setPointerCapture(e.pointerId)
    setPanning(true)
  }
  function movePan(e) {
    const start = drag.current
    if (!start || !e.isPrimary) return
    if (start.circleStart) {
      setDraft(drawnCircle(e, start.circleStart))
      return
    }
    const dx = e.clientX - start.clientX
    const dy = e.clientY - start.clientY
    if (!start.moved && Math.hypot(dx, dy) < 3) return
    start.moved = true
    setView({ scale: start.view.scale, x: start.view.x - dx / (start.scale * run.width), y: start.view.y - dy / (start.scale * run.height) })
  }
  function endPan(e) {
    if (!e.isPrimary) return
    const start = drag.current
    if (start?.circleStart) {
      if (e.type === 'pointerup') {
        const circle = drawnCircle(e, start.circleStart)
        if (circle.radius_px >= 1) editCircle('add', circle)
      }
      setDraft(null)
    } else if (e.type === 'pointerup' && start && !start.moved && start.index !== null) setSelection(Number(start.index))
    drag.current = null
    setPanning(false)
  }
  const canStartDrawing = !busy && !!id && (run || maskSource === 'agente' || !!supportId)
  const metrics = [
    ['Imagen', run?.image_name || image?.image_name], ['Tamaño', run && run.width + ' × ' + run.height + ' px'],
    ['Suavizado σ', params && params.smooth_sigma + ' px'], ['Fondo σ', params && params.background_sigma + ' px'],
    ['Umbral', params?.threshold], ['Filas analizadas', params?.field_height],
    ['Círculos', run?.circles.length ?? 0], ['Máximo solicitado', params?.limit],
    ['Radio seleccionado', circle && Number(circle.radius_px).toFixed(1) + ' px'], ['Cruces en la máscara', circle?.mask_crossings],
    ['Propuesta', run?.circles.some(c => c.source === 'manual')
      ? (run.circles.every(c => c.source === 'manual') ? 'manual' : run.circle_source + ' + manual')
      : run?.circle_source],
    ['Máscara utilizada', run && sources[run.mask_source || 'agente']],
    ...(run?.scribble_mask_id ? [['Versión de scribble', run.scribble_mask_id.slice(0, 8)]] : []),
  ]
  const computingEdges = !!run?.circles.length && !contacts && !edgeError
  return <div className="layout" data-tour="workspace-panel-agentMode">
    <aside className="left agent-sidebar">
      <section className="card">
        <h2>Detección</h2>
        {imagePicker}
        <form id="agent-run" onSubmit={e => { e.preventDefault(); if (id && !busy) openRun() }}>
          <label className="field"><span>Máximo de círculos</span><input required type="number" min="1" max="200" value={limit} onChange={e => setLimit(e.target.value)} /></label>
          <details className="agent-settings">
            <summary>Ajustes avanzados</summary>
            <label className="field"><span>Máscara para detectar fibras</span>
              <select value={maskSource} onChange={e => setMaskSource(e.target.value)}>
                {Object.entries(sources).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select></label>
            {maskSource !== 'agente' && <label className="field"><span>Máscara de scribble guardada</span>
              <select required value={supportId} onChange={e => setSupportId(e.target.value)}>
                {!supports.length && <option value="">Genera una en Obtención de máscara</option>}
                {supports.map(m => <option key={m.mask_id} value={m.mask_id}>{new Date(m.created_at).toLocaleString()} · {m.source} · {m.mask_id.slice(0,8)}</option>)}
              </select></label>}
            <label className="field"><span>Sigma del fondo (px)</span><input disabled={maskSource === 'scribble'} required type="number" min="2" max="40" step="any" value={sigma} onChange={e => setSigma(e.target.value)} /></label>
            <label className="field"><span>Umbral de contraste (fondo − suavizada ≥ umbral)</span><input disabled={maskSource === 'scribble'} required type="number" min="1" max="100" step="any" value={threshold} onChange={e => setThreshold(e.target.value)} /></label>
          </details>
        </form>
        {(error || edgeError || currentMask?.error) && <p role="alert">{error || edgeError || currentMask.error}</p>}
      </section>
      <section className="card">
        <h2>Vista</h2>
        <div className="inline">
          <label className="mask-toggle"><input type="checkbox" disabled={!run} checked={overlay} onChange={e => setOverlay(e.target.checked)} />Círculos</label>
          <label className="mask-toggle"><input type="checkbox" disabled={!contacts} checked={showContacts} onChange={e => setShowContacts(e.target.checked)} />Puntos de borde</label>
        </div>
        <details className="agent-settings"><summary>Capas e historial</summary>
          <label className="field"><span>Ejecución guardada</span>
            <select disabled={busy || !run} value={run?.run_id || ''} onChange={e => openRun(e.target.value)}>
              {!run && <option value="">Sin ejecución guardada</option>}
              {history.map(item => <option key={item.run_id} value={item.run_id}>{new Date(item.created_at).toLocaleString()}</option>)}
            </select>
          </label>
          <label className="field"><span>Capa principal</span>
            <select disabled={!run} value={primary} onChange={e => setComparison({
              ...comparison, primary: e.target.value, secondary: e.target.value === secondary ? primary : secondary,
            })}>
              {layers.map(key => <option key={key} value={key}>{names[key]}</option>)}
            </select>
          </label>
          <label className="field"><span>Capa secundaria</span>
            <select disabled={!run} value={secondary} onChange={e => setComparison({ ...comparison, secondary: e.target.value })}>
              <option value="">Ninguna</option>
              {layers.filter(key => key !== primary).map(key => <option key={key} value={key}>{names[key]}</option>)}
            </select>
          </label>
        </details>
        <details className="shortcut-note">
          <summary>Atajos del editor</summary>
          <p>C activa Círculo. Arrastra desde un borde hasta el borde opuesto y suelta para guardar. Esc cancela el dibujo. M activa Mano. Ctrl o ⌘ + rueda cambia el zoom en el puntero.</p>
          <p>+ / − cambia el zoom. F centra y amplía el círculo seleccionado. 0 ajusta la imagen. V muestra u oculta los círculos.</p>
          <p>← / ↑ anterior · → / ↓ siguiente · Inicio / Fin primero o último · Re Pág / Av Pág imagen anterior o siguiente.</p>
          <p>Supr o Retroceso elimina el seleccionado. Ctrl + Z deshace. Ctrl + Y o Ctrl + Mayús + Z rehace. En Mac también puedes usar ⌘.</p>
        </details>
      </section>
    </aside>
    <section className="main"><article className="card viewer loco-viewer">
      <h2>Detección de fibras y bordes</h2>
      <div className="viewer-toolbar loco-toolbar">
        <button className={'icon-tool' + (tool === 'pan' ? ' toggle-active' : '')} aria-pressed={tool === 'pan'} title="Mover vista (M)" disabled={!run} onClick={() => chooseTool('pan')}>{handIcon}Mano</button>
        <button className={'icon-tool' + (tool === 'circle' ? ' toggle-active' : '')} aria-pressed={tool === 'circle'} title="Dibujar de borde a borde (C)" disabled={!canStartDrawing} onClick={() => run ? chooseTool('circle') : openRun(null, true)}>Círculo</button>
        <span className="toolbar-sep" />
        <button className="icon-tool" aria-label="Alejar" onClick={() => zoomBy(0.84)} disabled={!run}>-</button>
        <button className="icon-tool" aria-label="Acercar" onClick={() => zoomBy(1.2)} disabled={!run}>+</button>
        <button className="icon-tool" onClick={() => setView(fit)} disabled={!run}>Reiniciar</button>
        <span className="zoom-chip">{Math.round(view.scale * 100)}%</span>
        <span className="toolbar-sep" />
        <label className="compact-slider mask-opacity-control" title="Intensidad de la capa secundaria sobre la principal">Transparencia
          <input aria-label="Intensidad de la capa secundaria" type="range" min="0" max="100" step="1" value={comparison.opacity} disabled={!run || !secondary}
            onChange={e => setComparison({ ...comparison, opacity: Number(e.target.value) })} />
          <span>{comparison.opacity}%</span>
        </label>
        <label className="compact-slider mask-opacity-control">Círculos
          <input aria-label="Opacidad de los círculos" type="range" min="0.05" max="1" step="0.05" value={opacity} disabled={!run || !overlay} onChange={e => setOpacity(Number(e.target.value))} />
          <span>{Math.round(opacity * 100)}%</span>
        </label>
        <button className="primary" type="submit" form="agent-run" disabled={busy || !id || (maskSource !== 'agente' && !supportId)}>{busy ? 'Procesando…' : 'Detectar fibras y bordes'}</button>
        <button disabled={!circle} onClick={() => focusCircle(circle)}>Zoom al círculo</button>
        <button disabled={busy || !contacts || !run?.circles.length} onClick={openMeasurements}>Abrir medición de diámetros</button>
      </div>
      <div className="loco-workspace loco-lab-workspace">
        <div id="agent-stage" ref={stageRef} tabIndex={0} aria-label="Visor de círculos" className={'stage loco-stage mode-' + tool + (panning ? ' is-panning' : '') + (run ? ' has-image' : '')}>
          {run ? <svg role="img" aria-label={[names[primary], names[secondary]].filter(Boolean).join(' + ') + ' de ' + run.image_name} viewBox={viewBox}
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', userSelect: 'none',
              '--agent-edge-dot-size': Math.max(2, run.edge_dot_size_px || 0) + 'px' }}
            onPointerDown={startPan} onPointerMove={movePan} onPointerUp={endPan} onPointerCancel={endPan} onLostPointerCapture={endPan}>
            <image crossOrigin="anonymous" href={displayLayer(primary)} width={run.width} height={run.height} preserveAspectRatio="none" />
            {secondaryLayer && <image crossOrigin="anonymous" href={secondaryLayer} width={run.width} height={run.height} preserveAspectRatio="none"
              opacity={comparison.opacity / 100} pointerEvents="none" />}
            {run.circles.map((c,i) => <g key={c.id} className={i === selection ? 'agent-circle-selected' : 'agent-circle'}>
              {overlay && <circle opacity={opacity} data-circle-index={i} cx={c.x} cy={c.y} r={c.radius_px} className={i === selection ? 'loco-best-circle' : 'loco-seed-circle'}>
                <title>Círculo {c.id}</title>
              </circle>}
              {showContacts && contacts?.[c.id]?.map((p,j)=>
                <circle key={j} className="agent-edge-dot" pointerEvents="none" cx={p.x} cy={p.y}
                  r={Math.min(0.85, 3.5 / view.scale)} />)}
              {showContacts && edgeReviewFor(run,c)?.tentative?.map((p,j)=>
                <circle key={'tentative'+j} className="agent-edge-dot agent-edge-tentative" pointerEvents="none"
                  cx={p.x} cy={p.y} r={Math.min(0.85, 3.5 / view.scale)} />)}
            </g>)}
            {draft && <circle pointerEvents="none" cx={draft.x} cy={draft.y} r={draft.radius_px} className="loco-best-circle" />}
          </svg> : <div className="placeholder">{busy ? 'Cargando imagen…' : id ? 'Pulsa Detectar fibras y bordes o dibuja un círculo en la imagen.' : 'Agrega una imagen al proyecto para procesarla.'}</div>}
        </div>
        <aside className="loco-debug-panel loco-lab-panel">
          <div className="loco-step-head"><strong>Resultado del agente</strong><span>{error || edgeError ? 'error' : busy ? 'cargando' : computingEdges ? 'buscando bordes' : run ? 'listo' : 'pendiente'}</span></div>
            <TargetResult metric={run?.circle_review} unit="círculos"/>
          {run && <div className="kpi-row">
            <span>Círculos <strong>{run.circles.length}</strong></span>
            <span>Con cuatro puntos <strong>{contacts ? run.circles.filter(c => contacts[c.id]?.length === 4).length : computingEdges ? '…' : 0}</strong></span>
          </div>}
          <details className="agent-settings"><summary>Detalles de la detección</summary>
            <div className="kpi-row">{metrics.map(([label, value]) => <span key={label}>{label} <strong>{value ?? '–'}</strong></span>)}</div>
            {review ? <>
              <p className="small">Círculo #{circle.id} · {review.points.length} cruces elegidos en rojo. La máscara propone {circle.mask_crossings}. {review.note}</p>
              <details className="shortcut-note"><summary>Reglas de esta revisión</summary><ol>{run.edge_review.rules.map(rule => <li key={rule}>{rule}</li>)}</ol></details>
            </> : <>
              <p className="small">La máscara propone los cruces y el contraste de la foto suavizada afina su posición.</p>
              {circle && contacts && <p className="small">Círculo #{circle.id} · {contacts[circle.id].length} puntos · {contacts[circle.id].filter(p=>!p.supported).length} situados solo por la máscara.</p>}
            </>}
          </details>
          <div className="loco-lab-section">
            <h3>Círculos propuestos</h3>
            <div className="loco-candidate-list" ref={listRef}>
              {run?.circles.length ? run.circles.map((c, i) => <button key={c.id} aria-pressed={i === selection}
                className={i === selection ? 'selected' : ''} onClick={() => selectCircle(i)}>
                <strong>#{c.id}{c.source === 'manual' && ' · Manual'}</strong><span>({Number(c.x.toFixed(1))}, {Number(c.y.toFixed(1))})</span><em>r {Number(c.radius_px).toFixed(1)} px · {contacts?.[c.id]?.length ?? '…'} puntos
                  {contacts?.[c.id]?.some(p=>!p.supported) && ' · Revisar contraste'}</em>
              </button>) : <div className="placeholder small">Sin círculos.</div>}
            </div>
            <button className="danger" title="Supr o Retroceso" disabled={busy || !circle} onClick={() => editCircle('remove')}>
              {circle ? 'Eliminar círculo #' + circle.id : 'Eliminar círculo'}
            </button>
            <div className="inline">
              <button disabled={busy || !undo.length} title="Ctrl + Z" onClick={() => editCircle('undo')}>Deshacer</button>
              <button disabled={busy || !redo.length} title="Ctrl + Y" onClick={() => editCircle('redo')}>Rehacer</button>
            </div>
          </div>
          {run && <a className="file-action" href={url} target="_blank" rel="noreferrer">Ver parámetros y coordenadas en JSON</a>}
        </aside>
      </div>
    </article></section>
  </div>
}
