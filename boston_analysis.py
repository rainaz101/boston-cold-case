# Boston Cold Cases Analysis Tool
# Scrapes and analyzes Boston cold cases

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import folium

class ColdCaseCrossChecker:
    def __init__(self):
        self.boston_cases = []
        self.BOSTON_URL = "https://police.boston.gov/2014-unsolved-homicides/"
        self.MAX_CASES = 25

    def parse_date(self, date_str):
        """Convert date string to consistent format."""
        try:
            if not date_str:
                return None
            
            # Clean up the date string
            date_str = date_str.strip()
            # Handle cases where the year might be missing
            if '2014' not in date_str:
                date_str += ' 2014'
            # Remove any extra spaces and commas
            date_str = re.sub(r'\s+', ' ', date_str)
            date_str = date_str.replace(',', '')
            # Parse the date
            date_obj = datetime.strptime(date_str, '%B %d %Y')
            # Return formatted date
            return date_obj.strftime('%B %d, %Y')
        except Exception as e:
            print(f"Date parsing error for '{date_str}': {str(e)}")
            return None

    def extract_name(self, text):
        """Extract victim name from case description."""
        # The Boston Police format is: "Name Address On Date, police responded... victim was later identified as Name, age"
        
        # First try to find "identified as [Name]" pattern which is most reliable
        identified_pattern = r'(?:victim\s+was\s+)?(?:later\s+)?identified\s+as\s+([A-Za-z\s\'-]+?)(?:\s*,\s*\d+|\s*,\s*age|\s*,\s*and|\s*\.|$)'
        match = re.search(identified_pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Clean up any extra words
            name = re.sub(r'\s+(?:aka|also\s+known\s+as)\s+.*$', '', name, flags=re.IGNORECASE)
            name = re.sub(r'\s+', ' ', name)
            name = name.title()
            if len(name) >= 2 and not any(word in name.lower() for word in ['victim', 'man', 'woman', 'person']):
                return name
        
        # Second try: Look for name at the very beginning before address/street
        # Pattern: "FirstName LastName [Address/Street info]"
        start_pattern = r'^([A-Za-z\s\'-]+?)\s+(?:\d+\s+[A-Za-z\s]+?(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Circle|Way|Place|Pl)|[A-Z][a-z]+\s+(?:Hill|Street|Avenue|Road))'
        match = re.search(start_pattern, text)
        if match:
            name = match.group(1).strip()
            # Remove common prefixes
            name = re.sub(r'^(?:the\s+body\s+of\s+|victim\s+)', '', name, flags=re.IGNORECASE)
            name = re.sub(r'\s+', ' ', name)
            name = name.title()
            if len(name) >= 2 and not any(word in name.lower() for word in ['victim', 'man', 'woman', 'person', 'body']):
                return name
        
        # Third try: Look for "body of [Name]" pattern
        body_pattern = r'(?:the\s+)?body\s+of\s+([A-Za-z\s\'-]+?)(?:\s*,|\s+was|\s+had|\s*\.|$)'
        match = re.search(body_pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'\s+', ' ', name)
            name = name.title()
            if len(name) >= 2 and not any(word in name.lower() for word in ['victim', 'man', 'woman', 'person']):
                return name
        
        # Fourth try: Look for name after "victim" but before common words
        victim_pattern = r'victim\s+([A-Za-z\s\'-]+?)(?:\s*,|\s+was|\s+had|\s+died|\s+suffered|\s*\.|$)'
        match = re.search(victim_pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'\s+', ' ', name)
            name = name.title()
            if len(name) >= 2 and not any(word in name.lower() for word in ['later', 'was', 'had', 'been']):
                return name
        
        # Last resort: try to find any name-like pattern at the start
        fallback_pattern = r'^([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        match = re.search(fallback_pattern, text)
        if match:
            name = match.group(1).strip()
            if not any(word in name.lower() for word in ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december', 'police', 'boston', 'department']):
                return name
        
        return "Unknown Victim"

    def parse_location(self, text):
        """Extract location from case description."""
        # Try to find specific address
        address_pattern = r'(?:at|on|near|in front of|behind)\s+(\d+\s+[A-Za-z\s\.]+?(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Circle|Way|Place|Pl)\.?)'
        address_match = re.search(address_pattern, text, re.IGNORECASE)
        
        neighborhoods = [
            'Roxbury', 'Dorchester', 'Mattapan', 'Hyde Park', 'Jamaica Plain',
            'East Boston', 'South Boston', 'Charlestown', 'Back Bay', 'Downtown',
            'South End', 'Brighton', 'Allston', 'West Roxbury', 'Roslindale'
        ]
        
        location = None
        neighborhood = None
        
        # Find the neighborhood
        for n in neighborhoods:
            if n.lower() in text.lower():
                neighborhood = n
                break
        
        # Get the specific address if available
        if address_match:
            location = address_match.group(1).strip()
            if neighborhood:
                location = f"{location}, {neighborhood}"
        elif neighborhood:
            location = neighborhood
        else:
            location = "Boston"
        
        return location

    def cleanup_description(self, description, date, victim_name=None, location=None):
        """Clean up the case description by removing redundant information while keeping meaningful details."""
        if not description:
            return ""
        
        original_description = description
        
        # Remove the redundant prefix that appears at the start
        # Pattern: "Name Address On Date, Boston Police Department responded..."
        
        # First, remove the name/address/date prefix more aggressively
        description = re.sub(r'^[^.]*?(?:On\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*2014,?\s*)?(?:the\s+)?Boston Police Department responded to[^.]*\.\s*', '', description, flags=re.IGNORECASE)
        
        # If that didn't work, try removing just the name/address part
        if victim_name and victim_name != "Unknown Victim":
            name_escaped = re.escape(victim_name)
            description = re.sub(fr'^{name_escaped}[^.]*?\.\s*', '', description, flags=re.IGNORECASE)
        
        # Remove any remaining address patterns at the beginning
        description = re.sub(r'^\d+\s+[A-Za-z\s]+?(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Circle|Way|Place|Pl)[^.]*?\.\s*', '', description, flags=re.IGNORECASE)
        
        # Remove any remaining date patterns at the beginning
        description = re.sub(r'^(?:On\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*2014[^.]*?\.\s*', '', description, flags=re.IGNORECASE)
        
        # Remove street names that might be left at the beginning
        description = re.sub(r'^(?:AKA\s+[^.]*?\s+)?\d*\s*[A-Za-z\s]*?(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Circle|Way|Place|Pl|Hill)\s*(?:&\s*[A-Za-z\s]*?(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Circle|Way|Place|Pl))?\s*', '', description, flags=re.IGNORECASE)
        
        # Remove the redundant victim identification sentence but keep age if it adds context
        description = re.sub(r'The victim was later identified as [^,]+,\s*(\d+),?\s*and was pronounced deceased\.?\s*', r'The \1-year-old was pronounced deceased. ', description, flags=re.IGNORECASE)
        description = re.sub(r'The victim was later identified as [^,]+,?\s*and was pronounced deceased\.?\s*', 'The victim was pronounced deceased. ', description, flags=re.IGNORECASE)
        description = re.sub(r'The victim was later identified as [^,]+,\s*\d+\.?\s*', '', description, flags=re.IGNORECASE)
        
        # Simplify the manner of death sentence
        description = re.sub(r'The manner of death of [^.]+ was determined to be (?:a )?homicide by the Office of the Chief Medical Examiner\.?\s*', 'The death was ruled a homicide. ', description, flags=re.IGNORECASE)
        
        # Clean up redundant phrases but keep meaningful content
        redundant_phrases = [
            (r'^(?:The\s+)?victim\s+', ''),
            (r'^(?:A|An)\s+(\d+)[\s-]year[\s-]old\s+(?:man|woman|male|female)\s+', r'A \1-year-old '),
            (r'^(?:Police|Officers)\s+(?:found|discovered)\s+(?:the\s+body\s+of\s+)?', 'Police found '),
            (r'^(?:The\s+)?body\s+of\s+(?:a|an)\s+', 'The body of a '),
        ]
        
        for pattern, replacement in redundant_phrases:
            description = re.sub(pattern, replacement, description, flags=re.IGNORECASE)
        
        # Clean up whitespace and format
        description = re.sub(r'\s+', ' ', description)
        description = description.strip()
        
        # Remove leading punctuation
        description = re.sub(r'^[,\.\-\s]+', '', description)
        
        # Capitalize first letter if needed
        if description and description[0].islower():
            description = description[0].upper() + description[1:]
        
        # If the description is too short, try to extract more meaningful content
        if len(description) < 50:
            # Look for key details in the original text
            details = []
            
            # Extract age if available
            age_match = re.search(r'(\d+)[\s-]year[\s-]old', original_description, re.IGNORECASE)
            if age_match:
                details.append(f"{age_match.group(1)} years old")
            
            # Extract circumstances
            circumstances = []
            if re.search(r'shot', original_description, re.IGNORECASE):
                circumstances.append('shot')
            if re.search(r'stabbed', original_description, re.IGNORECASE):
                circumstances.append('stabbed')
            if re.search(r'found.*body', original_description, re.IGNORECASE):
                circumstances.append('body discovered')
            
            # Extract time if available
            time_match = re.search(r'(?:at\s+)?(?:approximately\s+)?(\d{1,2}:\d{2}(?:\s*[ap]m)?|\d{1,2}\s*[ap]m)', original_description, re.IGNORECASE)
            if time_match:
                details.append(f"at {time_match.group(1)}")
            
            # Build a more complete description
            if circumstances:
                base_desc = f"Victim was {' and '.join(circumstances)}"
                if details:
                    base_desc += f" ({', '.join(details)})"
                base_desc += ". The death was ruled a homicide."
                description = base_desc
            elif len(description) < 20:
                description = "Victim of homicide. Investigation ongoing."
        
        return description

    def scrape_boston_cases(self):
        """Scrape Boston Police unsolved homicides."""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(self.BOSTON_URL, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            content = soup.get_text()
            
            # Extract cases using date pattern
            date_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s+2014)?'
            
            # Split content into blocks and process
            blocks = re.split(r'\n\s*\n', content)  # Split by one or more blank lines
            cases = []
            current_date = None
            
            for block in blocks:
                block = block.strip()
                if not block:  # Skip empty blocks
                    continue
                
                # Check if this block starts with a date
                date_match = re.match(date_pattern, block)
                if date_match:
                    current_date = date_match.group(0)
                    description = block[len(date_match.group(0)):].strip()
                else:
                    description = block
                
                # Only process blocks that have meaningful content
                if description and len(description) > 20:
                    # Parse the date
                    parsed_date = self.parse_date(current_date) if current_date else None
                    if not parsed_date:
                        continue
                    
                    # Extract name
                    name = self.extract_name(description)
                    
                    # Get location
                    location = self.parse_location(description)
                    
                    # Clean up the description
                    cleaned_description = self.cleanup_description(description, parsed_date, name, location)
                    
                    if cleaned_description:
                        case = {
                            'date': parsed_date,
                            'victim_name': name,
                            'description': cleaned_description,
                            'location': location
                        }
                        cases.append(case)
            
            # Remove any duplicates based on victim name and date
            cases = list({(case['victim_name'], case['date']): case for case in cases}.values())
            
            # Sort cases by date
            cases.sort(key=lambda x: datetime.strptime(x['date'].replace(',', ''), '%B %d %Y'))
            
            # Take only the first MAX_CASES cases
            if len(cases) > self.MAX_CASES:
                print(f"Found {len(cases)} cases, limiting to {self.MAX_CASES}")
                cases = cases[:self.MAX_CASES]
            elif len(cases) < self.MAX_CASES:
                print(f"Warning: Only found {len(cases)} cases, expected {self.MAX_CASES}")
            
            self.boston_cases = cases
            return f"Found {len(self.boston_cases)} Boston Police cases from 2014"
            
        except Exception as e:
            print(f"Error details: {str(e)}")
            return f"Error scraping Boston Police: {str(e)}"
    
    def generate_html_report(self, filename="boston_unsolved_homicides_2014.html"):
        """Generate an HTML report with multiple tabs for different analyses."""
        # Create a map for the cases
        boston_map = folium.Map(location=[42.3601, -71.0589], zoom_start=12)
        
        # Add custom markers for each case
        for case in self.boston_cases:
            # Use the same geocoding logic as before
            coords = {
                'Roxbury': [42.3301, -71.0995],
                'Dorchester': [42.3016, -71.0676],
                'Mattapan': [42.2771, -71.0914],
                'Hyde Park': [42.2565, -71.1241],
                'Jamaica Plain': [42.3097, -71.1151],
                'East Boston': [42.3702, -71.0389],
                'South Boston': [42.3381, -71.0476],
                'Charlestown': [42.3782, -71.0602],
                'Back Bay': [42.3503, -71.0810],
                'Downtown': [42.3601, -71.0589],
                'South End': [42.3388, -71.0765],
                'Brighton': [42.3464, -71.1627],
                'Allston': [42.3539, -71.1337],
                'West Roxbury': [42.2798, -71.1627],
                'Roslindale': [42.2832, -71.1270]
            }.get(case['location'], [42.3601, -71.0589])
            
            popup_html = f"""
                <div style='min-width: 200px'>
                    <h6>{case['victim_name']}</h6>
                    <p><strong>Date:</strong> {case['date']}</p>
                    <p><strong>Location:</strong> {case['location']}</p>
                    <p>{case['description']}</p>
                </div>
            """
            
            folium.Marker(
                coords,
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(boston_map)
            
        boston_map.save('boston_cases_map.html')
        
        # Calculate statistics
        total_cases = len(self.boston_cases)
        
        # Initialize statistics
        months = {
            'January': 0, 'February': 0, 'March': 0, 'April': 0, 
            'May': 0, 'June': 0, 'July': 0, 'August': 0, 
            'September': 0, 'October': 0, 'November': 0, 'December': 0
        }
        
        # Time of year statistics
        seasons = {'Winter': 0, 'Spring': 0, 'Summer': 0, 'Fall': 0}
        season_months = {
            'Winter': ['December', 'January', 'February'],
            'Spring': ['March', 'April', 'May'],
            'Summer': ['June', 'July', 'August'],
            'Fall': ['September', 'October', 'November']
        }
        
        # Time patterns
        time_patterns = {
            'Morning (6AM-12PM)': 0,
            'Afternoon (12PM-6PM)': 0,
            'Evening (6PM-12AM)': 0,
            'Night (12AM-6AM)': 0,
            'Unknown Time': 0
        }
        
        for case in self.boston_cases:
            # Monthly distribution
            month = case['date'].split()[0]
            if month in months:
                months[month] += 1
            
            # Seasonal distribution
            for season, season_month_list in season_months.items():
                if month in season_month_list:
                    seasons[season] += 1
                    break
            
            # Time of day analysis
            desc = case['description'].lower()
            if any(time in desc for time in ['morning', 'am', 'a.m.', '6am', '7am', '8am', '9am', '10am', '11am']):
                time_patterns['Morning (6AM-12PM)'] += 1
            elif any(time in desc for time in ['afternoon', 'pm', 'p.m.', '12pm', '1pm', '2pm', '3pm', '4pm', '5pm']):
                time_patterns['Afternoon (12PM-6PM)'] += 1
            elif any(time in desc for time in ['evening', 'night', '6pm', '7pm', '8pm', '9pm', '10pm', '11pm']):
                time_patterns['Evening (6PM-12AM)'] += 1
            elif any(time in desc for time in ['midnight', '12am', '1am', '2am', '3am', '4am', '5am']):
                time_patterns['Night (12AM-6AM)'] += 1
            else:
                time_patterns['Unknown Time'] += 1
        
        # Generate the HTML
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Boston 2014 Unsolved Homicides</title>
            <meta charset="UTF-8">            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css" rel="stylesheet">
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>                .case-card { 
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    height: 100%;
                    border: none;
                    border-radius: 8px;
                }
                .case-card:hover { 
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2); 
                    transition: all 0.3s ease; 
                }
                .case-details { 
                    padding: 20px; 
                    white-space: pre-line;
                }
                .card-text {
                    margin-bottom: 0;
                    font-size: 1rem;
                    line-height: 1.6;
                    color: #333;
                }
                .card-title {
                    color: #0d6efd;
                    font-size: 1.5rem;
                    font-weight: 600;
                    margin-bottom: 0.5rem;
                }
                .card-meta {
                    color: #6c757d;
                    font-size: 0.9rem;
                    margin-bottom: 1rem;
                }
                .card-body {
                    padding: 1.5rem;
                }
                hr {
                    opacity: 0.1;
                }
                .card-meta i {
                    margin-right: 0.5rem;
                }
                .stats-card { 
                    background-color: #f8f9fa; 
                    padding: 20px; 
                    margin-bottom: 20px; 
                    border-radius: 5px; 
                }
                .map-container { 
                    height: 700px; 
                    width: 100%; 
                    border-radius: 5px; 
                    overflow: hidden; 
                }
                .chart-container { 
                    position: relative; 
                    height: 400px; 
                    margin-bottom: 30px; 
                }
                .nav-tabs .nav-link.active { 
                    border-bottom: 3px solid #0d6efd; 
                }
                .stat-highlight {
                    font-size: 1.2em;
                    font-weight: bold;
                    color: #0d6efd;
                }
            </style>
        </head>
        <body>
            <nav class="navbar navbar-dark bg-primary">
                <div class="container">
                    <span class="navbar-brand mb-0 h1">Boston 2014 Unsolved Homicides Database</span>
                </div>
            </nav>
            
            <div class="container mt-4">
                <!-- Tab Navigation -->
                <ul class="nav nav-tabs mb-4" id="myTab" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active" id="summary-tab" data-bs-toggle="tab" data-bs-target="#summary" type="button">
                            Case Summary
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="stats-tab" data-bs-toggle="tab" data-bs-target="#stats" type="button">
                            Statistical Analysis
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="map-tab" data-bs-toggle="tab" data-bs-target="#map" type="button">
                            Case Map
                        </button>
                    </li>
                </ul>

                <!-- Tab Content -->
                <div class="tab-content" id="myTabContent">                    <!-- Summary Tab -->
                    <div class="tab-pane fade show active" id="summary" role="tabpanel">
                        <div class="row mb-4">
                            <div class="col">
                                <div class="alert alert-info">
                                    <h4 class="alert-heading">2014 Unsolved Homicides</h4>
                                    <p>Detailed information about """ + str(total_cases) + """ unsolved homicide cases from 2014 in Boston.</p>
                                </div>
                            </div>
                        </div>
                        <div class="row">
        """
        
        # Add full case summaries, two per row
        for i in range(0, len(self.boston_cases), 2):
            html += """
                            <div class="row mb-4">
            """
            
            # First case in the row
            case = self.boston_cases[i]
            description = self.cleanup_description(case['description'], case['date'], case['victim_name'], case['location'])
            
            html += f"""
                                <div class="col-md-6 mb-4">
                                    <div class="card case-card h-100">
                                        <div class="card-body">
                                            <h4 class="card-title">{case['victim_name']}</h4>
                                            <h6 class="card-subtitle mb-3 text-muted">
                                                <strong>Date:</strong> {case['date']} | <strong>Location:</strong> {case['location']}
                                            </h6>
                                            <p class="card-text case-details">{description}</p>
                                        </div>
                                    </div>
                                </div>
            """
            
            # Second case in the row (if available)
            if i + 1 < len(self.boston_cases):
                case = self.boston_cases[i + 1]
                description = self.cleanup_description(case['description'], case['date'], case['victim_name'], case['location'])
                
                html += f"""
                                <div class="col-md-6 mb-4">
                                    <div class="card case-card h-100">
                                        <div class="card-body">
                                            <h4 class="card-title">{case['victim_name']}</h4>
                                            <h6 class="card-subtitle mb-3 text-muted">
                                                <strong>Date:</strong> {case['date']} | <strong>Location:</strong> {case['location']}
                                            </h6>
                                            <p class="card-text case-details">{description}</p>
                                        </div>
                                    </div>
                                </div>
                """
            
            html += """
                            </div>
            """
        
        html += """
                        </div>
                    </div>
                    
                    <!-- Statistics Tab -->
                    <div class="tab-pane fade" id="stats" role="tabpanel">
                        <div class="row mb-4">
                            <div class="col">
                                <div class="card">
                                    <div class="card-body">
                                        <h4 class="card-title">Case Analysis Overview</h4>
                                        <p class="lead">Total Unsolved Cases in 2014: <span class="stat-highlight">""" + str(total_cases) + """</span></p>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6">
                                <div class="card mb-4">
                                    <div class="card-body">
                                        <h5 class="card-title">Monthly Distribution</h5>
                                        <div class="chart-container">
                                            <canvas id="monthlyChart"></canvas>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card mb-4">
                                    <div class="card-body">
                                        <h5 class="card-title">Seasonal Pattern</h5>
                                        <div class="chart-container">
                                            <canvas id="seasonalChart"></canvas>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-12">
                                <div class="card mb-4">
                                    <div class="card-body">
                                        <h5 class="card-title">Time of Day Analysis</h5>
                                        <div class="chart-container">
                                            <canvas id="timeChart"></canvas>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Map Tab -->
                    <div class="tab-pane fade" id="map" role="tabpanel">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">Case Locations</h5>
                                <div class="map-container">
                                    <iframe src="boston_cases_map.html" width="100%" height="100%" frameborder="0"></iframe>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Initialize Charts -->
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                // Monthly Distribution Chart
                const monthlyCtx = document.getElementById('monthlyChart').getContext('2d');
                new Chart(monthlyCtx, {
                    type: 'bar',
                    data: {
                        labels: """ + str(list(months.keys())) + """,
                        datasets: [{
                            label: 'Cases by Month',
                            data: """ + str(list(months.values())) + """,
                            backgroundColor: 'rgba(54, 162, 235, 0.7)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: { 
                                beginAtZero: true,
                                ticks: { precision: 0 }
                            }
                        }
                    }
                });

                // Seasonal Distribution Chart
                const seasonalCtx = document.getElementById('seasonalChart').getContext('2d');
                new Chart(seasonalCtx, {
                    type: 'pie',
                    data: {
                        labels: """ + str(list(seasons.keys())) + """,
                        datasets: [{
                            data: """ + str(list(seasons.values())) + """,
                            backgroundColor: [
                                'rgba(54, 162, 235, 0.7)',  // Winter
                                'rgba(75, 192, 192, 0.7)',  // Spring
                                'rgba(255, 159, 64, 0.7)',  // Summer
                                'rgba(255, 99, 132, 0.7)'   // Fall
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: { padding: 20 }
                            }
                        }
                    }
                });

                // Time of Day Chart
                const timeCtx = document.getElementById('timeChart').getContext('2d');
                new Chart(timeCtx, {
                    type: 'bar',
                    data: {
                        labels: """ + str(list(time_patterns.keys())) + """,
                        datasets: [{
                            label: 'Cases by Time of Day',
                            data: """ + str(list(time_patterns.values())) + """,
                            backgroundColor: 'rgba(153, 102, 255, 0.7)',
                            borderColor: 'rgba(153, 102, 255, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: { 
                                beginAtZero: true,
                                ticks: { precision: 0 }
                            }
                        }
                    }
                });
            </script>
        </body>
        </html>
        """
        
        # Write the HTML file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ HTML report generated: {filename}")
        return filename

def main():
    try:
        # Create the checker instance
        checker = ColdCaseCrossChecker()
        
        # Scrape cases
        print("🔍 Scraping Boston cases...")
        result = checker.scrape_boston_cases()
        print(result)
        
        # Generate report only if we have cases
        if checker.boston_cases:
            print(f"Found {len(checker.boston_cases)} cases")
            print("📄 Generating HTML report...")
            filename = checker.generate_html_report()
            print(f"✅ Report generated: {filename}")
            print(f"Open {filename} in your web browser to view the report.")
        else:
            print("❌ No cases found to generate report.")
    
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main()
