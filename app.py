import streamlit as st
import io
import requests
import pandas as pd
from geopy.geocoders import Nominatim
import geopandas as gpd
from shapely.geometry import shape
from streamlit_folium import folium_static
import folium
from geopy.distance import geodesic
from shapely.geometry import Point


# Initialize the geocoder
geolocator = Nominatim(user_agent="my_geocoder")
api_url = 'https://maps.victoria.ca/server/rest/services/OpenData/OpenData_Parks/MapServer/50/query?outFields=*&where=1%3D1&f=geojson'
# Function to fetch real-time park data from Open Data Victoria's RESTful API
def fetch_park_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        try:
            # Convert bytes to a file-like object
            data = io.BytesIO(response.content)
            # Load GeoJSON directly with geopandas
            gdf = gpd.read_file(data)
            return gdf
        except ValueError as e:
            st.error(f"Error parsing GeoJSON: {e}")
            return gpd.GeoDataFrame()
    else:
        st.error('Failed to retrieve data from the API')
        return gpd.GeoDataFrame()

parks_data = fetch_park_data(api_url)


# Function to geocode a postal code
def geocode_postal_code(postal_code):
    try:
        location = geolocator.geocode(f"{postal_code}, Victoria, BC")  # Specify more context
        if location:
            return (location.latitude, location.longitude)
        else:
            st.error("No location found for this postal code. Please check the format or try a nearby postal code.")
            return None, None
    except Exception as e:
        st.error(f"An error occurred during geocoding: {str(e)}")
        return None, None


# Function to calculate distances and return the closest park
def find_nearest_park(user_location, parks_data):
    # Convert user location to a Shapely Point and set as the geometry
    user_point = Point(user_location[1], user_location[0])
    
    # Calculate the distance from the user to each park
    parks_data['distance'] = parks_data.apply(lambda row: geodesic((row.geometry.centroid.y, row.geometry.centroid.x), user_location).meters, axis=1)
    
    # Find the park with the minimum distance to the user
    nearest_park = parks_data.loc[parks_data['distance'].idxmin()]
    
    return nearest_park, parks_data

# Streamlit app
st.title('Find the Nearest Park to Your Address')

# User input for postal code
postal_code = st.text_input('Enter your postal code')


if st.button('Find Nearest Park'):
    user_lat, user_lon = geocode_postal_code(postal_code)
    if user_lat and user_lon:
        # Call fetch_park_data with the correct parameter
        parks_data = fetch_park_data(api_url)
        if not parks_data.empty:
            user_location = (user_lat, user_lon)
            nearest_park, all_parks_with_distances = find_nearest_park(user_location, parks_data)
            # Show the nearest park details
            st.write(f"The nearest park is: {nearest_park['Park_Name']}")
            st.write(f"Distance: {nearest_park['distance']:.2f} meters")
            
            # Create and display the map
            m = folium.Map(location=user_location, zoom_start=12)
            folium.Marker(user_location, tooltip='Your Location', icon=folium.Icon(color='red')).add_to(m)
            folium.Marker(
                [nearest_park.geometry.centroid.y, nearest_park.geometry.centroid.x],
                tooltip=f"{nearest_park['Park_Name']}",
                icon=folium.Icon(color='green')
            ).add_to(m)
            
            folium_static(m)
        else:
            st.error("Could not retrieve or parse park data.")
    else:
        st.error("Could not geocode the postal code. Please try a different one.")
 
