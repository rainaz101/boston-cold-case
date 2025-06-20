# Boston Cold Cases Analysis Tool
# Scrapes and analyzes Boston cold cases

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import folium
import time
import random

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
    
    def geocode_address(self, address):
        """Geocode an address using Nominatim API. Returns (lat, lon) or None if not found."""
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': address + ', Boston, MA',
                'format': 'json',
                'limit': 1
            }
            headers = {'User-Agent': 'BostonColdCaseScript/1.0'}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
        except Exception as e:
            print(f"Geocoding failed for '{address}': {e}")
        return None

    def get_case_coordinates(self, case):
        """Get coordinates for a case using address, neighborhood, or fallback."""
        # Try to geocode address if available
        address = None
        if ',' in case['location']:
            address = case['location']
        elif case['location'] not in [
            'Roxbury', 'Dorchester', 'Mattapan', 'Hyde Park', 'Jamaica Plain',
            'East Boston', 'South Boston', 'Charlestown', 'Back Bay', 'Downtown',
            'South End', 'Brighton', 'Allston', 'West Roxbury', 'Roslindale', 'Boston']:
            address = case['location']
        
        if address:
            coords = self.geocode_address(address)
            if coords:
                return coords
        # Fallback to neighborhood center
        neighborhood_coords = {
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
            'Roslindale': [42.2832, -71.1270],
            'Boston': [42.3601, -71.0589]
        }
        if case['location'] in neighborhood_coords:
            # Add a small random jitter to avoid marker overlap
            lat, lon = neighborhood_coords[case['location']]
            lat += random.uniform(-0.002, 0.002)
            lon += random.uniform(-0.002, 0.002)
            return (lat, lon)
        # Fallback: random jitter around Boston center
        lat, lon = 42.3601, -71.0589
        lat += random.uniform(-0.01, 0.01)
        lon += random.uniform(-0.01, 0.01)
        return (lat, lon)

    def check_national_cold_case_matches(self):
        """Check if Boston 2014 cold case victims are in the national cold case database."""
        # We'll use the Project Cold Case search page and try to match by victim name and city/year
        base_url = "https://database.projectcoldcase.org/"
        matches = []
        for case in self.boston_cases:
            name = case['victim_name']
            if name == "Unknown Victim":
                continue
            # Try to search by name (simulate, since no API)
            # In a real implementation, you would automate browser or scrape search results
            # Here, we just note the name and city for manual/visual matching
            matches.append({
                'victim_name': name,
                'date': case['date'],
                'location': case['location'],
                'search_url': f"{base_url}?search={name.replace(' ', '+')}+Boston+2014"
            })
        return matches

    def find_national_db_matches(self):
        """Automatically search Project Cold Case DB for Boston 2014 victims and return matches and potential matches."""
        matches = []
        potential_matches = []
        base_url = "https://database.projectcoldcase.org/"
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; BostonColdCaseBot/1.0)'}
        for case in self.boston_cases:
            name = case['victim_name']
            if name == "Unknown Victim":
                continue
            params = {'search': f"{name} Boston"}
            try:
                resp = requests.get(base_url, params=params, headers=headers, timeout=15)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, 'lxml')
                rows = soup.find_all('tr')
                found_exact = False
                for row in rows:
                    # Check if row has find_all method (is a proper Tag element)
                    if not hasattr(row, 'find_all'):
                        continue
                    cells = row.find_all('td')
                    if len(cells) < 5:
                        continue
                    victim_cell = cells[0].get_text(strip=True)
                    city_cell = cells[4].get_text(strip=True)
                    # Exact match: name and city
                    if name.lower() == victim_cell.lower() and 'boston' in city_cell.lower():
                        match = {
                            'victim_name': victim_cell,
                            'date': case['date'],
                            'location': case['location'],
                            'city': city_cell,
                            'details': [c.get_text(strip=True) for c in cells],
                            'type': 'exact'
                        }
                        matches.append(match)
                        found_exact = True
                        break  # Only need first exact match per victim
                if not found_exact:
                    # Try to find potential matches (partial name, Boston, or similar year)
                    for row in rows:
                        # Check if row has find_all method (is a proper Tag element)
                        if not hasattr(row, 'find_all'):
                            continue
                        cells = row.find_all('td')
                        if len(cells) < 5:
                            continue
                        victim_cell = cells[0].get_text(strip=True)
                        city_cell = cells[4].get_text(strip=True)
                        # Potential: partial name match, Boston, or year in details
                        if (name.split()[0].lower() in victim_cell.lower() or name.split()[-1].lower() in victim_cell.lower()) and 'boston' in city_cell.lower():
                            match = {
                                'victim_name': victim_cell,
                                'date': case['date'],
                                'location': case['location'],
                                'city': city_cell,
                                'details': [c.get_text(strip=True) for c in cells],
                                'type': 'potential'
                            }
                            potential_matches.append(match)
                            break
                time.sleep(1)  # Be polite to the server
            except Exception as e:
                print(f"Error searching for {name}: {e}")
        return matches, potential_matches

    def scrape_2013_cases(self):
        """Scrape Boston Police 2013 unsolved homicides for monthly/seasonal analysis."""
        url = "https://police.boston.gov/2013-unsolved-homicides/"
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; BostonColdCaseBot/1.0)'}
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text()
            # Find all full date lines for month analysis
            full_date_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*2013'
            full_dates = re.findall(full_date_pattern, text)
            # Count by month
            months = {m: 0 for m in [
                'January', 'February', 'March', 'April', 'May', 'June', 'July',
                'August', 'September', 'October', 'November', 'December']}
            for date in full_dates:
                months[date] += 1
            # Count by season
            seasons = {'Winter': 0, 'Spring': 0, 'Summer': 0, 'Fall': 0}
            season_months = {
                'Winter': ['December', 'January', 'February'],
                'Spring': ['March', 'April', 'May'],
                'Summer': ['June', 'July', 'August'],
                'Fall': ['September', 'October', 'November']
            }
            for month, count in months.items():
                for season, season_month_list in season_months.items():
                    if month in season_month_list:
                        seasons[season] += count
            return months, seasons
        except Exception as e:
            print(f"Error scraping 2013 cases: {e}")
            return {m: 0 for m in [
                'January', 'February', 'March', 'April', 'May', 'June', 'July',
                'August', 'September', 'October', 'November', 'December']}, {'Winter': 0, 'Spring': 0, 'Summer': 0, 'Fall': 0}

    def scrape_2015_cases(self):
        """Scrape Boston Police 2015 unsolved homicides for monthly/seasonal analysis."""
        url = "https://police.boston.gov/2015-unsolved-homicides/"
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; BostonColdCaseBot/1.0)'}
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text()
            # Find all full date lines for month analysis
            full_date_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*2015'
            full_dates = re.findall(full_date_pattern, text)
            # Count by month
            months = {m: 0 for m in [
                'January', 'February', 'March', 'April', 'May', 'June', 'July',
                'August', 'September', 'October', 'November', 'December']}
            for date in full_dates:
                months[date] += 1
            # Count by season
            seasons = {'Winter': 0, 'Spring': 0, 'Summer': 0, 'Fall': 0}
            season_months = {
                'Winter': ['December', 'January', 'February'],
                'Spring': ['March', 'April', 'May'],
                'Summer': ['June', 'July', 'August'],
                'Fall': ['September', 'October', 'November']
            }
            for month, count in months.items():
                for season, season_month_list in season_months.items():
                    if month in season_month_list:
                        seasons[season] += count
            return months, seasons
        except Exception as e:
            print(f"Error scraping 2015 cases: {e}")
            return {m: 0 for m in [
                'January', 'February', 'March', 'April', 'May', 'June', 'July',
                'August', 'September', 'October', 'November', 'December']}, {'Winter': 0, 'Spring': 0, 'Summer': 0, 'Fall': 0}

    def generate_case_maps(self):
        """Generate separate maps for 2013, 2014, and 2015 cases with robust extraction and geocoding. Always add a marker for every case. Print debug info for extraction and mapping."""
        # 2014 map (already generated as boston_cases_map.html)
        # 2013 map
        url_2013 = "https://police.boston.gov/2013-unsolved-homicides/"
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; BostonColdCaseBot/1.0)'}
        response = requests.get(url_2013, headers=headers, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        text = soup.get_text()
        case_blocks = re.split(r'\n\s*\n', text)
        cases_2013 = []
        for block in case_blocks:
            block = block.strip()
            if len(block) < 20:
                continue
            date_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*2013'
            date_match = re.search(date_pattern, block)
            date = date_match.group(0) if date_match else None
            if not date:
                continue
            name = self.extract_name(block)
            location = self.parse_location(block)
            cases_2013.append({'victim_name': name, 'date': date, 'location': location, 'description': block})
        print(f"2013: Extracted {len(cases_2013)} cases")
        if cases_2013:
            print("2013: Sample case:", cases_2013[0])
        boston_map_2013 = folium.Map(location=[42.3601, -71.0589], zoom_start=12)
        for case in cases_2013:
            lat, lon = self.get_case_coordinates(case)
            if not lat or not lon:
                lat, lon = 42.3601 + random.uniform(-0.01, 0.01), -71.0589 + random.uniform(-0.01, 0.01)
            print(f"2013: Mapping {case['victim_name']} at {case['location']} -> ({lat}, {lon})")
            folium.Marker(
                [lat, lon],
                popup=f"{case['victim_name']}<br>{case['date']}<br>{case['location']}"
            ).add_to(boston_map_2013)
        boston_map_2013.save('boston_cases_map_2013.html')
        # 2015 map
        url_2015 = "https://police.boston.gov/2015-unsolved-homicides/"
        response = requests.get(url_2015, headers=headers, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        text = soup.get_text()
        case_blocks = re.split(r'\n\s*\n', text)
        cases_2015 = []
        for block in case_blocks:
            block = block.strip()
            if len(block) < 20:
                continue
            date_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*2015'
            date_match = re.search(date_pattern, block)
            date = date_match.group(0) if date_match else None
            if not date:
                continue
            name = self.extract_name(block)
            location = self.parse_location(block)
            cases_2015.append({'victim_name': name, 'date': date, 'location': location, 'description': block})
        print(f"2015: Extracted {len(cases_2015)} cases")
        if cases_2015:
            print("2015: Sample case:", cases_2015[0])
        boston_map_2015 = folium.Map(location=[42.3601, -71.0589], zoom_start=12)
        for case in cases_2015:
            lat, lon = self.get_case_coordinates(case)
            if not lat or not lon:
                lat, lon = 42.3601 + random.uniform(-0.01, 0.01), -71.0589 + random.uniform(-0.01, 0.01)
            print(f"2015: Mapping {case['victim_name']} at {case['location']} -> ({lat}, {lon})")
            folium.Marker(
                [lat, lon],
                popup=f"{case['victim_name']}<br>{case['date']}<br>{case['location']}"
            ).add_to(boston_map_2015)
        boston_map_2015.save('boston_cases_map_2015.html')

    def generate_html_report(self, filename="boston_unsolved_homicides_2014.html"):
        """Generate a comprehensive HTML report with tabs for different analyses."""
        if not self.boston_cases:
            print("No cases to generate report for.")
            return filename
        
        # Calculate statistics
        total_cases = len(self.boston_cases)
        
        # Monthly distribution for 2014
        months = {m: 0 for m in [
            'January', 'February', 'March', 'April', 'May', 'June', 'July',
            'August', 'September', 'October', 'November', 'December']}
        
        for case in self.boston_cases:
            try:
                month = case['date'].split()[0]
                if month in months:
                    months[month] += 1
            except Exception:
                pass
        
        # Seasonal distribution
        seasons = {'Winter': 0, 'Spring': 0, 'Summer': 0, 'Fall': 0}
        season_months = {
            'Winter': ['December', 'January', 'February'],
            'Spring': ['March', 'April', 'May'],
            'Summer': ['June', 'July', 'August'],
            'Fall': ['September', 'October', 'November']
        }
        
        for month, count in months.items():
            for season, season_month_list in season_months.items():
                if month in season_month_list:
                    seasons[season] += count
        
        # Get 2013 and 2015 data and case counts
        months_2013, seasons_2013 = self.scrape_2013_cases()
        months_2015, seasons_2015 = self.scrape_2015_cases()
        
        # Calculate total cases for each year for display
        total_2013 = sum(months_2013.values()) if months_2013 else 0
        total_2015 = sum(months_2015.values()) if months_2015 else 0
        
        # Create interactive map
        boston_map = folium.Map(location=[42.3601, -71.0589], zoom_start=12)
        
        for case in self.boston_cases:
            lat, lon = self.get_case_coordinates(case)
            folium.Marker(
                [lat, lon],
                popup=folium.Popup(
                    f"<b>{case['victim_name']}</b><br>"
                    f"Date: {case['date']}<br>"
                    f"Location: {case['location']}<br>"
                    f"<small>{case['description'][:100]}...</small>",
                    max_width=300
                ),
                tooltip=f"{case['victim_name']} - {case['date']}"
            ).add_to(boston_map)
        
        # Save the map
        boston_map.save('boston_cases_map.html')
        
        # Generate the complete HTML report
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
        .card {{
            border: none;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 1.5rem;
        }}
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            transition: all 0.3s ease;
        }}
        .stat-card {{
            background: white;
            border-radius: 10px;
            padding: 1.5rem;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .stat-number {{
            font-size: 2.5rem;
            font-weight: bold;
            color: #dc3545;
        }}
        .chart-container {{
            position: relative;
            height: 400px;
            margin: 1rem 0;
        }}
        .map-container {{
            height: 600px;
            border-radius: 8px;
            overflow: hidden;
        }}
        .nav-tabs .nav-link.active {{
            background-color: #dc3545;
            border-color: #dc3545;
            color: white;
        }}
        .case-item {{
            border-left: 4px solid #dc3545;
            padding: 1rem;
            margin-bottom: 1rem;
            background: white;
            border-radius: 0 8px 8px 0;
        }}
        .victim-name {{
            font-size: 1.1rem;
            font-weight: bold;
            color: #dc3545;
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
                    <div class="stat-card">
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
                    <i class="fas fa-list me-2"></i>Cases
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="statistics-tab" data-bs-toggle="tab" data-bs-target="#statistics" type="button" role="tab">
                    <i class="fas fa-chart-pie me-2"></i>Statistics
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="map-tab" data-bs-toggle="tab" data-bs-target="#map" type="button" role="tab">
                    <i class="fas fa-map me-2"></i>Map
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="national-tab" data-bs-toggle="tab" data-bs-target="#national" type="button" role="tab">
                    <i class="fas fa-database me-2"></i>National DB
                </button>
            </li>
        </ul>

        <!-- Tab Content -->
        <div class="tab-content" id="reportTabsContent">
            <!-- Overview Tab -->
            <div class="tab-pane fade show active" id="overview" role="tabpanel">
                <div class="row mb-4">
                    <div class="col">
                        <div class="card">
                            <div class="card-body">
                                <h4 class="card-title">Case Analysis Overview</h4>
                                <p class="lead">Total Unsolved Cases in 2014: <span class="text-danger fw-bold">{total_cases}</span></p>
                                <p>This report analyzes unsolved homicide cases from Boston in 2014, providing insights into patterns, locations, and victim demographics.</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row mb-4">
                    <div class="col">
                        <div class="card">
                            <div class="card-body">
                                <h4 class="card-title">2013 vs 2014 vs 2015 Monthly Distribution</h4>
                                <div class="chart-container">
                                    <canvas id="monthlyCompareChart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row mb-4">
                    <div class="col">
                        <div class="card">
                            <div class="card-body">
                                <h4 class="card-title">2013 vs 2014 vs 2015 Seasonal Pattern</h4>
                                <div class="chart-container">
                                    <canvas id="seasonalCompareChart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Cases Tab -->
            <div class="tab-pane fade" id="cases" role="tabpanel">
                <div class="row">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0">All Cases ({total_cases})</h5>
                            </div>
                            <div class="card-body">"""
        
        # Add individual cases
        for i, case in enumerate(self.boston_cases, 1):
            html += f"""
                                <div class="case-item">
                                    <div class="d-flex justify-content-between align-items-start">
                                        <div>
                                            <div class="victim-name">Case #{i}: {case['victim_name']}</div>
                                            <div class="text-muted mb-2">
                                                <i class="fas fa-calendar me-2"></i>{case['date']} | 
                                                <i class="fas fa-map-marker-alt me-2"></i>{case['location']}
                                            </div>
                                            <p class="mb-0">{case['description']}</p>
                                        </div>
                                    </div>
                                </div>"""
        
        html += """
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Statistics Tab -->
            <div class="tab-pane fade" id="statistics" role="tabpanel">
                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0">2014 Monthly Distribution</h5>
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
                                <h5 class="mb-0">2014 Seasonal Distribution</h5>
                            </div>
                            <div class="card-body">
                                <div class="chart-container">
                                    <canvas id="seasonalChart"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Map Tab -->
            <div class="tab-pane fade" id="map" role="tabpanel">
                <!-- Year Sub-tabs for Maps -->
                <ul class="nav nav-pills mb-3" id="mapYearTabs" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active" id="map2014-tab" data-bs-toggle="pill" data-bs-target="#map2014" type="button" role="tab">
                            2014 Cases ({total_cases})
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="map2013-tab" data-bs-toggle="pill" data-bs-target="#map2013" type="button" role="tab">
                            2013 Cases (15)
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="map2015-tab" data-bs-toggle="pill" data-bs-target="#map2015" type="button" role="tab">
                            2015 Cases (19)
                        </button>
                    </li>
                </ul>
                
                <div class="tab-content" id="mapYearTabsContent">
                    <!-- 2014 Map -->
                    <div class="tab-pane fade show active" id="map2014" role="tabpanel">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">2014 Case Locations</h5>
                                <div class="map-container">
                                    <iframe src="boston_cases_map.html" width="100%" height="100%" frameborder="0"></iframe>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 2013 Map -->
                    <div class="tab-pane fade" id="map2013" role="tabpanel">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">2013 Case Locations</h5>
                                <div class="map-container">
                                    <iframe src="boston_cases_map_2013.html" width="100%" height="100%" frameborder="0"></iframe>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 2015 Map -->
                    <div class="tab-pane fade" id="map2015" role="tabpanel">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">2015 Case Locations</h5>
                                <div class="map-container">
                                    <iframe src="boston_cases_map_2015.html" width="100%" height="100%" frameborder="0"></iframe>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- National Database Tab -->
            <div class="tab-pane fade" id="national" role="tabpanel">
                <div class="row mb-4">
                    <div class="col">
                        <div class="alert alert-warning">
                            <h4 class="alert-heading">National Cold Case Database Matches</h4>
                            <p>This section would show matches from the <a href='https://database.projectcoldcase.org/' target='_blank'>Project Cold Case National Database</a>. 
                            Due to technical limitations, this feature is currently disabled.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <footer class="bg-dark text-light py-4 mt-5">
        <div class="container text-center">
            <p class="mb-0">Boston Cold Cases Analysis Report</p>
            <p class="mb-0"><small>Data source: Boston Police Department</small></p>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Monthly Comparison Chart
        const monthlyCompareCtx = document.getElementById('monthlyCompareChart').getContext('2d');
        new Chart(monthlyCompareCtx, {{
            type: 'bar',
            data: {{
                labels: {list(months.keys())},
                datasets: [{{
                    label: '2014',
                    data: {list(months.values())},
                    backgroundColor: 'rgba(54, 162, 235, 0.7)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }}, {{
                    label: '2013',
                    data: {list(months_2013.values()) if months_2013 else [0]*12},
                    backgroundColor: 'rgba(255, 99, 132, 0.7)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1
                }}, {{
                    label: '2015',
                    data: {list(months_2015.values()) if months_2015 else [0]*12},
                    backgroundColor: 'rgba(75, 192, 192, 0.7)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{ 
                        beginAtZero: true,
                        ticks: {{ precision: 0 }}
                    }}
                }}
            }}
        }});

        // Seasonal Comparison Chart
        const seasonalCompareCtx = document.getElementById('seasonalCompareChart').getContext('2d');
        new Chart(seasonalCompareCtx, {{
            type: 'bar',
            data: {{
                labels: {list(seasons.keys())},
                datasets: [{{
                    label: '2014',
                    data: {list(seasons.values())},
                    backgroundColor: 'rgba(54, 162, 235, 0.7)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }}, {{
                    label: '2013',
                    data: {list(seasons_2013.values()) if seasons_2013 else [0]*4},
                    backgroundColor: 'rgba(255, 99, 132, 0.7)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1
                }}, {{
                    label: '2015',
                    data: {list(seasons_2015.values()) if seasons_2015 else [0]*4},
                    backgroundColor: 'rgba(75, 192, 192, 0.7)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{ 
                        beginAtZero: true,
                        ticks: {{ precision: 0 }}
                    }}
                }}
            }}
        }});
        
        // 2014 Monthly Chart
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

        // 2014 Seasonal Chart
        const seasonalCtx = document.getElementById('seasonalChart').getContext('2d');
        new Chart(seasonalCtx, {{
            type: 'doughnut',
            data: {{
                labels: {list(seasons.keys())},
                datasets: [{{
                    data: {list(seasons.values())},
                    backgroundColor: [
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(255, 206, 86, 0.8)',
                        'rgba(75, 192, 192, 0.8)'
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false
            }}
        }});
    </script>
</body>
</html>"""
        
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
            
            # Generate additional maps for different years
            print("🗺️  Generating case maps for all years...")
            checker.generate_case_maps()
            
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