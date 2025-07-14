#### IMPORTS ####

import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon, Point
import unicodedata
import re
import streamlit as st
import leafmap.foliumap as leafmap
from folium.plugins import HeatMap
import folium
# from folium.plugins import MarkerCluster
from streamlit_folium import st_folium # type:ignore
import matplotlib.pyplot as plt


##### SET FILE PATHS & CONSTANTS #####

# path = 'c:\\Users\\john.hazelton\\OneDrive - Cortland\\Documents\\Research & Strategy\\Code\\Steamlit App\\data\costar_denver_property_construction.csv'
# sm_path = 'c:\\Users\\john.hazelton\\OneDrive - Cortland\\Documents\\Research & Strategy\\Code\\Steamlit App\\data\costar_denver_submarket_demand_supply.csv'
# geo_path = 'c:\\Users\\john.hazelton\\OneDrive - Cortland\\Documents\\Research & Strategy\\Code\\Steamlit App\\data\\denver.geojson'
path= 'data/costar_denver_property_construction.csv'
sm_path = 'data/costar_denver_submarket_demand_supply.csv'
geo_path = 'data/denver.geojson' 


# @st.experimental_rerun()
# st.rerun()
# @st.cache_data

# Initialize session state for filters
if 'data_type' not in st.session_state:
    st.session_state.data_type = 'Construction Starts'
if 'date_ranges' not in st.session_state:
    st.session_state.date_ranges = ['2018-2020', '2021-2022', '2023-2024', '2025-2026', '2027-2028']
if 'submarket' not in st.session_state:
    st.session_state.submarket = 'All'



##### DEFINE FUNCTIONS TO LOAD, FORMAT, & FILTER DATA #####


def load_data():    
    # Load property construction data:
    df = pd.read_csv(path)

    # Load submarket demand vs supply data:
    ratio_df = pd.read_csv(sm_path)

    # Load submarket GeoDataFrame:
    submarket_gdf = gpd.read_file(geo_path)
    submarket_gdf.rename(columns={'SubName':'Submarket','CBSAName':'Market'}, inplace=True)
    submarket_gdf = submarket_gdf[['Submarket','Market','geometry']]
    submarket_gdf['Submarket'] = submarket_gdf['Submarket'].str.rstrip()

    return df, ratio_df, submarket_gdf


def filter_property_data(df, data_type, date_ranges, submarket):
    """Filter property data based on user selections"""
    filtered_df = df.copy()
    # Filter by date ranges:
    if data_type == 'Construction Starts':
        filtered_df = filtered_df[filtered_df['Start_year_range'].isin(date_ranges)]
    elif data_type == 'Construction Deliveries':
        filtered_df = filtered_df[filtered_df['Completion_year_range'].isin(date_ranges)]
    # Filter by submarket
    if submarket != 'All':
        filtered_df = filtered_df[filtered_df['SubmarketName'] == submarket]
    
    return filtered_df


def filter_ratio_data(df, date_ranges, submarket):
    """Filter ratio data based on user selections"""
    # Filter by date ranges:
    filtered_df = df[df['year_range'].isin(date_ranges)]
    # Filter by submarket:
    if submarket != 'All':
        filtered_df = filtered_df[filtered_df['SubmarketName'] == submarket]
    # Average ratios across all selected date ranges for the given submarket(s):
    grouped_df = filtered_df.groupby(['SubmarketName']).agg({'Demand':'sum','Supply':'sum'}).reset_index()
    grouped_df['demand_supply_ratio'] = np.where(grouped_df['Supply']>0, grouped_df['Demand']/grouped_df['Supply'], 1)
    
    return grouped_df


def filter_submarket_gdf(gdf, submarket):
    """Filter submarket geodataframe based on selected submarket"""
    if submarket == 'All':
        return gdf
    else:
        return gdf[gdf['Submarket'] == submarket]
    
    



##### DEFINE MAPPING FUNCTIONS #####



def get_map_center(submarket_gdf, submarket):
    """Get center coordinates for the map based on selected submarket"""
    # Default Denver center
    default_lat, default_lon, default_zoom = 39.7309, -105, 10   #39.7392, -104.9903
    
    if submarket == 'All':
        # If showing all submarkets, use overall Denver center:
        return default_lat, default_lon, default_zoom
    else:
        # Center on selected submarket polygon:
        if not submarket_gdf.empty:
            centroid = submarket_gdf['geometry'].iloc[0].centroid
            return centroid.y, centroid.x, 12
        # if not property_df.empty:
        #     lat, lng, zoom = property_df['Latitude'].mean(), property_df['Longitude'].mean(), 12
        #     return lat, lng, zoom
        else:
            # Fallback to defaults
            return default_lat, default_lon, 10


def create_color_scale(values, colormap='RdYlBu_r'):
    """Create color scale for values (blue for low, red for high)"""
    if len(values) == 0:
        return []
    
    min_val = min(values)
    max_val = max(values)
    
    if min_val == max_val:
        return ["#696969"] * len(values)
    
    # Normalize values to 0-1 range:
    normalized = [(v - min_val) / (max_val - min_val) for v in values]
    
    # Create color mapping (blue to red):
    cmap = plt.cm.get_cmap(colormap)
    colors = cmap(normalized)
    hex_colors = ['#{:02x}{:02x}{:02x}'.format(int(c[0]*255), int(c[1]*255), int(c[2]*255)) for c in colors]
    
    return hex_colors


def create_property_map(property_df, submarket_gdf, data_type, selected_submarket, unit_ratio):
    """Create folium map with property points and heatmap"""
    # Get center coordinates based on selected submarket:
    center_lat, center_lon, zoom_level = get_map_center(submarket_gdf,selected_submarket)
    
    m = folium.Map(
        location=[center_lat, center_lon], 
        zoom_start=zoom_level,
        tiles='CartoDB.Voyager',
    )
    
    # Add submarket polygons (light blue, transparent):
    if st.session_state.tiles:
        if not submarket_gdf.empty and submarket_gdf['geometry'].notna().any():
            # for idx, row in submarket_gdf.iterrows():
                # if row['geometry'] is not None:
            folium.GeoJson(
                submarket_gdf,  # row['geometry'],
                style_function=lambda x: {
                    'fillColor': 'blue',  #'#ADD8E6',
                    'color': 'white',  #'#4169E1'
                    'fillColor': 'blue',
                    'weight': 2,
                    'fillOpacity': 0.1
                },
                highlight_function= lambda x: {
                    'fillColor': 'blue',  # Change fill color to blue on hover
                    'color': 'white',      # Keep border color white
                    'weight': 5,           # Make border thicker on hover
                    'fillOpacity': 0     # Make fully transparent on hover (no fill color)
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['Submarket'], # Show submarket name on hover
                    aliases=['Submarket:'],
                    localize=True
                )
            ).add_to(m)
    
    # Add property coordinate points:
    if not property_df.empty:
        # Convert property DataFrame to GeoDataFrame for efficiently display all property points:
        property_gdf = gpd.GeoDataFrame(property_df, geometry=[Point(xy) for xy in zip(property_df['Longitude'], property_df['Latitude'])],crs='EPSG:4326')

        # Add property points as a GeoJson layer:
        folium.GeoJson(
            property_gdf,
            marker=folium.CircleMarker(
                radius=5, 
                weight=1.5, 
                fill=True,
                fillColor='#1e90ff',  # DodgerBlue
                fillOpacity=0.7,  #0.7
                color='white'
            ),
            highlight_function=lambda x: {
                'radius': 5,  #7
                'weight': 1.5,  #2,
                'fillColor': '#1e90ff',  # DodgerBlue
                'color': 'white',
                'fillOpacity': 1,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['PropertyName','UnitCount','SubmarketName'],
                aliases=['Property:','Units:','Submarket:'],
                localize=True,
                style=("background-color:#303030; border-color:black; color:white; font-size:14px; text-align:left;")
            )
        ).add_to(m)
        
        # Create heatmap data:
        if st.session_state.heatmap:
            heat_data = []
            if not property_df.empty:
                total_units = property_df['UnitCount'].sum()
            for idx, row in property_df.iterrows():
                unit_share = row['UnitCount'] / total_units if total_units > 0 else 0
                heat_data.append([row['Latitude'], row['Longitude'], unit_share])
            # Adjust gradient to ensure consistent scaling across maps (in down years, we limit the max "heat" of the map based on the ratio of units to that selected submarket(s) avg across time):
            gradient = {
                0.0: 'blue',
                0.2: 'lightblue',
                0.4: 'cyan',
                0.6: 'yellow',
                0.8: 'orange',
                1.0: 'red'
            }
            # If unit_ratio is less than 1, we scale down the max value to prevent overemphasis of heat:
            if unit_ratio < 1:
                # Scale down the gradient max value based on unit_ratio:
                gradient = {k: v for k, v in gradient.items() if k <= unit_ratio}
            # Adjust the max_val to match the new gradient:
            max_val = max(gradient.keys())  #* unit_ratio

            # Add heatmap layer
            if heat_data:
                HeatMap(
                    heat_data,
                    gradient=gradient,
                    min_opacity=0.5,  #0.2,
                    max_zoom=15,
                    radius=20,
                    blur=10,
                    max_val=max_val
                ).add_to(m)
    
    return m


def create_ratio_map(ratio_df, submarket_gdf, selected_submarket):
    """Create folium map with submarket polygons colored by ratio"""
    # Get center coordinates based on selected submarket:
    center_lat, center_lon, zoom_level = get_map_center(submarket_gdf,selected_submarket)
    
    m = folium.Map( 
        location=[center_lat, center_lon], 
        zoom_start=zoom_level,
        tiles='CartoDB.Voyager'
    )
    
    # Add shaded submarket polygons/tiles:
    if not ratio_df.empty and not submarket_gdf.empty:
        # Merge ratio data with submarket geodataframe:
        merged_gdf = submarket_gdf.merge(ratio_df, left_on='Submarket', right_on='SubmarketName', how='left')
        merged_gdf['demand_supply_ratio'] = np.where(merged_gdf['demand_supply_ratio'].isna(), 1, merged_gdf['demand_supply_ratio'])  
        if not merged_gdf.empty:
            # Create color scale for ratios:
            ratios = merged_gdf['demand_supply_ratio'].tolist()
            colors = create_color_scale(ratios)
            merged_gdf['color'] = colors
            
            # Add colored submarket polygons:
            folium.GeoJson(
                merged_gdf,
                style_function=lambda x: {
                    'fillColor': x['properties']['color'],
                    'color': 'white',
                    'weight': 2,
                    'fillOpacity': 0.6
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['Submarket', 'demand_supply_ratio'],
                    aliases=['Submarket:', 'Ratio:'],
                    localize=True,
                    style=("background-color:#303030; border-color:black; color:white; font-size:14px; text-align:left;")
                )
            ).add_to(m)
    
    return m



##### RUN THE MAIN APP #####


def main():
    st.title("Denver Supply Analysis")
    
    # Load data:
    property_df, ratio_df, submarket_gdf = load_data()
    
    # Top filter for data type:
    data_type = st.selectbox(
        label="Select Data to Display:",
        options=['Construction Starts', 'Construction Deliveries', 'Demand vs Supply Ratio'],
        key='data_type_select',
        index=['Construction Starts', 'Construction Deliveries', 'Demand vs Supply Ratio'].index(st.session_state.data_type)
    )
    
    # Update session state
    st.session_state.data_type = data_type

    # Create sidebar control panel for settings & filters:
    with st.sidebar.expander(label='Map Settings'):
        heatmap_on = st.toggle("Activate Heatmap", value=True)
        submarket_tiles_on = st.toggle("Activate Submarket Tiles", value=True)
        # heatmap_radius = st.slider("Radius", min_value=5, max_value=50, value=15, step=1)
        # heatmap_blur = st.slider("Blur", min_value=1, max_value=30, value=7, step=1)
    # Update session states:
    st.session_state.heatmap = True if heatmap_on else False
    st.session_state.tiles = True if submarket_tiles_on else False

    st.sidebar.markdown("---")
    st.sidebar.title("Filters") 

    # Date range multiselect:
    available_date_ranges = ['2018-2020', '2021-2022', '2023-2024', '2025-2026', '2027-2028']
    selected_date_ranges = st.sidebar.multiselect(
        label="Select Date Ranges:",
        options=available_date_ranges,
        default=st.session_state.date_ranges,
        key='date_ranges_select'
    )
    # Update session state:
    st.session_state.date_ranges = selected_date_ranges if selected_date_ranges else available_date_ranges
 
    # Submarket selector:
    available_submarkets = ['All'] + sorted(property_df['SubmarketName'].unique().tolist())
    selected_submarket = st.sidebar.selectbox(
        label="Select Submarket:",
        options=available_submarkets,
        index=available_submarkets.index(st.session_state.submarket) if st.session_state.submarket in available_submarkets else 0,
        key='submarket_select'
    )
    # Update session state:
    st.session_state.submarket = selected_submarket
        
    # Display current selections:
    # st.subheader("Current Selections:")
    # st.write(f"**Data Type:** {st.session_state.data_type}")
    # st.write(f"**Date Ranges:** {', '.join(st.session_state.date_ranges)}")
    # st.write(f"**Submarket:** {st.session_state.submarket}")
    # st.header("Interactive Map")
        
    if st.session_state.data_type in ['Construction Starts', 'Construction Deliveries']:
        # Filter property & submarket datasets:
        filtered_property_df = filter_property_data(property_df, st.session_state.data_type, st.session_state.date_ranges, st.session_state.submarket)
        filtered_submarket_gdf = filter_submarket_gdf(submarket_gdf, st.session_state.submarket)
        
        # For heatmap, set max "temperature" value based on the unit count for the selected submarket & date compared to that submarket's average across time:
        # If the selected year range has low unitcounts overall, we limit how "hot" the heatmap can get to reflect that:
        if st.session_state.data_type == 'Construction Starts':
            date_col = 'Start_year_range'
        else:
            date_col = 'Completion_year_range'
        hist_date_range_count = len(property_df[property_df[date_col].notna()][date_col].unique()) 
        date_range_count = len(filtered_property_df[date_col].unique())
        filtered_submarket_units = filtered_property_df['UnitCount'].sum()
        if st.session_state.submarket != 'All':
            # Calculate average unitcount for the selected submarket for the number of date ranges selected (out of a total of 5 date range options):
            # E.g. typically in one 2-year period (or 2, 3, etc), how many units are delivered/started in the submarket?
            avg_submarket_units = property_df[(property_df['SubmarketName']==st.session_state.submarket) & (property_df[date_col].notna())]['UnitCount'].sum() * (date_range_count / hist_date_range_count)
        else:
            # Calculate average unitcount for all submarkets for the number of date ranges selected (out of a total of 5 date range options):
            avg_submarket_units = property_df[property_df[date_col].notna()]['UnitCount'].sum() * (date_range_count / hist_date_range_count)
        # Now, take ratio of current value vs the average for this many date periods (& use this to adjust max "temperature" of the heatmap):
        unit_ratio = filtered_submarket_units / avg_submarket_units

        # Create property map:
        map_obj = create_property_map(filtered_property_df, filtered_submarket_gdf, st.session_state.data_type, st.session_state.submarket, unit_ratio)
        
        # Display summary statistics:
        if not filtered_property_df.empty:
            st.markdown("---")
            st.subheader("Summary Statistics")
            total_properties = len(filtered_property_df)
            total_units = filtered_property_df['UnitCount'].sum()
            avg_units = filtered_property_df['UnitCount'].mean()
            col_1, col_2, col_3, col_4 = st.columns(4)
            with col_1:
                st.metric("Total Properties", f"{total_properties:,}")
            with col_2:
                st.metric("Total Units", f"{total_units:,}")
            with col_3:
                st.metric("Avg Units per Property", f"{avg_units:.0f}")
            with col_4:
                st.metric("Pct of Avg Historical Volume", f"{(unit_ratio*100):.1f}%")

        # Display the map:
        st_folium(
            map_obj, 
            width=700, 
            height=700,
            key="folium_map"
            # returned_objects=['last_object_clicked']  # This would prevent interactions like zoom, pan, etc from needlessly triggering reruns
            )
        
        # Add description below map:
        st.write(f"**Note: Max \"Temperature\" of the heatmap is adjusted based on how the selected year(s) compare to historical average over all date ranges for the given submarket(s).")
        st.write(f"E.g. if the selected year(s) have low volume for a given submarket compared to other years, the heatmap will not show any areas as red or orange.")



    # Demand vs Supply Ratios: 
    else:  
        # Filter ratio & submarket geo datasets:
        filtered_ratio_df = filter_ratio_data(ratio_df, st.session_state.date_ranges, st.session_state.submarket)
        filtered_submarket_gdf = filter_submarket_gdf(submarket_gdf, st.session_state.submarket)

        # Create ratio map:
        map_obj = create_ratio_map(filtered_ratio_df, filtered_submarket_gdf, st.session_state.submarket)
        
        # Display ratio statistics:
        if not filtered_ratio_df.empty:
            st.subheader("Summary Statistics")
            avg_ratio = filtered_ratio_df['demand_supply_ratio'].mean()
            min_ratio = filtered_ratio_df['demand_supply_ratio'].min()
            max_ratio = filtered_ratio_df['demand_supply_ratio'].max()
            
            if selected_submarket == 'All':
                col_1, col_2, col_3 = st.columns(3)
                with col_1:
                    st.metric("Average Ratio", f"{avg_ratio:.2f}")
                with col_2:
                    st.metric("Min Ratio", f"{min_ratio:.2f}")
                with col_3:
                    st.metric("Max Ratio", f"{max_ratio:.2f}")
            else:
                # col_1 = st.columns(1)
                # with col_1:
                st.metric("Submarket Ratio", f"{avg_ratio:.2f}")

        # Display the map:
        st_folium(
            map_obj, 
            width=700, 
            height=700,
            key="folium_map2"
            # returned_objects=['last_object_clicked']  # This would prevent interactions like zoom, pan, etc from needlessly triggering reruns
            )
        
        # Add description below map:
        st.write(f"**Red-er values mean greater demand; blue-er mean greater supply.")


if __name__ == "__main__":
    main()



### TO RUN THE APP IN TERMINAL ###
# streamlit run 'c:/Users/john.hazelton/OneDrive - Cortland/Documents/Research "&" Strategy/Code/Steamlit App/denver_supply_app2.py'