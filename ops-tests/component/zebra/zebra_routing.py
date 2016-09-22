# -*- coding: utf-8 -*-

# (c) Copyright 2015-2016 Hewlett Packard Enterprise Development LP
#
# GNU Zebra is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2, or (at your option) any
# later version.
#
# GNU Zebra is distributed in the hope that it will be useful, but
# WITHoutput ANY WARRANTY; withoutput even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Zebra; see the file COPYING.  If not, write to the Free
# Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.


from time import sleep
from re import match
from re import sub
from operator import itemgetter
from pprint import pprint


IPV4_STATIC_ROUTE = "ipv4_static_route"
IPV6_STATIC_ROUTE = "ipv6_static_route"
IPV4_ROUTE = "ip route"
IPV6_ROUTE = "ipv6 route"
RIB = "rib"

# Default timeout for all the zebra component test scripts
ZEBRA_DEFAULT_TIMEOUT = 600

# Configuration install and processing time taken by ops-zebra
ZEBRA_TEST_SLEEP_TIME = 15


def get_route_and_nexthops_from_output(output, route, route_type):
    """
    Library function to get the show dump for a route in the command
    "show ip route/show ipv6 route/show rib".

    :param output    : Output of either of the show commands
                       "show ip route/show ipv6 route/show rib"
    :type output     : string
    :param route     : Route which is of the format "Prefix/Masklen"
    :type  route     : string
    :param route_type : Route type which can be "static/BGP"
    :type  route_type : string
    :return: string
    """

    found_route = False
    found_nexthop = False

    # Split the output in lines
    lines = output.splitlines()

    # Output buffer for storing the route and its next-hops
    route_output = ''

    # Walk through all the lines for the output of
    # "show ip route/show ipv6 route/show rib"
    for line in lines:

        # If the route ("prefix/mask-length") is not found in the output
        # then try to find the route in the output. Otherwise the route
        # was already found and now try to check whether the next-hop
        # is of type 'route_type'
        if not found_route:

            # If the route ("prefix/mask-length") is found in the line
            # then set 'found_route' to 'True' and add the line to the
            # output buffer
            if route in line:
                found_route = True
                route_output = "{}{}\n".format(route_output, line)
        else:

            # If the route_type occurs in the next-hop line,
            # then add the next-hop line into the output buffer.
            if 'via' in line and route_type in line:
                route_output = "{}{}\n".format(route_output, line)
                found_nexthop = True
            else:
                # If the next-hop is not of type 'route_type',
                # then reset 'found_route' to 'False'
                if not found_nexthop:
                    found_route = False
                    route_output = ''
                else:
                    break
    # Return the output buffer to caller
    return route_output


def get_route_from_show(sw1=None, route=None, route_type=None, show=None):
    """
    Library function to get the show dump for a route in the command
    "show ip route/show ipv6 route/show rib".

        :param sw1 : Device object
    :type  sw1 : topology.platforms.base.BaseNode
    :param route     : Route which is of the format "Prefix/Masklen"
    :type  route     : string
    :param routetype : Route type which can be "static/BGP"
    :type  routetype : string
    :param show : type of show to be checked
    :type show : string
    :return: Dictionary
            data keys
                Route - string set to route which is of the format
                        "Prefix/Masklen"
                NumberNexthops - string set to the number of next-hops
                                 of the route
                Next-hop - string set to the next-hop port or IP/IPv6
                           address as the key and a dictionary as value
                data keys
                    Distance:String whose numeric value is the administration
                             distance of the next-hop
                    Metric:String whose numeric value is the metric of the
                           next-hop
                    RouteType:String which is the route type of the next-hop
                              which is among "static/BGP"
    :returntype: dictionary
    """
    # checks if device is passed, if not, assertion will fail
    assert sw1 is not None

    # checks if route is passed, if not, assertion will fail
    assert route is not None

    # checks if route type is passed, if not, assertion will fail
    assert route_type is not None

    # getting output from the exact type of shw, passed from arg
    show_output = sw1("do show {}".format(show))

    # Get the route and the next-hops for the 'routetype' from the
    # "show ip route/show ipv6 route/show rib".
    route_output = get_route_and_nexthops_from_output(show_output,
                                                      route, route_type)
    # Initialize the return route dictionary
    route_dict = dict()

    # Add the prefix and the mask length of the route in the return
    # dictionary
    route_dict['Route'] = route

    lines = route_output.splitlines()

    # Declaring match to reuse it further
    m = ""
    diff = 0
    if show == RIB:
        m = "(.*)({})(,  )(\d+)( unicast next-hops)".format(route)
    else:
        m = "({})(,  )(\d+)( unicast next-hops)".format(route)
        diff = 1

    # Walk through all the lines of the route output for the route and
    # populate the return route distionary
    for line in lines:

        # Match the route ("prefix/mask-length") against the regular expression
        routeline = match(m, line)

        # The output line matches the route, then populate the route and number
        # of next-hops in the return route dictionary
        if routeline:
            route_dict['Route'] = routeline.group(2 - diff)
            route_dict['NumberNexthops'] = routeline.group(4 - diff)

        # Match the next-hop lines against the regular expression and populate
        # the next-hop dictionary with distance, metric and routetype
        nexthop = match("(.+)via  (.+),  \[(\d+)/(\d+)\],  (.+)",
                        line)

        if nexthop:
            route_dict[nexthop.group(2)] = dict()
            route_dict[nexthop.group(2)]['Distance'] = nexthop.group(3)
            route_dict[nexthop.group(2)]['Metric'] = nexthop.group(4)
            aux_nexthop = nexthop.group(5).rstrip('\r')
            route_dict[nexthop.group(2)]['RouteType'] = aux_nexthop

    # Returns thye result in a dictionary
    return route_dict


def verify_show(sw1, route, route_type, p_dict, show):
    """
    Library function tests whether a route ("prefix/mask-length") in the
    command "show ip route/show ipv6 route/show rib" exactly matches an
    expected route dictionary that is passed to this function. In case the
    route dictionary returned by 'get_route_from_show' is not the same as
    the expected route dictionary, then the script test run will assert out
    based on the timepout defined in the script which uses this function..

    :param sw1 : Device object
    :type  sw1 : topology.platforms.base.BaseNode
    :param route : IPV4/IPV6 address that must be verified
    :type route : string
    :param p_dict: Expected route dictionary
    :type  p_dict: dictionary
    :param route_type : Route type which can be "static/BGP"
    :type  route_type : string
    :param show : type of show to be checked
    :type show : string
    """
    # Parsing the received dictionary so we can compare it easily
    p_dict = sorted(p_dict.items(), key=itemgetter(0))

    # Get the actual route dictionary for the route. Execute the show command
    # until the route is seen in the show output, else sleep for a second in
    # every iteration to allow processing by ops-zebra.
    route_found = False
    num_of_iterations = 0
    while route_found is not True:
        dict_from_show = get_route_from_show(sw1,
                                             route,
                                             route_type,
                                             show)

        # Parsing the obtained dictionary so we can compare it easily
        dict_from_show = sorted(dict_from_show.items(), key=itemgetter(0))

        # Prints for debug purposes
        num_of_iterations = num_of_iterations + 1

        print("Verification attempt: %d\n" % num_of_iterations)

        print("Actual: {}\n".format(str(dict_from_show)))

        print("Expected: {}\n".format(str(p_dict)))

        if p_dict == dict_from_show:
            route_found = True
            # Break out of the while loop once the route is found
            break

        # Sleep for a second to allow processing by ops-zebra
        sleep(1)

    if route_found is True:
        print("Expected route found in the 'show %s' command\n" % show)


def verify_show_ip_route(sw1, route, route_type, p_dict):
    """
    Library function tests whether a route ("prefix/mask-length") in the
    command "show ip route" exactly matches an expected route dictionary
    that is passed to this function. It will be used as a wrapper to the
    function "verify_show".

    :param sw1 : Device object
    :type  sw1 : topology.platforms.base.BaseNode
    :param route : IPV4/IPV6 address that must be verified
    :type route : string
    :param p_dict: Expected route dictionary
    :type  p_dict: dictionary
    :param route_type : Route type which can be "static/BGP"
    :type  route_type : string
    """
    verify_show(sw1, route, route_type, p_dict, IPV4_ROUTE)


def verify_show_ipv6_route(sw1, route, route_type, p_dict):
    """
    Library function tests whether a route ("prefix/mask-length") in the
    command "show ipv6 route" exactly matches an expected route dictionary
    that is passed to this function. It will be used as a wrapper to the
    function "verify_show".

    :param sw1 : Device object
    :type  sw1 : topology.platforms.base.BaseNode
    :param route : IPV4/IPV6 address that must be verified
    :type route : string
    :param p_dict: Expected route dictionary
    :type  p_dict: dictionary
    :param route_type : Route type which can be "static/BGP"
    :type  route_type : string
    """
    verify_show(sw1, route, route_type, p_dict, IPV6_ROUTE)


def verify_show_rib(sw1, route, route_type, p_dict):
    """
    Library function tests whether a route ("prefix/mask-length") in the
    command "show rib" exactly matches an expected route dictionary that is
    passed to this function. It will be used as a wrapper to the function
    "verify_show".

    :param sw1 : Device object
    :type  sw1 : topology.platforms.base.BaseNode
    :param route : IPV4/IPV6 address that must be verified
    :type route : string
    :param p_dict: Expected route dictionary
    :type  p_dict: dictionary
    :param route_type : Route type which can be "static/BGP"
    :type  route_type : string
    """
    verify_show(sw1, route, route_type, p_dict, RIB)


def if_config_in_running_config(**kwargs):
    """
    Library function to checks whether a given configuration exists
    in the "show running-config" output or not. If the configuration
    exists in the "show running-config", then this function returns 'True'
    otherwise this function will return 'False'.

    :param sw1 : Device object
    :type  sw1 : topology.platforms.base.BaseNode
    :param configtype : Configuration type that the user wants to tests
                        in the "show running-config" output. This should
                        be a string. The configtype can be only one of
                        the following string:-
                        IPv4 static route configuration: "ipv4_static_route"
                        IPv6 static route configuration: "ipv6_static_route"
    :type configtype: string
    :param route     : Route which is of the format "Prefix/Masklen"
    :type  route     : string
    :param nexthop   : Nexthop which is of the format "IP/IPv6 address" or
                       "Port number"
    :type nexthop    : string
    :param distance  : Administration distance of the route
    :type distance   : string
    """

    sw1 = kwargs.get('sw1', None)
    config_type = kwargs.get('config_type', None)
    config_present_check = kwargs.get('config_present_check', None)
    running_config_string = ''

    # checks if device is passed, if not, assertion will fail
    assert sw1 is not None

    # checks if config typw is passed, if not, assertion will fail
    assert config_type is not None

    # checks if config_present_check parameter is passed, if not, assertion
    # will fail
    assert config_present_check is not None

    # If the config type is either IPV4_STATIC_ROUTE or IPV6_STATIC_ROUTE:,
    # then read the route, nexthop and distance from the arguments
    if config_type is IPV4_STATIC_ROUTE or config_type is IPV6_STATIC_ROUTE:

        route = kwargs.get('route', None)
        nexthop = kwargs.get('nexthop', None)
        distance = kwargs.get('distance', None)

        # If route is not passed, we need to fail so return False
        if route is None:
            return False

        # If nexthop is not passed, we need to fail so return False
        if nexthop is None:
            return False

        # Form the IPv4/IPV6 configuration string. This will be checked in the
        # the output of "show running-config"
        if config_type is IPV4_STATIC_ROUTE:

            # Check if the distance needs to be added into the configuration
            # string
            if distance is None:
                running_config_string = 'ip route {} {}'.format(route,
                                                                nexthop)
            else:
                running_config_string = 'ip route {} {} {}'.format(route,
                                                                   nexthop,
                                                                   distance)
        else:
            # Check if the distance needs to be added into the configuration
            # string
            if distance is None:
                running_config_string = 'ipv6 route {} {}'.format(route,
                                                                  nexthop)
            else:
                running_config_string = 'ipv6 route {} {} '
                '{}'.format(route,
                            nexthop,
                            distance)

    # The 'if' condition checks for the presence of "ip route" command in the
    # output of 'show running-config' whereas the else condition checks for the
    # absence of "ip route" command in the 'show running-config' output
    if config_present_check is True:

        # Execute the show command until the route is seen in the show output,
        # else sleep for a second in every iteration to allow processing by
        # ops-zebra.
        route_found = False
        num_of_iterations = 0
        while route_found is not True:

            # The command in whose output we need to check the presence of
            # configuration
            show_running_config = sw1("do show running-config")

            # Split the output of "show running-config" into lines
            show_running_config_lines = show_running_config.split('\n')

            num_of_iterations = num_of_iterations + 1
            print("Verification attempt: %d\n" % num_of_iterations)

            # Walk through all the lines of "show running-config" and check if
            # the configuration exists in one of the lines, if not then sleep
            # for a second until the route is found to allow processing by
            # ops-zebra
            for line in show_running_config_lines:

                # If the configuration exists in the "show running-config"
                # output, then mark route_found as True and break the cycle
                if running_config_string in line:
                    route_found = True
                    break

            sleep(1)

        if route_found is True:
            print("Expected route found in 'show running-config' command\n")

    else:
        # Execute the show command until the route is seen in the show output,
        # else sleep for a second in every iteration to allow processing by
        # ops-zebra.
        route_found = True
        num_of_iterations = 0
        while route_found is True:

            # The command in whose output we need to check the presence of
            # configuration
            show_running_config = sw1("do show running-config")

            # Split the output of "show running-config" into lines
            show_running_config_lines = show_running_config.split('\n')

            num_of_iterations = num_of_iterations + 1
            print("Verification attempt: %d\n" % num_of_iterations)

            # Walk through all the lines of "show running-config" and check if
            # the configuration does not exist in one of the lines, if yes then
            # sleep for a second until the route is removed to allow processing
            # by ops-zebra
            for line in show_running_config_lines:

                # If the configuration doesn't exist in the
                # "show running-config" output, then mark route_found as False
                # and break the cycle
                if running_config_string not in line:
                    route_found = False
                    break

            sleep(1)

        if route_found is False:
            print("Expected route not found in the 'show running-config' "
                  "command\n")


def route_and_nexthop_in_show_running_config(**kwargs):
    """
    Library function tests whether a static route with "prefix/mask-length",
    next-hop and administration distance exists in the command
    "show running-config". If such a static route configuration exists in the
    output of "show running-config" output, then this function returns True,
    otherwise the script test run will assert out based on the timepout
    defined in the script which uses this function..

    :param sw1 : Device object
    :type  sw1 : topology.platforms.base.BaseNode
    :param if_ipv4   : If the route passed is IPv4 or IPv6 route. If
                       the route passed in IPv4, then if_ipv4 should
                       be 'True' otherwise it should be 'False'
    :type  if_ipv4   : boolean
    :param route     : route is of the format "prefix/mask-length"
    :type  route     : string
    :param nexthop   : Nexthop which is of the format "IP/IPv6 address" or
                       "Port number"
    :type nexthop    : string
    :param distance  : Administration distance of the route
    :type distance   : string
    """
    sw1 = kwargs.get('sw1', None)
    if_ipv4 = kwargs.get('if_ipv4', None)
    route = kwargs.get('route', None)
    nexthop = kwargs.get('nexthop', None)
    distance = kwargs.get('distance', None)

    # If the route is a IPv4 route call if_config_in_running_config() with
    # IPV4_STATIC_ROUTE else call if_config_in_running_config() with
    # IPV6_STATIC_ROUTE
    if if_ipv4 is True:
        if_config_in_running_config(sw1=sw1,
                                    config_type=IPV4_STATIC_ROUTE,
                                    route=route,
                                    nexthop=nexthop,
                                    distance=distance,
                                    config_present_check=True)
    else:
        if_config_in_running_config(sw1=sw1,
                                    config_type=IPV6_STATIC_ROUTE,
                                    route=route,
                                    nexthop=nexthop,
                                    distance=distance,
                                    config_present_check=True)


def route_and_nexthop_not_in_show_running_config(**kwargs):
    """
    Library function tests whether a static route with "prefix/mask-length",
    next-hop and administration distance does not exists in the command
    "show running-config". If such a static route configuration exists in the
    output of "show running-config" output, then this function returns False,
    otherwise the script test run will assert out based on the timepout
    defined in the script which uses this function..

    :param sw1 : Device object
    :type  sw1 : topology.platforms.base.BaseNode
    :param if_ipv4   : If the route passed is IPv4 or IPv6 route. If
                       the route passed in IPv4, then if_ipv4 should
                       be 'True' otherwise it should be 'False'
    :type  if_ipv4   : boolean
    :param route     : route is of the format "prefix/mask-length"
    :type  route     : string
    :param nexthop   : Nexthop which is of the format "IP/IPv6 address" or
                       "Port number"
    :type nexthop    : string
    :param distance  : Administration distance of the route
    :type distance   : string
    """
    sw1 = kwargs.get('sw1', None)
    if_ipv4 = kwargs.get('if_ipv4', None)
    route = kwargs.get('route', None)
    nexthop = kwargs.get('nexthop', None)
    distance = kwargs.get('distance', None)

    # If the route is a IPv4 route call if_config_in_running_config() with
    # IPV4_STATIC_ROUTE else call if_config_in_running_config() with
    # IPV6_STATIC_ROUTE
    if if_ipv4 is True:
        if_config_in_running_config(sw1=sw1,
                                    config_type=IPV4_STATIC_ROUTE,
                                    route=route,
                                    nexthop=nexthop,
                                    distance=distance,
                                    config_present_check=False)
    else:
        if_config_in_running_config(sw1=sw1,
                                    config_type=IPV6_STATIC_ROUTE,
                                    route=route,
                                    nexthop=nexthop,
                                    distance=distance,
                                    config_present_check=False)


def get_route_from_show_kernel_route(**kwargs):
    """
    Library function to get the show dump for a route in the linux
    command "ip -6 route/ip -6 route" in swns namespace.

    :param switch : Device object
    :type  switch : topology.platforms.base.BaseNode
    :param if_ipv4   : If the route passed is IPv4 or IPv6 route. If
                       the route passed in IPv4, then if_ipv4 should
                       be 'True' otherwise it should be 'False'
    :type  if_ipv4   : boolean
    :param route     : Route which is of the format "Prefix/Masklen"
    :type  route     : string
    :param route_type : Route type which can be "static/BGP"
    :type  route_type : string
    :return: returnStruct Object
            buffer
            data keys
                Route - string set to route which is of the format
                        "Prefix/Masklen"
                NumberNexthops - string set to the number of next-hops
                                 of the route
                Next-hop - string set to the next-hop port or IP/IPv6
                           address as the key and a dictionary as value
                data keys
                    Distance - String whose numeric value is the administration
                               distance of the next-hop
                    Metric - String whose numeric value is the metric of the
                             next-hop
                    RouteType - String which is the route type of the next-hop
                                which is among "static/BGP"
    :returnType: dictionary
    """
    sw = kwargs.get('switch', None)
    if_ipv4 = kwargs.get('if_ipv4', True)
    route = kwargs.get('route', None)
    route_type = kwargs.get('route_type', None)

    # checks if device is passed, if not, assertion will fail
    assert sw is not None, "Switch object not passed"

    # checks if route is passed, if not, assertion will fail
    assert route is not None, "Route not passed"

    # checks if route_type is passed, if not, assertion will fail
    assert route_type is not None, "Route type not passed"

    # if 'if_ipv4' is 'True', then the command to be executed is
    # "ip route list <route>" otherwise the command is
    # "ip -6 route list <route>"
    if if_ipv4 is True:
        kernel_route_command = "ip netns exec swns ip route list " + route
    else:
        kernel_route_command = "ip netns exec swns ip -6 route list " + route

    # Execute the "command" on the Linux bash interface
    kernel_route_buffer = sw(kernel_route_command, shell="bash")
    sw("configure terminal")

    # Initialize the return route dictionary
    route_dict = dict()

    # Add the prefix and the mask length of the route in the return
    # dictionary
    route_dict['Route'] = route

    # Split the route into prefix and mask length
    [prefix, masklen] = route.split('/')

    # If the route is 10.0.0.0/32 or 123::1/128, then it appears in
    # kernel "ip route/ip -6 route" as:-
    # 10.0.0.0/32 -> 10.0.0.0
    # 123::1/128 -> 123::1
    #
    # If the route is 10.0.0.0/34 or 123:1::/64, then it appears in
    # kernel "ip route/ip -6 route" as:-
    # 10.0.0.0/24 -> 10.0.0.0/24
    # 123:1::/64 -> 123:1::/64
    #
    # That's why the logic below is put to handle this case.
    route_string = ""
    if if_ipv4:
        if int(masklen) >= 32:
            route_string = prefix
        else:
            route_string = route
    else:
        if int(masklen) >= 128:
            route_string = prefix
        else:
            route_string = route

    lines = kernel_route_buffer.split('\n')

    nexthop_number = 0
    if_route_found = False

    # populate the return route distionary
    for line in lines:

        commandline = match("ip netns exec swns ip", line)

        if commandline:
            continue

        line = sub("\s\s+", " ", line)
        routeline = match(
            "(%s)(.*)(proto %s)" %
            (route_string, route_type), line)

        nexthop_string = ""

        if routeline:

            if_route_found = True

            nexthopipline = match("(.*)via\s(.*)( )dev(.*)", line)

            if nexthopipline:
                nexthop_string = nexthopipline.group(2)
            else:
                nexthopifline = match("(.*)dev\s(.+)\sproto(.*)", line)

                if nexthopifline:
                    nexthop_string = nexthopifline.group(2)

        nexthopipline = match("(.*)nexthop\svia\s(.*)( )dev(.*)", line)

        if nexthopipline:
            nexthop_string = nexthopipline.group(2)

        nexthopifline = match("(.*)nexthop\sdev\s(.*)\sweight(.*)", line)

        if nexthopifline:
            nexthop_string = nexthopifline.group(2)

        if len(nexthop_string) > 0 and if_route_found:

            route_dict[nexthop_string.rstrip(' ')] = dict()
            route_dict[nexthop_string.rstrip(' ')]['Distance'] = ""
            route_dict[nexthop_string.rstrip(' ')]['Metric'] = ""
            route_dict[nexthop_string.rstrip(' ')]['RouteType'] = route_type

            nexthop_number = nexthop_number + 1

    if nexthop_number > 0:
        route_dict['NumberNexthops'] = str(nexthop_number)

    # Return the kernel route dictionary
    print("returning\n")
    return route_dict


def verify_route_in_show_kernel_route(sw, if_ipv4, expected_route_dict,
                                      route_type):
    """
    Library function tests whether a route ("prefix/mask-length") in the
    linux command "ip route/ip -6 route" exactly matches an expected route
    dictionary that is passed to this function. In case the route dictionary
    returned by 'get_route_from_show_kernel_route()' is not same as the
    expected route dictionary, then this function will fail the test case by
    calling assert().

    :param sw : Device object
    :type  sw : topology.platforms.base.BaseNode
    :param if_ipv4   : If the route passed is IPv4 or IPv6 route. If
                       the route passed in IPv4, then if_ipv4 should
                       be 'True' otherwise it should be 'False'
    :type  if_ipv4   : boolean
    :param expected_route_dict: Expected route dictionary
    :type  expected_route_dict: dictionary
    :param route_type : Route type which is zebra
    :type  route_type : string
    """

    print("\nCheck kernel route table for "
          + expected_route_dict['Route'])

    # Get the actual route dictionary for the route
    actual_route_dict = get_route_from_show_kernel_route(
        switch=sw,
        if_ipv4=if_ipv4,
        route=expected_route_dict['Route'],
        route_type=route_type)

    # If there was error getting the actual route dictionary, then assert
    # and fail the test case
    if actual_route_dict is None:
        assert False,  "Failed to get the dictionary for route " + \
            expected_route_dict['Route'] + " and route type " \
            + route_type

    # Sort the actual route dictionary
    actual_route_dict = sorted(actual_route_dict.items(),
                               key=itemgetter(0))

    # Sort the expected route dictionary
    expected_route_dict = sorted(expected_route_dict.items(),
                                 key=itemgetter(0))

    # Print the actual and expected route dictionaries for debugging
    # purposes
    print("\nThe expected kernel route dictionary is:")
    pprint(expected_route_dict, width=1)

    print("\nThe actual kernel route dictionary is:")
    pprint(actual_route_dict, width=1)

    # Comparing dictionaries, if not equals, assertion will fail
    assert actual_route_dict == expected_route_dict


def verify_active_router_id_in_vrf(sw, expected_active_router_id):
    """
    Library function tests whether active router id is set correctly
    in the VRF table in the database.

    :param sw : Device object
    :type  sw : topology.platforms.base.BaseNode
    :param expected_active_router_id : Expected router-id that should be
                                       present in the VRF table
    :type expected_active_router_id : string
    """

    # Execute the "ovsdb-client dump VRF" command until the router-id is seen
    # in the show output, else sleep for a second in every iteration to allow
    # processing by ops-zebra.
    router_id_found = False
    num_of_iterations = 0
    while router_id_found is not True:

        num_of_iterations = num_of_iterations + 1
        print("Verification attempt: %d\n" % num_of_iterations)

        output = sw("ovsdb-client dump VRF", shell='bash')
        if expected_active_router_id in output:
            router_id_found = True
            # Break out of the while loop once the active router-id is found
            break

        # Sleep for a second to allow processing by ops-zebra
        sleep(1)

    if router_id_found is True:
        print("Expected active router id found in the VRF database\n")


__all__ = ["verify_show_ip_route",
           "verify_show_ipv6_route", "verify_show_rib",
           "route_and_nexthop_in_show_running_config",
           "route_and_nexthop_not_in_show_running_config",
           "verify_route_in_show_kernel_route",
           "verify_active_router_id_in_vrf",
           ZEBRA_DEFAULT_TIMEOUT,
           ZEBRA_TEST_SLEEP_TIME]
