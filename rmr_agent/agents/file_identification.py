"""
file_identification_agent.py
Optimized version - Faster ML file detection
"""

import os
import re
import json
from typing import List, Dict, Any, Set
from pathlib import Path
import logging
import concurrent.futures
import nbformat

# Adjust imports based on your actual project structure
try:
    from rmr_agent.llms import LLMClient
except ImportError:
    class LLMClient:
        def call_llm(self, prompt, **kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(choices=[
                SimpleNamespace(message=SimpleNamespace(
                    content='{"ml_files": [], "confidence": 0.5, "reasoning": "Mock response"}'
                ))
            ])

logger = logging.getLogger(__name__)

class LLMFileIdentificationAgent:
    """
    Optimized version: Fast ML file identification
    """
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.all_code_files = []
        
    def identify_ml_files(self) -> Dict[str, Any]:
        """Main method: Identify ML files and sort them"""
        logger.info(f"Analyzing repository at: {self.repo_path}")
        
        # Step 1: Fast file scanning
        self._fast_find_files()
        
        if not self.all_code_files:
            return {
                'ml_files': [],
                'confidence': 0.0,
                'reasoning': "No Python or Notebook files found in repository"
            }
        
        # Step 2: Rule-based quick detection
        ml_candidates = self._fast_rule_detection()
        
        # Step 3: If there are few files and obvious ML files, return directly
        if len(ml_candidates) <= 10 and len(ml_candidates) > 0:
            logger.info(f"Fast path: Found {len(ml_candidates)} ML files by rules")
            return {
                'ml_files': ml_candidates,
                'confidence': 0.75,
                'reasoning': f"Quick detection: Found {len(ml_candidates)} ML pipeline files"
            }
        
        # Step 4: If there are too many files or rules are uncertain, use LLM
        if len(self.all_code_files) > 30:
            # Too many files, only analyze the 20 most likely ones
            files_to_analyze = ml_candidates[:20] if ml_candidates else self.all_code_files[:20]
        else:
            files_to_analyze = self.all_code_files
        
        # Step 5: Prepare minimal information for LLM
        file_info = self._prepare_minimal_info(files_to_analyze)
        
        # Step 6: LLM analysis
        return self._analyze_with_llm(file_info, files_to_analyze)
    
    def _fast_find_files(self):
        """Ultra-fast file scanning - faster using os.scandir"""
        skip_dirs = {
            '.git', '__pycache__', '.pytest_cache', 'node_modules',
            'venv', 'env', '.venv', '.tox', '.eggs', 'build', 'dist',
            '.ipynb_checkpoints', 'tests', 'test', 'docs', 'doc'
        }
        
        def scan_directory(path: Path, depth: int = 0) -> List[str]:
            if depth > 3:  # Limit depth
                return []
            
            files = []
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        name_lower = entry.name.lower()
                        
                        if entry.is_dir() and entry.name not in skip_dirs:
                            # Recursively scan subdirectories
                            if not name_lower.startswith('.'):
                                files.extend(scan_directory(Path(entry.path), depth + 1))
                        
                        elif entry.is_file():
                            # Quick check of file extensions
                            if entry.name.endswith(('.py', '.ipynb')):
                                # Quick filter of obvious non-ML files
                                if not any(skip in name_lower for skip in ['test', '__pycache__', '.pyc', '__init__']):
                                    rel_path = Path(entry.path).relative_to(self.repo_path)
                                    files.append(str(rel_path))
            except PermissionError:
                pass
            
            return files
        
        self.all_code_files = scan_directory(self.repo_path)
        logger.info(f"Fast scan found {len(self.all_code_files)} files")
    
    def _fast_rule_detection(self) -> List[str]:
        """Ultra-fast rule detection - without reading file contents"""
        scores = {}
        
        # Keyword weights
        ml_keywords = {
            # Strong signals in filenames
            'train': 100,
            'model': 90,
            'data': 80,
            'preprocess': 75,
            'feature': 70,
            'eval': 65,
            'predict': 60,
            'pipeline': 55,
            'main': 50,
            'run': 45,
        }
        
        # Exclusion keywords
        exclude_keywords = {'util', 'helper', 'config', 'setting', 'constant', 'init', 'setup', 'install'}
        
        for file_path in self.all_code_files:
            path_lower = file_path.lower()
            filename_lower = Path(file_path).name.lower()
            
            # Quick exclusion
            if any(exc in filename_lower for exc in exclude_keywords):
                continue
            
            # Calculate score
            score = 0
            
            # Check filename
            for keyword, weight in ml_keywords.items():
                if keyword in filename_lower:
                    score += weight
                elif keyword in path_lower:  # Keywords in path have half the weight
                    score += weight // 2
            
            # Files with numeric prefixes are usually pipeline components
            if re.match(r'^\d+[_\-]', Path(file_path).name):
                score += 200
            
            # Notebooks are usually main logic
            if file_path.endswith('.ipynb'):
                score += 50
            
            # Add points for files in src or source directories
            if any(d in path_lower for d in ['/src/', '/source/', '/ml/', '/model/']):
                score += 30
            
            if score > 0:
                scores[file_path] = score
        
        # Sort and return
        sorted_files = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        return [f for f, _ in sorted_files[:15]]
    
    def _prepare_minimal_info(self, files: List[str]) -> str:
        """Prepare minimal file information - only look at filenames and paths"""
        file_list = []
        for file_path in files[:30]:  # Maximum 30 files
            file_list.append({
                'path': file_path,
                'type': 'notebook' if file_path.endswith('.ipynb') else 'script',
                'name': Path(file_path).name
            })
        
        return json.dumps(file_list, indent=2)
    
    def _analyze_with_llm(self, file_info: str, available_files: List[str]) -> Dict[str, Any]:
        """Fast LLM analysis - simplified prompt"""
        
        prompt = f"""Quick task: Identify CORE ML pipeline files from this list.

Files:
{file_info}

Return ONLY files that are CORE ML pipeline (data, training, evaluation).
Skip utilities, configs, helpers.

JSON response:
{{"ml_files": ["file1", "file2"], "confidence": 0.8, "reasoning": "brief"}}"""

        try:
            llm_client = LLMClient()
            response = llm_client.call_llm(
                prompt=prompt,
                max_tokens=1024,  # Reduce tokens
                temperature=0,
                repetition_penalty=1.0,
                top_p=0.3,
            )
            
            result_text = response.choices[0].message.content or ""
            result_text = re.sub(r'```[a-z]*\n?', '', result_text.strip())
            result = json.loads(result_text)
            
            # Verify files
            valid_files = []
            for f in result.get('ml_files', []):
                # Support partial matching (LLM may only return filenames)
                for available in available_files:
                    if f in available or available.endswith(f):
                        valid_files.append(available)
                        break
            
            return {
                'ml_files': valid_files[:15],  # Maximum 15 files
                'confidence': result.get('confidence', 0.7),
                'reasoning': result.get('reasoning', 'LLM analysis complete')
            }
            
        except Exception as e:
            logger.warning(f"LLM failed, using rule-based: {e}")
            return self._simple_fallback(available_files)
    
    def _simple_fallback(self, files: List[str]) -> Dict[str, Any]:
        """Minimal fallback - based on filename patterns"""
        ml_files = []
        
        # Simple sorting rules
        def score_file(file_path: str) -> tuple:
            name = Path(file_path).name.lower()
            # Prioritize numeric prefixes
            num_match = re.match(r'^(\d+)', name)
            if num_match:
                return (0, int(num_match.group(1)), file_path)
            # Keyword priorities
            for i, keyword in enumerate(['data', 'preprocess', 'train', 'model', 'eval', 'predict', 'main']):
                if keyword in name:
                    return (1, i, file_path)
            return (2, 0, file_path)
        
        # Sort and select top 15
        sorted_files = sorted(files, key=score_file)
        ml_files = sorted_files[:15]
        
        return {
            'ml_files': ml_files,
            'confidence': 0.5,
            'reasoning': 'Rule-based detection (fallback)'
        }