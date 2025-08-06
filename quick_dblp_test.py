#!/usr/bin/env python3
"""
Quick reproduction test for the DBLP issue - simulates PDF processing context
"""

import sys
import os
import logging

# Add parent directory to path to import verifyref modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from verifier.dblp_client import DBLPClient

def test_exact_pdf_context():
    """Test DBLP with the exact same conditions as PDF processing"""
    
    print("=== Testing DBLP in PDF Processing Context ===")
    
    # Enable logging to match PDF processing
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s')
    
    # Create client
    client = DBLPClient()
    
    # Exact data from your log - reference 38
    title = "Programming the demirci-selçuk meet-in-the-middle attack with constraints"
    authors = ["D Shi", "S Sun", "P Derbez"]  # First 3 authors as shown in log
    year = 2018
    venue = None  # PDF processing might not extract venue properly
    
    print(f"Title: {title}")
    print(f"Authors: {authors}")  
    print(f"Year: {year}")
    print(f"Venue: {venue}")
    print()
    
    print("Calling client.search_paper() with PDF processing parameters...")
    
    try:
        # Call exactly like PDF processing would
        results = client.search_paper(
            title=title,
            authors=authors,
            year=year,
            venue=venue  # This might be None in PDF processing
        )
        
        print(f"Results: {len(results)} papers found")
        
        if results:
            print("✅ DBLP found results:")
            for i, result in enumerate(results, 1):
                print(f"  {i}. {result.get('title', 'No title')}")
                print(f"     Authors: {result.get('authors', [])}")
                print(f"     Venue: {result.get('venue', 'Unknown')}")
        else:
            print("❌ DBLP found 0 results (reproducing the bug!)")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_dblp_query_variations():
    """Test different query variations to identify the issue"""
    
    print("\n=== Testing DBLP Query Variations ===")
    
    client = DBLPClient()
    
    # Test different parameter combinations
    test_cases = [
        {
            "name": "Full parameters (our working test)",
            "title": "Programming the Demirci-Selçuk Meet-in-the-Middle Attack with Constraints",
            "authors": ["Danping Shi", "Siwei Sun", "Patrick Derbez", "Yosuke Todo", "Bing Sun", "Lei Hu"],
            "year": 2018,
            "venue": "ASIACRYPT"
        },
        {
            "name": "PDF-style parameters (shortened authors)",
            "title": "Programming the demirci-selçuk meet-in-the-middle attack with constraints",
            "authors": ["D Shi", "S Sun", "P Derbez"],
            "year": 2018,
            "venue": None
        },
        {
            "name": "Case-sensitive test",
            "title": "programming the demirci-selçuk meet-in-the-middle attack with constraints",
            "authors": ["d shi", "s sun", "p derbez"],
            "year": 2018,
            "venue": None
        },
        {
            "name": "Title only",
            "title": "Programming the demirci-selçuk meet-in-the-middle attack with constraints",
            "authors": None,
            "year": None,
            "venue": None
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- {test_case['name']} ---")
        try:
            results = client.search_paper(
                title=test_case['title'],
                authors=test_case['authors'],
                year=test_case['year'],
                venue=test_case['venue']
            )
            print(f"Results: {len(results)} papers")
            if len(results) == 0:
                print("⚠️  This query fails (0 results)")
            else:
                print("✅ This query works")
        except Exception as e:
            print(f"❌ Error: {e}")

def test_rate_limiting_scenario():
    """Test if rate limiting causes the issue"""
    
    print("\n=== Testing Rate Limiting Scenario ===")
    
    client = DBLPClient()
    
    # Simulate multiple requests like PDF processing would do
    test_queries = [
        "machine learning",
        "deep learning",
        "neural networks", 
        "artificial intelligence",
        "computer vision"
    ]
    
    print("Making multiple DBLP requests to simulate PDF processing...")
    
    for i, query in enumerate(test_queries, 1):
        print(f"Request {i}: {query}")
        try:
            results = client.search_paper(title=query)
            print(f"  → {len(results)} results")
        except Exception as e:
            print(f"  → Error: {e}")
        
        # Small delay like real processing
        import time
        time.sleep(0.5)
    
    # Now test our target paper
    print("\nTesting target paper after multiple requests...")
    try:
        results = client.search_paper(
            title="Programming the demirci-selçuk meet-in-the-middle attack with constraints",
            authors=["D Shi", "S Sun", "P Derbez"],
            year=2018
        )
        print(f"Target paper results: {len(results)}")
        if len(results) == 0:
            print("🚨 REPRODUCED THE BUG! Rate limiting caused 0 results")
        else:
            print("✅ Still working after multiple requests")
    except Exception as e:
        print(f"❌ Error on target paper: {e}")

if __name__ == "__main__":
    test_exact_pdf_context()
    test_dblp_query_variations()
    test_rate_limiting_scenario()
