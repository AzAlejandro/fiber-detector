"""Project-scoped review rounds and versioned, portable agent instructions."""
import json
from hashlib import sha256
import sqlite3
from collections import Counter
from contextlib import closing, contextmanager
from io import BytesIO
from typing import Literal
from uuid import uuid4

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, Field

from . import agent_mode
from .agent_skill_guides import BASE
from .agent_targets import project_targets
from .library_store import load_library_image
from .persistence import OUTPUT_ROOT
from .projects_store import list_projects

router = APIRouter(prefix='/api/agent-training', tags=['Entrenamiento del agente'])
DB = OUTPUT_ROOT / 'agent_training' / 'training.sqlite3'
Kind = Literal['scribbles', 'circulos']
SkillKind = Literal['scribbles', 'circulos', 'cruces']
GUIDANCE = {
    'multifibra': 'Recorre todo el disco en la foto limpia. Si entra un ramal o un haz, desplaza el círculo a un tramo aislado y vuelve a seguir los cuatro cruces hasta la misma hebra.',
    'sin_fibra': 'Oculta las marcas y sigue los dos bordes más allá del disco en la foto original. Si solo ves grano, fondo o halo, descarta el candidato aunque la máscara produzca cuatro cruces.',
    'fibra_incompleta': 'Compara el centro del disco con el eje y comprueba el ancho a ambos lados. Si falta un flanco, recentra y ajusta el radio. Si sobra cobertura, reduce el radio o cambia de tramo. Tras el ajuste verifica dos cruces por borde. La etiqueta sola admite ambos sentidos.',
    'doble_fibra': 'Busca una franja de fondo que separe dos hebras dentro del disco. Sigue cada hebra fuera del círculo y mueve la marca a un tramo donde solo entre una.',
    'fibra': 'Sigue el eje en ambos sentidos antes de descartar una hebra tenue.',
    'halo': 'Comprueba que el trazo sigue una franja exterior contigua a la fibra.',
    'fondo': 'Contrasta el trazo con el fondo cercano y revisa si cruza una fibra.',
    'dudoso': 'Recorta la zona donde los bordes o la clase dejan de ser identificables.',
    'incorrecto': 'Revisa en el original los errores sin clase indicada y omite los tramos ambiguos.',
}
REASONS = {'circulos': list(GUIDANCE)[:4], 'scribbles': list(GUIDANCE)[4:]}

CONFUSIONS = {
    ('halo', 'fibra'): 'Antes de pintar halo, sigue el borde exterior de la hebra. Si el centro o el ancho del pincel quedan dentro de ese borde, recorta el trazo y marca como fibra solo el tramo interior confirmado.',
    ('fondo', 'fibra'): 'Antes de pintar fondo, amplía el tramo y busca dos bordes tenues que continúen a ambos lados. Si una hebra atraviesa la trayectoria, interrumpe el fondo en ambos bordes.',
    ('fibra', 'halo'): 'Sigue el eje de la hebra y su borde externo. Si el trazo corre por la franja contigua fuera del borde, desplázalo hacia el eje para marcar fibra o marca solo esa franja como halo.',
    ('fondo', 'halo'): 'Antes de marcar fondo junto a una hebra, sigue su flanco en contexto. Reserva para halo la franja exterior continua y empieza el fondo donde termine esa franja.',
    ('fibra', 'fondo'): 'Comprueba en el original si ambos bordes de la supuesta hebra continúan más allá del trazo. Si la línea se pierde entre el grano, retira la marca de fibra y revisa el fondo local.',
    ('halo', 'fondo'): 'Antes de extender el halo, comprueba que la franja siga pegada al mismo flanco. Detén el trazo donde la franja se confunda con la textura del fondo.',
}


def review_patterns(marks, reviews):
    """Group current individual corrections and pair them with a nearby accepted comparison."""
    groups = {}
    individuals = Counter()
    accepted = {}
    for mark in marks:
        decision = reviews.get(mark['id'])
        if decision in (None, 'bulk'):
            continue
        proposal = mark.get('clase', 'círculo')
        if decision != 'dudoso':
            individuals[proposal] += 1
        if decision == 'ok':
            accepted.setdefault(proposal, []).append(mark)
            continue
        pair = (proposal, decision)
        if pair not in groups:
            groups[pair] = dict(key='/'.join(pair), proposed=proposal, decision=decision,
                                ids=[], partial=0, rule=CONFUSIONS.get(pair, GUIDANCE[decision]))
        group = groups[pair]
        group['ids'].append(mark['id'])
        group['partial'] += int('original_key' in mark)

    def center(mark):
        if 'puntos' in mark:
            return np.mean(mark['puntos'], axis=0)
        return np.array([mark['x'], mark['y']])

    by_id = {m['id']: m for m in marks}
    for (proposal, _), group in groups.items():
        group['individual'] = individuals[proposal]
        nearby = accepted.get(proposal, [])
        group['comparison'] = None
        if nearby:
            at = center(by_id[group['ids'][0]])
            group['comparison'] = min(nearby, key=lambda m: np.linalg.norm(center(m)-at))['id']
    return sorted(groups.values(), key=lambda g: (g['decision']=='dudoso', -len(g['ids']), g['key']))


def generation_steps(kind):
    parameters = 'Toma las cantidades de los parámetros de la ejecución. Conserva los recuentos observados como evidencia de esa ronda y redacta la regla en términos de señales visibles y decisiones.'
    if kind == 'cruces':
        return [
            'Parte de la versión activa y de un círculo revisado. Registra la imagen, la ejecución, el ID, el centro y el radio para comparar la misma geometría.',
            'Superpón la propuesta y la corrección sobre el original. Determina qué flanco se siguió, qué arco quedó dudoso y si el error proviene del halo, la máscara, un cruce vecino, la geometría editada o la escala.',
            parameters,
            'En Biblioteca de skills, edita la versión activa y guarda una versión nueva. Describe qué evidencia haría aceptar, desplazar u omitir el contacto. Conserva la incertidumbre si el revisor no eligió un punto.',
            'Contrasta la regla en otra imagen. Separa círculos completos, pendientes y contactos corregidos; usa como denominador los casos que recibieron revisión individual.',
        ]
    inspect_marks = (
        'Compara la clase propuesta con la corrección humana (fibra, halo o fondo) sobre la foto original. Si solo cambió un tramo, usa ese tramo como ejemplo. Conserva la incertidumbre donde la clase quedó dudosa.'
        if kind == 'scribbles' else
        'Inspecciona el círculo rechazado en la foto original y conserva el motivo indicado: multifibra, sin fibra, fibra incompleta o doble fibra. Fibra incompleta abarca tanto falta como exceso de cobertura. Comprueba si una sola fibra atraviesa el disco y si cada borde cruza dos veces el perímetro.'
    )
    return [
        'Empieza con la skill activa del proyecto y del tipo de marca. Identifica la imagen, la ronda, su revisión y la versión que propuso las marcas.',
        inspect_marks,
        parameters,
        'Agrupa los errores por motivo. Calcula la tasa dividiendo los errores confirmados por las marcas con veredicto individual definido. Informa aparte los pendientes, los dudosos y los aceptados en lote. Si el denominador es cero, deja la tasa sin calcular.',
        'Abre «Analizar errores y dudas de esta ronda». Compara la marca con el original limpio y, cuando exista, con la marca aceptada de la misma propuesta. Comprueba qué rasgo las distingue. Ajusta la regla propuesta con una señal visible y una acción. Limita la regla al tramo revisado y conserva como desconocida cualquier causa sin evidencia.',
        'Guarda la nueva versión con «Guardar skill con esta revisión». Para evaluar el cambio, prepara una ronda en una imagen distinta y compara los errores tras la revisión humana, indicando cuántas marcas se revisaron en cada versión.',
    ]


@contextmanager
def database():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB, timeout=20)) as db:
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE IF NOT EXISTS skills(id INTEGER PRIMARY KEY, project TEXT, kind TEXT, version INTEGER,
                body TEXT, parent INTEGER, evidence TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project, kind, version));
            CREATE TABLE IF NOT EXISTS rounds(id INTEGER PRIMARY KEY, project TEXT, kind TEXT, image TEXT,
                name TEXT, width INTEGER, height INTEGER, skill INTEGER, source TEXT, marks TEXT,
                revision INTEGER DEFAULT 0, created TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS verdicts(round_id INTEGER, mark TEXT, decision TEXT,
                PRIMARY KEY(round_id, mark));
            CREATE TABLE IF NOT EXISTS review_history(round_id INTEGER, revision INTEGER, event TEXT,
                created TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(round_id,revision));
        """)
        with db:
            yield db


def project_exists(project):
    if not any(p['project_id'] == project for p in list_projects()['projects']):
        raise HTTPException(404, 'Proyecto desconocido.')


def active(db, project, kind):
    db.execute('INSERT OR IGNORE INTO skills(project,kind,version,body,evidence) VALUES(?,?,1,?,?)',
               (project, kind, BASE[kind], '{}'))
    return dict(db.execute('SELECT * FROM skills WHERE project=? AND kind=? ORDER BY version DESC LIMIT 1',
                           (project, kind)).fetchone())


def skill_by_id(db, sid):
    row = db.execute('SELECT * FROM skills WHERE id=?', (sid,)).fetchone()
    if not row:
        raise HTTPException(404, 'Versión desconocida.')
    return dict(row)


def skill_summary(row):
    item = dict(row)
    evidence = json.loads(item['evidence'])
    item['evidence'] = {k:v for k,v in evidence.items() if k not in ('changes','splits')}
    return item


def photo(project, iid):
    try:
        rgb, meta = load_library_image(iid)
    except FileNotFoundError as exc:
        raise HTTPException(404, 'Imagen desconocida.') from exc
    if project not in meta.get('project_ids', []):
        raise HTTPException(404, 'La imagen no pertenece al proyecto.')
    return rgb, meta


@router.get('/{project}/{kind}/photo/{iid}')
def image(project: str, kind: Kind, iid: str):
    rgb, _ = photo(project, iid)
    buffer = BytesIO()
    Image.fromarray(rgb).save(buffer, format='PNG')
    return Response(buffer.getvalue(), media_type='image/png')


@router.get('/{project}/{kind}/state')
def state(project: str, kind: SkillKind):
    project_exists(project)
    with database() as db:
        current = active(db, project, kind)
        rounds = db.execute("""SELECT r.id,r.name,r.image,r.skill,r.source,r.revision,r.created,s.version,
            json_array_length(r.marks) AS total, count(v.mark) AS reviewed,
            count(CASE WHEN v.decision NOT IN ('ok','bulk','dudoso') THEN 1 END) AS errors,
            count(CASE WHEN v.decision='bulk' THEN 1 END) AS bulk,
            count(CASE WHEN v.decision='dudoso' THEN 1 END) AS uncertain
            FROM rounds r JOIN skills s ON s.id=r.skill LEFT JOIN verdicts v ON v.round_id=r.id
            WHERE r.project=? AND r.kind=? GROUP BY r.id ORDER BY r.id DESC""", (project, kind))
        catalog = db.execute('SELECT * FROM skills WHERE kind=? ORDER BY id DESC', (kind,))
        targets = project_targets(project)
        resolved = targets.instruction(kind, current['body'])
        return dict(active={**skill_summary(current), 'execution_body': resolved}, targets=targets.model_dump(),
                    rounds=[dict(r) for r in rounds], catalog=[skill_summary(r) for r in catalog],
                    generation_steps=generation_steps(kind))


def read_round(db, project, kind, rid):
    row = db.execute('SELECT * FROM rounds WHERE project=? AND kind=? AND id=?', (project, kind, rid)).fetchone()
    if not row:
        raise HTTPException(404, 'Ronda desconocida en este proyecto.')
    marks = json.loads(row['marks'])
    reviews = dict(db.execute('SELECT mark, decision FROM verdicts WHERE round_id=?', (rid,)))
    return {**dict(row), 'marks': marks, 'reviews': reviews, 'patterns': review_patterns(marks, reviews)}


def geometry_key(mark):
    shape = [mark['clase'], mark['ancho_px'], mark['puntos']] if 'puntos' in mark else [mark['x'], mark['y'], mark['radius_px']]
    return sha256(json.dumps(shape, separators=(',', ':')).encode()).hexdigest()


def apply_examples(db, skill, image_id, marks):
    """Only transfer a saved human correction automatically to identical geometry."""
    decisions, splits, seen_rounds = {}, {}, set()
    while skill:
        evidence = json.loads(skill['evidence'])
        round_id = evidence.get('round')
        if evidence.get('image') == image_id and round_id not in seen_rounds:
            for key, value in evidence.get('changes', {}).items():
                decisions.setdefault(key, value)
            for key, pieces in evidence.get('splits', {}).items():
                splits.setdefault(key, pieces)
            seen_rounds.add(round_id)
        skill = skill_by_id(db, skill['parent']) if skill['parent'] else None
    updated = []
    expanded = [piece for m in marks for piece in splits.get(geometry_key(m), [m])]
    for mark in expanded:
        decision = decisions.get(geometry_key(mark))
        if decision in (None, 'ok', 'bulk'):
            updated.append(mark)
        elif 'puntos' in mark and decision in ('fibra','halo','fondo'):
            updated.append({**mark,'clase':decision})
    return updated


@router.get('/{project}/{kind}/rounds/{rid}')
def get_round(project: str, kind: Kind, rid: int):
    with database() as db:
        return read_round(db, project, kind, rid)


@router.get('/{project}/{kind}/rounds/{rid}/history')
def history(project: str, kind: Kind, rid: int):
    with database() as db:
        read_round(db, project, kind, rid)
        return [{**dict(row),'event':json.loads(row['event'])} for row in db.execute(
            'SELECT revision,event,created FROM review_history WHERE round_id=? ORDER BY revision',(rid,))]


class Stroke(BaseModel):
    id: str = Field(min_length=1, max_length=72)
    clase: Literal['fibra', 'halo', 'fondo']
    ancho_px: int = Field(ge=1, le=60)
    puntos: list[tuple[int, int]] = Field(min_length=2, max_length=10000)
    dudoso: bool = False


class NewRound(BaseModel):
    image_id: str
    skill_id: int
    source_run_id: str | None = None
    from_round: int | None = None
    trazos: list[Stroke] | None = Field(None, min_length=1, max_length=3000)
    source: str = Field('Propuesta importada', max_length=120)


def scribbles_from_circles(data):
    """Sample short fiber/outer-flank paths inside isolated circle neighborhoods."""
    folder = agent_mode.manifest_path(data['run_id']).parent
    with Image.open(folder / 'mascara.png') as raster:
        mask = np.asarray(raster) > 0
    with Image.open(folder / 'contraste.png') as raster:
        contrast = np.asarray(raster)
    marks = []
    def add(label, points):
        marks.append(dict(id=str(len(marks)+1), clase=label, ancho_px=1, puntos=points))
    for c in data['circles']:
        x,y,r = round(c['x']), round(c['y']), c['radius_px']
        n = int(np.floor(r))
        if n < 3:
            continue
        yy,xx = np.nonzero(mask[y-n:y+n+1,x-n:x+n+1])
        p = np.column_stack((xx-n, yy-n))
        p = p[(p*p).sum(axis=1) <= (r-1)**2]
        if len(p) < 5:
            continue
        _, vectors = np.linalg.eigh(np.cov(p.T))
        tangent, normal = vectors[:,1], vectors[:,0]
        center, flank = [], []
        for along in np.linspace(-r*.52,r*.52,5):
            band = p[np.abs(p@tangent-along)<1.3]
            if not len(band):
                break
            across = band@normal
            for line, offset in ((center,np.median(across)), (flank,np.max(across)+1.6)):
                point = np.rint([x,y]+along*tangent+offset*normal).astype(int).tolist()
                if not line or line[-1] != point:
                    line.append(point)
        if len(center)>=2 and all(mask[b,a] for a,b in center):
            add('fibra',center)
        if len(flank)>=2 and all(not mask[b,a] and contrast[b,a]<118 for a,b in flank):
            add('halo',flank)
    bottom = data['parameters']['field_height']
    for row in range(16,bottom-22,48):
        for col in range(16,data['width']-24,48):
            for dx,dy in ((0,0),(-5,-5),(8,5),(-4,10),(10,-5)):
                x,y = col+dx,row+dy
                patch = mask[y-8:y+9,x-11:x+12]
                line = contrast[y,x-4:x+5]
                if patch.mean() < .14 and not mask[y,x-4:x+5].any() and line.min() >= 105 and line.max() <= 145:
                    add('fondo',[[x-4,y],[x+4,y]])
                    break
    return marks


@router.post('/{project}/{kind}/rounds', status_code=201)
def create_round(project: str, kind: Kind, req: NewRound):
    project_exists(project)
    rgb, meta = photo(project, req.image_id)
    height,width = rgb.shape[:2]
    with database() as db:
        selected = active(db, project, kind)
    if selected['id'] != req.skill_id:
        raise HTTPException(409, 'La skill activa cambió. Actualiza antes de crear la ronda.')
    if sum(v is not None for v in (req.trazos,req.source_run_id,req.from_round)) > 1:
        raise HTTPException(422, 'Elige una sola fuente de propuestas.')
    if req.from_round is not None:
        with database() as db:
            old = read_round(db,project,kind,req.from_round)
        if old['image'] != req.image_id:
            raise HTTPException(422, 'La ronda de origen pertenece a otra imagen.')
        marks = old['marks']
        source = f"Skill reaplicada · ronda #{old['id']}"
    elif req.trazos is not None:
        if kind != 'scribbles':
            raise HTTPException(422, 'Los trazos requieren una ronda de scribbles.')
        marks = [s.model_dump() for s in req.trazos if not s.dudoso]
        if any(not (0<=x<width and 0<=y<height) for s in marks for x,y in s['puntos']):
            raise HTTPException(422, 'El trazo sale de la imagen de biblioteca.')
        source = req.source
    else:
        runs = agent_mode.list_runs(req.image_id, project, (meta.get('project_ids') or [None])[0] == project)
        if req.source_run_id:
            if not any(item['run_id']==req.source_run_id for item in runs):
                raise HTTPException(422, 'La ejecución indicada no pertenece al proyecto y a la imagen.')
            data = agent_mode.result(req.source_run_id)
        else:
            data = agent_mode.result(runs[0]['run_id']) if runs else agent_mode.run_agent(
                agent_mode.AgentRequest(image_id=req.image_id,project_id=project))
        marks = data['circles'] if kind == 'circulos' else scribbles_from_circles(data)
        source = ('Círculos guardados' if kind == 'circulos' else 'Trazos automáticos') + ' · ' + data['run_id'][:8]
    if not marks or len({str(m['id']) for m in marks}) != len(marks):
        raise HTTPException(422, 'Se requieren marcas visibles con identificadores únicos.')
    for m in marks:
        m['id'] = str(m['id'])
    with database() as db:
        if req.trazos is None:
            marks = apply_examples(db, selected, req.image_id, marks)
            if not marks:
                raise HTTPException(422, 'Las correcciones de la skill descartan todas las propuestas de esta imagen.')
            if len({str(m['id']) for m in marks}) != len(marks):
                marks = [{**m,'id':str(i)} for i,m in enumerate(marks,1)]
        rid = db.execute('INSERT INTO rounds(project,kind,image,name,width,height,skill,source,marks) VALUES(?,?,?,?,?,?,?,?,?)',
                         (project,kind,req.image_id,meta['image_name'],width,height,req.skill_id,source,json.dumps(marks))).lastrowid
        return read_round(db,project,kind,rid)


class Review(BaseModel):
    revision: int
    mark: str = ''
    decision: str
    start: int = Field(0, ge=0, le=100)
    end: int = Field(100, ge=0, le=100)


def split_stroke(mark, start, end):
    points = np.asarray(mark['puntos'], dtype=float)
    lengths = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
    if not start < end or lengths[-1] * (end-start)/100 < 1:
        raise HTTPException(422, 'Elige un tramo de al menos un píxel.')
    pieces = []
    for a,b in [(0,start),(start,end),(end,100)]:
        if a == b:
            continue
        lo,hi = lengths[-1]*np.array([a,b])/100
        def point(d):
            return [round(float(np.interp(d,lengths,axis)), 3) for axis in points.T]
        coords = [point(lo), *points[(lengths>lo)&(lengths<hi)].tolist(), point(hi)]
        pieces.append({**mark, 'original_key':mark.get('original_key') or geometry_key(mark),
                       'id':mark['id'] if (a,b)==(start,end) else uuid4().hex[:8], 'puntos':coords})
    return pieces


@router.post('/{project}/{kind}/rounds/{rid}/review')
def review(project: str, kind: Kind, rid: int, req: Review):
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        r = read_round(db,project,kind,rid)
        if req.revision != r['revision']:
            raise HTTPException(409, 'La ronda cambió en otra ventana. Vuelve a cargarla.')
        event = req.model_dump(exclude={'revision'})
        if req.decision == 'bulk':
            event['marks'] = [m['id'] for m in r['marks'] if m['id'] not in r['reviews']]
            db.executemany('INSERT OR IGNORE INTO verdicts VALUES(?,?,?)', [(rid,m['id'],'bulk') for m in r['marks']])
        else:
            mark = next((m for m in r['marks'] if m['id']==req.mark),None)
            if not mark or req.decision not in ['ok','',*REASONS[kind]]:
                raise HTTPException(422,'Marca o corrección inválida.')
            event['previous'] = r['reviews'].get(req.mark)
            if (req.start,req.end) != (0,100):
                if kind != 'scribbles' or not req.decision:
                    raise HTTPException(422, 'La selección parcial requiere un veredicto sobre un trazo.')
                pieces = split_stroke(mark,req.start,req.end)
                event.update(original=mark, pieces=pieces)
                pos = r['marks'].index(mark)
                r['marks'][pos:pos+1] = pieces
                db.execute('UPDATE rounds SET marks=? WHERE id=?',(json.dumps(r['marks']),rid))
                if req.mark in r['reviews']:
                    db.executemany('INSERT INTO verdicts VALUES(?,?,?)',[(rid,p['id'],r['reviews'][req.mark])
                                   for p in pieces if p['id']!=req.mark])
            if req.decision:
                decision = 'ok' if req.decision == mark.get('clase') else req.decision
                db.execute('INSERT OR REPLACE INTO verdicts VALUES(?,?,?)',(rid,req.mark,decision))
            else:
                db.execute('DELETE FROM verdicts WHERE round_id=? AND mark=?',(rid,req.mark))
        db.execute('UPDATE rounds SET revision=revision+1 WHERE id=?',(rid,))
        db.execute('INSERT INTO review_history(round_id,revision,event) VALUES(?,?,?)',
                   (rid,r['revision']+1,json.dumps(event)))
        return read_round(db,project,kind,rid)


class SaveSkill(BaseModel):
    expected: int
    body: str = Field(min_length=1,max_length=60000)
    copy_id: int | None = None
    round_id: int | None = None
    revision: int | None = None
    rules: dict[str, str] = Field(default_factory=dict, max_length=12)


@router.post('/{project}/{kind}/skills')
def save_skill(project: str, kind: SkillKind, req: SaveSkill):
    project_exists(project)
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        current = active(db,project,kind)
        if current['id'] != req.expected:
            raise HTTPException(409,'La versión activa cambió. Vuelve a cargar la biblioteca.')
        parent,body,evidence = current['id'],req.body.strip(),{}
        if req.copy_id is not None:
            src = skill_by_id(db,req.copy_id)
            if src['kind'] != kind:
                raise HTTPException(422,'La skill corresponde a otro tipo de revisión.')
            parent,body,evidence = src['id'],src['body'],json.loads(src['evidence'])
        elif req.round_id is not None:
            r = read_round(db,project,kind,req.round_id)
            if r['revision'] != req.revision:
                raise HTTPException(409,'Hay nuevas correcciones. Actualiza la ronda.')
            counts = Counter(r['reviews'].values())
            if not sum(counts.values()):
                raise HTTPException(422,'Revisa al menos una marca antes de incorporar la ronda.')
            evidence = dict(project=project,round=r['id'],image=r['image'],revision=r['revision'],skill=r['skill'],
                            reviewed=sum(counts.values()),total=len(r['marks']),counts=counts,
                            changes={geometry_key(m):r['reviews'][m['id']] for m in r['marks'] if m['id'] in r['reviews']})
            patterns = r['patterns']
            if req.rules.keys() - {p['key'] for p in patterns} or any(
                    not text.strip() or len(text) > 1500 for text in req.rules.values()):
                raise HTTPException(422, 'Cada regla debe corresponder a un patrón de esta revisión y tener entre 1 y 1500 caracteres.')
            examples = {}
            by_id = {m['id']: m for m in r['marks']}
            for pattern in patterns:
                key = pattern['key']
                if key in req.rules:
                    pattern['rule'] = req.rules[key].strip()
                for mid in [*pattern['ids'][:2], pattern['comparison']]:
                    if mid is not None:
                        examples[mid] = dict(mark=by_id[mid], decision=r['reviews'][mid])
            evidence['examples'] = list(examples.values())
            evidence['patterns'] = patterns
            splits = {}
            for m in r['marks']:
                if 'original_key' in m:
                    splits.setdefault(m['original_key'], []).append(m)
            if splits:
                evidence['splits'] = splits
            additions = [p['rule'] for p in patterns if p['rule'] not in body]
            if additions:
                body += '\n\n'+'\n'.join('- '+text for text in additions)
        if not body:
            raise HTTPException(422,'Escribe las instrucciones de la skill.')
        sid=db.execute('INSERT INTO skills(project,kind,version,body,parent,evidence) VALUES(?,?,?,?,?,?)',
                       (project,kind,current['version']+1,body,parent,json.dumps(evidence))).lastrowid
        return skill_summary(skill_by_id(db,sid))


@router.get('/skills/{sid}/SKILL.md')
def download(sid: int):
    with database() as db:
        s=skill_by_id(db,sid)
    name='loco-'+s['kind']
    content=f"---\nname: {name}\ndescription: Revisar {s['kind']} en micrografías con LOCO.\n---\n\n# {s['project']} · {s['kind']} · v{s['version']}\n\n{s['body']}\n"
    content += ("\nAl ejecutar esta plantilla, consulta la skill activa del proyecto de destino en "
                f"`GET /api/agent-training/{{proyecto}}/{s['kind']}/state`. Usa `active.execution_body` "
                "para leer las instrucciones con los objetivos de Configuración y envía `targets` como `expected_targets` al guardar máscaras o círculos.\n")
    evidence = json.loads(s['evidence'])
    if evidence.get('patterns'):
        content += '\n## Patrones de la ronda\n\n'
        for p in evidence['patterns']:
            group = f"{p['proposed']} → {p['decision'].replace('_', ' ')}"
            frequency = (f"{len(p['ids'])} dudosos" if p['decision'] == 'dudoso'
                         else f"{len(p['ids'])}/{p['individual']} marcas individuales de esa propuesta")
            content += f"- {group} · {frequency} · {p['partial']} parciales. Caso #{p['ids'][0]}."
            if p['comparison'] is not None:
                content += f" Contrasta con la marca aceptada #{p['comparison']}."
            content += f" Regla para comprobar en otra imagen: {p['rule']}\n"
    if evidence.get('examples'):
        content += f"\n## Ejemplos revisados\n\nFoto de biblioteca: `/api/agent-training/{evidence['project']}/{s['kind']}/photo/{evidence['image']}`. Ronda #{evidence['round']}, revisión {evidence['revision']}.\n"
        for example in evidence['examples']:
            mark = example['mark']
            geometry = str(mark['puntos']) if 'puntos' in mark else f"centro ({mark['x']}, {mark['y']}), radio {mark['radius_px']:.2f} px"
            content += f"\n- #{mark['id']} · {mark.get('clase','círculo')} · {geometry} → {example['decision']}."
        content += '\n'
    base = f"/api/agent-training/{{proyecto}}/{s['kind']}"
    content += "\n## Cómo generar la siguiente versión de esta skill\n\n"
    content += "\n".join(f"{i}. {step}" for i, step in enumerate(generation_steps(s['kind']), 1)) + "\n"
    if s['kind'] == 'cruces':
        content += f"\nLee la versión activa en `GET {base}/state`. Guarda las instrucciones revisadas con `POST {base}/skills`, enviando `expected` (active.id) y `body` (texto completo).\n"
        return Response(content, media_type='text/markdown', headers={'Content-Disposition':'attachment; filename="SKILL.md"'})
    content += f"\nDesde la API, envía a `POST {base}/skills` los campos `expected` (active.id), `body` (instrucciones completas), `round_id` y `revision` (revisión actual de la ronda).\n"
    content += f"\n## Preparar la siguiente ronda en LOCO\n\nLee la skill activa en `GET {base}/state` y guarda su `active.id`. Abre la foto de biblioteca en `GET {base}/photo/{{image_id}}`. Revisa los errores de rondas previas en `GET {base}/rounds/{{id}}`. Trabaja en las coordenadas de la foto de biblioteca.\n\n"
    if s['kind'] == 'scribbles':
        content += "Prepara polilíneas con id, clase (fibra, halo o fondo), ancho_px y puntos [x,y]. Envía image_id, skill_id, source y la lista trazos"
    else:
        content += "Guarda primero tu propuesta en `POST /api/agent/runs` con project_id, image_id y circles (x, y, radius_px). Envía image_id, skill_id y el run_id obtenido como source_run_id"
    content += f" a `POST {base}/rounds`. La ronda queda pendiente de revisión humana.\n"
    return Response(content,media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="SKILL.md"'})
