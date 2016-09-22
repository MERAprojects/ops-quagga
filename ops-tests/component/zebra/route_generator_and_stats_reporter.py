#!/usr/bin/python

# (c) Copyright 2016 Hewlett Packard Enterprise Development LP
#
# GNU Zebra is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2, or (at your option) any
# later version.
#
# GNU Zebra is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Zebra; see the file COPYING.  If not, write to the Free
# Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.

from time import sleep

IPV4_MIN_OCTET_NUMBER = 1
IPV4_MAX_OCTET_NUMBER = 200
IPV6_MIN_OCTET_NUMBER = 1
IPV6_MAX_OCTET_NUMBER = 9999


def get_static_route_dict(route_count, if_ipv4, nexthop):

    if route_count is None:
        return None

    if if_ipv4 is None:
        return None

    if route_count <= 0:
        return None

    if nexthop is None:
        return None

    routelist = []

    if if_ipv4 is True:
        min_number = IPV4_MIN_OCTET_NUMBER
        max_number = IPV4_MAX_OCTET_NUMBER + 1
    else:
        min_number = IPV6_MIN_OCTET_NUMBER
        max_number = IPV6_MAX_OCTET_NUMBER + 1

    total_routes = 0
    for first_octet in range(min_number, max_number):
        for second_octet in range(min_number, max_number):
            for third_octet in range(min_number, max_number):
                for fourth_octet in range(min_number, max_number):

                    if total_routes >= route_count:
                        break

                    if if_ipv4 is True:
                        prefix_string = "%s.%s.%s.%s/32" % (first_octet,
                                                            second_octet,
                                                            third_octet,
                                                            fourth_octet)
                    else:
                        prefix_string = "%s:%s:%s:%s::1/128" % (first_octet,
                                                                second_octet,
                                                                third_octet,
                                                                fourth_octet)

                    if prefix_string is None:
                        continue

                    routedict = dict()

                    routedict['Prefix'] = prefix_string
                    routedict['Nexthop'] = nexthop
                    routedict["show ip route"] = False
                    routedict["kernel ip route"] = False
                    routedict["running-config"] = False

                    routelist.append(routedict)

                    total_routes = total_routes + 1

                if total_routes >= route_count:
                    break

            if total_routes >= route_count:
                break

        if total_routes >= route_count:
            break

    return routelist


def print_route_list_stats(route_list, time_elapsed, time_test_snapshot,
                           trigger_reason):

    if route_list is None:
        print("Route list is None")
        return(None)

    if time_elapsed is None:
        print("Time is None")
        return(None)

    if time_test_snapshot is None:
        print("The final time snapshot is missing")
        return(None)

    if trigger_reason is None:
        print("The trigger reason is None")
        return(None)

    num_route_set_selected_ovsdb = 0
    num_route_in_kernel = 0
    num_route_in_ovsdb = 0

    for route in route_list:
        if route['show ip route'] is True:
            num_route_set_selected_ovsdb = num_route_set_selected_ovsdb + 1

        if route['kernel ip route'] is True:
            num_route_in_kernel = num_route_in_kernel + 1

        if route['running-config'] is True:
            num_route_in_ovsdb = num_route_in_ovsdb + 1

    print("The time elapsed since the trigger " + trigger_reason + " is "
          + str(time_elapsed) + " seconds")
    print("Number of routes in show ip route output are: "
          + str(num_route_set_selected_ovsdb))
    print("Number of routes in kernel are: "
          + str(num_route_in_kernel))
    print("Number of routes in show running-config output are: "
          + str(num_route_in_ovsdb))

    perf_stat_dict = None

    if time_test_snapshot <= time_elapsed:
        perf_stat_dict = dict()
        perf_stat_dict['TotalShowIpRoute'] = num_route_set_selected_ovsdb
        perf_stat_dict['TotalKernelIpRoute'] = num_route_in_kernel
        perf_stat_dict['TotalShowRunning'] = num_route_in_ovsdb

    return perf_stat_dict


def update_static_route_list_with_route_status_in_show_ip_route(
                                                        show_ip_route_output,
                                                        route_list):
    if show_ip_route_output is None:
        print("show ip route output is None")
        return

    if route_list is None:
        print("The route list is None")
        return

    for route in route_list:
        route["show ip route"] = False

        if route['Prefix'] in show_ip_route_output:
            route["show ip route"] = True


def update_static_route_list_with_route_status_in_show_running(
                                                        show_running_output,
                                                        if_ipv4,
                                                        route_list):
    if show_running_output is None:
        print("show running output is None")
        return

    if route_list is None:
        print("The route list is None")
        return

    if if_ipv4 is None:
        print("Ipv4 flag is None")
        return(None)

    for route in route_list:
        route["running-config"] = False

        if if_ipv4 is True:
            show_running_config_string = \
                "ip route %s %s" % (route['Prefix'], route['Nexthop'])
        else:
            show_running_config_string = \
                "ipv6 route %s %s" % (route['Prefix'], route['Nexthop'])

        if show_running_config_string in show_running_output:
            route["running-config"] = True


def update_static_route_list_with_route_status_in_kernel_ip_route(
                                                        kernel_ip_route_output,
                                                        route_list):
    if kernel_ip_route_output is None:
        print("kernel ip route output is None")
        return

    if route_list is None:
        print("The route list is None")
        return

    for route in route_list:
        route["kernel ip route"] = False

        [prefix, masklen] = route["Prefix"].split('/')

        if prefix in kernel_ip_route_output:
            route["kernel ip route"] = True


def capture_output_samples_and_generate_perf_stats(switch,
                                                   route_list,
                                                   trigger_name,
                                                   if_ipv4,
                                                   total_time,
                                                   sampling_time,
                                                   time_test_snapshot):
    if switch is None:
        print("Switch is None")
        return(None)

    if route_list is None:
        print("The route list is None")
        return(None)

    if trigger_name is None:
        print("The trigger name is None")
        return(None)

    if if_ipv4 is None:
        print("Ipv4 flag is None")
        return(None)

    if total_time <= 0 or sampling_time <= 0:
        print("Invalid time values for total time and sampling time")
        return(None)

    if time_test_snapshot is None:
        print("The final time snapshot is missing")
        return(None)

    print("Capturing route output samples..")

    time_inc = 0
    index = 0
    show_ip_route_dump_list = []
    kernel_ip_route_dump_list = []
    show_running_dump_list = []

    while time_inc <= total_time:

        if if_ipv4 is True:
            show_ip_route = switch("show ip route")
            kernel_ip_route = switch("ip netns exec swns ip route",
                                     shell='bash')
        else:
            show_ip_route = switch("show ipv6 route")
            kernel_ip_route = switch("ip netns exec swns ip -6 route",
                                     shell='bash')

        show_running = switch("show running-config")

        show_ip_route_dump_list.append(show_ip_route)
        kernel_ip_route_dump_list.append(kernel_ip_route)
        show_running_dump_list.append(show_running)

        sleep(sampling_time)
        time_inc = time_inc + sampling_time

    print("Finsih capturing output samples")

    time_inc = 0
    index = 0
    final_route_perf_stat_dict = None
    while time_inc <= total_time:

        update_static_route_list_with_route_status_in_show_ip_route(
            show_ip_route_dump_list[index], route_list)
        update_static_route_list_with_route_status_in_kernel_ip_route(
            kernel_ip_route_dump_list[index], route_list)

        if if_ipv4 is True:
            update_static_route_list_with_route_status_in_show_running(
                show_running_dump_list[index], True,
                route_list)
        else:
            update_static_route_list_with_route_status_in_show_running(
                show_running_dump_list[index], False,
                route_list)

        route_perf_stat_dict = print_route_list_stats(route_list, time_inc,
                                                      time_test_snapshot,
                                                      trigger_name)

        if route_perf_stat_dict is not None:
            final_route_perf_stat_dict = route_perf_stat_dict

        time_inc = time_inc + sampling_time
        index = index + 1

    return final_route_perf_stat_dict


__all__ = ["get_static_route_dict", "print_route_list_stats",
           "update_static_route_list_with_route_status_in_show_ip_route",
           "update_static_route_list_with_route_status_in_kernel_ip_route",
           "update_static_route_list_with_route_status_in_show_running",
           "capture_output_samples_and_generate_perf_stats"]
