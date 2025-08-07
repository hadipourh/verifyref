"""
VerifyRef - High-performance academic reference verification tool
Copyright (C) 2025 Hosein Hadipour <hsn.hadipour@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Output handling utilities for saving results in different formats
"""

import json
import logging
from typing import Dict, Any
from .report_generator import generate_human_readable_report

logger = logging.getLogger(__name__)

def make_json_serializable(data):
    """Recursively convert data to JSON-serializable format"""
    if isinstance(data, dict):
        return {k: make_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [make_json_serializable(item) for item in data]
    elif hasattr(data, '__dict__'):
        return make_json_serializable(data.__dict__)
    elif isinstance(data, (int, float, str, bool, type(None))):
        return data
    else:
        return str(data)

def determine_output_format(output_file: str, output_format: str = None) -> str:
    """Determine output format from file extension or explicit format"""
    if output_format:
        return output_format.lower()
    
    if output_file:
        if output_file.lower().endswith('.json'):
            return 'json'
        elif output_file.lower().endswith('.txt'):
            return 'txt'
    
    # Default to JSON
    return 'json'

def save_results(results: Dict[str, Any], output_file: str, output_format: str, classifier=None, console=None):
    """Save results in the specified format"""
    try:
        if output_format == 'json':
            # Convert to JSON-serializable format
            json_safe_results = make_json_serializable(results)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(json_safe_results, f, indent=2, ensure_ascii=False)
        
        elif output_format == 'txt':
            # Generate human-readable report
            report = generate_human_readable_report(results, classifier)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
        
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
        
        if console:
            console.print(f"[green]📊 Results saved to: {output_file} ({output_format.upper()} format)[/green]")
        
    except Exception as e:
        if console:
            console.print(f"[red]❌ Error saving results: {e}[/red]")
        logger.error(f"Error saving results: {e}")
        raise
