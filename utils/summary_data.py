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
"""

from typing import Dict, List, Any

def get_verification_summary_data(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract verification summary data for both terminal and file output"""
    counts = summary.get('classification_counts', {})
    percentages = summary.get('percentages', {})
    
    summary_data = [
        {
            'label': '[+] AUTHENTIC',
            'count': counts.get('authentic', 0),
            'percentage': percentages.get('authentic', 0),
            'color': 'green'
        },
        {
            'label': '[?] SUSPICIOUS',
            'count': counts.get('suspicious', 0),
            'percentage': percentages.get('suspicious', 0),
            'color': 'yellow'
        },
        {
            'label': '[X] FAKE',
            'count': counts.get('fake', 0),
            'percentage': percentages.get('fake', 0),
            'color': 'red'
        },
        {
            'label': '[~] AUTHOR MANIPULATION',
            'count': counts.get('author_manipulation', 0),
            'percentage': percentages.get('author_manipulation', 0),
            'color': 'purple'
        },
        {
            'label': '[-] FABRICATED',
            'count': counts.get('fabricated', 0),
            'percentage': percentages.get('fabricated', 0),
            'color': 'red'
        },
        {
            'label': '[!] INCONCLUSIVE',
            'count': counts.get('inconclusive', 0),
            'percentage': percentages.get('inconclusive', 0),
            'color': 'blue'
        }
    ]
    
    return summary_data
