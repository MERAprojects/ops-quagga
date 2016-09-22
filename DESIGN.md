#High level design of OPS-Quagga-BGP
============================
#BGP overview

BGP can be classified into the following types:
-eBGP--Acts as an exterior gateway protocol to exchange large amount of routing information among routers and switches in different autonomous systems (AS).
-iBGP--Exchanges routing information within an AS, typically to distribute exterior routing information across an AS while leaving interior routing to a dedicated IGP.
-MPLS VPN--Is a BGP VPN based on RFC 4364, "BGP/MPLS IP Virtual Private Networks (VPNs)", to ensure that VPNs remain private and isolated from public internet and other VPNs. It is known as BGP/MPLS VPNs because BGP is used to distribute VPN routing information across the provider backbone, and MPLS is used to forward VPN traffic across the backbone.

Unlike IGP that does neighbor auto-discovery, eBGP acquires its peers by configuration.

eBGP establishes sessions with its peers. On successfully establishing a session with a neighbor, eBGP starts exchanging routing information, and updates its local RIB accordingly.

eBGP then chooses the best path to a destination from among the paths available in the eBGP RIB. The best path is then sent to the global RIB for forwarding, and is also advertised to its other eBGP peers.

As a result, eBGP selects best-paths through an extended form of distributed Bellman-Ford.

Each eBGP speaker selects a set of path vectors according to what is locally available, and updates its neighbors accordingly, converging on a reachable set of paths that are available to the eBGP speaker.

eBGP frequently uses routing policy to control routing information exchanges. Quagga routing policy is in the form of a library that includes a prefix list, an access list, and a route map.

By matching prefixes, destination addresses, tags, communities, and as-paths, Quagga routing policy can influence eBGP decisions on both receiving and advertising routes.

By using the Quagga route map, eBGP can modify path attributes before route selection to influence routing decisions or before advertising it to a peer (refer to Figure 5).

OpenSwitch eBGP supports BGP version 4 that supports for Ipv4, IPv6, unicast, multicast, and capability negotiations. OpenSwitch eBGP also supports 4 byte AS numbers.

Because eBGP establishes its session on top of TCP which provides ordered, reliable, secured transport, it is freed from implementing update fragmentation, re-transmission, acknowledgment, and sequencing. Unlike IGP periodic flooding, eBGP is able to do incremental updates as the routing table changes.

This document mainly describes eBGP design in OpenSwitch Architecture by using large-scale data centers as an example (Figure 1). eBGP major internal data structures is also documented in this document. For the interactions among eBGP and other OpenSwitch modules, refer to BGP_feature_design.md (http://www.openswitch.net/documents/dev/ops/docs/BGP_feature_design.md)

#Responsibilities
---------------
eBGP is responsible for providing dynamic routing for routers and switches that are usually deployed in ISP, enterprise, campus, and large scale data center environments. eBGP can be deployed alone or with other protocols such as OSPF, ISIS, MPLS and so on.

#Design choice
--------------
The current goal is to provide simple and stable routing for large scale data centers that support over 100,000 servers. In a typical large data center, a common choice of topology is a Clos (see 5-stage Clos as illustrated on Figure 1). ECMP is the fundamental load-sharing mechanism used by a Clos topology. eBGP is chosen because it provides multipath and multi-hop features, and is simple to operate.

#eBGP route selection process
eBGP selects the best routes according to the order shown Table 1.


```ditaa

          ##Table 1 eBGP route selection

     Check Order           |  Favor
===============================================================================
     1. Weight             |  highest
     2. Local preference   |  highest
     3. Local route        |  static, aggregate, or redistribute
     4. AS path length     |  shortest
     5. Origin             |  IGP > EGP > INCOMPLETE
     6. MED                |  Lowest (default: missing as lowest)
     7. Peer type          |  eBGP > IBGP
     8. IGP metric         |  Lowest
     9. Router-ID          |  Lowest (tie breaker)
     10. Cluster length    |  Shortest
     11. Neighbor address  |  Lowest
---------------------------|----------------------------------------------------

```

#eBGP multipath, equal-cost load balancing
Figure 1 shows the 5-stage Clos topology and the ECMP paths existing in this topology.

```ditaa

                                  Tier 1
                                 +-----+
                                 | DEV |
                              +->|  1  |--+
                              |  +-----+  |
                      Tier 2  |           |   Tier 2
        Tier 3       +-----+  |  +-----+  |  +-----+      Tier 3
       +------------>| DEV |--+->| DEV |--+--|     |-------------+
       |       +-----|  B  |--+  |  2  |  +--|  E  |-----+       |
       |       |     +-----+     +-----+     +-----+     |       |
       |       |                                         |       |
       |       |     +-----+     +-----+     +-----+     |       |
       | +-----+---->| DEV |--+  | DEV |  +--|     |-----+-----+ |
       | |     | +---|  C  |--+->|  3  |--+--|  F  |---+ |     | |
       | |     | |   +-----+  |  +-----+  |  +-----+   | |     | |
       | |     | |            |           |            | |     | |
     +-----+ +-----+          |  +-----+  |          +-----+ +-----+
     | DEV | |     |          +->| DEV |--+          |     | |     |
     |  A  | |     |             |  4  |             |  G  | |     |
     +-----+ +-----+             +-----+             +-----+ +-----+
       | |     | |                                     | |     | |
       O O     O O            <- Servers ->            X Y     O O


     Figure 1: ECMP paths from A to X and Y in a 5-stage Clos topology

    - A--->B--->1--->E--->G
    - A--->B--->2--->E--->G
    - A--->c--->3--->F--->G
    - A--->c--->4--->F--->G

```
The eBGP multi-path implementation declares paths to be equal from an ECMP perspective if they match up with step (e) in Section 9.1.2.2 of [RFC4271] (refer to Table 1, (8)). ECMP paths have the same AS path length, but they can have the different router IDs, or different AS path values. Figure 1 displays that this topology has four ECMP paths from source A to destination X. Traffic sending from A to X will load balance to device B and device C, at device B traffic will load balance to device 1 and device 2.

By default, multipath is disabled. To enable multipath, the "max-path" parameter needs to be configured. For load-balancing applications, the same prefix can be advertised from multiple Tier-3 switches. This prefix needs to have eBGP paths with different AS PATH attribute values, but with the same AS path attribute lengths.

To support load-sharing over the paths, the "AS PATH multipath relax" parameter needs to be configured separately for some implementations. This extra configuration enables ECMP across different neighboring ASNs. In OpenSwitch, this is automatically enabled when the max-path parameter is configured.

When using eBGP multipath, the link failure is minimized. For example, if a link between Tier-1 and Tier-2 fails, the local node can simply update its ECMP group and the Tier-3 devices will not be involved in the re-convergence process.

Relying on eBGP Keepalive packets solely may result in high convergence delays, in the order of multiple seconds (minimum eBGP hold timer value is 3 seconds). However, in modern data centers, fiber link failure can be detected in milliseconds.

eBGP implementations with the "fast fail-over" feature can shut down local eBGP peering sessions immediately in response to a "link down" event for the outgoing interface and subsequently triggers an eBGP re-convergence quickly. (Refer to Table 2 for multipath columns in the OVSDB BGP Router table.)

eBGP can in some certain circumstances get into unstable, oscillating behavior. This issue can occur when there is a non-transitive order of preference between different paths AND path-hiding mechanisms are used. Non-transitive ordering of route preferences can occur with interactions between MED and IGP costs, and can also occur with IGP costs if the eBGP topology is not aligned with the IGP topology. The common path-hiding mechanism involved in oscillation is iBGP route-reflection. eBGP multi-path however also has the potential to hide path information, as it aggregates routes and some, but not all (e.g. not MED) of the metrics.

Operators should satisfy themselves that their topology and configurations will meet their needs when using these features and metrics.


#Multihop eBGP
Multihop eBGP makes it possible to establish a peering session with the application "controller". This allows for ECMP routing or forwarding based on application-defined forwarding paths. This requires recursive resolution of the next-hop address specified in eBGP updates to be fully supported.

#OVSDB-Schema
------------
eBGP configurations and statistics are stored in the BGP_router, and the BGP_Neighbor tables in OVSDB.
For details refer to the tables/columns in the eBGP_feature_design.md at http://www.openswitch.net/documents/dev/ops/docs/eBGP_feature_design.md.

eBGP uses the following three level hierarchical configuration schema:
-Global eBGP router
-eBGP peer group
-eBGP peer

Lower levels inherit a higher level configuration if a higher level configuration is missing, and the lower level configuration overwrites the higher level configuration if it exists at this level.

##ECMP feature related OVSDB table and column
Table 2 displays multipath parameters related to the OVSDB eBGP router.


```ditaa

    ##Table 2 OVSDB eBGP router multipath parameters

    Column               |   Purpose
=========================|======================================================
    ......               |
-------------------------|------------------------------------------------------
  maximum_paths          |   max ECMP path allowed, to enable ECMP
-------------------------|------------------------------------------------------
  fast-external-failover |   fast convergence
-------------------------|------------------------------------------------------
  multipath relax        |   allow ECMP accross different neighboring ASNs
-------------------------|------------------------------------------------------

```


#Internal structure
------------------
##eBGP FSM
eBGP uses a finite state machine (FSM) to establish a session with its peers.

Figure 2 illustrates the six FSM states and their relationships.

```ditaa

    +-------+         1           +---------------+
    |       <--------------------->               <--+
    |       |       +------+      |   CONNECT     |  |
    |       |       |  A   <------>               +--+
    |       |       |  C   |      +-------+-------+
    |       |       |  T   <--+           |
    |   I   <-------+  I   |  |           v
    |       |       |  V   +--+           | 2
    |       |       |  E   |      +-------v-------+
    |       |       |      <------>               |
    |       |       +------+      |   OPENSEND    |
    |   D   |                     |               |
    |       <--+                  +-------+-------+
    |       |  |                          |
    |       +--+                          | 3
    |       |                     +-------v-------+
    |   L   |                     |               <--+
    |       <---------------------+  OPENCONFIRM  |  |
    |       |                     |               +--+
    |       |                     +-------+-------+
    |       |                             |
    |   E   |                             | 4
    |       |                     +-------v-------+
    |       |                     |               <--+
    |       <---------------------+  ESTABLISHED  |  |
    +-------+                     |               +--+
                                  +---------------+

             Figure 2, eBGP FSM

```

There are six FSM states. The first state is "Idle" state. In the "Idle" state. eBGP initializes all resources and initiates a TCP connection to the peer.

In the second state or the "Connect" state, the router waits for the TCP connection to complete and transitions to the third state or the "OpenSend" state if the TCP connection is successful.

In the fourth or "OpenSent" state, the router sends an Open message and waits for one in return in order to transition to the fifth or the "OpenConfirm" state.

In the "OpenConfirm" state, keepalive messages are exchanged and, upon a successful receipt of a keepalive message, the router is transferred  to the sixth and last "Established" state.

The "Established"state is the eBGP normal operational state.

During the session establishing process, if a pair of eBGP speakers try simultaneously to establish an eBGP connection with each other, then two parallel connections might be formed. If the source IP address used by one of these connections is the same as the destination IP address used by the other, and the destination IP address used by the first connection is the same as the source IP address used by the other, connection collision has occurred. In the event of connection collision, one of the connections MUST be closed.

If a connection collision occurs with an existing eBGP connection that is in Established states, the connection in Established state is preserved and the newly created connection is closed.

If a collision occurs with an existing eBGP connection in OpenConfirm or OpenSend state, the eBGP Identifier of the local system is compared to the eBGP Identifier of the remote system (as specified in the OPEN message), the eBGP session with the lower-valued Identifier will be closed.

A connection collision cannot be detected with connections that are in Idle, or Connect, or Active states.


##eBGP local RIB
eBGP maintains a local routing table (LocRIB), where received routes from all peers are added.

A route established in eBGP does not automatically mean that it is used for forwarding. Routes in the local RIB may be advertised to other eBGP speakers.

Figure 3 shows the internal data structure of the eBGP rib.

Each route is a bgp_node that consists of a prefix, and path attributes organized as bgp_info.


```ditaa

                               2. bgp
                           +---------------------+
                           | as                  |
                           | config              |
                           | router_id           |
                           | cluster_id          |
                           | confed_id           |
                           | confed_peers        |
                           | confed_peers_cnt    |
                           |                     |
                           | t_startup           |
                           | flags               |
                           | af_flags[AFI][SAFI] |
                           | route[AFI][SAFI]    |
                           | aggregate[][]       |
                           | redist[AFI][SAFI]   |
                           | default_holdtime    |
                           | defautl_keepalive   |
     1. bgp_master         | restart_time        |          3. bgp_node
    +---------------+      | stalepath_time      |          (radix tree)
    |               |      |                     |         +-------------+
    | bgp (list) ---+----->| peer (list)         |         | p           |
    |               |      | group (list)        |         | info (list) |-----+
    |               |      | rib[AFI][SAFI] -----+-------->| adj_in(list)|     |
    +---------------+      | rmap[AFI][SAFI]     |         | adj_o(list) |     |
                           | maxpaths[AFI][SAFI] |         | aggreagate  |     |
                           +---------------------+         +-------------+     |
                                                                               |
    +--------------------------------------------------------------------------+
    |
    |        bgp_info            attr              attr_extra
    |      +-----------+      +-----------+     +----------------+
    +----->| peer      |      | aspath    |     | mp_nh_global   |
           | attr -----+----->| community |     | mp_nh_local    |
           | extra     |      | extra ----+---->| ecommunity     |
           | mpath ----+--+   | refcnt    |     | cluster        |
           | uptime    |  |   | flag      |     | transit (TLV)  |
           | flags     |  |   | nexthop   |     | aggregator_addr|
           | type      |  |   | med       |     | orignator_id   |
           | sub_type  |  |   | local_pref|     | weight         |
           | next/prev |  |   | origin    |     | aggregator_as  |
           +-----------+  |   +-----------+     | mp_nh_len      |
                          |                     +----------------+
                          |
                          |      7. bgp_info_mpath
                          |      +-----------+
                          +----->| mp_info   |
                                 | mp_count  |
                                 | mp_attr   |
                                 +-----------+

                  Figure 3, RIB internal data structure and relationships

```

##eBGP peer
Each eBGP speaker is organized as a peer structure. The eBGP peer holds all eBGP configurations, states, timers, threads, and statistics. It also contains the eBGP filter that controls routes received from a peer and routes advertised to a peer. The eBGP peer filter consists of distribute, prefix and AS lists, and the route map. The Route map contains match and set operations and it is the technique used to modify eBGP route information (Refer to Figure 4).


```ditaa

                                      peer
                                +----------------------+
                                | config               |
                                | allowasin[AFI][SAFI] |
                                | weight               |
                                | holdtime             |
                                | keepalive            |
                                | connect              |
                                | routeadv             |
                                | v_start              |
                                | v_connect            |
                                | v_holdtime           |
                                | v_keepalive          |
                                | v_asorig             |
                                | v_routeadv           |
      2. bgp                    | v_gr_restart         |
    +---------------------+     |                      |
    |                     |     | t_read               |
    | group (list)        |     | t_start              |
    | peer (list)  -------+---->| t_write              |
    | rib[AFI][SAFI]      |     | t_connect            |
    | rmap[AFI][SAFI]     |     | t_holdtime           |
    | maxpaths[AFI][SAFI] |     | t_keepalive          |
    |                     |     | t_asorig             |
    +---------------------+     | t_routeadv           |
                                | t_gr_restart         |      bgp_synchronize
                                | t_gr_stale           |     +--------------+
                                |                      |     | update       |
                                | sync[AFI][SAFI] -----+---->| withdraw     |
                                | synctime             |     | withdraw_low |
                                | bgp                  |     +--------------+
                                | group                |
                                | as                   |
                                | sort                 |
                                | remote_d             |
                                | local_id             |
                                | status               |
                                | ostatus              |
                                | fd                   |
                                | ttl                  |
                                | ibuf                 |
                                | work                 |
                                | scratch              |
                                | obuf                 |
                                | port                 |       bgp_filter
                                | su                   |     +-------------+
                                | uptime               |     | dlist[MAX]  |
                                | notify               |     | plist[MAX]  |
                                | filter[AFI][SAFI] ---+---->| aslist[Max] |
                                | orf_plist[AFI][SAFI] |     | map[MAX] ---+---+
                                | last_reset           |     | usmap       |   |
                                | su_local             |     +-------------+   |
                                | su_remote            |                       |
                                | nexthop              |                       |
                                | afc[AFI][SAFI]       |                       |
                                | afc_nego[AFI][SAFI]  |                       |
                                | afc_recv[AFI][SAFI]  |                       |
                                | cap                  |                       |
                                | af_cap[AFI][SAFI]    |                       |
                                | flags                |                       |
                                | nsf[AFI][SAFI]       |                       |
                                | af_flags[AFI][SAFI]  |                       |
                                | sflags               |                       |
                                | af_sflags[AFI][SAFI] |                       |
                                | ...                  |                       |
                                +----------------------+                       |
                                                                               |
    +--------------------------------------------------------------------------+
    |
    |    route_map    route_map_index
    |    +------+     +------------+
    |    | name |     | pref       |
    +--->| head |---->| type       |    route_map_rule     route_map_rule_cmd
         | tail |     | exitpolicy |     +----------+     +--------------+
         | next |     | nextpref   |     | cmd  ----|---->| str          |
         | prev |     | nextrm     |     | rule_str |     | func_apply   |
         +------+     | match_list |---->| value    |     | func_compile |
                      | set_list   |     | next/prev|     | func_free    |
                      | next/prev  |     +----------+     +--------------+
                      +------------+

                 Figure 4, eBGP peer internal data structure

```

##eBGP policy or filter
The I-Filter controls which routes eBGP places in the routing tables. The O-Filter controls which routes eBGP a dvertises (see Figure 5). The route map is used to change specific route information, and controls which route is selected as the best route to reach the destination.

```ditaa

                        +-----+                       +-----+
                        |  i  |                       |  o  |
                        |     |                       |     |
    +--------------+    |  F  |     +-----------+     |  F  |    +--------------+
    |              |    |  i  |     |           |     |  i  |    |              |
    | eBGP speaker +---->  l  +----->   RIB     +----->  l  +----> eBGP speaker |
    |              |    |  t  |     |           |     |  t  |    |              |
    +--------------+    |  e  |     +-----------+     |  e  |    +--------------+
                        |  r  |                       |  r  |
                        +-----+                       +-----+

               Figure 5: Routing Policies to Control Routing Information Flow

```

##eBGP timer
eBGP employs six per-peer timers: ConnectRetryTimer, HoldTimer, KeepaliveTimer, MinASOriginationIntervalTimer, MinRouteAdvertisementIntervalTimer, and GRRestartTimer (see Table 3).


```ditaa

         ##Table 3 eBGP important timers

   Timer name            | default | Description
  =======================|=========|======================================
  ConnectRetryTimer      | 120     | Minimum connection retry interval
  HoldTimer              | 180     | Time to wait to declear connection down
  KeepaliveTimer         | 60      | Keepalive timer (1/3 holdtimer)
  AsOriginationTimer     | 15      | Minimum AS origination interval
  RouteAdvertisementTimer| 30/5    | Minimum route advertisement interval
  GRRestartTimer         |         | Maximum wait for session re-establishing

```

Hold Time: The maximum number of seconds that can elapse between the receipt of successive KEEPALIVE or UPDATE messages from the sender. The Hold Time MUST be either zero or at least three seconds.

AS origination time: MinASOriginationIntervalTimer determines the minimum amount of time that must elapse between UPDATE message successive advertisements that report changes within the advertising eBGP speaker's own autonomous systems.

Route advertisement time: Two UPDATE messages sent by an eBGP speaker to a peer that advertise feasible routes or withdrawal of unfeasible routes to some common set of destinations. These UPDATE messages MUST be separated by at least one MinRouteAdvertisementIntervalTimer.

GR restart time: Restart time is received from restarting a peer previously advertised. If the session does not get re-established within the "Restart Time", the receiving speaker MUST delete all the stale routes from the peer that it is retaining.

#References
----------
* [BGP](https://www.ietf.org/rfc/rfc4271.txt)
* [OpenSwitch](http://www.openswitch.net/documents/dev/ops-openvswitch/DESIGN)
* [Quagga](http://www.nongnu.org/quagga/docs.html)
* [Architecture](http://www.openswitch.net/documents/user/architecture)

High level design of OPS-ZEBRA
==============================
The Zebra module from Quagga project is integrated as one of the modules in OpenSwitch. To fit Zebra in the OpenSwitch architecture, Quagga Zebra is modified to register for route, next hop, interface, and port table notifications from the OVSDB and also program the best routes and next hops in the kernel for slow path routing. This document mainly focuses on the role that Zebra plays in the OpenSwitch architecture and its interaction with other modules. For the details of any other module that participates in, refer to the corresponding design page.

Responsibilities
----------------
The main responsibility of ops-zebra is to read routes and next hop configurations from the OVSDB and select the active routes and program them into the kernel.

Design choices
--------------
The Quagga open source project was chosen for layer-3 functionality in OpenSwitch, and zebra is one of the modules in the Quagga project.

Relationships to external OpenSwitch entities
---------------------------------------------
Figure 1 indicates the intermodule interaction and Zebra data flow through the OpenSwitch architecture.

```ditaa
    +------------------------+  +---------------------------+
    |  Management Daemons    |  |   Routing Protocol        |
    |  (CLI, REST, etc.)     |  |       Daemons             |
    |                        |  |   (eBGP, OSPF etc.)        |
    |                        |  |                           |
    +------------------------+  +------------+--------------+
    L3 Interfaces|               Protocol    |
    Static Routes|               Routes      |
                 |                           |
    +------------v---------------------------v---------------+
    |                                                        |
    |                        OVSDB                           |
    |                                                        |
    +----------------^---------------------------------+-----+
         Routes/     |                                 |
         Port/Intf.  |                           Routes|Intf.
         Config/Stat |                           Nbr.  |
                     |                                 |
               +-----v-----+                     +-----v------+
               |           |                     |            |
               | ops-zebra |                     | ops-switchd|
               |           |                     |            |
               +-----------+                     +-----^------+
                Route|                                 |
                     |                                 |
    +----------------v------------------------+  +-----v-----+
    |                                         |  |           |
    |                 Kernel                  <--+   ASIC    |
    |               (SlowPath)                |  | (FastPath)|
    +-----------------------------------------+  +-----------+
                  Figure 1, ZEBRA Architecture
```

OVSDB
-----
OVSDB serves as a central communication hub. All other modules communicate from and to Zebra through the OVSDB.
The OVSDB provides a single view of data to all modules in the system. All modules and the OVSDB interact through publisher and subscriber mechanisms. As a result with no direct interaction with other rmodules, Zebra is shielded from all sorts of other module issues in the system.

OPS-ZEBRA
---------
* Zebra subscribes to the OVSDB for routes, next hop, port and interface table update notifications.
* All static and protocol routes are advertised to Zebra through the OVSDB.
* Zebra takes all the advertised routes into account and internally decides the best as the active routes and set of best next hops for the routes.
* When selecting or unselecting the set of best next hops for an active route, Zebra creates a Forwarding Infor mation Base (FIB) and updates the kernel with these routes.
* These selected routes are also communicated to ops-switchd through the OVSDB for further programming in ASIC.
* To handle routes and next hop deletes when getting delete notification from the OVSDB, Zebra creates a local hash of current routes and next hops, and compares them with its local RIB/FIB storage. It also removes the deleted routes from its storage and kernel.
* On getting interface up/down notification from OVSDB, Zebra walks through all the static routes and next hops, marks them selected or unselected in the FIB, and updates the OVSDB accordingly.
* On getting interface enable/disable of layer-3 funtionality, Zebra walks through all the static routes and next hops, deletes them from the FIB, the kernel, and the OVSDB.

Static routes
-------------
Static routes are important in the absence of routing layer3 protocols or when there is a need to override the routes advertised by the routing protocols.
When the static routes are configured using one of the management interfaces such as the CLI or the REST, this information is written to the OVSDB.
A static route has a configurable distance and has a default distance of 1 (highest preference), which is the least distance compared to the routes advertised by the routing protocols. So for the same destination prefix, a static next hop is preferred and selected as an active route over any other protocol next hop. Zebra picks the static routes from the OVSDB and programs them into the kernel.

eBGP / Routing protocols
-----------------------
eBGP selects the best routes from all routes and publishes them in the OVSDB. Similary other routing protocols update the active routes in the OVSDB. Zebra gets these active protocol routes from OSVDB and programs them into the kernel.

Slow-path routing
-----------------
In OpenSwitch, slow routing refers to instances where the routing happens in the kernel. On selecting or unselecting active routes, Zebra updates the kernel with these routes.
The kernel has a copy of all the active routes and neighbors. When a transit packet is received by the kernel, the destination prefix is accessed in the kernel routing table (Forwarding Information Base, FIB) for the longest match. Once a match is found, the kernel uses the information from the route, its next hop and the corresponding ARP entry to reconstruct the packet and send it to the correct egress interface.
OpenSwitch running on a virtual machine always uses slow routing, whereas OpenSwitch running on a physical device uses slow routing on an as-needed basis when the necessary fast routing information is not available in the ASIC.

ECMP
----
Equal Cost Multipath routing is a scenario where a single prefix can have multiple "Equal Cost" route next hops. Zebra accepts static and protocol routes with multiple next hops and programs them as ECMP routes in the kernel.
For slow path routing, the default Linux kernel ECMP algorithm of load-balancing across all the next hops is used. And once the routes and next hops are programmed in ASIC, the configured ASIC ECMP algorithm is used during fast path forwarding.

The current version of Zebra supports ECMP for ipv4 routes only.

Kernel
------
The kernel receives a copy of FIB and can perform slow path forwarding compared to ASIC fast path forwarding.

UI
--
The CLI or REST is responsible for configuring IP addresses in a layer-3 interface and providing static rou tes, which are published in the OVSDB and then Zebra is notified to program the IP addresses and static routes in the kernel.

Interface
---------
Zebra gets notifications related to interface configurations, up or down state changes, and enabling or disabling of a layer-3 network on an interface.
When an interface goes down, Zebra walks through all the routes and next hops and it marks whatever routes or next hops using that interface, unselected in FIB and updates the OVSDB accordingly. And when layer-3 functionality is disabled on an interface, Zebra walks through all routes and next-hops, and deletes whatever routes or next hops using that interface, from the FIB, the kernel, and the OVSDB.

Intermodule data flows
-----------------------
Input to Zebra:
---------------
```ditaa
    - Static Routes Configurations:       UI---->OVSDB---->Zebra
    - Port/Interface ip addr/up/down:     UI/Intfd/Portd---> OVSDB ----> Zebra
    - Protocol routes:                    eBGP ---> OVSDB --->Zebra
```

Zebra output:
-------------
```ditaa
    - Best routes:                        Zebra ----> kernel
                                                |
                                                ----> OVSDB
    - show rib/route                      OVSDB ---> UI
```

OVSDB-Schema related to Zebra
-----------------------------------
The following Figure 2 describes the OVSDB tables related to Zebra.
```ditaa
    +-----------+
    |  +----+   |         +------+
    |  |VRF |   |         |  O   |
    |  |    |   |         |      |
    |  +-^--+   |         |  P   |         +-----+
    |    |      |         |      |         |     |
    |  +-+--+   |         |  S   |         |  K  |
    |  |Route   + 1       |      |         |     |
    |  |(RIB/FIB)<-------->  |   |         |  E  |
    |  +-+--+   +         |      |         |     |
    |    |      |         |  Z   | 5       |  R  |
    |  +-v--+   |         |      +--------->     |
    |  |Nexthop | 2       |  E   |         |  N  |
    |  |    +------------->      |         |     |
    |  +--+-+   |         |  B   |         |  E  |
    |     |     |         |      |         |     |
    |  +--v-+   +         |  R   |         |  L  |
    |  |Port|     3       |      |         +-----+
    |  |    +---+--------->  A   |
    |  +--+-+   |         |      |
    |     |     |         |      |
    |  +--v-+   +         | (RIB/|
    |  |Interface 4       |  FIB)|
    |  |    +---+--------->      |
    |  +----+   |         +------+
    +-----------+
              Figure 2 Zebra and OVSDB tables
```

Zebra performs the following tasks:
-Subscribes to the route table and gets notifications for any route configurations.
-Updates the route selected or unselected column.
-Subscribes to the next hop table and updates the next hop selected or unselected column.
-Subscribes to the port table and gets port layer-3 enabled or disabled configurations.
-Subscribes to the interface table and gets the interface up or down status.
-Selects the best routes and programs them into the kernel.

Zebra table summary
-------------------
The following list summarizes the purpose of each of the tables in the OpenSwitch database subscribed by Zebra. Some important columns referenced by Zebra from these tables are described after the summary table.

Table 1: Table summary
----------------------
```ditaa

    Table        |  Purpose
=================|==============================================================
    Interface    |  Interface referred by a Port.
    Nexthop      |  Nexthops for IP routes, either ip address or out going interface.
    Port         |  Port within an VRF, If  port has an IP address, then it becomes L3.
    RIB/FIB      |  Routing Information Base and Forwarding Information Base.
    VRF          |  Virtual Routing and Forwarding domain.
-----------------|--------------------------------------------------------------
```

Table 2: Column summary for interface table
-------------------------------------------
```ditaa

    Column           |   Purpose
=====================|==========================================================
    name             |   Unique name of Interface
---------------------|----------------------------------------------------------
    type             |   System/Internal
---------------------|----------------------------------------------------------
    admin_state      |   Up/Down
---------------------|----------------------------------------------------------
    link_state       |   Up/Down
---------------------|----------------------------------------------------------
```

Table 3: Column summary for nexthop table
------------------------------------------
```ditaa

    Column           |   Purpose
=====================|==========================================================
    ip_address       |   Nexthop ip address
---------------------|----------------------------------------------------------
    type             |   Nexthop type  (unicast, multicast, indirect etc)
---------------------|----------------------------------------------------------
    port             |   Reference to Port table entry, if nexthop is via an port
  ---------------------|--------------------------------------------------------
    selected         |   Active nexthop
---------------------|----------------------------------------------------------
```

Table 4: Column summary for port table
------------------------------------------
```ditaa

    Column           |   Purpose
=====================|==========================================================
    name             |   Unique name of port.
---------------------|----------------------------------------------------------
    interfaces       |   References to Interface Table
---------------------|----------------------------------------------------------
    ip4_address      |   port IPv4 address
---------------------|----------------------------------------------------------
    ip6_address      |   port IPv6 address
---------------------|----------------------------------------------------------
    ip4_address_     |   port IPv4 secondary addresses
    secondary        |
---------------------|----------------------------------------------------------
    ip6_address_     |   port IPv6 secondary addresses
    secondary        |
---------------------|----------------------------------------------------------

```

Table 5: Column summary for route table (RIB)
---------------------------------------------
```ditaa

    Column             |   Purpose
=======================|========================================================
    vrf                |   Back pointer to vrf table that this rib belong to.
-----------------------|--------------------------------------------------------
    prefix             |   Prefix/len
-----------------------|--------------------------------------------------------
    from               |   Which protocol this prefix learned
-----------------------|--------------------------------------------------------
    address_family     |   IPv4, IPv6
-----------------------|--------------------------------------------------------
    sub_address_family |   Unicast, multicast
-----------------------|--------------------------------------------------------
    distance           |   Administrative preference of this route
-----------------------|--------------------------------------------------------
                       |   n_nexthops: count of nh
    nexthops           |   Array of pointer to next hop table row
-----------------------|--------------------------------------------------------
    selected           |   Active route
-----------------------|--------------------------------------------------------
```

Table 6: Column summary for vrf table
-------------------------------------
```ditaa

    Column           |   Purpose
=====================|==========================================================
     name            |   unique vrf name.
--------------------------------------------------------------------------------
     ports           |   set of Ports pariticipating in this VRF.
---------------------|----------------------------------------------------------
```

Zebra debugging
--------------------
ovs-appctl command can be used to enable different levels of debug in ops-zebra daemon.
Sample: ovs-appctl -t ops-zebra vlog/set dbg.

Apart from standard appctl debug levels, appctl can also be used with zebra/debug
option to enable various existing debug level in zebra.

The bash command to look at the help string for the zebra debug options is:
"ovs-appctl -t ops-zebra list-commands"

The output of the command contains the following line:
zebra/debug           event|packet|send|recv|detail|kernel|rib|ribq|fpm|all|show

One example of using the command to set the zebra kernel debugs is :
"ovs-appctl -t ops-zebra zebra/debug kernel"

Restrictions
------------

Eventhough OpenSwitch supports configuration of more than 64000 routes, the system becomes unstable when the number of routes exceeds 64000 routes.
So it is recommended to restrict the number of routes to not more than 64000 routes.

References
----------
* [Reference 1 Quagga Documents](http://www.nongnu.org/quagga)
* [Reference 2 OpenSwitch L3 Architecture](http://openswitch.net/documents/user/layer3_design)
* [Reference 3 OpenSwitch Architecture](http://www.openswitch.net/documents/user/architecture)
