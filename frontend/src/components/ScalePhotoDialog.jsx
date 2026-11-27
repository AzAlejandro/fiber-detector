import React, { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { apiPost } from '../api'
import { convertScaleLength } from './CalibrationPanel'
import { scaleBarBounds } from '../scaleBarView.mjs'

const format = new Intl.NumberFormat('es-CL', { maximumSignificantDigits: 8 })

function savedLine(cal, horizontal) {
  if (!cal || cal.direct_factor || ![cal.line_x1, cal.line_y1, cal.line_x2, cal.line_y2].every(Number.isFinite)) return null
  return [{ x: cal.line_x1, y: cal.line_y1 }, { x: cal.line_x2, y: horizontal ? cal.line_y1 : cal.line_y2 }]
}

function horizontalLine(start, end) {
  return [start, { x: end.x, y: start.y }]
}

export default function ScalePhotoDialog({ photo, onClose, onSaved, handIcon }) {
  const dialog = useRef(null)
  const stage = useRef(null)
  const image = useRef(null)
  const target = useRef(null)
  const pan = useRef(null)
  const [panning, setPanning] = useState(false)
  const [viewport, setViewport] = useState({ width: 1, height: 1 })
  const [size, setSize] = useState(null)
  const [zoom, setZoom] = useState(1)
  const [failed, setFailed] = useState(false)
  const [editing, setEditing] = useState(photo.reviewScale === 'editar')
  const [saved, setSaved] = useState(null)
  const cal = saved || photo.calibration
  const [value, setValue] = useState(() => cal?.direct_factor ? '' : String(cal?.known_value ?? ''))
  const [unitCode, setUnitCode] = useState(cal?.unit || 'nm')
  const [draftLine, setDraftLine] = useState(null)
  const [drawing, setDrawing] = useState(editing)
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const gesture = useRef(null)
  const saving = useRef(false)
  const focusScale = useRef(editing)
  const valueInput = useRef(null)
  const [status, setStatus] = useState('')

  useEffect(() => {
    if (!draftLine && cal) {
      setValue(cal.direct_factor ? '' : String(cal.known_value ?? ''))
      setUnitCode(cal.unit || 'nm')
    }
  }, [photo.calibration])

  useEffect(() => {
    const el = dialog.current
    el.showModal()
    const observer = new ResizeObserver(() => setViewport({ width: stage.current.clientWidth, height: stage.current.clientHeight }))
    observer.observe(stage.current)
    return () => { observer.disconnect(); el.close() }
  }, [])

  const factor = size ? Math.min(viewport.width / size.width, viewport.height / size.height) : 1
  const width = size ? size.width * factor * zoom : 0
  const height = size ? size.height * factor * zoom : 0
  const hasScale = cal?.unit_per_px > 0
  const unit = cal?.unit === 'um' ? 'µm' : 'nm'
  const line = (!drawing && preview) || draftLine || savedLine(cal, editing)
  const displayLine = preview || line
  const pixels = line ? Math.abs(line[1].x - line[0].x) : 0
  const knownValue = Number(value.trim().replace(',', '.'))
  const conversion = knownValue / pixels

  function imagePoint(e) {
    const point = new DOMPoint(e.clientX, e.clientY).matrixTransform(e.currentTarget.getScreenCTM().inverse())
    return { x: Math.max(0, Math.min(size.width - 1, point.x)), y: Math.max(0, Math.min(size.height - 1, point.y)) }
  }
  function startLine(e) {
    if (!editing || busy || !e.isPrimary || e.button !== 0) return
    const point = imagePoint(e)
    if (!drawing) {
      const handle = e.target.dataset.handle
      if (!handle || !line) return
      gesture.current = { handle, line, point, pointerId: e.pointerId }
      e.currentTarget.setPointerCapture(e.pointerId)
      e.preventDefault()
      return
    }
    const start = preview?.[0] || point
    gesture.current = { start, finishing: !!preview, x: e.clientX }
    e.currentTarget.setPointerCapture(e.pointerId)
    setPreview(horizontalLine(start, point))
  }
  function adjustedLine(drag, point) {
    let dx = point.x - drag.point.x, dy = drag.handle === 'line' ? point.y - drag.point.y : 0
    const moved = drag.line.filter((_, i) => drag.handle === 'line' || drag.handle === String(i))
    dx = Math.max(-Math.min(...moved.map(p => p.x)), Math.min(size.width - 1 - Math.max(...moved.map(p => p.x)), dx))
    dy = Math.max(-Math.min(...moved.map(p => p.y)), Math.min(size.height - 1 - Math.max(...moved.map(p => p.y)), dy))
    return drag.line.map(p => moved.includes(p) ? { x: p.x + dx, y: p.y + dy } : p)
  }
  function moveLine(e) {
    if (!e.isPrimary) return
    const drag = gesture.current
    if (drag?.handle && drag.pointerId === e.pointerId) setPreview(adjustedLine(drag, imagePoint(e)))
    else if (drawing && preview) setPreview(horizontalLine(preview[0], imagePoint(e)))
  }
  function endLine(e) {
    const drag = gesture.current
    if (!drag || !e.isPrimary) return
    gesture.current = null
    if (drag.handle) {
      const next = adjustedLine(drag, imagePoint(e))
      if (Math.abs(next[1].x - next[0].x) >= 1) finishLine(next)
      setPreview(null)
      return
    }
    if (!drag.finishing && Math.abs(e.clientX - drag.x) < 3) return
    const end = imagePoint(e)
    if (Math.abs(end.x - drag.start.x) < 1) return
    setPreview(null)
    finishLine(horizontalLine(drag.start, end))
  }
  function finishLine(next) {
    setDraftLine(next)
    setDrawing(false)
    if (knownValue > 0 && Number.isFinite(knownValue)) save(next)
    else {
      setStatus('Ingresa la longitud impresa para guardar.')
      valueInput.current?.focus()
    }
  }
  async function save(next, length = knownValue, unit = unitCode) {
    if (!next || saving.current) return
    if (!Number.isFinite(length) || length <= 0) {
      setStatus('Ingresa una longitud mayor que cero para guardar.')
      return
    }
    const [a, b] = next
    const distance = Math.abs(b.x - a.x)
    if (distance < 1) return
    const payload = { image_id: photo.image_id, enabled: true, unit, known_value: length,
      pixel_distance: distance, unit_per_px: length / distance, line_x1: a.x, line_y1: a.y, line_x2: b.x, line_y2: b.y }
    if (cal && ['unit', 'known_value', 'line_x1', 'line_x2', 'line_y1', 'line_y2'].every(key => cal[key] === payload[key])) {
      setStatus('Escala guardada.')
      return
    }
    saving.current = true
    setBusy(true)
    setError('')
    try {
      const response = await apiPost('/api/diameter-research/calibration/save', payload)
      const result = response.calibration || payload
      setSaved(result)
      onSaved(photo.image_id, result, response.measurements?.updated_count)
      setStatus('Escala guardada.')
    } catch (err) { setError(err.message); setStatus('') }
    finally { saving.current = false; setBusy(false) }
  }

  function changeZoom(next, point, anchor) {
    const el = stage.current
    const at = anchor || { x: el.clientWidth / 2, y: el.clientHeight / 2 }
    target.current = {
      x: point?.x ?? (el.scrollLeft + at.x - Math.max(0, (el.clientWidth - width) / 2)) / width,
      y: point?.y ?? (el.scrollTop + at.y - Math.max(0, (el.clientHeight - height) / 2)) / height,
      at,
    }
    const nextZoom = Math.max(1, Math.min(32, next))
    if (nextZoom === zoom) centerView()
    else setZoom(nextZoom)
  }
  function centerView() {
    const point = target.current
    const el = stage.current
    if (!point || !el) return
    el.scrollTo(point.x * width - point.at.x, point.y * height - point.at.y)
    target.current = null
  }
  useLayoutEffect(centerView, [width, height])

  useEffect(() => {
    const el = stage.current
    function wheel(e) {
      if (!(e.ctrlKey || e.metaKey)) return
      e.preventDefault()
      if (!size || gesture.current || pan.current || !e.deltaY) return
      const rect = el.getBoundingClientRect()
      const delta = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? el.clientHeight : 1)
      changeZoom(zoom * Math.exp(-Math.max(-250, Math.min(250, delta)) * .002), null, {
        x: (e.clientX - rect.left) * el.clientWidth / rect.width,
        y: (e.clientY - rect.top) * el.clientHeight / rect.height,
      })
    }
    el.addEventListener('wheel', wheel, { passive: false })
    return () => el.removeEventListener('wheel', wheel)
  }, [size, zoom, width, height])

  function showScale() {
    const bounds = scaleBarBounds(image.current, line)
    changeZoom(Math.min(viewport.width / (bounds.right - bounds.left),
      viewport.height / (bounds.bottom - bounds.top)) / factor, {
      x: (bounds.left + bounds.right) / (2 * size.width),
      y: (bounds.top + bounds.bottom) / (2 * size.height),
    })
  }
  useLayoutEffect(() => {
    if (focusScale.current && size && viewport.width > 1 && viewport.height > 1 && cal !== undefined) {
      focusScale.current = false
      showScale()
    }
  }, [size, viewport, editing, cal])
  function selectTool(draw) {
    gesture.current = null
    setPreview(null)
    setDrawing(draw)
    if (draw) {
      setStatus('')
      setEditing(true)
    }
  }
  function editScale() {
    const bar = scaleBarBounds(image.current, line)
    const frame = image.current.getBoundingClientRect()
    const visible = stage.current.getBoundingClientRect()
    const nearBar = frame.left + bar.right * frame.width / size.width >= visible.left
      && frame.left + bar.left * frame.width / size.width <= visible.right
      && frame.top + bar.bottom * frame.height / size.height >= visible.top
      && frame.top + bar.top * frame.height / size.height <= visible.bottom
    if (zoom === 1 || !nearBar) {
      if (editing) showScale()
      else focusScale.current = true
    }
    selectTool(true)
  }

  function startPan(e) {
    if (!size || drawing || e.button !== 0 || !e.isPrimary || e.target.closest('[data-handle]')) return
    const el = e.currentTarget
    pan.current = { x: e.clientX, y: e.clientY, left: el.scrollLeft, top: el.scrollTop,
      ratio: el.clientWidth / el.getBoundingClientRect().width }
    el.setPointerCapture(e.pointerId)
    setPanning(true)
    e.preventDefault()
  }
  function movePan(e) {
    const p = pan.current
    if (p && e.isPrimary) e.currentTarget.scrollTo(p.left - (e.clientX - p.x) * p.ratio, p.top - (e.clientY - p.y) * p.ratio)
  }
  function endPan(e) {
    if (!e.isPrimary || !pan.current) return
    pan.current = null
    setPanning(false)
  }

  return <dialog className="scale-photo-dialog" ref={dialog} aria-labelledby="scale-photo-title"
    onCancel={e => { e.preventDefault(); if (!busy) onClose() }} onClick={e => { if (!busy && e.target === dialog.current) onClose() }}>
    <div className="viewer-toolbar">
      <h2 id="scale-photo-title">{photo.image_name}</h2>
      <button type="button" className="icon-tool" disabled={!size || busy || cal === undefined}
        onClick={editScale}>Editar escala</button>
      <button type="button" className={'icon-tool' + (!drawing ? ' toggle-active' : '')} aria-pressed={!drawing} disabled={!size}
        onClick={() => selectTool(false)}>{handIcon}Mano</button>
      <button type="button" className={'icon-tool' + (drawing ? ' toggle-active' : '')} aria-pressed={drawing}
        disabled={!size || busy || cal === undefined} onClick={() => selectTool(true)}>Dibujar línea</button>
      <button type="button" className="icon-tool" aria-label="Reducir zoom" disabled={!size || zoom <= 1} onClick={() => changeZoom(zoom / 1.5)}>−</button>
      <button type="button" className="icon-tool" aria-label="Ampliar foto" disabled={!size || zoom >= 32} onClick={() => changeZoom(zoom * 1.5)}>+</button>
      <button type="button" className="icon-tool" disabled={!size} onClick={() => changeZoom(1)}>Ajustar vista</button>
      <span className="zoom-chip">{Math.round(zoom * 100)}%</span>
      <button type="button" className="icon-tool scale-photo-close" disabled={busy} onClick={onClose} autoFocus>Cerrar</button>
    </div>
    <div className={'scale-photo-stage' + (panning ? ' is-panning' : '')} ref={stage}
      onPointerDown={startPan} onPointerMove={movePan} onPointerUp={endPan} onLostPointerCapture={endPan} onPointerCancel={endPan}>
      {failed || photo.error ? <p role="alert">{photo.error || 'No se pudo abrir la foto.'}</p>
        : photo.loading ? <p>Cargando foto…</p>
        : <div className="scale-photo-canvas">
          <div className="scale-photo-frame" style={{ width, height }}><img ref={image} src={photo.url} alt={photo.image_name} draggable="false"
            style={{ width, height }} onLoad={e => setSize({ width: e.target.naturalWidth, height: e.target.naturalHeight })}
            onError={() => setFailed(true)} />
          {size && <svg className={'scale-photo-overlay' + (drawing ? ' drawing' : '')} viewBox={`-0.5 -0.5 ${size.width} ${size.height}`}
            aria-label="Línea de calibración" onPointerDown={startLine} onPointerUp={endLine}
            onPointerMove={moveLine}
            onLostPointerCapture={() => { if (gesture.current?.handle) { gesture.current = null; setPreview(null) } }}
            onPointerCancel={() => { gesture.current = null; setPreview(null) }}>
            {displayLine && <g stroke="#ffce42" fill="#ffce42" pointerEvents="none">
              <line x1={displayLine[0].x} y1={displayLine[0].y} x2={displayLine[1].x} y2={displayLine[1].y}
                vectorEffect="non-scaling-stroke" strokeWidth="2" />
              {displayLine.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r={3 / (factor * zoom)}
                stroke="#322500" vectorEffect="non-scaling-stroke" />)}
              {editing && !drawing && !busy && <g className="scale-photo-handles">
                <line data-handle="line" x1={line[0].x} y1={line[0].y} x2={line[1].x} y2={line[1].y}
                  stroke="transparent" strokeWidth="14" vectorEffect="non-scaling-stroke" pointerEvents="stroke" />
                {line.map((p, i) => <circle key={i} data-handle={i} cx={p.x} cy={p.y} r={9 / (factor * zoom)}
                  fill="transparent" stroke="none" pointerEvents="all" />)}
              </g>}
            </g>}
          </svg>}</div>
        </div>}
    </div>
    <div className="scale-photo-footer">
      <div className="scale-photo-form" style={{ visibility: editing ? 'visible' : 'hidden' }}>
        <label>Longitud de la barra <input ref={valueInput} aria-label="Valor de escala" inputMode="decimal" value={value} disabled={busy}
          onChange={e => { setValue(e.target.value); setStatus('') }}
          onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur() }}
          onBlur={() => { if (draftLine && !drawing) save(draftLine) }} /></label>
        <label>Unidad <select aria-label="Unidad de escala" value={unitCode} disabled={busy} onChange={e => {
          const converted = convertScaleLength(value, unitCode, e.target.value)
          setValue(String(converted))
          setUnitCode(e.target.value)
          if (draftLine && !drawing) save(draftLine, Number(converted), e.target.value)
        }}>
          <option value="nm">nm</option><option value="um">µm</option>
        </select></label>
        {pixels > 0 && <output style={{ visibility: drawing || !editing ? 'hidden' : 'visible' }}>{format.format(pixels)} px
          {Number.isFinite(conversion) && conversion > 0 && ` · ${format.format(conversion)} ${unitCode === 'um' ? 'µm' : 'nm'}/px`}</output>}
        <span role="status">{busy ? 'Guardando…' : drawing ? (preview ? 'Marca el último extremo.' : 'Traza la barra completa para guardarla.') : status}</span>
        {error && <span role="alert">{error} <button type="button" onClick={() => save(draftLine)}>Reintentar</button></span>}
      </div>
      {!editing && <div className="scale-photo-hint">{photo.scaleError || (hasScale
        ? [line && format.format(cal.known_value) + ' ' + unit + ' = ' + format.format(cal.pixel_distance) + ' px', format.format(cal.unit_per_px) + ' ' + unit + '/px'].filter(Boolean).join(' · ')
        : 'Sin escala guardada')} · Ctrl + rueda para ampliar</div>}
    </div>
  </dialog>
}
