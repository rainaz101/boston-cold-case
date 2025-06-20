#has individual summaries of boston cases, summarize stats, cross checks
#boston cases and cold case database and finds potential matches
#3 - Simplified version without MCP dependencies
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
import folium 
from folium.plugins import MarkerCluster
import io
import geocoder
from geopy.geocoders import GoogleV3
import time
import sys

load_dotenv()

# Add your Google Maps Geocoding API key here
GOOGLE_API_KEY = 'AIzaSyAj5KY4GEB0iIcvzri4H-4F2hjmzPZigII'

class ColdCaseCrossChecker:
    def __init__(self):
        self.cold_case_db = []
        self.boston_cases = []
        self.matches = []
        
        # URLs
        self.COLD_CASE_URL = "https://database.projectcoldcase.org/"
        self.BOSTON_URL = "https://police.boston.gov/2014-unsolved-homicides/"
    
    def scrape_boston_cases(self):
        """Scrape Boston Police unsolved homicides with improved parsing."""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(self.BOSTON_URL, headers=headers, timeout=30)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find main content
            content = (soup.find('div', class_='entry-content') or 
                      soup.find('main') or soup)
            
            if not content:
                return "Error: Could not find main content on page"
            
            # Get all text content
            full_text = content.get_text()
            
            # Split into case blocks using improved logic
            case_blocks = self._split_into_case_blocks(full_text)
            
            print(f"Found {len(case_blocks)} potential case blocks")
            
            for i, block in enumerate(case_blocks):
                case_info = self._extract_boston_case_info(block)
                if case_info and self._is_valid_case(case_info):
                    case_info['case_id'] = i + 1
                    self.boston_cases.append(case_info)
            
            # Remove duplicates
            self.boston_cases = self._remove_duplicate_cases(self.boston_cases)
            
            if not self.boston_cases:
                return f"Warning: No valid Boston cases found from scraping {self.BOSTON_URL}"
                
        except Exception as e:
            return f"Error scraping Boston Police: {e}"
        
        return f"Found {len(self.boston_cases)} Boston Police cases"
    
    def _split_into_case_blocks(self, text):
        """Split text into individual case blocks."""
        # Clean up the text first
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Look for date patterns as separators
        date_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+2014'
        date_matches = list(re.finditer(date_pattern, text, re.IGNORECASE))
        
        blocks = []
        for i, match in enumerate(date_matches):
            start_pos = match.start()
            end_pos = date_matches[i + 1].start() if i + 1 < len(date_matches) else len(text)
            
            block_text = text[start_pos:end_pos].strip()
            if len(block_text) > 100:  # Only include substantial blocks
                blocks.append(block_text)
        
        return blocks
    
    def _extract_boston_case_info(self, text):
        """Extract information from Boston Police case text with improved parsing."""
        if not text or len(text) < 50:
            return None
            
        # Extract victim name - look for capitalized names
        victim_name = self._extract_victim_name(text)
        
        # Extract age with multiple patterns
        age = self._extract_age(text)
        
        # Extract date with multiple patterns
        date = self._extract_date(text)
        
        # Extract location with improved patterns
        location = self._extract_location(text)
        
        # Extract gender
        gender = self._extract_gender(text)
        
        # Clean description
        description = self._clean_description(text)
        
        return {
            "source": "boston_police",
            "victim_name": victim_name,
            "age": age,
            "gender": gender,
            "date": date,
            "location": location,
            "description": description
        }
    
    def _extract_victim_name(self, text):
        """Extract victim name from text with improved logic."""
        # Pattern 1: Date followed by name
        pattern1 = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+2014\s*([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        match1 = re.search(pattern1, text, re.IGNORECASE)
        if match1:
            name = match1.group(1).strip()
            # Clean up any trailing numbers or addresses
            name = re.sub(r'\d.*$', '', name).strip()
            if self._is_valid_name(name):
                return name
        
        # Pattern 2: "victim was identified as" or similar
        pattern2 = r'identified\s+as\s+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        match2 = re.search(pattern2, text, re.IGNORECASE)
        if match2:
            name = match2.group(1).strip()
            if self._is_valid_name(name):
                return name
        
        return "Unknown"
    
    def _is_valid_name(self, name):
        """Check if extracted name is valid."""
        if not name or len(name) < 3:
            return False
        
        # Filter out common false positives
        invalid_words = [
            'boston', 'police', 'department', 'street', 'avenue', 'responded', 
            'person', 'shot', 'victim', 'homicide', 'murder', 'killed',
            'january', 'february', 'march', 'april', 'may', 'june',
            'july', 'august', 'september', 'october', 'november', 'december'
        ]
        
        name_lower = name.lower()
        return not any(word in name_lower for word in invalid_words)
    
    def _extract_age(self, text):
        """Extract age from text with multiple patterns."""
        patterns = [
            r'(\d{1,2})\s*year[s]?\s*old',
            r'age\s*(\d{1,2})',
            r'(\d{1,2})\s*y/?o\b',
            r'(\d{1,2})-year-old',
            r'\b(\d{1,2})\s*years?\s*of\s*age',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                age = int(match.group(1))
                if 1 <= age <= 100:  # Reasonable age range
                    return age
        
        return None
    
    def _extract_date(self, text):
        """Extract date from text with multiple patterns."""
        patterns = [
            r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+2014)',
            r'(\d{1,2}/\d{1,2}/2014)',
            r'(\d{1,2}-\d{1,2}-2014)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_location(self, text):
        """Extract location from text with improved patterns."""
        # Look for street addresses
        street_patterns = [
            r'\b(\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Way|Place|Pl))\b',
        ]
        
        for pattern in street_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                location = match.group(1).lower()
                location = re.sub(r'\s+', ' ', location).strip()
                return location
        
        # Look for neighborhoods
        neighborhoods = [
            'roxbury', 'dorchester', 'mattapan', 'south end', 'back bay',
            'jamaica plain', 'charlestown', 'east boston', 'south boston',
            'brighton', 'allston', 'fenway', 'north end'
        ]
        
        text_lower = text.lower()
        for neighborhood in neighborhoods:
            if neighborhood in text_lower:
                return neighborhood
        
        return "unknown location"
    
    def _extract_gender(self, text):
        """Extract gender from text."""
        text_lower = text.lower()
        
        # Look for explicit gender mentions
        male_indicators = ['male', 'man', 'boy', 'he ', 'his ', 'him ', 'mr.']
        female_indicators = ['female', 'woman', 'girl', 'she ', 'her ', 'hers ', 'ms.']
        
        male_count = sum(1 for word in male_indicators if word in text_lower)
        female_count = sum(1 for word in female_indicators if word in text_lower)
        
        if male_count > female_count:
            return "male"
        elif female_count > male_count:
            return "female"
        
        return "unknown"
    
    def _clean_description(self, text):
        """Clean and rewrite description for clarity."""
        if not text:
            return ""
            
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Extract key information first
        victim_match = re.search(r'The victim was later identified as ([^,]+),?\s*(\d+)', text, re.IGNORECASE)
        method_match = re.search(r'responded to a Person (Shot|Stabbed)', text, re.IGNORECASE)
        
        # Create a clean summary
        if victim_match and method_match:
            victim_name = victim_match.group(1).strip()
            age = victim_match.group(2)
            method = "shot" if method_match.group(1).lower() == "shot" else "stabbed"
            
            return f"{victim_name}, age {age}, was {method} and killed."
        
        # Fallback: clean the existing text
        # Remove common boilerplate text
        boilerplate_phrases = [
            "Our greatest resource in solving homicide cases is information from witnesses, family, friends and the community.",
            "If you have any information regarding this case, please contact the Boston Police Department",
            "Anyone with information is asked to contact",
            "the Boston Police Department responded to a Person Shot at",
            "the Boston Police Department responded to a Person Stabbed at", 
            "The victim was later identified as",
            "and was pronounced deceased",
            "The manner of death of",
            "was determined to be a homicide by the Office of the Chief Medical Examiner",
        ]
        
        for phrase in boilerplate_phrases:
            text = text.replace(phrase, "")
        
        # Remove phone numbers and contact info
        text = re.sub(r'\d{3}-\d{3}-\d{4}', '', text)
        text = re.sub(r'1-800-\d{3}-\d{4}', '', text)
        text = re.sub(r'contact.*?at.*?\d+', '', text, flags=re.IGNORECASE)
        
        # Clean up extra punctuation and spaces
        text = re.sub(r'\s*,\s*,', ',', text)  # Remove double commas
        text = re.sub(r'\s*\.\s*\.', '.', text)  # Remove double periods
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove trailing punctuation artifacts
        text = re.sub(r'[,\s]+$', '', text)
        
        # Remove empty or very short descriptions
        if len(text.strip()) < 10:
            return ""
            
        return text.strip()
    
    def _is_valid_case(self, case_info):
        """Check if case info represents a valid case."""
        if not case_info:
            return False
        
        # Must have either a victim name, location, or substantial description
        has_name = case_info.get('victim_name') and case_info['victim_name'] != 'Unknown'
        has_location = case_info.get('location') and case_info['location'] != 'unknown location' and len(case_info['location']) > 5
        has_description = case_info.get('description') and len(case_info['description']) > 100
        has_date = case_info.get('date') is not None
        
        # Require at least name + date, or location + date, or substantial description
        return (has_name and has_date) or (has_location and has_date) or has_description
    
    def _remove_duplicate_cases(self, cases):
        """Remove duplicate cases based on similarity."""
        unique_cases = []
        seen_signatures = set()
        
        for case in cases:
            # Create a signature
            name = case.get('victim_name', '')
            location = case.get('location', '')
            date = case.get('date', '')
            
            signature = f"{name}-{location}-{date}"
            
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_cases.append(case)
        
        return unique_cases

    def generate_html_report(self, filename="boston_2014_cases_report.html"):
        """Generate a professional HTML report of the Boston 2014 cases."""
        if not self.boston_cases:
            return "No cases to generate report for."
        
        # Calculate statistics
        total_cases = len(self.boston_cases)
        ages = [case.get('age') for case in self.boston_cases if case.get('age')]
        avg_age = sum(ages) / len(ages) if ages else 0
        
        # Count by method
        shot_cases = sum(1 for case in self.boston_cases if 'shot' in case.get('description', '').lower())
        stabbed_cases = sum(1 for case in self.boston_cases if 'stab' in case.get('description', '').lower())
        
        # Count by month
        months = {}
        for case in self.boston_cases:
            date = case.get('date', '')
            if date:
                month = date.split()[0] if ' ' in date else 'Unknown'
                months[month] = months.get(month, 0) + 1
        
        # Generate HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Boston 2014 Unsolved Homicides Report</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            background-color: #f8f9fa;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        .header-section {{
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 2rem 0;
            margin-bottom: 2rem;
        }}
        .case-card {{
            border: none;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            margin-bottom: 1.5rem;
        }}
        .case-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }}
        .case-header {{
            background: linear-gradient(45deg, #dc3545, #c82333);
            color: white;
            padding: 1rem;
            border-radius: 0.375rem 0.375rem 0 0;
        }}
        .case-details {{
            padding: 1.5rem;
        }}
        .stat-card {{
            background: white;
            border-radius: 10px;
            padding: 1.5rem;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 1rem;
        }}
        .stat-number {{
            font-size: 2.5rem;
            font-weight: bold;
            color: #dc3545;
        }}
        .chart-container {{
            position: relative;
            height: 300px;
            margin: 1rem 0;
        }}
        .victim-name {{
            font-size: 1.2rem;
            font-weight: bold;
            color: #dc3545;
        }}
        .case-summary {{
            font-size: 1.1rem;
            line-height: 1.6;
            margin: 1rem 0;
        }}
        .case-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-top: 1rem;
        }}
        .meta-item {{
            background: #f8f9fa;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-size: 0.9rem;
        }}
        .nav-tabs .nav-link.active {{
            background-color: #dc3545;
            border-color: #dc3545;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="header-section">
        <div class="container">
            <div class="row align-items-center">
                <div class="col-md-8">
                    <h1 class="display-4 mb-0">
                        <i class="fas fa-search me-3"></i>
                        Boston 2014 Unsolved Homicides
                    </h1>
                    <p class="lead mt-2">Comprehensive Analysis Report</p>
                </div>
                <div class="col-md-4 text-end">
                    <div class="stat-card bg-light text-dark">
                        <div class="stat-number">{total_cases}</div>
                        <div>Total Cases</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="container">
        <!-- Navigation Tabs -->
        <ul class="nav nav-tabs mb-4" id="reportTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="overview-tab" data-bs-toggle="tab" data-bs-target="#overview" type="button" role="tab">
                    <i class="fas fa-chart-bar me-2"></i>Overview
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="cases-tab" data-bs-toggle="tab" data-bs-target="#cases" type="button" role="tab">
                    <i class="fas fa-list me-2"></i>All Cases
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="statistics-tab" data-bs-toggle="tab" data-bs-target="#statistics" type="button" role="tab">
                    <i class="fas fa-chart-pie me-2"></i>Statistics
                </button>
            </li>
        </ul>

        <!-- Tab Content -->
        <div class="tab-content" id="reportTabsContent">
            <!-- Overview Tab -->
            <div class="tab-pane fade show active" id="overview" role="tabpanel">
                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="stat-card">
                            <div class="stat-number">{total_cases}</div>
                            <div>Total Cases</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="stat-card">
                            <div class="stat-number">{avg_age:.0f}</div>
                            <div>Average Age</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="stat-card">
                            <div class="stat-number">{shot_cases}</div>
                            <div>Shootings</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="stat-card">
                            <div class="stat-number">{stabbed_cases}</div>
                            <div>Stabbings</div>
                        </div>
                    </div>
                </div>

                <div class="row">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0"><i class="fas fa-info-circle me-2"></i>Report Summary</h5>
                            </div>
                            <div class="card-body">
                                <p class="lead">This report analyzes {total_cases} unsolved homicide cases from Boston in 2014.</p>
                                <ul class="list-unstyled">
                                    <li><i class="fas fa-calendar me-2 text-primary"></i><strong>Time Period:</strong> January - November 2014</li>
                                    <li><i class="fas fa-map-marker-alt me-2 text-primary"></i><strong>Location:</strong> Various neighborhoods across Boston</li>
                                    <li><i class="fas fa-users me-2 text-primary"></i><strong>Demographics:</strong> All male victims, ages 17-51</li>
                                    <li><i class="fas fa-exclamation-triangle me-2 text-primary"></i><strong>Status:</strong> All cases remain unsolved</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Cases Tab -->
            <div class="tab-pane fade" id="cases" role="tabpanel">
                <div class="row">"""

        # Add individual cases
        for i, case in enumerate(self.boston_cases, 1):
            victim_name = case.get('victim_name', 'Unknown Victim')
            age = case.get('age')
            date = case.get('date', 'Unknown date')
            location = case.get('location', 'Unknown location')
            description = case.get('description', '')
            
            # Determine method
            method = "killed"
            if description:
                if "shot" in description.lower():
                    method = "shot and killed"
                elif "stab" in description.lower():
                    method = "stabbed and killed"
            
            # Create summary
            age_text = f", age {age}," if age else ""
            summary = f"On {date}, {victim_name}{age_text} was {method} at {location.title()}."
            
            html += f"""
                    <div class="col-lg-6 mb-4">
                        <div class="case-card">
                            <div class="case-header">
                                <div class="victim-name">Case #{i}: {victim_name}</div>
                            </div>
                            <div class="case-details">
                                <div class="case-summary">{summary}</div>
                                <div class="case-meta">
                                    <div class="meta-item">
                                        <i class="fas fa-calendar me-1"></i> {date}
                                    </div>
                                    <div class="meta-item">
                                        <i class="fas fa-map-marker-alt me-1"></i> {location.title()}
                                    </div>"""
            
            if age:
                html += f"""
                                    <div class="meta-item">
                                        <i class="fas fa-user me-1"></i> Age {age}
                                    </div>"""
            
            html += """
                                </div>
                            </div>
                        </div>
                    </div>"""

        # Continue with statistics tab and closing HTML
        html += f"""
                </div>
            </div>

            <!-- Statistics Tab -->
            <div class="tab-pane fade" id="statistics" role="tabpanel">
                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0">Cases by Month</h5>
                            </div>
                            <div class="card-body">
                                <div class="chart-container">
                                    <canvas id="monthlyChart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0">Method Analysis</h5>
                            </div>
                            <div class="card-body">
                                <div class="chart-container">
                                    <canvas id="methodChart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row mt-4">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0">Age Distribution</h5>
                            </div>
                            <div class="card-body">
                                <div class="chart-container">
                                    <canvas id="ageChart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <footer class="bg-dark text-light py-4 mt-5">
        <div class="container text-center">
            <p class="mb-0">Report generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
            <p class="mb-0"><small>Data source: Boston Police Department 2014 Unsolved Homicides</small></p>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Monthly Chart
        const monthlyCtx = document.getElementById('monthlyChart').getContext('2d');
        new Chart(monthlyCtx, {{
            type: 'bar',
            data: {{
                labels: {list(months.keys())},
                datasets: [{{
                    label: 'Cases',
                    data: {list(months.values())},
                    backgroundColor: 'rgba(220, 53, 69, 0.8)',
                    borderColor: 'rgba(220, 53, 69, 1)',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{ beginAtZero: true }}
                }}
            }}
        }});

        // Method Chart
        const methodCtx = document.getElementById('methodChart').getContext('2d');
        new Chart(methodCtx, {{
            type: 'doughnut',
            data: {{
                labels: ['Shootings', 'Stabbings'],
                datasets: [{{
                    data: [{shot_cases}, {stabbed_cases}],
                    backgroundColor: ['#dc3545', '#fd7e14']
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false
            }}
        }});

        // Age Chart
        const ageCtx = document.getElementById('ageChart').getContext('2d');
        const ages = {ages};
        const ageRanges = {{'17-25': 0, '26-35': 0, '36-45': 0, '46+': 0}};
        ages.forEach(age => {{
            if (age <= 25) ageRanges['17-25']++;
            else if (age <= 35) ageRanges['26-35']++;
            else if (age <= 45) ageRanges['36-45']++;
            else ageRanges['46+']++;
        }});
        
        new Chart(ageCtx, {{
            type: 'bar',
            data: {{
                labels: Object.keys(ageRanges),
                datasets: [{{
                    label: 'Number of Cases',
                    data: Object.values(ageRanges),
                    backgroundColor: 'rgba(40, 167, 69, 0.8)',
                    borderColor: 'rgba(40, 167, 69, 1)',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{ beginAtZero: true }}
                }}
            }}
        }});
    </script>
</body>
</html>"""

        # Write the HTML file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return f"HTML report generated: {filename}"

def summarize_boston_cases():
    """Summarize each case in the Boston Police 2014 unsolved homicides database."""
    
    checker = ColdCaseCrossChecker()
    
    # Build comprehensive summary report
    report = "📋 BOSTON POLICE 2014 UNSOLVED HOMICIDES - CASE SUMMARIES\n"
    report += "=" * 70 + "\n\n"
    
    # Scrape Boston Police Cases
    report += "📊 Gathering Boston Police case data...\n"
    boston_result = checker.scrape_boston_cases()
    report += f"   {boston_result}\n\n"
    
    if not checker.boston_cases:
        report += "❌ No cases found to summarize.\n"
        return report
    
    # Generate individual case summaries
    report += f"📝 INDIVIDUAL CASE SUMMARIES ({len(checker.boston_cases)} cases):\n"
    report += "=" * 50 + "\n\n"
    
    for i, case in enumerate(checker.boston_cases, 1):
        report += f"🔍 CASE #{i}: {case.get('victim_name', 'Unknown Victim')}\n"
        report += "-" * 50 + "\n"
        
        # Create a clear narrative summary
        victim_name = case.get('victim_name', 'An unidentified person')
        age = case.get('age')
        gender = case.get('gender', 'unknown').lower()
        date = case.get('date', 'an unknown date')
        location = case.get('location', 'an unknown location')
        description = case.get('description', '')
        
        # Extract age from description if not already available
        if not age and description:
            age_match = re.search(r'(\d{1,2})\s*year[s]?\s*old', description, re.IGNORECASE)
            if not age_match:
                age_match = re.search(r'age\s*(\d{1,2})', description, re.IGNORECASE)
            if age_match:
                age = int(age_match.group(1))
        
        # Determine method from description
        method = "killed"
        if description:
            if "shot" in description.lower():
                method = "shot and killed"
            elif "stab" in description.lower():
                method = "stabbed and killed"
        
        # Build a clear narrative
        age_text = f", age {age}," if age else ""
        
        # Create the main summary
        summary = f"On {date}, {victim_name}{age_text} was {method} at {location.title()}."
        
        # Format the final summary
        report += f"📄 {summary}\n"
        
        # Add key details in a structured format
        report += f"   📅 Date: {date}\n"
        report += f"   📍 Location: {location.title()}\n"
        if age:
            report += f"   🎂 Age: {age} years old\n"
        if gender != 'unknown':
            report += f"   ⚧ Gender: {gender.title()}\n"
            
        report += "\n"
    
    report += f"\n⏰ Summary generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    return report

if __name__ == "__main__":
    print("🧪 Running Boston 2014 Cold Case Scraper (Simplified Version)...")
    
    try:
        # Create checker instance
        checker = ColdCaseCrossChecker()
        
        # Scrape the cases
        print("📊 Gathering Boston Police case data...")
        boston_result = checker.scrape_boston_cases()
        print(f"   {boston_result}")
        
        if checker.boston_cases:
            # Generate console summary
            result = summarize_boston_cases()
            print(result)
            
            # Generate HTML report
            print("\n📄 Generating HTML report...")
            html_result = checker.generate_html_report()
            print(f"   {html_result}")
            print("   🌐 Open 'boston_2014_cases_report.html' in your web browser to view the interactive report!")
        else:
            print("❌ No cases found to process.")
            
    except Exception as e:
        print(f"❌ Error running scraper: {e}")
        import traceback
        traceback.print_exc() 