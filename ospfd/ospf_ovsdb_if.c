/* ospf daemon ovsdb integration.
 * Copyright (C) 2015-2016 Hewlett Packard Enterprise Development LP
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
 *
 * File: ospf_ovsdb_if.c
 *
 * Purpose: Main file for integrating ospfd with ovsdb and ovs poll-loop.
 */

/* Linux headers */
#include <net/if.h>

/* Quagga lib headers */
#include <zebra.h>
#include <lib/version.h>
#include "getopt.h"
#include "command.h"
#include "thread.h"
#include "prefix.h"
#include "if.h"
#include "memory.h"
#include "shash.h"
#include "config.h"
#include "command-line.h"
#include "daemon.h"
#include "dirs.h"
#include "dummy.h"
#include "fatal-signal.h"
#include "poll-loop.h"
#include "stream.h"
#include "timeval.h"
#include "unixctl.h"
#include "table.h"
#include "openvswitch/vlog.h"
#include "openswitch-idl.h"
#include "vswitch-idl.h"
#include "coverage.h"

/* Quagga ospfd headers */
#include "ospfd/ospfd.h"
#include "ospfd/ospf_lsa.h"
#include "ospfd/ospf_lsdb.h"
#include "ospfd/ospf_nsm.h"
#include "ospfd/ospf_ism.h"
#include "ospfd/ospf_neighbor.h"
#include "ospfd/ospf_interface.h"
#include "ospfd/ospf_route.h"
#include "ospfd/ospf_zebra.h"
#include "ospfd/ospf_ovsdb_if.h"
#include "ospfd/ospf_asbr.h"
#include "ospfd/ospf_dump.h"

#define NEXTHOP_STR_SIZE 64

COVERAGE_DEFINE(ospf_ovsdb_cnt);
VLOG_DEFINE_THIS_MODULE(ospf_ovsdb_if);

extern int
ospf_area_vlink_count (struct ospf *ospf, struct ospf_area *area);

extern void
ospf_area_type_set (struct ospf_area *area, int type);

extern void
ospf_external_info_free (struct external_info *ei);

/*
 * Static Function Prototypes
 */
static void ospf_route_add_to_area_route_table (struct route_table * oart, struct prefix *p_or,
                                                struct ospf_route *or);
static void ospf_area_route_table_free (struct route_table *oart);

static char * ospf_route_path_type_string (u_char path_type);
static char * ospf_route_path_type_ext_string (u_char path_type);

/* Interface/Port change related functions */
static int ospf_interface_add_from_ovsdb (struct ovsdb_idl *idl, const struct ovsrec_vrf *ovs_vrf,
                                          const struct ovsrec_port *ovs_port);
static int ospf_interface_delete_from_ovsdb (struct ovsdb_idl *idl, const struct ovsrec_vrf *ovs_vrf,
                                             struct interface *ifp);
static int ospf_interface_update_from_ovsdb (struct ovsdb_idl *idl, const struct ovsrec_vrf *ovs_vrf,
                                             const struct ovsrec_port *ovs_port);

static void ospf_interface_state_update_from_ovsdb (struct ovsdb_idl *idl, const struct ovsrec_port *ovs_port,
                              const struct ovsrec_interface *ovs_interface, struct interface *ifp);

/* TODO This util function can be moved to common utils file */
static char * boolean2string (bool flag);

/*
 * Local structure to hold the master thread
 * and counters for read/write callbacks
 */
typedef struct ospf_ovsdb_t_ {
    int enabled;
    struct thread_master *master;

    unsigned int read_cb_count;
    unsigned int write_cb_count;
} ospf_ovsdb_t;

static ospf_ovsdb_t glob_ospf_ovs;
static struct shash all_routes = SHASH_INITIALIZER(&all_routes); //Delete on OSPF exit
unsigned char redist[ZEBRA_ROUTE_MAX] = {0};
unsigned char redist_default = 0;
static struct ovsdb_idl *idl;
static unsigned int idl_seqno;
static char *appctl_path = NULL;
static struct unixctl_server *appctl;
static int system_configured = false;

boolean exiting = false;

lsa_type lsa_str[] = {
    {OSPF_UNKNOWN_LSA,"unknown_lsa"},
    {OSPF_ROUTER_LSA,"type1_router_lsa"},
    {OSPF_NETWORK_LSA,"type2_network_lsa"},
    {OSPF_SUMMARY_LSA,"type3_abr_summary_lsa"},
    {OSPF_ASBR_SUMMARY_LSA,"type4_asbr_summary_lsa"},
    {OSPF_AS_EXTERNAL_LSA,"type5_as_external_lsa"},
    {OSPF_GROUP_MEMBER_LSA,"type6_multicast_lsa"},
    {OSPF_AS_NSSA_LSA,"type7_nssa_lsa"},
    {OSPF_EXTERNAL_ATTRIBUTES_LSA,"type8_external_attributes_lsa"},
    {OSPF_OPAQUE_LINK_LSA,"type9_opaque_link_lsa"},
    {OSPF_OPAQUE_AREA_LSA,"type10_opaque_area_lsa"},
    {OSPF_OPAQUE_AS_LSA,"type11_opaque_as_lsa"}
};

typedef struct
{
  int key;
  const char *str;
}nsm_str;

const nsm_str ospf_nsm_state[] =
{
  { NSM_DependUpon, "depend_upon" },
  { NSM_Deleted,    "deleted"    },
  { NSM_Down,       "down" },
  { NSM_Attempt,    "attempt" },
  { NSM_Init,       "init" },
  { NSM_TwoWay,     "two_way" },
  { NSM_ExStart,    "ex_start" },
  { NSM_Exchange,   "exchange" },
  { NSM_Loading,    "loading" },
  { NSM_Full,       "full" },
};

typedef nsm_str ism_str;

const ism_str ospf_ism_state[] =
{
  { ISM_DependUpon, "depend_upon" },
  { ISM_Down,       "down" },
  { ISM_Loopback,    "loopback" },
  { ISM_Waiting,       "waiting" },
  { ISM_PointToPoint,     "point_to_point" },
  { ISM_DROther,    "dr_other" },
  { ISM_Backup,   "backup_dr" },
  { ISM_DR,    "dr" },
};

const char* nssa_translate_role_str[] = {
  "never",
  "candidate",
  "always"
};

/* OPS_TODO : For fast look up now only 4 intervals are considered
   if new interval keys are added to schema this will have to change */
enum OSPF_INTERVALS_KEY_SORTED {
  OVS_OSPF_DEAD_INTERVAL_SORTED = 0,
  OVS_OSPF_HELLO_INTERVAL_SORTED,
  OVS_OSPF_RETRANSMIT_INTERVAL_SORTED,
  OVS_OSPF_TRANSMIT_DELAY_SORTED,
  OVS_OSPF_INTERVAL_SORTED_MAX
};
static int ospf_ovspoll_enqueue (ospf_ovsdb_t *ospf_ovs_g);
static int ospf_ovs_read_cb (struct thread *thread);

static void
ospfd_unixctl_show_debug_info(struct unixctl_conn *conn, int argc,
                  const char *argv[], void *aux)
{
    char *buf = NULL;
    buf = xcalloc(1, BUF_LEN);
    char err_str[MAX_ERR_STR_LEN];

    if (buf)
    {
        strcpy (buf, "--------------------------------------------\n");
        show_debug_info (buf, BUF_LEN);
        unixctl_command_reply (conn, buf);
        free (buf);
    }
    else
    {
        snprintf (err_str, sizeof(err_str),
                 "ospf daemon failed to allocate %d bytes", BUF_LEN);
        unixctl_command_reply (conn, err_str);
    }
    return;
}

/* ovs appctl dump function for this daemon
 * This is useful for debugging
 */
static void
ospf_unixctl_dump(struct unixctl_conn *conn, int argc OVS_UNUSED,
                  const char *argv[] OVS_UNUSED, void *aux OVS_UNUSED)
{
    unixctl_command_reply_error(conn, "Nothing to dump :)");
}

static void
ospf_unixctl_debug(struct unixctl_conn *conn, int argc,
                  const char *argv[], void *aux OVS_UNUSED)
{
    int status;
    char *buf = NULL;
    char err_str[MAX_ERR_STR_LEN];
    buf = xcalloc(1, BUF_LEN);

    status = ospf_debug(buf, err_str, argc, argv);
    if (status == 0)
    {
        unixctl_command_reply(conn, err_str);
    }
    else
    {
        unixctl_command_reply(conn, NULL);
    }
    return;
}

static void
ospf_unixctl_no_debug(struct unixctl_conn *conn, int argc,
                  const char *argv[], void *aux OVS_UNUSED)
{
    int status;
    char *buf = NULL;
    char err_str[MAX_ERR_STR_LEN];
    buf = xcalloc(1, BUF_LEN);

    status = ospf_no_debug(buf, err_str, argc, argv);
    if (status == 0)
    {
        unixctl_command_reply(conn, err_str);
    }
    else
    {
        unixctl_command_reply(conn, NULL);
    }
    return;
}

/* Register OSPF tables to idl */
/* Add more columns and tables if needed by tge daemon */
static void
ospf_ovsdb_tables_init()
{
   /* Add VRF columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_vrf);
    ovsdb_idl_add_column(idl, &ovsrec_vrf_col_name);
    ovsdb_idl_add_column(idl, &ovsrec_vrf_col_active_router_id);
    ovsdb_idl_add_column(idl, &ovsrec_vrf_col_ospf_routers);
    ovsdb_idl_add_column(idl, &ovsrec_vrf_col_ports);

    /* Add interface columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_interface);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_admin_state);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_duplex);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_error);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_hw_intf_config);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_link_resets);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_link_speed);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_link_state);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_mac_in_use);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_mtu);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_name);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_options);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_other_config);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_pause);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_statistics);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_status);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_type);
    ovsdb_idl_add_column(idl, &ovsrec_interface_col_user_config);

    /* Add OSPF_Router columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_ospf_router);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_areas);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_router_col_areas);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_as_ext_lsas);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_default_information);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_distance);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_lsa_timers);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_opaque_as_lsas);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_ext_ospf_routes);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_opaque_as_lsas);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_passive_interface_default);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_redistribute);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_router_id);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_status);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_spf_calculation);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_stub_router_adv);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_networks);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_router_col_other_config);

    /* Add Route columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_route);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_address_family);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_distance);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_from);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_metric);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_nexthops);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_prefix);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_protocol_private);
    ovsdb_idl_omit_alert(idl, &ovsrec_route_col_protocol_private);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_protocol_specific);
    ovsdb_idl_omit_alert(idl, &ovsrec_route_col_protocol_specific);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_selected);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_sub_address_family);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_vrf);

    /* Add Route Nexthop columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_nexthop);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_ip_address);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_ports);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_selected);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_status);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_external_ids);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_other_config);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_type);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_weight);

    /* Add Port columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_port);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_admin);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_hw_config);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_interfaces);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_ip4_address);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_ip4_address_secondary);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_mac);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_name);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_ospf_intervals);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_ospf_if_out_cost);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_ospf_priority);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_ospf_if_type);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_ospf_auth_type);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_ospf_auth_text_key);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_ospf_auth_md5_keys);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_ospf_mtu_ignore);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_other_config);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_statistics);
    ovsdb_idl_add_column(idl, &ovsrec_port_col_status);

    /* Add OSPF_Area columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_ospf_area);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_abr_summary_lsas);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_area_type);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_nssa_translator_role);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_other_config);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_ospf_area_summary_addresses);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_statistics);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_area_col_statistics);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_status);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_area_col_status);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_asbr_summary_lsas);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_as_nssa_lsas);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_ospf_auth_type);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_prefix_lists);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_network_lsas);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_area_col_network_lsas);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_opaque_area_lsas);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_ospf_interfaces);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_area_col_ospf_interfaces);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_inter_area_ospf_routes);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_intra_area_ospf_routes);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_router_ospf_routes);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_router_lsas);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_area_col_router_lsas);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_area_col_ospf_vlinks);

    /* Add OSPF_Area_Summary_Addr columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_ospf_summary_address);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_summary_address_col_other_config);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_summary_address_col_prefix);

    /* Add OSPF_Interface columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_ospf_interface);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_interface_col_ifsm_state);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_interface_col_ifsm_state);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_interface_col_statistics);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_interface_col_status);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_interface_col_status);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_interface_col_name);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_interface_col_name);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_interface_col_neighbors);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_interface_col_neighbors);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_interface_col_port);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_interface_col_port);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_interface_col_ospf_vlink);

    /* Add OSPF_Neighbor columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_ospf_neighbor);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_neighbor_col_bdr);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_neighbor_col_bdr);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_neighbor_col_dr);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_neighbor_col_dr);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_neighbor_col_nbma_nbr);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_neighbor_col_nbr_if_addr);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_neighbor_col_nbr_if_addr);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_neighbor_col_nbr_options);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_neighbor_col_nbr_options);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_neighbor_col_nbr_router_id);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_neighbor_col_nbr_router_id);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_neighbor_col_statistics);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_neighbor_col_statistics);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_neighbor_col_status);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_neighbor_col_status);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_neighbor_col_nfsm_state);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_neighbor_col_nfsm_state);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_neighbor_col_nbr_priority);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_neighbor_col_nbr_priority);

    /* Add OSPF_NBMA_Neighbor_Config columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_ospf_nbma_neighbor);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_nbma_neighbor_col_interface_name);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_nbma_neighbor_col_other_config);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_nbma_neighbor_col_status);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_nbma_neighbor_col_nbr_router_id);

    /* Add OSPF_Vlink columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_ospf_vlink);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_vlink_col_area_id);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_vlink_col_ospf_auth_type);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_vlink_col_ospf_auth_text_key);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_vlink_col_ospf_auth_md5_keys);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_vlink_col_name);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_vlink_col_peer_router_id);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_vlink_col_other_config);

    /* Add OSPF_Route columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_ospf_route);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_route_col_paths);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_route_col_path_type);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_route_col_prefix);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_route_col_route_info);

    /* Add OSPF_lsa columns */
    ovsdb_idl_add_table(idl, &ovsrec_table_ospf_lsa);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_lsa_col_adv_router);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_lsa_col_adv_router);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_lsa_col_area_id);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_lsa_col_area_id);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_lsa_col_chksum);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_lsa_col_chksum);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_lsa_col_flags);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_lsa_col_length);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_lsa_col_lsa_data);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_lsa_col_lsa_type);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_lsa_col_lsa_type);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_lsa_col_ls_birth_time);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_lsa_col_ls_birth_time);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_lsa_col_ls_id);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_lsa_col_ls_id);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_lsa_col_ls_seq_num);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_lsa_col_ls_seq_num);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_lsa_col_num_router_links);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_lsa_col_options);
    ovsdb_idl_add_column(idl, &ovsrec_ospf_lsa_col_prefix);
    ovsdb_idl_omit_alert(idl, &ovsrec_ospf_lsa_col_prefix);
}

/* Create a connection to the OVSDB at db_path and create a dB cache
 * for this daemon. */
static void
ovsdb_init (const char *db_path)
{
    /* Initialize IDL through a new connection to the dB. */
    idl = ovsdb_idl_create(db_path, &ovsrec_idl_class, false, true);
    idl_seqno = ovsdb_idl_get_seqno(idl);
    ovsdb_idl_set_lock(idl, "OpenSwitch_ospf");

    /* Cache OpenVSwitch table */
    ovsdb_idl_add_table(idl, &ovsrec_table_open_vswitch);

    ovsdb_idl_add_column(idl, &ovsrec_system_col_cur_cfg);
    ovsdb_idl_add_column(idl, &ovsrec_system_col_hostname);

    ospf_ovsdb_tables_init();

    /* Register ovs-appctl commands for this daemon. */
    unixctl_command_register("ospfd/dump", "", 0, 0, ospf_unixctl_dump, NULL);
    unixctl_command_register("ospf/debug", "packet|ism|nsm|lsa|event|nssa", 2,
                                         5, ospf_unixctl_debug, NULL);
    unixctl_command_register("ospf/no-debug", "packet|ism|nsm|lsa|event|nssa",
                                            2, 5, ospf_unixctl_no_debug, NULL);
    unixctl_command_register("ospf/show-debug", "ospfv2", 1, 1,
                                              ospfd_unixctl_show_debug_info, NULL);
}

static void
ops_ospf_exit(struct unixctl_conn *conn, int argc OVS_UNUSED,
                const char *argv[] OVS_UNUSED, void *exiting_)
{
    boolean *exiting = exiting_;
    *exiting = true;
    unixctl_command_reply(conn, NULL);
}

static void
ops_ospf_lsa_dump(struct unixctl_conn *conn, int argc OVS_UNUSED,
                const char *argv[] OVS_UNUSED, void *ext_arg)
{
    struct ospf* ospf = NULL;
    struct ospf_lsa *lsa;
    struct route_node *rn;
    struct ospf_area *area;
    struct listnode *node;
    int type;
    char buf[4096] = {0};

    ospf= ospf_lookup();
    if (!ospf)
        unixctl_command_reply_error(conn,"NO OSPF instance present");
    else
    {
        for (ALL_LIST_ELEMENTS_RO (ospf->areas, node, area))
        {
            for (type = OSPF_MIN_LSA; type < OSPF_MAX_LSA; type++)
            {
                switch (type)
                {
                    case OSPF_AS_EXTERNAL_LSA:
                    #ifdef HAVE_OPAQUE_LSA
                    case OSPF_OPAQUE_AS_LSA:
                    #endif /* HAVE_OPAQUE_LSA */
                      continue;
                    default:
                      break;
                }
                LSDB_LOOP (AREA_LSDB (area, type), rn, lsa)
                {
                    sprintf (buf+strlen(buf),"%-15s ", inet_ntoa (lsa->data->id));
                    sprintf (buf+strlen(buf),"%-15s %4d 0x%08lx 0x%04x type%d\n",
                     inet_ntoa (lsa->data->adv_router), LS_AGE (lsa),
                     (u_long)ntohl (lsa->data->ls_seqnum),
                     ntohs (lsa->data->checksum),lsa->data->type);
                }
            }
        }
        type = OSPF_AS_EXTERNAL_LSA;
        LSDB_LOOP (AS_LSDB (ospf, type), rn, lsa)
        {
            sprintf (buf+strlen(buf),"%-15s ", inet_ntoa (lsa->data->id));
            sprintf (buf+strlen(buf),"%-15s %4d 0x%08lx 0x%04x type%d\n",
                    inet_ntoa (lsa->data->adv_router), LS_AGE (lsa),
                    (u_long)ntohl (lsa->data->ls_seqnum),
                    ntohs (lsa->data->checksum),lsa->data->type);
        }
        unixctl_command_reply(conn,buf);
    }
}


static void
usage(void)
{
    printf("%s: Halon ospf daemon\n"
           "usage: %s [OPTIONS] [DATABASE]\n"
           "where DATABASE is a socket on which ovsdb-server is listening\n"
           "      (default: \"unix:%s/db.sock\").\n",
           program_name, program_name, ovs_rundir());
    stream_usage("DATABASE", true, false, true);
    daemon_usage();
    vlog_usage();
    printf("\nOther options:\n"
           "  --unixctl=SOCKET        override default control socket name\n"
           "  -h, --help              display this help message\n"
           "  -V, --version           display version information\n");

    exit(EXIT_SUCCESS);
}

/* OPS_TODO: Need to merge this parse function with the main parse function
 * in ospf_main to avoid issues.
 */
static char *
ospf_ovsdb_parse_options(int argc, char *argv[], char **unixctl_pathp)
{
    enum {
        OPT_UNIXCTL = UCHAR_MAX + 1,
        VLOG_OPTION_ENUMS,
        DAEMON_OPTION_ENUMS,
        OVSDB_OPTIONS_END,
    };
    static const struct option long_options[] = {
        {"help",        no_argument, NULL, 'h'},
        {"unixctl",     required_argument, NULL, OPT_UNIXCTL},
        DAEMON_LONG_OPTIONS,
        VLOG_LONG_OPTIONS,
        {NULL, 0, NULL, 0},
    };
    char *short_options = long_options_to_short_options(long_options);

    for (;;) {
        int c;

        c = getopt_long(argc, argv, short_options, long_options, NULL);
        if (c == -1) {
            break;
        }

        switch (c) {
        case 'h':
            usage();

        case OPT_UNIXCTL:
            *unixctl_pathp = optarg;
            break;

        VLOG_OPTION_HANDLERS
        DAEMON_OPTION_HANDLERS

        case '?':
            exit(EXIT_FAILURE);

        default:
           abort();
        }
    }
    free(short_options);

    argc -= optind;
    argv += optind;

    return xasprintf("unix:%s/db.sock", ovs_rundir());
}

/* Setup ospf to connect with ovsdb and daemonize. This daemonize is used
 * over the daemonize in the main function to keep the behavior consistent
 * with the other daemons in the OpenSwitch system
 */
void ospf_ovsdb_init (int argc, char *argv[])
{
    int retval;
    char *ovsdb_sock;

    memset(&glob_ospf_ovs, 0, sizeof(glob_ospf_ovs));

    set_program_name(argv[0]);
    proctitle_init(argc, argv);
    fatal_ignore_sigpipe();

    /* Parse commandline args and get the name of the OVSDB socket. */
    ovsdb_sock = ospf_ovsdb_parse_options(argc, argv, &appctl_path);

    /* Initialize the metadata for the IDL cache. */
    ovsrec_init();
    /* Fork and return in child process; but don't notify parent of
     * startup completion yet. */
    daemonize_start();

    /* Create UDS connection for ovs-appctl. */
    retval = unixctl_server_create(appctl_path, &appctl);
    if (retval) {
       exit(EXIT_FAILURE);
    }

    /* Register the ovs-appctl "exit" command for this daemon. */
    unixctl_command_register("exit", "", 0, 0, ops_ospf_exit, &exiting);

    unixctl_command_register("lsdb/dump", "", 0, 0, ops_ospf_lsa_dump, NULL);

   /* Create the IDL cache of the dB at ovsdb_sock. */
   ovsdb_init(ovsdb_sock);
   free(ovsdb_sock);

   /* Notify parent of startup completion. */
   daemonize_complete();

   /* Enable asynch log writes to disk. */
   vlog_enable_async();

   VLOG_INFO_ONCE("%s (Halon Ospfd Daemon) started", program_name);

   glob_ospf_ovs.enabled = 1;
   return;
}

static void
ospf_ovs_clear_fds (void)
{
    struct poll_loop *loop = poll_loop();
    free_poll_nodes(loop);
    loop->timeout_when = LLONG_MAX;
    loop->timeout_where = NULL;
}

/* Check if the system is already configured. The daemon should
 * not process any callbacks unless the system is configured.
 */
static inline void ospf_chk_for_system_configured(void)
{
  const struct ovsrec_system *ovs_vsw = NULL;

  if (system_configured) {
    /* Nothing to do if we're already configured. */
    return;
  }

  ovs_vsw = ovsrec_system_first(idl);

  if (ovs_vsw && (ovs_vsw->cur_cfg > (int64_t) 0)) {
    system_configured = true;
    VLOG_INFO("System is now configured (cur_cfg=%d).",
    (int)ovs_vsw->cur_cfg);
  }
}

static struct ovsrec_ospf_interface*
find_ospf_interface_by_name (const char* ifname)
{
    struct ovsrec_ospf_interface* ospf_intf_row = NULL;

    OVSREC_OSPF_INTERFACE_FOR_EACH(ospf_intf_row,idl)
    {
        if (0 == strcmp (ospf_intf_row->name,ifname))
            return ospf_intf_row;
    }
    return NULL;
}

static struct ovsrec_port*
find_vrf_port_by_name (const struct ovsrec_vrf *vrf_row, const char *ifname)
{
  struct ovsrec_port* port_row = NULL;
  int i;

  if (vrf_row) {
    for (i = 0; i < vrf_row->n_ports; i++) {
      if (vrf_row->ports[i] && (0 == strcmp (vrf_row->ports[i]->name, ifname))) {
        return vrf_row->ports[i];
      }
    }
  }

  return NULL;
}

static struct ovsrec_port*
find_port_by_ip_addr (const char* ipv4_addr)
{
    struct ovsrec_port* port_row = NULL;

    OVSREC_PORT_FOR_EACH(port_row,idl)
    {
        if (port_row->ip4_address &&
            !strcmp (port_row->ip4_address,ipv4_addr))
            return port_row;
    }
    return NULL;
}

static struct ovsrec_port*
find_port_by_name (const char* ifname)
{
    struct ovsrec_port* port_row = NULL;

    OVSREC_PORT_FOR_EACH(port_row,idl)
    {
        if (0 == strcmp (port_row->name,ifname))
            return port_row;
    }
    return NULL;
}

static struct ovsrec_ospf_vlink*
find_ospf_vl_by_name (const char* ifname)
{
    struct ovsrec_ospf_vlink* vlink_row = NULL;

    OVSREC_OSPF_VLINK_FOR_EACH(vlink_row,idl)
    {
        if (0 == strcmp (vlink_row->name,ifname))
            return vlink_row;
    }
    return NULL;
}

static struct ovsrec_ospf_neighbor*
find_ospf_nbr_by_if_addr (const struct ovsrec_ospf_interface* ovs_oi, struct in_addr src)
{
    struct ovsrec_ospf_neighbor* nbr_row = NULL;
    int i = 0;

    for (i = 0 ; i < ovs_oi->n_neighbors ; i++)
    {
        nbr_row = ovs_oi->neighbors[i];
        if (nbr_row && (*(nbr_row->nbr_if_addr) == (int64_t)(src.s_addr)))
            return nbr_row;
    }
    return NULL;
}


/* Similar to ospf_vl_new() but takes vlink name from OVSDB
   instead of VLINK%d */
static struct ospf_interface *
ovs_ospf_vl_new (struct ospf *ospf, struct ospf_vl_data *vl_data,
                    const char* ovs_vl_name)
{
  struct ospf_interface * voi;
  struct interface * vi;
  char   ifname[INTERFACE_NAMSIZ + 1];
  struct ospf_area *area;
  struct in_addr area_id;
  struct connected *co;
  struct prefix_ipv4 *p;

  VLOG_DBG ("ovs_ospf_vl_new(): Start");
  if (vlink_count == OSPF_VL_MAX_COUNT)
    {
      VLOG_DBG ("ovs_ospf_vl_new(): Alarm: "
           "cannot create more than OSPF_MAX_VL_COUNT virtual links");
      return NULL;
    }

  VLOG_DBG ("ovs_ospf_vl_new(): creating pseudo zebra interface");

  snprintf (ifname, sizeof(ifname), ovs_vl_name);
  /* Take VLINK name from OVSDB */
  vi = if_create (ifname, strnlen(ifname, sizeof(ifname)));
  co = connected_new ();
  co->ifp = vi;
  listnode_add (vi->connected, co);

  p = prefix_ipv4_new ();
  p->family = AF_INET;
  p->prefix.s_addr = 0;
  p->prefixlen = 0;

  co->address = (struct prefix *)p;

  voi = ospf_if_new (ospf, vi, co->address);
  if (voi == NULL)
  {
    VLOG_DBG ("ovs_ospf_vl_new(): Alarm: OSPF int structure is not created");
    return NULL;
  }
  voi->connected = co;
  voi->vl_data = vl_data;
  voi->ifp->mtu = OSPF_VL_MTU;
  voi->type = OSPF_IFTYPE_VIRTUALLINK;

  vlink_count++;
  VLOG_DBG ("ovs_ospf_vl_new(): Created name: %s", ifname);
  VLOG_DBG ("ovs_ospf_vl_new(): set if->name to %s", vi->name);

  area_id.s_addr = 0;
  area = ospf_area_get (ospf, area_id, OSPF_AREA_ID_FORMAT_ADDRESS);
  voi->area = area;

  VLOG_DBG ("ovs_ospf_vl_new(): set associated area to the backbone");

  ospf_nbr_add_self (voi);
  ospf_area_add_if (voi->area, voi);

  ovsdb_ospf_add_nbr_self(voi->nbr_self,voi->ifp->name);

  ospf_if_stream_set (voi);

  VLOG_DBG ("ovs_ospf_vl_new(): Stop");
  return voi;
}


static void
ospf_vl_config_data_init (struct ospf_vl_config_data *vl_config,
                        char* vl_name)
{
  memset (vl_config, 0, sizeof (struct ospf_vl_config_data));
  vl_config->auth_type = OSPF_AUTH_CMD_NOTSEEN;
  vl_config->vl_name = vl_name;
}


static struct ospf_vl_data *
ospf_find_vl_data (struct ospf *ospf, struct ospf_vl_config_data *vl_config,
                const char* ovs_vl_name)
{
  struct ospf_area *area;
  struct ospf_vl_data *vl_data;
  struct in_addr area_id;

  area_id = vl_config->area_id;

  if (area_id.s_addr == OSPF_AREA_BACKBONE)
  {
     VLOG_DBG ("Configuring VLs over the backbone"
                "is not allowed%s");
     return NULL;
  }
  area = ospf_area_get (ospf, area_id, vl_config->format);

  if (area->external_routing != OSPF_AREA_DEFAULT)
  {
      VLOG_DBG ("Area %s is %s%s",inet_ntoa (area_id),
      area->external_routing == OSPF_AREA_NSSA?"nssa":"stub");
    return NULL;
  }

  if ((vl_data = ospf_vl_lookup (ospf, area, vl_config->vl_peer)) == NULL)
    {
      vl_data = ospf_vl_data_new (area, vl_config->vl_peer);
      if (vl_data->vl_oi == NULL)
      {
        vl_data->vl_oi = ovs_ospf_vl_new (ospf, vl_data,ovs_vl_name);
        ospf_vl_add (ospf, vl_data);
        ospf_spf_calculate_schedule (ospf, SPF_FLAG_CONFIG_CHANGE);
      }
    }
  return vl_data;
}


/* Main function to create/modify VLINKS */
static int
ospf_vl_set (struct ospf *ospf, struct ospf_vl_config_data *vl_config)
{
  struct ospf_vl_data *vl_data;
  int ret;

  vl_data = ospf_find_vl_data (ospf, vl_config,vl_config->vl_name);
  if (!vl_data)
    return 1;

  return 0;

}

int ovsdb_options_count(u_char options_val)
{
    int count = 0;
    u_char options = options_val;

    while (options != 0)
    {
        if ((options & 1) == 1)
            count++;
        options = options >> 1;
    }
}

int
ovsdb_ospf_router_set_router_id(const struct ovsrec_ospf_router *ovs_ospf_router,
    const char *active_router_id)
{
    struct smap smap = SMAP_INITIALIZER (&smap);
    struct ovsdb_idl_txn *ospf_router_txn;
    enum ovsdb_idl_txn_status status;

    ospf_router_txn = ovsdb_idl_txn_create (idl);
    if (!ospf_router_txn) {
       VLOG_ERR ("Transaction create failed");
       return 1;
    }

    smap_clone (&smap, &ovs_ospf_router->router_id);
    smap_replace (&smap, OSPF_KEY_ROUTER_ID_VAL, active_router_id);
    smap_replace (&smap, OSPF_KEY_ROUTER_ID_STATIC, "false");
    ovsrec_ospf_router_set_router_id (ovs_ospf_router, &smap);
    smap_destroy (&smap);

    status = ovsdb_idl_txn_commit_block (ospf_router_txn);
    if (status != TXN_SUCCESS && status != TXN_UNCHANGED) {
        VLOG_ERR ("Transaction commit failed: %d", status);
        return 1;
    }
    ovsdb_idl_txn_destroy (ospf_router_txn);
    return 0;
}

int
modify_ospf_router_id_config (struct ospf *ospf_cfg,
    const struct ovsrec_ospf_router *ospf_mod_row)
{
    const struct ovsrec_vrf *ovs_vrf;
    bool router_id_static = false;
    char *router_id = NULL;
    char *active_router_id = NULL;
    struct in_addr addr;

    memset (&addr, 0, sizeof(addr));
    router_id = smap_get (&(ospf_mod_row->router_id), "router_id_val");
    router_id_static = smap_get_bool (&(ospf_mod_row->router_id), "router_id_static", false);

    if (!router_id_static) {
        OVSREC_VRF_FOR_EACH (ovs_vrf, idl) {
            if (!strcmp (ovs_vrf->name, DEFAULT_VRF_NAME)) {
               active_router_id = ovs_vrf->active_router_id;
            }
        }

        if (router_id && active_router_id && !strcmp (router_id, active_router_id)) {
            return 0;
        }

        if (active_router_id) {
            ovsdb_ospf_router_set_router_id(ospf_mod_row, active_router_id);
            inet_aton (active_router_id, &addr);
        }			
    }
    else {
        if (router_id)		
            inet_aton (router_id, &addr);
    }

    if (!addr.s_addr) {
        VLOG_DBG ("Unable to convert router-id");
    }

    if (router_id_static)
        ospf_cfg->router_id_static.s_addr = addr.s_addr;
    else
        ospf_cfg->router_id.s_addr = addr.s_addr;

    ospf_router_id_update (ospf_cfg);
    return 0;
}

int
modify_ospf_router_config (struct ospf *ospf_cfg,
    const struct ovsrec_ospf_router *ospf_mod_row)
{

   if (smap_get_bool(&(ospf_mod_row->other_config), "ospf_rfc1583_compatible",false))
        SET_FLAG(ospf_cfg->config,OSPF_RFC1583_COMPATIBLE);
   else
        UNSET_FLAG(ospf_cfg->config,OSPF_RFC1583_COMPATIBLE);

   if (smap_get_bool(&(ospf_mod_row->other_config), "enable_ospf_opaque_lsa",false))
        SET_FLAG(ospf_cfg->config,OSPF_OPAQUE_CAPABLE);
   else
        UNSET_FLAG(ospf_cfg->config,OSPF_OPAQUE_CAPABLE);

   if (smap_get_bool(&(ospf_mod_row->other_config), "log_adjacency_changes",false))
        SET_FLAG(ospf_cfg->config,OSPF_LOG_ADJACENCY_CHANGES);
   else
        UNSET_FLAG(ospf_cfg->config,OSPF_LOG_ADJACENCY_CHANGES);

   if (smap_get_bool(&(ospf_mod_row->other_config), "log_adjacency_details",false))
        SET_FLAG(ospf_cfg->config,OSPF_LOG_ADJACENCY_DETAIL);
   else
        UNSET_FLAG(ospf_cfg->config,OSPF_LOG_ADJACENCY_DETAIL);

   ospf_cfg->default_metric = smap_get_int(&(ospf_mod_row->other_config),
                                                 OSPF_KEY_ROUTER_DEFAULT_METRIC,
                                                  OSPF_DEFAULT_METRIC_DEFAULT);

   return 0;
}

int
modify_ospf_lsa_timers_router_config(struct ospf *ospf_cfg,
             const struct ovsrec_ospf_router *ospf_mod_row)
{
    int i, timer;

    for (i = 0; i < ospf_mod_row->n_lsa_timers; i++) {
        if (strcmp(ospf_mod_row->key_lsa_timers[i],
                                             OSPF_KEY_LSA_GROUP_PACING) == 0) {
            timer = ospf_mod_row->value_lsa_timers[i];
        }
    }

    ospf_timers_refresh_set(ospf_cfg, timer);

    return 0;
}

int
modify_ospf_stub_router_config (struct ovsdb_idl *idl, struct ospf *ospf_cfg,
    const struct ovsrec_ospf_router *ospf_mod_row)
{
    struct listnode *ln;
    struct ospf_area *area;
    int stub_admin_set = -1;
    bool admin_set = false;
    int startup = 0;
    int i = 0;

    admin_set = smap_get_bool(&(ospf_mod_row->stub_router_adv),
                              OVSREC_OSPF_ROUTER_STUB_ROUTER_ADV_ADMIN_SET,false);
    startup = smap_get_int(&(ospf_mod_row->stub_router_adv),
                              OVSREC_OSPF_ROUTER_STUB_ROUTER_ADV_STARTUP,0);
    if(admin_set) {
       if (!CHECK_FLAG(ospf_cfg->stub_router_admin_set,OSPF_STUB_ROUTER_ADMINISTRATIVE_SET))
           stub_admin_set = 1;
    }
    else {
       if (CHECK_FLAG(ospf_cfg->stub_router_admin_set,OSPF_STUB_ROUTER_ADMINISTRATIVE_SET))
               stub_admin_set = 0;
    }
   if (startup != ospf_cfg->stub_router_startup_time)
       ospf_cfg->stub_router_startup_time = startup;

   if (1 == stub_admin_set)
   {
       for (ALL_LIST_ELEMENTS_RO (ospf_cfg->areas, ln, area))
       {
         SET_FLAG (area->stub_router_state, OSPF_AREA_ADMIN_STUB_ROUTED);

         if (!CHECK_FLAG (area->stub_router_state, OSPF_AREA_IS_STUB_ROUTED))
             ospf_router_lsa_update_area (area);
       }
       ospf_cfg->stub_router_admin_set = OSPF_STUB_ROUTER_ADMINISTRATIVE_SET;
   }
   else if (0 == stub_admin_set)
   {
    for (ALL_LIST_ELEMENTS_RO (ospf_cfg->areas, ln, area))
    {
      UNSET_FLAG (area->stub_router_state, OSPF_AREA_ADMIN_STUB_ROUTED);

      /* Don't trample on the start-up stub timer */
      if (CHECK_FLAG (area->stub_router_state, OSPF_AREA_IS_STUB_ROUTED)
          && !area->t_stub_router)
        {
          UNSET_FLAG (area->stub_router_state, OSPF_AREA_IS_STUB_ROUTED);
          ospf_router_lsa_update_area (area);
        }
    }
    ospf_cfg->stub_router_admin_set = OSPF_STUB_ROUTER_ADMINISTRATIVE_UNSET;
   }
}

static struct ovsrec_ospf_area*
ovsrec_ospf_area_get_area_by_id (struct ovsrec_ospf_router* ovs_ospf,
                                                     struct in_addr areaid)
{
    int i = 0;
    struct ovsrec_ospf_area* ovs_area = NULL;
    for (i = 0 ; i < ovs_ospf->n_areas ; i++) {
        ovs_area = ovs_ospf->value_areas[i];
        if (ovs_ospf->key_areas[i] == areaid.s_addr)
            return ovs_area;
    }

    return NULL;
}

struct ovsrec_ospf_router*
ovsdb_ospf_get_router_by_instance_num (int instance)
{
    struct ovsrec_vrf* ovs_vrf = NULL;
    struct ovsrec_ospf_router* ovs_router = NULL;
    int i = 0;

    /* OPS_TODO : Support for multiple VRF */
    ovs_vrf = ovsrec_vrf_first(idl);
    if (!ovs_vrf)
    {
       VLOG_DBG ("No VRF found");
       return NULL;
    }

    for (i = 0 ; i < ovs_vrf->n_ospf_routers ; i++)
    {
       ovs_router = ovs_vrf->value_ospf_routers[i];
       if (instance == ovs_vrf->key_ospf_routers[i])
        return ovs_router;
    }

    return NULL;
}

void
ovsdb_ospf_vl_update (const struct ospf_interface* voi)
{
    const struct ovsrec_port* ovs_port = NULL;
    struct ovsrec_ospf_vlink* ovs_vl = NULL;
    struct ovsrec_ospf_interface* ovs_if = NULL;
    struct ovsdb_idl_txn* vl_txn = NULL;
    enum ovsdb_idl_txn_status status;
    char vl_addr_ipv4[OSPF_MAX_PREFIX_LEN] = {0};

    if(!voi ||
       !voi->ifp ||
       !voi->ifp->name ||
       !voi->address) {
       VLOG_DBG ("No associated interface found");
       return;
    }
    ovs_if = find_ospf_interface_by_name(voi->ifp->name);
    if (!ovs_if) {
       VLOG_DBG ("No OSPF interface found %s",voi->ifp->name);
       return;
    }
    ovs_vl = ovs_if->ospf_vlink;
    if (!ovs_vl) {
       VLOG_DBG ("No OSPF VLINK found for %s",voi->ifp->name);
       return;
    }
    vl_txn = ovsdb_idl_txn_create(idl);
    if (!vl_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    /* VL interface address got after SPF calculation Update*/
    prefix2str(voi->address,vl_addr_ipv4,sizeof(vl_addr_ipv4));

    if (!ovs_if->port) {
        ovs_port = find_port_by_ip_addr(vl_addr_ipv4);
        if (!ovs_port){
            VLOG_DBG ("No Port found for %s",voi->ifp->name);
            ovsdb_idl_txn_abort(vl_txn);
            return;
        }
        ovsrec_ospf_interface_set_port(ovs_if, ovs_port);
    }
    /* Check if address is changes */
    else {
        ovs_port = ovs_if->port;
        /* Update ip address if not same */
        if (NULL == ovs_port->ip4_address ||
        strcmp(vl_addr_ipv4,ovs_port->ip4_address)) {
            ovs_port = find_port_by_ip_addr(vl_addr_ipv4);
            if (ovs_port)
                ovsrec_ospf_interface_set_port(ovs_if, ovs_port);
        }
    }

    status = ovsdb_idl_txn_commit_block(vl_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("VL Updater commit failed:%d",status);

    ovsdb_idl_txn_destroy(vl_txn);
}

void
ovsdb_ospf_add_lsa  (struct ospf_lsa* lsa)
{
    struct ovsrec_ospf_router* ospf_router_row = NULL;
    struct ovsrec_ospf_area* area_row = NULL;
    struct ovsdb_idl_txn* area_txn = NULL;
    struct ovsrec_ospf_lsa* new_lsas = NULL;
    struct ovsrec_ospf_lsa** router_lsas = NULL;
    struct ovsrec_ospf_lsa** network_lsas = NULL;
    enum ovsdb_idl_txn_status status;
    struct smap chksum_smap;
    char buf [64] = {0};
    int64_t lsa_area_id = 0;
    int64_t lsa_id = 0;
    int64_t lsa_age = 0;
    int64_t lsa_adv_router = 0;
    int64_t lsa_chksum = 0;
    int64_t lsa_seqnum = 0;
    int ospf_instance = 0;
    int i = 0;

    memset (&chksum_smap,0,sizeof(chksum_smap));
    if (NULL == lsa->data)
    {
        VLOG_DBG ("No LSA data to add");
        return;
    }
    if (NULL == lsa->area)
    {
        VLOG_DBG ("No area may be AS_EXTERNAL LSA, Not dealing now");
        return;
    }

    ospf_instance = lsa->area->ospf->ospf_inst;

    area_txn = ovsdb_idl_txn_create(idl);
    if (!area_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    ospf_router_row =
        ovsdb_ospf_get_router_by_instance_num (ospf_instance);
    if (!ospf_router_row)
    {
       VLOG_DBG ("No OSPF router found");
       ovsdb_idl_txn_abort(area_txn);
       return;
    }
    /* OPS_TODO : AS_EXTERNAL LSA check */
    area_row = ovsrec_ospf_area_get_area_by_id(ospf_router_row,
                             lsa->area->area_id);
    if (!area_row)
    {
       VLOG_DBG ("No associated OSPF area : %d exist",lsa->area->area_id.s_addr);
       ovsdb_idl_txn_abort(area_txn);
       return;
    }
    new_lsas = ovsrec_ospf_lsa_insert(area_txn);
    if (!new_lsas)
    {
       VLOG_DBG ("LSA insert failed");
       ovsdb_idl_txn_abort(area_txn);
       return;
    }
    switch (lsa->data->type)
    {
        case OSPF_ROUTER_LSA:
            router_lsas = xmalloc(sizeof * area_row->router_lsas *
                                         (area_row->n_router_lsas + 1));
            for (i = 0; i < area_row->n_router_lsas; i++) {
                   router_lsas[i] = area_row->router_lsas[i];
            }
            router_lsas[area_row->n_router_lsas] = new_lsas;

            ovsrec_ospf_area_set_router_lsas (area_row,router_lsas,
                                   area_row->n_router_lsas + 1);

            if (NULL != lsa->lsdb)
            {
                snprintf (buf,sizeof(buf),"%u",lsa->lsdb->type[OSPF_ROUTER_LSA].checksum);
                smap_clone(&chksum_smap,&(area_row->status));
                smap_replace(&chksum_smap,"router_lsas_sum_cksum",buf);
                ovsrec_ospf_area_set_status(area_row,&chksum_smap);
                smap_destroy(&chksum_smap);
            }

            lsa_area_id = lsa->area->area_id.s_addr;
            ovsrec_ospf_lsa_set_area_id (new_lsas,
                                            &lsa_area_id,1);

            ovsrec_ospf_lsa_set_lsa_type (new_lsas,
                                            lsa_str[lsa->data->type].lsa_type_str);
            lsa_id = lsa->data->id.s_addr;
            ovsrec_ospf_lsa_set_ls_id (new_lsas,lsa_id);

            lsa_age = lsa->data->ls_age;
            ovsrec_ospf_lsa_set_ls_birth_time(new_lsas, lsa_age);

            ovsrec_ospf_lsa_set_prefix (new_lsas, "0.0.0.0");

            lsa_adv_router = lsa->data->adv_router.s_addr;
            ovsrec_ospf_lsa_set_adv_router (new_lsas,lsa_adv_router);

            lsa_chksum = lsa->data->checksum;
            ovsrec_ospf_lsa_set_chksum (new_lsas,&lsa_chksum,1);
            lsa_seqnum = lsa->data->ls_seqnum;
            ovsrec_ospf_lsa_set_ls_seq_num (new_lsas,lsa_seqnum);

            free(router_lsas);
            break;
        case OSPF_NETWORK_LSA:
                network_lsas = xmalloc(sizeof * area_row->network_lsas *
                                         (area_row->n_network_lsas + 1));
            for (i = 0; i < area_row->n_network_lsas; i++) {
                   network_lsas[i] = area_row->network_lsas[i];
            }
            network_lsas[area_row->n_network_lsas] = new_lsas;

            ovsrec_ospf_area_set_network_lsas (area_row,network_lsas,
                                   area_row->n_network_lsas + 1);

            if (NULL != lsa->lsdb)
            {
                snprintf (buf,sizeof(buf),"%u",lsa->lsdb->type[OSPF_NETWORK_LSA].checksum);
                smap_clone(&chksum_smap,&(area_row->status));
                smap_replace(&chksum_smap,"network_lsas_sum_cksum",buf);
                ovsrec_ospf_area_set_status(area_row,&chksum_smap);
                smap_destroy(&chksum_smap);
            }
            lsa_area_id = lsa->area->area_id.s_addr;
            ovsrec_ospf_lsa_set_area_id (new_lsas,
                                            &lsa_area_id,1);

            ovsrec_ospf_lsa_set_lsa_type (new_lsas,
                                            lsa_str[lsa->data->type].lsa_type_str);
            lsa_id = lsa->data->id.s_addr;
            ovsrec_ospf_lsa_set_ls_id (new_lsas,lsa_id);
            lsa_age = lsa->data->ls_age;
            ovsrec_ospf_lsa_set_ls_birth_time (new_lsas, lsa_age);
            ovsrec_ospf_lsa_set_prefix (new_lsas, "0.0.0.0");  //change to prefix as its type 3
            lsa_adv_router = lsa->data->adv_router.s_addr;
            ovsrec_ospf_lsa_set_adv_router (new_lsas,lsa_adv_router);
            lsa_chksum = lsa->data->checksum;
            ovsrec_ospf_lsa_set_chksum (new_lsas,&lsa_chksum,1);
            lsa_seqnum = lsa->data->ls_seqnum;
            ovsrec_ospf_lsa_set_ls_seq_num (new_lsas,lsa_seqnum);
            free(router_lsas);
            break;
    }

    status = ovsdb_idl_txn_commit_block(area_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("LSA transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(area_txn);
}

//void
//ovsdb_ospf_remove_lsa  (struct in_addr lsa_id, unsigned char lsa_type, struct ospf_lsa* lsa)
void
ovsdb_ospf_remove_lsa  (struct ospf_lsa* lsa)
{
    struct ovsrec_ospf_router* ospf_router_row = NULL;
    struct ovsrec_ospf_area* area_row = NULL;
    struct ovsdb_idl_txn* area_txn = NULL;
    struct ovsrec_ospf_lsa* old_lsas = NULL;
    struct ovsrec_ospf_lsa** router_lsas = NULL;
    struct ovsrec_ospf_lsa** network_lsas = NULL;
    enum ovsdb_idl_txn_status status;
    int ospf_instance = 0;
    int i = 0, j = 0;

    if (NULL == lsa->data)
    {
        VLOG_DBG ("No LSA data to delete");
        return;
    }
    if (NULL == lsa->area)
    {
        VLOG_DBG ("No area may be AS_EXTERNAL LSA");
        return;
    }
    ospf_instance = lsa->area->ospf->ospf_inst;

    area_txn = ovsdb_idl_txn_create(idl);
    if (!area_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    ospf_router_row =
        ovsdb_ospf_get_router_by_instance_num (ospf_instance);
    if (!ospf_router_row)
    {
       VLOG_DBG ("No OSPF router found");
       ovsdb_idl_txn_abort(area_txn);
       return;
    }
    /* OPS_TODO : AS_EXTERNAL LSA check */
    area_row = ovsrec_ospf_area_get_area_by_id(ospf_router_row,
                             lsa->area->area_id);
    if (!area_row)
    {
       VLOG_DBG ("No associated OSPF area : %d exist",lsa->area->area_id.s_addr);
       ovsdb_idl_txn_abort(area_txn);
       return;
    }
    switch (lsa->data->type)
    {
        case OSPF_ROUTER_LSA:
            if (0 >= area_row->n_router_lsas)
            {
               ovsdb_idl_txn_abort(area_txn);
               return;
            }
            router_lsas = xmalloc(sizeof * area_row->router_lsas *
                                         (area_row->n_router_lsas - 1));

            for (i = 0,j = 0; (i < area_row->n_router_lsas) && (j < area_row->n_router_lsas - 1); i++) {
                if ((area_row->router_lsas[i]->ls_id == lsa->data->id.s_addr) &&
                    (area_row->router_lsas[i]->ls_seq_num == lsa->data->ls_seqnum) &&
                    (area_row->router_lsas[i]->adv_router == lsa->data->adv_router.s_addr)) {
                   old_lsas = area_row->router_lsas[i];
                }
                else
                {
                   router_lsas[j] = area_row->router_lsas[i];
                   j++;
                }
            }
            if (!old_lsas)
            {

                ovsdb_idl_txn_abort(area_txn);
                free(router_lsas);
                return;
            }

            ovsrec_ospf_area_set_router_lsas (area_row,router_lsas,
                                   area_row->n_router_lsas - 1);


            ovsrec_ospf_lsa_delete (old_lsas);
            // TODO: Update the checksum sum
            free(router_lsas);
            break;
        case OSPF_NETWORK_LSA:
            if (0 >= area_row->n_network_lsas)
            {
               ovsdb_idl_txn_abort(area_txn);
               return;
            }
            network_lsas = xmalloc(sizeof * area_row->network_lsas *
                                         (area_row->n_network_lsas - 1));

            for (i = 0,j = 0; (i < area_row->n_network_lsas) & (j < area_row->n_network_lsas - 1); i++) {
                if ((area_row->network_lsas[i]->ls_id == lsa->data->id.s_addr) &&
                    (area_row->network_lsas[i]->ls_seq_num == lsa->data->ls_seqnum) &&
                    (area_row->network_lsas[i]->adv_router == lsa->data->adv_router.s_addr)) {
                    old_lsas = area_row->network_lsas[i];
                }
                else
                {
                   network_lsas[j] = area_row->network_lsas[i];
                   j++;
                }
            }

            if (!old_lsas)
            {
                VLOG_DBG ("No lsa");
                ovsdb_idl_txn_abort(area_txn);
                free(network_lsas);
                return;
            }

            ovsrec_ospf_area_set_network_lsas (area_row,network_lsas,
                                   area_row->n_network_lsas - 1);

            ovsrec_ospf_lsa_delete (old_lsas);
            // TODO: Update the checksum sum
            free(network_lsas);
            break;
    }

    status = ovsdb_idl_txn_commit_block(area_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("LSA delete transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(area_txn);
    return;
}

void
ovsdb_ospf_update_full_nbr_count (struct ospf_neighbor* nbr,
                           uint32_t full_nbr_count)
{
    struct ovsrec_ospf_area* ovs_area = NULL;
    struct ovsrec_ospf_router* ovs_router = NULL;
    struct ovsdb_idl_txn* nbr_txn = NULL;
    enum ovsdb_idl_txn_status status;
    struct smap area_smap;
    char buf[32] = {0};

    int instance = 0;

    if (NULL == nbr)
    {
        VLOG_DBG ("No neighbor data to add");
        return;
    }
    if (NULL == nbr->oi)
    {
        VLOG_DBG ("No associated interface of neighbor");
        return;
    }
    if (NULL == nbr->oi->ospf)
    {
        VLOG_DBG ("No associated ospf instance of neighbor");
        return;
    }
    if (NULL == nbr->oi->area)
    {
        VLOG_DBG ("No associated area of neighbor");
        return;
    }
    nbr_txn = ovsdb_idl_txn_create(idl);
    if (!nbr_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }

    instance = nbr->oi->ospf->ospf_inst;
    ovs_router = ovsdb_ospf_get_router_by_instance_num (instance);
    if (NULL == ovs_router)
    {
        VLOG_DBG ("No ospf instance of neighbor");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    ovs_area = ovsrec_ospf_area_get_area_by_id(ovs_router,nbr->oi->area->area_id);
    if (NULL == ovs_area)
    {
        VLOG_DBG ("No associated area of neighbor");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    snprintf(buf,sizeof(buf),"%u",full_nbr_count);
    memset(&area_smap,0,sizeof(area_smap));
    smap_clone(&area_smap,&(ovs_area->status));
    smap_replace(&area_smap,"full_nbrs",buf);
    ovsrec_ospf_area_set_status(ovs_area,&area_smap);

    status = ovsdb_idl_txn_commit_block(nbr_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("Full nbr # transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(nbr_txn);
    smap_destroy(&area_smap);
    return;
}

void
ovsdb_ospf_update_vl_full_nbr_count (struct ospf_area* vl_area)
{
    struct ovsrec_ospf_area* ovs_area = NULL;
    struct ovsrec_ospf_router* ovs_router = NULL;
    struct ovsdb_idl_txn* vl_txn = NULL;
    enum ovsdb_idl_txn_status status;
    struct smap area_smap;
    char buf[32] = {0};
    int instance = 0;

    if (NULL == vl_area)
    {
        VLOG_DBG ("No associated area of VL");
        return;
    }
    if (NULL == vl_area->ospf)
    {
        VLOG_DBG ("No associated OSPF intance of VL");
        return;
    }
    instance = vl_area->ospf->ospf_inst;
    ovs_router = ovsdb_ospf_get_router_by_instance_num (instance);
    if (NULL == ovs_router)
    {
        VLOG_DBG ("No ospf instance of VL");
        return;
    }
    ovs_area = ovsrec_ospf_area_get_area_by_id(ovs_router, vl_area->area_id);
    if (NULL == ovs_area)
    {
        VLOG_DBG ("No associated area of neighbor");
        return;
    }
    vl_txn = ovsdb_idl_txn_create(idl);
    if (!vl_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    snprintf(buf,sizeof(buf),"%u",vl_area->full_vls);
    memset(&area_smap,0,sizeof(area_smap));
    smap_clone(&area_smap,&(ovs_area->status));
    smap_replace(&area_smap,"full_virtual_nbrs",buf);
    ovsrec_ospf_area_set_status(ovs_area,&area_smap);

    status = ovsdb_idl_txn_commit_block(vl_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("Full VL nbr # transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(vl_txn);
    smap_destroy(&area_smap);
    return;
}

void
ovsdb_ospf_update_nbr_dr_bdr  (struct in_addr if_addr,
                      struct in_addr d_router, struct in_addr bd_router)
{
    struct ovsrec_ospf_neighbor* ovs_nbr = NULL;
    struct ovsdb_idl_txn* nbr_txn = NULL;
    int64_t ip_src = 0;
    enum ovsdb_idl_txn_status status;
    int i = 0;

    nbr_txn = ovsdb_idl_txn_create(idl);
    if (!nbr_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    OVSREC_OSPF_NEIGHBOR_FOR_EACH(ovs_nbr,idl)
    {
        /* Includes self-neighbor */
        if (ovs_nbr && (if_addr.s_addr == ovs_nbr->nbr_if_addr[0]))
        {
            ip_src = d_router.s_addr;
            ovsrec_ospf_neighbor_set_dr (ovs_nbr,&ip_src,1);

            ip_src = bd_router.s_addr;
            ovsrec_ospf_neighbor_set_bdr (ovs_nbr,&ip_src,1);
            break;
        }
    }

    status = ovsdb_idl_txn_commit_block(nbr_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("NBR DR-BDR transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(nbr_txn);
    return;
}

void
ovsdb_ospf_update_nbr  (struct ospf_neighbor* nbr)
{
    struct ovsrec_ospf_interface* ovs_oi = NULL;
    struct ovsrec_ospf_neighbor* ovs_nbr = NULL;
    struct ovsdb_idl_txn* nbr_txn = NULL;
    struct interface* intf = NULL;
    //int64_t ip_src = 0;
    int64_t nbr_id = 0;
    int64_t nbr_priority = 0;
    enum ovsdb_idl_txn_status status;
    char** value_nbr_option = NULL;
    int nbr_option_cnt = 0;
    char** key_nbr_statistics = NULL;
    int64_t* value_nbr_statistics = NULL;
    int i = 0;

    if (NULL == nbr)
    {
        VLOG_DBG ("No neighbor data to add");
        return;
    }
    if (NULL == nbr->oi)
    {
        VLOG_DBG ("No associated interface of neighbor");
        return;
    }

    nbr_txn = ovsdb_idl_txn_create(idl);
    if (!nbr_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    intf = nbr->oi->ifp;
    if (NULL == intf)
    {
        VLOG_DBG ("No associated interface of neighbor");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    ovs_oi = find_ospf_interface_by_name(intf->name);
    if (NULL == ovs_oi)
    {
        VLOG_DBG ("No associated interface of neighbor");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    ovs_nbr = find_ospf_nbr_by_if_addr(ovs_oi,nbr->src);
    if (!ovs_nbr)
    {
       VLOG_DBG ("No Neighbor present");
       ovsdb_idl_txn_abort(nbr_txn);
       return;
    }

    nbr_id = nbr->router_id.s_addr;
    ovsrec_ospf_neighbor_set_nbr_router_id (ovs_nbr,&nbr_id,1);

    if (CHECK_FLAG(nbr->options,OSPF_OPTION_E))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_EXTERNAL_ROUTING;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_MC))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_MULTICAST;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_NP))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_TYPE_7_LSA;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_EA))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_EXTERNAL_ATTRIBUTES_LSA;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_DC))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_DEMAND_CIRCUITS;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_O))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_OPAQUE_LSA;
    }

    ovsrec_ospf_neighbor_set_nbr_options (ovs_nbr,value_nbr_option,
                                                             nbr_option_cnt);
    nbr_priority = nbr->priority;
    ovsrec_ospf_neighbor_set_nbr_priority (ovs_nbr,&nbr_priority,1);

    ovsrec_ospf_neighbor_set_nfsm_state (ovs_nbr,ospf_nsm_state[nbr->state].str);

    for (i = 0 ; i < ovs_nbr->n_statistics; i++)
        if (0 == strcmp (ovs_nbr->key_statistics[i],OSPF_KEY_NEIGHBOR_STATE_CHG_CNT))
            ovs_nbr->value_statistics[i] = nbr->state_change;
    ovsrec_ospf_neighbor_set_statistics(ovs_nbr,ovs_nbr->key_statistics,
        ovs_nbr->value_statistics,ovs_nbr->n_statistics);

    status = ovsdb_idl_txn_commit_block(nbr_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("NBR add transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(nbr_txn);
    free (key_nbr_statistics);
    free (value_nbr_statistics);
    free (value_nbr_option);
    return;
}

void
ovsdb_ospf_add_nbr  (struct ospf_neighbor* nbr)
{
    struct ovsrec_ospf_interface* ovs_oi = NULL;
    struct ovsrec_ospf_neighbor** ovs_nbr = NULL;
    struct ovsrec_ospf_neighbor* new_ovs_nbr = NULL;
    struct ovsdb_idl_txn* nbr_txn = NULL;
    struct timeval tv;
    struct smap nbr_status;
    struct interface* intf = NULL;
    int64_t ip_src = 0;
    int64_t nbr_id = 0;
    enum ovsdb_idl_txn_status status;
    char** key_nbr_statistics = NULL;
    char** value_nbr_option = NULL;
    int nbr_option_cnt = 0;
    int64_t* value_nbr_statistics = NULL;
    long nbr_up_time = 0;
    char buf[32] = {0};
    int i = 0;

    if (NULL == nbr)
    {
        VLOG_DBG ("No neighbor data to add");
        return;
    }
    if (NULL == nbr->oi)
    {
        VLOG_DBG ("No associated interface of neighbor");
        return;
    }

    nbr_txn = ovsdb_idl_txn_create(idl);
    if (!nbr_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    intf = nbr->oi->ifp;
    if (NULL == intf)
    {
        VLOG_DBG ("No associated interface of neighbor");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    ovs_oi = find_ospf_interface_by_name(intf->name);
    if (NULL == ovs_oi)
    {
        VLOG_DBG ("No associated interface of neighbor");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    /* Fix me : Update NBR instead of looping through
     * all the neighbor (OVSDB lookup). May be a local cache
     * and if there is change then commit to DB
     */

    new_ovs_nbr = find_ospf_nbr_by_if_addr(ovs_oi,nbr->src);
    if (new_ovs_nbr)
    {
       VLOG_DBG ("Neighbor already present");
       ovsdb_idl_txn_abort(nbr_txn);
       return;
    }
    new_ovs_nbr = ovsrec_ospf_neighbor_insert (nbr_txn);
    if (NULL == new_ovs_nbr)
    {
        VLOG_DBG ("Neighbor insertion failed");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    ovs_nbr = xmalloc(sizeof * ovs_oi->neighbors *
                                    (ovs_oi->n_neighbors + 1));
    for (i = 0; i < ovs_oi->n_neighbors; i++) {
                 ovs_nbr[i] = ovs_oi->neighbors[i];
    }
    ovs_nbr[ovs_oi->n_neighbors] = new_ovs_nbr;
    ovsrec_ospf_interface_set_neighbors (ovs_oi,ovs_nbr,ovs_oi->n_neighbors + 1);
    nbr_id = nbr->router_id.s_addr;
    ovsrec_ospf_neighbor_set_nbr_router_id (new_ovs_nbr,&nbr_id,1);

    ip_src = nbr->src.s_addr;
    ovsrec_ospf_neighbor_set_nbr_if_addr (new_ovs_nbr,&ip_src,1);

    if (CHECK_FLAG(nbr->options,OSPF_OPTION_E))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_EXTERNAL_ROUTING;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_MC))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_MULTICAST;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_NP))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_TYPE_7_LSA;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_EA))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_EXTERNAL_ATTRIBUTES_LSA;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_DC))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_DEMAND_CIRCUITS;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_O))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_OPAQUE_LSA;
    }

    ovsrec_ospf_neighbor_set_nbr_options (new_ovs_nbr,value_nbr_option,
                                                             nbr_option_cnt);

    ovsrec_ospf_neighbor_set_nfsm_state (new_ovs_nbr,ospf_nsm_state[nbr->state].str);

    key_nbr_statistics =  xmalloc(OSPF_STAT_NAME_LEN * (OSPF_NEIGHBOR_STATISTICS_MAX));

    value_nbr_statistics =  xmalloc(sizeof *new_ovs_nbr->value_statistics *
                                 (OSPF_NEIGHBOR_STATISTICS_MAX));

    key_nbr_statistics [OSPF_NEIGHBOR_DB_SUMMARY_COUNT] = OSPF_KEY_NEIGHBOR_DB_SUMMARY_CNT;
    key_nbr_statistics [OSPF_NEIGHBOR_LS_REQUEST_COUNT] = OSPF_KEY_NEIGHBOR_LS_REQUEST_CNT;
    key_nbr_statistics [OSPF_NEIGHBOR_LS_RETRANSMIT_COUNT] = OSPF_KEY_NEIGHBOR_LS_RE_TRANSMIT_CNT;
    key_nbr_statistics [OSPF_NEIGHBOR_STATE_CHANGE_COUNT] = OSPF_KEY_NEIGHBOR_STATE_CHG_CNT;

    value_nbr_statistics [OSPF_NEIGHBOR_DB_SUMMARY_COUNT] = 0;
    value_nbr_statistics [OSPF_NEIGHBOR_LS_REQUEST_COUNT] = 0;
    value_nbr_statistics [OSPF_NEIGHBOR_LS_RETRANSMIT_COUNT] = 0;
    value_nbr_statistics [OSPF_NEIGHBOR_STATE_CHANGE_COUNT] = nbr->state_change;

    ovsrec_ospf_neighbor_set_statistics(new_ovs_nbr,key_nbr_statistics,
                          value_nbr_statistics,OSPF_NEIGHBOR_STATISTICS_MAX);

    quagga_gettime(QUAGGA_CLK_MONOTONIC,&tv);
    nbr_up_time = (1000000 * tv.tv_sec + tv.tv_usec)/1000;
    snprintf(buf,sizeof (buf),"%u",nbr_up_time);
    smap_clone (&nbr_status,&(new_ovs_nbr->status));
    smap_replace(&nbr_status, OSPF_KEY_NEIGHBOR_LAST_UP_TIMESTAMP, buf);
    ovsrec_ospf_neighbor_set_status(new_ovs_nbr,&nbr_status);

    status = ovsdb_idl_txn_commit_block(nbr_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("NBR add transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(nbr_txn);
    smap_destroy (&nbr_status);
    free (ovs_nbr);
    free (key_nbr_statistics);
    free (value_nbr_statistics);
    free (value_nbr_option);
    return;
}

void
ovsdb_ospf_add_nbr_self  (struct ospf_neighbor* nbr, char* intf)
{
    struct ovsrec_ospf_interface* ovs_oi = NULL;
    struct ovsrec_ospf_neighbor** ovs_nbr = NULL;
    struct ovsrec_ospf_neighbor* new_ovs_nbr = NULL;
    struct ovsdb_idl_txn* nbr_txn = NULL;
    struct timeval tv;
    struct smap nbr_status;
    int64_t ip_src = 0;
    int64_t nbr_id = 0;
    enum ovsdb_idl_txn_status status;
    char** key_nbr_statistics = NULL;
    char** value_nbr_option = NULL;
    int nbr_option_cnt = 0;
    int64_t* value_nbr_statistics = NULL;
    long nbr_up_time = 0;
    char buf[32] = {0};
    int i = 0;

    if (NULL == nbr)
    {
        VLOG_DBG ("No neighbor data to add");
        return;
    }
    nbr_txn = ovsdb_idl_txn_create(idl);
    if (!nbr_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    if (NULL == intf)
    {
        VLOG_DBG ("No associated interface of neighbor");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    ovs_oi = find_ospf_interface_by_name(intf);
    if (NULL == ovs_oi)
    {
        VLOG_DBG ("No associated interface of neighbor");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    /* Fix me : Update NBR instead of looping through
     * all the neighbor (OVSDB lookup). May be a local cache
     * and if there is change then commit to DB
     */

    new_ovs_nbr = find_ospf_nbr_by_if_addr(ovs_oi,nbr->src);
    if (new_ovs_nbr)
    {
       VLOG_DBG ("Neighbor already present");
       ovsdb_idl_txn_abort(nbr_txn);
       return;
    }
    new_ovs_nbr = ovsrec_ospf_neighbor_insert (nbr_txn);
    if (NULL == new_ovs_nbr)
    {
        VLOG_DBG ("Neighbor insertion failed");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    ovs_nbr = xmalloc(sizeof * ovs_oi->neighbors *
                                    (ovs_oi->n_neighbors + 1));
    for (i = 0; i < ovs_oi->n_neighbors; i++) {
                 ovs_nbr[i] = ovs_oi->neighbors[i];
    }
    ovs_nbr[ovs_oi->n_neighbors] = new_ovs_nbr;
    ovsrec_ospf_interface_set_neighbors (ovs_oi,ovs_nbr,ovs_oi->n_neighbors + 1);
    nbr_id = nbr->router_id.s_addr;
    ovsrec_ospf_neighbor_set_nbr_router_id (new_ovs_nbr,&nbr_id,1);

    ip_src = nbr->src.s_addr;
    ovsrec_ospf_neighbor_set_nbr_if_addr (new_ovs_nbr,&ip_src,1);
    /*  Non-zero TOS are not supported
        if (CHECK_FLAG(nbr->options,OSPF_OPTION_T))
        {
            nbr_option_cnt++;
            if(!value_nbr_option)
                value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
            else
                value_nbr_option = xrealloc(value_nbr_option,
                                      OSPF_STAT_NAME_LEN * (nbr_option_cnt));
            value_nbr_option[nbr_option_cnt -1 ] =
                OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_TYPE_OF_SERVICE;
        }
    */
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_E))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_EXTERNAL_ROUTING;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_MC))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_MULTICAST;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_NP))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_TYPE_7_LSA;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_EA))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_EXTERNAL_ATTRIBUTES_LSA;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_DC))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_DEMAND_CIRCUITS;
    }
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_O))
    {
        nbr_option_cnt++;
        if(!value_nbr_option)
            value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        else
            value_nbr_option = xrealloc(value_nbr_option,
                                  OSPF_STAT_NAME_LEN * (nbr_option_cnt));
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_OPAQUE_LSA;
    }

    ovsrec_ospf_neighbor_set_nbr_options (new_ovs_nbr,value_nbr_option,
                                                             nbr_option_cnt);

    ovsrec_ospf_neighbor_set_nfsm_state (new_ovs_nbr,ospf_nsm_state[nbr->state].str);

    key_nbr_statistics =  xmalloc(OSPF_STAT_NAME_LEN * (OSPF_NEIGHBOR_STATISTICS_MAX));

    value_nbr_statistics =  xmalloc(sizeof *new_ovs_nbr->value_statistics *
                                 (OSPF_NEIGHBOR_STATISTICS_MAX));

    key_nbr_statistics [OSPF_NEIGHBOR_DB_SUMMARY_COUNT] = OSPF_KEY_NEIGHBOR_DB_SUMMARY_CNT;
    key_nbr_statistics [OSPF_NEIGHBOR_LS_REQUEST_COUNT] = OSPF_KEY_NEIGHBOR_LS_REQUEST_CNT;
    key_nbr_statistics [OSPF_NEIGHBOR_LS_RETRANSMIT_COUNT] = OSPF_KEY_NEIGHBOR_LS_RE_TRANSMIT_CNT;
    key_nbr_statistics [OSPF_NEIGHBOR_STATE_CHANGE_COUNT] = OSPF_KEY_NEIGHBOR_STATE_CHG_CNT;

    value_nbr_statistics [OSPF_NEIGHBOR_DB_SUMMARY_COUNT] = 0;
    value_nbr_statistics [OSPF_NEIGHBOR_LS_REQUEST_COUNT] = 0;
    value_nbr_statistics [OSPF_NEIGHBOR_LS_RETRANSMIT_COUNT] = 0;
    value_nbr_statistics [OSPF_NEIGHBOR_STATE_CHANGE_COUNT] = nbr->state_change;

    ovsrec_ospf_neighbor_set_statistics(new_ovs_nbr,key_nbr_statistics,
                          value_nbr_statistics,OSPF_NEIGHBOR_STATISTICS_MAX);

    quagga_gettime(QUAGGA_CLK_MONOTONIC,&tv);
    nbr_up_time = (1000000 * tv.tv_sec + tv.tv_usec)/1000;
    snprintf(buf,sizeof (buf),"%u",nbr_up_time);
    smap_clone (&nbr_status,&(new_ovs_nbr->status));
    smap_replace(&nbr_status, OSPF_KEY_NEIGHBOR_LAST_UP_TIMESTAMP, buf);
    ovsrec_ospf_neighbor_set_status(new_ovs_nbr,&nbr_status);

    status = ovsdb_idl_txn_commit_block(nbr_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("NBR add transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(nbr_txn);
    smap_destroy (&nbr_status);
    free (ovs_nbr);
    free (key_nbr_statistics);
    free (value_nbr_statistics);
    free (value_nbr_option);
    return;
}

void
ovsdb_ospf_set_nbr_self_router_id  (char* ifname, struct in_addr if_addr,
                                                struct in_addr router_id)
{
    struct ovsrec_ospf_interface* ovs_oi = NULL;
    struct ovsrec_ospf_neighbor* ovs_nbr = NULL;
    struct ovsdb_idl_txn* nbr_txn = NULL;
    enum ovsdb_idl_txn_status status;
    int64_t nbr_router_id = 0;

    nbr_txn = ovsdb_idl_txn_create(idl);
    if (!nbr_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    if (NULL == ifname)
    {
        VLOG_DBG ("No associated interface of neighbor");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    ovs_oi = find_ospf_interface_by_name(ifname);
    if (NULL == ovs_oi)
    {
        VLOG_DBG ("No associated interface of neighbor");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    ovs_nbr = find_ospf_nbr_by_if_addr(ovs_oi,if_addr);
    if (!ovs_nbr)
    {
       VLOG_DBG ("Self neighbor not present");
       ovsdb_idl_txn_abort(nbr_txn);
       return;
    }
    nbr_router_id = router_id.s_addr;
    ovsrec_ospf_neighbor_set_nbr_router_id(ovs_nbr,&nbr_router_id,1);
    status = ovsdb_idl_txn_commit_block(nbr_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("NBR add transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(nbr_txn);
}

void
ovsdb_ospf_set_nbr_self_priority(char* ifname, struct in_addr if_addr,
                                 int64_t priority)
{
    struct ovsrec_ospf_interface* ovs_oi = NULL;
    struct ovsrec_ospf_neighbor* ovs_nbr = NULL;
    struct ovsdb_idl_txn* nbr_txn = NULL;
    enum ovsdb_idl_txn_status status;

    if (NULL == ifname)
    {
        VLOG_DBG ("No associated interface of neighbor");
        return;
    }
    ovs_oi = find_ospf_interface_by_name(ifname);
    if (NULL == ovs_oi)
    {
        VLOG_DBG ("No associated interface of neighbor");
        return;
    }
    ovs_nbr = find_ospf_nbr_by_if_addr(ovs_oi,if_addr);
    if (!ovs_nbr)
    {
       VLOG_DBG ("Self neighbor not present");
       return;
    }

    nbr_txn = ovsdb_idl_txn_create(idl);
    if (!nbr_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }

    ovsrec_ospf_neighbor_set_nbr_priority(ovs_nbr,&priority,1);

    status = ovsdb_idl_txn_commit_block(nbr_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("NBR add transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(nbr_txn);
}

void
ovsdb_ospf_reset_nbr_self  (struct ospf_neighbor* nbr, char* intf)
{
    struct ovsrec_ospf_interface* ovs_oi = NULL;
    struct ovsrec_ospf_neighbor* new_ovs_nbr = NULL;
    struct ovsdb_idl_txn* nbr_txn = NULL;
    struct timeval tv;
    struct smap nbr_status;
    int64_t ip_src = 0;
    int64_t nbr_id = 0;
    enum ovsdb_idl_txn_status status;
    char** key_nbr_statistics = NULL;
    char** value_nbr_option = NULL;
    int nbr_option_cnt = 0;
    int64_t* value_nbr_statistics = NULL;
    long nbr_up_time = 0;
    char buf[32] = {0};
    int i = 0;

    if (NULL == nbr)
    {
        VLOG_DBG ("No neighbor data to add");
        return;
    }

    if (NULL == intf)
    {
        VLOG_DBG ("No associated interface of neighbor");
        return;
    }

    ovs_oi = find_ospf_interface_by_name(intf);
    if (NULL == ovs_oi)
    {
        VLOG_DBG ("No associated interface of neighbor");
        return;
    }
    /* Fix me : Update NBR instead of looping through
     * all the neighbor (OVSDB lookup). May be a local cache
     * and if there is change then commit to DB
     */

    new_ovs_nbr = find_ospf_nbr_by_if_addr(ovs_oi,nbr->src);
    if (!new_ovs_nbr)
    {
       VLOG_DBG ("Neighbor not present");
       return;
    }

    nbr_txn = ovsdb_idl_txn_create(idl);
    if (!nbr_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }

    nbr_id = nbr->router_id.s_addr;
    ovsrec_ospf_neighbor_set_nbr_router_id (new_ovs_nbr,&nbr_id,1);

    ip_src = nbr->src.s_addr;
    ovsrec_ospf_neighbor_set_nbr_if_addr (new_ovs_nbr,&ip_src,1);


    nbr_option_cnt = ovsdb_options_count(nbr->options);
    value_nbr_option = xmalloc(OSPF_STAT_NAME_LEN * (nbr_option_cnt + 1));
    if(!value_nbr_option)
        assert(0);

    nbr_option_cnt = 0;
    if (CHECK_FLAG(nbr->options,OSPF_OPTION_E))
    {
        nbr_option_cnt++;
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_EXTERNAL_ROUTING;
    }

    if (CHECK_FLAG(nbr->options,OSPF_OPTION_MC))
    {
        nbr_option_cnt++;
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_MULTICAST;
    }

    if (CHECK_FLAG(nbr->options,OSPF_OPTION_NP))
    {
        nbr_option_cnt++;
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_TYPE_7_LSA;
    }

    if (CHECK_FLAG(nbr->options,OSPF_OPTION_EA))
    {
        nbr_option_cnt++;
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_EXTERNAL_ATTRIBUTES_LSA;
    }

    if (CHECK_FLAG(nbr->options,OSPF_OPTION_DC))
    {
        nbr_option_cnt++;
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_DEMAND_CIRCUITS;
    }

    if (CHECK_FLAG(nbr->options,OSPF_OPTION_O))
    {
        nbr_option_cnt++;
        value_nbr_option[nbr_option_cnt -1 ] =
            OVSREC_OSPF_NEIGHBOR_NBR_OPTIONS_OPAQUE_LSA;
    }

    ovsrec_ospf_neighbor_set_nbr_options (new_ovs_nbr,value_nbr_option,
                                                             nbr_option_cnt);

    ovsrec_ospf_neighbor_set_nfsm_state (new_ovs_nbr,ospf_nsm_state[nbr->state].str);

    key_nbr_statistics =  xmalloc(OSPF_STAT_NAME_LEN * (OSPF_NEIGHBOR_STATISTICS_MAX));

    value_nbr_statistics =  xmalloc(sizeof *new_ovs_nbr->value_statistics *
                                 (OSPF_NEIGHBOR_STATISTICS_MAX));

    if(!key_nbr_statistics || !value_nbr_statistics)
    {
        assert(0);
    }

    key_nbr_statistics [OSPF_NEIGHBOR_DB_SUMMARY_COUNT] =
                                    OSPF_KEY_NEIGHBOR_DB_SUMMARY_CNT;
    key_nbr_statistics [OSPF_NEIGHBOR_LS_REQUEST_COUNT] =
                                    OSPF_KEY_NEIGHBOR_LS_REQUEST_CNT;
    key_nbr_statistics [OSPF_NEIGHBOR_LS_RETRANSMIT_COUNT] =
                                    OSPF_KEY_NEIGHBOR_LS_RE_TRANSMIT_CNT;
    key_nbr_statistics [OSPF_NEIGHBOR_STATE_CHANGE_COUNT] =
                                    OSPF_KEY_NEIGHBOR_STATE_CHG_CNT;

    value_nbr_statistics [OSPF_NEIGHBOR_DB_SUMMARY_COUNT] = 0;
    value_nbr_statistics [OSPF_NEIGHBOR_LS_REQUEST_COUNT] = 0;
    value_nbr_statistics [OSPF_NEIGHBOR_LS_RETRANSMIT_COUNT] = 0;
    value_nbr_statistics [OSPF_NEIGHBOR_STATE_CHANGE_COUNT] = nbr->state_change;

    ovsrec_ospf_neighbor_set_statistics(new_ovs_nbr,key_nbr_statistics,
                          value_nbr_statistics,OSPF_NEIGHBOR_STATISTICS_MAX);



    quagga_gettime(QUAGGA_CLK_MONOTONIC,&tv);
    nbr_up_time = (1000000 * tv.tv_sec + tv.tv_usec)/1000;
    snprintf(buf,sizeof (buf),"%u",nbr_up_time);
    smap_clone (&nbr_status,&(new_ovs_nbr->status));
    smap_replace(&nbr_status, OSPF_KEY_NEIGHBOR_LAST_UP_TIMESTAMP, buf);
    ovsrec_ospf_neighbor_set_status(new_ovs_nbr,&nbr_status);

    status = ovsdb_idl_txn_commit_block(nbr_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("self NBR reset transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(nbr_txn);
    smap_destroy (&nbr_status);
    free (key_nbr_statistics);
    free (value_nbr_statistics);
    free (value_nbr_option);
    return;
}


void
ovsdb_ospf_delete_nbr  (struct ospf_neighbor* nbr)
{
    struct ovsrec_ospf_interface* ovs_oi = NULL;
    struct ovsrec_ospf_neighbor** ovs_nbr = NULL;
    struct ovsrec_ospf_neighbor* old_ovs_nbr = NULL;
    struct ovsdb_idl_txn* nbr_txn = NULL;
    struct interface* intf = NULL;
    int64_t ip_src = 0;
    enum ovsdb_idl_txn_status status;
    int i = 0,j = 0;

    if (NULL == nbr)
    {
        VLOG_DBG ("No neighbor data to delete");
        return;
    }

    if (NULL == nbr->oi)
    {
        VLOG_DBG ("No associated interface of neighbor");
        return;
    }

    intf = nbr->oi->ifp;
    if (NULL == intf)
    {
        VLOG_DBG ("No associated interface of neighbor");
        return;
    }

    ovs_oi = find_ospf_interface_by_name(intf->name);
    if (NULL == ovs_oi)
    {
        VLOG_DBG ("No associated interface of neighbor");
        return;
    }
    /* Fix me : Update NBR instead of looping through
     * all the neighbor (OVSDB lookup). May be a local cache
     * and if there is change then commit to DB
     */
    old_ovs_nbr = find_ospf_nbr_by_if_addr(ovs_oi,nbr->src);
    if (!old_ovs_nbr)
    {
       VLOG_DBG ("Neighbor not found");
       return;
    }

    nbr_txn = ovsdb_idl_txn_create(idl);
    if (!nbr_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }

    ovs_nbr = xmalloc(sizeof * ovs_oi->neighbors *
                                    (ovs_oi->n_neighbors - 1));

    ip_src = nbr->src.s_addr;
    for (i = 0, j =0; i < ovs_oi->n_neighbors; i++) {
       if (ip_src != ovs_oi->neighbors[i]->nbr_if_addr[0])
          ovs_nbr[j++] = ovs_oi->neighbors[i];
    }
    ovsrec_ospf_interface_set_neighbors (ovs_oi,ovs_nbr,ovs_oi->n_neighbors - 1);

    ovsrec_ospf_neighbor_delete (old_ovs_nbr);

    status = ovsdb_idl_txn_commit_block(nbr_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("NBR delete transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(nbr_txn);
    free (ovs_nbr);
    return;
}


void
ovsdb_ospf_delete_nbr_self  (struct ospf_neighbor* nbr, char* ifname)
{
    struct ovsrec_ospf_interface* ovs_oi = NULL;
    struct ovsrec_ospf_neighbor** ovs_nbr = NULL;
    struct ovsrec_ospf_neighbor* old_ovs_nbr = NULL;
    struct ovsdb_idl_txn* nbr_txn = NULL;
    int64_t ip_src = 0;
    enum ovsdb_idl_txn_status status;
    int i = 0,j = 0;

    if (NULL == nbr)
    {
        VLOG_DBG ("No neighbor data to delete");
        return;
    }
    if (NULL == nbr->oi)
    {
        VLOG_DBG ("No associated interface of neighbor");
        return;
    }

    nbr_txn = ovsdb_idl_txn_create(idl);
    if (!nbr_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    if (NULL == ifname)
    {
        VLOG_DBG ("No associated interface of neighbor");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    ovs_oi = find_ospf_interface_by_name(ifname);
    if (NULL == ovs_oi)
    {
        VLOG_DBG ("No associated interface of neighbor");
        ovsdb_idl_txn_abort(nbr_txn);
        return;
    }
    /* Fix me : Update NBR instead of looping through
     * all the neighbor (OVSDB lookup). May be a local cache
     * and if there is change then commit to DB
     */

    old_ovs_nbr = find_ospf_nbr_by_if_addr(ovs_oi,nbr->src);
    if (!old_ovs_nbr)
    {
       VLOG_DBG ("Neighbor not found");
       ovsdb_idl_txn_abort(nbr_txn);
       return;
    }
    ovs_nbr = xmalloc(sizeof * ovs_oi->neighbors *
                                    (ovs_oi->n_neighbors - 1));

    ip_src = nbr->src.s_addr;
    for (i = 0,j = 0; i < ovs_oi->n_neighbors; i++) {
       if (ip_src != ovs_oi->neighbors[i]->nbr_if_addr[0])
          ovs_nbr[j++] = ovs_oi->neighbors[i];
    }
    ovsrec_ospf_interface_set_neighbors (ovs_oi,ovs_nbr,ovs_oi->n_neighbors - 1);

    ovsrec_ospf_neighbor_delete (old_ovs_nbr);

    status = ovsdb_idl_txn_commit_block(nbr_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("NBR delete transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(nbr_txn);
    free (ovs_nbr);
    return;
}

void
ovsdb_ospf_add_area_to_router (int ospf_intance,struct in_addr area_id)
{
    int64_t *area;
    struct ovsrec_ospf_router* ospf_router_row = NULL;
    struct ovsrec_ospf_area* area_row = NULL;
    struct ovsrec_ospf_area **area_list;
    struct ovsdb_idl_txn* area_txn = NULL;
    enum ovsdb_idl_txn_status status;
    int i = 0;

    ospf_router_row =
        ovsdb_ospf_get_router_by_instance_num (ospf_intance);
    if (!ospf_router_row)
    {
       VLOG_DBG ("No OSPF router found");
       ovsdb_idl_txn_abort(area_txn);
       return;
    }

    for (i = 0; i < ospf_router_row->n_areas; i++)
    {
        if (ospf_router_row->key_areas[i] == area_id.s_addr)
            return;
    }
	
    area_txn = ovsdb_idl_txn_create(idl);
    if (!area_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }

    area_row = ovsrec_ospf_area_insert(area_txn);
    if (!area_row)
    {
       VLOG_DBG ("OSPF area insert failed");
       ovsdb_idl_txn_abort(area_txn);
       return;
    }

    /* Insert OSPF_Area table reference in OSPF_Router table. */
    area = xmalloc(sizeof(int64_t) * (ospf_router_row->n_areas + 1));
    area_list = xmalloc(sizeof * ospf_router_row->key_areas *
                              (ospf_router_row->n_areas + 1));
    for (i = 0; i < ospf_router_row->n_areas; i++)
    {
        area[i] = ospf_router_row->key_areas[i];
        area_list[i] = ospf_router_row->value_areas[i];
    }
    area[ospf_router_row->n_areas] = area_id.s_addr;
    area_list[ospf_router_row->n_areas] =
                        CONST_CAST(struct ovsrec_ospf_area *, area_row);
    ovsrec_ospf_router_set_areas(ospf_router_row, area, area_list,
                               (ospf_router_row->n_areas + 1));
    ovsdb_ospf_set_area_tbl_default (area_row);

    status = ovsdb_idl_txn_commit_block(area_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("Area transaction commit failed:%d",status);

    ovsdb_idl_txn_destroy(area_txn);

    free(area);
    free(area_list);

    return;
}

void
ovsdb_ospf_set_spf_statistics (int instance, struct in_addr area_id,
                              long spf_ts, int spf_count)
{
    struct ovsrec_ospf_area* ovs_area = NULL;
    struct ovsrec_ospf_router* ovs_ospf = NULL;
    bool is_found = false;
    char buf[32] = {0};
    struct smap spf_smap;
    struct ovsdb_idl_txn* spf_txn = NULL;
    enum ovsdb_idl_txn_status status;
    int i = 0;

    ovs_ospf = ovsdb_ospf_get_router_by_instance_num (instance);
    if (!ovs_ospf)
    {
       VLOG_DBG ("No OSPF instance");
       return;
    }

    for (i = 0 ; i < ovs_ospf->n_areas ; i++)
    {
       if (ovs_ospf->key_areas[i] == area_id.s_addr)
        {
            ovs_area = ovs_ospf->value_areas[i];
            is_found = true;
            break;
        }
    }

    if (!is_found)
    {
       VLOG_DBG ("No area %s found", inet_ntoa (area_id));
       return;
    }

    spf_txn = ovsdb_idl_txn_create (idl);
    if (!spf_txn)
    {
       VLOG_DBG ("Transaction create failed");
       return;
    }

    snprintf(buf,sizeof (buf),"%u",spf_ts);
    smap_clone (&spf_smap, &(ovs_area->status));
    smap_replace (&spf_smap, OSPF_KEY_AREA_SPF_LAST_RUN, buf);

    ovsrec_ospf_area_set_status(ovs_area,&spf_smap);

    for (i = 0 ; i < ovs_area->n_statistics ; i++)
    {
        if (0 == strcmp (ovs_area->key_statistics[i],
                      OSPF_KEY_AREA_STATS_SPF_EXEC)) {
            ovs_area->value_statistics[i] = (int64_t)spf_count;
            break;
        }
    }

    ovsrec_ospf_area_set_statistics(ovs_area,ovs_area->key_statistics,
                        ovs_area->value_statistics,ovs_area->n_statistics);

    status = ovsdb_idl_txn_commit_block (spf_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("Set OSPF SPF statistics failed : %d",status);

    ovsdb_idl_txn_destroy (spf_txn);

    smap_destroy (&spf_smap);
}

void
ovsdb_ospf_set_dead_time_intervals (char* ifname, int interval_type,long time_msec,
                                      struct in_addr src)
{
    struct smap interval_smap;
    struct ovsrec_ospf_interface* ospf_if_row = NULL;
    struct ovsrec_ospf_neighbor* ospf_nbr_row = NULL;
    struct ovsdb_idl_txn* if_txn = NULL;
    enum ovsdb_idl_txn_status status;
    char buf[32] = {0};

    if (NULL == ifname)
    {
        VLOG_DBG ("Invalid Interface/Neighbor name");
        return;
    }
    if_txn = ovsdb_idl_txn_create (idl);
    if (!if_txn)
    {
       VLOG_DBG ("Transaction create failed");
       return;
       //smap_destroy (&interval_smap);
    }
    ospf_if_row = find_ospf_interface_by_name(ifname);
    if (!ospf_if_row)
    {
       VLOG_DBG ("No OSPF interface found");
       ovsdb_idl_txn_abort (if_txn);
       return;
    }
    ospf_nbr_row = find_ospf_nbr_by_if_addr(ospf_if_row,src);
    if (!ospf_nbr_row)
    {
       VLOG_DBG ("No OSPF Neighbor found");
       ovsdb_idl_txn_abort (if_txn);
       return;
    }
    snprintf(buf,sizeof (buf),"%u",time_msec);
    smap_clone (&interval_smap,&(ospf_nbr_row->status));
    smap_replace(&interval_smap, OSPF_KEY_NEIGHBOR_DEAD_TIMER_DUE, buf);
    ovsrec_ospf_neighbor_set_status(ospf_nbr_row,&interval_smap);

    status = ovsdb_idl_txn_commit_block (if_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("OSPF interval commit failed : %d",status);

    ovsdb_idl_txn_destroy (if_txn);
    smap_destroy (&interval_smap);

    return;
}

void
ovsdb_ospf_set_hello_time_intervals (const char* ifname, int interval_type,long time_msec)
{
    struct smap interval_smap;
    struct ovsrec_ospf_interface* ospf_if_row = NULL;
    struct ovsrec_ospf_neighbor* ospf_nbr_row = NULL;
    struct ovsdb_idl_txn* if_txn = NULL;
    enum ovsdb_idl_txn_status status;
    char buf[32] = {0};

    if (NULL == ifname)
    {
        VLOG_DBG ("Invalid Interface/Neighbor name");
        return;
    }
    //smap_init (&interval_smap);
    if_txn = ovsdb_idl_txn_create (idl);
    if (!if_txn)
    {
       VLOG_DBG ("Transaction create failed");
       return;
       //smap_destroy (&interval_smap);
    }

    ospf_if_row = find_ospf_interface_by_name(ifname);
    if (!ospf_if_row)
    {
       VLOG_DBG ("No OSPF interface found");
       ovsdb_idl_txn_abort (if_txn);
       return;
    }
    snprintf(buf,sizeof (buf),"%u",time_msec);
    smap_clone (&interval_smap,&(ospf_if_row->status));
    smap_replace (&interval_smap, OSPF_KEY_HELLO_DUE, buf);
    ovsrec_ospf_interface_set_status(ospf_if_row,&interval_smap);

    status = ovsdb_idl_txn_commit_block (if_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("OSPF interval commit failed : %d",status);

    ovsdb_idl_txn_destroy (if_txn);
    smap_destroy (&interval_smap);
}


/* Set the values in the area table to default. */
void ovsdb_ospf_set_area_tbl_default (const struct ovsrec_ospf_area *area_row)
{
    char** key_area_statistics = NULL;
    int64_t *area_stat_value = NULL;

    if (area_row == NULL)
    {
        return;
    }
    ovsrec_ospf_area_set_area_type(area_row,
                             OVSREC_OSPF_AREA_AREA_TYPE_DEFAULT);
    ovsrec_ospf_area_set_nssa_translator_role(area_row,
                             OVSREC_OSPF_AREA_NSSA_TRANSLATOR_ROLE_CANDIDATE);

    key_area_statistics =
        xmalloc(OSPF_STAT_NAME_LEN * (OSPF_AREA_STATISTICS_MAX));
    area_stat_value =
        xmalloc(sizeof *area_row->value_statistics *
                              (OSPF_AREA_STATISTICS_MAX));

    /* OPS_TODO : Map OSPF memtypes in memtype.h and use XSTRDUP */
    key_area_statistics[OSPF_AREA_STATISTICS_SPF_CALC] =
                           OSPF_KEY_AREA_STATS_SPF_EXEC;
    key_area_statistics[OSPF_AREA_STATISTICS_ABR_COUNT] =
                           OSPF_KEY_AREA_STATS_ABR_COUNT;
    key_area_statistics[OSPF_AREA_STATISTICS_ASBR_COUNT] =
                           OSPF_KEY_AREA_STATS_ASBR_COUNT;

    area_stat_value[OSPF_AREA_STATISTICS_SPF_CALC] = 0;
    area_stat_value[OSPF_AREA_STATISTICS_ABR_COUNT] = 0;
    area_stat_value[OSPF_AREA_STATISTICS_ASBR_COUNT] = 0;

    ovsrec_ospf_area_set_statistics(area_row,key_area_statistics,
                        area_stat_value,OSPF_AREA_STATISTICS_MAX);

    free (key_area_statistics);
    free(area_stat_value);
}


/* Set default OSPF interface config values  */
void ovsdb_ospf_set_interface_if_config_tbl_default  (const struct ovsrec_port *ovs_port)
{
    char** key_ospf_interval = NULL;
    int64_t* value_ospf_interval = NULL;
    int64_t ospf_if_cost = 0;
    int64_t ospf_priority = 0;
    bool ospf_mtu_ignore = false;
    char show_str[10];

    if (ovs_port == NULL)
    {
        return;
    }

    key_ospf_interval =
        xmalloc(OSPF_STAT_NAME_LEN * (OSPF_INTERVAL_MAX));

    value_ospf_interval =
           xmalloc(sizeof *ovs_port->value_ospf_intervals*
                                 (OSPF_INTERVAL_MAX));

    key_ospf_interval [OSPF_INTERVAL_TRANSMIT_DELAY] = OSPF_KEY_TRANSMIT_DELAY;
    key_ospf_interval [OSPF_INTERVAL_RETRANSMIT_INTERVAL] = OSPF_KEY_RETRANSMIT_INTERVAL;
    key_ospf_interval [OSPF_INTERVAL_HELLO_INTERVAL] = OSPF_KEY_HELLO_INTERVAL;
    key_ospf_interval [OSPF_INTERVAL_DEAD_INTERVAL] = OSPF_KEY_DEAD_INTERVAL;

    value_ospf_interval [OSPF_INTERVAL_TRANSMIT_DELAY] = OSPF_TRANSMIT_DELAY_DEFAULT;
    value_ospf_interval [OSPF_INTERVAL_RETRANSMIT_INTERVAL] = OSPF_RETRANSMIT_INTERVAL_DEFAULT;
    value_ospf_interval [OSPF_INTERVAL_HELLO_INTERVAL] = OSPF_HELLO_INTERVAL_DEFAULT;
    value_ospf_interval [OSPF_INTERVAL_DEAD_INTERVAL] = OSPF_ROUTER_DEAD_INTERVAL_DEFAULT;


    ovsrec_port_set_ospf_intervals(ovs_port,key_ospf_interval,value_ospf_interval,OSPF_INTERVAL_MAX);

    ospf_priority = OSPF_ROUTER_PRIORITY_DEFAULT;
    ovsrec_port_set_ospf_priority(ovs_port,&ospf_priority,1);
    ospf_mtu_ignore = OSPF_MTU_IGNORE_DEFAULT;
    ovsrec_port_set_ospf_mtu_ignore(ovs_port,&ospf_mtu_ignore,1);
    ospf_if_cost = OSPF_OUTPUT_COST_DEFAULT;
    ovsrec_port_set_ospf_if_out_cost(ovs_port,&ospf_if_cost,1);
    ovsrec_port_set_ospf_if_type(ovs_port,OVSREC_PORT_OSPF_IF_TYPE_OSPF_IFTYPE_BROADCAST);

}

/* Default the values if OSPF_interface_Config table. */
void ospf_interface_tbl_default(
                  const struct ovsrec_ospf_interface *ospf_if_row)
{
    struct smap smap;
    char show_str[10] = {0};

    if (ospf_if_row == NULL)
       return;
    snprintf(show_str, sizeof(show_str), "%d", OSPF_INTERFACE_ACTIVE);
    smap_clone (&smap, &(ospf_if_row->status));
    smap_replace (&smap, OSPF_KEY_INTERFACE_ACTIVE, (const char *)show_str);

    ovsrec_ospf_interface_set_status(ospf_if_row,&smap);

    smap_destroy(&smap);
}


/* Set the reference to the interface row to the area table. */
void
ovsdb_area_set_interface(int instance,struct in_addr area_id,
                    struct ospf_interface* oi)
{
    struct ovsrec_ospf_interface **ospf_interface_list;
    struct ovsrec_ospf_interface* interface_row = NULL;
    struct ovsrec_port* ovs_port = NULL;
    struct ovsrec_ospf_vlink* ovs_vl = NULL;
    struct ovsrec_ospf_router* ovs_ospf = NULL;
    struct ovsrec_ospf_area* area_row = NULL;
    struct ovsdb_idl_txn* intf_txn = NULL;
    enum ovsdb_idl_txn_status status;
    struct smap area_smap;
    char buf[10] = {0};
    int i = 0;

    ovs_ospf = ovsdb_ospf_get_router_by_instance_num (instance);
    if (!ovs_ospf)
    {
       VLOG_DBG ("No associated OSPF instance exist");
       return;
    }
    area_row = ovsrec_ospf_area_get_area_by_id(ovs_ospf,area_id);
    if (!area_row)
    {
       VLOG_DBG ("No associated OSPF area : %d exist",area_id.s_addr);
       return;
    }
    if (NULL == oi ||
        NULL == oi->ifp ||
        NULL == oi->ifp->name)
    {
       VLOG_DBG ("No associated Interface exist");
       return;
    }

   /* OPS_TODO : Handle loopback/NBMA interfaces */
    if (OSPF_IFTYPE_VIRTUALLINK != oi->type &&
        OSPF_IFTYPE_NBMA != oi->type &&
        OSPF_IFTYPE_NONE != oi->type) {
       /* Normal interface */
       ovs_port = find_port_by_name(oi->ifp->name);
       if (!ovs_port)
       {
          VLOG_DBG ("No associated port exist for %s",oi->ifp->name);
          return;
       }
    }
    else if (OSPF_IFTYPE_VIRTUALLINK == oi->type){
       /* Virtual link interface */
       ovs_vl= find_ospf_vl_by_name(oi->ifp->name);
       if (!ovs_vl)
       {
          VLOG_DBG ("No associated VLINK exist for %s",oi->ifp->name);
          return;
       }
    }
    else {
       VLOG_DBG ("Invalid OSPF interface type");
       return;
    }

    for (i = 0; i < area_row->n_ospf_interfaces; i++) {
        if (!strcmp(area_row->ospf_interfaces[i]->name, oi->ifp->name))
            return;         
    }
	
    intf_txn = ovsdb_idl_txn_create(idl);
    if (!intf_txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    interface_row = ovsrec_ospf_interface_insert(intf_txn);
    if (!interface_row)
    {
       VLOG_DBG ("OSPF interface insert failed");
       ovsdb_idl_txn_abort(intf_txn);
       return;
    }
    /* Insert OSPF_Interface table reference in OSPF_Area table. */
    ospf_interface_list = xmalloc(sizeof * area_row->ospf_interfaces *
                              (area_row->n_ospf_interfaces + 1));
    for (i = 0; i < area_row->n_ospf_interfaces; i++) {
        ospf_interface_list[i] = area_row->ospf_interfaces[i];
    }
    ospf_interface_list[area_row->n_ospf_interfaces] =
                        CONST_CAST(struct ovsrec_ospf_interface *, interface_row);
    ovsrec_ospf_area_set_ospf_interfaces(area_row, ospf_interface_list,
                               (area_row->n_ospf_interfaces + 1));

    ovsdb_ospf_set_interface_if_config_tbl_default (ovs_port);
    ovsrec_ospf_interface_set_ifsm_state(interface_row,
                                             OSPF_INTERFACE_IFSM_DEPEND_ON);
    ovsrec_ospf_interface_set_name(interface_row, oi->ifp->name);

    ospf_interface_tbl_default(interface_row);

    /* OPS_TODO : Need to check for passive interfaces */
    snprintf (buf,sizeof (buf),"%d",area_row->n_ospf_interfaces);
    smap_clone (&area_smap,&(area_row->status));
    smap_replace (&area_smap,OSPF_KEY_AREA_ACTIVE_INTERFACE,buf);
    ovsrec_ospf_area_set_status(area_row,&area_smap);

    if(OSPF_IFTYPE_VIRTUALLINK == oi->type)
        ovsrec_ospf_interface_set_ospf_vlink(interface_row,ovs_vl);
    else
        ovsrec_ospf_interface_set_port(interface_row,ovs_port);
    status = ovsdb_idl_txn_commit_block(intf_txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("OSPF interface transaction commit failed : %d",status);

    ovsdb_idl_txn_destroy(intf_txn);

    free(ospf_interface_list);

    return;
}

void
ovsdb_ospf_update_ifsm_state  (char* ifname, int ism_state)
{
    struct ovsrec_ospf_interface* ovs_oi = NULL;
    struct ovsdb_idl_txn* txn = NULL;
    enum ovsdb_idl_txn_status status;

    if (NULL == ifname)
    {
       VLOG_DBG ("No OSPF interface found");
       return;
    }
    ovs_oi = find_ospf_interface_by_name(ifname);
    if (!ovs_oi)
    {
       VLOG_DBG ("No OSPF interface found");
       return;
    }
    txn = ovsdb_idl_txn_create(idl);
    if (!txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }

    ovsrec_ospf_interface_set_ifsm_state(ovs_oi,ospf_ism_state[ism_state].str);

    status = ovsdb_idl_txn_commit_block(txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("OSPF interface transaction commit failed : %d",status);

    ovsdb_idl_txn_destroy(txn);
}


/* Check if any non default values is present in area table.
    If present then return false. Else true. */
int
ovsdb_ospf_is_area_tbl_empty(const struct ovsrec_ospf_area *ospf_area_row)
{
    const char *val;
    int i = 0;

    if (ospf_area_row->n_ospf_interfaces > 0)
        return false;

   if (ospf_area_row->area_type &&
          (0 != strcmp (ospf_area_row->area_type,OVSREC_OSPF_AREA_AREA_TYPE_DEFAULT)))
            return false;

    if (0 == strcmp (ospf_area_row->nssa_translator_role,OVSREC_OSPF_AREA_NSSA_TRANSLATOR_ROLE_ALWAYS) ||
        0 == strcmp (ospf_area_row->nssa_translator_role,OVSREC_OSPF_AREA_NSSA_TRANSLATOR_ROLE_NEVER))
        return false;

    if (ospf_area_row->n_ospf_vlinks > 0)
        return false;

    if (ospf_area_row->n_ospf_area_summary_addresses > 0)
        return false;

    if (ospf_area_row->ospf_auth_type)
        return false;

    return true;
}

/* Remove the area row matching the area id and remove reference from the router table. */
void
ovsdb_ospf_remove_area_from_router (int instance,
                              struct in_addr area_id)
{
    int64_t *area;
    struct ovsrec_ospf_area **area_list;
    struct ovsrec_ospf_router* ospf_router_row = NULL;
    struct ovsrec_ospf_area* ovs_area = NULL;
    struct ovsdb_idl_txn* txn = NULL;
    enum ovsdb_idl_txn_status status;
    int i = 0, j;

    txn = ovsdb_idl_txn_create(idl);
    if (!txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    ospf_router_row = ovsdb_ospf_get_router_by_instance_num (instance);
    if (!ospf_router_row)
    {
        VLOG_DBG ("No OSPF instance there");
        ovsdb_idl_txn_abort(txn);
        return;
    }

    ovs_area = ovsrec_ospf_area_get_area_by_id(ospf_router_row,area_id);
    if (!ovs_area)
    {
        VLOG_DBG ("No OSPF area there");
        ovsdb_idl_txn_abort(txn);
        return;
    }
    if (ovsdb_ospf_is_area_tbl_empty(ovs_area))
    {
        /* Remove OSPF_area table reference in OSPF_Router table. */
        area = xmalloc(sizeof(int64_t) * (ospf_router_row->n_areas - 1));
        area_list = xmalloc(sizeof * ospf_router_row->key_areas *
                                  (ospf_router_row->n_areas - 1));
        for (i = 0, j = 0; i < ospf_router_row->n_areas; i++) {
            if(ospf_router_row->key_areas[i] !=  area_id.s_addr) {
                area[j] = ospf_router_row->key_areas[i];
                area_list[j] = ospf_router_row->value_areas[i];
                j++;
            }
        }
        ovsrec_ospf_router_set_areas(ospf_router_row, area, area_list,
                                   (ospf_router_row->n_areas - 1));
        ovsrec_ospf_area_delete(ovs_area);

        free(area);
        free(area_list);
    }
    status = ovsdb_idl_txn_commit_block(txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("Transaction commit error");

    ovsdb_idl_txn_destroy(txn);
}

/* Remove the interface row matching the interface name and remove the reference from
     area table. */
void
ovsdb_ospf_remove_interface_from_area (int instance, struct in_addr area_id,
                                      char* ifname)
{
    struct ovsrec_ospf_interface **ospf_interface_list;
    struct ovsrec_ospf_area* area_row = NULL;
    struct ovsrec_ospf_router* ovs_ospf = NULL;
    struct ovsrec_ospf_interface* ovs_oi = NULL;
    struct ovsrec_port* ovs_port = NULL;
    struct ovsdb_idl_txn* txn = NULL;
    enum ovsdb_idl_txn_status status;
    struct smap area_smap;
    char buf[10] = {0};
    int i, j;

    txn = ovsdb_idl_txn_create(idl);
    if (!txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    ovs_ospf = ovsdb_ospf_get_router_by_instance_num (instance);
    if (!ovs_ospf)
    {
        VLOG_DBG ("No OSPF instance there : %d",instance);
        ovsdb_idl_txn_abort(txn);
        return;
    }
    area_row = ovsrec_ospf_area_get_area_by_id(ovs_ospf,area_id);
    if (!area_row)
    {
        VLOG_DBG ("No OSPF area there");
        ovsdb_idl_txn_abort(txn);
        return;
    }
    ospf_interface_list = xmalloc(sizeof * area_row->ospf_interfaces *
                              (area_row->n_ospf_interfaces - 1));
    for (i = 0, j = 0; i < area_row->n_ospf_interfaces; i++)
    {
        if (strcmp(area_row->ospf_interfaces[i]->name,  ifname) != 0)
        {
            ospf_interface_list[j] = area_row->ospf_interfaces[i];
            j++;
        }
        else
            ovs_oi = area_row->ospf_interfaces[i];
    }
    if (ovs_oi)
    {
       ovsrec_ospf_area_set_ospf_interfaces(area_row, ospf_interface_list,
                                               (area_row->n_ospf_interfaces - 1));
       ovs_port = ovs_oi->port;

       ovsrec_ospf_interface_delete(ovs_oi);

       /* OPS_TODO : Need to check for passive interfaces */
       snprintf (buf,sizeof (buf),"%d",area_row->n_ospf_interfaces);
       smap_clone (&area_smap,&(area_row->status));
       smap_replace (&area_smap,OSPF_KEY_AREA_ACTIVE_INTERFACE,buf);
       ovsrec_ospf_area_set_status(area_row,&area_smap);
    }
    else
    {
       VLOG_DBG ("No OSPF Interface there for the area");
       ovsdb_idl_txn_abort(txn);
       free(ospf_interface_list);
       return;
    }

    status = ovsdb_idl_txn_commit_block(txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("Transaction commit error");

    ovsdb_idl_txn_destroy(txn);

    free(ospf_interface_list);
}

static int
ovsdb_ospf_add_route_nexthops (const struct ovsdb_idl_txn *txn,
 const struct ovsrec_route *ovs_rib, struct ospf_route *or, char** next_hop_str)
{
    struct ovsrec_nexthop **nexthop_list = NULL;
    struct ovsrec_nexthop *pnexthop = NULL;
    struct ovsrec_port *ovs_port = NULL;
    struct ospf_path *path = NULL;
    struct listnode *node = NULL;
    char* saf_str = OSPF_NEXTHOP_SAF_UNICAST;
    char* ifname;
    char nexthop_buf[INET_ADDRSTRLEN];
    bool selected = true;
    int n_nexthops = 0, i = 0;
    int len_str = 0;
    char temp_str [NEXTHOP_STR_SIZE] = {0};
    char * pnexthopstr = NULL;

    n_nexthops = listcount(or->paths);
    if (!n_nexthops)
    {
        VLOG_DBG ("No nexthop present for the route");
        return -1;
    }
    nexthop_list = xmalloc(sizeof *ovs_rib->nexthops * n_nexthops);
    if (!nexthop_list)
    {
        VLOG_DBG ("Error in allocation memory");
        return -1;
    }
    pnexthopstr = calloc(n_nexthops,sizeof(temp_str));
    for (ALL_LIST_ELEMENTS_RO (or->paths, node, path))
    {
        snprintf(temp_str,NEXTHOP_STR_SIZE-1," ");
        len_str = strlen(temp_str);
        pnexthop = ovsrec_nexthop_insert(txn);
        if (path->nexthop.s_addr != INADDR_ANY)
        {
            inet_ntop(AF_INET,&path->nexthop,nexthop_buf,sizeof(nexthop_buf));
            snprintf(temp_str,NEXTHOP_STR_SIZE-1," %s ", nexthop_buf);
            len_str = strlen( temp_str);
            ovsrec_nexthop_set_ip_address(pnexthop, nexthop_buf);
        }
        if (path->ifindex != 0)
        {
            ifname = ifindex2ifname(path->ifindex);
            if (ifname)
            {
                snprintf(temp_str + len_str,NEXTHOP_STR_SIZE - (len_str+1),
                         "interface:%s",ifname);
                len_str = strlen(temp_str);
                ovs_port = find_port_by_name(ifname);
                if (ovs_port)
                {
                    ovsrec_nexthop_set_ports(pnexthop,&ovs_port,1);
                }
            }
        }
        strcat (temp_str, ",");
        if (pnexthopstr)
           strncat (pnexthopstr, temp_str, strlen(temp_str));

        ovsrec_nexthop_set_type(pnexthop, saf_str);
        ovsrec_nexthop_set_selected(pnexthop, &selected, 1);
        nexthop_list[i++] = (struct ovsrec_nexthop*) pnexthop;
    }
    if (pnexthopstr)
      *next_hop_str = pnexthopstr;
    else
      *next_hop_str = strdup("");
    ovsrec_route_set_nexthops(ovs_rib, nexthop_list, n_nexthops);
    free(nexthop_list);
    return 0;
}

void
ovsdb_ospf_add_rib_entry (struct prefix_ipv4 *p, struct ospf_route *or)
{
    struct ovsrec_route *ovs_rib = NULL;
    struct ovsrec_vrf *ovs_vrf = NULL;
    struct ovsdb_idl_txn *txn = NULL;
    struct uuid *rt_uuid = NULL;
    enum ovsdb_idl_txn_status status;
    int64_t distance = 0;
    int64_t metric = 0;
    char* saf_str = OVSREC_ROUTE_SUB_ADDRESS_FAMILY_UNICAST;
    char* addr_family = OVSREC_ROUTE_ADDRESS_FAMILY_IPV4;
    char* from = OVSREC_ROUTE_FROM_OSPF;
    char prefix_str[OSPF_MAX_PREFIX_LEN] = {0};
    char * next_hop_str =NULL;

    /* OPS_TODO : Will change when getting default VRF */
    ovs_vrf = ovsrec_vrf_first(idl);
    if (!ovs_vrf)
    {
        VLOG_DBG ("No VRF found");
        return;
    }
    txn = ovsdb_idl_txn_create(idl);
    if (!txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    ovs_rib = ovsrec_route_insert(txn);
    if (!ovs_rib)
    {
        VLOG_DBG ("Route insertion failed");
        ovsdb_idl_txn_abort(txn);
        return;
    }
    /* Not checking for Duplicate routes as done in route_install */
    ovsrec_route_set_vrf(ovs_rib,ovs_vrf);
    ovsrec_route_set_address_family(ovs_rib,addr_family);
    distance = ospf_distance_apply (p, or);
    if (!distance)
        distance = ZEBRA_OSPF_DISTANCE_DEFAULT;
    ovsrec_route_set_distance(ovs_rib,&distance,1);
    ovsrec_route_set_from(ovs_rib,from);
    if (or->path_type == OSPF_PATH_TYPE1_EXTERNAL)
        metric = or->cost + or->u.ext.type2_cost;
    else if (or->path_type == OSPF_PATH_TYPE2_EXTERNAL)
        metric = or->u.ext.type2_cost;
    else
        metric = or->cost;
    ovsrec_route_set_metric(ovs_rib,&metric,1);
    ovsrec_route_set_sub_address_family(ovs_rib,saf_str);
    prefix2str(p, prefix_str, sizeof(prefix_str));
    if (!strlen (prefix_str))
    {
        VLOG_DBG ("Invalid prefix for the route");
        ovsdb_idl_txn_abort(txn);
        return;
    }
    ovsrec_route_set_prefix(ovs_rib,prefix_str);
    /* Set Nexthops for the route */
    (void)ovsdb_ospf_add_route_nexthops(txn,ovs_rib,or,&next_hop_str);
    /* Event logging */
    log_event("OSPFv2_ROUTE",
       EV_KV("event","OSPFv2 ROUTE ADD"),
       EV_KV("destination","%s",prefix_str),
       EV_KV("nexthops","nexthop:%s distance:%d metric:%d",
              next_hop_str,distance,metric));
    if (next_hop_str)
      free(next_hop_str);
    status = ovsdb_idl_txn_commit_block(txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("Transaction commit error");
    else if (TXN_SUCCESS == status ) {
        ovs_rib = NULL;
        OVSREC_ROUTE_FOR_EACH(ovs_rib,idl)
        {
            if (!strcmp (prefix_str,ovs_rib->prefix) &&
                !strcmp (OVSREC_ROUTE_FROM_OSPF,ovs_rib->from)) {
                  rt_uuid = xzalloc(sizeof (struct uuid));
                  if (rt_uuid)
                    memcpy(rt_uuid,&ovs_rib->header_.uuid,sizeof (struct uuid));
                  else
                    VLOG_ERR ("Memory allocation error");
                  break;
                }
        }
        if (rt_uuid)
            shash_add(&all_routes,prefix_str,(void *)rt_uuid);
    }
    ovsdb_idl_txn_destroy(txn);
}

void
ovsdb_ospf_delete_rib_entry (struct prefix_ipv4 *p,
                                    struct ospf_route *or OVS_UNUSED)
{
    struct ovsrec_route *ovs_rib = NULL;
    struct uuid *rt_uuid = NULL;
    struct shash_node* node = NULL;
    struct ovsdb_idl_txn *txn = NULL;
    enum ovsdb_idl_txn_status status;
    char pr[OSPF_MAX_PREFIX_LEN] = {0};
    int i = 0;

    prefix2str(p,pr,sizeof (pr));
    node = shash_find(&all_routes,pr);
    if (!node)
    {
        VLOG_DBG ("No route node found in local hash");
        return;
    }
    rt_uuid = (struct uuid*)node->data;
    if (!rt_uuid)
    {
        VLOG_DBG ("No route data found in local hash");
        return;
    }
    /* Event logging */
    log_event("OSPFv2_ROUTE",
              EV_KV("event","OSPFv2 ROUTE DELETE"),
              EV_KV("destination","%s",pr),
              EV_KV("nexthops",""));
    txn = ovsdb_idl_txn_create(idl);
    if (!txn)
    {
        VLOG_DBG ("Transaction create failed");
        return;
    }
    ovs_rib = ovsrec_route_get_for_uuid(idl,rt_uuid);
    /* OPS_TODO : Not sure whether to remove shash data */
    if (!ovs_rib)
    {
        VLOG_DBG ("No route found for the uuid");
        ovsdb_idl_txn_abort(txn);
        return;
    }
    ovsrec_route_delete(ovs_rib);
    status = ovsdb_idl_txn_commit_block(txn);
    if (TXN_SUCCESS != status &&
        TXN_UNCHANGED != status)
        VLOG_DBG ("Transaction commit error");
    else if (TXN_SUCCESS == status) {
        free(node->data);
        shash_delete(&all_routes,node);
    }
    ovsdb_idl_txn_destroy(txn);
}

int
modify_ospf_network_config (struct ovsdb_idl *idl, struct ospf *ospf_cfg,
    const struct ovsrec_ospf_router *ospf_mod_row)
{
    struct prefix_ipv4 p;
    struct in_addr area_id;
    bool is_network_found = false;
    int i = 0, ret;
    struct listnode* intf_node = NULL, *intf_nnode = NULL;
    struct route_node *rn = NULL;
    struct ospf_network* ospf_netwrk = NULL;
    char prefix_str[32] = {0};

    memset (&p,0,sizeof(p));
    for (i = 0 ; i < ospf_mod_row->n_networks; i++)
    {
        (void)str2prefix_ipv4(ospf_mod_row->key_networks[i],&p);
        area_id.s_addr =  (in_addr_t)(ospf_mod_row->value_networks[i]);

        ret = ospf_network_set (ospf_cfg, &p, area_id);
        if (ret == 0)
        {
          VLOG_DBG ("Network statement prefix:%s area:%d exist",ospf_mod_row->key_networks[i],area_id.s_addr);
          continue;
        }
    }
    /* Check if any network is deleted via. no network command */
    for (rn = route_top (ospf_cfg->networks); rn; rn = route_next (rn))
    {
        /* Continue if no network information is present */
        if(NULL == rn->info)
            continue;
        is_network_found = false;
        for (i = 0 ; i < ospf_mod_row->n_networks ; i++)
        {
            memset(prefix_str,0,sizeof(prefix_str));
            (void)prefix2str(&rn->p,prefix_str,sizeof(prefix_str));
            if (0 == strcmp (prefix_str,ospf_mod_row->key_networks[i]))
            {
                 is_network_found = true;
                 break;
            }
        }
        if (!is_network_found)
        {
            ospf_netwrk = (struct ospf_network*)rn->info;
            ospf_network_unset(ospf_cfg,&rn->p,ospf_netwrk->area_id);
            // TODO:Delete area only if it has no default values

        }
    }
    return 0;
}

void
insert_ospf_router_instance(struct ovsdb_idl *idl, struct ovsrec_ospf_router* ovs_ospf, int64_t instance_number)
{
    struct ospf* ospf = NULL;
    int i = 0;

    /* Check if by any chance the ospf instance is already present */
    ospf = ospf_lookup_by_instance(instance_number);
    if (ospf == NULL)
    {
        ospf = ospf_new ();
        ospf->ospf_inst = instance_number;
        ospf_add (ospf);

  #ifdef HAVE_OPAQUE_LSA
        ospf_opaque_type11_lsa_init (ospf);
  #endif /* HAVE_OPAQUE_LSA */
    }
    else
        VLOG_DBG("%s : That's wierd OSPF instance already present",__FUNCTION__);

    if(!ospf){
        VLOG_DBG("OSPF instance Insertion failed");
        return;
    }
}

void
modify_ospf_router_instance(struct ovsdb_idl *idl,
    const struct ovsrec_ospf_router* ovs_ospf, int64_t instance_number)
{
    const struct ovsrec_route *route_mod_row = NULL;
    const struct ovsdb_idl_column *column = NULL;
    const struct ovsrec_port* nh_port = NULL;
    struct prefix rt_prefix;
    struct ospf *ospf_instance;
    struct in_addr fwd;
    unsigned int nh_ifindex =0;
    struct prefix nh;
    struct prefix_ipv4 rt_prefix_ipv4;
    struct listnode *node;
    struct ospf_interface *oi;
    struct external_info *ei;
    struct in_addr nh_addr;
    bool nh_ipv4_found = false;
    int ret_status = -1;
    int i = 0,nh_index = 0;

    ospf_instance = ospf_lookup_by_instance(instance_number);
    if (!ospf_instance)
    {
         VLOG_DBG ("No OSPF config found!Critical error");
         return;
    }

    /* Check if router_id is modified */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_router_col_router_id, idl_seqno) ||
            OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_vrf_col_active_router_id, idl_seqno)) {
        ret_status = modify_ospf_router_id_config(ospf_instance, ovs_ospf);
        if (!ret_status) {
            VLOG_DBG("OSPF router_id set to %s", inet_ntoa(ospf_instance->router_id));
        }
        else
             VLOG_DBG("OSPF router_id set Failed");
    }

    /* Check if router_config is modified */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_router_col_other_config, idl_seqno)) {
        ret_status = modify_ospf_router_config(ospf_instance, ovs_ospf);
        if (!ret_status) {
            VLOG_DBG("OSPF router config set");
        }
    }

    /* Check if router_config is modified */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_router_col_lsa_timers, idl_seqno)) {
        ret_status = modify_ospf_lsa_timers_router_config(ospf_instance, ovs_ospf);
        if (ret_status){
            VLOG_DBG("OSPF router lsa timers not set");
        }
    }

    /* Check if stub_router_config is modified */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_router_col_stub_router_adv, idl_seqno)) {
        ret_status = modify_ospf_stub_router_config(idl,ospf_instance, ovs_ospf);
        if (!ret_status) {
            VLOG_DBG("OSPF router stub router config set");
        }
    }

    /* Check if network is modified */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_router_col_networks, idl_seqno)) {
        ret_status = modify_ospf_network_config(idl,ospf_instance, ovs_ospf);
        if (!ret_status) {
            VLOG_DBG("OSPF router network set");
        }
    }
    else
        VLOG_DBG("OSPF router network not set");

    /* Check if distance is modified */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_router_col_distance, idl_seqno)) {
        /* OPS_TODO : Handle if and when distance values are not created
           while creating OSPF OVSDB instance */
        ospf_instance->distance_all =
            (unsigned char)ovs_ospf->value_distance[OSPF_ROUTER_DISTANCE_ALL];
        ospf_instance->distance_intra =
            (unsigned char)ovs_ospf->value_distance[OSPF_ROUTER_DISTANCE_INTRA_AREA];
        ospf_instance->distance_inter =
            (unsigned char)ovs_ospf->value_distance[OSPF_ROUTER_DISTANCE_INTER_AREA];
        ospf_instance->distance_external =
            (unsigned char)ovs_ospf->value_distance[OSPF_ROUTER_DISTANCE_EXTERNAL];
        VLOG_DBG("OSPF Admin distance set");
    }
    else
        VLOG_DBG("OSPF Admin distance not set");

    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_router_col_redistribute, idl_seqno)) {
        do {
            int is_connected = 0, is_static = 0, is_bgp = 0;
            /* For checking if redistribution is ceased */
            int is_redist_connect = 0, is_redist_static = 0, is_redist_bgp =0;
            for (i = 0 ; i < ovs_ospf->n_redistribute ; i++) {
                if(!redist[ZEBRA_ROUTE_CONNECT] &&
                    !strcmp(ovs_ospf->redistribute[i],OVSREC_OSPF_ROUTER_REDISTRIBUTE_CONNECTED)) {
                    ospf_instance->redistribute++;
                    is_connected = 1;
                    is_redist_connect = 1;
                    ospf_instance->dmetric[ZEBRA_ROUTE_CONNECT].type = -1;
                    ospf_instance->dmetric[ZEBRA_ROUTE_CONNECT].value = -1;
                    redist[ZEBRA_ROUTE_CONNECT] = 1;
                    ospf_asbr_status_update (ospf_instance, ospf_instance->redistribute);
                    continue;
                 }
                else if (!strcmp(ovs_ospf->redistribute[i],OVSREC_OSPF_ROUTER_REDISTRIBUTE_CONNECTED))
                    is_redist_connect = 1;

                if(!redist[ZEBRA_ROUTE_STATIC] &&
                    !strcmp(ovs_ospf->redistribute[i],OVSREC_OSPF_ROUTER_REDISTRIBUTE_STATIC)) {
                    ospf_instance->redistribute++;
                    is_static = 1;
                    is_redist_static = 1;
                    ospf_instance->dmetric[ZEBRA_ROUTE_STATIC].type = -1;
                    ospf_instance->dmetric[ZEBRA_ROUTE_STATIC].value = -1;
                    redist[ZEBRA_ROUTE_STATIC] = 1;
                    ospf_asbr_status_update (ospf_instance, ospf_instance->redistribute);
                    continue;
                }
                else if (!strcmp(ovs_ospf->redistribute[i],OVSREC_OSPF_ROUTER_REDISTRIBUTE_STATIC))
                    is_redist_static = 1;

                if(!redist[ZEBRA_ROUTE_BGP] &&
                    !strcmp(ovs_ospf->redistribute[i],OVSREC_OSPF_ROUTER_REDISTRIBUTE_BGP)) {
                    ospf_instance->redistribute++;
                    is_bgp = 1;
                    is_redist_bgp = 1;
                    ospf_instance->dmetric[ZEBRA_ROUTE_BGP].type = -1;
                    ospf_instance->dmetric[ZEBRA_ROUTE_BGP].value = -1;
                    redist[ZEBRA_ROUTE_BGP] = 1;
                    ospf_asbr_status_update (ospf_instance, ospf_instance->redistribute);
                    continue;
                }
                else if (!strcmp(ovs_ospf->redistribute[i],OVSREC_OSPF_ROUTER_REDISTRIBUTE_BGP))
                    is_redist_bgp = 1;
            }

            if (!is_redist_connect && redist[ZEBRA_ROUTE_CONNECT])
            {
                ospf_redistribute_withdraw (ospf_instance, ZEBRA_ROUTE_CONNECT);
                ospf_asbr_status_update (ospf_instance, --ospf_instance->redistribute);
                redist[ZEBRA_ROUTE_CONNECT] = 0;
            }
            if (!is_redist_static && redist[ZEBRA_ROUTE_STATIC])
            {
                ospf_redistribute_withdraw (ospf_instance, ZEBRA_ROUTE_STATIC);
                ospf_asbr_status_update (ospf_instance, --ospf_instance->redistribute);
                redist[ZEBRA_ROUTE_STATIC] = 0;
            }
            if (!is_redist_bgp && redist[ZEBRA_ROUTE_BGP])
            {
                ospf_redistribute_withdraw (ospf_instance, ZEBRA_ROUTE_BGP);
                ospf_asbr_status_update (ospf_instance, --ospf_instance->redistribute);
                redist[ZEBRA_ROUTE_BGP] = 0;
            }

            if (0 == ospf_instance->redistribute ||
                (!is_connected && !is_static && !is_bgp))
                break;

            OVSREC_ROUTE_FOR_EACH(route_mod_row,idl) {
                struct prefix_ipv4 p_temp;
                nh_ipv4_found = false;
                rt_prefix_ipv4.family = AF_INET;
                if (route_mod_row->address_family &&
                    !strcmp(route_mod_row->address_family,OVSREC_ROUTE_ADDRESS_FAMILY_IPV6))
                     continue;
                str2prefix_ipv4(route_mod_row->prefix,&p_temp);
                if (is_prefix_default(&p_temp))
                    continue;

                if (is_connected && (route_mod_row->from &&
                     !strcmp(route_mod_row->from,OVSREC_ROUTE_FROM_CONNECTED))) {
                       str2prefix(route_mod_row->prefix,&rt_prefix);
                       nh_port = NULL;
                       for (nh_index = 0 ; nh_index < route_mod_row->n_nexthops;nh_index++)
                       {
                           if (!nh_port && route_mod_row->nexthops[nh_index]->n_ports)
                            nh_port = route_mod_row->nexthops[nh_index]->ports[0];
                           /* Zebra takes time to update the selected flag. Not sure
                            whether to check or not
                            if (route_mod_row->nexthops[nh_index]->ip_address &&
                                route_mod_row->nexthops[nh_index]->selected[0]) { */
                           if (route_mod_row->nexthops[nh_index]->ip_address) {
                               inet_aton(route_mod_row->nexthops[nh_index]->ip_address,&nh_addr);
                               nh.family = AF_INET;
                               nh.u.prefix4 = nh_addr;
                               nh.prefixlen = IPV4_MAX_BITLEN;
                               for (ALL_LIST_ELEMENTS_RO (ospf_instance->oiflist, node, oi))
                               {
                                  if (if_is_operative (oi->ifp))
                                    if (oi->address->family == AF_INET)
                                      if (prefix_match (oi->address, &nh)) {
                                         fwd = nh_addr;
                                         nh_ifindex = oi->ifp->ifindex;
                                         nh_ipv4_found = true;
                                         break;
                                       }
                               }
                               if (nh_ipv4_found)
                                break;
                           }
                       }
                       if (!nh_ipv4_found)
                       {
                           fwd.s_addr = 0;
                           if (nh_port)
                            nh_ifindex = ifname2ifindex(nh_port->name);
                           else
                            nh_ifindex = 0;
                        }
                       rt_prefix_ipv4.prefix = rt_prefix.u.prefix4;
                       rt_prefix_ipv4.prefixlen = rt_prefix.prefixlen;
                        ei = ospf_external_info_add (ZEBRA_ROUTE_CONNECT,rt_prefix_ipv4,
                                                    nh_ifindex, fwd);
                        if (ospf_instance->router_id.s_addr == 0)
                         /* Set flags to generate AS-external-LSA originate event
                           for each redistributed protocols later. */
                            ospf_instance->external_origin |= (1 << ZEBRA_ROUTE_CONNECT);
                        else {
                             if (ei) {
                                struct ospf_lsa *current;
                                current = ospf_external_info_find_lsa (ospf_instance, &ei->p);
                                if (!current)
                                  ospf_external_lsa_originate (ospf_instance, ei);
                                else if (IS_LSA_MAXAGE (current))
                                  ospf_external_lsa_refresh (ospf_instance, current,
                                                             ei, LSA_REFRESH_FORCE);
                                else
                                  VLOG_WARN("%s already exists",
                                             inet_ntoa (rt_prefix.u.prefix4));
                             }
                        }
                 }
                 else if (is_static && (route_mod_row->from &&
                      !strcmp(route_mod_row->from,OVSREC_ROUTE_FROM_STATIC))) {
                        str2prefix(route_mod_row->prefix,&rt_prefix);
                        nh_port = NULL;
                        for (nh_index = 0 ; nh_index < route_mod_row->n_nexthops;nh_index++)
                        {
                            if (!nh_port && route_mod_row->nexthops[nh_index]->n_ports)
                             nh_port = route_mod_row->nexthops[nh_index]->ports[0];
                            /* Zebra takes time to update the selected flag. Not sure
                            whether to check or not
                            if (route_mod_row->nexthops[nh_index]->ip_address &&
                                route_mod_row->nexthops[nh_index]->selected[0]) { */
                            if (route_mod_row->nexthops[nh_index]->ip_address){
                                inet_aton(route_mod_row->nexthops[nh_index]->ip_address,&nh_addr);
                                nh.family = AF_INET;
                                nh.u.prefix4 = nh_addr;
                                nh.prefixlen = IPV4_MAX_BITLEN;
                                for (ALL_LIST_ELEMENTS_RO (ospf_instance->oiflist, node, oi))
                                {
                                     if (if_is_operative (oi->ifp))
                                       if (oi->address->family == AF_INET)
                                         if (prefix_match (oi->address, &nh)) {
                                           fwd = nh_addr;
                                           nh_ifindex = oi->ifp->ifindex;
                                           nh_ipv4_found = true;
                                           break;
                                         }
                                }
                                if (nh_ipv4_found)
                                    break;
                            }
                        }
                        if (!nh_ipv4_found)
                        {
                            fwd.s_addr = 0;
                            if (nh_port)
                             nh_ifindex = ifname2ifindex(nh_port->name);
                            else
                             nh_ifindex = 0;
                        }
                        rt_prefix_ipv4.prefix = rt_prefix.u.prefix4;
                        rt_prefix_ipv4.prefixlen = rt_prefix.prefixlen;
                        ei = ospf_external_info_add (ZEBRA_ROUTE_STATIC,rt_prefix_ipv4,
                                                     nh_ifindex, fwd);
                        if (ospf_instance->router_id.s_addr == 0)
                         /* Set flags to generate AS-external-LSA originate event
                            for each redistributed protocols later. */
                            ospf_instance->external_origin |= (1 << ZEBRA_ROUTE_STATIC);
                        else {
                           if (ei) {
                              struct ospf_lsa *current;
                              current = ospf_external_info_find_lsa (ospf_instance, &ei->p);
                              if (!current)
                                ospf_external_lsa_originate (ospf_instance, ei);
                              else if (IS_LSA_MAXAGE (current))
                                ospf_external_lsa_refresh (ospf_instance, current,
                                                           ei, LSA_REFRESH_FORCE);
                              else
                                VLOG_WARN("%s already exists",
                                           inet_ntoa (rt_prefix.u.prefix4));
                           }
                        }
                 }
                 else if (is_bgp && (route_mod_row->from &&
                      !strcmp(route_mod_row->from,OVSREC_ROUTE_FROM_BGP))) {
                        str2prefix(route_mod_row->prefix,&rt_prefix);
                        nh_port = NULL;
                        for (nh_index = 0 ; nh_index < route_mod_row->n_nexthops;nh_index++)
                        {
                            if (!nh_port && route_mod_row->nexthops[nh_index]->n_ports)
                             nh_port = route_mod_row->nexthops[nh_index]->ports[0];
                            /* Zebra takes time to update the selected flag. Not sure
                            whether to check or not
                            if (route_mod_row->nexthops[nh_index]->ip_address &&
                                route_mod_row->nexthops[nh_index]->selected[0]) { */
                            if (route_mod_row->nexthops[nh_index]->ip_address) {
                                inet_aton(route_mod_row->nexthops[nh_index]->ip_address,&nh_addr);
                                nh.family = AF_INET;
                                nh.u.prefix4 = nh_addr;
                                nh.prefixlen = IPV4_MAX_BITLEN;
                                for (ALL_LIST_ELEMENTS_RO (ospf_instance->oiflist, node, oi))
                                {
                                     if (if_is_operative (oi->ifp))
                                       if (oi->address->family == AF_INET)
                                         if (prefix_match (oi->address, &nh)) {
                                           fwd = nh_addr;
                                           nh_ifindex = oi->ifp->ifindex;
                                           nh_ipv4_found = true;
                                           break;
                                         }
                                }
                                if (nh_ipv4_found)
                                    break;
                            }
                        }
                        if (!nh_ipv4_found)
                        {
                            fwd.s_addr = 0;
                            if (nh_port)
                             nh_ifindex = ifname2ifindex(nh_port->name);
                            else
                             nh_ifindex = 0;
                        }
                        rt_prefix_ipv4.prefix = rt_prefix.u.prefix4;
                        rt_prefix_ipv4.prefixlen = rt_prefix.prefixlen;
                        ei = ospf_external_info_add (ZEBRA_ROUTE_BGP,rt_prefix_ipv4,
                                                     nh_ifindex, fwd);
                        if (ospf_instance->router_id.s_addr == 0)
                         /* Set flags to generate AS-external-LSA originate event
                            for each redistributed protocols later. */
                            ospf_instance->external_origin |= (1 << ZEBRA_ROUTE_BGP);
                        else {
                           if (ei) {
                              struct ospf_lsa *current;
                              current = ospf_external_info_find_lsa (ospf_instance, &ei->p);
                              if (!current)
                                ospf_external_lsa_originate (ospf_instance, ei);
                              else if (IS_LSA_MAXAGE (current))
                                ospf_external_lsa_refresh (ospf_instance, current,
                                                           ei, LSA_REFRESH_FORCE);
                              else
                                VLOG_WARN("%s already exists",
                                           inet_ntoa (rt_prefix.u.prefix4));
                           }
                        }
                 }
             }
       }while(0);
  }
  else
     VLOG_DBG("OSPF Redistribute not set");

  if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_router_col_default_information, idl_seqno)) {
        bool redist_def = false,redist_def_always = false;
        redist_def = smap_get_bool(&(ovs_ospf->default_information),
            OSPF_DEFAULT_INFO_ORIGINATE,BOOLEAN_STRING_FALSE);
        redist_def_always = smap_get_bool(&(ovs_ospf->default_information),
            OSPF_DEFAULT_INFO_ORIGINATE_ALWAYS,BOOLEAN_STRING_FALSE);
        if (!redist_default && redist_def) {
            ospf_instance->dmetric[DEFAULT_ROUTE].type = -1;
            ospf_instance->dmetric[DEFAULT_ROUTE].value = -1;
            if (redist_def_always)
                ospf_instance->default_originate = DEFAULT_ORIGINATE_ALWAYS;
            else
                ospf_instance->default_originate = DEFAULT_ORIGINATE_ZEBRA;

            ospf_asbr_status_update (ospf_instance, ++ospf_instance->redistribute);
            redist_default = 1;
            if (ospf_instance->router_id.s_addr == 0)
                ospf_instance->external_origin |= (1 << DEFAULT_ROUTE);
            else {
                if (ospf_instance->default_originate != DEFAULT_ORIGINATE_ALWAYS)
                {
                    OVSREC_ROUTE_FOR_EACH(route_mod_row,idl) {
                        struct prefix p;
                        struct prefix_ipv4 p_ipv4;
                        if (route_mod_row->address_family &&
                            !strcmp(route_mod_row->address_family,OVSREC_ROUTE_ADDRESS_FAMILY_IPV6))
                            continue;

                        str2prefix(route_mod_row->prefix,&p);
                        str2prefix_ipv4(route_mod_row->prefix,&p_ipv4);
                        if(is_prefix_default(&p_ipv4)) {
                            /* Only is route is selected */
                            if (route_mod_row->n_selected && route_mod_row->selected[0]) {
                                ospf_external_info_add(DEFAULT_ROUTE,p_ipv4,0,p_ipv4.prefix);
                                ospf_external_lsa_refresh_default (ospf_instance);
                            }
                        }
                    }
                }
                else
                    thread_add_timer (master, ospf_default_originate_timer, ospf_instance, 1);
            }
        }
        else if (redist_default && redist_def_always &&
            (ospf_instance->default_originate != DEFAULT_ORIGINATE_ALWAYS))
        {
            ospf_instance->default_originate = DEFAULT_ORIGINATE_ALWAYS;
            if (EXTERNAL_INFO (DEFAULT_ROUTE) == NULL)
                thread_add_timer (master, ospf_default_originate_timer, ospf_instance, 1);
            else
                ospf_external_lsa_refresh_default (ospf_instance);
        }
        //OPS_TODO : Handle case when always flag is cleared but meanwhile a default route has come to route table
        else if (redist_default && !redist_def)
        {
            struct prefix_ipv4 p;

            p.family = AF_INET;
            p.prefix.s_addr = 0;
            p.prefixlen = 0;
            ospf_external_lsa_flush (ospf_instance, DEFAULT_ROUTE, &p, 0);
            if (EXTERNAL_INFO (DEFAULT_ROUTE)) {
                ospf_external_info_delete (DEFAULT_ROUTE, p);
                route_table_finish (EXTERNAL_INFO (DEFAULT_ROUTE));
                EXTERNAL_INFO (DEFAULT_ROUTE) = NULL;
            }
            ospf_instance->default_originate = DEFAULT_ORIGINATE_NONE;
            ospf_asbr_status_update (ospf_instance, --ospf_instance->redistribute);
            redist_default = 0;
        }
  }
}

static void
insert_ospf_area_instance(struct ovsdb_idl *idl OVS_UNUSED,
                                    int64_t area_id, int64_t ospf_inst)
{
    struct ospf* ospf = NULL;
    struct ospf_area *area = NULL;
    struct in_addr areaid;

    areaid.s_addr = area_id;
    ospf = ospf_lookup_by_instance(ospf_inst);
    if (!ospf)
    {
         VLOG_DBG ("No OSPF config found!Critical error");
         return;
    }
    area = ospf_area_lookup_by_area_id(ospf,areaid);
    if (!area)
    {
         area = ospf_area_new (ospf, areaid);
         listnode_add_sort (ospf->areas, area);
         ospf_check_abr_status (ospf);
         if (ospf->stub_router_admin_set == OSPF_STUB_ROUTER_ADMINISTRATIVE_SET)
        {
          SET_FLAG (area->stub_router_state, OSPF_AREA_ADMIN_STUB_ROUTED);
        }
    }
    else
        VLOG_DBG ("OSPF Area already present");

    return;
}

static int
insert_ospf_vlink(struct ovsdb_idl *idl,const struct ospf* ospf,
          const struct ovsrec_ospf_vlink* ovs_vlink)
{
    struct ospf_vl_config_data vl_config;

    ospf_vl_config_data_init(&vl_config,ovs_vlink->name);
    vl_config.area_id.s_addr= ovs_vlink->area_id;
    vl_config.vl_peer.s_addr= ovs_vlink->peer_router_id;
    ospf_vl_set(ospf,&vl_config);

    return 0;
}

int
modify_ospf_area_col_other_config(const struct ovsrec_ospf_area* ovs_area,
                                                   struct ospf_area* area)
{
    struct prefix_ipv4 p;
    int cost;

    cost = smap_get_int(&ovs_area->other_config,
                            OSPF_KEY_AREA_STUB_DEFAULT_COST,
                            OSPF_AREA_STUB_DEFAULT_COST_DEFAULT);

    if (area->external_routing == OSPF_AREA_DEFAULT)
    {
        VLOG_DBG ("The area is neither stub, nor NSSA");
        return -1;
    }

    area->default_cost = cost;

    p.family = AF_INET;
    p.prefix.s_addr = OSPF_DEFAULT_DESTINATION;
    p.prefixlen = 0;

    if (IS_DEBUG_OSPF_EVENT)
        zlog_debug ("ospf_abr_announce_stub_defaults(): "
                    "announcing 0.0.0.0/0 to area %s",
                     inet_ntoa (area->area_id));

    ospf_abr_announce_network_to_area (&p, area->default_cost, area);

    return 0;
}

static void
modify_ospf_area_instance(struct ovsdb_idl *idl,
    const struct ovsrec_ospf_area* ovs_area, int64_t area_id, int64_t ospf_inst)
{
    struct ospf_area* area = NULL;
    struct ospf* ospf = NULL;
    struct in_addr areaid;
    int ret = 0;
    bool sched_ab_task = false;

    areaid.s_addr = area_id;
    ospf = ospf_lookup_by_instance(ospf_inst);
    if (!ospf)
    {
         VLOG_DBG ("No OSPF config found!Critical error");
         return;
    }
    area = ospf_area_lookup_by_area_id(ospf,areaid);
    if (!area)
    {
         VLOG_DBG ("No OSPF area config found!Critical error");
         return;
    }
    /* Check if auth type is modified */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_area_col_ospf_auth_type, idl_seqno)) {
        if (ovs_area->ospf_auth_type) {
          if(!strcmp(ovs_area->ospf_auth_type,OVSREC_OSPF_AREA_OSPF_AUTH_TYPE_TEXT))
              area->auth_type = OSPF_AUTH_SIMPLE;
          else if(!strcmp(ovs_area->ospf_auth_type,OVSREC_OSPF_AREA_OSPF_AUTH_TYPE_MD5))
              area->auth_type = OSPF_AUTH_CRYPTOGRAPHIC;
        }
        else {
          area->auth_type = OSPF_AUTH_NULL;
        }
    }
     /* Check if area type is modified */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_area_col_area_type, idl_seqno)) {
        if (!ovs_area->area_type ||
            !strcmp(ovs_area->area_type,OVSREC_OSPF_AREA_AREA_TYPE_DEFAULT)) {
            /* Not checking if backbone area for making area type default */
            if (OSPF_AREA_STUB == area->external_routing) {
                ospf_area_type_set (area, OSPF_AREA_DEFAULT);
                area->no_summary = 0;
            }
            else if(OSPF_AREA_NSSA == area->external_routing) {
                ospf->anyNSSA--;
                ospf_area_type_set (area, OSPF_AREA_DEFAULT);
                area->no_summary = 0;
            }
        }
        else if(!strcmp(ovs_area->area_type,OVSREC_OSPF_AREA_AREA_TYPE_STUB)) {
            if (!OSPF_IS_AREA_ID_BACKBONE(areaid)) {
                ret = ospf_area_vlink_count (ospf, area);
                if (ret != 0)
                    VLOG_INFO ("Error setting area as stub. Area has virtual links through it");
                else {
                    if (area->external_routing != OSPF_AREA_STUB)
                        ospf_area_type_set (area, OSPF_AREA_STUB);
                    area->no_summary = 0;
                }
            }
            else
                VLOG_INFO ("Cannot configure Backbone area as stub");
        }
        else if(!strcmp(ovs_area->area_type,OVSREC_OSPF_AREA_AREA_TYPE_STUB_NO_SUMMARY)) {
            if (!OSPF_IS_AREA_ID_BACKBONE(areaid)) {
                ret = ospf_area_vlink_count (ospf, area);
                if (ret != 0)
                    VLOG_INFO ("Error setting area %d as stub. Area has virtual links through it");
                else {
                    /* OPS_TODO:This step is alligned with Quagga, but may need to change, in case
                       when no_summary is set. To remove summary LSA (if self originated)
                       may need to run abr task again*/
                    if (area->external_routing != OSPF_AREA_STUB)
                        ospf_area_type_set (area, OSPF_AREA_STUB);
                     area->no_summary = 1;
                }
            }
            else
                VLOG_INFO ("Cannot configure Backbone area as stub");
        }
        else if(!strcmp(ovs_area->area_type,OVSREC_OSPF_AREA_AREA_TYPE_NSSA) ||
                !strcmp(ovs_area->area_type,OVSREC_OSPF_AREA_AREA_TYPE_NSSA_NO_SUMMARY)) {
            sched_ab_task = false;
            if (!OSPF_IS_AREA_ID_BACKBONE(areaid)) {
                ret = ospf_area_vlink_count (ospf, area);
                if (ret != 0)
                    VLOG_INFO ("Error setting area %d as NSSA. Area has virtual links through it");
                else {
                    /* OPS_TODO : Is it needed to run abr task again,
                    if only area type is changed as its handled in ospf_area_type_set() */
                    if (area->external_routing != OSPF_AREA_NSSA) {
                        ospf_area_type_set (area, OSPF_AREA_NSSA);
                        ospf->anyNSSA++;
                        sched_ab_task = true;
                    }
                    /* Set translator role also */
                    if (ovs_area->nssa_translator_role &&
                        strcmp(ovs_area->nssa_translator_role,
                        nssa_translate_role_str[area->NSSATranslatorRole])) {
                          if(!strcmp(ovs_area->nssa_translator_role,OVSREC_OSPF_AREA_NSSA_TRANSLATOR_ROLE_CANDIDATE))
                            area->NSSATranslatorRole = OSPF_NSSA_ROLE_CANDIDATE;
                          if(!strcmp(ovs_area->nssa_translator_role,OVSREC_OSPF_AREA_NSSA_TRANSLATOR_ROLE_ALWAYS))
                            area->NSSATranslatorRole = OSPF_NSSA_ROLE_ALWAYS;
                          if(!strcmp(ovs_area->nssa_translator_role,OVSREC_OSPF_AREA_NSSA_TRANSLATOR_ROLE_NEVER))
                          area->NSSATranslatorRole = OSPF_NSSA_ROLE_NEVER;
                          sched_ab_task = true;
                    }
                    /* If OVSDB has no data but ospf instance has something other than candidate */
                    else if (!ovs_area->nssa_translator_role &&
                        strcmp(nssa_translate_role_str[area->NSSATranslatorRole],
                        OVSREC_OSPF_AREA_NSSA_TRANSLATOR_ROLE_CANDIDATE)) {
                          area->NSSATranslatorRole = OSPF_NSSA_ROLE_CANDIDATE;
                          sched_ab_task = true;
                    }
                    if (!strcmp(ovs_area->area_type,OVSREC_OSPF_AREA_AREA_TYPE_NSSA))
                        area->no_summary = 0;
                    else {
                        area->no_summary = 1;
                        sched_ab_task = true;
                    }
                    if (sched_ab_task) {
                        area->NSSATranslatorState = OSPF_NSSA_TRANSLATE_DISABLED;
                        area->NSSATranslatorStabilityInterval = OSPF_NSSA_TRANS_STABLE_DEFAULT;
                        ospf_schedule_abr_task (ospf);
                    }
                }
            }
            else
                VLOG_INFO ("Cannot configure Backbone area as NSSA");
        }
    }

    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_area_col_other_config, idl_seqno)) {
        ret = modify_ospf_area_col_other_config(ovs_area, area);
        if (ret){
            VLOG_DBG("OSPF Area default cost not set");
        }
    }

    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_area_col_nssa_translator_role, idl_seqno)) {
        if (area->external_routing == OSPF_AREA_NSSA) {
            if (ovs_area->nssa_translator_role &&
                strcmp (nssa_translate_role_str[area->NSSATranslatorRole],ovs_area->nssa_translator_role)) {
                  area->NSSATranslatorState = OSPF_NSSA_TRANSLATE_DISABLED;
                  area->NSSATranslatorStabilityInterval = OSPF_NSSA_TRANS_STABLE_DEFAULT;
                  if (!strcmp(ovs_area->nssa_translator_role,OVSREC_OSPF_AREA_NSSA_TRANSLATOR_ROLE_ALWAYS))
                    area->NSSATranslatorRole = OSPF_NSSA_ROLE_ALWAYS;
                  else if (!strcmp(ovs_area->nssa_translator_role,OVSREC_OSPF_AREA_NSSA_TRANSLATOR_ROLE_NEVER))
                    area->NSSATranslatorRole = OSPF_NSSA_ROLE_NEVER;
                  else
                    area->NSSATranslatorRole = OSPF_NSSA_ROLE_CANDIDATE;
                  ospf_schedule_abr_task (ospf);
            }
            else if (!ovs_area->nssa_translator_role &&
                strcmp (nssa_translate_role_str[area->NSSATranslatorRole],OVSREC_OSPF_AREA_NSSA_TRANSLATOR_ROLE_CANDIDATE)) {
                  area->NSSATranslatorState = OSPF_NSSA_TRANSLATE_DISABLED;
                  area->NSSATranslatorStabilityInterval = OSPF_NSSA_TRANS_STABLE_DEFAULT;
                  area->NSSATranslatorRole = OSPF_NSSA_ROLE_CANDIDATE;
                  ospf_schedule_abr_task (ospf);
            }
        }
        else
            VLOG_INFO ("Area is not configured as NSSA");
    }
    ospf_area_check_free(ospf,areaid);
}

static void
ospf_nbr_timer_update (struct ospf_interface *oi)
{
  struct route_node *rn;
  struct ospf_neighbor *nbr;

  for (rn = route_top (oi->nbrs); rn; rn = route_next (rn))
    if ((nbr = rn->info))
    {
       nbr->v_inactivity = OSPF_IF_PARAM (oi, v_wait);
       nbr->v_db_desc = OSPF_IF_PARAM (oi, retransmit_interval);
       nbr->v_ls_req = OSPF_IF_PARAM (oi, retransmit_interval);
       nbr->v_ls_upd = OSPF_IF_PARAM (oi, retransmit_interval);
    }
}


void
modify_ospf_interface (struct ovsdb_idl *idl,
    const struct ovsrec_port* ovs_port, const char* if_name)
{
    const struct ovsdb_idl_column *column = NULL;
    struct interface* ifp = NULL;
    struct ospf_if_params *params = NULL;
    struct ospf_interface *oi;
    struct route_node *rn = NULL;
    struct crypt_key *ck = NULL;
    struct crypt_key *lookup_ck = NULL;
    struct listnode *node;
    unsigned char key_id;
    u_int32_t seconds = 0;
    u_int32_t val = 0;
    int ret_status = -1;
    int i =0;
    bool is_key_found = false;

    if (!ovs_port || !if_name)
    {
         VLOG_DBG ("No OSPF Port found!");
         return;
    }
    ifp = if_lookup_by_name(if_name);
    if (!ifp)
    {
         VLOG_DBG ("No OSPF Interface found!");
         return;
    }
    params = IF_DEF_PARAMS (ifp);
    /* Check if ospf intervals are modified */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_port_col_ospf_intervals, idl_seqno)) {
        /*!!!!Change the sorted enum list if new key value pair is added */
        if (ovs_port->n_ospf_intervals != OVS_OSPF_INTERVAL_SORTED_MAX)
            VLOG_DBG("Requisite number of intervals are not set");
        else {
            seconds = ovs_port->value_ospf_intervals [OVS_OSPF_HELLO_INTERVAL_SORTED];
            if (seconds < OSPF_MIN_INTERVAL || seconds > OSPF_MAX_INTERVAL)
                VLOG_DBG("Hello Interval is invalid");
            else {
                SET_IF_PARAM (params, v_hello);
                params->v_hello = seconds;
            }

            seconds = ovs_port->value_ospf_intervals [OVS_OSPF_DEAD_INTERVAL_SORTED];
            if (seconds < OSPF_MIN_INTERVAL || seconds > OSPF_MAX_INTERVAL)
                VLOG_DBG("Dead Interval is invalid");
            else {
                SET_IF_PARAM (params, v_wait);
                params->v_wait = seconds;
                for (rn = route_top (IF_OIFS (ifp)); rn; rn = route_next (rn))
                    if ((oi = rn->info))
                        ospf_nbr_timer_update (oi);
            }

            /* Retransmit Interval */
            seconds = ovs_port->value_ospf_intervals [OVS_OSPF_RETRANSMIT_INTERVAL_SORTED];
            if (seconds < OSPF_MIN__RETRANSMIT_INTERVAL || seconds > OSPF_MAX_INTERVAL)
                VLOG_DBG("Retransmit Interval is invalid");
            else {
                SET_IF_PARAM (params, retransmit_interval);
                params->retransmit_interval = seconds;
            }

            /* Transmit Delay */
            seconds = ovs_port->value_ospf_intervals [OVS_OSPF_TRANSMIT_DELAY_SORTED];
            if (seconds < OSPF_MIN_INTERVAL || seconds > OSPF_MAX_INTERVAL)
                VLOG_DBG("Transmit delay is invalid");
            else {
                SET_IF_PARAM (params, retransmit_interval);
                params->retransmit_interval = seconds;
            }
        }
    }

    /* Priority */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_port_col_ospf_priority, idl_seqno)) {
        if (ovs_port->n_ospf_priority){
            val = *ovs_port->ospf_priority;
            if (val < OSPF_MIN_PRIORITY || val > OSPF_MAX_PRIORITY)
                    VLOG_DBG("Priority value is invalid");
            else {
                SET_IF_PARAM (params, priority);
                params->priority = val;

                for (rn = route_top (IF_OIFS (ifp)); rn; rn = route_next (rn)){
                    struct ospf_interface *oi = rn->info;

                    if (!oi)
                        continue;

                    if (PRIORITY (oi) != OSPF_IF_PARAM (oi, priority)) {
                        PRIORITY (oi) = OSPF_IF_PARAM (oi, priority);
                        OSPF_ISM_EVENT_SCHEDULE (oi, ISM_NeighborChange);
                        ovsdb_ospf_set_nbr_self_priority(oi->ifp->name, oi->nbr_self->src,
                                                      oi->nbr_self->priority);
                    }
                }
            }
        }
    }

    /* MTU ignore */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_port_col_ospf_mtu_ignore, idl_seqno)) {
        if (ovs_port->n_ospf_mtu_ignore){
            val = *ovs_port->ospf_mtu_ignore;
            params->mtu_ignore = val;
            if (val)
                SET_IF_PARAM (params, mtu_ignore);
            else
                UNSET_IF_PARAM (params, mtu_ignore);
        }
        else
        {
            VLOG_DBG("MTU ignore flag is not present");
            UNSET_IF_PARAM (params, mtu_ignore);
        }
    }

    /* Cost */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_port_col_ospf_if_out_cost, idl_seqno)) {
        if (ovs_port->n_ospf_if_out_cost){
            val = *ovs_port->ospf_if_out_cost;
            if (val < OSPF_MIN_INTERVAL || val > OSPF_MAX_INTERVAL)
                    VLOG_DBG("Cost value is invalid");
            else {
                SET_IF_PARAM (params, output_cost_cmd);
                params->output_cost_cmd = val;

                ospf_if_recalculate_output_cost (ifp);
            }
        }
        else
            VLOG_DBG("Interface cost is not present");
    }

    /* Network Type */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_port_col_ospf_if_type, idl_seqno)) {
        val = IF_DEF_PARAMS (ifp)->type;
        if (!strncmp(ovs_port->ospf_if_type,
                     OVSREC_PORT_OSPF_IF_TYPE_OSPF_IFTYPE_BROADCAST,
                     strlen(OVSREC_PORT_OSPF_IF_TYPE_OSPF_IFTYPE_BROADCAST))){
            IF_DEF_PARAMS (ifp)->type = OSPF_IFTYPE_BROADCAST;
        }
        else if (!strncmp(ovs_port->ospf_if_type,
                          OVSREC_PORT_OSPF_IF_TYPE_OSPF_IFTYPE_POINTOPOINT,
                          strlen(OVSREC_PORT_OSPF_IF_TYPE_OSPF_IFTYPE_POINTOPOINT))){
            IF_DEF_PARAMS (ifp)->type = OSPF_IFTYPE_POINTOPOINT;
        }

        if (val != IF_DEF_PARAMS (ifp)->type) {
            SET_IF_PARAM (IF_DEF_PARAMS (ifp), type);
            for (rn = route_top (IF_OIFS (ifp)); rn; rn = route_next (rn)){
                struct ospf_interface *oi = rn->info;

                if (!oi)
                    continue;

                oi->type = IF_DEF_PARAMS (ifp)->type;

                if (oi->state > ISM_Down){
                    OSPF_ISM_EVENT_EXECUTE (oi, ISM_InterfaceDown);
                    OSPF_ISM_EVENT_EXECUTE (oi, ISM_InterfaceUp);
                }
            }
        }
    }

    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_port_col_ospf_auth_type, idl_seqno))  {
        if (ovs_port->ospf_auth_type) {
            if (!strcmp(ovs_port->ospf_auth_type,OVSREC_PORT_OSPF_AUTH_TYPE_TEXT)) {
                SET_IF_PARAM (params, auth_type);
                params->auth_type = OSPF_AUTH_SIMPLE;
            }
            else if (!strcmp(ovs_port->ospf_auth_type,OVSREC_PORT_OSPF_AUTH_TYPE_MD5)) {
                SET_IF_PARAM (params, auth_type);
                params->auth_type = OSPF_AUTH_CRYPTOGRAPHIC;
            }
            else if (!strcmp(ovs_port->ospf_auth_type,OVSREC_PORT_OSPF_AUTH_TYPE_NULL)) {
                SET_IF_PARAM (params, auth_type);
                params->auth_type = OSPF_AUTH_NULL;
            }
        }
        else {
            params->auth_type = OSPF_AUTH_NOTSET;
            UNSET_IF_PARAM (params, auth_type);
        }
    }
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_port_col_ospf_auth_text_key, idl_seqno)) {
        if (ovs_port->ospf_auth_text_key) {
            memset (params->auth_simple, 0, OSPF_AUTH_SIMPLE_SIZE + 1);
            strncpy ((char *) params->auth_simple,
                ovs_port->ospf_auth_text_key, OSPF_AUTH_SIMPLE_SIZE);
            SET_IF_PARAM (params, auth_simple);
        }
        else {
            memset (params->auth_simple, 0, OSPF_AUTH_SIMPLE_SIZE);
            UNSET_IF_PARAM (params, auth_simple);
        }
    }
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_port_col_ospf_auth_md5_keys, idl_seqno)) {
        for (i = 0 ; i < ovs_port->n_ospf_auth_md5_keys;i++) {
            key_id = (unsigned char)ovs_port->key_ospf_auth_md5_keys[i];
            if (ospf_crypt_key_lookup (params->auth_crypt, key_id) != NULL) {
                VLOG_INFO ("OSPF MD5 key already present");
                continue;
            }
            else {
                ck = ospf_crypt_key_new ();
                ck->key_id = (u_char) key_id;
                memset (ck->auth_key, 0, OSPF_AUTH_MD5_SIZE+1);
                strncpy ((char *) ck->auth_key, ovs_port->value_ospf_auth_md5_keys[i], OSPF_AUTH_MD5_SIZE);
                ospf_crypt_key_add (params->auth_crypt, ck);
                SET_IF_PARAM (params, auth_crypt);
            }
        }
        /* check to see if any key is deleted */
        for (ALL_LIST_ELEMENTS_RO (params->auth_crypt, node, lookup_ck)) {
            is_key_found = false;
            for (i = 0; i<ovs_port->n_ospf_auth_md5_keys;i++) {
                if (lookup_ck->key_id == ovs_port->key_ospf_auth_md5_keys[i]) {
                    is_key_found = true;
                    break;
                }
            }
            if (!is_key_found) {
                ospf_crypt_key_delete (params->auth_crypt, lookup_ck->key_id);
            }
        }
    }
}

void
modify_ospf_vlink (struct ovsdb_idl *idl,
    const struct ovsrec_ospf_vlink* ovs_vlink,const struct ospf* ospf)
{
    struct ospf_vl_config_data vl_config;
    struct ospf_if_params *params = NULL;
    struct interface* ifp = NULL;
    struct listnode *node;
    struct crypt_key *ck;
    char auth_key[OSPF_AUTH_SIMPLE_SIZE+1];
    char md5_key[OSPF_AUTH_MD5_SIZE+1];
    int i = 0;
    u_int32_t seconds = 0;
    bool key_found = false;

    ifp = if_lookup_by_name(ovs_vlink->name);
    if(!ifp)
    {
        VLOG_DBG ("No VLINK interface %s found",ovs_vlink->name);
        return;
    }
    params = IF_DEF_PARAMS (ifp);
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_vlink_col_ospf_auth_type,idl_seqno)) {
        vl_config.auth_type = OSPF_AUTH_CMD_NOTSEEN;
        if (ovs_vlink->ospf_auth_type &&
            !strcmp(ovs_vlink->ospf_auth_type,OVSREC_OSPF_VLINK_OSPF_AUTH_TYPE_NULL))
               vl_config.auth_type = OSPF_AUTH_NULL;
        else if (ovs_vlink->ospf_auth_type &&
            !strcmp(ovs_vlink->ospf_auth_type,OVSREC_OSPF_VLINK_OSPF_AUTH_TYPE_TEXT))
               vl_config.auth_type = OSPF_AUTH_SIMPLE;
        else if (ovs_vlink->ospf_auth_type &&
            !strcmp(ovs_vlink->ospf_auth_type,OVSREC_OSPF_VLINK_OSPF_AUTH_TYPE_MD5))
               vl_config.auth_type = OSPF_AUTH_CRYPTOGRAPHIC;
        if (OSPF_AUTH_CMD_NOTSEEN != vl_config.auth_type) {
            SET_IF_PARAM (params, auth_type);
            params->auth_type = vl_config.auth_type;
        }
        else {
            if (OSPF_IF_PARAM_CONFIGURED(params,auth_type))
                UNSET_IF_PARAM (params, auth_type);
            params->auth_type = OSPF_AUTH_NOTSET;
        }
    }

    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_vlink_col_ospf_auth_text_key,idl_seqno)) {
        memset(params->auth_simple, 0, OSPF_AUTH_SIMPLE_SIZE+1);
        memset (auth_key, 0, OSPF_AUTH_SIMPLE_SIZE + 1);
        if (ovs_vlink->ospf_auth_text_key) {
            strncpy (auth_key, ovs_vlink->ospf_auth_text_key, OSPF_AUTH_SIMPLE_SIZE);
        }
        strncpy ((char *) params->auth_simple, auth_key,
                           OSPF_AUTH_SIMPLE_SIZE);
    }

    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_vlink_col_ospf_auth_md5_keys,idl_seqno)) {
        /*OPS_TODO : Make ospf_vlink->name as "mutable": false and
        "indexes": [
            [
              "name"
            ]
        ]*/
        for (i = 0 ; i < ovs_vlink->n_ospf_auth_md5_keys ; i++) {
            vl_config.crypto_key_id = ovs_vlink->key_ospf_auth_md5_keys[i];
            vl_config.md5_key = ovs_vlink->value_ospf_auth_md5_keys[i];
            if (!ospf_crypt_key_lookup (params->auth_crypt, vl_config.crypto_key_id)){
               ck = ospf_crypt_key_new ();
               ck->key_id = vl_config.crypto_key_id;
               memset(ck->auth_key, 0, OSPF_AUTH_MD5_SIZE+1);
               strncpy ((char *) ck->auth_key, vl_config.md5_key, OSPF_AUTH_MD5_SIZE);
               ospf_crypt_key_add (params->auth_crypt, ck);
            }
        }
        for (ALL_LIST_ELEMENTS_RO (params->auth_crypt, node, ck)) {
          key_found = false;
          for (i = 0 ; i < ovs_vlink->n_ospf_auth_md5_keys ; i++) {
              if (ck->key_id == ovs_vlink->key_ospf_auth_md5_keys[i]) {
                  key_found = true;
                  break;
              }
          }
          if (!key_found) {
              ospf_crypt_key_delete (params->auth_crypt, ck->key_id);
          }
        }
    }

    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_ospf_vlink_col_other_config,idl_seqno)) {
        seconds = smap_get_int(&(ovs_vlink->other_config),OSPF_KEY_HELLO_INTERVAL,10);
        if (seconds < 1 || seconds > 65535)
            VLOG_DBG("Hello Interval is invalid");
        else {
            vl_config.hello_interval = seconds;
            SET_IF_PARAM (params, v_hello);
            params->v_hello = vl_config.hello_interval;
        }
        seconds = smap_get_int(&(ovs_vlink->other_config),OSPF_KEY_DEAD_INTERVAL,40);
        if (seconds < 1 || seconds > 65535)
            VLOG_DBG("Dead Interval is invalid");
        else {
            vl_config.dead_interval = seconds;
            SET_IF_PARAM (params, v_wait);
            params->v_wait = vl_config.dead_interval;
        }
        seconds = smap_get_int(&(ovs_vlink->other_config),OSPF_KEY_RETRANSMIT_INTERVAL,5);
        if (seconds < 1 || seconds > 65535)
            VLOG_DBG("Retransmit Interval is invalid");
        else {
            vl_config.retransmit_interval = seconds;
            SET_IF_PARAM (params, retransmit_interval);
            params->retransmit_interval = vl_config.retransmit_interval;
        }
        seconds = smap_get_int(&(ovs_vlink->other_config),OSPF_KEY_TRANSMIT_DELAY,1);
        if (seconds < 1 || seconds > 65535)
            VLOG_DBG("Transmit delay is invalid");
        else {
            vl_config.transmit_delay = seconds;
            SET_IF_PARAM (params, transmit_delay);
            params->transmit_delay = vl_config.transmit_delay;
        }
    }
}

void
delete_ospf_router_instance (struct ovsdb_idl *idl)
{
    struct ovsrec_vrf* ovs_vrf;
    struct ospf *ospf_instance;
    struct listnode *node = NULL,*nnode = NULL;
    int i;

    for (ALL_LIST_ELEMENTS(om->ospf,node,nnode,ospf_instance)){
        bool match_found = 0;

        OVSREC_VRF_FOR_EACH (ovs_vrf, idl) {
            for (i = 0; i < ovs_vrf->n_ospf_routers; i++)
            {
                if ( ospf_instance->ospf_inst == ovs_vrf->key_ospf_routers[i]){
                    match_found = 1;
                    break;
                }

            if (!match_found) {
                VLOG_DBG("ospf_instance->ospf_inst: %d will be deleted from OSPFD\n", ospf_instance->ospf_inst);
                ospf_finish(ospf_instance);
            }
        }
    }
  }
}

static void
ospf_router_read_ovsdb_apply_changes(struct ovsdb_idl *idl)
{
    const struct ovsrec_vrf *ovs_vrf = NULL;
    const struct ovsrec_ospf_router* ovs_ospf = NULL;
    int i = 0;

     OVSREC_VRF_FOR_EACH(ovs_vrf, idl) {
        for (i = 0; i < ovs_vrf->n_ospf_routers; i++) {
            ovs_ospf = ovs_vrf->value_ospf_routers[i];
            if (OVSREC_IDL_IS_ROW_INSERTED(ovs_ospf, idl_seqno)) {
                    insert_ospf_router_instance(idl, ovs_ospf,ovs_vrf->key_ospf_routers[i]);
            }
            if (OVSREC_IDL_IS_ROW_MODIFIED(ovs_ospf, idl_seqno) ||
                (OVSREC_IDL_IS_ROW_INSERTED(ovs_ospf, idl_seqno))) {
                    modify_ospf_router_instance(idl, ovs_ospf,ovs_vrf->key_ospf_routers[i]);
            }
        }
    }
}

static void
ospf_area_read_ovsdb_apply_changes (struct ovsdb_idl *idl)
{
    const struct ovsrec_vrf* ovs_vrf = NULL;
    const struct ovsrec_ospf_router* ovs_ospf = NULL;
    const struct ovsrec_ospf_area* ovs_area = NULL;
    int64_t instance = 0;
    int i = 0,j = 0;

     OVSREC_VRF_FOR_EACH(ovs_vrf, idl) {
        for (j = 0 ; j < ovs_vrf->n_ospf_routers; j++) {
            ovs_ospf = ovs_vrf->value_ospf_routers[j];
            if (ovs_ospf) {
                instance = ovs_vrf->key_ospf_routers[j];
                for (i = 0; i < ovs_ospf->n_areas; i++) {
                    ovs_area = ovs_ospf->value_areas[i];
                    if (OVSREC_IDL_IS_ROW_INSERTED(ovs_area, idl_seqno)) {
                        insert_ospf_area_instance(idl, ovs_ospf->key_areas[i],instance);
                    }
                    if (OVSREC_IDL_IS_ROW_MODIFIED(ovs_area, idl_seqno) ||
                        OVSREC_IDL_IS_ROW_INSERTED(ovs_area, idl_seqno)) {
                            modify_ospf_area_instance(idl, ovs_area,ovs_ospf->key_areas[i],instance);
                    }
                }
            }
        }
    }
}

static void
ospf_port_read_ovsdb_apply_changes (struct ovsdb_idl *idl)
{
  const struct ovsrec_vrf *ovs_vrf = NULL;
  const struct ovsrec_port *ovs_port = NULL;
  struct listnode *node, *nextnode;
  int i = 0;

  OVSREC_VRF_FOR_EACH (ovs_vrf, idl) {
    for (i = 0 ; i < ovs_vrf->n_ports; i++) {
      ovs_port = ovs_vrf->ports[i];
      if (ovs_port) {
        if (OVSREC_IDL_IS_ROW_INSERTED(ovs_port, idl_seqno)) {
          ospf_interface_add_from_ovsdb (idl, ovs_vrf, ovs_port);
        }
        if (OVSREC_IDL_IS_ROW_MODIFIED(ovs_port, idl_seqno) ||
           (OVSREC_IDL_IS_ROW_INSERTED(ovs_port, idl_seqno))) {
          ospf_interface_update_from_ovsdb (idl, ovs_vrf, ovs_port);
        }
      }
    }
  }
}

static void
ospf_intf_read_ovsdb_apply_changes (struct ovsdb_idl *idl)
{
  const struct ovsrec_vrf *ovs_vrf = NULL;
  const struct ovsrec_port *ovs_port = NULL;
  const struct ovsrec_interface *ovs_interface = NULL;
  int i = 0;

  OVSREC_VRF_FOR_EACH (ovs_vrf, idl) {
    for (i = 0 ; i < ovs_vrf->n_ports; i++) {
      ovs_port = ovs_vrf->ports[i];
      if (ovs_port) {
        ovs_interface = ovs_port->interfaces[0];
        if (ovs_interface) {
          if (OVSREC_IDL_IS_ROW_MODIFIED(ovs_interface, idl_seqno) ||
             (OVSREC_IDL_IS_ROW_INSERTED(ovs_interface, idl_seqno))) {
            ospf_interface_state_update_from_ovsdb (idl, ovs_port, ovs_interface, NULL);
          }
        }
      }
    }
  }
}

static void
ospf_interface_read_ovsdb_apply_changes(struct ovsdb_idl *idl)
{
    const struct ovsrec_ospf_interface* ovs_oi = NULL;
    struct ovsrec_port* ovs_port = NULL;
    int i = 0;

     OVSREC_OSPF_INTERFACE_FOR_EACH(ovs_oi, idl) {
        ovs_port = ovs_oi->port;
        if (ovs_port && OVSREC_IDL_IS_ROW_MODIFIED(ovs_port, idl_seqno))
           modify_ospf_interface (idl, ovs_port, ovs_oi->name);
     }
}

static int
ovs_ospf_vl_delete(struct ovsdb_idl *idl)
{
    struct listnode *node = NULL,*nnode = NULL;
    struct ovsrec_ospf_vlink* ovs_vl = NULL;
    struct ospf_vl_data* vl_data = NULL;
    struct ospf* ospf = NULL;
    int i;

    ospf = ospf_lookup_by_instance(OSPF_DEFAULT_INSTANCE);
    if (!ospf)
    {
        VLOG_DBG (" No OSPF instance found for VLINKS");
        return 1;
    }

    for (ALL_LIST_ELEMENTS(ospf->vlinks,node,nnode,vl_data)){
        bool match_found = 0;
        if(NULL == vl_data->vl_oi||
           NULL == vl_data->vl_oi->ifp ||
           NULL == vl_data->vl_oi->ifp->name) {
              ospf_vl_data_free (vl_data);
              continue;
        }
        OVSREC_OSPF_VLINK_FOR_EACH (ovs_vl, idl) {
           if (!strcmp(ovs_vl->name,vl_data->vl_oi->ifp->name)){
               match_found = 1;
               break;
           }
        }
        if (!match_found) {
                VLOG_DBG("VLINK %s will be deleted from OSPFD\n", vl_data->vl_oi->ifp->name);
                ospf_vl_delete (ospf, vl_data);
                ospf_area_check_free (ospf, vl_data->vl_area_id);
        }
    }
    return 0;
}

static int
ovs_ospf_vlink_delete_all (struct ovsdb_idl *idl)
{
    struct listnode *node = NULL,*nnode = NULL;
    struct ovsrec_ospf_vlink* ovs_vl = NULL;
    struct ospf_vl_data* vl_data = NULL;
    struct ospf* ospf = NULL;

    ospf = ospf_lookup_by_instance(OSPF_DEFAULT_INSTANCE);
    if (!ospf)
    {
        VLOG_DBG (" No OSPF instance found for VLINKS");
        return 1;
    }
    for (ALL_LIST_ELEMENTS(ospf->vlinks,node,nnode,vl_data))
        ospf_vl_delete(ospf, vl_data);

    return 0;

}

static void
ospf_vlink_read_ovsdb_apply_changes (struct ovsdb_idl *idl)
{
    const struct ovsrec_ospf_vlink* ovs_vlink = NULL;
    struct ospf* ospf_inst = NULL;
    int i = 0;

    ospf_inst = ospf_lookup_by_instance(OSPF_DEFAULT_INSTANCE);
    if (!ospf_inst)
    {
        VLOG_DBG ("No OSPF Instance found");
        return;
    }

     OVSREC_OSPF_VLINK_FOR_EACH(ovs_vlink, idl) {
        if (OVSREC_IDL_IS_ROW_INSERTED(ovs_vlink, idl_seqno))
           insert_ospf_vlink (idl, ospf_inst, ovs_vlink);
        if (OVSREC_IDL_IS_ROW_MODIFIED(ovs_vlink, idl_seqno) ||
            OVSREC_IDL_IS_ROW_INSERTED(ovs_vlink, idl_seqno))
           modify_ospf_vlink (idl, ovs_vlink,ospf_inst);
     }
}


static void
ospf_set_hostname (char *hostname)
{
    if (host.name)
        XFREE (MTYPE_HOST, host.name);

    host.name = XSTRDUP(MTYPE_HOST, hostname);
}

static void
ospf_apply_global_changes (void)
{
    const struct ovsrec_system *ovs;

    ovs = ovsrec_system_first(idl);
    if (OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ovs, idl_seqno)) {
        VLOG_DBG ("First Row deleted from Open_vSwitch tbl\n");
        return;
    }
    if (!OVSREC_IDL_ANY_TABLE_ROWS_INSERTED(ovs, idl_seqno) &&
            !OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED(ovs, idl_seqno)) {
        VLOG_DBG ("No Open_vSwitch cfg changes");
        return;
    }

//Not needed to set hostname.
    if (ovs) {
        /* Update the hostname */
        ospf_set_hostname(ovs->hostname);
    }

    // TODO: Add reconfigurations that will be needed by OSPF daemon
}

static int
ospf_apply_port_changes (struct ovsdb_idl *idl)
{
  const struct ovsrec_vrf *ovs_vrf = NULL;
  const struct ovsrec_port* port_first = NULL;
  struct listnode *node, *nextnode;
  struct interface *ifp;

  port_first = ovsrec_port_first(idl);

  if (port_first == NULL) {
    /* No row in the Port table present */
    /* Delete all the interfaces in the iflist */
    OVSREC_VRF_FOR_EACH (ovs_vrf, idl) {
      for (ALL_LIST_ELEMENTS (iflist, node, nextnode, ifp)) {
        ospf_interface_delete_from_ovsdb (idl, ovs_vrf, ifp);
      }
    }
    return 1;
  }

  if (port_first && !OVSREC_IDL_ANY_TABLE_ROWS_INSERTED(port_first, idl_seqno)
      && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED(port_first, idl_seqno)
      && !OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED(port_first, idl_seqno)) {
    return 0;
  }

  if (OVSREC_IDL_ANY_TABLE_ROWS_DELETED(port_first, idl_seqno)) {
    /* Delete the interface from the iflist */
    OVSREC_VRF_FOR_EACH (ovs_vrf, idl) {
      for (ALL_LIST_ELEMENTS (iflist, node, nextnode, ifp)) {
        if (!find_vrf_port_by_name (ovs_vrf, ifp->name)) {
          ospf_interface_delete_from_ovsdb (idl, ovs_vrf, ifp);
        }
      }
    }
  }

  /* insert and modify cases */
  ospf_port_read_ovsdb_apply_changes (idl);

  /* Other ospf interface configuration  parameter changes */
  ospf_interface_read_ovsdb_apply_changes(idl);

  return 1;
}

static int
ospf_apply_interface_changes (struct ovsdb_idl *idl)
{
  const struct ovsrec_interface* intf_first = NULL;

  intf_first = ovsrec_interface_first(idl);

  if (intf_first == NULL) {
    VLOG_DBG("No row in the Interface table present!\n");
    return 1;
  }

  /*
   * Check if any table changes present.
   * If no change just return from here
   */
  if (intf_first && !OVSREC_IDL_ANY_TABLE_ROWS_INSERTED (intf_first, idl_seqno)
      && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED (intf_first, idl_seqno)
      && !OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED (intf_first, idl_seqno)) {
    return 0;
  }

  if (OVSREC_IDL_ANY_TABLE_ROWS_DELETED (intf_first, idl_seqno)) {
    VLOG_DBG ("Interface delete\n");
    /*TODO Handle interface delete - Unlikely case*/
  }
  if (OVSREC_IDL_ANY_TABLE_ROWS_INSERTED (intf_first, idl_seqno)
      || OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED (intf_first, idl_seqno)) {
    /* Interface insert or modify */
    ospf_intf_read_ovsdb_apply_changes (idl);
  }

  return 1;
}

static int
ospf_apply_ospf_router_changes (struct ovsdb_idl *idl)
{
   const struct ovsrec_ospf_router* ospf_router_first = NULL;
   struct ospf *ospf_instance;

    ospf_router_first = ovsrec_ospf_router_first(idl);

    if (ospf_router_first && !OVSREC_IDL_ANY_TABLE_ROWS_INSERTED(ospf_router_first, idl_seqno)
        && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ospf_router_first, idl_seqno)
        && !OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED(ospf_router_first, idl_seqno)) {
        /* No OSPF router changes */
        return 0;
    }
    if (ospf_router_first == NULL) {
            /* Check if it is a first row deletion */
            VLOG_DBG("OSPF config empty!\n");
            /* OPS_TODO : Support for multiple instances */
            ospf_instance = ospf_lookup();
            // TODO: Delete all instance as  there is no OSPF config in DB
            if (ospf_instance) {
                ospf_finish(ospf_instance);
            }
            return 1;
        }

    /* Check if any row deletion */
    if (OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ospf_router_first, idl_seqno)) {
        delete_ospf_router_instance(idl);
    }

    /* insert and modify cases */
    ospf_router_read_ovsdb_apply_changes(idl);

    // TODO: Add reconfigurations that will be needed by OSPF daemon
    return 1;
}

static int
ospf_apply_ospf_area_changes (struct ovsdb_idl *idl)
{
    const struct ovsrec_ospf_area* ospf_area_first = NULL;
    struct ospf *ospf_instance;

    ospf_area_first = ovsrec_ospf_area_first(idl);
    /*
     * Check if any table changes present.
     * If no change just return from here
     */
    if (ospf_area_first && !OVSREC_IDL_ANY_TABLE_ROWS_INSERTED(ospf_area_first, idl_seqno)
        && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ospf_area_first, idl_seqno)
        && !OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED(ospf_area_first, idl_seqno)) {
            VLOG_DBG("No OSPF area changes");
            return 0;
    }
    if (ospf_area_first == NULL) {
            /* Check if it is a first row deletion */
            /* Area is created by the OSPF daemon so donothing ish */
            VLOG_DBG("OSPF area config empty!\n");
            return 1;
        }

    /* Check if any row deletion */
    if (OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ospf_area_first, idl_seqno)) {
        VLOG_DBG("Some OSPF areas are deleted!\n");
    }

    /* insert and modify cases */
    ospf_area_read_ovsdb_apply_changes(idl);

    return 1;
}

static unsigned char
route_from2type(const char* from)
{
    if (!strcmp(from,OVSREC_ROUTE_FROM_CONNECTED))
        return ZEBRA_ROUTE_CONNECT;
    else if (!strcmp(from,OVSREC_ROUTE_FROM_STATIC))
        return ZEBRA_ROUTE_STATIC;
    else if (!strcmp(from,OVSREC_ROUTE_FROM_BGP))
        return ZEBRA_ROUTE_BGP;

    return ZEBRA_ROUTE_MAX;
}

static int
ospf_apply_route_changes (struct ovsdb_idl *idl)
{
   const struct ovsrec_route* route_first = NULL;
   const struct ovsrec_route* route_iter = NULL;
   const struct ovsrec_route* route_redist = NULL;
   const struct ovsrec_port* nh_port = NULL;
   struct in_addr nh_addr;
   struct in_addr fwd;
   struct ospf* ospf_instance = NULL;
   struct prefix_ipv4 p_redist;
   struct prefix nh;
   struct external_info* ei = NULL;
   struct external_info* ei_iter = NULL;
   struct listnode* node;
   struct route_node *rn;
   struct ospf_interface* oi;
   unsigned int nh_ifindex = 0;
   unsigned char type;
   int nh_index = 0;
   bool nh_ipv4_found = false;
   bool route_found = false;
   bool def_route_found = false;

   route_first = ovsrec_route_first(idl);
   if(!route_first)
   {
        VLOG_DBG("No Route present");
        return 0;
   }
   /*
    * Check if any table changes present.
    * If no change just return from here
    */
    if (route_first && !OVSREC_IDL_ANY_TABLE_ROWS_INSERTED(route_first, idl_seqno)
        && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED(route_first, idl_seqno)
        && !OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED(route_first, idl_seqno)) {
            VLOG_DBG("No Route changes");
            return 0;
    }

    ospf_instance = ospf_lookup_by_instance(OSPF_DEFAULT_INSTANCE);
    if (!ospf_instance)
    {
        VLOG_ERR ("No OSPF instance found to apply route changes");
        return 0;
    }
    /* Check if any route is deleted but AS external LSA is present
       then delete it.
       FIXME:Need route optimization*/
    if (OVSREC_IDL_ANY_TABLE_ROWS_DELETED(route_first,idl_seqno)) {
        for (type = ZEBRA_ROUTE_CONNECT; type <= ZEBRA_ROUTE_MAX; type++) {
            if ((type == ZEBRA_ROUTE_MAX) &&
                !redist_default)
                continue;
            else if ((type != ZEBRA_ROUTE_MAX) &&
                !redist[type])
                continue;

            if (EXTERNAL_INFO (type) != NULL)
                for (rn = route_top (EXTERNAL_INFO (type)); rn; rn = route_next (rn))
                {
                  if (rn->info == NULL)
                    continue;
                  ei_iter = (struct external_info*)rn->info;
                  struct prefix p_ei;
                  p_ei.family = AF_INET;
                  p_ei.prefixlen = ei_iter->p.prefixlen;
                  p_ei.u.prefix4 = ei_iter->p.prefix;
                  route_found = false;
                  def_route_found = false;
                  OVSREC_ROUTE_FOR_EACH(route_iter,idl)
                  {
                    struct prefix p_temp;
                    struct prefix p_ipv4_temp;
                    if (route_iter->address_family &&
                        !strcmp(route_iter->address_family,OVSREC_ROUTE_ADDRESS_FAMILY_IPV6))
                        continue;
                    str2prefix(route_iter->prefix,&p_temp);
                    str2prefix_ipv4(route_iter->prefix,&p_ipv4_temp);
                    if (type == ZEBRA_ROUTE_MAX)
                    {
                        if (is_prefix_default(&p_ipv4_temp)) {
                            def_route_found = true;
                            break;
                        }
                        else
                            continue;
                    }
                    if (type != route_from2type(route_iter->from))
                        continue;
                    if (prefix_same(&p_temp,&p_ei)) {
                        route_found = true;
                        break;
                    }
                  }
                  if ((type == ZEBRA_ROUTE_MAX) &&
                    !def_route_found) {
                    if (ospf_instance->default_originate != DEFAULT_ORIGINATE_ALWAYS) {
                        if (ospf_external_info_find_lsa (ospf_instance, &ei_iter->p))
                        {
                          ospf_external_lsa_flush (ospf_instance, type, &ei_iter->p,
                                       ei_iter->ifindex /*, ei->nexthop */);
                          ospf_external_info_free (ei_iter);
                          route_unlock_node (rn);
                          rn->info = NULL;
                        }
                    }
                  }
                  else if ((type != ZEBRA_ROUTE_MAX) &&
                    !route_found) {
                    /* Flush the LSA */
                    if (ospf_external_info_find_lsa (ospf_instance, &ei_iter->p))
                    {
                      ospf_external_lsa_flush (ospf_instance, type, &ei_iter->p,
                                   ei_iter->ifindex /*, ei->nexthop */);
                      ospf_external_info_free (ei_iter);
                      route_unlock_node (rn);
                      rn->info = NULL;
                    }
                  }
                }
        }
    }
    if (redist[ZEBRA_ROUTE_CONNECT] ||
        redist[ZEBRA_ROUTE_STATIC] ||
        redist[ZEBRA_ROUTE_BGP] ||
        redist_default)
    {
        OVSREC_ROUTE_FOR_EACH(route_redist,idl)
        {
            if (OVSREC_IDL_IS_ROW_INSERTED(route_redist,idl_seqno) ||
                OVSREC_IDL_IS_ROW_MODIFIED(route_redist,idl_seqno)) {
                str2prefix_ipv4(route_redist->prefix,&p_redist);
                type = route_from2type(route_redist->from);
                if (is_prefix_default(&p_redist) &&
                    redist_default)
                {
                    if((NULL == EXTERNAL_INFO (DEFAULT_ROUTE)) ||
                        !(ei = ospf_external_info_lookup(DEFAULT_ROUTE,&p_redist))) {
                        /* if DEFAULT_ORIGINATE_ALWAYS then we assume that the ospf router
                        instance changes has covered that */
                        p_redist.prefix.s_addr = 0;
                        ospf_external_info_add(DEFAULT_ROUTE,p_redist,0,p_redist.prefix);
                    }
                    ospf_external_lsa_refresh_default (ospf_instance);
                }
                else if (!is_prefix_default(&p_redist) &&
                    redist[type])
                {
                   if((NULL == EXTERNAL_INFO (DEFAULT_ROUTE)) ||
                    !(ei = ospf_external_info_lookup(type,&p_redist))) {
                       nh_ipv4_found = false;
                       for (nh_index = 0 ; nh_index < route_redist->n_nexthops;nh_index++)
                       {
                           if (!nh_port && route_redist->nexthops[nh_index]->n_ports)
                            nh_port = route_redist->nexthops[nh_index]->ports[0];
                           /* Zebra takes time to update the selected flag. Not sure
                           whether to check or not
                           if (route_first->nexthops[nh_index]->ip_address &&
                              route_first->nexthops[nh_index]->selected[0]) { */
                           if (route_redist->nexthops[nh_index]->ip_address) {
                               inet_aton(route_redist->nexthops[nh_index]->ip_address,&nh_addr);
                               nh.family = AF_INET;
                               nh.u.prefix4 = nh_addr;
                               nh.prefixlen = IPV4_MAX_BITLEN;
                               for (ALL_LIST_ELEMENTS_RO (ospf_instance->oiflist, node, oi))
                               {
                                    if (if_is_operative (oi->ifp))
                                      if (oi->address->family == AF_INET)
                                        if (prefix_match (oi->address, &nh)) {
                                          fwd = nh_addr;
                                          nh_ifindex = oi->ifp->ifindex;
                                          nh_ipv4_found = true;
                                          break;
                                        }
                               }
                               if (nh_ipv4_found)
                                   break;
                           }
                       }
                       if (!nh_ipv4_found)
                       {
                          fwd.s_addr = 0;
                          if (nh_port)
                            nh_ifindex = ifname2ifindex(nh_port->name);
                          else
                            nh_ifindex = 0;
                       }
                       ospf_external_info_add(type,p_redist,nh_ifindex,fwd);
                   }
                   ospf_external_lsa_refresh_type(ospf_instance,type,LSA_REFRESH_FORCE);
                }

            }
        }
    }
    return 1;
}

static int
ospf_apply_ospf_interface_changes (struct ovsdb_idl *idl)
{
  const struct ovsrec_ospf_interface* ospf_intf_first = NULL;
  struct ospf *ospf_instance;

  ospf_intf_first = ovsrec_ospf_interface_first(idl);

  /* OPS_TODO : Not sure to handle forceful deletion
   * interfaces using external tools as interface will be
   * created and deleted by ospfd or "[no] router ospf"
   */

  if (ospf_intf_first == NULL) {
    /* No row in the OSPF_Interface table present */
    return 1;
  }

  if (ospf_intf_first && !OVSREC_IDL_ANY_TABLE_ROWS_INSERTED(ospf_intf_first, idl_seqno)
      && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ospf_intf_first, idl_seqno)
      && !OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED(ospf_intf_first, idl_seqno)) {
    /* No OSPF OSPF Interface changes */
    return 0;
  }


  /* Check if any row deletion. May or may not by CLI */
  if (OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ospf_intf_first, idl_seqno)) {
    /* Some OSPF interfaces deleted externally */
    VLOG_ERR ("Some OSPF interfaces deleted externally!");
  }

  /* insert and modify cases */
  ospf_interface_read_ovsdb_apply_changes(idl);

  return 1;
}

static int
ospf_apply_vlink_changes (struct ovsdb_idl *idl)
{
   const struct ovsrec_ospf_vlink* ospf_vl_first = NULL;
   struct ospf *ospf_instance;

   ospf_vl_first = ovsrec_ospf_vlink_first(idl);
   /*
    * Check if any table changes present.
    * If no change just return from here
    */
    if (ospf_vl_first && !OVSREC_IDL_ANY_TABLE_ROWS_INSERTED(ospf_vl_first, idl_seqno)
        && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ospf_vl_first, idl_seqno)
        && !OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED(ospf_vl_first, idl_seqno)) {
            VLOG_DBG("No OSPF VLINK changes");
            return 0;
    }
    else if (NULL == ospf_vl_first) {
        (void)ovs_ospf_vlink_delete_all(idl);
        return 1;
    }

    /* Check if any row deletion. May or may not by CLI */
    if (OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ospf_vl_first, idl_seqno)) {
        (void)ovs_ospf_vl_delete(idl);
    }

    /* insert and modify cases */
    ospf_vlink_read_ovsdb_apply_changes(idl);

    return 1;
}

/*
 * Update the ospf rib routes in the OSPF_Route table of the OVSDB database *
 */

/*
 * Update the ospf network routes in the OSPF_Route table of the OVSDB database *
 */
void
ovsdb_ospf_update_network_routes (const struct ospf *ospf, const struct route_table *rt)
{
  struct ovsrec_ospf_router *ospf_router_row = NULL;
  struct ovsrec_ospf_area *ospf_area_row = NULL;
  struct ovsrec_ospf_route *ospf_route_row = NULL;
  struct ovsrec_ospf_route **intra_area_rts = NULL, **inter_area_rts = NULL;
  struct ovsdb_idl_txn* ort_txn = NULL;
  enum   ovsdb_idl_txn_status txn_status;
  struct route_node *rn, *rn1;
  struct ospf_route *or;
  struct route_table *ospf_area_route_table = NULL, *per_area_rt_table = NULL;
  struct in_addr area_id;
  struct smap route_info;
  char   cost[9] = {0};
  char   prefix_str[19] = {0};
  struct listnode *pnode, *pnnode;
  struct ospf_path *path;
  char   **pathstrs = NULL;
  int    i = 0, j = 0, k = 0, l = 0;

  if (NULL == ospf || NULL == rt) {
    VLOG_DBG ("No ospf instance or no routes to add");
    return;
  }

  ospf_router_row = ovsdb_ospf_get_router_by_instance_num (ospf->ospf_inst);
  if (!ospf_router_row) {
    VLOG_DBG ("No OSPF Router in OVSDB could be found");
    return;
  }

  if (!ospf_router_row->n_areas) {
    VLOG_DBG ("No OSPF Area in OSPF Router in OVSDB could be found");
    return;
  }

  ort_txn = ovsdb_idl_txn_create(idl);
  if (!ort_txn) {
    VLOG_DBG ("Transaction create failed");
    return;
  }

  /* Delete all the network routes of all the areas in the ospf router instance */
  for (i = 0 ; i < ospf_router_row->n_areas ; i++) {
    ospf_area_row = ospf_router_row->value_areas[i];

    ovsrec_ospf_area_set_intra_area_ospf_routes (ospf_area_row, NULL, 0);

    ovsrec_ospf_area_set_inter_area_ospf_routes (ospf_area_row, NULL, 0);
  }

  /* Add ospf routes to OVSDB OSPF_Route table */

  /* Generating the per area ospf routing table */
  ospf_area_route_table = route_table_init ();
  for (rn = route_top (rt); rn; rn = route_next (rn)) {
    if ((or = rn->info)) {
      ospf_route_add_to_area_route_table (ospf_area_route_table, &(rn->p), or);
    }
  }

  /* Updating the OVSDB databse from the per area ospf routing table */
  for (rn = route_top (ospf_area_route_table); rn; rn = route_next (rn)) {
    if ((per_area_rt_table = (struct route_table *)(rn->info))) {
      area_id = rn->p.u.prefix4;
      if (ospf_area_row = ovsrec_ospf_area_get_area_by_id (ospf_router_row, area_id)) {
        i = j = 0;
        if (!(intra_area_rts = xcalloc (per_area_rt_table->count, sizeof (struct ovsrec_ospf_route *)))) {
          VLOG_ERR ("Memory allocation Failure");
          ovsdb_idl_txn_abort(ort_txn);
          route_unlock_node (rn);
          return;
        }
        if (!(inter_area_rts = xcalloc (per_area_rt_table->count, sizeof (struct ovsrec_ospf_route *)))) {
          VLOG_ERR ("Memory allocation Failure");
          free (intra_area_rts);
          ovsdb_idl_txn_abort(ort_txn);
          route_unlock_node (rn);
          return;
        }
        for (rn1 = route_top (per_area_rt_table); rn1; rn1 = route_next (rn1))
          if ((or = (struct ospf_route *)(rn1->info))) {
            memset(prefix_str, 0, sizeof(prefix_str));

            if (!(ospf_route_row = ovsrec_ospf_route_insert (ort_txn))) {
              VLOG_ERR ("insert in OSPF_Route Failed.");
              continue;
            }

            if (or->path_type == OSPF_PATH_INTRA_AREA) {
              intra_area_rts[i++] = ospf_route_row;
              ovsrec_ospf_route_set_path_type (ospf_route_row, OSPF_PATH_TYPE_STRING_INTRA_AREA);
            }
            else if (or->path_type == OSPF_PATH_INTER_AREA) {
              inter_area_rts[j++] = ospf_route_row;
              ovsrec_ospf_route_set_path_type (ospf_route_row, OSPF_PATH_TYPE_STRING_INTER_AREA);
            }
            else {
              continue;
            }

            snprintf (prefix_str, sizeof(prefix_str), "%s/%d", inet_ntoa (rn1->p.u.prefix4), rn1->p.prefixlen);
            ovsrec_ospf_route_set_prefix (ospf_route_row, prefix_str);

            if (!(or->path_type == OSPF_PATH_INTER_AREA && or->type == OSPF_DESTINATION_DISCARD)) {
              memset(cost, 0, sizeof(cost));
              smap_clone (&route_info, &(ospf_route_row->route_info));
              smap_replace (&route_info, OSPF_KEY_ROUTE_AREA_ID, inet_ntoa (or->u.std.area_id));
              snprintf (cost, sizeof(cost), "%d", or->cost);
              smap_replace (&route_info, OSPF_KEY_ROUTE_COST, cost);
              ovsrec_ospf_route_set_route_info (ospf_route_row, &route_info);
              smap_destroy (&route_info);
            }

            if (or->type == OSPF_DESTINATION_NETWORK) {
              k = 0;

              if (or->paths) {
                if (!(pathstrs = xcalloc (or->paths->count, sizeof (char *)))) {
                  VLOG_ERR ("Memory allocation Failure");
                  free (intra_area_rts);
                  free (inter_area_rts);
                  ovsdb_idl_txn_abort(ort_txn);
                  route_unlock_node (rn1);
                  route_unlock_node (rn);
                  return;
                }

                for (ALL_LIST_ELEMENTS (or->paths, pnode, pnnode, path))
                  if (if_lookup_by_index(path->ifindex)) {
                    if (!(pathstrs[k] = xcalloc (1, MAX_PATH_STRING_LEN * sizeof (char )))) {
                      VLOG_ERR ("Memory allocation Failure");
                      free (intra_area_rts);
                      free (inter_area_rts);
                      for (l = 0; l < k; l++) {
                        free(pathstrs[l]);
                      }
                      free (pathstrs);
                      ovsdb_idl_txn_abort(ort_txn);
                      route_unlock_node (rn1);
                      route_unlock_node (rn);
                      return;
                    }
                    if (path->nexthop.s_addr == 0) {
                      snprintf (pathstrs[k++], MAX_PATH_STRING_LEN, "directly attached to %s", ifindex2ifname (path->ifindex));
                    }
                    else {
                      snprintf (pathstrs[k++], MAX_PATH_STRING_LEN, "via %s, %s", inet_ntoa (path->nexthop), ifindex2ifname (path->ifindex));
                    }
                  }

                ovsrec_ospf_route_set_paths (ospf_route_row, pathstrs, k);
                for (l = 0; l < k; l++) {
                  free(pathstrs[l]);
                }
                free (pathstrs);
              }
            }
          }
         ovsrec_ospf_area_set_intra_area_ospf_routes (ospf_area_row, intra_area_rts, i);
         free (intra_area_rts);
         ovsrec_ospf_area_set_inter_area_ospf_routes (ospf_area_row, inter_area_rts, j);
         free (inter_area_rts);
      }
    }
  }

  ospf_area_route_table_free (ospf_area_route_table);

  txn_status = ovsdb_idl_txn_commit_block(ort_txn);
  if (TXN_SUCCESS != txn_status && TXN_UNCHANGED != txn_status) {
    VLOG_DBG ("OSPF Route add transaction commit failed:%d",txn_status);
  }

  ovsdb_idl_txn_destroy(ort_txn);

  return;
}

/*
 * Update the ospf router routes in the OSPF_Route table of the OVSDB database *
*/
void
ovsdb_ospf_update_router_routes (const struct ospf *ospf, const struct route_table *rt)
{
  struct ovsrec_ospf_router *ospf_router_row = NULL;
  struct ovsrec_ospf_area *ospf_area_row = NULL;
  struct ovsrec_ospf_route *ospf_route_row = NULL;
  struct ovsrec_ospf_route **router_rts = NULL;
  struct ovsdb_idl_txn* ort_txn = NULL;
  enum   ovsdb_idl_txn_status txn_status;
  struct route_node *rn, *rn1;
  struct listnode *node;
  struct ospf_route *or;
  struct route_table *ospf_area_route_table = NULL, *per_area_rt_table = NULL;
  struct in_addr area_id;
  struct listnode *pnode, *pnnode;
  struct ospf_path *path;
  struct smap route_info;
  char   prefix_str[19] = {0};
  char   cost[9] = {0};
  char   **pathstrs = NULL;
  int    i = 0, j = 0, k = 0, l = 0;

  if (NULL == ospf || NULL == rt) {
    VLOG_DBG ("No ospf instance or no routes to add");
    return;
  }

  ospf_router_row = ovsdb_ospf_get_router_by_instance_num (ospf->ospf_inst);
  if (!ospf_router_row) {
    VLOG_DBG ("No OSPF Router in OVSDB could be found");
    return;
  }

  if (!ospf_router_row->n_areas) {
    VLOG_DBG ("No OSPF Area in OSPF Router in OVSDB could be found");
    return;
  }

  ort_txn = ovsdb_idl_txn_create(idl);
  if (!ort_txn) {
    VLOG_DBG ("Transaction create failed");
    return;
  }

  /* Delete all the network routes of all the areas in the ospf router instance */
  for (i = 0 ; i < ospf_router_row->n_areas ; i++) {
    ospf_area_row = ospf_router_row->value_areas[i];

    ovsrec_ospf_area_set_router_ospf_routes (ospf_area_row, NULL, 0);
  }

  /* Add ospf routes to OVSDB OSPF_Route table */

  /* Generating the per area ospf routing table */
  ospf_area_route_table = route_table_init ();
  for (rn = route_top (rt); rn; rn = route_next (rn))
    if (rn->info)
      for (ALL_LIST_ELEMENTS_RO ((struct list *)rn->info, node, or))
        ospf_route_add_to_area_route_table (ospf_area_route_table, &(rn->p), or);

  /* Updating the OVSDB databse from the per area ospf routing table */
  for (rn = route_top (ospf_area_route_table); rn; rn = route_next (rn)) {
    if ((per_area_rt_table = (struct route_table *)(rn->info))) {
      area_id = rn->p.u.prefix4;
      if (ospf_area_row = ovsrec_ospf_area_get_area_by_id (ospf_router_row, area_id)) {
        i = j = 0;
        if (!(router_rts = xcalloc (per_area_rt_table->count, sizeof (struct ovsrec_ospf_route *)))) {
          VLOG_ERR ("Memory allocation Failure");
          ovsdb_idl_txn_abort(ort_txn);
          route_unlock_node (rn);
          return;
        }
        for (rn1 = route_top (per_area_rt_table); rn1; rn1 = route_next (rn1)) {
          if ((or = (struct ospf_route *)(rn1->info))) {
            memset(prefix_str, 0, sizeof(prefix_str));
            memset(cost, 0, sizeof(cost));
            k = 0;

            if (!(ospf_route_row = ovsrec_ospf_route_insert (ort_txn))) {
              VLOG_ERR ("insert in OSPF_Route Failed.");
              continue;
            }

            router_rts[i++] = ospf_route_row;

            snprintf (prefix_str, sizeof(prefix_str), "%s", inet_ntoa (rn1->p.u.prefix4));
            ovsrec_ospf_route_set_prefix (ospf_route_row, prefix_str);

            ovsrec_ospf_route_set_path_type (ospf_route_row, ospf_route_path_type_string (or->path_type));

            smap_clone (&route_info, &(ospf_route_row->route_info));
            smap_replace (&route_info, OSPF_KEY_ROUTE_AREA_ID, inet_ntoa (or->u.std.area_id));
            snprintf (cost, sizeof (cost), "%d", or->cost);
            smap_replace (&route_info, OSPF_KEY_ROUTE_COST, cost);
            smap_replace (&route_info, OSPF_KEY_ROUTE_TYPE_ABR, boolean2string(or->u.std.flags & ROUTER_LSA_BORDER));
            smap_replace (&route_info, OSPF_KEY_ROUTE_TYPE_ASBR, boolean2string(or->u.std.flags & or->u.std.flags & ROUTER_LSA_EXTERNAL));
            ovsrec_ospf_route_set_route_info (ospf_route_row, &route_info);
            smap_destroy (&route_info);

            if (or->paths) {
              if (!(pathstrs = xcalloc (or->paths->count, sizeof (char *)))) {
                VLOG_ERR ("Memory allocation Failure");
                free (router_rts);
                ovsdb_idl_txn_abort(ort_txn);
                route_unlock_node (rn1);
                route_unlock_node (rn);
                return;
              }

              for (ALL_LIST_ELEMENTS (or->paths, pnode, pnnode, path)) {
                if (if_lookup_by_index(path->ifindex)) {
                  if (!(pathstrs[k] = xcalloc (1, MAX_PATH_STRING_LEN * sizeof (char )))) {
                    VLOG_ERR ("Memory allocation Failure");
                    free (router_rts);
                    for (l = 0; l < k; l++) {
                      free(pathstrs[l]);
                    }
                    free (pathstrs);
                    ovsdb_idl_txn_abort(ort_txn);
                    route_unlock_node (rn1);
                    route_unlock_node (rn);
                    return;
                  }
                  if (path->nexthop.s_addr == 0) {
                    snprintf (pathstrs[k++], MAX_PATH_STRING_LEN, "directly attached to %s", ifindex2ifname (path->ifindex));
                  }
                  else {
                    snprintf (pathstrs[k++], MAX_PATH_STRING_LEN, "via %s, %s", inet_ntoa (path->nexthop), ifindex2ifname (path->ifindex));
                  }
                }
              }

              ovsrec_ospf_route_set_paths (ospf_route_row, pathstrs, k);
              for (l = 0; l < k; l++) {
                free(pathstrs[l]);
              }
              free (pathstrs);
            }
          }
        }
        ovsrec_ospf_area_set_router_ospf_routes (ospf_area_row, router_rts, i);
        free (router_rts);
      }
    }
  }

  ospf_area_route_table_free (ospf_area_route_table);

  txn_status = ovsdb_idl_txn_commit_block(ort_txn);
  if (TXN_SUCCESS != txn_status && TXN_UNCHANGED != txn_status) {
    VLOG_DBG ("OSPF Route add transaction commit failed:%d",txn_status);
  }

  ovsdb_idl_txn_destroy(ort_txn);

  return;
}

/*
 * Update the ospf external routes in the OSPF_Route table of the OVSDB database *
*/
void
ovsdb_ospf_update_ext_routes (const struct ospf *ospf, const struct route_table *rt)
{
  struct ovsrec_ospf_router *ospf_router_row = NULL;
  struct ovsrec_ospf_route *ospf_route_row = NULL;
  struct ovsrec_ospf_route **ext_rts = NULL;
  struct ovsdb_idl_txn* ort_txn = NULL;
  enum   ovsdb_idl_txn_status txn_status;
  struct route_node *rn;
  struct ospf_route *or;
  char   prefix_str[19] = {0};
  struct listnode *pnode, *pnnode;
  struct ospf_path *path;
  struct smap route_info;
  char   buf[20] = {0};
  char   **pathstrs = NULL;
  int    i = 0, k = 0, l = 0;

  if (NULL == ospf || NULL == rt) {
      VLOG_DBG ("No ospf instance or no routes to add");
      return;
  }

  ospf_router_row = ovsdb_ospf_get_router_by_instance_num (ospf->ospf_inst);
  if (!ospf_router_row) {
      VLOG_DBG ("No OSPF Router in OVSDB could be found");
      return;
  }

  ort_txn = ovsdb_idl_txn_create(idl);
  if (!ort_txn) {
      VLOG_DBG ("Transaction create failed");
      return;
  }

  /* Delete all the network routes of all the areas in the ospf router instance */
  ovsrec_ospf_router_set_ext_ospf_routes (ospf_router_row, NULL, 0);

  /* Add ospf routes to OVSDB OSPF_Route table */
  if (!(ext_rts = xcalloc (rt->count, sizeof (struct ovsrec_ospf_route *)))) {
    VLOG_ERR ("Memory allocation Failure");
    ovsdb_idl_txn_abort(ort_txn);
    return;
  }

  for (rn = route_top (rt); rn; rn = route_next (rn)) {
    if ((or = (struct ospf_route *)(rn->info))) {
      memset(prefix_str, 0, sizeof(prefix_str));
      memset(buf, 0, sizeof(buf));
      k = 0;

      if (!(ospf_route_row = ovsrec_ospf_route_insert (ort_txn))) {
        VLOG_ERR ("Insert in OSPF_Route table Failed.");
        continue;
      }

      ext_rts[i++] = ospf_route_row;

      snprintf (prefix_str, sizeof(prefix_str), "%s/%d", inet_ntoa (rn->p.u.prefix4), rn->p.prefixlen);
      ovsrec_ospf_route_set_prefix (ospf_route_row, prefix_str);

      ovsrec_ospf_route_set_path_type (ospf_route_row, ospf_route_path_type_string (or->path_type));

      smap_clone (&route_info, &(ospf_route_row->route_info));
      smap_replace (&route_info, OSPF_KEY_ROUTE_AREA_ID, inet_ntoa (or->u.std.area_id));
      snprintf (buf, 11, "%u", or->cost);
      smap_replace (&route_info, OSPF_KEY_ROUTE_COST, buf);
      smap_replace (&route_info, OSPF_KEY_ROUTE_TYPE_ABR, boolean2string(or->u.std.flags & ROUTER_LSA_BORDER));
      smap_replace (&route_info, OSPF_KEY_ROUTE_TYPE_ASBR, boolean2string(or->u.std.flags & or->u.std.flags & ROUTER_LSA_EXTERNAL));
      smap_replace (&route_info, OSPF_KEY_ROUTE_EXT_TYPE, ospf_route_path_type_ext_string (or->path_type));
      snprintf (buf, sizeof (buf), "%u", or->u.ext.tag);
      smap_replace (&route_info, OSPF_KEY_ROUTE_EXT_TAG, buf);
      if (or->path_type == OSPF_PATH_TYPE2_EXTERNAL) {
        snprintf (buf, sizeof (buf), "%u", or->u.ext.type2_cost);
        smap_replace (&route_info, OSPF_KEY_ROUTE_TYPE2_COST, buf);
      }
      ovsrec_ospf_route_set_route_info (ospf_route_row, &route_info);
      smap_destroy (&route_info);

      if (or->paths) {
        if (!(pathstrs = xcalloc (or->paths->count, sizeof (char *)))) {
          VLOG_ERR ("Memory allocation Failure");
          free (ext_rts);
          ovsdb_idl_txn_abort(ort_txn);
          route_unlock_node (rn);
          return;
        }
        for (ALL_LIST_ELEMENTS (or->paths, pnode, pnnode, path)) {
          if (if_lookup_by_index(path->ifindex)) {
            if (!(pathstrs[k] = xcalloc (1, MAX_PATH_STRING_LEN * sizeof (char )))) {
              VLOG_ERR ("Memory allocation Failure");
              free (ext_rts);
              for (l = 0; l < k; l++)
                free(pathstrs[l]);
              free (pathstrs);
              ovsdb_idl_txn_abort(ort_txn);
              route_unlock_node (rn);
              return;
            }
            if (path->nexthop.s_addr == 0) {
              snprintf (pathstrs[k++], MAX_PATH_STRING_LEN, "directly attached to %s", ifindex2ifname (path->ifindex));
            }
            else {
              snprintf (pathstrs[k++], MAX_PATH_STRING_LEN, "via %s, %s", inet_ntoa (path->nexthop), ifindex2ifname (path->ifindex));
            }
          }
        }

        ovsrec_ospf_route_set_paths (ospf_route_row, pathstrs, k);
        for (l = 0; l < k; l++) {
          free(pathstrs[l]);
        }
        free (pathstrs);
      }
    }
  }

  ovsrec_ospf_router_set_ext_ospf_routes (ospf_router_row, ext_rts, i);
  free (ext_rts);

  txn_status = ovsdb_idl_txn_commit_block(ort_txn);
  if (TXN_SUCCESS != txn_status && TXN_UNCHANGED != txn_status) {
    VLOG_DBG ("OSPF Route add transaction commit failed:%d",txn_status);
  }

  ovsdb_idl_txn_destroy(ort_txn);

  return;
}

/*
 * Update a single ospf external route in the OSPF_Route table of the OVSDB database *
*/
void
ovsdb_ospf_update_ext_route (const struct ospf *ospf, const struct prefix *p_or, const struct ospf_route *or)
{
  struct ovsrec_ospf_router *ospf_router_row = NULL;
  struct ovsrec_ospf_route *ospf_route_row = NULL;
  struct ovsrec_ospf_route **ext_rts = NULL;
  struct ovsdb_idl_txn* ort_txn = NULL;
  enum   ovsdb_idl_txn_status txn_status;
  char   prefix_str[19] = {0};
  struct listnode *pnode, *pnnode;
  struct ospf_path *path;
  struct smap route_info;
  char   buf[20] = {0};
  char   **pathstrs = NULL;
  int    k = 0, l = 0, match_found = 0;

  if (NULL == ospf || NULL == p_or ) {
      VLOG_DBG ("No ospf instance or no route");
      return;
  }

  ospf_router_row = ovsdb_ospf_get_router_by_instance_num (ospf->ospf_inst);
  if (!ospf_router_row) {
      VLOG_DBG ("No OSPF Router in OVSDB could be found");
      return;
  }

  ort_txn = ovsdb_idl_txn_create(idl);
  if (!ort_txn) {
      VLOG_DBG ("Transaction create failed");
      return;
  }

  /* Add ospf routes to OVSDB OSPF_Route table */
  if (!(ext_rts = xcalloc (ospf_router_row->n_ext_ospf_routes + 1, sizeof (struct ovsrec_ospf_route *)))) {
    VLOG_ERR ("Memory allocation Failure");
    ovsdb_idl_txn_abort(ort_txn);
    return;
  }

  prefix2str(p_or, prefix_str, sizeof(prefix_str));

  if (or) {
    if (!(ospf_route_row = ovsrec_ospf_route_insert (ort_txn))) {
      VLOG_ERR ("Insert in OSPF_Route table Failed.");
      free (ext_rts);
      ovsdb_idl_txn_abort(ort_txn);
      return;
    }

    ovsrec_ospf_route_set_prefix (ospf_route_row, prefix_str);

    ovsrec_ospf_route_set_path_type (ospf_route_row, ospf_route_path_type_string (or->path_type));

    smap_clone (&route_info, &(ospf_route_row->route_info));
    smap_replace (&route_info, OSPF_KEY_ROUTE_AREA_ID, inet_ntoa (or->u.std.area_id));
    snprintf (buf, sizeof (buf), "%u", or->cost);
    smap_replace (&route_info, OSPF_KEY_ROUTE_COST, buf);
    smap_replace (&route_info, OSPF_KEY_ROUTE_TYPE_ABR, boolean2string(or->u.std.flags & ROUTER_LSA_BORDER));
    smap_replace (&route_info, OSPF_KEY_ROUTE_TYPE_ASBR, boolean2string(or->u.std.flags & or->u.std.flags & ROUTER_LSA_EXTERNAL));
    smap_replace (&route_info, OSPF_KEY_ROUTE_EXT_TYPE, ospf_route_path_type_ext_string (or->path_type));
    snprintf (buf, sizeof (buf), "%u", or->u.ext.tag);
    smap_replace (&route_info, OSPF_KEY_ROUTE_EXT_TAG, buf);
    if (or->path_type == OSPF_PATH_TYPE2_EXTERNAL) {
      snprintf (buf, sizeof (buf), "%u", or->u.ext.type2_cost);
      smap_replace (&route_info, OSPF_KEY_ROUTE_TYPE2_COST, buf);
    }
    ovsrec_ospf_route_set_route_info (ospf_route_row, &route_info);
    smap_destroy (&route_info);
    if (or->paths) {
      if (!(pathstrs = xcalloc (or->paths->count, sizeof (char *)))) {
        VLOG_ERR ("Memory allocation Failure");
        free (ext_rts);
        ovsdb_idl_txn_abort(ort_txn);
        return;
      }
      for (ALL_LIST_ELEMENTS (or->paths, pnode, pnnode, path)) {
        if (if_lookup_by_index(path->ifindex)) {
          if (!(pathstrs[k] = xcalloc (1, MAX_PATH_STRING_LEN * sizeof (char )))) {
            VLOG_ERR ("Memory allocation Failure");
            free (ext_rts);
            for (l = 0; l < k; l++) {
              free(pathstrs[l]);
            }
            free (pathstrs);
            ovsdb_idl_txn_abort(ort_txn);
            return;
          }
          if (path->nexthop.s_addr == 0) {
            snprintf (pathstrs[k++], MAX_PATH_STRING_LEN, "directly attached to %s", ifindex2ifname (path->ifindex));
          }
          else {
            snprintf (pathstrs[k++], MAX_PATH_STRING_LEN, "via %s, %s", inet_ntoa (path->nexthop), ifindex2ifname (path->ifindex));
          }
        }
      }

      ovsrec_ospf_route_set_paths (ospf_route_row, pathstrs, k);
      for (l = 0; l < k; l++) {
        free(pathstrs[l]);
      }
      free (pathstrs);
    }
  }

  for (l = 0, k = 0; l < ospf_router_row->n_ext_ospf_routes; l++) {
    if (!match_found && !strncmp (ospf_router_row->ext_ospf_routes[l]->prefix, prefix_str, 19)) {
      if (or) {
        /* Update case */
        ext_rts[k++] = ospf_route_row;
        match_found = 1;
      }
      else {
        /* Delete case */
        continue;
      }
    }
    else {
      /* PASS case */
      ext_rts[k++] = ospf_router_row->ext_ospf_routes[l];
    }
  }

  if (or && !match_found) {
    /* Add case */
    ext_rts[k++] = ospf_route_row;
  }

  ovsrec_ospf_router_set_ext_ospf_routes (ospf_router_row, ext_rts, k);
  free (ext_rts);

  txn_status = ovsdb_idl_txn_commit_block(ort_txn);
  if (TXN_SUCCESS != txn_status && TXN_UNCHANGED != txn_status) {
    VLOG_DBG ("OSPF Route add transaction commit failed:%d",txn_status);
  }

  ovsdb_idl_txn_destroy(ort_txn);

  return;
}

/* Check idl seqno. to make sure there are updates to the idl
 * and update the local structures accordingly.
 */
static void
ospf_reconfigure(struct ovsdb_idl *idl)
{
    unsigned int new_idl_seqno = ovsdb_idl_get_seqno(idl);
    COVERAGE_INC(ospf_ovsdb_cnt);

    if (new_idl_seqno == idl_seqno){
        VLOG_DBG("No config change for ospf in ovs\n");
        return;
    }

    ospf_apply_global_changes();
    if (ospf_apply_port_changes(idl) |
        ospf_apply_interface_changes(idl) |
        ospf_apply_ospf_router_changes(idl) |
        ospf_apply_ospf_area_changes(idl) |
        ospf_apply_route_changes(idl)|
        ospf_apply_vlink_changes(idl))
    {
         /* Some OSPF configuration changed. */
        VLOG_DBG("OSPF Configuration changed\n");
    }

    /* update the seq. number */
    idl_seqno = new_idl_seqno;
}

/* Wrapper function that checks for idl updates and reconfigures the daemon
 */
static void
ospf_ovs_run (void)
{
    ovsdb_idl_run(idl);
    unixctl_server_run(appctl);

    if (ovsdb_idl_is_lock_contended(idl)) {
        static struct vlog_rate_limit rl = VLOG_RATE_LIMIT_INIT(1, 1);

        VLOG_ERR_RL(&rl, "another ospfd process is running, "
                    "disabling this process until it goes away");
        return;
    } else if (!ovsdb_idl_has_lock(idl)) {
        return;
    }

    ospf_chk_for_system_configured();

    if (system_configured) {
        ospf_reconfigure(idl);

        daemonize_complete();
        vlog_enable_async();
        VLOG_INFO_ONCE("%s (Halon ospfd) %s", program_name, VERSION);
    }
}

static void
ospf_ovs_wait (void)
{
    ovsdb_idl_wait(idl);
    unixctl_server_wait(appctl);
}

/* Callback function to handle read events
 * In the event of an update to the idl cache, this callback is triggered.
 * In this event, the changes are processed in the daemon and the cb
 * functions are re-registered.
 */
static int
ospf_ovs_read_cb (struct thread *thread)
{
    ospf_ovsdb_t *ospf_ovs_g;
    if (!thread) {
        VLOG_ERR("NULL thread in read cb function\n");
        return -1;
    }
    ospf_ovs_g = THREAD_ARG(thread);
    if (!ospf_ovs_g) {
        VLOG_ERR("NULL args in read cb function\n");
        return -1;
    }

    ospf_ovs_g->read_cb_count++;

    ospf_ovs_clear_fds();
    ospf_ovs_run();
    ospf_ovs_wait();

    if (0 != ospf_ovspoll_enqueue(ospf_ovs_g)) {
        /*
         * Could not enqueue the events.
         * Retry in 1 sec
         */
        thread_add_timer(ospf_ovs_g->master,
                         ospf_ovs_read_cb, ospf_ovs_g, 1);
    }
    return 1;
}

/* Add the list of OVS poll fd to the master thread of the daemon
 */
static int
ospf_ovspoll_enqueue (ospf_ovsdb_t *ospf_ovs_g)
{
    struct poll_loop *loop = poll_loop();
    struct poll_node *node;
    long int timeout;
    int retval = -1;

    /* Populate with all the fds events. */
    HMAP_FOR_EACH (node, hmap_node, &loop->poll_nodes) {
        thread_add_read(ospf_ovs_g->master,
                                    ospf_ovs_read_cb,
                                    ospf_ovs_g, node->pollfd.fd);
        /*
         * If we successfully connected to OVS return 0.
         * Else return -1 so that we try to reconnect.
         * */
        retval = 0;
    }

    /* Populate the timeout event */
    timeout = loop->timeout_when - time_msec();
    if(timeout > 0 && loop->timeout_when > 0 &&
       loop->timeout_when < LLONG_MAX) {
        /* Convert msec to sec */
        timeout = (timeout + 999)/1000;

        thread_add_timer(ospf_ovs_g->master,
                                     ospf_ovs_read_cb, ospf_ovs_g,
                                     timeout);
    }

    return retval;
}

/* Initialize and integrate the ovs poll loop with the daemon */
void ospf_ovsdb_init_poll_loop (struct ospf_master *ospfm)
{
    if (!glob_ospf_ovs.enabled) {
        VLOG_ERR("OVS not enabled for ospf. Return\n");
        return;
    }
    glob_ospf_ovs.master = ospfm->master;

    ospf_ovs_clear_fds();
    ospf_ovs_run();
    ospf_ovs_wait();
    ospf_ovspoll_enqueue(&glob_ospf_ovs);
}

static void
ovsdb_exit(void)
{
    ovsdb_idl_destroy(idl);
}

/* When the daemon is ready to shut, delete the idl cache
 * This happens with the ovs-appctl exit command.
 */
void ospf_ovsdb_exit(void)
{
    ovsdb_exit();
}

/*
 * Static routines related to OVSDB OSPF_Route table update *
 */

static void
ospf_route_add_to_area_route_table (struct route_table * oart, struct prefix *p_or, struct ospf_route *or)
{
  struct route_table *area_rt_table;
  struct route_node *rn, *rn_or;
  struct prefix p_area;
  struct ospf_route *or_new;

  if (!oart) {
    return;
  }

  p_area.family = AF_INET;
  p_area.prefixlen = IPV4_MAX_BITLEN;
  p_area.u.prefix4 = or->u.std.area_id;

  rn = route_node_get (oart, (struct prefix *)&p_area);

  if (!rn->info) {
    rn->info = route_table_init ();
  }

  area_rt_table = (struct  route_table *) (rn->info);

  or_new = ospf_route_new ();
  or_new->type = or->type;
  or_new->id = or->id;
  or_new->mask = or->mask;
  or_new->path_type = or->path_type;
  or_new->cost = or->cost;
  or_new->u = or->u;

  ospf_route_add (area_rt_table, (struct prefix_ipv4 *)p_or, or_new, or);
}

static void
ospf_area_route_table_free (struct route_table *oart)
{
  struct route_table *area_rt_table;
  struct route_node *rn, *rn1;
  struct ospf_route *or;

  if (!oart) {
    return;
  }

  for (rn = route_top (oart); rn; rn = route_next (rn)) {
    if ((area_rt_table = rn->info) != NULL) {
      for (rn1 = route_top (area_rt_table); rn1; rn1 = route_next (rn1)) {
         if ((or = rn1->info) != NULL) {
           ospf_route_free (or);
           rn1->info = NULL;
           route_unlock_node (rn1);
         }
      }
      route_table_finish (area_rt_table);
      rn->info = NULL;
      route_unlock_node (rn);
    }
  }
  route_table_finish (oart);
}

/* TODO This util function can be moved to common utils file */
static char *
boolean2string (bool flag)
{
  if (flag) {
    return BOOLEAN_STRING_TRUE;
  }
  else {
    return BOOLEAN_STRING_FALSE;
  }
}

static char *
ospf_route_path_type_string (u_char path_type)
{
  switch (path_type) {
    case OSPF_PATH_INTRA_AREA:
           return OSPF_PATH_TYPE_STRING_INTRA_AREA;

    case OSPF_PATH_INTER_AREA:
           return OSPF_PATH_TYPE_STRING_INTER_AREA;

    case OSPF_PATH_TYPE1_EXTERNAL:
    case OSPF_PATH_TYPE2_EXTERNAL:
           return OSPF_PATH_TYPE_STRING_EXTERNAL;

    default:
           return "invalid";
  }
}

static char *
ospf_route_path_type_ext_string (u_char path_type)
{
  switch (path_type) {
    case OSPF_PATH_TYPE1_EXTERNAL:
           return OSPF_EXT_TYPE_STRING_TYPE1;
    case OSPF_PATH_TYPE2_EXTERNAL:
           return OSPF_EXT_TYPE_STRING_TYPE2;

    default:
           return "invalid";
  }
}

#define INTERFACE_HW_INTF_INFO_MAP_MEDIA_TYPE "media_type"

#define INTERFACE_HW_INTF_INFO_MAP_HW_TYPE_BROADCAST "broadcast"
#define INTERFACE_HW_INTF_INFO_MAP_HW_TYPE_POINT_TO_POINT "point-to-point"

#define DEFAULT_ETH_MTU 1500

/*
 * check the port status from the ovsdb port row
 * return value: 1 for up, 0 for down
 */
static int
is_ovs_port_state_up (struct ovsdb_idl *idl, const struct ovsrec_port *ovs_port,
      const struct ovsrec_interface *ovs_interface, const struct interface *ifp)
{
  assert (ovs_port && ovs_interface && ifp);

  if (ifp->ifindex == IFINDEX_INTERNAL) {
    return 0;
  }

  if ((ovs_interface->admin_state &&
        (strncmp (ovs_interface->admin_state, OVSREC_INTERFACE_ADMIN_STATE_UP,
                  sizeof (OVSREC_INTERFACE_ADMIN_STATE_UP)) == 0)) &&
     (ovs_interface->link_state &&
        (strncmp (ovs_interface->link_state, OVSREC_INTERFACE_LINK_STATE_UP,
                  sizeof (OVSREC_INTERFACE_LINK_STATE_UP)) == 0))) {
    return 1;
  }

  return 0;
}

void
if_set_value_from_ovsdb (struct ovsdb_idl *idl, const struct ovsrec_port *ovs_port, struct interface *ifp)
{
  const struct ovsrec_interface *ovs_interface = NULL;
  const struct ovsrec_ospf_router *ovs_ospf_router = NULL;
  u_int32_t ifindex = IFINDEX_INTERNAL;
  const char *data = NULL;
  int i = 0;

  assert (ovs_port && ifp);

  VLOG_DBG ("Old interface %s - ifindex: %u status: %u flags: %u mtu %u bandwidth %u kbits\n",
             ifp->name, ifp->ifindex, ifp->status, ifp->flags, ifp->mtu, ifp->bandwidth);

  if (ifp->ifindex == IFINDEX_INTERNAL)
    UNSET_FLAG (ifp->status, ZEBRA_INTERFACE_ACTIVE);
  else
    SET_FLAG (ifp->status, ZEBRA_INTERFACE_ACTIVE);

  if (ovs_port->n_interfaces > 0)
    ovs_interface = ovs_port->interfaces[0];

  if (ovs_interface) {
    if (ovs_interface->admin_state &&
        (strncmp (ovs_interface->admin_state, OVSREC_INTERFACE_ADMIN_STATE_UP,
                   sizeof (OVSREC_INTERFACE_ADMIN_STATE_UP)) == 0)) {
      SET_FLAG (ifp->flags, IFF_UP);

      if (ovs_interface->link_state &&
          (strncmp (ovs_interface->link_state, OVSREC_INTERFACE_LINK_STATE_UP,
                     sizeof (OVSREC_INTERFACE_LINK_STATE_UP)) == 0)) {
        SET_FLAG (ifp->flags, IFF_RUNNING);
      }
      else {
        UNSET_FLAG (ifp->flags, IFF_RUNNING);
      }
    }
    else {
      UNSET_FLAG (ifp->flags, IFF_UP|IFF_RUNNING);
    }

    if (ovs_interface->type &&
        (strncmp (ovs_interface->type, OVSREC_INTERFACE_TYPE_LOOPBACK,
                   sizeof (OVSREC_INTERFACE_TYPE_LOOPBACK)) == 0)) {
      SET_FLAG (ifp->flags, IFF_LOOPBACK);
    }
    else {
      UNSET_FLAG (ifp->flags, IFF_LOOPBACK);
    }

    SET_FLAG (ifp->flags, IFF_BROADCAST);

    data = smap_get (&(ovs_interface->hw_intf_info), INTERFACE_HW_INTF_INFO_MAP_MEDIA_TYPE);
    if (data && STR_EQ (data, INTERFACE_HW_INTF_INFO_MAP_HW_TYPE_POINT_TO_POINT)) {
      SET_FLAG (ifp->flags, IFF_POINTOPOINT);
    }
    else {
      UNSET_FLAG (ifp->flags, IFF_POINTOPOINT);
    }

    if (ovs_interface->mtu) {
      ifp->mtu = *(ovs_interface->mtu);
    }
    else {
      ifp->mtu = DEFAULT_ETH_MTU;
    }

    /* link_speed is bps and bandwidth is in kbps */
    if (ovs_interface->link_speed) {
      ifp->bandwidth = *(ovs_interface->link_speed) / 1024;
    }
  }

  VLOG_DBG ("New interface %s - ifindex: %u status: %u flags: %u mtu %u bandwidth %u kbits\n",
             ifp->name, ifp->ifindex, ifp->status, ifp->flags, ifp->mtu, ifp->bandwidth);
}

/* Interface/Port change related functions */
static int
ospf_interface_add_from_ovsdb (struct ovsdb_idl *idl, const struct ovsrec_vrf *ovs_vrf, const struct ovsrec_port *ovs_port)
{
  struct interface *ifp;
  struct ospf *ospf;
  const struct ovsrec_interface *ovs_interface = NULL;
  const struct ovsrec_ospf_router *ovs_ospf_router = NULL;
  u_int32_t ifindex = IFINDEX_INTERNAL;
  const char *data = NULL;
  int i = 0;

  ifp = if_get_by_name_len (ovs_port->name, strnlen(ovs_port->name, INTERFACE_NAMSIZ));

  if (ifp) {
    ifindex = if_nametoindex(ifp->name);
    if (ifindex == IFINDEX_INTERNAL) {
      VLOG_ERR ("Interface %s created - Failed to get ifindex\n", ifp->name);
      //return -1;
    }
    ifp->ifindex = ifindex;
    VLOG_DBG ("Interface %s created - ifindex:%u\n", ifp->name, ifp->ifindex);
  }
  else {
    VLOG_ERR ("Failed to create interface with ifname %s\n", ovs_port->name);
    return -1;
  }

  if_set_value_from_ovsdb (idl, ovs_port, ifp);

  ospf_interface_state_update_from_ovsdb (idl, ovs_port, ovs_interface, ifp);

  if (!OSPF_IF_PARAM_CONFIGURED (IF_DEF_PARAMS (ifp), type))
    {
      SET_IF_PARAM (IF_DEF_PARAMS (ifp), type);
      IF_DEF_PARAMS (ifp)->type = ospf_default_iftype(ifp);
    }

  for (i = 0 ; i < ovs_vrf->n_ospf_routers; i++) {
    ovs_ospf_router = ovs_vrf->value_ospf_routers[i];
    if (ovs_ospf_router) {
      if (ospf = ospf_lookup_by_instance (ovs_vrf->key_ospf_routers[i]))
        ospf_interface_add (ospf, ifp);
    }
  }

  return 0;
}

static int
ospf_interface_delete_from_ovsdb (struct ovsdb_idl *idl, const struct ovsrec_vrf *ovs_vrf, struct interface * ifp)
{
  const struct ovsrec_ospf_router *ovs_ospf_router = NULL;
  struct ospf *ospf;
  int i;

  for (i = 0 ; i < ovs_vrf->n_ospf_routers; i++) {
    ovs_ospf_router = ovs_vrf->value_ospf_routers[i];
    if (ovs_ospf_router) {
      if (ospf = ospf_lookup_by_instance (ovs_vrf->key_ospf_routers[i]))
        ospf_interface_delete (ospf, ifp);
    }
  }

  return 0;
}
static void
ospf_interface_state_update_from_ovsdb (struct ovsdb_idl *idl, const struct ovsrec_port *ovs_port,
                              const struct ovsrec_interface *ovs_interface, struct interface *ifp)
{
  assert (ovs_port);

  if (!ovs_interface) {
    if (ovs_port->n_interfaces > 0)
      ovs_interface = ovs_port->interfaces[0];
    if (!ovs_interface)
      return;
  }

  if (!ifp) {
    ifp = if_lookup_by_name_len (ovs_port->name, strnlen(ovs_port->name, INTERFACE_NAMSIZ));
    if (!ifp || ifp->ifindex == IFINDEX_INTERNAL)
      return;
  }

  if ((OVSREC_IDL_IS_COLUMN_MODIFIED (ovsrec_interface_col_admin_state, idl_seqno) ||
       OVSREC_IDL_IS_COLUMN_MODIFIED (ovsrec_interface_col_link_state, idl_seqno))) {
    if (is_ovs_port_state_up (idl, ovs_port, ovs_interface, ifp)) {
      VLOG_DBG ("interface %s state UP\n", ifp->name);
      ospf_interface_state_up (idl, ovs_port, ifp);
    }
    else {
      VLOG_DBG ("interface %s state DOWN\n", ifp->name);
      ospf_interface_state_down (idl, ovs_port, ifp);
    }
  }
}

static int
ospf_interface_update_from_ovsdb (struct ovsdb_idl *idl, const struct ovsrec_vrf *ovs_vrf,
                                  const struct ovsrec_port *ovs_port)
{
  struct interface *ifp;
  struct ospf *ospf;
  const struct ovsrec_ospf_router *ovs_ospf_router = NULL;
  u_int32_t ifindex = IFINDEX_INTERNAL;
  const char *data = NULL;
  int i = 0;
  struct connected *ifc;
  struct listnode *node, *nextnode;
  struct prefix p;
  struct prefix *pfxlist = NULL, *pfx = NULL;

  ifp = if_lookup_by_name_len (ovs_port->name, strnlen(ovs_port->name, INTERFACE_NAMSIZ));

  if (ifp) {
    if (ifp->ifindex == IFINDEX_INTERNAL) {
      VLOG_ERR ("Interface %s is present - ifindex is %u\n", ifp->name, ifp->ifindex);
      return -1;
    }
    VLOG_INFO ("Interface %s present - ifindex:%u\n", ifp->name, ifp->ifindex);
  }
  else {
    VLOG_ERR ("No interface present with ifname %s\n", ovs_port->name);
    return -1;
  }

  ospf_interface_state_update_from_ovsdb (idl, ovs_port, NULL, ifp);

  if (OVSREC_IDL_IS_COLUMN_MODIFIED (ovsrec_port_col_ip4_address, idl_seqno)) {
    if (ovs_port->ip4_address) {
      if (ovs_port->ip4_address && str2prefix (ovs_port->ip4_address, &p)) {
        if (ifc = connected_lookup_address (ifp, p.u.prefix4)) {
          if (CHECK_FLAG (ifc->flags, ZEBRA_IFA_SECONDARY)) {
            ospf_interface_address_delete (ifp, ifc);
            UNSET_FLAG (ifc->flags, ZEBRA_IFA_SECONDARY);
            ospf_interface_address_add (ifp, ifc);
          }
        }
        else {
          /* Primary ipv4 address is added */
          ifc = connected_add_by_prefix (ifp, &p, NULL);
          ospf_interface_address_add (ifp, ifc);
        }
      }
    }
    else {
      /* Primary ipv4 address is deleted */
      for (node = listhead (ifp->connected); node; node = nextnode) {
        ifc = listgetdata (node);
        nextnode = node->next;
        if (ifc && !CHECK_FLAG (ifc->flags, ZEBRA_IFA_SECONDARY)) {
          VLOG_DBG ("ifp %s: primary addr delete %s\n", ifp->name, ovs_port->ip4_address);
          listnode_delete (ifp->connected, ifc);
          ospf_interface_address_delete (ifp, ifc);
        }
      }
    }
  }

  if (OVSREC_IDL_IS_COLUMN_MODIFIED (ovsrec_port_col_ip4_address_secondary, idl_seqno)) {
    pfxlist = XCALLOC (MTYPE_PREFIX, sizeof(struct prefix) * ovs_port->n_ip4_address_secondary);
    if (!pfxlist) {
      VLOG_ERR ("Memory alloc Error\n");
      return -1;
    }
    for (i = 0, pfx = pfxlist; i < ovs_port->n_ip4_address_secondary; i++, pfx++) {
      if (ovs_port->ip4_address_secondary[i] && str2prefix (ovs_port->ip4_address_secondary[i], pfx)) {
        if (ifc = connected_lookup_address (ifp, pfx->u.prefix4)) {
          if (!CHECK_FLAG (ifc->flags, ZEBRA_IFA_SECONDARY)) {
            ospf_interface_address_delete (ifp, ifc);
            SET_FLAG (ifc->flags, ZEBRA_IFA_SECONDARY);
            ospf_interface_address_add (ifp, ifc);
          }
        }
        else {
          /* Secondary ipv4 address is added */
          ifc = connected_add_by_prefix (ifp, pfx, NULL);
          SET_FLAG (ifc->flags, ZEBRA_IFA_SECONDARY);
          ospf_interface_address_add (ifp, ifc);
        }
      }
    }

    /* If any Secondary ipv4 address is deleted */
    for (node = listhead (ifp->connected); node; node = nextnode) {
      ifc = listgetdata (node);
      nextnode = node->next;
      if (ifc && CHECK_FLAG (ifc->flags, ZEBRA_IFA_SECONDARY)) {
        for (i = 0, pfx = pfxlist; i < ovs_port->n_ip4_address_secondary; i++, pfx++) {
          if (prefix_same (ifc->address, pfx)) {
            VLOG_DBG ("ifp %s: secondary addr delete %s\n", ifp->name, ovs_port->ip4_address_secondary[i]);
            listnode_delete (ifp->connected, ifc);
            ospf_interface_address_delete (ifp, ifc);
          }
        }
      }
    }

    XFREE (MTYPE_PREFIX, pfxlist);

  }

  return 0;
}
