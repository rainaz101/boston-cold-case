#!/usr/bin/env python3
"""
Visual Map Generator for Boston 2014 Unsolved Homicides
Creates an interactive map showing case locations using Folium
"""

import folium
import pandas as pd
import sys
import os

# Add the current directory to the path so we can import the cold case checker
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cold_case_cross_checker import ColdCaseCrossChecker

def load_case_data():
    """Load Boston Police 2014 case data"""
    print("🔍 Loading Boston Police 2014 unsolved homicide data...")
    
    checker = ColdCaseCrossChecker()
    result = checker.scrape_boston_cases()
    print(f"📊 {result}")
    
    if not checker.boston_cases:
        print("❌ No case data available for mapping")
        return None
    
    # Convert to DataFrame for easier processing
    cases_data = []
    for i, case in enumerate(checker.boston_cases, 1):
        cases_data.append({
            'Case_Number': i,
            'Victim': case.get('victim_name', 'Unknown'),
            'Age': case.get('age', 'Unknown'),
            'Gender': case.get('gender', 'Unknown'),
            'Date': case.get('date', 'Unknown'),
            'Location': case.get('location', 'Unknown'),
            'Description': case.get('description', 'No description available')
        })
    
    df = pd.DataFrame(cases_data)
    print(f"✅ Loaded {len(df)} cases for mapping")
    return df

def geocode_locations(data):
    """Add latitude and longitude coordinates to case data"""
    print("🌍 Geocoding case locations...")
    
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderServiceError
        import time
        
        geolocator = Nominatim(user_agent="boston_crime_mapper", timeout=10)
        
        latitudes = []
        longitudes = []
        
        for index, row in data.iterrows():
            location = row['Location']
            
            if location == 'Unknown' or location == 'unknown location':
                latitudes.append(None)
                longitudes.append(None)
                continue
            
            try:
                # Add Boston, MA to improve geocoding accuracy
                full_address = f"{location}, Boston, MA"
                print(f"  Geocoding: {full_address}")
                
                # Add delay to avoid rate limiting
                time.sleep(1)
                
                location_data = geolocator.geocode(full_address)
                
                if location_data:
                    latitudes.append(location_data.latitude)
                    longitudes.append(location_data.longitude)
                    print(f"    ✅ Found coordinates: {location_data.latitude}, {location_data.longitude}")
                else:
                    # Try without Boston, MA if first attempt fails
                    location_data = geolocator.geocode(location)
                    if location_data:
                        latitudes.append(location_data.latitude)
                        longitudes.append(location_data.longitude)
                        print(f"    ✅ Found coordinates: {location_data.latitude}, {location_data.longitude}")
                    else:
                        latitudes.append(None)
                        longitudes.append(None)
                        print(f"    ❌ Could not geocode: {location}")
                        
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                print(f"    ⚠️ Geocoding error for {location}: {e}")
                latitudes.append(None)
                longitudes.append(None)
            except Exception as e:
                print(f"    ❌ Unexpected error for {location}: {e}")
                latitudes.append(None)
                longitudes.append(None)
        
        data['Latitude'] = latitudes
        data['Longitude'] = longitudes
        
        # Count successful geocoding
        successful_geocodes = data.dropna(subset=['Latitude', 'Longitude'])
        print(f"📍 Successfully geocoded {len(successful_geocodes)} out of {len(data)} locations")
        
        return data
        
    except ImportError:
        print("❌ geopy not installed. Please run: pip install geopy")
        return None
    except Exception as e:
        print(f"❌ Error during geocoding: {e}")
        return None

def create_interactive_map(data):
    """Create an interactive Folium map with case markers"""
    print("🗺️ Creating interactive map...")
    
    # Filter data to only include cases with valid coordinates
    valid_data = data.dropna(subset=['Latitude', 'Longitude'])
    
    if len(valid_data) == 0:
        print("❌ No valid coordinates available for mapping")
        return None
    
    # Calculate the center point for the map
    avg_lat = valid_data['Latitude'].mean()
    avg_lng = valid_data['Longitude'].mean()
    
    print(f"📍 Map center: {avg_lat:.4f}, {avg_lng:.4f}")
    
    # Create the base map centered on Boston
    m = folium.Map(
        location=[avg_lat, avg_lng], 
        zoom_start=12,
        tiles='OpenStreetMap'
    )
    
    # Add markers for each case
    for _, row in valid_data.iterrows():
        # Create popup content with case details
        popup_content = f"""
        <div style="width: 300px;">
            <h4>Case #{row['Case_Number']}</h4>
            <p><strong>Victim:</strong> {row['Victim']}</p>
            <p><strong>Age:</strong> {row['Age']}</p>
            <p><strong>Gender:</strong> {row['Gender']}</p>
            <p><strong>Date:</strong> {row['Date']}</p>
            <p><strong>Location:</strong> {row['Location']}</p>
            <p><strong>Description:</strong> {row['Description'][:100]}{'...' if len(str(row['Description'])) > 100 else ''}</p>
        </div>
        """
        
        # Add marker to map
        folium.Marker(
            location=[row['Latitude'], row['Longitude']],
            popup=folium.Popup(popup_content, max_width=350),
            tooltip=f"Case #{row['Case_Number']}: {row['Victim']}",
            icon=folium.Icon(color='red', icon='exclamation-sign', prefix='glyphicon')
        ).add_to(m)
    
    # Add a title to the map
    title_html = '''
                 <h3 align="center" style="font-size:20px"><b>Boston Police 2014 Unsolved Homicides</b></h3>
                 <p align="center" style="font-size:14px">Interactive map showing locations of unsolved homicide cases</p>
                 '''
    m.get_root().html.add_child(folium.Element(title_html))
    
    print(f"✅ Created map with {len(valid_data)} case markers")
    return m

def save_map(map_object, filename='boston_unsolved_homicides_2014.html'):
    """Save the map to an HTML file"""
    if map_object is None:
        print("❌ No map to save")
        return False
    
    try:
        map_object.save(filename)
        print(f"💾 Map saved as: {filename}")
        print(f"🌐 Open {filename} in your web browser to view the interactive map")
        return True
    except Exception as e:
        print(f"❌ Error saving map: {e}")
        return False

def generate_summary_report(data):
    """Generate a summary report of the mapping results"""
    if data is None or len(data) == 0:
        return
    
    print("\n📊 MAPPING SUMMARY REPORT")
    print("=" * 50)
    
    total_cases = len(data)
    geocoded_cases = len(data.dropna(subset=['Latitude', 'Longitude']))
    geocoding_rate = (geocoded_cases / total_cases * 100) if total_cases > 0 else 0
    
    print(f"Total cases: {total_cases}")
    print(f"Successfully geocoded: {geocoded_cases}")
    print(f"Geocoding success rate: {geocoding_rate:.1f}%")
    print(f"Cases without coordinates: {total_cases - geocoded_cases}")
    
    if geocoded_cases > 0:
        print(f"\n📍 Geographic coverage:")
        print(f"Latitude range: {data['Latitude'].min():.4f} to {data['Latitude'].max():.4f}")
        print(f"Longitude range: {data['Longitude'].min():.4f} to {data['Longitude'].max():.4f}")
    
    # Location analysis
    location_counts = data['Location'].value_counts()
    print(f"\n🏘️ Most common locations:")
    for location, count in location_counts.head(5).items():
        if location not in ['Unknown', 'unknown location']:
            print(f"  • {location}: {count} case(s)")

def main():
    """Main function to create the Boston crime map"""
    print("🗺️ BOSTON 2014 UNSOLVED HOMICIDES INTERACTIVE MAP GENERATOR")
    print("=" * 70)
    print("This tool creates an interactive map of Boston Police 2014 unsolved homicide cases")
    print()
    
    try:
        # Step 1: Load case data
        case_data = load_case_data()
        if case_data is None:
            return
        
        # Step 2: Geocode locations
        geocoded_data = geocode_locations(case_data)
        if geocoded_data is None:
            return
        
        # Step 3: Create interactive map
        crime_map = create_interactive_map(geocoded_data)
        if crime_map is None:
            return
        
        # Step 4: Save map
        success = save_map(crime_map)
        if not success:
            return
        
        # Step 5: Generate summary report
        generate_summary_report(geocoded_data)
        
        print("\n✅ Map generation completed successfully!")
        print("🌐 Open 'boston_unsolved_homicides_2014.html' in your web browser to view the map")
        
    except KeyboardInterrupt:
        print("\n⚠️ Map generation interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during map generation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
