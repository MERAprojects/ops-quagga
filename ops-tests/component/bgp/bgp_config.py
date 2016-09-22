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


class BgpConfig(object):
    def __init__(self, asn, routerid, network):
        self.neighbors = []
        self.networks = []
        self.route_maps = []
        self.prefix_lists = []
        self.prefixList_entries = []
        self.asn = asn
        self.routerid = routerid
        self.add_network(network)

    def add_neighbor(self, neighbor):
        self.neighbors.append(neighbor)

    def add_network(self, network):
        self.networks.append(network)

    def add_route_map(self, neighbor, prefix_list, dir, action='', metric='',
                      community=''):
        self.route_maps.append([neighbor, prefix_list, dir, action,
                               metric, community])


# Prefix-list configurations
class PrefixList(object):
    def __init__(self, name, seq_num, action, network, prefix_len):
        self.name = name
        self.seq_num = seq_num
        self.action = action
        self.network = network
        self.prefix_len = prefix_len


# Prefix-list Entry configurations
class PrefixListEntry(object):
    def __init__(self, name, seq_num, action, network, prefix_len, ge, le):
        self.name = name
        self.seq_num = seq_num
        self.action = action
        self.network = network
        self.prefix_len = prefix_len
        self.ge = ge
        self.le = le
