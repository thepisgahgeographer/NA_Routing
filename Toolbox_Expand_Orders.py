# -*- coding: utf-8 -*-

import arcpy


class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Expand Orders"
        self.alias = "Expand Orders"

        # List of tool classes associated with this toolbox
        self.tools = [Tool]


class Tool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Expand Orders"
        self.description = "This takes the solved consolidated orders and expands them back out to the individual orders to see individual arrival times."
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""

        param0 = arcpy.Parameter(
        displayName="Order Dependency File From the Consolidate Orders Script",
        name="order_dependencies_file",
        datatype="DETextfile",
        parameterType="Required",
        direction="Input")

        

########################################################################################
        

        params = [param0, param1, param2, param3, param4, param5]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        import arcpy
        import os
        import sys

        def consolidatedOrders(original_orders, consolidated_orders, network_dataset, \
                        undissolved_streets_network, order_dependency_file, \
                        stops_location):

                # Create a Route Analysis layer so we can get the correct side of edge
            routes_object = arcpy.na.MakeRouteAnalysisLayer(network_dataset, "Route", \
                                    "Driving Time", "USE_CURRENT_ORDER", None, \
                                    "LOCAL_TIME_AT_LOCATIONS", "ALONG_NETWORK", \
                                    None, "DIRECTIONS")

            layer_object = routes_object.getOutput(0)
            sublayer_names = arcpy.na.GetNAClassNames(layer_object)
            stops_layer_name = sublayer_names["Stops"]
            stops_layer_object = layer_object.listLayers(stops_layer_name)[0]
            field_mappings = "Name USER_Customer_Name #"
            arcpy.na.AddLocations(layer_object, "Stops", original_orders, field_mappings)

            # Save the Stops layer so we can use it again when expanding
            arcpy.management.CopyFeatures(stops_layer_object, stops_location)

            # Perform a near analysis to the undissolved streets network
            arcpy.analysis.Near(stops_layer_object, undissolved_streets_network, None, \
                        "NO_LOCATION", "NO_ANGLE", "PLANAR")

            # Create a search cursor for the stops_layer_object
            arcpy.AddMessage("Consolidated orders on streets...")
            fields = ["NEAR_FID", "Name", "PosAlong", "SideOfEdge"]
            cursor = arcpy.da.SearchCursor(stops_layer_object, fields)

            # Save a dictionary street_position_order - {street: {side_of_edge : (posAlong, name)}}
            street_position_order = {}
            for row in cursor:
                street_segment = row[0]
                order_name = row[1]
                order_pos = row[2]
                side_of_edge = row[3]
                if side_of_edge in street_position_order:
                    if street_segment in street_position_order[side_of_edge]:
                        orders_on_side = street_position_order[side_of_edge][street_segment]
                        orders_on_side.append((order_pos, order_name))
                        street_position_order[side_of_edge][street_segment] = orders_on_side
                    else:
                        street_position_order[side_of_edge][street_segment] = [(order_pos, order_name)]
                else:
                    street_position_order[side_of_edge] = {}
                    street_position_order[side_of_edge][street_segment] = [(order_pos, order_name)]

            # Add a single consolidated order for each street segment and side of edge
            name_to_number_of_orders = {}

            for side_of_edge in street_position_order:
                for street_segment in street_position_order[side_of_edge]:
                    number_consolidating = len(street_position_order[side_of_edge][street_segment])
                    order_to_use_as_consolidate = street_position_order[side_of_edge][street_segment][0][1]
                    sqlQuery = "Name = '{}'".format(order_to_use_as_consolidate)
                    print (sqlQuery, street_position_order[side_of_edge][street_segment], number_consolidating)
                    arcpy.management.SelectLayerByAttribute(stops_layer_object, "NEW_SELECTION", sqlQuery)
                    name_to_number_of_orders[order_to_use_as_consolidate] = number_consolidating

                    # Append to the consolidated orders feature class
                    arcpy.management.Append(stops_layer_object, consolidated_orders, "NO_TEST")

                    # Write the order dependencies to a text file so they can be expanded
                    # back out after we have a solution to the clustering
                    dependent_orders = ""
                    if number_consolidating > 1:
                        for i in range(1, number_consolidating):
                            dependent_orders += ",{}".format(street_position_order[side_of_edge][street_segment][i][1])
                    with open(order_dependency_file, "a") as f:
                        f.write("{}{}\n".format(order_to_use_as_consolidate, dependent_orders))

            # Update the table with the right service time and pickup quantity
            update_cursor = arcpy.da.UpdateCursor(consolidated_orders, ["Name", "ServiceTime", "PickupQuantities", "CurbApproach"])
            for row in update_cursor:
                quantity = name_to_number_of_orders[row[0]]
                row[1] = quantity*0.25
                row[2] = quantity
                row[3] = 1
                update_cursor.updateRow(row)

if __name__ == '__main__':
    undissolved_streets_network = ''#Put the path to the streets feature class that is the output from the Feature To Line
    network_dataset = '' #Put the path to the actual network dataset used for routing
    original_orders = '' #Put the path to the feature class of the order locations. I uesd the Monday_Addresses
    consolidated_orders = '' #Put the path to an empty feature class with the Orders schema
    order_dependency_file = '' # Put a path with filename.txt for the dependency of the consolidation to the full set of orders to be stored
    stops_location = '' # Put a path to a gdb with a feature class name such as orginal_stops to store the original orders in a feature class with schema needed for expanding
    try:
        consolidatedOrders(original_orders, consolidated_orders, network_dataset, undissolved_streets_network, order_dependency_file, stops_location)
        print("Successful")
    except:
        print("Script Failed")
  