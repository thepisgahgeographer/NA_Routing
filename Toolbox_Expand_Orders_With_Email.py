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

        param1 = arcpy.Parameter(
        displayName="VRP Solved Stops",
        name="solved_stops",
        datatype="GPFeatureLayer",
        parameterType="Required",
        direction="Input")

        param2 = arcpy.Parameter(
        displayName="Routes Table/Feature Class",
        name="input_routes",
        datatype=["GPFeatureLayer", "DETable"],
        parameterType="Required",
        direction="Input")

        param3 = arcpy.Parameter(
        displayName="Depots",
        name="input_depots",
        datatype="GPFeatureLayer",
        parameterType="Required",
        direction="Input")

        param4 = arcpy.Parameter(
        displayName="Consolidate Orders Output Stops",
        name="stops_location",
        datatype="GPFeatureLayer",
        parameterType="Required",
        direction="Input")

        param5 = arcpy.Parameter(
        displayName="Network Dataset",
        name="network_dataset",
        datatype="DENetworkDataset",
        parameterType="Required",
        direction="Input")
     
        param6 = arcpy.Parameter(
        displayName="Output Route Data",
        name="route_data_location",
        datatype="DEFolder",
        parameterType="Required",
        direction="Input")

        param7 = arcpy.Parameter(
        displayName="Origin Email Account",
        name="sending_email_account",
        datatype="GPString",
        parameterType="Required",
        direction="Input")

        param8 = arcpy.Parameter(
        displayName="Destination Email Account",
        name="recieving_email_account",
        datatype="GPString",
        parameterType="Required",
        direction="Input")
 
        params = [param0, param1, param2, param3, param4, param5, param6, param7, param8]
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
        

        def ExpandOrders(order_dependencies_file, solved_stops, stops_location, network_dataset, input_routes, input_depots, route_data_location):
     
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
            order_dependencies_file = parameters[0].valueAsText # The location of the order dependency file from the ConsolidateOrders script
            solved_stops = parameters[1].valueAsText # The Stops output table from the VRP problem
            input_routes = parameters[2].valueAsText # The routes table or feature class that was used for the VRP problem
            input_depots = parameters[3].valueAsText # The depots feature class that was used for the VRP problem
            stops_location = parameters[4].valueAsText # The location of the stops saved from the ConsolidateOrders script (should have all the original locations)
            network_dataset = parameters[5].valueAsText # The network dataset location
            route_data_location = parameters[6].valueAsText # Where the final zip file will be saved
        try:
            ExpandOrders(order_dependencies_file, solved_stops, stops_location, \
                    network_dataset, input_routes, input_depots, route_data_location)
            print("Successful")
        except:
            print("Script Failed")      

        def emailClient(sending_email_account,recieving_email_account):
            import smtplib, ssl
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            #sending_email_account = parameters[7].valueAsText # Where the final zip file will be saved
            #recieving_email_account = parameters[8].valueAsText # Where the final zip file will be saved

            sending_email_account = parameters[7].valueAsText
            recieving_email_account = parameters[8].valueAsText
            password = getpass.getpass('Enter password')

            msg = MIMEMultipart("alternative")
            msg['From'] = sending_email_account
            msg['To'] = recieving_email_account
            msg['Subject'] = "Route Data"

            text = """\
                Hi,
                You have a new route ready:"""+navigatorLink 
            html = """\
                <html>
                <body>
                    <p>Hi,<br><br>
                    You have a new route ready:<br><br>
                    <a href="""+navigatorLink+""">Open Turn by Turn Directions</a> OR<br><br>
                    <a href="""+navigatorLinkOptimized+""">Open <b>Optimized</b> Turn by Turn Directions</a>
                    </p>
                </body>
                </html>
                """

            # Turn these into plain/html MIMEText objects
            part1 = MIMEText(text, "plain")
            part2 = MIMEText(html, "html")

            # Add HTML/plain-text parts to MIMEMultipart message
            # The email client will try to render the last part first
            msg.attach(part1)
            msg.attach(part2)

            # Create secure connection with server and send email
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                server.login(sending_email_account, password)
                server.sendmail(
                    sending_email_account, recieving_email_account, message.as_string()
                )
                