#### IMPORTS ####

import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon
import unicodedata
import re
# import matplotlib.colors as mcolors

import streamlit as st
# from streamlit_jupyter import StreamlitJupyter
import leafmap.foliumap as leafmap
from folium.plugins import HeatMap
# import folium
# from folium.plugins import MarkerCluster
# from streamlit_folium import st_folium


##### SET FILE PATHS #####

# path = 'c:\\Users\\john.hazelton\\OneDrive - Cortland\\Documents\\Research & Strategy\\Code\\Steamlit App\\data\costar_denver_deliveries.csv'
# sm_path = 'c:\\Users\\john.hazelton\\OneDrive - Cortland\\Documents\\Research & Strategy\\Code\\Steamlit App\\data\\denver.geojson'
path='data/costar_denver_deliveries.csv'
sm_path = 'data/denver.geojson' 


# @st.experimental_rerun()
# st.rerun()
@st.cache_data


##### LOAD & FORMAT DATA #####


def load_data(path):
    # Load file:
    df = pd.read_csv(path)
    # Group construction years into buckets:
    year_ranges = ['2018-2020','2021-2022','2023-2024','2025-2026','2027-2028']
    df['year_range'] = np.nan
    for yr in year_ranges:
        df['year_range'] = np.where((df['YearBuilt']>=int(yr[:4])) & (df['YearBuilt']<=int(yr[-4:])), yr, df['year_range'])
    df.rename(columns={'YearBuilt':'Year Built / Expected'}, inplace=True)
    return df
df = load_data(path)


##### HEADER & SIDEBAR CONTROLS #####


# Add page header:
st.title("Denver Supply Explorer")

# Add settings control panel to sidebar:
# st.sidebar.title("Controls") 
with st.sidebar.expander(label='Map Settings'):
    heatmap_on = st.toggle("Activate Heatmap", value=True)
    submarket_tiles_on = st.toggle("Activate Submarket Tiles", value=True)
    heatmap_radius = st.slider("Radius", min_value=5, max_value=50, value=15, step=1)
    heatmap_blur = st.slider("Blur", min_value=1, max_value=30, value=7, step=1)

# Create date selector:
st.sidebar.markdown("---")
# st.sidebar.subheader("Filters")
st.sidebar.title("Filters") 
years = sorted(df['year_range'].unique().tolist())
year_select = st.sidebar.multiselect("Years", years, default=['2018-2020'])
df = df[df['year_range'].isin(year_select)]

# Initialize session state defaults for selected submarket:
submarkets = ['All'] + sorted(df['SubmarketName'].unique().tolist())
if 'selected_submarket' not in st.session_state:
    st.session_state.selected_submarket = 'All'

# Create submarket selector (w/ session state bounded to it so when we refresh or select a different date, the selected submarket persists):
selected_submarket = st.sidebar.selectbox("Submarket", options=submarkets, index=submarkets.index(st.session_state.selected_submarket), key='selected_submarket')
# submarket = st.sidebar.selectbox("Submarket", submarkets, default=st.session_state.submarket)  #, index=default_i)



##### CREATE MAP USING LEAFMAP #####



# Adjust default zoom & center of map based on submarket selection(s):
# print(selected_submarket)
if selected_submarket == "All":
    center_lat, center_lon, zoom = 39.7309, -105, 10  # centered on core Denver area
else:
    # Zoom in on the selected submarket:
    df = df[df['SubmarketName'] == selected_submarket]
    center_lat = df['Latitude'].mean()
    center_lon = df['Longitude'].mean()
    zoom = 12
    # rank_to_radius = {1: 30, 2: 20, 3: 15}

# Filter dataset based on selections:
fltr_df = df[df['year_range'].isin(year_select)]

# Create map:
m = leafmap.Map(center=[center_lat, center_lon], zoom=zoom)
# m.add_basemap("CartoDB.Positron")
# m.add_basemap("CartoDB.DarkMatter")
m.add_basemap("CartoDB.Voyager")

# Add Denver submarket polygons as a layer (filtered on selected submarkets):
if submarket_tiles_on:
    denver_gdf = gpd.read_file(sm_path)
    denver_gdf.rename(columns={'SubName':'Submarket','CBSAName':'Market'}, inplace=True)
    denver_gdf = denver_gdf[['Submarket','Market','geometry']]
    # denver_gdf = denver_gdf[denver_gdf['Submarket'].isin(submarkets)]
    if selected_submarket != 'All':
        # Filter the GeoDataFrame based on the selected submarket: 
        print('Selected submarket before tiles:', selected_submarket)
        denver_gdf = denver_gdf[denver_gdf['Submarket'].str.rstrip() == selected_submarket]
        print(len(denver_gdf))
    point_style = {"radius": 2,"weight": 2,"color": 'white',"fillColor": 'blue',"fillOpacity": 0.1}
    # hover_style = {"fillColor": 'red',"fillOpacity": 5,"radius": 10}
    m.add_gdf(denver_gdf, layer_name="Denver Submarkets", zoom_to_layer=False, style=point_style)  # hover_style=hover_style

# # Filter dataset based on selections:
# years_df = df[df['year_range'].isin(year_select)]

# Display heatmap:
if heatmap_on:
    m.add_heatmap(
        data=fltr_df,
        latitude="Latitude",
        longitude="Longitude",
        value="UnitCount",
        radius=heatmap_radius
        # name=f"{manager} Heatmap",
        # blur=heatmap_blur,
        # gradient=gradient
        # gradient={0.5:'cyan', 0.7: 'lime', 0.8:'yellow', 1.0:'red'}
    )

# Plot points with property info in the popup:
m.add_points_from_xy(
    data=fltr_df,
    x='Longitude',
    y='Latitude',
    popup=['PropertyName','ConstructionStatus','Year Built / Expected','UnitCount'],  # this shows on click
    # tooltip=['PropertyName','ConstructionStatus','Year Built / Expected','UnitCount'],  # this shows on hover
    layer_name='Properties',
    clustered=False,
    # show=True,
)
m.to_streamlit(height=700, width=900)



##### DISPLAY DATA AS A TABLE #####


# Filter data table based on selections:
data = []
table_df = fltr_df.groupby(['year_range']).agg({'UnitCount':'sum'}).reset_index().rename(columns={'year_range':'Years', 'UnitCount':'Total Delivered/Expected Units'})
# st.subheader('Entries')
html_table = table_df.to_html(escape=False, index=False)
html_table = html_table.replace(
    "<thead>",
    "<thead><style>th { text-align: center !important; }</style>",
)
st.markdown(html_table, unsafe_allow_html=True)


##### USING FOLIUM DIRECTLY #####

# # Create the map
# m = folium.Map(location=[39.7309, -105], zoom_start=10)

# # Create the cluster group with zoom-level control
# marker_cluster = MarkerCluster(
#     name="Units",
#     disableClusteringAtZoom=12,  # <- This controls when clusters stop
# ).add_to(m)

# # Add markers with unit_count stored in the popup:
# for idx, row in years_df.iterrows():
#     folium.Marker(
#         location=[row['Latitude'], row['Longitude']],
#         popup=f"Unit Count: {row['UnitCount']}"
#     ).add_to(marker_cluster)

# # Add layer control and display
# folium.LayerControl().add_to(m)
# st_folium(m, width=700, height=700)


### TO RUN THE APP IN TERMINAL ###
# streamlit run 'c:/Users/john.hazelton/OneDrive - Cortland/Documents/Research "&" Strategy/Code/Steamlit App/denver_supply_app.py'

### TO SAVE MAP AS HTML FILE ###
# m.to_html('c:\\Users\\john.hazelton\\OneDrive - Cortland\\Documents\\Research & Strategy\\Code\\Steamlit App\\denver_map.html')
