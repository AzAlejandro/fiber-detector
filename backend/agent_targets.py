"""Per-image goals configured by a project and captured with each proposal."""
from math import isclose

from pydantic import BaseModel, Field
from fastapi import HTTPException

from .projects_store import list_projects


class AgentTargets(BaseModel):
    painted_percent: float | None = Field(None, gt=0, le=100, allow_inf_nan=False)
    percent_tolerance: float = Field(1, ge=0, le=100, allow_inf_nan=False)
    circle_count: int | None = Field(None, ge=1, le=200)
    circle_tolerance: int = Field(2, ge=0, le=200)

    def instruction(self, kind, body):
        values = {'porcentaje_pintado': self.painted_percent, 'cantidad_circulos': self.circle_count,
                  'tolerancia_puntos': self.percent_tolerance, 'tolerancia_circulos': self.circle_tolerance}
        for key, val in values.items():
            body = body.replace('{{'+key+'}}', 'sin objetivo' if val is None else f'{val:g}')
        if kind == 'scribbles' and self.painted_percent is not None:
            return body + (f'\n\nObjetivo por imagen: pinta {self.painted_percent:g} % del campo útil '
                           f'con fibra, halo y fondo. Margen: ±{self.percent_tolerance:g} puntos porcentuales.')
        if kind == 'circulos' and self.circle_count is not None:
            return body + (f'\n\nObjetivo por imagen: propone {self.circle_count} círculos válidos en tramos '
                           f'distintos. Margen: ±{self.circle_tolerance} círculos.')
        return body


def project_targets(project_id, expected=None):
    project = next((p for p in list_projects()['projects'] if p['project_id'] == project_id), {})
    current = AgentTargets(**(project.get('agent_targets') or {}))
    if expected is not None and expected != current:
        raise HTTPException(409, 'Los objetivos del proyecto cambiaron. Relee la skill antes de guardar.')
    return current


def comparison(actual, target, tolerance):
    difference = actual - target if target is not None else None
    within = None if difference is None else abs(difference) < tolerance or isclose(abs(difference), tolerance, abs_tol=1e-10)
    return dict(actual=actual, target=target, tolerance=tolerance, difference=difference, within=within)
