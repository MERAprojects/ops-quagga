# (C) Copyright 2016 Hewlett Packard Enterprise Development LP
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#


"""
OpenSwitch Test Utility for BGP
"""

# from pytest import set_trace
import re
from time import sleep
from functools import wraps

def find_device_label(sw, interface):
    assert interface in sw.ports.values()
    for key, value in sw.ports.items():
        if value == interface:
            return key

def turn_on_interface(sw, interface):
    port = find_device_label(sw, interface)
    with sw.libs.vtysh.ConfigInterface(port) as ctx:
        ctx.no_shutdown()


def turn_off_interface(sw, interface):
    port = find_device_label(sw, interface)
    with sw.libs.vtysh.ConfigInterface(port) as ctx:
        ctx.shutdown()


def validate_turn_on_interfaces(sw, interfaces):
    for intf in interfaces:
        port = find_device_label(sw, intf)
        output = sw.libs.vtysh.show_interface(port)
        assert output['interface_state'] == 'up',\
            "Interface state for " + intf + " is down"


def validate_turn_off_interfaces(sw, interfaces):
    for intf in interfaces:
        port = find_device_label(sw, intf)
        output = sw.libs.vtysh.show_interface(port)
        assert output['interface_state'] == 'down',\
            "Interface state for " + port + "is up"


def verify_turn_off_interfaces(sw, intf_list):
    @retry_wrapper(
        'Ensure interfaces are turn off',
        'Interfaces not yet ready',
        5,
        60)
    def check_interfaces(sw):
        validate_turn_off_interfaces(sw, intf_list)
    check_interfaces(sw)

def get_device_mac_address(sw, interface):
    cmd_output = sw('ifconfig'.format(**locals()),
                    shell='bash_swns')
    mac_re = (r'' + interface + '\s*Link\sencap:Ethernet\s*HWaddr\s'
              r'(?P<mac_address>([0-9A-Fa-f]{2}[:-]){5}'
              r'[0-9A-Fa-f]{2})')

    re_result = re.search(mac_re, cmd_output)
    assert re_result

    result = re_result.groupdict()
    print(result)

    return result['mac_address']


def tcpdump_capture_interface(sw, interface_id, wait_time):
    cmd_output = sw('tcpdump -D'.format(**locals()),
                    shell='bash_swns')
    interface_re = (r'(?P<linux_interface>\d)\.' + interface_id +
                    r'\s[\[Up, Running\]]')
    re_result = re.search(interface_re, cmd_output)
    assert re_result
    result = re_result.groupdict()

    sw('tcpdump -ni ' + result['linux_interface'] +
        ' -e ether proto ' + LACP_PROTOCOL + ' -vv'
        '> /tmp/interface.cap 2>&1 &'.format(**locals()),
        shell='bash_swns')

    sleep(wait_time)

    sw('killall tcpdump'.format(**locals()),
        shell='bash_swns')

    capture = sw('cat /tmp/interface.cap'.format(**locals()),
                 shell='bash_swns')

    sw('rm /tmp/interface.cap'.format(**locals()),
       shell='bash_swns')

    return capture


def get_info_from_packet_capture(capture, switch_side, sw_mac):
    packet_re = (r'[\s \S]*' + sw_mac.lower() + '\s\>\s' + LACP_MAC_HEADER +
                 r'\,[\s \S]*'
                 r'' + switch_side + '\sInformation\sTLV\s\(0x\d*\)'
                 r'\,\slength\s\d*\s*'
                 r'System\s(?P<system_id>([0-9A-Fa-f]{2}[:-]){5}'
                 r'[0-9A-Fa-f]{2})\,\s'
                 r'System\sPriority\s(?P<system_priority>\d*)\,\s'
                 r'Key\s(?P<key>\d*)\,\s'
                 r'Port\s(?P<port_id>\d*)\,\s'
                 r'Port\sPriority\s(?P<port_priority>\d*)')

    re_result = re.search(packet_re, capture)
    assert re_result

    result = re_result.groupdict()

    return result


def tcpdump_capture_interface_start(sw, interface_id):
    cmd_output = sw('tcpdump -D'.format(**locals()),
                    shell='bash_swns')
    interface_re = (r'(?P<linux_interface>\d)\.' + interface_id +
                    r'\s[\[Up, Running\]]')
    re_result = re.search(interface_re, cmd_output)
    assert re_result
    result = re_result.groupdict()

    cmd_output = sw(
        'tcpdump -ni ' + result['linux_interface'] +
        ' -e ether proto ' + LACP_PROTOCOL + ' -vv'
        '> /tmp/ops_{interface_id}.cap 2>&1 &'.format(**locals()),
        shell='bash_swns'
    )

    res = re.compile(r'\[\d+\] (\d+)')
    res_pid = res.findall(cmd_output)

    if len(res_pid) == 1:
        tcpdump_pid = int(res_pid[0])
    else:
        tcpdump_pid = -1

    return tcpdump_pid


def tcpdump_capture_interface_stop(sw, interface_id, tcpdump_pid):
    sw('kill {tcpdump_pid}'.format(**locals()),
        shell='bash_swns')

    capture = sw('cat /tmp/ops_{interface_id}.cap'.format(**locals()),
                 shell='bash_swns')

    sw('rm /tmp/ops_{interface_id}.cap'.format(**locals()),
       shell='bash_swns')

    return capture


def get_counters_from_packet_capture(capture):
    tcp_counters = {}

    packet_re = (r'(\d+) (\S+) (received|captured|dropped)')
    res = re.compile(packet_re)
    re_result = res.findall(capture)

    for x in re_result:
        tcp_counters[x[2]] = int(x[0])

    return tcp_counters


def set_debug(sw):
    sw('ovs-appctl -t ops-lacpd vlog/set dbg'.format(**locals()),
       shell='bash')


def create_vlan(sw, vlan_id):
    with sw.libs.vtysh.ConfigVlan(vlan_id) as ctx:
        ctx.no_shutdown()


def validate_vlan_state(sw, vlan_id, state):
    output = sw.libs.vtysh.show_vlan(vlan_id)
    assert output[vlan_id]['status'] == state,\
        'Vlan is not in ' + state + ' state'


def delete_vlan(sw, vlan):
    with sw.libs.vtysh.Configure() as ctx:
        ctx.no_vlan(vlan)
    output = sw.libs.vtysh.show_vlan()
    for vlan_index in output:
        assert vlan != output[vlan_index]['vlan_id'],\
            'Vlan was not deleted'


def associate_vlan_to_l2_interface(
    sw,
    vlan_id,
    interface,
    vlan_type='access'
):
    port = find_device_label(sw, interface)
    with sw.libs.vtysh.ConfigInterface(port) as ctx:
        ctx.no_routing()
        if vlan_type == 'access':
            ctx.vlan_access(vlan_id)
    output = sw.libs.vtysh.show_vlan(vlan_id)
    assert interface in output[vlan_id]['ports'],\
        'Vlan was not properly associated with Interface'


def check_connectivity_between_hosts(h1, h1_ip, h2, h2_ip,
                                     ping_num=5, success=True):
    ping = h1.libs.ping.ping(ping_num, h2_ip)
    if success:
        # Assuming it is OK to lose 1 packet
        assert ping['transmitted'] == ping_num <= ping['received'] + 1,\
            'Ping between ' + h1_ip + ' and ' + h2_ip + ' failed'
    else:
        assert ping['received'] == 0,\
            'Ping between ' + h1_ip + ' and ' + h2_ip + ' success'

    ping = h2.libs.ping.ping(ping_num, h1_ip)
    if success:
        # Assuming it is OK to lose 1 packet
        assert ping['transmitted'] == ping_num <= ping['received'] + 1,\
            'Ping between ' + h2_ip + ' and ' + h1_ip + ' failed'
    else:
        assert ping['received'] == 0,\
            'Ping between ' + h2_ip + ' and ' + h1_ip + ' success'


def check_connectivity_between_switches(s1, s1_ip, s2, s2_ip,
                                        ping_num=5, success=True):
    ping = s1.libs.vtysh.ping_repetitions(s2_ip, ping_num)
    if success:
        assert ping['transmitted'] == ping['received'] == ping_num,\
            'Ping between ' + s1_ip + ' and ' + s2_ip + ' failed'
    else:
        assert len(ping.keys()) == 0, \
            'Ping between ' + s1_ip + ' and ' + s2_ip + ' success'

    ping = s2.libs.vtysh.ping_repetitions(s1_ip, ping_num)
    if success:
        assert ping['transmitted'] == ping['received'] == ping_num,\
            'Ping between ' + s2_ip + ' and ' + s1_ip + ' failed'
    else:
        assert len(ping.keys()) == 0,\
            'Ping between ' + s2_ip + ' and ' + s1_ip + ' success'


def is_interface_up(sw, interface):
    interface_status = sw('show interface {interface}'.format(**locals()))
    lines = interface_status.split('\n')
    for line in lines:
        if "Admin state" in line and "up" in line:
            return True
    return False


def is_interface_down(sw, interface):
    interface_status = sw('show interface {interface}'.format(**locals()))
    lines = interface_status.split('\n')
    for line in lines:
        if "Admin state" in line and "up" not in line:
            return True
    return False

def verify_vlan_full_state(sw, vlan_id, interfaces=None, status='up'):
    vlan_status = sw.libs.vtysh.show_vlan()
    vlan_str_id = str(vlan_id)
    assert vlan_str_id in vlan_status,\
        'VLAN not found, Expected: {}'.format(vlan_str_id)
    assert vlan_status[vlan_str_id]['status'] == status,\
        'Unexpected VLAN status, Expected: {}'.format(status)
    if interfaces is None:
        assert len(vlan_status[vlan_str_id]['ports']) == 0,\
            ''.join(['Unexpected number of interfaces in VLAN',
                     '{}, Expected: 0'.format(vlan_id)])
    else:
        assert len(vlan_status[vlan_str_id]['ports']) == len(interfaces),\
            'Unexpected number of interfaces in VLAN {}, Expected: {}'.format(
            vlan_id,
            len(interfaces)
        )
        for interface in interfaces:
            port = find_device_label(sw, interface)
            assert port not in vlan_status[vlan_str_id],\
                'Interface not found in VLAN {}, Expected {}'.format(
                vlan_id,
                port
            )

def retry_wrapper(
    init_msg,
    soft_err_msg,
    time_steps,
    timeout,
    err_condition=None
):
    if err_condition is None:
        err_condition = AssertionError

    def actual_retry_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(init_msg)
            cont = 0
            while cont <= timeout:
                try:
                    func(*args, **kwargs)
                    return
                except err_condition:
                    print(soft_err_msg)
                    if cont < timeout:
                        print('Waiting {} seconds to retry'.format(
                            time_steps
                        ))
                        sleep(time_steps)
                        cont += time_steps
                        continue
                    print('Retry time of {} seconds expired'.format(
                        timeout
                    ))
                    raise
        return wrapper
    return actual_retry_wrapper


def verify_turn_on_interfaces(sw, intf_list):
    @retry_wrapper(
        'Ensure interfaces are turn on',
        'Interfaces not yet ready',
        5,
        60)
    def check_interfaces(sw):
        validate_turn_on_interfaces(sw, intf_list)
    check_interfaces(sw)

def verify_connectivity_between_hosts(h1, h1_ip, h2, h2_ip, success=True):
    @retry_wrapper(
        'Ensure connectivity between hosts',
        'LAG not yet ready',
        5,
        40)
    def check_ping(h1, h1_ip, h2, h2_ip, success):
        check_connectivity_between_hosts(h1, h1_ip, h2, h2_ip, success=success)
    check_ping(h1, h1_ip, h2, h2_ip, success=success)


def verify_connectivity_between_switches(s1, s1_ip, s2, s2_ip, success=True):
    @retry_wrapper(
        'Ensure connectivity between switches',
        'LAG not yet ready',
        5,
        40)
    def check_ping(s1, s1_ip, s2, s2_ip, success):
        check_connectivity_between_switches(s1, s1_ip, s2, s2_ip,
                                            success=success)
    check_ping(s1, s1_ip, s2, s2_ip, success=success)
