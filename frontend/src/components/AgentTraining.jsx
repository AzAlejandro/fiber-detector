import React, { useEffect, useRef, useState } from 'react'
import { API_BASE, apiGet, apiPost } from '../api'

const labels = {
  ok: 'Aceptado', bulk: 'Aceptado en lote', multifibra: 'Multifibra', sin_fibra: 'No hay fibra',
  fibra_incompleta: 'Fibra incompleta', doble_fibra: 'Doble fibra', fibra: 'Fibra', halo: 'Halo',
  fondo: 'Fondo', dudoso: 'Dudoso', incorrecto: 'Está mal · clase desconocida',
}
const reasons = {
  circulos: ['multifibra', 'sin_fibra', 'fibra_incompleta', 'doble_fibra'],
  scribbles: ['fibra', 'halo', 'fondo', 'dudoso', 'incorrecto'],
}
const colors = { fibra: '#00ddf4', halo: '#ff9e27', fondo: '#9b5af3' }
const titles = { circulos: 'Círculos', scribbles: 'Scribbles', cruces: 'Cruces', descripcion: 'Lectura visual del proyecto' }
const fit = { x: .5, y: .5, z: 1 }

export default function AgentTraining({ tab, project, projects, images }) {
  const [libraryKind, setLibraryKind] = useState('scribbles')
  if (!project) return <section className="card"><h2>Entrenamiento del agente</h2><p>Selecciona un proyecto en la sección Proyecto para abrir sus rondas y skills.</p></section>
  const library = tab === 'trainSkills'
  const kind = library ? libraryKind : tab === 'trainCircles' ? 'circulos' : 'scribbles'
  return <Workspace key={project.project_id + kind + library} {...{ project, projects, kind, library, setLibraryKind }}
    images={images.filter(im => im.project_ids?.includes(project.project_id))} />
}

function Workspace({ project, projects, images, kind, library, setLibraryKind }) {
  const base = '/api/agent-training/' + encodeURIComponent(project.project_id) + '/' + kind
  const [state, setState] = useState(null)
  const [round, setRound] = useState(null)
  const [imageId, setImageId] = useState(images[0]?.image_id || '')
  const [markId, setMarkId] = useState('')
  const [wrong, setWrong] = useState(false)
  const [interval, setInterval] = useState([0,100])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [copyId, setCopyId] = useState(0)
  const [draft, setDraft] = useState(null)
  const [ruleEdits, setRuleEdits] = useState({})
  const [hide, setHide] = useState(false)
  const [focus, setFocus] = useState(false)
  const gate = useRef(false)
  const [view, setView] = useState(fit)
  const svg = useRef(null)
  const drag = useRef(null)
  const selected = round?.marks.find(m => m.id === markId)
  const reviewed = Object.keys(round?.reviews || {}).length
  const remaining = (round?.marks.length || 0) - reviewed
  const reasonList = reasons[kind]
  const copy = state?.catalog.find(s => s.id === copyId)
  const selectedImage = images.find(i => i.image_id === imageId) || images[0]
  const photoId = round?.image || selectedImage?.image_id
  const photoName = round?.name || selectedImage?.image_name
  const photoUrl = photoId && API_BASE + base + '/photo/' + encodeURIComponent(photoId)
  const width = round?.width || selectedImage?.shape_hw?.[1]
  const height = round?.height || selectedImage?.shape_hw?.[0]
  const canNavigate = Boolean(state && !library && photoUrl && width && height)
  const imageRounds = state?.rounds.filter(r => r.image === selectedImage?.image_id) || []
  const originName = id => projects.find(p => p.project_id === id)?.name || id

  function showRound(r) {
    setRound(r)
    setRuleEdits({})
    setMarkId(r?.marks.find(m => !r.reviews[m.id])?.id || r?.marks[0]?.id || '')
    setWrong(false)
    setInterval([0,100])
    setView(fit)
    setFocus(false)
  }
  useEffect(() => {
    let mounted = true
    async function load() {
      const s = await apiGet(base + '/state')
      const initial = s.rounds.find(r => r.reviewed < r.total) || s.rounds[0]
      const r = !library && initial ? await apiGet(base + '/rounds/' + initial.id) : null
      if (!mounted) return
      setState(s)
      setCopyId(s.active.id)
      if (r) { setImageId(r.image); showRound(r) }
    }
    load().catch(e => { if (mounted) setError(e.message) })
    return () => { mounted = false }
  }, [base, library])

  async function work(fn) {
    if (gate.current) return
    gate.current = true; setBusy(true); setError('')
    try { await fn() } catch (e) { setError(e.message) }
    finally { gate.current = false; setBusy(false) }
  }
  async function refresh() {
    const s = await apiGet(base + '/state')
    setState(s)
    return s
  }
  async function openImage(id) {
    setImageId(id)
    showRound(null)
    const latest = state.rounds.find(r => r.image === id)
    if (latest) showRound(await apiGet(base + '/rounds/' + latest.id))
  }
  async function newRound(proposal = {}) {
    const r = await apiPost(base + '/rounds', { ...proposal, image_id: selectedImage.image_id, skill_id: state.active.id })
    await refresh()
    setImageId(r.image); showRound(r)
  }
  function choose(m) { if (m) { setMarkId(m.id); setWrong(false); setInterval([0,100]) } }
  function nextMark(r, from) {
    const i = r.marks.findIndex(m => m.id === from)
    return [...r.marks.slice(i + 1), ...r.marks.slice(0, i + 1)].find(m => !r.reviews[m.id])
  }
  async function record(decision) {
    if (!round || !selected) return
    const partial = wrong && kind==='scribbles' && reasonList.includes(decision)
    const r = await apiPost(base + '/rounds/' + round.id + '/review', { revision: round.revision, mark: markId, decision,
      ...(partial ? {start:interval[0],end:interval[1]} : {}) })
    setRound(r); setWrong(false); setInterval([0,100])
    setRuleEdits(edits => Object.fromEntries(Object.entries(edits).filter(([key])=>r.patterns?.some(p=>p.key===key))))
    const s = await refresh()
    if (!decision) return
    const next = nextMark(r, markId)
    if (next) choose(next)
    else {
      const other = s.rounds.find(row => row.id !== r.id && row.reviewed < row.total)
      if (other) {
        const nextRound = await apiGet(base + '/rounds/' + other.id)
        setImageId(nextRound.image); showRound(nextRound)
      }
    }
  }
  async function saveSkill(options) {
    const skill = await apiPost(base + '/skills', { expected: state.active.id, body: state.active.body, ...options })
    await refresh(); setCopyId(skill.id); setDraft(null)
  }
  useEffect(() => {
    if (!round || library) return
    function onKey(e) {
      if (busy || e.repeat || e.isComposing || e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey ||
          e.target.isContentEditable || e.target.closest?.('input,textarea,select,summary,dialog')) return
      const key = e.key.toLowerCase()
      if (key === 'b') work(() => record('ok'))
      else if (key === 'm') setWrong(!wrong)
      else if (wrong && reasonList[Number(key)-1]) work(() => record(reasonList[Number(key)-1]))
      else if (key === 'arrowright' || key === 'arrowleft') {
        const i = round.marks.findIndex(m => m.id === markId)
        choose(round.marks[i + (key === 'arrowright' ? 1 : -1)])
      } else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  function centerMark(m) {
    if (!m || !round) return
    const xs = m.puntos?.map(p => p[0]) || [m.x-m.radius_px,m.x+m.radius_px]
    const ys = m.puntos?.map(p => p[1]) || [m.y-m.radius_px,m.y+m.radius_px]
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
    const side = Math.max(48, 3*(maxX-minX), 3*(maxY-minY))
    setView({ x:(maxX+minX)/2/round.width, y:(maxY+minY)/2/round.height, z:Math.max(1,Math.min(round.width,round.height)/side) })
  }
  useEffect(() => { if (focus) centerMark(selected) }, [focus, markId, round?.id])
  function inspectMark(id) {
    const mark = round.marks.find(m => m.id === id)
    if (mark) { choose(mark); setFocus(true); centerMark(mark) }
  }
  useEffect(() => {
    const node = svg.current
    if (!node || !canNavigate) return
    function wheel(e) {
      if (!(e.ctrlKey || e.metaKey) || !e.deltaY) return
      e.preventDefault()
      const at = new DOMPoint(e.clientX,e.clientY).matrixTransform(node.getScreenCTM().inverse())
      setView(v => {
        const z = Math.min(64,Math.max(.25,v.z*(e.deltaY<0?1.15:1/1.15)))
        return { z, x:v.x+(at.x/width-v.x)*(1-v.z/z), y:v.y+(at.y/height-v.y)*(1-v.z/z) }
      })
    }
    node.addEventListener('wheel',wheel,{passive:false})
    return () => node.removeEventListener('wheel',wheel)
  }, [photoId, width, height, canNavigate])

  function start(e) {
    if (!e.isPrimary || e.button !== 0) return
    drag.current = { x:e.clientX,y:e.clientY,view,scale:e.currentTarget.getScreenCTM().a,mark:e.target.dataset.mark }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  function move(e) {
    const d = drag.current
    if (!d || !e.isPrimary) return
    const dx=e.clientX-d.x, dy=e.clientY-d.y
    if (Math.hypot(dx,dy)>3) d.moved=true
    if (d.moved) setView({...d.view,x:d.view.x-dx/d.scale/width,y:d.view.y-dy/d.scale/height})
  }
  function stop(e) {
    if (!e.isPrimary) return
    const d=drag.current
    if (e.type==='pointerup' && d && !d.moved && d.mark) choose(round.marks.find(m=>m.id===d.mark))
    drag.current=null
  }
  function markShape(m, halo=false) {
    const color=halo?'#ffe45e':m.puntos?colors[m.clase]:m.id===markId?'#ffe45e':'#35e9eb'
    return m.puntos ? <polyline key={m.id+(halo?'outline':'')} data-mark={m.id} fill="none" stroke={color} strokeLinejoin="round" strokeLinecap="round"
      points={m.puntos.map(p=>p.join(',')).join(' ')} strokeWidth={m.ancho_px+(halo?3:0)} />
      : <circle key={m.id} data-mark={m.id} cx={m.x} cy={m.y} r={m.radius_px} fill="transparent" stroke={color} strokeWidth={m.id===markId?2:1.3} vectorEffect="non-scaling-stroke" />
  }
  const status = error && <p className="small" role="alert">{error}</p>
  const skillDownload = state && <a className="file-action" href={API_BASE+'/api/agent-training/skills/'+(library?copyId:state.active.id)+'/SKILL.md'}>Descargar SKILL.md</a>
  const outcome = m => round.reviews[m.id] ? labels[round.reviews[m.id]] : 'Pendiente'
  const versionRounds = state?.rounds.filter(r => r.skill === (library?copyId:round?.skill)) || []
  const individual = versionRounds.reduce((n,r)=>n+r.reviewed-r.bulk-r.uncertain,0)
  const errors = versionRounds.reduce((n,r)=>n+r.errors,0)
  const groups = new Map()
  for (const r of state?.rounds || []) {
    const row = groups.get(r.version) || { version:r.version, rounds:0, individual:0, errors:0, uncertain:0, bulk:0 }
    row.rounds++; row.individual+=r.reviewed-r.bulk-r.uncertain; row.errors+=r.errors; row.uncertain+=r.uncertain; row.bulk+=r.bulk
    groups.set(r.version,row)
  }
  return <div className="layout" data-tour="workspace-agent-training">
    <aside className="left agent-sidebar">
      <section className="card">
        <h2>{project.name}</h2>
        {library ? <label className="field"><span>Tipo de skill</span><select value={kind} onChange={e=>setLibraryKind(e.target.value)}>
          <option value="descripcion">{titles.descripcion}</option><option value="scribbles">Scribbles</option><option value="circulos">Círculos</option><option value="cruces">Cruces</option></select></label> : <>
          <label className="field"><span>Imagen del proyecto</span><select disabled={!state||busy} value={selectedImage?.image_id||''} onChange={e=>work(()=>openImage(e.target.value))}>
            {images.map(i=><option key={i.image_id} value={i.image_id}>{i.image_name}</option>)}</select></label>
          <label className="field"><span>Ronda guardada</span><select disabled={busy||!imageRounds.length} value={round?.id||''} onChange={e=>work(async()=>showRound(await apiGet(base+'/rounds/'+e.target.value)))}>
            {!imageRounds.length&&<option value="">Sin rondas</option>}{imageRounds.map(r=><option key={r.id} value={r.id}>#{r.id} · skill v{r.version} · {r.reviewed}/{r.total} revisados</option>)}</select></label>
          <button className="primary" disabled={!selectedImage||busy||!state} onClick={()=>work(()=>newRound())}>Preparar ronda de {titles[kind].toLowerCase()}</button>
          {round && round.skill!==state?.active.id &&
            <button disabled={busy} onClick={()=>work(()=>newRound({from_round:round.id}))}>Reaplicar skill v{state.active.version} a esta propuesta</button>}
          {kind==='scribbles' && <details className="training-disclosure agent-disclosure-card"><summary>Importar propuesta del agente</summary><div className="training-disclosure-body">
            <p className="small">Selecciona el JSON con los trazos en las coordenadas de la imagen de biblioteca.</p>
            <input type="file" accept=".json" disabled={!selectedImage||busy||!state} aria-label="Importar propuesta JSON" onChange={e=>{
              const file=e.target.files[0];e.target.value=''
              if(file) work(async()=>{
                const p=JSON.parse(await file.text())
                if(!Array.isArray(p.trazos))throw Error('El archivo debe incluir la lista de trazos.')
                if(p.image_id && p.image_id!==selectedImage.image_id)throw Error('La propuesta pertenece a otra imagen.')
                if(!p.image_id && p.imagen && p.imagen.split(/[\\/]/).pop().replace(/\.[^.]+$/,'').toLowerCase()!==selectedImage.image_name.replace(/\.[^.]+$/,'').toLowerCase())throw Error('El nombre de la imagen de la propuesta no coincide.')
                if(p.tamano && (p.tamano[0]!==selectedImage.shape_hw[1] || p.tamano[1]!==selectedImage.shape_hw[0]))throw Error('Ajusta las coordenadas a la resolución de biblioteca.')
                await newRound({trazos:p.trazos,source:p.autor||'Propuesta importada'})
              })
            }}/></div></details>}
        </>}
        {status}
      </section>
      {state && <section className="card"><h2>{library?'Versiones guardadas':'Skill activa · v'+state.active.version}</h2>
        {library ? <label className="field"><span>Proyecto de origen y versión</span><select value={copyId} disabled={busy} onChange={e=>{setCopyId(Number(e.target.value)); setDraft(null)}}>
          {state.catalog.map(s=><option key={s.id} value={s.id}>{originName(s.project)} · v{s.version}{s.id===state.active.id?' · activa':''}</option>)}</select></label>
          : <details className="training-disclosure agent-disclosure-card"><summary>Ver instrucciones</summary><div className="training-disclosure-body agent-skill-text">{state.active.execution_body ?? state.active.body}</div></details>}
        <details className="training-disclosure agent-disclosure-card"><summary>Cómo generar la siguiente versión</summary>
          {state.generation_steps?.length
            ? <ol className="training-disclosure-body">{state.generation_steps.map(step => <li key={step}>{step}</li>)}</ol>
            : <p className="training-disclosure-body">Reinicia el servidor de LOCO y recarga la página para ver la guía de esta versión.</p>}
        </details>
        {skillDownload}
      </section>}
      {!library && state && <section className="card"><h2>Rondas del proyecto</h2>
        {['Pendientes','Completas'].map((group,i)=><details key={group} className="training-disclosure" open={i===0}><summary>{group} ({state.rounds.filter(r=>(r.reviewed===r.total)===Boolean(i)).length})</summary><div className="training-disclosure-body">
          {state.rounds.filter(r=>(r.reviewed===r.total)===Boolean(i)).map(r=><button key={r.id} disabled={busy} className="model-row" onClick={()=>work(async()=>{const data=await apiGet(base+'/rounds/'+r.id);setImageId(r.image);showRound(data)})}>
            {r.name} · #{r.id} · {r.reviewed}/{r.total}</button>)}</div></details>)}</section>}
    </aside>
    <section className="main"><article className="card viewer loco-viewer">
      <h2>{library?'Biblioteca de skills':'Revisión de '+titles[kind].toLowerCase()}</h2>
      {!state ? <div className="placeholder">Cargando entrenamiento…</div> : library ? <>
        {copy && <section className="loco-lab-section"><div className="loco-step-head"><strong>{originName(copy.project)} · {titles[kind]}</strong><span>v{copy.version}</span></div>
          {draft === null ? <p className="agent-skill-text">{copy.body}</p>
            : <><textarea autoFocus className="agent-skill-editor" aria-label="Instrucciones de la skill del proyecto" value={draft}
                maxLength={60000} disabled={busy} onChange={e=>setDraft(e.target.value)}/>
                <span className="small">{kind === 'descripcion' ? 'Cita una imagen o un círculo donde se vea el detalle que describes.' : 'Variables del proyecto: {{porcentaje_pintado}}, {{cantidad_circulos}}, {{tolerancia_puntos}} y {{tolerancia_circulos}}.'}</span></>}
          {copy.evidence.round && <p className="small">Revisión de origen · ronda #{copy.evidence.round} · {copy.evidence.reviewed}/{copy.evidence.total} marcas revisadas</p>}
          {copy.parent && <div className="small">Versión de origen: {state.catalog.filter(s=>s.id===copy.parent).map(s=>originName(s.project)+' · v'+s.version).join('')}</div>}
          {copy.id!==state.active.id
            ? <button disabled={busy} onClick={()=>work(()=>saveSkill({copy_id:copyId}))}>Usar una copia en {project.name}</button>
            : draft === null
              ? <button onClick={()=>setDraft(copy.body)}>Editar</button>
              : <div className="inline">
                  <button className="primary" disabled={busy||!draft.trim()||draft.trim()===copy.body} onClick={()=>work(()=>saveSkill({body:draft.trim()}))}>Guardar nueva versión</button>
                  <button disabled={busy} onClick={()=>setDraft(null)}>Cancelar</button>
                </div>}
        </section>}
        {groups.size>0 && <section className="loco-lab-section"><h3>Resultados por versión · {project.name}</h3>
          <div className="training-batch-table"><table><thead><tr><th>Skill</th><th>Rondas</th><th>Errores / individuales</th><th>Dudosos</th><th>En lote</th></tr></thead><tbody>
            {[...groups.values()].map(r=><tr key={r.version}><td>v{r.version}</td><td>{r.rounds}</td><td>{r.errors} / {r.individual}</td><td>{r.uncertain}</td><td>{r.bulk}</td></tr>)}
          </tbody></table></div></section>}
      </> : <>
        <div className="viewer-toolbar loco-toolbar">
          <button className="icon-tool" disabled={!canNavigate} onClick={()=>setView({...view,z:Math.max(.25,view.z/1.2)})}>−</button>
          <button className="icon-tool" disabled={!canNavigate} onClick={()=>setView({...view,z:Math.min(64,view.z*1.2)})}>+</button>
          <button className="icon-tool" disabled={!canNavigate} onClick={()=>{setFocus(false);setView(fit)}}>Ajustar</button>
          <span className="zoom-chip">{Math.round(view.z*100)}%</span>
          <button className="icon-tool" disabled={!selected} onClick={()=>{setFocus(true);centerMark(selected)}}>Zoom a la marca</button>
          <label className="mask-toggle"><input type="checkbox" checked={!hide} onChange={e=>setHide(!e.target.checked)}/>Ver marcas</label>
        </div>
        <div className="loco-workspace loco-lab-workspace">
          <div className="stage loco-stage mode-pan">
            {canNavigate ? <svg ref={svg} className="agent-training-canvas" role="img" aria-label={'Revisión de '+photoName}
              viewBox={[(view.x-.5/view.z)*width,(view.y-.5/view.z)*height,width/view.z,height/view.z].join(' ')}
              onPointerDown={start} onPointerMove={move} onPointerUp={stop} onPointerCancel={stop}>
              <image key={photoId} href={photoUrl} width={width} height={height}/>
              {!hide&&round&&<>{selected?.puntos&&markShape(selected,true)}{round.marks.map(m=>markShape(m))}</>}
              {!hide && wrong && selected?.puntos && (interval[0]>0||interval[1]<100) && <polyline points={selected.puntos.map(p=>p.join(',')).join(' ')}
                fill="none" stroke="#ff3266" strokeWidth={selected.ancho_px+1} pathLength="100" strokeDasharray={`0 ${interval[0]} ${interval[1]-interval[0]} 101`} pointerEvents="none"/>}
            </svg> : photoUrl ? <img className="agent-training-canvas" style={{objectFit:'contain'}} src={photoUrl} alt={photoName}/>
              : <div className="placeholder">Agrega imágenes a este proyecto para entrenar.</div>}
          </div>
          <aside className="loco-debug-panel loco-lab-panel">
            <div className="loco-step-head"><strong>{round?.name||titles[kind]}</strong><span>{round?(remaining?'En revisión':'Completa'):'Sin ronda'}</span></div>
            <div className="kpi-row"><span>Revisados <strong>{reviewed}/{round?.marks.length||0}</strong></span><span>Pendientes <strong>{remaining}</strong></span></div>
            {round && <>
              <p className="small">{round.source} · skill v{state.rounds.find(r=>r.id===round.id)?.version}</p>
              <label className="field"><span>{kind==='circulos'?'Círculo':'Trazo'}</span><select value={markId} disabled={busy} onChange={e=>choose(round.marks.find(m=>m.id===e.target.value))}>
                {round.marks.map(m=><option key={m.id} value={m.id}>#{m.id}{m.clase?' · '+labels[m.clase]:''} · {outcome(m)}</option>)}</select></label>
              <div className="inline"><button className="primary" disabled={busy} onClick={()=>work(()=>record('ok'))}>Está bien (B)</button><button disabled={busy} aria-expanded={wrong} onClick={()=>setWrong(!wrong)}>Está mal (M)</button></div>
              {wrong && <div className="loco-lab-section"><h3>{kind==='circulos'?'Motivo del rechazo':'Corrección del trazo'}</h3>
                {kind==='scribbles' && <details className="training-disclosure"><summary>Corregir solo un tramo</summary><div className="training-disclosure-body">
                  <label className="field"><span>Desde {interval[0]} %</span><input type="range" min="0" max={interval[1]-1} value={interval[0]} onChange={e=>setInterval([Number(e.target.value),interval[1]])}/></label>
                  <label className="field"><span>Hasta {interval[1]} %</span><input type="range" min={interval[0]+1} max="100" value={interval[1]} onChange={e=>setInterval([interval[0],Number(e.target.value)])}/></label>
                </div></details>}
                {reasonList.map((v,i)=><button key={v} disabled={busy} onClick={()=>work(()=>record(v))}>{i+1} · {labels[v]}</button>)}</div>}
              <button disabled={busy||!round.reviews[markId]} onClick={()=>work(()=>record(''))}>Quitar revisión</button>
              <button disabled={busy||!remaining} onClick={()=>work(()=>record('bulk'))}>Aceptar {remaining} pendientes de esta imagen</button>
              <section className="loco-lab-section"><h3>Resultados de esta versión en el proyecto</h3>
                <div className="kpi">Errores individuales <strong>{errors} / {individual}</strong></div>
                <p className="small">{versionRounds.length} rondas · {versionRounds.reduce((n,r)=>n+r.bulk,0)} aceptados en lote · {versionRounds.reduce((n,r)=>n+r.uncertain,0)} dudosos</p>
                {reviewed>0 && <details className="training-disclosure"><summary>Veredictos de esta ronda</summary><div className="training-disclosure-body">
                  {[...new Set(Object.values(round.reviews))].map(v=><div className="kpi" key={v}>{labels[v]} <strong>{Object.values(round.reviews).filter(d=>d===v).length}</strong></div>)}
                </div></details>}
                {round.patterns?.length>0 && <details className="training-disclosure agent-disclosure-card">
                  <summary>Analizar errores y dudas de esta ronda</summary><div className="training-disclosure-body">
                    {round.patterns.map(p=><section key={p.key} className="loco-lab-section">
                      <strong>{labels[p.proposed] || 'Círculo'} → {labels[p.decision]}</strong>
                      <span className="small">{p.decision==='dudoso' ? p.ids.length+' dudosos' : p.ids.length+' de '+p.individual+' revisiones individuales de '+p.proposed}
                        {p.partial>0 && ' · '+p.partial+' tramos parciales'}</span>
                      <label className="field"><span>Inspeccionar en la imagen</span>
                        <select value="" onChange={e=>inspectMark(e.target.value)}><option value="">Elegir una marca</option>
                          {p.ids.map(id=><option key={id} value={id}>#{id} · {labels[p.decision]}</option>)}
                          {p.comparison && <option value={p.comparison}>#{p.comparison} · Aceptada para comparar</option>}
                        </select></label>
                      <label className="field"><span>Regla para la próxima ronda</span><textarea rows={4} maxLength={1500} disabled={busy}
                        value={ruleEdits[p.key] ?? p.rule} onChange={e=>setRuleEdits({...ruleEdits,[p.key]:e.target.value})}/></label>
                    </section>)}
                  </div></details>}
                <button disabled={busy||!reviewed||Object.values(ruleEdits).some(text=>!text.trim())||state.catalog.some(s=>s.project===project.project_id&&s.evidence.round===round.id&&s.evidence.revision===round.revision)}
                  onClick={()=>work(()=>saveSkill({round_id:round.id, revision:round.revision, rules:ruleEdits}))}>Guardar skill con esta revisión</button>
              </section>
            </>}
          </aside>
        </div>
      </>}
    </article></section>
  </div>
}
