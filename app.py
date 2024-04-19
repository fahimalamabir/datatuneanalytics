import streamlit as st
import io
import requests
import folium
from streamlit_folium import folium_static
import pandas as pd
from geopy.geocoders import Nominatim
import geopandas as gpd
from shapely.geometry import Point
from geopy.distance import geodesic
from opencage.geocoder import OpenCageGeocode
import os
import openrouteservice
from openrouteservice import convert
from dotenv import load_dotenv
load_dotenv()

st.title('Victoria Parks and Routes Explorer')
tab1, tab2 = st.tabs(["Parks Overview", "Find Nearest Park"])


# Initialize the geocoder with Nominatim and OpenCage
geolocator = Nominatim(user_agent="my_geocoder")
API_KEY = os.getenv("API_KEY")
geolocator_oc = OpenCageGeocode(API_KEY)
api_url = 'https://maps.victoria.ca/server/rest/services/OpenData/OpenData_Parks/MapServer/50/query?outFields=*&where=1%3D1&f=geojson'

# Function to fetch park data
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




def get_route(start_coords, end_coords, profile='foot-walking'):
    client = openrouteservice.Client(key=os.getenv("ORS_API_KEY"))
    try:
        routes = client.directions(
            coordinates=[start_coords[::-1], end_coords[::-1]],  # Ensure [lon, lat] format
            profile=profile,
            format='geojson'
        )
        # Extract duration in minutes
        duration = routes['features'][0]['properties']['segments'][0]['duration'] / 60  # Duration in minutes
        return routes, duration
    except Exception as e:
        st.error(f"Failed to get route: {e}")
        return None, None



# Function to geocode postal code using OpenCage
def geocode_postal_code(postal_code):
    try:
        query = f"{postal_code}, Victoria, BC"
        results = geolocator_oc.geocode(query)
        if results:
            location = results[0]  # Taking the first result
            return (location['geometry']['lat'], location['geometry']['lng'])
        else:
            st.error("No location found for this postal code. Please check the format or try a nearby postal code.")
            return None, None
    except Exception as e:
        st.error(f"An error occurred during geocoding: {str(e)}")
        return None, None

with tab1:
    st.header("Parks and Open Spaces Overview")
    shapefile_path = 'Parks_and_Open_Spaces.shp'
    parks_data1 = gpd.read_file(shapefile_path)

    parks_data1 = parks_data1.to_crs(epsg=4326)
    parks_map = folium.Map(location=[48.4284, -123.3656], zoom_start=13)
    
    for _, row in parks_data1.iterrows():
        # Simplify geometry to make the map load faster, if necessary
        simplified_geom = row['geometry'].simplify(tolerance=0.001, preserve_topology=True)

        # Popup content
        popup_content = f"""
        <strong>OBJECTID:</strong> {row['OBJECTID']}<br>
        <strong>Park Name:</strong> {row['Park_Name']}<br>
        <strong>Alias Name:</strong> {row['Alias_Name']}<br>
        <strong>Park Class Code:</strong> {row['ParkClassC']}<br>
        <strong>Ball Diamond:</strong> {row['BallDiamon']}<br>
        <strong>Concession:</strong> {row['Concession']}<br>
        <strong>Dogs Off Leash:</strong> {row['DogsOffLea']}<br>
        <strong>Horticultural Interest:</strong> {row['Horticultu']}<br>
        <strong>Lawn Bowling:</strong> {row['LawnBowlin']}<br>
        <strong>Picnic Shelter:</strong> {row['PicnicShel']}<br>
        <strong>Play Equipment:</strong> {row['PlayEquipm']}<br>
        <strong>Sport Field:</strong> {row['SportField']}<br>
        <strong>Tennis Court:</strong> {row['TennisCour']}<br>
        <strong>Trail:</strong> {row['Trail']}<br>
        <strong>Washroom:</strong> {row['Washroom']}<br>
        <strong>Water View:</strong> {row['WaterView']}<br>
        <strong>SHAPE Length:</strong> {row['SHAPE_Leng']:.2f} meters<br>
        <strong>SHAPE Area:</strong> {row['SHAPE_Area']:.2f} square meters
        """


        # Create a popup object
        popup = folium.Popup(folium.Html(popup_content, script=True), max_width=300)

        # Create a folium polygon for each park and add to the map
        folium.GeoJson(simplified_geom,
                       style_function=lambda x: {'fillColor': 'green'},
                       popup=popup).add_to(parks_map)

    folium_static(parks_map)


# Function to find the nearest park
def find_nearest_park(user_location, parks_data):
    try:
        user_point = Point(user_location[1], user_location[0])  # Point expects (x, y)
        parks_data['distance'] = parks_data.apply(
            lambda row: geodesic(
                (row.geometry.centroid.y, row.geometry.centroid.x),
                (user_point.y, user_point.x)
            ).meters, axis=1
        )
        nearest_park = parks_data.loc[parks_data['distance'].idxmin()]
        return nearest_park, parks_data
    except Exception as e:
        st.error(f"Error calculating distances: {str(e)}")
        return None, None
with tab2:
    postal_code = st.text_input('Enter your postal code')
    mode = st.radio("Choose your mode of transportation:", ('Driving', 'Walking'))
    if mode == 'Driving':
        profile = 'driving-car'
    else:
        profile = 'foot-walking'
        
    if st.button('Find Nearest Park'):
        geocode_result = geocode_postal_code(postal_code)
        if geocode_result:
            user_lat, user_lon = geocode_result
            if user_lat is not None and user_lon is not None:
                user_location = (user_lat, user_lon)
                parks_data = fetch_park_data(api_url)
                if not parks_data.empty:
                    nearest_park, all_parks_with_distances = find_nearest_park(user_location, parks_data)
                    if nearest_park is not None:
                        park_location = (nearest_park.geometry.centroid.y, nearest_park.geometry.centroid.x)
                        route, duration = get_route(user_location, park_location, profile)
                        if route:
                            # Map and route display
                            m = folium.Map(location=[user_lat, user_lon], zoom_start=12)
                            folium.Marker([user_lat, user_lon], tooltip='Your Location', icon=folium.Icon(color='red')).add_to(m)
                            folium.Marker(
                                [park_location[0], park_location[1]],
                                tooltip=f"{nearest_park['Park_Name']}",
                                icon=folium.Icon(color='green')
                            ).add_to(m)
                            folium.GeoJson(route, name='Route').add_to(m)
                            folium.LayerControl().add_to(m)
                            folium_static(m)

                            # Display park and route information
                            st.write(f"The nearest park is: {nearest_park['Park_Name']}")
                            st.write(f"Distance: {nearest_park['distance']:.2f} meters")
                            st.write(f"Estimated travel time by {mode}: {duration:.1f} minutes")
                        else:
                            st.error("Could not retrieve route.")
                    else:
                        st.error("Could not retrieve or parse park data.")
                else:
                    st.error("Park data is empty.")
            else:
                st.error("Invalid coordinates received from geocoding.")
        else:
            st.error("Could not geocode the postal code.")
