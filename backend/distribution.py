from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import PlainTextResponse
import numpy as np
from PIL import Image

from . import agent_masks, agent_mode
from .agent_targets import AgentTargets, comparison
from .agent_worklist import image_summary
from .paths import DATA_HOME, PROJECT_ROOT
from .projects_store import list_projects

router = APIRouter(prefix='/api/agent', tags=['Modo agente'])
GUIDES = PROJECT_ROOT / '.agents' / 'skills' / 'loco-inicio'
REVIEW_GUIDE = GUIDES.parent / 'loco-revision' / 'SKILL.md'
AGENT_MODEL_PATH = DATA_HOME / 'data' / 'agent-model.txt'
DEFAULT_AGENT_MODEL = 'gpt-6.2-sol'
AGENT_MODELS = {DEFAULT_AGENT_MODEL: 'GPT-6.2 Sol', 'gpt-6.2-astra': 'GPT-6.2 Astra'}


def selected_agent_model():
    try:
        saved = AGENT_MODEL_PATH.read_text(encoding='utf8').strip()
    except FileNotFoundError:
        return DEFAULT_AGENT_MODEL
    return saved if saved in AGENT_MODELS else DEFAULT_AGENT_MODEL


@router.get('/model')
def agent_model():
    return dict(model=selected_agent_model(), default=DEFAULT_AGENT_MODEL, options=AGENT_MODELS)


@router.post('/model')
def set_agent_model(model: str = Body(embed=True)):
    if model not in AGENT_MODELS:
        raise HTTPException(422, 'Selecciona un modelo de la lista.')
    AGENT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=AGENT_MODEL_PATH.parent, delete=False) as pending:
        pending.write(model.encode('utf8'))
    path = Path(pending.name)
    try:
        path.replace(AGENT_MODEL_PATH)
    finally:
        path.unlink(missing_ok=True)
    return agent_model()


@router.get('/connection')
def connection():
    version_file = PROJECT_ROOT / 'VERSION'
    ready = all(path.is_file() for path in (GUIDES / 'SKILL.md', GUIDES / 'references/herramientas.md', REVIEW_GUIDE))
    return dict(application='LOCO Detector', version=version_file.read_text().strip() if version_file.exists() else 'desarrollo',
                protocol=1, engine='ok', skill='loco-inicio' if ready else None, ready=ready,
                active_project_id=list_projects()['active_project_id'], agent_model=selected_agent_model())


@router.get('/guide', response_class=PlainTextResponse)
def guide(tools: bool = False, review: bool = False):
    path = REVIEW_GUIDE if review else GUIDES / ('references/herramientas.md' if tools else 'SKILL.md')
    if not path.is_file():
        raise HTTPException(404, 'Skill ausente en esta instalación.')
    content = path.read_text(encoding='utf8')
    if not tools and not review:
        content += f'\nModelo configurado para los próximos subagentes: `{selected_agent_model()}`.\n'
    return content


@router.get('/worklist')
def worklist(project: str, image: str):
    try:
        return image_summary(project, image)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get('/target-review')
def target_review(project_id: str, image_id: str, mask_id: str | None = None, run_id: str | None = None):
    """Recount saved annotations for the exact artifacts submitted for review."""
    if not mask_id and not run_id:
        raise HTTPException(422, 'Indica mask_id o run_id de la propuesta.')
    report = {}
    def check_scope(record):
        if (record.get('project_id'), record['image_id']) != (project_id, image_id):
            raise HTTPException(404, 'El resultado pertenece a otra imagen o proyecto.')
        return AgentTargets(**record.get('targets', {}))

    if run_id:
        run = agent_mode.result(run_id)
        targets = check_scope(run)
        report['circles'] = dict(**comparison(len(run['circles']), targets.circle_count, targets.circle_tolerance), run_id=run_id)
        linked = run.get('scribble_mask_id')
        if linked and mask_id and linked != mask_id:
            raise HTTPException(422, 'La ejecución utilizó otra máscara de scribbles.')
        mask_id = mask_id or linked
    if mask_id:
        mask = agent_masks.get_manifest(mask_id)
        targets = check_scope(mask)
        with Image.open(agent_masks.ROOT / mask_id / 'labels.png') as raster:
            field = np.asarray(raster)[:mask['field_height']]
            painted = int(np.count_nonzero(field))
            percent = 100 * painted / field.size
        report['scribbles'] = dict(**comparison(percent, targets.painted_percent, targets.percent_tolerance),
                                  painted_pixels=painted, field_pixels=field.size, mask_id=mask_id)
    return report
