# Changelog

All notable changes to LOCO Detector will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.2] â€” 2026-11-25

### VersiÃ³n de prueba de escritorio

- Modo Agente con skills por proyecto para scribbles, cÃ­rculos y cruces. La configuraciÃ³n de cobertura y cÃ­rculos se aplica a las siguientes propuestas y queda registrada para su revisiÃ³n.
- ConfiguraciÃ³n por pestaÃ±as, zoom de la interfaz y anÃ¡lisis de diÃ¡metros con calibraciÃ³n por imagen.
- Instalador de escritorio y conexiÃ³n MCP local. Los datos del proyecto se guardan aparte del programa para conservarlos durante las actualizaciones.

## [1.0.0] â€” 2026-05-19

### Added
- Initial release of LOCO Detector as a standalone program
- Scribble-based interactive segmentation with real-time feedback
- LOCO Circle Detection pipeline with ML models (Random Forest, ExtraTrees, XGBoost, CatBoost, LightGBM)
- Diameter measurement with 3 methodology versions (v1, v2, v3)
- Hierarchical 3-group UI navigation with backward compatibility
- Scale calibration system (px â†’ nm/Î¼m) with persistent JSON storage
- Statistical distribution histogram with mean, median, std, min, max, and CSV export
- Pipeline connection: LOCO Detector accepted circles â†’ Diameter Research points
- Validation system for manual review of detected circles
- LOCO Lab experimental pipeline (proposals â†’ filter â†’ measure â†’ evaluate)
- Dataset management: build, augment, and manage training datasets
- Training system with binary + multiclass classification
- Circle-NMS and spatial final filter for overlap removal
- Comprehensive test suite (50+ tests)
- Security documentation and localhost-only binding

### Changed
- Migrated from Scribble Research library context to standalone LOCO Detector program
- Reorganized flat 9-tab navigation into 3 hierarchical groups
- Archived obsolete documentation to `archived/` directory

### Fixed
- Various spatial overlap issues in circle detection
- Pipeline connection between LOCO Detector and Diameter Research modules
