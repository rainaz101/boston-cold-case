#has individual summaries of boston cases, summarize stats, cross checks
#boston cases and cold case database and finds potential matches
#3
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import json
from typing import List, Dict, Any
from mcp.server import FastMCP
from mcp.types import Tool
from dotenv import load_dotenv
import folium 
from folium.plugins import MarkerCluster
import io
import geocoder
from geopy.geocoders import GoogleV3
import time


load_dotenv()

# Initialize MCP server
mcp = FastMCP("ColdCaseCrossChecker")

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
        """Clean and truncate description."""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove common boilerplate text
        boilerplate_phrases = [
            "Our greatest resource in solving homicide cases is information from witnesses, family, friends and the community.",
            "If you have any information regarding this case, please contact the Boston Police Department",
            "Anyone with information is asked to contact",
        ]
        
        for phrase in boilerplate_phrases:
            text = text.replace(phrase, "")
        
        # Remove phone numbers
        text = re.sub(r'\d{3}-\d{3}-\d{4}', '', text)
        text = re.sub(r'1-800-\d{3}-\d{4}', '', text)
        
        # Clean up extra spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Truncate if too long
        if len(text) > 300:
            text = text[:300] + "..."
        
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
    
    def scrape_cold_case_db(self):
        """Scrape Project Cold Case database for Boston cases."""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(self.COLD_CASE_URL, headers=headers, timeout=30)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for case entries
            case_elements = soup.find_all(['div', 'tr', 'li'], class_=re.compile(r'case|entry|row'))
            
            # If no structured cases found, look for any text mentioning Boston
            if not case_elements:
                case_elements = soup.find_all(['p', 'div', 'td'])
            
            for element in case_elements:
                text = element.get_text(strip=True)
                if self._is_boston_case(text):
                    case_info = self._extract_cold_case_info(text)
                    if case_info:
                        self.cold_case_db.append(case_info)
            
            if not self.cold_case_db:
                return f"Warning: No cold cases found from scraping {self.COLD_CASE_URL}"
                
        except Exception as e:
            return f"Error scraping Cold Case DB: {e}"
        
        return f"Found {len(self.cold_case_db)} cold cases from Boston area"
    
    def _is_boston_case(self, text):
        """Check if cold case is from Boston area."""
        text_lower = text.lower()
        boston_indicators = ['boston', 'massachusetts', 'ma', 'suffolk county']
        return any(indicator in text_lower for indicator in boston_indicators) and len(text) > 30
    
    def _extract_cold_case_info(self, text):
        """Extract information from cold case text."""
        # Extract victim name
        name_pattern = r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b'
        name_matches = re.findall(name_pattern, text)
        victim_name = name_matches[0] if name_matches else "Unknown"
        
        # Extract age
        age_match = re.search(r'\b(\d{1,2})\s*year[s]?\s*old\b', text.lower())
        age = int(age_match.group(1)) if age_match else None
        
        # Extract date
        date_patterns = [
            r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b',
            r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',
            r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})\b'
        ]
        
        date = None
        for pattern in date_patterns:
            date_match = re.search(pattern, text.lower())
            if date_match:
                date = date_match.group(0)
                break
        
        # Extract location
        location = self._extract_location(text)
        
        return {
            "source": "cold_case_db",
            "victim_name": victim_name,
            "age": age,
            "date": date,
            "location": location,
            "description": text[:200] + "..." if len(text) > 200 else text
        }
    
    def find_enhanced_boston_matches(self):
        """Enhanced matching specifically for Boston 2014 cases against cold case database."""
        self.matches = []
        
        if not self.boston_cases:
            return self.matches
        
        for boston_case in self.boston_cases:
            # Focus on 2014 cases specifically
            boston_year = self._extract_year(boston_case.get('date', ''))
            if boston_year != 2014:
                continue
                
            for cold_case in self.cold_case_db:
                match_score = self._calculate_enhanced_match_score(boston_case, cold_case)
                
                if match_score > 0.2:  # Lower threshold for Boston 2014 cases
                    self.matches.append({
                        "boston_case": boston_case,
                        "cold_case": cold_case,
                        "match_score": match_score,
                        "match_reasons": self._get_enhanced_match_reasons(boston_case, cold_case)
                    })
        
        # Sort by match score
        self.matches.sort(key=lambda x: x['match_score'], reverse=True)
        return self.matches
    
    def _calculate_enhanced_match_score(self, boston_case, cold_case):
        """Enhanced scoring specifically for Boston 2014 cases."""
        score = 0.0
        
        # Name similarity (highest weight for Boston cases)
        boston_name = boston_case.get('victim_name', '').lower()
        cold_name = cold_case.get('victim_name', '').lower()
        if boston_name and cold_name and boston_name != 'unknown' and cold_name != 'unknown':
            if boston_name == cold_name:
                score += 0.6  # Exact name match
            elif any(part in cold_name for part in boston_name.split() if len(part) > 2):
                score += 0.4  # Partial name match
        
        # Age match (important for victim identification)
        if boston_case.get('age') and cold_case.get('age'):
            age_diff = abs(boston_case['age'] - cold_case['age'])
            if age_diff == 0:
                score += 0.3
            elif age_diff <= 2:
                score += 0.2
            elif age_diff <= 5:
                score += 0.1
        
        # Date proximity (focus on 2014 and nearby years)
        boston_year = self._extract_year(boston_case.get('date', ''))
        cold_year = self._extract_year(cold_case.get('date', ''))
        if boston_year and cold_year:
            year_diff = abs(boston_year - cold_year)
            if year_diff == 0:
                score += 0.3
            elif year_diff <= 1:
                score += 0.2
            elif year_diff <= 3:
                score += 0.1
        
        # Location match (Boston area focus)
        boston_loc = boston_case.get('location', '').lower()
        cold_loc = cold_case.get('location', '').lower()
        if boston_loc and cold_loc:
            # Check for Boston area matches
            boston_areas = ['boston', 'roxbury', 'dorchester', 'mattapan', 'south end', 
                          'jamaica plain', 'charlestown', 'east boston', 'south boston']
            
            boston_in_area = any(area in boston_loc for area in boston_areas)
            cold_in_area = any(area in cold_loc for area in boston_areas)
            
            if boston_in_area and cold_in_area:
                if boston_loc == cold_loc:
                    score += 0.3
                elif any(area in boston_loc and area in cold_loc for area in boston_areas):
                    score += 0.2
                else:
                    score += 0.1
        
        return min(score, 1.0)
    
    def _get_enhanced_match_reasons(self, boston_case, cold_case):
        """Get detailed reasons for Boston 2014 case matches."""
        reasons = []
        
        # Name analysis
        boston_name = boston_case.get('victim_name', '').lower()
        cold_name = cold_case.get('victim_name', '').lower()
        if boston_name and cold_name and boston_name != 'unknown' and cold_name != 'unknown':
            if boston_name == cold_name:
                reasons.append(f"Exact victim name match: {boston_case.get('victim_name')}")
            elif any(part in cold_name for part in boston_name.split() if len(part) > 2):
                reasons.append(f"Partial name match: {boston_case.get('victim_name')} / {cold_case.get('victim_name')}")
        
        # Age analysis
        if boston_case.get('age') and cold_case.get('age'):
            age_diff = abs(boston_case['age'] - cold_case['age'])
            if age_diff == 0:
                reasons.append(f"Exact age match: {boston_case['age']} years old")
            elif age_diff <= 2:
                reasons.append(f"Very close age: {boston_case['age']} vs {cold_case['age']} years old")
            elif age_diff <= 5:
                reasons.append(f"Similar age range: {boston_case['age']} vs {cold_case['age']} years old")
        
        # Date analysis
        boston_year = self._extract_year(boston_case.get('date', ''))
        cold_year = self._extract_year(cold_case.get('date', ''))
        if boston_year and cold_year:
            year_diff = abs(boston_year - cold_year)
            if year_diff == 0:
                reasons.append(f"Same year: {boston_year}")
            elif year_diff <= 1:
                reasons.append(f"Adjacent years: {boston_year} vs {cold_year}")
            elif year_diff <= 3:
                reasons.append(f"Close timeframe: {boston_year} vs {cold_year}")
        
        # Location analysis
        boston_loc = boston_case.get('location', '')
        cold_loc = cold_case.get('location', '')
        if boston_loc and cold_loc:
            if boston_loc.lower() == cold_loc.lower():
                reasons.append(f"Exact location match: {boston_loc}")
            elif any(word in cold_loc.lower() for word in boston_loc.lower().split()):
                reasons.append(f"Location overlap: {boston_loc} / {cold_loc}")
        
        # Boston area confirmation
        if any(area in boston_case.get('location', '').lower() for area in ['boston', 'roxbury', 'dorchester']):
            reasons.append("Confirmed Boston area case")
        
        return reasons
    
    def _extract_year(self, date_str):
        """Extract year from date string."""
        if not date_str:
            return None
        year_match = re.search(r'\b(19|20)\d{2}\b', str(date_str))
        return int(year_match.group(0)) if year_match else None

@mcp.tool()
def summarize_boston_cases() -> str:
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
        report += f"🔍 CASE #{i}\n"
        report += "-" * 20 + "\n"
        
        # Basic case information
        if case.get('victim_name') and case['victim_name'] != 'Unknown':
            report += f"👤 Victim: {case['victim_name']}\n"
        else:
            report += f"👤 Victim: Unknown\n"
            
        if case.get('age'):
            report += f"🎂 Age: {case['age']} years old\n"
        else:
            report += f"🎂 Age: Unknown\n"
            
        if case.get('gender') and case['gender'] != 'unknown':
            report += f"⚧ Gender: {case['gender'].title()}\n"
        else:
            report += f"⚧ Gender: Not specified\n"
            
        if case.get('date'):
            report += f"📅 Date: {case['date']}\n"
        else:
            report += f"📅 Date: Not specified\n"
            
        if case.get('location') and case['location'] != 'unknown location':
            report += f"📍 Location: {case['location'].title()}\n"
        else:
            report += f"📍 Location: Not specified\n"
            
        # Case description
        if case.get('description'):
            report += f"📄 Description: {case['description']}\n"
        else:
            report += f"📄 Description: No details available\n"
            
        report += "\n"
    
    report += f"\n⏰ Summary generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    return report

@mcp.tool()
def check_boston_cases_in_cold_case_db() -> str:
    """Check if Boston Police 2014 unsolved homicide cases appear in the Project Cold Case database."""
    
    checker = ColdCaseCrossChecker()
    
    # Build comprehensive report
    report = "🔍 BOSTON 2014 CASES vs COLD CASE DATABASE CROSS-CHECK\n"
    report += "=" * 70 + "\n\n"
    
    # Scrape Boston Police Cases first (our primary focus)
    report += "📊 STEP 1: Gathering Boston Police 2014 Unsolved Homicides...\n"
    boston_result = checker.scrape_boston_cases()
    report += f"   {boston_result}\n\n"
    
    if not checker.boston_cases:
        report += "❌ CRITICAL ERROR: No Boston 2014 cases found to cross-check.\n"
        return report
    
    # Scrape Cold Case Database
    report += "📊 STEP 2: Searching Cold Case Database for Boston/Massachusetts entries...\n"
    cold_case_result = checker.scrape_cold_case_db()
    report += f"   {cold_case_result}\n\n"
    
    # Enhanced matching with Boston 2014 focus
    report += "🔗 STEP 3: Cross-referencing Boston 2014 cases against cold case database...\n"
    matches = checker.find_enhanced_boston_matches()
    report += f"   Found {len(matches)} potential matches for Boston 2014 cases\n\n"
    
    # Summary statistics with Boston 2014 focus
    report += "📈 BOSTON 2014 CROSS-CHECK RESULTS:\n"
    report += f"   Boston 2014 cases analyzed: {len(checker.boston_cases)}\n"
    report += f"   Cold case database entries found: {len(checker.cold_case_db)}\n"
    report += f"   Potential matches identified: {len(matches)}\n"
    
    if len(checker.boston_cases) > 0:
        match_percentage = (len(matches) / len(checker.boston_cases)) * 100
        report += f"   Boston 2014 cases with potential matches: {match_percentage:.1f}%\n"
    
    report += "\n"
    
    # Detailed match results with enhanced analysis
    if matches:
        report += "🎯 DETAILED BOSTON 2014 MATCH ANALYSIS:\n"
        for i, match in enumerate(matches, 1):
            cold_case = match['cold_case']
            boston_case = match['boston_case']
            
            report += f"\n--- BOSTON 2014 MATCH #{i} (Confidence: {match['match_score']:.2f}) ---\n"
            
            report += f"🚨 BOSTON 2014 CASE:\n"
            report += f"   Victim: {boston_case.get('victim_name', 'Unknown')}\n"
            report += f"   Age: {boston_case.get('age', 'Unknown')}\n"
            report += f"   Gender: {boston_case.get('gender', 'Unknown')}\n"
            report += f"   Date: {boston_case.get('date', 'Unknown')}\n"
            report += f"   Location: {boston_case.get('location', 'Unknown')}\n"
            
            report += f"\n📁 MATCHING COLD CASE ENTRY:\n"
            report += f"   Victim: {cold_case.get('victim_name', 'Unknown')}\n"
            report += f"   Age: {cold_case.get('age', 'Unknown')}\n"
            report += f"   Date: {cold_case.get('date', 'Unknown')}\n"
            report += f"   Location: {cold_case.get('location', 'Unknown')}\n"
            
            report += f"\n✅ MATCH INDICATORS:\n"
            for reason in match['match_reasons']:
                report += f"   • {reason}\n"
            
            # Add match confidence explanation
            if match['match_score'] >= 0.7:
                report += f"   🔥 HIGH CONFIDENCE MATCH - Strong similarity indicators\n"
            elif match['match_score'] >= 0.4:
                report += f"   ⚠️  MODERATE CONFIDENCE - Some matching elements\n"
            else:
                report += f"   ❓ LOW CONFIDENCE - Limited matching data\n"
    else:
        report += "❌ NO MATCHES FOUND BETWEEN BOSTON 2014 CASES AND COLD CASE DATABASE\n"
        report += "\n🔍 ANALYSIS OF NO MATCHES:\n"
        report += "   Possible explanations:\n"
        report += "   • Boston 2014 cases may not be included in this cold case database\n"
        report += "   • Cases may be listed under different victim names or details\n"
        report += "   • Database may focus on older cold cases (pre-2014)\n"
        report += "   • Cases may have been solved and removed from cold case status\n"
        report += "   • Different data formatting preventing automatic matching\n"
    
    report += f"\n⏰ Boston 2014 cross-check completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    return report

# Start MCP server with SSE transport

    # Check if we should run as MCP server or just test functions
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("🧪 Running in test mode...")
        print("\n--- Testing summarize_boston_cases ---")
        try:
            result = summarize_boston_cases()
            print("✅ summarize_boston_cases test completed successfully!")
            print(f"Result length: {len(result)} characters")
        except Exception as e:
            print(f"❌ summarize_boston_cases test failed: {e}")
        
        print("\n--- Testing check_boston_cases_in_cold_case_db ---")
        try:
            result = check_boston_cases_in_cold_case_db()
            print("✅ check_boston_cases_in_cold_case_db test completed successfully!")
            print(f"Result length: {len(result)} characters")
        except Exception as e:
            print(f"❌ check_boston_cases_in_cold_case_db test failed: {e}")
    else:
        # Try to start MCP server with port management
        default_port = 5553
        if not check_port_available(default_port):
            print(f"⚠️ Port {default_port} is already in use, finding alternative...")
            available_port = find_available_port(default_port + 1)
            if available_port:
                print(f"✅ Found available port: {available_port}")
                print(f"⏳ Starting server on port {available_port}...")
                # Note: FastMCP doesn't easily allow port configuration, so we'll provide instructions
                print(f"❌ Cannot automatically change port in FastMCP.")
                print(f"💡 SOLUTIONS:")
                print(f"   1. Stop other MCP servers running on port {default_port}")
                print(f"   2. Run in test mode: python {sys.argv[0]} --test")
                print(f"   3. Use functions directly in Python:")
                print(f"      from cold_case_cross_checker import summarize_boston_cases")
                print(f"      result = summarize_boston_cases()")
                sys.exit(1)
            else:
                print("❌ No available ports found in range 5554-5563")
                print("💡 Please stop other MCP servers or use test mode")
                sys.exit(1)
        else:
            print("⏳ Starting server on default port 5553...")
            try:
                mcp.run(transport="sse")
            except Exception as e:
                print(f"❌ Failed to start MCP server: {e}")
                print("💡 Try running in test mode: python cold_case_cross_checker.py --test")
                sys.exit(1)
def generate_boston_cases_map(cases, filename="boston_cases_map.html"):
    # Center on Boston
    m = folium.Map(location=[42.3601, -71.0589], zoom_start=12)
    for case in cases:
        # Try to geocode or use dummy coordinates if you don't have lat/lon
        # Here, just place all markers at Boston center for demo
        folium.Marker(
            location=[42.3601, -71.0589],
            popup=f"{case.get('victim_name', 'Unknown')}<br>{case.get('date', 'Unknown')}<br>{case.get('location', 'Unknown')}",
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(m)
    m.save(filename)

def create_boston_case_map(boston_cases):
    # Initialize Boston map
    boston_map = folium.Map(location=[42.3601, -71.0589], zoom_start=12)
    marker_cluster = MarkerCluster().add_to(boston_map)

    # Predefined coordinates for Boston neighborhoods
    neighborhood_coords = {
        'dorchester': [42.2931, -71.0706],
        'mattapan': [42.2725, -71.0969],
        'roxbury': [42.3218, -71.0886],
        'south boston': [42.3389, -71.0476],
        'jamaica plain': [42.3097, -71.1151],
        'hyde park': [42.2554, -71.1248],
        'south end': [42.3437, -71.0726],
        'back bay': [42.3503, -71.0809],
        'beacon hill': [42.3584, -71.0707],
        'charlestown': [42.3785, -71.0645],
        'east boston': [42.3751, -71.0392],
        'allston': [42.3538, -71.1312],
        'brighton': [42.3508, -71.1474],
        'west roxbury': [42.2797, -71.1389],
        'roslindale': [42.2876, -71.1294]
    }

    geolocator = GoogleV3(api_key=GOOGLE_API_KEY, timeout=10)

    for case in boston_cases:
        loc = case.get("location", "").strip()
        name = case.get("victim_name", "Unknown")
        date = case.get("date", "Unknown")
        desc = case.get("description", "")
        latlon = None
        
        # Create a cleaner popup with just the essential information
        popup = f"""
        <div style='font-family: Arial, sans-serif; padding: 5px;'>
            <b>Location:</b> {loc}<br>
            <b>Victim:</b> {name}<br>
            <b>Case Date:</b> {date}
        </div>
        """

        # 1. Try to geocode the full address
        if loc and loc.lower() != "unknown location":
            try:
                full_address = f"{loc}, Boston, MA"
                location = geolocator.geocode(full_address)
                if location:
                    latlon = [location.latitude, location.longitude]
                else:
                    # 2. Try to match a neighborhood
                    for neighborhood, coords in neighborhood_coords.items():
                        if neighborhood in loc.lower():
                            latlon = coords
                            break
            except Exception as e:
                # 2. Try to match a neighborhood if geocoding fails
                for neighborhood, coords in neighborhood_coords.items():
                    if neighborhood in loc.lower():
                        latlon = coords
                        break
            time.sleep(0.2)  # Delay to avoid rate limits
        # 3. If still no latlon, use Boston city center
        if not latlon:
            latlon = [42.3601, -71.0589]

        folium.Marker(
            location=latlon,
            popup=popup,
            icon=folium.Icon(color='red', icon='info-sign', prefix='glyphicon')
        ).add_to(marker_cluster)

    # Save to HTML string
    map_html = boston_map._repr_html_()
    return map_html

def generate_html_report(filename="cold_case_report.html"):
    checker = ColdCaseCrossChecker()
    checker.scrape_boston_cases()
    checker.scrape_cold_case_db()
    matches = checker.find_enhanced_boston_matches()
    map_html = create_boston_case_map(checker.boston_cases)

    def html_escape(text):
        return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def format_case(case):
        return f"""
        <strong>Victim:</strong> {html_escape(case.get('victim_name', 'Unknown'))}<br>
        <strong>Age:</strong> {html_escape(str(case.get('age', 'Unknown')))}<br>
        <strong>Gender:</strong> {html_escape(case.get('gender', 'Unknown'))}<br>
        <strong>Date:</strong> {html_escape(case.get('date', 'Unknown'))}<br>
        <strong>Location:</strong> {html_escape(case.get('location', 'Unknown'))}<br>
        <strong>Description:</strong> {html_escape(case.get('description', ''))}
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Boston 2014 Cold Case Information</title>
        <meta charset="UTF-8">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ padding: 20px; }}
            .timeline {{ border-left: 3px solid #ddd; padding-left: 20px; }}
            .timeline-event {{ margin-bottom: 20px; }}
            .match-card {{ background: #f9f9f9; padding: 15px; margin-bottom: 20px; border-radius: 8px; }}
            .map-container {{ height: 600px; width: 100%; }}
        </style>
    </head>
    <body>
        <h1>🕵️ Boston 2014 Cold Case Cross-Check Report</h1>
        <p><em>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>

        <!-- Nav tabs -->
        <ul class="nav nav-tabs" id="reportTabs" role="tablist">
          <li class="nav-item" role="presentation">
            <button class="nav-link active" id="cases-tab" data-bs-toggle="tab" data-bs-target="#cases" type="button" role="tab" aria-controls="cases" aria-selected="true">Boston Cases</button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="matches-tab" data-bs-toggle="tab" data-bs-target="#matches" type="button" role="tab" aria-controls="matches" aria-selected="false">Potential Matches</button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="timeline-tab" data-bs-toggle="tab" data-bs-target="#timeline" type="button" role="tab" aria-controls="timeline" aria-selected="false">Timeline</button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="map-tab" data-bs-toggle="tab" data-bs-target="#map" type="button" role="tab" aria-controls="map" aria-selected="false">🗺 Map</button>
          </li>
        </ul>

        <!-- Tab panes -->
        <div class="tab-content" id="reportTabsContent">
          <div class="tab-pane fade show active" id="cases" role="tabpanel" aria-labelledby="cases-tab">
            <h2 class="mt-3">📋 Boston Unsolved Homicides (2014)</h2>
            <div class="row row-cols-1 row-cols-md-2 g-4">
    """

    # Boston Cases Tab
    for case in checker.boston_cases:
        html += f"""
        <div class="col">
            <div class="card h-100">
                <div class="card-body">
                    {format_case(case)}
                </div>
            </div>
        </div>
        """
    html += "</div></div>"

    # Map Tab
    html += f"""
    <div class="tab-pane fade" id="map" role="tabpanel" aria-labelledby="map-tab">
        <h2 class="mt-3">🗺 Boston Case Map</h2>
        <div class="map-container">
            {map_html}
        </div>
    </div>
    """

    # Potential Matches Tab
    html += """
    <div class="tab-pane fade" id="matches" role="tabpanel" aria-labelledby="matches-tab">
      <h2 class="mt-3">🔗 Potential Matches</h2>
    """
    if matches:
        for i, match in enumerate(matches, 1):
            html += f"""
            <div class="match-card">
                <h5>Match #{i} - Confidence: {match['match_score']:.2f}</h5>
                <p><strong>Boston Case:</strong><br>{format_case(match['boston_case'])}</p>
                <p><strong>Matched Cold Case:</strong><br>{format_case(match['cold_case'])}</p>
                <ul>
            """
            for reason in match['match_reasons']:
                html += f"<li>{html_escape(reason)}</li>"
            html += "</ul></div>"
    else:
        html += "<p>No potential matches found.</p>"
    html += "</div>"

    # Timeline Tab
    html += """
    <div class="tab-pane fade" id="timeline" role="tabpanel" aria-labelledby="timeline-tab">
      <h2 class="mt-3">📅 Timeline of Boston Cases</h2>
      <div class='timeline'>
    """
    sorted_cases = sorted(checker.boston_cases, key=lambda c: checker._extract_year(c.get("date", "")) or 0)
    for case in sorted_cases:
        html += f"""
        <div class="timeline-event">
            <h6>{html_escape(case.get('date', 'Unknown'))} – {html_escape(case.get('victim_name', 'Unknown'))}</h6>
            <p><strong>Location:</strong> {html_escape(case.get('location', 'Unknown'))}</p>
            <p>{html_escape(case.get('description', '')[:200])}...</p>
        </div>
        """
    html += "</div></div></div>"

    # Bootstrap JS for tabs
    html += """
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Report generated: {filename}")
    
if __name__ == "__main__":
    import sys

    args = sys.argv[1:]

    if "--report" in args:
        print("▶️ Generating cold case HTML report...")
        generate_html_report()
        print("✅ HTML report saved as cold_case_report.html")
        sys.exit(0)

    elif "--test" in args:
        print("🧪 Running test tools...")
        result = summarize_boston_cases()
        print(result)
        result = check_boston_cases_in_cold_case_db()
        print(result)
        sys.exit(0)

    else:
        # Default: start the server
        print("🚨 Starting Cold Case Cross Checker MCP Server...")
        print("🔧 Available tools: check_boston_cases_in_cold_case_db, summarize_boston_cases")

        import socket

        def port_available(port):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind(("0.0.0.0", port))
                    return True
            except OSError:
                return False

        if not port_available(5553):
            print("⚠️ Port 5553 is already in use.")
            print("💡 Run this file with:")
            print("   python cold_case_cross_checker.py --report")
            print("   python cold_case_cross_checker.py --test")
            sys.exit(1)

        from mcp.server import FastMCP
        mcp.run(transport="sse")

