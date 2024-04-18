import streamlit as st
from geopy.geocoders import Nominatim
import geopandas as gpd
from shapely.geometry import Point
from streamlit_folium import folium_static
import folium
from geopy.distance import geodesic

# Initialize the geocoder
geolocator = Nominatim(user_agent="my_geocoder")

# Function to geocode a postal code
def geocode_postal_code(postal_code):
    try:
        location = geolocator.geocode(postal_code)
        return (location.latitude, location.longitude)
    except:
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

# Load your data
shapefile_path = 'Parks_and_Open_Spaces.shp'
parks_data = gpd.read_file(shapefile_path)
parks_data = parks_data.to_crs(epsg=4326)

if st.button('Find Nearest Park'):
    user_lat, user_lon = geocode_postal_code(postal_code)
    if user_lat and user_lon:
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
        st.error("Could not geocode the address. Please try a different one.")