import requests
from bs4 import BeautifulSoup
import pandas as pd

# URL of the Boston Police Department's 2014 Unsolved Homicides page
url = 'https://police.boston.gov/2014-unsolved-homicides/'

# Fetch the page content
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

# Initialize lists to store extracted data
victim_names = []
incident_dates = []
incident_addresses = []

# Find all elements that contain victim information
# Note: The actual HTML structure may vary; adjust selectors accordingly
entries = soup.find_all('p')  # Assuming each entry is within a <p> tag

for entry in entries:
    text = entry.get_text(strip=True)
    if text:
        # Simple heuristic to separate name, date, and address
        parts = text.split('\n')
        if len(parts) >= 3:
            victim_names.append(parts[0])
            incident_dates.append(parts[1])
            incident_addresses.append(parts[2])

# Create a DataFrame
data = pd.DataFrame({
    'Victim': victim_names,
    'Date': incident_dates,
    'Address': incident_addresses
})

# Preview the data
print(data.head())
