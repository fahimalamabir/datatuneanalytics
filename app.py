import streamlit as st
import io
import requests
import folium
from streamlit_folium import folium_static
import pandas as pd
import matplotlib.pyplot as plt
from geopy.geocoders import Nominatim
import geopandas as gpd
from shapely.geometry import Point
from geopy.distance import geodesic
from opencage.geocoder import OpenCageGeocode
import os
import openrouteservice
from openrouteservice import convert
from dotenv import load_dotenv
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px

load_dotenv()

st.title('Victoria Parks and Routes Explorer')
with st.sidebar:
    st.header('Navigation')
    selected_tab = st.radio('Select a view:', ['Parks Overview', 'Find Nearest Park', 'Park Size Distribution','Amenities Analysis'])

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
    
def amenities_analysis(parks_data):
    amenities_cols = ['BallDiamon', 'Concession', 'DogsOffLea', 'Horticultu',
                      'LawnBowlin', 'PicnicShel', 'PlayEquipm', 'SportField',
                      'TennisCour', 'Trail', 'Washroom', 'WaterView']
    
    # Create a count dictionary for each amenity
    amenities_count = {amenity: parks_data[amenity].value_counts().get('Yes', 0) for amenity in amenities_cols}

    # Convert to DataFrame for visualization
    amenities_df = pd.DataFrame(list(amenities_count.items()), columns=['Amenity', 'Count']).sort_values('Count', ascending=False)
    
    # Plotting
    plt.figure(figsize=(10, 6))
    sns.barplot(data=amenities_df, x='Count', y='Amenity', palette='viridian')
    plt.title('Count of Amenities in Parks')
    plt.xlabel('Count')
    plt.ylabel('Amenity')
    plt.tight_layout()

    return plt

# Function to integrate the amenities analysis into the Streamlit app
amenities_cols = [
    'BallDiamond', 'Concession', 'DogsOffLeash', 'HorticulturalInterest',
    'LawnBowling', 'PicnicShelter', 'PlayEquipment', 'SportField',
    'TennisCourt', 'Trail', 'Washroom', 'WaterView'
]

def amenities_analysis(parks_data):
    # Create a count dictionary for each amenity
    amenities_count = {amenity: parks_data[amenity].value_counts().get('Yes', 0) for amenity in amenities_cols}

    # Convert to DataFrame for visualization
    amenities_df = pd.DataFrame(list(amenities_count.items()), columns=['Amenity', 'Count']).sort_values('Count', ascending=False)
    
    # Plotting
    plt.figure(figsize=(10, 6))
    sns.barplot(data=amenities_df, x='Count', y='Amenity', palette='viridis')
    plt.title('Count of Amenities in Parks')
    plt.xlabel('Count')
    plt.ylabel('Amenity')
    plt.tight_layout()
    

    return plt

if selected_tab == 'Parks Overview':
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

elif selected_tab == 'Find Nearest Park':
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
                            st.write(f"The nearest park is: {nearest_park['Park_Name']}")
                            st.write(f"Distance: {nearest_park['distance']:.2f} meters")
                            st.write(f"Estimated travel time by {mode}: {duration:.1f} minutes")
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
elif selected_tab == 'Park Size Distribution':
    st.header("Park Size Distribution Analysis")
    if 'SHAPE_Area' in parks_data.columns:
        # For the histogram
        st.write("### Histogram of Park Sizes")
        fig_hist, ax_hist = plt.subplots()
        parks_data['SHAPE_Area'].plot(kind='hist', bins=30, ax=ax_hist, color='skyblue')
        ax_hist.set_title('Distribution of Park Sizes')
        ax_hist.set_xlabel('Area (square units)')
        ax_hist.set_ylabel('Frequency')
        st.pyplot(fig_hist)

        # Text below histogram
        st.write("""
        There's a large spike in the first bin, indicating that a majority of the parks are small in size. 
        The distribution is heavily right-skewed, meaning there are fewer large parks.
        """)

        # For the boxplot
        st.write("### Boxplot of Park Sizes")
        fig_box, ax_box = plt.subplots()
        parks_data['SHAPE_Area'].plot(kind='box', ax=ax_box, vert=False, color='green')
        ax_box.set_title('Boxplot of Park Sizes')
        ax_box.set_xlabel('Area (square units)')
        st.pyplot(fig_box)

        # Text below boxplot
        st.write("""
        The boxplot shows that the median park size is quite low compared to the mean, and there are a few parks 
        that are significantly larger than the rest, as indicated by the points far to the right (outliers).
        """)

    else:
        st.error("SHAPE_Area column is missing from the data")

elif selected_tab == 'Amenities Analysis':
    # Call the amenities analysis function and store the returned figure
    fig = amenities_analysis(parks_data)
    st.pyplot(fig)

    for col in parks_data.columns[2:]:
        parks_data[col] = parks_data[col].apply(lambda x: 1 if x == 'Yes' else 0)

    # Prepare data for Sunburst Chart
    sunburst_data = parks_data.melt(id_vars=['Park_Name', 'ParkClassCode'], var_name='Amenity', value_name='Available')
    sunburst_data = sunburst_data[sunburst_data['Available'] == 1]

    fig_sunburst = px.sunburst(
        sunburst_data,
        path=['ParkClassCode', 'Park_Name', 'Amenity'],
        title="Distribution of Amenities by Park and Class (click on segments for details)"
    )

    # Update layout settings to adjust margins and title position
    fig_sunburst.update_layout(
        height=1000,
        title=dict(
            text="Distribution of Amenities by Park and Class (click on segments for details)",
            y=0.9,  # Adjust the y-position of the title
            x=0.5,  # Center the title
            xanchor='center',
            yanchor='top'
        )
    )
    st.plotly_chart(fig_sunburst, use_container_width=True)

    fig_sunburst.add_annotation(
        text="Click on a segment to explore!",
        xref="paper", yref="paper",
        x=0.5, y=1.2,  # Adjust these coordinates to position the annotation
        showarrow=False,
        font=dict(size=16, color="red"),
        align="center"
    )

    # Adjust plot layout after adding annotations
    fig_sunburst.update_layout(
        height=1000,
        margin=dict(t=100, l=0, r=0, b=0)  # Increase the top margin if necessary
    )

