#-------------------------------------------------------------------------------
# Name:        ExpandOrders.py
# Purpose:     This takes the solved consolidated orders and expands them back
#              out to the individual orders to see individual arrival times.
#-------------------------------------------------------------------------------
import arcpy
import os
import sys

def ExpandOrders(order_dependencies_file, solved_stops, stops_location, network_dataset, input_routes, input_depots, route_data_location):

    
    
    """ This takes the solved consolidated orders and expands them back
        out to the individual orders to see individual arrival times. 
        
        
        parameters to the function are (order_dependencies_file, solved_stops,
                stops_location, network_dataset, input_routes, input_depots, route_data_location)
        
    """


    # Open the file that was created when consolidating orders so we can find
    # all of the dependent orders
    order_dependencies = {}
    with open (order_dependencies_file, "r") as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip("\n")
            orders = [e for e in line.split(",")]
            order_dependencies[orders[0]] = orders

    # Open the stops table and make a dictionary for the orders with their route
    # assignment and a list of all the route names
    stops_search_cursor = arcpy.da.SearchCursor(solved_stops, ["Name", "RouteName"])
    stops_route_assignment = {}
    route_names = []
    for row in stops_search_cursor:
        stops_route_assignment[row[0]] = row[1]
        if row[1] not in route_names:
            route_names.append(row[1])

    # Update the stops_location with the route assignment for all of the orders
    # based on the route the super order was assigned
    arcpy.AddMessage("Adding Route Assignments...")
    arcpy.MakeFeatureLayer_management(stops_location, "original_stops_layer")
    for order in order_dependencies:
        # Get the route assignment
        route_assignment = stops_route_assignment[order]
        # Select all the orders that were consolidated into that super order
        for order_name in order_dependencies[order]:
            select_by_attribute_expression = "Name = '{}'".format(order_name)
            arcpy.management.SelectLayerByAttribute("original_stops_layer", "ADD_TO_SELECTION", select_by_attribute_expression)
        # Update the original orders with the assignment rule
        update_cursor = arcpy.da.UpdateCursor("original_stops_layer", ["RouteName", "Attr_TravelTime", "Sequence", "CurbApproach"])
        for row in update_cursor:
            row[0] = route_assignment
            row[1] = 0.25
            row[2] = None
            row[3] = 1
            update_cursor.updateRow(row)
        arcpy.management.SelectLayerByAttribute("original_stops_layer", "CLEAR_SELECTION")

    # For each route name in the VRP problem make a route layer and solve it
    # with finding the best route preserving the first and last stop.
    arcpy.CheckOutExtension("network")

    # Create a feature layer for the depot
    arcpy.MakeFeatureLayer_management(input_depots, "depots_layer")

    depot_search_cursor = arcpy.da.SearchCursor("depots_layer", ["Name"])
    for row in depot_search_cursor:
        print (row[0])

    for route_name in route_names:
        arcpy.AddMessage("Making Route Layer for " + route_name)

        # Make a route layer
        routes_object = arcpy.na.MakeRouteAnalysisLayer(network_dataset, route_name, \
                                    "Driving Time", "PRESERVE_BOTH", None, \
                                    "LOCAL_TIME_AT_LOCATIONS", "ALONG_NETWORK", \
                                    None, "DIRECTIONS")

        # Identify the Stops layer
        layer_object = routes_object.getOutput(0)
        sublayer_names = arcpy.na.GetNAClassNames(layer_object)
        stops_layer_name = sublayer_names["Stops"]
        stops_layer_object = layer_object.listLayers(stops_layer_name)[0]

        # Find out what the starting and ending depot are for the route
        routes_search_cursor = arcpy.da.SearchCursor(input_routes, ["Name", "StartDepotName", "EndDepotName"])
        for row in routes_search_cursor:
            if row[0] == route_name:
                start_depot = row[1]
                end_depot = row[2]
                print(start_depot, end_depot)

        # select the start depot and load it
        select_by_attribute_expression = "Name = '{}'".format(start_depot)
        arcpy.management.SelectLayerByAttribute("depots_layer", "NEW_SELECTION", select_by_attribute_expression)
        arcpy.na.AddLocations(layer_object, "Stops", "depots_layer")

        # select the orders that are on the route
        select_by_attribute_expression = "RouteName = '{}'".format(route_name)
        arcpy.management.SelectLayerByAttribute("original_stops_layer", "NEW_SELECTION", select_by_attribute_expression)
        arcpy.na.AddLocations(layer_object, "Stops", "original_stops_layer")

        # select the end depot and load it
        select_by_attribute_expression = "Name = '{}'".format(end_depot)
        arcpy.management.SelectLayerByAttribute("depots_layer", "NEW_SELECTION", select_by_attribute_expression)
        arcpy.na.AddLocations(layer_object, "Stops", "depots_layer")

        # Use the field calculator to make the route name the same on all the routes
        # and the sequence to be the object ID
        arcpy.management.CalculateField(stops_layer_object, "RouteName", "'" + route_name + "'", "PYTHON3", '', "TEXT")
        arcpy.management.CalculateField(stops_layer_object, "Sequence", "!ObjectID!", "PYTHON3", '', "TEXT")

        # Solve and save the route
        arcpy.na.Solve(layer_object,"SKIP")
        saved_route_file = os.path.join(route_data_location, route_name + ".lyr")
        arcpy.management.SaveToLayerFile(layer_object, saved_route_file, "RELATIVE")
        arcpy.na.ShareAsRouteLayers(layer_object)

    arcpy.AddMessage("Finished running")

if __name__ == '__main__':
    order_dependencies_file = '' # The location of the order dependency file from the ConsolidateOrders script
    solved_stops = '' # The Stops output table from the VRP problem
    input_routes = '' # The routes table or feature class that was used for the VRP problem
    input_depots = '' # The depots feature class that was used for the VRP problem
    stops_location = '' # The location of the stops saved from the ConsolidateOrders script (should have all the original locations)
    network_dataset = '' # The network dataset location
    route_data_location = '' # Where the final zip file will be saved
    try:
        ExpandOrders(order_dependencies_file, solved_stops, stops_location, \
                network_dataset, input_routes, input_depots, route_data_location)
        print("Successful")
    except:
        print("Script Failed")            

