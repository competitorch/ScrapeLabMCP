import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from .debug_logger import debug_logger
except ImportError:
    from debug_logger import debug_logger

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from comprehensive_element_cloner import ComprehensiveElementCloner
from element_cloner import element_cloner

class FileBasedElementCloner:
    """Element cloner that saves data to files and returns file paths."""

    def __init__(self, output_dir: str = "element_clones"):
        self.output_dir = Path(output_dir) if Path(output_dir).is_absolute() else Path(__file__).parent / output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.comprehensive_cloner = ComprehensiveElementCloner()

    def _safe_process_framework_handlers(self, framework_handlers):
        """Safely process framework handlers that might be dict or list."""
        if isinstance(framework_handlers, dict):
            return {k: len(v) if isinstance(v, list) else str(v) for k, v in framework_handlers.items()}
        elif isinstance(framework_handlers, list):
            return {"handlers": len(framework_handlers)}
        else:
            return {"value": str(framework_handlers)}

    def _generate_filename(self, prefix: str, extension: str = "json") -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{prefix}_{timestamp}_{unique_id}.{extension}"

    def _save_to_file(self, data: Dict[str, Any], filename: str) -> str:
        file_path = self.output_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return str(file_path.absolute())

    def _save_extraction(self, data: Dict[str, Any], extraction_type: str) -> Dict[str, Any]:
        """Save already-extracted data to file, return file path + size metadata."""
        data['_metadata'] = {
            'extraction_type': extraction_type,
            'timestamp': datetime.now().isoformat(),
        }
        filename = self._generate_filename(extraction_type)
        file_path = self._save_to_file(data, filename)
        return {
            "file_path": file_path,
            "extraction_type": extraction_type,
            "file_size_kb": round(len(json.dumps(data)) / 1024, 2),
        }

    async def _extract_and_save(
        self,
        extract_coro,
        extraction_type: str,
        selector: str,
        options: dict,
        summary_fn,
    ) -> Dict[str, Any]:
        """Generic extract -> metadata -> save -> summarize wrapper.

        Args:
            extract_coro: Awaitable returning extracted data dict.
            extraction_type: Type identifier (e.g. 'structure', 'events').
            selector: CSS selector used for extraction.
            options: Options dict stored in metadata.
            summary_fn: Callable(data) -> dict of extra keys merged into result.
        """
        try:
            data = await extract_coro
            data['_metadata'] = {
                'extraction_type': extraction_type,
                'selector': selector,
                'timestamp': datetime.now().isoformat(),
                'options': options,
            }
            filename = self._generate_filename(extraction_type)
            file_path = self._save_to_file(data, filename)
            debug_logger.log_info(
                "file_element_cloner", f"extract_{extraction_type}_to_file",
                f"Saved {extraction_type} data to {file_path}"
            )
            result = {
                "file_path": file_path,
                "extraction_type": extraction_type,
                "selector": selector,
            }
            result.update(summary_fn(data))
            return result
        except Exception as e:
            debug_logger.log_error("file_element_cloner", f"extract_{extraction_type}_to_file", e)
            return {"error": str(e)}

    async def extract_element_styles_to_file(
        self, tab, selector: str,
        include_computed: bool = True, include_css_rules: bool = True,
        include_pseudo: bool = True, include_inheritance: bool = False,
    ) -> Dict[str, Any]:
        """Extract element styles and save to file, returning file path and summary."""
        return await self._extract_and_save(
            element_cloner.extract_element_styles(
                tab, selector=selector, include_computed=include_computed,
                include_css_rules=include_css_rules, include_pseudo=include_pseudo,
                include_inheritance=include_inheritance,
            ),
            "styles", selector,
            {'include_computed': include_computed, 'include_css_rules': include_css_rules,
             'include_pseudo': include_pseudo, 'include_inheritance': include_inheritance},
            lambda data: {
                "url": getattr(tab, 'url', 'unknown'),
                "components": {
                    "computed_styles_count": len(data.get('computed_styles', {})),
                    "css_rules_count": len(data.get('css_rules', [])),
                    "pseudo_elements_count": len(data.get('pseudo_elements', {})),
                    "custom_properties_count": len(data.get('custom_properties', {})),
                },
            },
        )

    async def extract_element_structure_to_file(
        self, tab, element=None, selector: str = None,
        include_children: bool = False, include_attributes: bool = True,
        include_data_attributes: bool = True, max_depth: int = 3,
    ) -> Dict[str, str]:
        """Extract structure and save to file, return file path."""
        return await self._extract_and_save(
            element_cloner.extract_element_structure(
                tab, element, selector, include_children,
                include_attributes, include_data_attributes, max_depth,
            ),
            "structure", selector,
            {'include_children': include_children, 'include_attributes': include_attributes,
             'include_data_attributes': include_data_attributes, 'max_depth': max_depth},
            lambda data: {"summary": {
                "tag_name": data.get('tag_name'),
                "attributes_count": len(data.get('attributes', {})),
                "data_attributes_count": len(data.get('data_attributes', {})),
                "children_count": len(data.get('children', [])),
                "dom_path": data.get('dom_path'),
            }},
        )

    async def extract_element_events_to_file(
        self, tab, element=None, selector: str = None,
        include_inline: bool = True, include_listeners: bool = True,
        include_framework: bool = True, analyze_handlers: bool = True,
    ) -> Dict[str, str]:
        """Extract events and save to file, return file path."""
        return await self._extract_and_save(
            element_cloner.extract_element_events(
                tab, element, selector, include_inline,
                include_listeners, include_framework, analyze_handlers,
            ),
            "events", selector,
            {'include_inline': include_inline, 'include_listeners': include_listeners,
             'include_framework': include_framework, 'analyze_handlers': analyze_handlers},
            lambda data: {"summary": {
                "inline_handlers_count": len(data.get('inline_handlers', [])),
                "event_listeners_count": len(data.get('event_listeners', [])),
                "detected_frameworks": data.get('detected_frameworks', []),
                "framework_handlers": self._safe_process_framework_handlers(data.get('framework_handlers', {})),
            }},
        )

    async def extract_element_animations_to_file(
        self, tab, element=None, selector: str = None,
        include_css_animations: bool = True, include_transitions: bool = True,
        include_transforms: bool = True, analyze_keyframes: bool = True,
    ) -> Dict[str, str]:
        """Extract animations and save to file, return file path."""
        return await self._extract_and_save(
            element_cloner.extract_element_animations(
                tab, element, selector, include_css_animations,
                include_transitions, include_transforms, analyze_keyframes,
            ),
            "animations", selector,
            {'include_css_animations': include_css_animations, 'include_transitions': include_transitions,
             'include_transforms': include_transforms, 'analyze_keyframes': analyze_keyframes},
            lambda data: {"summary": {
                "has_animations": data.get('animations', {}).get('animation_name', 'none') != 'none',
                "has_transitions": data.get('transitions', {}).get('transition_property', 'none') != 'none',
                "has_transforms": data.get('transforms', {}).get('transform', 'none') != 'none',
                "keyframes_count": len(data.get('keyframes', [])),
            }},
        )

    async def extract_element_assets_to_file(
        self, tab, element=None, selector: str = None,
        include_images: bool = True, include_backgrounds: bool = True,
        include_fonts: bool = True, fetch_external: bool = False,
    ) -> Dict[str, str]:
        """Extract assets and save to file, return file path."""
        return await self._extract_and_save(
            element_cloner.extract_element_assets(
                tab, element, selector, include_images,
                include_backgrounds, include_fonts, fetch_external,
            ),
            "assets", selector,
            {'include_images': include_images, 'include_backgrounds': include_backgrounds,
             'include_fonts': include_fonts, 'fetch_external': fetch_external},
            lambda data: {"summary": {
                "images_count": len(data.get('images', [])),
                "background_images_count": len(data.get('background_images', [])),
                "font_family": data.get('fonts', {}).get('family'),
                "custom_fonts_count": len(data.get('fonts', {}).get('custom_fonts', [])),
                "icons_count": len(data.get('icons', [])),
                "videos_count": len(data.get('videos', [])),
                "audio_count": len(data.get('audio', [])),
            }},
        )

    async def extract_related_files_to_file(
        self, tab, element=None, selector: str = None,
        analyze_css: bool = True, analyze_js: bool = True,
        follow_imports: bool = False, max_depth: int = 2,
    ) -> Dict[str, str]:
        """Extract related files and save to file, return file path."""
        return await self._extract_and_save(
            element_cloner.extract_related_files(
                tab, element, selector, analyze_css, analyze_js, follow_imports, max_depth,
            ),
            "related_files", selector,
            {'analyze_css': analyze_css, 'analyze_js': analyze_js,
             'follow_imports': follow_imports, 'max_depth': max_depth},
            lambda data: {"summary": {
                "stylesheets_count": len(data.get('stylesheets', [])),
                "scripts_count": len(data.get('scripts', [])),
                "imports_count": len(data.get('imports', [])),
                "modules_count": len(data.get('modules', [])),
            }},
        )

    async def extract_complete_element_to_file(
        self, tab, selector: str, include_children: bool = True,
    ) -> Dict[str, Any]:
        """Extract complete element using comprehensive cloner and save to file."""
        try:
            complete_data = await self.comprehensive_cloner.extract_complete_element(
                tab, selector, include_children
            )
            complete_data['_metadata'] = {
                'extraction_type': 'complete_comprehensive',
                'selector': selector,
                'timestamp': datetime.now().isoformat(),
                'include_children': include_children
            }
            filename = self._generate_filename("complete_comprehensive")
            file_path = self._save_to_file(complete_data, filename)
            debug_logger.log_info("file_element_cloner", "extract_complete_to_file",
                                  f"Saved complete element data to {file_path}")
            return {
                "file_path": file_path,
                "extraction_type": "complete_comprehensive",
                "selector": selector,
                "url": complete_data.get('url', 'unknown'),
                "summary": {
                    "tag_name": complete_data.get('html', {}).get('tagName', 'unknown'),
                    "computed_styles_count": len(complete_data.get('styles', {})),
                    "attributes_count": len(complete_data.get('html', {}).get('attributes', [])),
                    "event_listeners_count": len(complete_data.get('eventListeners', [])),
                    "children_count": len(complete_data.get('children', [])) if include_children else 0,
                    "has_pseudo_elements": bool(complete_data.get('pseudoElements')),
                    "css_rules_count": len(complete_data.get('cssRules', [])),
                    "animations_count": len(complete_data.get('animations', [])),
                    "file_size_kb": round(len(json.dumps(complete_data)) / 1024, 2)
                }
            }
        except Exception as e:
            debug_logger.log_error("file_element_cloner", "extract_complete_to_file", e)
            return {"error": str(e)}

    async def clone_element_complete_to_file(
        self, tab, element=None, selector: str = None,
        extraction_options: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Master function: extract all element data and save to file."""
        try:
            complete_data = await element_cloner.clone_element_complete(
                tab, element, selector, extraction_options
            )
            if 'error' in complete_data:
                return complete_data
            complete_data['_metadata'] = {
                'extraction_type': 'complete_clone',
                'selector': selector,
                'timestamp': datetime.now().isoformat(),
                'extraction_options': extraction_options
            }
            filename = self._generate_filename("complete_clone")
            file_path = self._save_to_file(complete_data, filename)
            summary = {
                "file_path": file_path,
                "extraction_type": "complete_clone",
                "selector": selector,
                "url": complete_data.get('url'),
                "components": {}
            }
            if 'styles' in complete_data:
                styles = complete_data['styles']
                summary['components']['styles'] = {
                    'computed_styles_count': len(styles.get('computed_styles', {})),
                    'css_rules_count': len(styles.get('css_rules', [])),
                    'pseudo_elements_count': len(styles.get('pseudo_elements', {}))
                }
            if 'structure' in complete_data:
                structure = complete_data['structure']
                summary['components']['structure'] = {
                    'tag_name': structure.get('tag_name'),
                    'attributes_count': len(structure.get('attributes', {})),
                    'children_count': len(structure.get('children', []))
                }
            if 'events' in complete_data:
                events = complete_data['events']
                summary['components']['events'] = {
                    'inline_handlers_count': len(events.get('inline_handlers', [])),
                    'detected_frameworks': events.get('detected_frameworks', [])
                }
            if 'animations' in complete_data:
                animations = complete_data['animations']
                summary['components']['animations'] = {
                    'has_animations': animations.get('animations', {}).get('animation_name', 'none') != 'none',
                    'keyframes_count': len(animations.get('keyframes', []))
                }
            if 'assets' in complete_data:
                assets = complete_data['assets']
                summary['components']['assets'] = {
                    'images_count': len(assets.get('images', [])),
                    'background_images_count': len(assets.get('background_images', []))
                }
            if 'related_files' in complete_data:
                files = complete_data['related_files']
                summary['components']['related_files'] = {
                    'stylesheets_count': len(files.get('stylesheets', [])),
                    'scripts_count': len(files.get('scripts', []))
                }
            debug_logger.log_info("file_element_cloner", "clone_complete_to_file",
                                  f"Saved complete clone data to {file_path}")
            return summary
        except Exception as e:
            debug_logger.log_error("file_element_cloner", "clone_complete_to_file", e)
            return {"error": str(e)}

    def list_clone_files(self) -> List[Dict[str, Any]]:
        """List all clone files in the output directory."""
        files = []
        for file_path in self.output_dir.glob("*.json"):
            try:
                file_info = {
                    "file_path": str(file_path.absolute()),
                    "filename": file_path.name,
                    "size": file_path.stat().st_size,
                    "created": datetime.fromtimestamp(file_path.stat().st_ctime).isoformat(),
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                }
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if '_metadata' in data:
                            file_info['metadata'] = data['_metadata']
                except:
                    pass
                files.append(file_info)
            except Exception as e:
                debug_logger.log_warning("file_element_cloner", "list_files", f"Error reading {file_path}: {e}")
        files.sort(key=lambda x: x['created'], reverse=True)
        return files

    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """Clean up clone files older than specified hours."""
        import time
        cutoff_time = time.time() - (max_age_hours * 3600)
        deleted_count = 0
        for file_path in self.output_dir.glob("*.json"):
            try:
                if file_path.stat().st_ctime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
                    debug_logger.log_info("file_element_cloner", "cleanup", f"Deleted old file: {file_path.name}")
            except Exception as e:
                debug_logger.log_warning("file_element_cloner", "cleanup", f"Error deleting {file_path}: {e}")
        return deleted_count

file_based_element_cloner = FileBasedElementCloner()
