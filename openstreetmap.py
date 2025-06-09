from geopy.geocoders import Nominatim
from time import sleep
import pandas as pd

# Example data
data = pd.DataFrame({
    'Victim': ['John Doe', 'Jane Smith'],
    'Date': ['January 2, 2014', 'February 10, 2014'],
    'Address': ['123 Main St', '456 Elm St']
})

# Add "Boston, MA" to help geocoding
data['Full_Address'] = data['Address'] + ', Boston, MA'

# Initialize geocoder
geolocator = Nominatim(user_agent="boston-cold-cases")

# Geocode function
def geocode_address(address):
    try:
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        else:
            return None, None
    except Exception as e:
        print(f"Error: {e}")
        return None, None

# Apply geocoding
latitudes = []
longitudes = []

for addr in data['Full_Address']:
    lat, lon = geocode_address(addr)
    latitudes.append(lat)
    longitudes.append(lon)
    sleep(1)  # Respect Nominatim's rate limit

data['Latitude'] = latitudes
data['Longitude'] = longitudes

print(data)
