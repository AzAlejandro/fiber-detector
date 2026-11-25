import React, { useState } from 'react'

/**
 * Navigation component: collapsible sidebar (level 1) + exported GROUPS for tab strip.
 *
 * Props:
 *   activeGroup: 'project' | 'scribble' | 'loco' | 'detection' | 'analysis' | 'configuration' | 'tutorial'
 *   activeTab: string
 *   onGroupChange: (group) => void
 *   onTabChange: (tab) => void
 *   forceExpanded?: boolean
 */

const GROUPS = [
  {
    key: 'project',
    label: 'Proyecto',
    fullLabel: 'Gestion de proyectos y tags',
    icon: 'folder_open',
    section: 'project',
    tabs: [
      { key: 'projectSelect', label: 'Seleccion proyecto' },
      { key: 'projectImages', label: 'Imagenes y tags' },
      { key: 'projectTags', label: 'Manejo de tags' },
    ],
  },
  {
    key: 'scribble',
    label: 'Scribble',
    fullLabel: 'Grupo 1: Entrenamiento Scribble',
    icon: 'edit_note',
    section: 'training',
    tabs: [
      { key: 'workbench', label: 'Scribbles y Experimentos' },
      { key: 'review', label: 'Revision de Resultados' },
      { key: 'models', label: 'Modelos de Asistencia' },
      { key: 'scribbleModelManager', label: 'Gestion de Modelos' },
    ],
  },
  {
    key: 'loco',
    label: 'LOCO',
    fullLabel: 'Grupo 2: Entrenamiento LOCO',
    icon: 'adjust',
    section: 'training',
    tabs: [
      { key: 'locoDataset', label: 'Generar Dataset' },
      { key: 'locoAugment', label: 'Aumentacion' },
      { key: 'locoTraining', label: 'Entrenamiento' },
      { key: 'locoTest', label: 'Test de Modelo' },
      { key: 'locoModelManager', label: 'Gestion de Modelos' },
    ],
  },
  {
    key: 'agentTraining', label: 'Agente', fullLabel: 'Entrenamiento del agente',
    icon: 'psychology', section: 'training',
    tabs: [
      { key: 'trainStrokes', label: 'Scribbles' },
      { key: 'trainCircles', label: 'Círculos' },
      { key: 'trainSkills', label: 'Biblioteca de skills' },
    ],
  },
  {
    key: 'detection',
    label: 'Deteccion',
    fullLabel: 'Grupo 3: Deteccion y Medicion',
    icon: 'straighten',
    section: 'production',
    tabs: [
      { key: 'locoModel', label: 'Detector LOCO' },
      { key: 'diameter', label: 'Medicion de Diametros' },
    ],
  },
  {
    key: 'agent',
    label: 'Modo agente',
    fullLabel: 'Modo agente · Detección de fibras y bordes',
    icon: 'smart_toy',
    section: 'production',
    tabs: [{ key: 'agentMask', label: 'Obtención de máscara' }, { key: 'agentMode', label: 'Detección de fibras y bordes' },
      { key: 'agentDiameter', label: 'Medición de diámetros' }],
  },
  {
    key: 'analysis',
    label: 'Analisis',
    fullLabel: 'Grupo 4: Analisis de diametros',
    icon: 'bar_chart',
    section: 'production',
    tabs: [
      { key: 'diameterAnalysisSelect', label: 'Seleccion de imagenes' },
      { key: 'diameterAnalysisHistogram', label: 'Histograma' },
    ],
  },
  {
    key: 'configuration',
    label: 'Configuracion',
    fullLabel: 'Configuracion del proyecto',
    icon: 'settings',
    section: 'other',
    tabs: [
      { key: 'projectTransfer', label: 'Exportar e importar' },
    ],
  },
  {
    key: 'tutorial',
    label: 'Tutorial',
    fullLabel: 'Tutoriales guiados del proyecto',
    icon: 'menu_book',
    section: 'other',
    tabs: [
      { key: 'tutorialOverview', label: 'General' },
      { key: 'tutorialScribble', label: 'Ruta Scribble' },
      { key: 'tutorialLoco', label: 'Ruta LOCO' },
      { key: 'tutorialDetection', label: 'Ruta Produccion / Deteccion' },
    ],
  },
]

function MaterialIcon({ name, className = '' }) {
  return (
    <span aria-hidden="true" className={`material-symbols-outlined ${className}`}>
      {name}
    </span>
  )
}

export function legacyToGroup(tab) {
  const mapping = {
    projectSelect: { group: 'project', tab: 'projectSelect' },
    projectImages: { group: 'project', tab: 'projectImages' },
    projectTags: { group: 'project', tab: 'projectTags' },
    workbench: { group: 'scribble', tab: 'workbench' },
    review: { group: 'scribble', tab: 'review' },
    models: { group: 'scribble', tab: 'models' },
    scribbleModelManager: { group: 'scribble', tab: 'scribbleModelManager' },
    locoDataset: { group: 'loco', tab: 'locoDataset' },
    locoAugment: { group: 'loco', tab: 'locoAugment' },
    locoTraining: { group: 'loco', tab: 'locoTraining' },
    locoTest: { group: 'loco', tab: 'locoTest' },
    locoModelManager: { group: 'loco', tab: 'locoModelManager' },
    locoModel: { group: 'detection', tab: 'locoModel' },
    diameter: { group: 'detection', tab: 'diameter' },
    agentMode: { group: 'agent', tab: 'agentMode' },
    agentEdges: { group: 'agent', tab: 'agentMode' },
    trainStrokes: { group: 'agentTraining', tab: 'trainStrokes' },
    trainCircles: { group: 'agentTraining', tab: 'trainCircles' },
    trainSkills: { group: 'agentTraining', tab: 'trainSkills' },
    diameterAnalysis: { group: 'analysis', tab: 'diameterAnalysisSelect' },
    diameterAnalysisSelect: { group: 'analysis', tab: 'diameterAnalysisSelect' },
    diameterAnalysisHistogram: { group: 'analysis', tab: 'diameterAnalysisHistogram' },
    projectTransfer: { group: 'configuration', tab: 'projectTransfer' },
    tutorialHub: { group: 'tutorial', tab: 'tutorialOverview' },
    loco: { group: 'detection', tab: 'locoModel' },
  }
  return mapping[tab] || { group: 'scribble', tab: 'workbench' }
}

export function groupToLegacy(group, tab) {
  const mapping = {
    'project:projectSelect': 'projectSelect',
    'project:projectImages': 'projectImages',
    'project:projectTags': 'projectTags',
    'scribble:workbench': 'workbench',
    'scribble:review': 'review',
    'scribble:models': 'models',
    'scribble:scribbleModelManager': 'scribbleModelManager',
    'loco:locoDataset': 'locoDataset',
    'loco:locoAugment': 'locoAugment',
    'loco:locoTraining': 'locoTraining',
    'loco:locoTest': 'locoTest',
    'loco:locoModelManager': 'locoModelManager',
    'detection:locoModel': 'locoModel',
    'detection:diameter': 'diameter',
    'agent:agentMode': 'agentMode',
    'agent:agentMask': 'workbench',
    'agent:agentEdges': 'agentMode',
    'agent:agentDiameter': 'diameter',
    'agentTraining:trainStrokes': 'trainStrokes',
    'agentTraining:trainCircles': 'trainCircles',
    'agentTraining:trainSkills': 'trainSkills',
    'detection:diameterAnalysis': 'diameterAnalysisSelect',
    'analysis:diameterAnalysisSelect': 'diameterAnalysisSelect',
    'analysis:diameterAnalysisHistogram': 'diameterAnalysisHistogram',
    'configuration:projectTransfer': 'projectTransfer',
    'tutorial:tutorialOverview': 'tutorialHub',
    'tutorial:tutorialScribble': 'tutorialHub',
    'tutorial:tutorialLoco': 'tutorialHub',
    'tutorial:tutorialDetection': 'tutorialHub',
  }
  return mapping[`${group}:${tab}`] || 'workbench'
}

export { GROUPS }

const AGENT_GROUPS = new Set(['project', 'agentTraining', 'agent', 'analysis', 'configuration'])
export function isAgentGroup(key) { return AGENT_GROUPS.has(key) }

const sections = [
  ['project', 'Proyecto', 'folder_open'],
  ['training', 'Entrenamiento', 'model_training'],
  ['production', 'Produccion', 'precision_manufacturing'],
  ['other', 'Otros', 'more_horiz'],
]

export default function Navigation({ activeGroup, onGroupChange, forceExpanded = false, agentOnly = false }) {
  const [collapsed, setCollapsed] = useState(true)
  const isCollapsed = forceExpanded ? false : collapsed

  function groupButton(group) {
    return (
      <button key={group.key} className={`sidebar-group-btn ${activeGroup === group.key ? 'active' : ''}`}
        onClick={() => onGroupChange(group.key)} title={isCollapsed ? group.fullLabel : group.label}
        aria-label={group.label} data-tour={`sidebar-group-${group.key}`}>
        <MaterialIcon className="sidebar-icon" name={group.icon} />
        {!isCollapsed && <span className="sidebar-label">{group.label}</span>}
      </button>
    )
  }

  return (
    <aside className={`sidebar ${isCollapsed ? 'collapsed' : 'expanded'}`}
      onMouseEnter={() => setCollapsed(false)} onMouseLeave={() => { if (!forceExpanded) setCollapsed(true) }}>
      <button className="sidebar-toggle" onClick={() => { if (!forceExpanded) setCollapsed(current => !current) }}
        title={isCollapsed ? 'Expandir menu' : 'Colapsar menu'}>
        <MaterialIcon className="sidebar-toggle-icon" name={isCollapsed ? 'menu' : 'close'} />
        {!isCollapsed && <span className="sidebar-toggle-label">Menu</span>}
      </button>
      {agentOnly ? GROUPS.filter(group => isAgentGroup(group.key)).map(groupButton)
        : sections.map(([section, label, icon], i) => (
          <React.Fragment key={section}>
            {i > 0 && <div className="sidebar-separator" />}
            <div className="sidebar-section-label">
              {isCollapsed ? <MaterialIcon className="sidebar-section-icon" name={icon} /> : label}
            </div>
            {GROUPS.filter(group => group.section === section).map(groupButton)}
          </React.Fragment>
        ))}
    </aside>
  )
}
