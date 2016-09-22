/*
 * (c) Copyright 2015 Hewlett Packard Enterprise Development LP
 *
 * This file is part of GNU Zebra.
 *
 * GNU Zebra is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the
 * Free Software Foundation; either version 2, or (at your option) any
 * later version.
 *
 * GNU Zebra is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with GNU Zebra; see the file COPYING.  If not, write to the Free
 * Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
 * 02111-1307, USA.
 */

#ifndef ZEBRA_OVSDB_IF_H
#define ZEBRA_OVSDB_IF_H 1

#include "uuid.h"
#include "shash.h"
#include "hmap.h"
#include "vswitch-idl.h"

/*
 * Zebra route install and un-install codes
 */
#define ZEBRA_RT_UNINSTALL             0
#define ZEBRA_RT_INSTALL               1

/*
 * Zebra next-hop install and un-install codes
 */
#define ZEBRA_NH_UNINSTALL             ZEBRA_RT_UNINSTALL
#define ZEBRA_NH_INSTALL               ZEBRA_RT_INSTALL

/*
 * Max IPv4 and IPv6 mask length
 */
#define ZEBRA_MAX_IPV4_MASKLEN         32
#define ZEBRA_MAX_IPV6_MASKLEN         128

/*
 * Connected route administration distance
 */
#define ZEBRA_CONNECTED_ROUTE_DISTANCE 0

/*
 * Zebra max string length
 */
#define ZEBRA_MAX_STRING_LEN           256

/*
 * TODO: Remove this macro once the macro is available through OVSDB IDL
 *       libraries.
 */
#define OVSREC_IDL_GET_TABLE_ROW_UUID(ovsrec_row_struct) \
                             (ovsrec_row_struct->header_.uuid)

#define MAX_ZEBRA_TXN_COUNT 100

extern bool zebra_cleanup_kernel_after_restart;
extern char* zebra_l3_port_cache_actions_str[];

struct ipv4v6_addr
{
  union {
    struct in_addr ipv4_addr;
    struct in6_addr ipv6_addr;
  } u;
};

struct zebra_route_key
{
  struct ipv4v6_addr prefix;
  int64_t prefix_len;
  struct ipv4v6_addr nexthop;
  char ifname[IF_NAMESIZE+1];
  /* OPS_TODO: add vrf support */
};

struct zebra_route_del_data
{
  struct route_node *rnode;
  struct rib *rib;
  struct nexthop *nexthop;
};

/*
 * Type of port actions. The action done on the port is stored in the
 * cached L3 port node.
 */
enum zebra_l3_port_cache_actions
{
  ZEBRA_L3_PORT_NO_CHANGE,
  ZEBRA_L3_PORT_ADD,
  ZEBRA_L3_PORT_L3_CHANGED_TO_L2,
  ZEBRA_L3_PORT_DELETE,
  ZEBRA_L3_PORT_UPADTE_IP_ADDR,
  ZEBRA_L3_PORT_ACTIVE_STATE_CHANGE
};

/*
 * The L3 port structure. This structure is used to store the
 * L3 ovsrec_port data. We need to cache this data in order to
 * handle triggers like "no routing" on a port where the port
 * entry in the port table loses all the IP/IPv6 addresses. We
 * use the cached IP addresses to clean up the kernel and the
 * update the OVSDB tables appropriately.
 */
struct zebra_l3_port
{
  char *port_name;                       /* name of the port */
  char *ip4_address;                     /* Primary IP address on port */
  char *ip6_address;                     /* Primary IPv6 address on port */
  struct shash ip4_address_secondary;    /* Hash for the secondary
                                            IP addresses. The key is the
                                            IP address in string format and
                                            value is IP address in string
                                            format */
  struct shash ip4_connected_routes_uuid;/* Hash for the UUIDs for the
                                            connected routes programmed by
                                            zebra for the IP addresses on the
                                            port. The key is connected route
                                            prefix string and the value is
                                            OVSDB connected route UUID. */
  struct shash ip6_address_secondary;    /* Hash for the secondary
                                            IPv6 addresses. The key is the
                                            IPv6 address in string format and
                                            value is IPv6 address in string
                                            format */
  struct shash ip6_connected_routes_uuid;/* Hash for the UUIDs for the
                                            connected routes programmed by
                                            zebra for the IPv6 addresses on the
                                            port. The key is connected route
                                            prefix string and the value is
                                            OVSDB connected route UUID.*/
  struct uuid ovsrec_port_uuid;          /* UUID to the OVSDB port entry */
  enum zebra_l3_port_cache_actions port_action;
                                         /* Action performed on the
                                            port */
  bool if_active;                        /* If the port is still active in
                                            event of shut/un-shut triggers
                                            on the resolving interfaces.*/
};

/* Local Neighbor struct to store in hash-map and handle add/modify/deletes */
struct neighbor {
  struct hmap_node node;               /* node pointer to walk hash */
  char *ip_address;                    /* IP of the neighbor */
  bool in_use_by_routes;               /* in use by routes flag */
  struct uuid idl_row_uuid;            /* reference to idl uuid */
  bool is_ipv6_addr;                   /* Quick flag for type */
  struct shash routes_shash;           /* shash of routes referring this
                                       ** neighbor */
};

/* Setup zebra to connect with ovsdb and daemonize. This daemonize is used
 * over the daemonize in the main function to keep the behavior consistent
 * with the other daemons in the OpenSwitch system
 */
void zebra_ovsdb_init (int argc, char *argv[]);

/* When the daemon is ready to shut, delete the idl cache
 * This happens with the ovs-appctl exit command.
 */
void zebra_ovsdb_exit (void);

/* Initialize and integrate the ovs poll loop with the daemon */
void zebra_ovsdb_init_poll_loop (struct zebra_t *zebrad);

void zebra_delete_route_nexthop_port_from_db (struct rib *route,
                                              char* port_name);
void zebra_delete_route_nexthop_addr_from_db (struct rib *route,
                                              char* port_name);
void zebra_route_list_add_data (struct route_node *rnode,
                                struct rib *rib_p,
                                struct nexthop *nhop);
void zebra_update_selected_nh (struct route_node *rn,
                               struct rib *route,
                               char* port_name,
                               char* nh_addr,
                               int if_selected);
void zebra_update_selected_route_nexthops_to_db (
                                            struct route_node *rn,
                                            struct rib *route,
                                            int action);
int
zebra_ovs_update_selected_route (const struct ovsrec_route *ovs_route,
                                 bool *selected);
void cleanup_kernel_routes_after_restart();
extern int zebra_create_txn (void);
extern int zebra_finish_txn (bool);

#endif /* ZEBRA_OVSDB_IF_H */
