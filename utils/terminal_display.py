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

Terminal display utilities for Rich-based output
"""

import logging
from typing import Dict, Any
from rich.table import Table
from rich import box
from .summary_data import get_verification_summary_data

logger = logging.getLogger(__name__)

def display_verification_summary(summary: Dict[str, Any], total_refs: int, console):
    """Display a beautiful summary table of verification results in terminal"""
    
    table = Table(title="[*] Verification Summary", box=box.ROUNDED)
    table.add_column("Classification", style="bold", min_width=24)
    table.add_column("Count", justify="right", min_width=5)
    table.add_column("Percentage", justify="right", min_width=10)
    table.add_column("Status", justify="center", min_width=6)
    
    # Get shared summary data
    summary_data = get_verification_summary_data(summary)
    
    # Add rows with colors and monochrome hacker-style symbols
    for item in summary_data:
        color = item['color']
        count = item['count']
        percentage = item['percentage']
        label = item['label']
        
        table.add_row(
            f"[{color}]{label}[/{color}]", 
            str(count), 
            f"{percentage:6.1f}%",
            f"[{color}]●[/{color}]" if count > 0 else "[dim]○[/dim]"
        )
    
    console.print()
    console.print(table)
    
    # Overall assessment from classifier
    risk_assessment = summary.get('risk_assessment', '🔍 Inconclusive - More investigation needed')
    console.print(f"\n{risk_assessment}")
    console.print()
