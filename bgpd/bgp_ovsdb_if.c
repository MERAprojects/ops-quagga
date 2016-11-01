/* bgp daemon ovsdb integration.
 *
 * Hewlett-Packard Company Confidential (C)
 * Copyright 2015 Hewlett-Packard Development Company, L.P.
 *
 * (c) Copyright 2015 Hewlett Packard Enterprise Development LP.
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
 * File: bgp_ovsdb_if.c
 *
 * Purpose: Main file for integrating bgpd with ovsdb and ovs poll-loop.
 */

#include <zebra.h>

#include <lib/version.h>
#include "getopt.h"
#include "command.h"
#include "thread.h"
#include "memory.h"
#include "bgpd/bgpd.h"
#include "bgpd/bgp_debug.h"

/* OVS headers */
#include "config.h"
#include "command-line.h"
#include "daemon.h"
#include "dirs.h"
#include "dummy.h"
#include "fatal-signal.h"
#include "poll-loop.h"
#include "ovs/stream.h"
#include "timeval.h"
#include "unixctl.h"
#include "openvswitch/vlog.h"
#include "vswitch-idl.h"
#include "coverage.h"
#include "openswitch-idl.h"
#include "prefix.h"

#include "bgpd/bgp_ovsdb_if.h"
#include "bgpd/bgp_table.h"
#include "bgpd/bgp_route.h"
#include "bgpd/bgp_community.h"
#include "bgpd/bgp_ecommunity.h"
#include "bgpd/bgp_nexthop.h"
#include "bgpd/bgp_aspath.h"
#include "bgpd/bgp_advertise.h"
#include "linklist.h"
#include "dynamic-string.h"
#include "sockunion.h"
#include  <diag_dump.h>
#include "bgpd/bgp_fsm.h"
#include "bgp_vty.h"
#include "bgp_backend_functions.h"
#include "bgp_ovsdb_route.h"
#include "bgp_zebra.h"
#include "bgp_mpath.h"

/*
 * Local structure to hold the master thread
 * and counters for read/write callbacks
 */
typedef struct bgp_ovsdb_t_ {
    int enabled;
    struct thread_master *master;
    unsigned int read_cb_count;
    unsigned int write_cb_count;
} bgp_ovsdb_t;

static bgp_ovsdb_t glob_bgp_ovs;
#define MAX_BUF_LEN 10
#define BUF_LEN 16000
#define MAX_ERR_STR_LEN 256
#define PEER_DOWN_TRIGGER_LEN 100

COVERAGE_DEFINE(bgp_ovsdb_cnt);
VLOG_DEFINE_THIS_MODULE(bgp_ovsdb_if);

struct ovsdb_idl *idl;
unsigned int idl_seqno;
static char *appctl_path = NULL;
static struct unixctl_server *appctl;
static int system_configured = false;
static int diag_buffer_len = BUF_LEN;
static struct bgp_master *bgpmaster;
/*
 * Global System ECMP status affects maxpath config
 * Keep a local ECMP status to update when needed
 * Default ECMP status is true
 */
static boolean sys_ecmp_status = true;
boolean exiting = false;
static int bgp_ovspoll_enqueue (bgp_ovsdb_t *bovs_g);
static int bovs_cb (struct thread *thread);
static void bgpd_dump(char *buf, int len);
static void bgpd_diag_dump_basic_cb(const char *feature , char **buf);

extern struct in_addr router_id_zebra;
/* Prototypes */
int
modify_bgp_router_id_config (struct bgp *bgp_cfg,
    const struct ovsrec_bgp_router *bgp_mod_row);
int
modify_bgp_network_config (struct bgp *bgp_cfg,
    const struct ovsrec_bgp_router *bgp_mod_row);
int
modify_bgp_maxpaths_config (struct bgp *bgp_cfg,
    const struct ovsrec_bgp_router *bgp_mod_row);
int
modify_bgp_timers_config (struct bgp *bgp_cfg,
    const struct ovsrec_bgp_router *bgp_mod_row);
int
bgp_static_route_addition (struct bgp *bgp_cfg,
    const struct ovsrec_bgp_router *bgp_mod_row);
int
bgp_static_route_deletion (struct bgp *bgp_cfg,
                           const struct ovsrec_bgp_router *bgp_mod_row);

/*
 * ovs appctl dump function for this daemon
 * This is useful for debugging
 */
static void
bgp_unixctl_dump (struct unixctl_conn *conn, int argc OVS_UNUSED,
    const char *argv[] OVS_UNUSED, void *aux OVS_UNUSED)
{
    char err_str[MAX_ERR_STR_LEN];
    char *buf = xcalloc(1, diag_buffer_len);
    if(!buf) {
        snprintf(err_str,sizeof(err_str),
                 "bpg daemon failed to allocate %d bytes", diag_buffer_len);
        unixctl_command_reply(conn, err_str);
    } else {
        bgpd_dump(buf,diag_buffer_len);
        unixctl_command_reply(conn, buf);
        free(buf);
    }
}
static void
bgp_diag_buff_set(struct unixctl_conn *conn, int argc OVS_UNUSED,
    const char *argv[] OVS_UNUSED, void *aux OVS_UNUSED)
{
    char buf[256];
    int tmp = diag_buffer_len;
    diag_buffer_len = atoi(argv[1]);
    snprintf(buf, sizeof(buf), "Set diag buffer size:\n"
             "  Old: %d bytes\n  New: %d bytes\n", tmp, diag_buffer_len);
    unixctl_command_reply(conn, buf);

}
boolean get_global_ecmp_status()
{
   return sys_ecmp_status;
}

/*
 * If BGP Router ID is not configured then this function updates
 * the BGP router id from VRF table active_router_id column.
 */
static void
bgp_update_active_router_id (const struct ovsrec_bgp_router *bgp_router_row,
                             char *active_router_id)
{
    struct ovsdb_idl_txn *bgp_router_txn=NULL;
    enum ovsdb_idl_txn_status status;
    struct prefix active_router_id_prefix;
    struct listnode *node, *nnode;
    struct bgp *bgp = NULL;

    VLOG_DBG("BGP received active_router_id update: %s, \
            Current value of BGP router_id: %s",
            active_router_id, bgp_router_row->router_id);
    str2prefix(active_router_id, &active_router_id_prefix);
    router_id_zebra = active_router_id_prefix.u.prefix4;

    for (ALL_LIST_ELEMENTS (bgpmaster->bgp, node, nnode, bgp)){
        if (bgp->router_id_static.s_addr == 0){
            bgp_router_id_set (bgp, &active_router_id_prefix.u.prefix4);
            VLOG_INFO("Setting active_router_id for BGP ASN: %d", bgp->as);
            break;
        }
    }
}

/*
 * From bgp router row in db to get bgp asn #
 */
static int
ovsdb_bgp_router_from_row_to_asn (struct ovsdb_idl *idl,
    const struct ovsrec_bgp_router *ovs_bgp)
{
    int j;
    const struct ovsrec_vrf *ovs_vrf;

    OVSREC_VRF_FOR_EACH(ovs_vrf, idl) {
        for (j = 0; j < ovs_vrf->n_bgp_routers; j++) {
            if (ovs_bgp == ovs_vrf->value_bgp_routers[j]) {
                return ovs_vrf->key_bgp_routers[j];
            }
        }
    }
    return -1;
}


/*
 * From bgp nbr row in db to get peer name, a by product is that
 * it also returns its bgp asn#
 */
static char *
ovsdb_nbr_from_row_to_peer_name (struct ovsdb_idl *idl,
    const struct ovsrec_bgp_neighbor *ovs_nbr, int64_t *asn)
{
    int i, j;
    const struct ovsrec_vrf *ovs_vrf;
    const struct ovsrec_bgp_router *ovs_bgp;

    OVSREC_VRF_FOR_EACH(ovs_vrf, idl) {
        for (i = 0; i < ovs_vrf->n_bgp_routers; i++) {
            if (asn)
                *asn = ovs_vrf->key_bgp_routers[i];
            ovs_bgp = ovs_vrf->value_bgp_routers[i];
            for (j = 0; j < ovs_bgp->n_bgp_neighbors; j++) {
                if (ovs_nbr == ovs_bgp->value_bgp_neighbors[j]) {
                    return ovs_bgp->key_bgp_neighbors[j];
                }
            }
        }
    }
    return NULL;
}

static bool
object_is_peer (const struct ovsrec_bgp_neighbor *db_bgpn_p)
{
    return (db_bgpn_p->n_is_peer_group == 0) || !(db_bgpn_p->is_peer_group[0]);
}

static bool
object_is_peer_group (const struct ovsrec_bgp_neighbor *db_bgpn_p)
{
    return (db_bgpn_p->n_is_peer_group > 0) && db_bgpn_p->is_peer_group[0];
}

static void
bgp_policy_ovsdb_init (struct ovsdb_idl *idl)
{

    ovsdb_idl_add_table(idl, &ovsrec_table_bgp_community_filter);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_community_filter_col_name);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_community_filter_col_type);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_community_filter_col_permit);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_community_filter_col_deny);

    ovsdb_idl_add_table(idl, &ovsrec_table_prefix_list);
    ovsdb_idl_add_column(idl, &ovsrec_prefix_list_col_name);
    ovsdb_idl_add_column(idl, &ovsrec_prefix_list_col_prefix_list_entries);
    ovsdb_idl_add_column(idl, &ovsrec_prefix_list_col_description);

    ovsdb_idl_add_table(idl, &ovsrec_table_prefix_list_entry);
    ovsdb_idl_add_column(idl, &ovsrec_prefix_list_entry_col_action);
    ovsdb_idl_add_column(idl, &ovsrec_prefix_list_entry_col_prefix);
    ovsdb_idl_add_column(idl, &ovsrec_prefix_list_entry_col_le);
    ovsdb_idl_add_column(idl, &ovsrec_prefix_list_entry_col_ge);

    ovsdb_idl_add_table(idl, &ovsrec_table_route_map);
    ovsdb_idl_add_column(idl, &ovsrec_route_map_col_name);
    ovsdb_idl_add_column(idl, &ovsrec_route_map_col_route_map_entries);

    ovsdb_idl_add_table(idl, &ovsrec_table_route_map_entry);
    ovsdb_idl_add_column(idl, &ovsrec_route_map_entry_col_action);
    ovsdb_idl_add_column(idl, &ovsrec_route_map_entry_col_description);
    ovsdb_idl_add_column(idl, &ovsrec_route_map_entry_col_exitpolicy);
    ovsdb_idl_add_column(idl, &ovsrec_route_map_entry_col_goto_target);
    ovsdb_idl_add_column(idl, &ovsrec_route_map_entry_col_call);
    ovsdb_idl_add_column(idl, &ovsrec_route_map_entry_col_match);
    ovsdb_idl_add_column(idl, &ovsrec_route_map_entry_col_set);

    ovsdb_idl_add_table(idl, &ovsrec_table_bgp_aspath_filter);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_aspath_filter_col_name);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_aspath_filter_col_permit);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_aspath_filter_col_deny);
}

static void
bgp_ovsdb_tables_init (struct ovsdb_idl *idl)
{
    /* VRF Table */
    ovsdb_idl_add_table(idl, &ovsrec_table_vrf);
    ovsdb_idl_add_column(idl, &ovsrec_vrf_col_name);
    ovsdb_idl_add_column(idl, &ovsrec_vrf_col_bgp_routers);
    ovsdb_idl_add_column(idl, &ovsrec_vrf_col_active_router_id);

    /* BGP router table */
    ovsdb_idl_add_table(idl, &ovsrec_table_bgp_router);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_router_id);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_networks);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_maximum_paths);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_timers);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_always_compare_med);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_deterministic_med);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_gr_stale_timer);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_bgp_neighbors);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_other_config);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_status);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_external_ids);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_fast_external_failover);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_log_neighbor_changes);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_redistribute);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_router_col_redistribute_route_map);
    /* BGP neighbor table */
    ovsdb_idl_add_table(idl, &ovsrec_table_bgp_neighbor);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_is_peer_group);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_description);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_shutdown);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_bgp_peer_group);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_local_interface);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_remote_as);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_bfd_fallover_enable);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_bfd_session);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_allow_as_in);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_local_as);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_weight);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_tcp_port_number);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_advertisement_interval);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_maximum_prefix_limit);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_inbound_soft_reconfiguration);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_remove_private_as);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_passive);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_password);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_timers);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_route_maps);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_prefix_lists);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_aspath_filters);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_statistics);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_status);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_external_ids);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_other_config);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_ebgp_multihop);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_ttl_security_hops);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_neighbor_col_update_source);

    /* BGP policy */
    bgp_policy_ovsdb_init(idl);

    /* Global RIB table */
    ovsdb_idl_add_table(idl, &ovsrec_table_route);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_prefix);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_from);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_nexthops);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_address_family);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_sub_address_family);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_selected);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_distance);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_metric);
    ovsdb_idl_add_column(idl, &ovsrec_route_col_vrf);

    /* Global nexthop table */
    ovsdb_idl_add_table(idl, &ovsrec_table_nexthop);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_ip_address);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_selected);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_weight);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_status);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_other_config);
    ovsdb_idl_add_column(idl, &ovsrec_nexthop_col_external_ids);

    /* BGP RIB table */
    ovsdb_idl_add_table(idl, &ovsrec_table_bgp_route);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_route_col_prefix);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_route_col_bgp_nexthops);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_route_col_address_family);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_route_col_sub_address_family);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_route_col_distance);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_route_col_metric);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_route_col_vrf);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_route_col_path_attributes);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_route_col_peer);

    /* BGP Nexthop table */
    ovsdb_idl_add_table(idl, &ovsrec_table_bgp_nexthop);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_nexthop_col_ip_address);
    ovsdb_idl_add_column(idl, &ovsrec_bgp_nexthop_col_type);

    /* BFD Session table */
    ovsdb_idl_add_table(idl, &ovsrec_table_bfd_session);
    ovsdb_idl_add_column(idl, &ovsrec_bfd_session_col_enable);
    ovsdb_idl_add_column(idl, &ovsrec_bfd_session_col_bfd_dst_ip);
    ovsdb_idl_add_column(idl, &ovsrec_bfd_session_col_bfd_src_ip);
    ovsdb_idl_add_column(idl, &ovsrec_bfd_session_col_min_tx);
    ovsdb_idl_add_column(idl, &ovsrec_bfd_session_col_min_rx);
    ovsdb_idl_add_column(idl, &ovsrec_bfd_session_col_decay_min_rx);
    ovsdb_idl_add_column(idl, &ovsrec_bfd_session_col_state);
    ovsdb_idl_track_add_column(idl, &ovsrec_bfd_session_col_state);
    ovsdb_idl_add_column(idl, &ovsrec_bfd_session_col_from);
}

/*
 * Create a connection to the OVSDB at db_path and create a dB cache
 * for this daemon.
 */
static void
ovsdb_init (const char *db_path)
{
    /* Initialize IDL through a new connection to the dB. */
    idl = ovsdb_idl_create(db_path, &ovsrec_idl_class, false, true);
    idl_seqno = ovsdb_idl_get_seqno(idl);
    ovsdb_idl_set_lock(idl, "OpenSwitch_bgp");

    /* Cache OpenVSwitch table */
    ovsdb_idl_add_table(idl, &ovsrec_table_system);

    ovsdb_idl_add_column(idl, &ovsrec_system_col_cur_cfg);
    ovsdb_idl_add_column(idl, &ovsrec_system_col_hostname);
    ovsdb_idl_add_column(idl, &ovsrec_system_col_ecmp_config);

    /* BGP tables */
    bgp_ovsdb_tables_init(idl);

    INIT_DIAG_DUMP_BASIC(bgpd_diag_dump_basic_cb);
    /* Register ovs-appctl commands for this daemon. */
    unixctl_command_register("bgpd/dump", "", 0, 0, bgp_unixctl_dump, NULL);
    unixctl_command_register("bgpd/diag", "buffer size", 1, 1, bgp_diag_buff_set, NULL);
}

/* Show BGP memory usage information */
static void
bgp_dump_memory (struct ds *ds)
{
    char memstrbuf[MTYPE_MEMSTR_LEN];
    unsigned long count;

    if(!ds) {
        VLOG_ERR("Invalid Entry\n");
        return;
    }

    /* RIB related usage stats */
    count = mtype_stats_alloc (MTYPE_BGP_NODE);
    ds_put_format (ds, "%ld RIB nodes, using %s of memory\n", count,
                   mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                 count * sizeof (struct bgp_node)));

    count = mtype_stats_alloc (MTYPE_BGP_ROUTE);
    ds_put_format (ds, "%ld BGP routes, using %s of memory\n", count,
                   mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                 count * sizeof (struct bgp_info)));

    count = mtype_stats_alloc (MTYPE_BGP_ROUTE_EXTRA);
    if (count > 0)
        ds_put_format (ds, "%ld BGP route ancillaries, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof (struct bgp_info_extra)));

    count = mtype_stats_alloc (MTYPE_BGP_STATIC);
    if (count > 0)
        ds_put_format (ds, "%ld Static routes, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof (struct bgp_static)));

    /* Adj-In/Out */
    count = mtype_stats_alloc (MTYPE_BGP_ADJ_IN);
    if (count > 0)
        ds_put_format (ds, "%ld Adj-In entries, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof (struct bgp_adj_in)));

    count = mtype_stats_alloc (MTYPE_BGP_ADJ_OUT);
    if (count > 0)
        ds_put_format (ds, "%ld Adj-Out entries, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof (struct bgp_adj_out)));

    count = mtype_stats_alloc (MTYPE_BGP_NEXTHOP_CACHE);
    if (count > 0)
        ds_put_format (ds, "%ld Nexthop cache entries, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof (struct bgp_nexthop_cache)));

    /* Attributes */
    count = attr_count();
    if (count > 0)
        ds_put_format (ds, "%ld BGP attributes, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof(struct attr)));
    count = mtype_stats_alloc (MTYPE_ATTR_EXTRA);
    if (count > 0)
        ds_put_format (ds, "%ld BGP extra attributes, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof(struct attr_extra)));

    count = attr_unknown_count();
    if (count > 0)
        ds_put_format (ds, "%ld unknown attributes\n", count);

    /* AS_PATH attributes */
    count = aspath_count ();
    if (count > 0)
        ds_put_format (ds, "%ld BGP AS-PATH entries, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof (struct aspath)));

    count = mtype_stats_alloc (MTYPE_AS_SEG);
    if (count > 0)
        ds_put_format (ds, "%ld BGP AS-PATH segments, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof (struct assegment)));

    /* Other attributes */
    count = community_count ();
    if (count > 0)
        ds_put_format (ds, "%ld BGP community entries, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof (struct community)));
    count = mtype_stats_alloc (MTYPE_ECOMMUNITY);
    if (count > 0)
        ds_put_format (ds,
                       "%ld BGP ecommunity entries, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof (struct ecommunity)));

    count = mtype_stats_alloc (MTYPE_CLUSTER);
    if (count > 0)
        ds_put_format (ds,
                       "%ld Cluster lists, using %s of memory%s",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof (struct cluster_list)));

    /* Peer related usage */
    count = mtype_stats_alloc (MTYPE_BGP_PEER);
    ds_put_format (ds, "%ld peers, using %s of memory\n", count,
                   mtype_memstr (memstrbuf, sizeof (memstrbuf),
                   count * sizeof (struct peer)));

    count = mtype_stats_alloc (MTYPE_PEER_GROUP);
    if (count > 0)
        ds_put_format (ds, "%ld peer groups, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof (struct peer_group)));

    /* Other */
    count = mtype_stats_alloc (MTYPE_HASH);
    if (count > 0)
        ds_put_format (ds, "%ld hash tables, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof (struct hash)));
    count = mtype_stats_alloc (MTYPE_HASH_BACKET);
    if (count > 0)
        ds_put_format (ds, "%ld hash buckets, using %s of memory\n",
                       count,
                       mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                     count * sizeof (struct hash_backet)));
    ds_put_format (ds, "\n");
}

/* Show BGP peer's summary information. */
static void
bgp_dump_summary (struct ds *ds, struct bgp *bgp, int afi, int safi)
{
    struct peer *peer;
    struct listnode *node, *nnode;
    char timebuf[BGP_UPTIME_LEN];
    unsigned int count = 0;
    int n;
    if(!bgp || !ds) {
        VLOG_ERR("Invalid Entry\n");
        return;
    }
    /* Header string for each address family. */
    static char header[] = "Neighbor           AS MsgRcvd MsgSent"
                           "   TblVer  InQ OutQ Up/Down  State";

    for (ALL_LIST_ELEMENTS (bgp->peer, node, nnode, peer)) {
       if (peer->afc[afi][safi]) {
           if (!count) {
               unsigned long ents;

               ds_put_format(ds,
                             "BGP router identifier %s, local AS number %u\n"
                             "RIB table counts %ld\n"
                             "Peers %ld\n",
                             inet_ntoa (bgp->router_id), bgp->as,
                             bgp_table_count (bgp->rib[afi][safi]),
                             listcount (bgp->peer));

               if((ents = listcount (bgp->rsclient))) {
                   ds_put_format(ds, "RS-Client peers %ld\n", ents);
               }
               if((ents = listcount (bgp->group))) {
                   ds_put_format(ds, "Peer groups %ld\n", ents);
               }
               ds_put_format(ds, "\n%s\n", header);
           }
           count++;

           ds_put_format(ds, "%s", peer->host);
           n = 16 - strlen(peer->host);
           if (n < 1) {
               ds_put_format(ds, "\n%*s", 16, " ");
           } else {
               ds_put_format(ds, "%*s", n, " ");
           }
           ds_put_format(ds, "%5u %7d %7d %8d %4d %4lu ",
                           peer->as, peer->open_in +
                           peer->update_in + peer->keepalive_in +
                           peer->notify_in + peer->refresh_in +
                           peer->dynamic_cap_in, peer->open_out +
                           peer->update_out + peer->keepalive_out +
                           peer->notify_out + peer->refresh_out +
                           peer->dynamic_cap_out,
                           0, 0, (unsigned long) peer->obuf->count);

           ds_put_format(ds, "%8s",
                 peer_uptime (peer->uptime, timebuf, BGP_UPTIME_LEN));

           ds_put_format(ds,  " %-11s\n",
                           LOOKUP(bgp_status_msg, peer->status));
        }
    } /* bgp peer loop */

    if (count) {
        ds_put_format(ds, "\nTotal number of neighbors "
                        "%d\n", count);
    } else {
        ds_put_format(ds,  "No %s neighbor is configured"
                        "\n\n", afi == AFI_IP ? "IPv4" : "IPv6");
    }
}

static void
bgp_dump_peer(struct ds *ds, struct peer *p)
{
    struct bgp *bgp;
    char buf1[INET6_ADDRSTRLEN];
    char timebuf[BGP_UPTIME_LEN];
    afi_t afi;
    safi_t safi;
    char peer_down_reason[PEER_DOWN_TRIGGER_LEN] = {0};
    if(!p || !ds) {
        VLOG_ERR("Invalid Entry\n");
        return;
    }
    bgp = p->bgp;

    /* Configured IP address. */

    ds_put_format(ds, "BGP neighbor is %s, remote AS %u, local AS %u%s%s, "
                    "%s link\n", p->host, p->as,
                    p->change_local_as ? p->change_local_as : p->local_as,
                    CHECK_FLAG (p->flags, PEER_FLAG_LOCAL_AS_NO_PREPEND) ?
                    " no-prepend" : "",
                    CHECK_FLAG (p->flags, PEER_FLAG_LOCAL_AS_REPLACE_AS) ?
                    " replace-as" : "", p->as == p->local_as ?
                    "internal" : "external");

    ds_put_format(ds, "  Remote router ID %s\n",
                    inet_ntop (AF_INET, &p->remote_id, buf1, BUFSIZ));

    /* Peer-group */
    if (p->group) {
        ds_put_format(ds, " Member of peer-group %s "
                        "for session parameters\n", p->group->name);
    }

    /* Status. */
    ds_put_format(ds, "  BGP state = %s",
                    LOOKUP (bgp_status_msg, p->status));
    if (p->status == Established) {
        ds_put_format(ds, ", up for %8s\n",
                        peer_uptime (p->uptime, timebuf, BGP_UPTIME_LEN));
    }
    else if (p->status == Active) {
        if(CHECK_FLAG (p->flags, PEER_FLAG_PASSIVE)) {
           ds_put_format(ds, " (passive)\n");
        } else if(CHECK_FLAG (p->sflags, PEER_STATUS_NSF_WAIT)) {
           ds_put_format(ds, " (NSF passive)\n");
        }
    } else {
        ds_put_format(ds, "\n");
    }

    /* read timer */
    ds_put_format(ds, "  Last read %s",
                    peer_uptime (p->readtime, timebuf, BGP_UPTIME_LEN));

    /* Configured timer values. */
    ds_put_format(ds, ", hold time is %d,"
                    " keepalive interval is %d seconds\n",
                    p->v_holdtime, p->v_keepalive);

    if (CHECK_FLAG (p->config, PEER_CONFIG_TIMER)) {
        ds_put_format(ds, "  Configured hold time is %d"
                        ", keepalive interval is %d seconds\n", p->holdtime,
                        p->keepalive);
    }

    /* Packet counts. */
    ds_put_format(ds,
                    "  Message statistics:\n"
                    "    Inq depth is 0\n"
                    "    Outq depth is %lu\n"
                    "    Reset time: %d\n"
                    "    Dropped: %d\n"
                    "                         Sent       Rcvd\n"
                    "    Dynamic:       %10d %10d\n"
                    "    Opens:         %10d %10d\n"
                    "    Notifications: %10d %10d\n"
                    "    Updates:       %10d %10d\n"
                    "    Keepalives:    %10d %10d\n"
                    "    Route Refresh: %10d %10d\n"
                    "    Capability:    %10d %10d\n"
                    "    Total:         %10d %10d\n\n",
                    (unsigned long) p->obuf->count, p->resettime, p->dropped,
                    p->dynamic_cap_out, p->dynamic_cap_in,
                    p->open_out, p->open_in,
                    p->notify_out, p->notify_in,
                    p->update_out, p->update_in,
                    p->keepalive_out, p->keepalive_in,
                    p->refresh_out, p->refresh_in,
                    p->dynamic_cap_out, p->dynamic_cap_in,
                    p->open_out + p->notify_out +
                    p->update_out + p->keepalive_out + p->refresh_out +
                    p->dynamic_cap_out, p->open_in + p->notify_in +
                    p->update_in + p->keepalive_in + p->refresh_in +
                    p->dynamic_cap_in);

    /* Default weight */
    if (CHECK_FLAG (p->config, PEER_CONFIG_WEIGHT)) {
        ds_put_format(ds, "  Default weight %d\n",
                        p->weight);
    }
    ds_put_format(ds, "  Connections established: %d\n",
                    p->established);

    if (!p->dropped) {
        ds_put_format(ds, "  Last reset never\n");
    } else {
        snprintf(peer_down_reason,  PEER_DOWN_TRIGGER_LEN, "%s",
                 peer_down_str[(int) p->last_reset]);
        if ((peer_down_reason[0] == '\0') ||
             (!p->su_local)) {
            p->last_reset = LOCAL_INTERFACE_DOWN;
        }
        ds_put_format(ds, "  Last reset %s, due to %s\n",
        peer_uptime (p->resettime, timebuf, BGP_UPTIME_LEN),
        peer_down_str[(int) p->last_reset]);
    }

    if(CHECK_FLAG (p->sflags, PEER_STATUS_PREFIX_OVERFLOW)) {
        ds_put_format(ds, "  Peer had exceeded the "
                        "max. no. of prefixes configured.\n");

        if (p->t_pmax_restart) {
            ds_put_format(ds, "  Reduce the no. of prefix "
                           "from %s, will restart in %ld seconds\n", p->host,
                           thread_timer_remain_second (p->t_pmax_restart));
        } else {
            ds_put_format(ds, "  Reduce the no. of prefix "
                           ", clear ip bgp %s to restore peering\n", p->host);
        }
    }

    /* Local address. */
    if (p->su_local) {
        ds_put_format(ds, "  Local host: %s, Local port: %d\n",
                        sockunion2str (p->su_local, buf1, SU_ADDRSTRLEN),
                        ntohs (p->su_local->sin.sin_port));
    }

    /* Remote address. */
    if (p->su_remote) {
        ds_put_format(ds, "  Foreign host: %s, Foreign port:"
                     " %d\n", sockunion2str(p->su_remote, buf1, SU_ADDRSTRLEN),
                     ntohs (p->su_remote->sin.sin_port));
    }
}

static void
bgpd_dump(char *buf, int buf_size)
{
    struct ds ds = DS_EMPTY_INITIALIZER;
    struct bgp *bgp;
    struct listnode *node, *nnode;
    struct peer *peer;
    int afi, safi, err_len, len = 0;

    char *err = "\nTruncated due to data exceeds buffer size";
    char *promt = "\nIncrease buffer size using "
                  "'ovs-appctl -t ops-bgpd bgpd/diag newsize'\n";
    bgp = bgp_get_default ();

    if (bgp) {
        bgp_dump_memory(&ds);
        bgp_dump_summary(&ds, bgp, AFI_IP, SAFI_UNICAST);
        for (ALL_LIST_ELEMENTS (bgp->peer, node, nnode, peer))
        {
            bgp_dump_peer(&ds, peer);
        }
        len = snprintf(buf, buf_size, ds_cstr(&ds));
        /* Large data > buffer size: log err, truncate data,
         * promt user to increase size */
        if(len > buf_size) {
            VLOG_ERR("diag-dump: No more space on buffer to dump."
                     "  Data size: %d, buffer size: %d, exceeds: %d\n",
                     len, buf_size, len - buf_size);
            err_len = strlen(err) + strlen(promt) + 35;
            if(buf_size > err_len) {
                snprintf(&buf[buf_size - err_len-1], err_len, "%s\nData %d "
                        "bytes, Buffer %d bytes%s", err, len, buf_size, promt);
            }
        }
    }
    ds_destroy(&ds);
}

/*
 * Function       : bgpd_diag_dump_basic_cb
 * Responsibility : callback handler function for diagnostic dump basic
 *                  it allocates memory as per requirment and populates data.
 *                  INIT_DIAG_DUMP_BASIC will free allocated memory.
 * Parameters     : feature name string, buffer ptr
 * Returns        : void
 */

static void
bgpd_diag_dump_basic_cb(const char *feature , char **buf)
{
     if (!buf)
         return;
     *buf =  xcalloc(1, diag_buffer_len);

     if (*buf) {
         bgpd_dump(*buf, diag_buffer_len);
         /* populate basic diagnostic data to buffer  */
         VLOG_DBG("basic diag-dump data populated for feature %s",
                  feature);
     }else{
         VLOG_ERR("Memory allocation failed for feature %s , %d bytes",
                  feature , diag_buffer_len);
     }
     return;
}

static void
ops_bgp_exit (struct unixctl_conn *conn, int argc OVS_UNUSED,
    const char *argv[] OVS_UNUSED, void *exiting_)
{
    boolean *exiting = exiting_;

    *exiting = true;
    unixctl_command_reply(conn, NULL);
}

static void
usage (void)
{
    printf("%s: OpenSwitch bgp daemon\n"
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

/*
 * OPS_TODO: Need to merge this parse function with the main parse function
 * in bgp_main to avoid issues.
 */
static char *
bgp_ovsdb_parse_options (int argc, char *argv[], char **unixctl_pathp)
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

/*
 * Setup bgp to connect with ovsdb and daemonize. This daemonize is used
 * over the daemonize in the main function to keep the behavior consistent
 * with the other daemons in the OpenSwitch system
 */
void bgp_ovsdb_init (int argc, char *argv[])
{
    int retval;
    char *ovsdb_sock;

    memset(&glob_bgp_ovs, 0, sizeof(glob_bgp_ovs));

    set_program_name(argv[0]);
    proctitle_init(argc, argv);
    fatal_ignore_sigpipe();

    /* Parse commandline args and get the name of the OVSDB socket. */
    ovsdb_sock = bgp_ovsdb_parse_options(argc, argv, &appctl_path);

    /* Initialize the metadata for the IDL cache. */
    ovsrec_init();

    /*
     * Fork and return in child process; but don't notify parent of
     * startup completion yet.
     */
    daemonize_start();

    /* Create UDS connection for ovs-appctl. */
    retval = unixctl_server_create(appctl_path, &appctl);
    if (retval) {
       exit(EXIT_FAILURE);
    }

    /* Register the ovs-appctl "exit" command for this daemon. */
    unixctl_command_register("exit", "", 0, 0, ops_bgp_exit, &exiting);

   /* Create the IDL cache of the dB at ovsdb_sock. */
   ovsdb_init(ovsdb_sock);
   free(ovsdb_sock);

   /* Notify parent of startup completion. */
   daemonize_complete();

   /* Enable asynch log writes to disk. */
   vlog_enable_async();

   VLOG_INFO_ONCE("%s (OpenSwitch Bgpd Daemon) started", program_name);

   glob_bgp_ovs.enabled = 1;
}

static void
bgp_ovs_clear_fds (void)
{
    struct poll_loop *loop = poll_loop();
    free_poll_nodes(loop);
    loop->timeout_when = LLONG_MAX;
    loop->timeout_where = NULL;
}

/* Check if the system is already configured. The daemon should
 * not process any callbacks unless the system is configured.
 */
static inline void bgp_chk_for_system_configured(void)
{
    const struct ovsrec_system *sys = NULL;

    if (system_configured) {
        /* Nothing to do if we're already configured. */
        return;
    }

    sys = ovsrec_system_first(idl);

    if (sys && (sys->cur_cfg > (int64_t) 0)) {
        system_configured = true;
        VLOG_INFO("System is now configured (cur_cfg=%d).",
            (int)sys->cur_cfg);
    }
}

static void
bgp_set_hostname (char *hostname)
{
    if (host.name)
        XFREE (MTYPE_HOST, host.name);
    host.name = XSTRDUP(MTYPE_HOST, hostname);
}

static void
modify_bgp_neighbor_route_map (const struct ovsrec_bgp_neighbor *ovs_bgpn,
    struct bgp *bgp_instance,
    const char *direction,
    afi_t afi, safi_t safi)
{
    /*
     * If an entry for "direction" is not found in the record, NULL name
     * will trigger an unset
     */
    char *name = NULL;

    int i;
    char *direct;

    for (i = 0; i < ovs_bgpn->n_route_maps; i++) {
        direct = ovs_bgpn->key_route_maps[i];
        if (!strcmp(direct, direction)) {
            struct ovsrec_route_map *rm = ovs_bgpn->value_route_maps[i];
            name = rm->name;
            break;
        }
    }
    daemon_neighbor_route_map_cmd_execute(bgp_instance,
        ovsdb_nbr_from_row_to_peer_name(idl, ovs_bgpn, NULL),
        afi, safi, name, direction);
}

static void
modify_bgp_neighbor_prefix_list (const struct ovsrec_bgp_neighbor *ovs_bgpn,
    struct bgp *bgp_instance,
    const char *direction,
    afi_t afi, safi_t safi)
{
    /*
     * If an entry for "direction" is not found in the record, NULL name
     * will trigger an unset
     */
    char *name = NULL;
    char *direct;
    int i;

    for (i = 0; i < ovs_bgpn->n_prefix_lists; i++) {
        direct = ovs_bgpn->key_prefix_lists[i];
        if (!strcmp(direct, direction)) {
            struct ovsrec_prefix_list *plist = ovs_bgpn->value_prefix_lists[i];
            name = plist->name;
            break;
        }
    }
    daemon_neighbor_prefix_list_cmd_execute(bgp_instance,
                          ovsdb_nbr_from_row_to_peer_name(idl, ovs_bgpn, NULL),
                          afi, safi, name, direction);
}

static void
modify_bgp_neighbor_aspath_filter(const struct ovsrec_bgp_neighbor *ovs_bgpn,
                                  struct bgp *bgp_instance,
                                  const char *direction,
                                  afi_t afi, safi_t safi)
{
    /*
     * If an entry for "direction" is not found in the record, NULL name
     * will trigger an unset
     */
    char *name = NULL;
    char *direct;
    struct ovsrec_bgp_aspath_filter *flist;
    int i;

    for (i = 0; i < ovs_bgpn->n_aspath_filters; i++) {
        direct = ovs_bgpn->key_aspath_filters[i];
        if (!strcmp(direct, direction)) {
            flist = ovs_bgpn->value_aspath_filters[i];
            name = flist->name;
            break;
        }
    }
    daemon_neighbor_aspath_filter_cmd_execute(bgp_instance,
        ovsdb_nbr_from_row_to_peer_name(idl, ovs_bgpn, NULL),
            afi, safi, name, direction);
}

afi_t
network2afi (const char *network)
{
    struct prefix p;
    afi_t afi;

    if (!str2prefix(network, &p)) {
        return 0;
    }

    afi = family2afi(p.family);
    return afi;
}

static void
apply_bgp_neighbor_route_map_changes(const struct ovsrec_bgp_neighbor *ovs_bgpn,
                                     struct bgp *bgp_instance)
{
    afi_t afi;
    safi_t safi = SAFI_UNICAST;

    /* Attempt to obtain the AFI. If it is a neighbor, then the AFI can be
     * obtained from the IP address.
     */
    if (object_is_peer(ovs_bgpn)) {
        afi = network2afi(ovsdb_nbr_from_row_to_peer_name(idl, ovs_bgpn, NULL));
    } else {
        /* OPS_TODO: For now, until IPv6 is supported, use AFI_IP by default
         * for peer-groups
         */
        afi = AFI_IP;
    }

    if (afi) {
        char *direct;
        direct = OVSREC_BGP_NEIGHBOR_ROUTE_MAPS_IN;
        modify_bgp_neighbor_route_map(ovs_bgpn, bgp_instance, direct,
                                      afi, safi);
        direct = OVSREC_BGP_NEIGHBOR_ROUTE_MAPS_OUT;
        modify_bgp_neighbor_route_map(ovs_bgpn, bgp_instance, direct,
                                      afi, safi);
    } else {
        VLOG_ERR("Invalid AFI");
    }
}

static void
apply_bgp_neighbor_prefix_list_changes(const struct ovsrec_bgp_neighbor *ovs_bgpn,
                                     struct bgp *bgp_instance)
{
    afi_t afi;
    safi_t safi = SAFI_UNICAST;
    char *direct;

    if (object_is_peer(ovs_bgpn)) {
        afi = network2afi(ovsdb_nbr_from_row_to_peer_name(idl, ovs_bgpn, NULL));
    } else {
        afi = AFI_IP;
    }

    if (afi) {
        direct = OVSREC_BGP_NEIGHBOR_PREFIX_LISTS_IN;
        modify_bgp_neighbor_prefix_list(ovs_bgpn, bgp_instance, direct,
                                      afi, safi);
        direct = OVSREC_BGP_NEIGHBOR_PREFIX_LISTS_OUT;
        modify_bgp_neighbor_prefix_list(ovs_bgpn, bgp_instance, direct,
                                      afi, safi);
    }
}

static void
apply_bgp_neighbor_aspath_filter_changes(const struct ovsrec_bgp_neighbor *ovs_bgpn,
                                         struct bgp *bgp_instance)
{
    afi_t afi;
    safi_t safi = SAFI_UNICAST;
    char *direct;

    /* Attempt to obtain the AFI. If it is a neighbor, then the AFI can be
     * obtained from the IP address.
     */
    if (object_is_peer(ovs_bgpn)) {
        afi = network2afi(ovsdb_nbr_from_row_to_peer_name(idl, ovs_bgpn, NULL));
    } else {
        afi = AFI_IP;
    }

    if (afi) {
        direct = OVSREC_BGP_NEIGHBOR_ASPATH_FILTERS_IN;
        modify_bgp_neighbor_aspath_filter(ovs_bgpn, bgp_instance, direct,
                                          afi, safi);
        direct = OVSREC_BGP_NEIGHBOR_ASPATH_FILTERS_OUT;
        modify_bgp_neighbor_aspath_filter(ovs_bgpn, bgp_instance, direct,
                                          afi, safi);
    } else {
        VLOG_ERR("Invalid AFI");
    }
}

static void
bgp_update_router_id_from_active_router_id(void)
{
    const struct ovsrec_vrf *ovs_vrf;
    const struct ovsrec_bgp_router *ovs_bgp;
    char *router_id = NULL;
    int i;

    OVSREC_VRF_FOR_EACH(ovs_vrf, idl) {
        if (!strcmp(ovs_vrf->name, DEFAULT_VRF_NAME)) {
            for (i = 0; i < ovs_vrf->n_bgp_routers; i++) {
                ovs_bgp = ovs_vrf->value_bgp_routers[i];
                if (ovs_bgp != NULL){
                    router_id = ovs_vrf->active_router_id;
                    VLOG_DBG("Setting BGP router_id to %s from active_router_id", router_id);

                    if (router_id != NULL)
                        bgp_update_active_router_id(ovs_bgp, router_id);
                }
            }
        }
    }
}

static void
bgp_apply_global_changes (void)
{
    const struct ovsrec_system *sys;
    const struct ovsrec_vrf *ovs_vrf;
    const struct ovsrec_bgp_router *ovs_bgp;
    int64_t asn;
    int i;
    boolean ecmp_status;

    sys = ovsrec_system_first(idl);
    if (OVSREC_IDL_ANY_TABLE_ROWS_DELETED(sys, idl_seqno)) {
        VLOG_WARN("First Row deleted from System tbl\n");
        return;
    }
    if (!OVSREC_IDL_ANY_TABLE_ROWS_INSERTED(sys, idl_seqno) &&
            !OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED(sys, idl_seqno)) {
        VLOG_DBG("No System cfg changes");
        return;
    }

    if(OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_system_col_ecmp_config, idl_seqno) ) {
        ecmp_status = smap_get_bool(&sys->ecmp_config, SYSTEM_ECMP_CONFIG_STATUS,
                SYSTEM_ECMP_CONFIG_ENABLE_DEFAULT);
        if(sys_ecmp_status != ecmp_status) {
            VLOG_INFO("ECMP changed compared to local cache!");
            sys_ecmp_status = ecmp_status;
            OVSREC_VRF_FOR_EACH(ovs_vrf, idl) {
                for (i = 0; i < ovs_vrf->n_bgp_routers; i++) {
                    asn = ovs_vrf->key_bgp_routers[i];
                    ovs_bgp = ovs_vrf->value_bgp_routers[i];
                    bgp_ovsdb_republish_route(ovs_bgp, asn);
                }
            }
        }
    }

    if (sys) {
        /* Update the hostname */
        bgp_set_hostname(sys->hostname);
    }
}

void
delete_bgp_router_config (struct ovsdb_idl *idl)
{
    struct ovsrec_bgp_router *bgp_del_row;
    const struct ovsrec_vrf *ovs_vrf;
    int64_t asn;
    struct bgp *bgp_cfg;
    int i;

    while (bgp_cfg = bgp_lookup_by_name(NULL)) {
        bool match_found = 0;

        OVSREC_VRF_FOR_EACH(ovs_vrf, idl) {
            for (i = 0; i < ovs_vrf->n_bgp_routers; i++) {
                if (bgp_cfg->as == ovs_vrf->key_bgp_routers[i]) {
                    match_found = 1;
                    break;
                }
            }
            if (!match_found) {
                VLOG_DBG("bgp_cfg->as: %d will be deleted from BGPD\n", bgp_cfg->as);
                bgp_delete(bgp_cfg);
            }
        }
    }
}

void
delete_redistribute_rmap_config(struct ovsdb_idl *idl,
                           const struct ovsrec_bgp_router *bgp_mod_row,
                           struct bgp *bgp)
{
    const struct ovsrec_bgp_router *ovs_first;
    int i,j,type;
    int ret = 0;
    bool match_found = false;
    for (j = 0; j < ZEBRA_ROUTE_MAX; j++) {
        match_found = false;
        if (bgp->redist[AFI_IP][j] && j != ZEBRA_ROUTE_BGP) {
            OVSREC_BGP_ROUTER_FOR_EACH(bgp_mod_row, idl) {
                for (i=0; i< bgp_mod_row->n_redistribute_route_map; i++) {
                    if (strcmp(bgp_mod_row->key_redistribute_route_map[i],
                               zebra_route_string(j)) ==0 &&
                        strcmp(bgp_mod_row->value_redistribute_route_map[i]->name,
                               bgp->rmap[AFI_IP][j].name) == 0) {
                        match_found = true;
                        break;
                    }
                }
                if (match_found == true) {
                    break;
                }
            }
            if ( match_found == false && bgp->rmap[AFI_IP][j].name) {
                    ret = bgp_redistribute_unset (bgp, AFI_IP, j);
                    if (!ret) {
                        VLOG_DBG("Deleted redistribute %s",
                                  zebra_route_string(j));
                    }
            }
        }
    }
    return;
}

void
delete_redistribute_config(struct ovsdb_idl *idl,
                           const struct ovsrec_bgp_router *bgp_mod_row,
                           struct bgp *bgp)
{
    const struct ovsrec_bgp_router *ovs_first;
    int i,j,type;
    int ret = 0;
    bool match_found = false;
    for (j = 0; j < ZEBRA_ROUTE_MAX; j++) {
        match_found = false;
        if (bgp->redist[AFI_IP][j] && j != ZEBRA_ROUTE_BGP) {
            OVSREC_BGP_ROUTER_FOR_EACH(bgp_mod_row, idl) {
                for (i=0; i< bgp_mod_row->n_redistribute; i++) {
                    if (strcmp(bgp_mod_row->redistribute[i],
                               zebra_route_string(j)) == 0 &&
                        bgp->rmap[AFI_IP][j].name == NULL)  {
                        match_found = true;
                        break;
                    }
                }
                if (match_found == true) {
                    break;
                }
            }
            if ( match_found == false  && bgp->rmap[AFI_IP][j].name == NULL) {
                    ret = bgp_redistribute_unset (bgp, AFI_IP, j);
                    if (!ret) {
                        VLOG_DBG("Deleted redistribute %s",
                                  zebra_route_string(j));
                    }
            }
        }
    }
    return;
}


void
modify_bgp_redistribute_rmap_config(struct ovsdb_idl *idl,struct bgp *bgp_cfg,
    const struct ovsrec_bgp_router *bgp_mod_row)
{
    int i=0;
    int type;
    int rmap;
    int ret_status = -1;

    /* Handle redistribute deletions. */
    delete_redistribute_rmap_config(idl,bgp_mod_row, bgp_cfg);

    VLOG_DBG("Setting  BGP Redistribute rmap configuration");
    OVSREC_BGP_ROUTER_FOR_EACH(bgp_mod_row, idl) {
        for (i = 0; i<bgp_mod_row->n_redistribute_route_map; i++) {
            type = proto_redistnum (AFI_IP, bgp_mod_row->
                                    key_redistribute_route_map[i]);
            if (type < 0 || type == ZEBRA_ROUTE_BGP) {
                VLOG_DBG("Invalid route type");
                continue;
            }

            rmap=bgp_redistribute_rmap_set (bgp_cfg, AFI_IP, type,
                                  bgp_mod_row->value_redistribute_route_map[i]->name);
            ret_status = bgp_redistribute_set(bgp_cfg, AFI_IP, type);
            if (!rmap && !ret_status) {
                VLOG_DBG("redistribute %s route-map %s is set",
                          bgp_mod_row->key_redistribute_route_map[i],
                          bgp_mod_row->value_redistribute_route_map[i]->name);
            }
        }
    }
}

void
modify_bgp_redistribute_config(struct ovsdb_idl *idl,struct bgp *bgp_cfg,
    const struct ovsrec_bgp_router *bgp_mod_row)
{
    int i=0;
    int type;
    int ret_status = -1;

    /* Handle redistribute deletions. */
    delete_redistribute_config(idl,bgp_mod_row, bgp_cfg);

    VLOG_DBG("Setting  BGP redistribute configuration");
    OVSREC_BGP_ROUTER_FOR_EACH(bgp_mod_row, idl) {
        for (i = 0; i<bgp_mod_row->n_redistribute; i++) {
            type = proto_redistnum (AFI_IP, bgp_mod_row->
                                    redistribute[i]);
            if (type < 0 || type == ZEBRA_ROUTE_BGP) {
                VLOG_DBG("Invalid route type");
                continue;
            }
            ret_status = bgp_redistribute_set(bgp_cfg, AFI_IP, type);
            if (!ret_status) {
                VLOG_DBG("redistribute %s is set",
                          bgp_mod_row->redistribute[i]);
            }
        }
    }
}

void
insert_bgp_router_config (struct ovsdb_idl *idl,
    const struct ovsrec_bgp_router *bgp_first, int64_t asn)
{
    struct bgp *bgp_cfg;
    int ret_status;

    VLOG_DBG("New row insertion to BGP config\n");
    ret_status = bgp_get(&bgp_cfg, (as_t *)&asn, NULL);
    if (!ret_status) {
        VLOG_DBG("bgp_cfg->as: %d", bgp_cfg->as);
    }
}

/* To configure BGP fast-external-failover flag which allows to immediately
 * reset external BGP peering sessions if the link goes down.
 */
void
modify_bgp_fast_external_failover_config (struct bgp *bgp_cfg,
                                          const struct ovsrec_bgp_router *bgp_mod_row)
{
    if (bgp_mod_row->n_fast_external_failover && bgp_mod_row->fast_external_failover[0]) {
        VLOG_DBG("Setting BGP fast external failover flag");
        bgp_flag_unset (bgp_cfg, BGP_FLAG_NO_FAST_EXT_FAILOVER);
    } else {
        VLOG_DBG("Unsetting BGP fast external failover flag");
        bgp_flag_set (bgp_cfg, BGP_FLAG_NO_FAST_EXT_FAILOVER);
    }
}

/* To configure BGP log-neighbor-changes flag which enables the generation of
 * logging messages generated when the status of a BGP neighbor changes.
 */
void
modify_bgp_log_neighbor_changes_config (struct bgp *bgp_cfg,
                                        const struct ovsrec_bgp_router *bgp_mod_row)
{
    if (bgp_mod_row->n_log_neighbor_changes && bgp_mod_row->log_neighbor_changes[0]) {
        VLOG_DBG("Setting BGP log neighbor changes flag");
        bgp_flag_set(bgp_cfg, BGP_FLAG_LOG_NEIGHBOR_CHANGES);
    } else {
        VLOG_DBG("Unsetting BGP log neighbor changes flag");
        bgp_flag_unset(bgp_cfg, BGP_FLAG_LOG_NEIGHBOR_CHANGES);
    }
}

void
modify_bgp_router_config (struct ovsdb_idl *idl,
    const struct ovsrec_bgp_router *bgp_first, int64_t asn)
{
    const struct ovsrec_bgp_router *bgp_mod_row = bgp_first;
    const struct ovsdb_idl_column *column;
    struct bgp *bgp_cfg;
    as_t as;
    int ret_status;

    bgp_cfg = bgp_lookup((as_t)asn, NULL);

    /* Check if router_id is modified */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_bgp_router_col_router_id, idl_seqno)) {
        ret_status = modify_bgp_router_id_config(bgp_cfg, bgp_mod_row);
        if (!ret_status) {
            VLOG_DBG("BGP router_id set to %s", inet_ntoa(bgp_cfg->router_id));
        }
    }

    /* Check if network is modified */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_bgp_router_col_networks, idl_seqno)) {
        ret_status = modify_bgp_network_config(bgp_cfg,bgp_mod_row);
        if (!ret_status) {
             VLOG_DBG("Static route added/deleted to bgp routing table");
        }
    }

    /* Check if maximum_paths is modified */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_bgp_router_col_maximum_paths, idl_seqno)) {
        ret_status = modify_bgp_maxpaths_config(bgp_cfg,bgp_mod_row);
        if (!ret_status) {
            VLOG_DBG("Maximum paths for BGP is set to %d",
                bgp_cfg->maxpaths[AFI_IP][SAFI_UNICAST].maxpaths_ebgp);
        }
    }

    /* Check if bgp timers are modified */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_bgp_router_col_timers, idl_seqno)) {
        modify_bgp_timers_config(bgp_cfg,bgp_mod_row);
    }

    /* Check if bgp fast external failover is set */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_bgp_router_col_fast_external_failover,
                                      idl_seqno)) {
        modify_bgp_fast_external_failover_config(bgp_cfg, bgp_mod_row);
    }

    /* Check if bgp log neighbor changes is set */
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_bgp_router_col_log_neighbor_changes,
                                      idl_seqno)) {
        modify_bgp_log_neighbor_changes_config(bgp_cfg, bgp_mod_row);
    }

    /* Check redistribute protocol configuration is modified*/
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_bgp_router_col_redistribute,
        idl_seqno)) {
        modify_bgp_redistribute_config(idl, bgp_cfg, bgp_mod_row);
    }

    /* Check redistribute rmap configuration is modified*/
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_bgp_router_col_redistribute_route_map, idl_seqno)) {
        modify_bgp_redistribute_rmap_config(idl, bgp_cfg, bgp_mod_row);
    }

}


int
modify_bgp_router_id_config (struct bgp *bgp_cfg,
    const struct ovsrec_bgp_router *bgp_mod_row)
{
    const struct ovsdb_idl_column *column;
    struct in_addr addr;

    addr.s_addr = inet_addr(bgp_mod_row->router_id);
    if (addr.s_addr != 0) {
        bgp_cfg->router_id_static = addr;
        return bgp_router_id_set(bgp_cfg, &addr);
    }
    else {
        bgp_cfg->router_id_static.s_addr = 0;
        return bgp_router_id_unset(bgp_cfg, &addr);
    }

}

void
bgp_static_route_dump (struct bgp *bgp_cfg, struct bgp_node *rn)
{
    char prefix_str[256];
    int ret;

    for (rn = bgp_table_top (bgp_cfg->route[AFI_IP][SAFI_UNICAST]); rn;
         rn = bgp_route_next (rn)) {
            memset(prefix_str, 0 ,sizeof(prefix_str));
            ret = prefix2str(&rn->p, prefix_str, sizeof(prefix_str));
            if (ret) {
                VLOG_ERR("Prefix to string conversion failed!");
            } else {
                if (!strcmp(prefix_str,"0.0.0.0/0"))
                   continue;
                if (rn->info != NULL)
                    VLOG_DBG("Static route : %s", prefix_str);
            }
    }
}

int
modify_bgp_network_config (struct bgp *bgp_cfg,
    const struct ovsrec_bgp_router *bgp_mod_row)
{
    int ret_status = 0;

    VLOG_DBG("bgp_mod_row->n_networks = %d", bgp_mod_row->n_networks);
    ret_status = bgp_static_route_addition(bgp_cfg, bgp_mod_row);
    if (ret_status == CMD_SUCCESS) {
        VLOG_DBG("Static route added.");
    }
    ret_status = bgp_static_route_deletion(bgp_cfg, bgp_mod_row);
    if (ret_status == CMD_SUCCESS) {
        VLOG_DBG("Static route deleted.");
    }
    return ret_status;
}

int
bgp_static_route_addition (struct bgp *bgp_cfg,
    const struct ovsrec_bgp_router *bgp_mod_row)
{
    struct prefix p;
    struct bgp_node *rn;
    afi_t afi;
    safi_t safi;
    int ret_status = -1;
    int i = 0;

    for (i = 0; i < bgp_mod_row->n_networks; i++) {
        VLOG_DBG("bgp_mod_row->networks[%d]: %s", i, bgp_mod_row->networks[i]);

        int ret = str2prefix(bgp_mod_row->networks[i], &p);
        if (! ret) {
            VLOG_ERR("Malformed prefix");
            return -1;
        }
        afi = family2afi(p.family);
        safi = SAFI_UNICAST;
        rn = bgp_node_lookup(bgp_cfg->route[afi][safi], &p);
        if (!rn) {
            VLOG_DBG("Can't find specified static route configuration..\n");
            ret_status = bgp_static_set(NULL, bgp_cfg,
                            bgp_mod_row->networks[i], afi, safi, NULL, 0);
            if (!ret_status)
                bgp_static_route_dump(bgp_cfg,rn);
            else
                VLOG_ERR("Static route addition failed!!");
        } else {
            VLOG_DBG("Network %s already exists. Skip adding.");
        }
    }
    return ret_status;
}

int
bgp_static_route_deletion (struct bgp *bgp_cfg,
                           const struct ovsrec_bgp_router *bgp_mod_row)
{
    struct bgp_node *rn;
    afi_t afi;
    safi_t safi;
    int ret_status = -1;
    int i = 0;
    int afi_type;

    if (bgp_cfg = bgp_lookup((as_t)ovsdb_bgp_router_from_row_to_asn(idl, bgp_mod_row),
        NULL))
    {
        bool match_found = 0;
        char prefix_str[256];

        for (afi_type = AFI_IP; afi_type < AFI_MAX; afi_type++) {
            for (rn = bgp_table_top (bgp_cfg->route[afi_type][SAFI_UNICAST]); rn;
                   rn = bgp_route_next (rn)) {
                memset(prefix_str, 0 ,sizeof(prefix_str));

                int ret = prefix2str(&rn->p, prefix_str, sizeof(prefix_str));
                if (ret) {
                    VLOG_ERR("Prefix to string conversion failed!");
                    return -1;
                } else {
                    VLOG_DBG("Prefix to str : %s", prefix_str);
                }

                afi = family2afi(rn->p.family);
                safi = SAFI_UNICAST;

                if ((bgp_mod_row->n_networks == 0)) {
                    VLOG_DBG("Last static route being deleted...");
                    ret_status = bgp_static_unset(NULL, bgp_cfg, prefix_str,
                                     afi, safi);
                    if (!ret_status)
                        bgp_static_route_dump(bgp_cfg,rn);
                    else
                        VLOG_ERR("Last static route deletion failed!!");
                } else {
                    bool match_found = 0;
                    for (i = 0; i < bgp_mod_row->n_networks; i++) {
                        if (!strcmp(prefix_str, bgp_mod_row->networks[i])) {
                            match_found = 1;
                            break;
                        }
                    }
                    if (!match_found) {
                        VLOG_DBG("Static route being deleted...");
                        ret_status = bgp_static_unset(NULL, bgp_cfg, prefix_str,
                                                      afi, safi);
                        if (!ret_status)
                            bgp_static_route_dump(bgp_cfg,rn);
                        else
                            VLOG_ERR("Static route deletion failed!!");
                    } else {
                        VLOG_DBG("Static route exists. Skip deleting.");
                    }
                }

            }
        }
    }
    return ret_status;
}

int
modify_bgp_maxpaths_config (struct bgp *bgp_cfg,
    const struct ovsrec_bgp_router *bgp_mod_row)
{
    if (bgp_mod_row->n_maximum_paths && bgp_mod_row->maximum_paths[0]) {
        VLOG_DBG("Setting max paths");
        bgp_flag_set(bgp_cfg, BGP_FLAG_ASPATH_MULTIPATH_RELAX);
        return
            bgp_maximum_paths_set(bgp_cfg, AFI_IP, SAFI_UNICAST,
                BGP_PEER_EBGP, (u_int16_t) bgp_mod_row->maximum_paths[0]);
    }

    VLOG_DBG("Unsetting max paths");
    bgp_flag_unset(bgp_cfg, BGP_FLAG_ASPATH_MULTIPATH_RELAX);
    return
        bgp_maximum_paths_unset(bgp_cfg, AFI_IP, SAFI_UNICAST, BGP_PEER_EBGP);
}

int
modify_bgp_timers_config (struct bgp *bgp_cfg,
    const struct ovsrec_bgp_router *bgp_mod_row)
{
    int64_t keepalive = 0, holdtime = 0, ret_status = 0;
    struct smap smap;
    const struct ovsdb_datum *datum;

    datum = ovsrec_bgp_router_get_timers(bgp_mod_row, OVSDB_TYPE_STRING,
                OVSDB_TYPE_INTEGER);

    /* Can be seen on ovsdb restart */
    if (NULL == datum) {
        VLOG_DBG("No value found for given key");
        ret_status = -1;
    } else {
        if (bgp_mod_row->n_timers) {
            ovsdb_datum_get_int64_value_given_string_key(datum,
                bgp_mod_row->key_timers[1], &keepalive);
            ovsdb_datum_get_int64_value_given_string_key(datum,
                bgp_mod_row->key_timers[0], &holdtime);

            ret_status = bgp_timers_set(bgp_cfg, keepalive, holdtime);
            VLOG_DBG("Set keepalive:%lld and holdtime:%lld timers",
                     keepalive, holdtime);
        } else {
            ret_status = bgp_timers_unset(bgp_cfg);
            VLOG_DBG("Timers have been unset");
        }
    }

    return ret_status;
}

static void
bgp_router_read_ovsdb_apply_changes (struct ovsdb_idl *idl)
{
    const struct ovsrec_vrf *ovs_vrf = NULL;
    const struct ovsrec_bgp_router *ovs_bgp;
    const struct ovsrec_bgp_neighbor *ovs_bgpnbr;
    struct smap_node *node;
    int64_t asn;
    char peer[80];

    struct bgp *bgp_instance;
    bool modified = false;
    bool deleted = false;
    int i;

   /*
    * From each VRF table,
    *   for each row in bgp router table, inserted/modified ?
    *      for the changed row, any specific column ?
    */
    OVSREC_VRF_FOR_EACH(ovs_vrf, idl) {
        for (i = 0; i < ovs_vrf->n_bgp_routers; i++) {
            asn = ovs_vrf->key_bgp_routers[i];
            ovs_bgp = ovs_vrf->value_bgp_routers[i];
            if (OVSREC_IDL_IS_ROW_INSERTED(ovs_bgp, idl_seqno)) {
                insert_bgp_router_config(idl, ovs_bgp, asn);
            }
            if (OVSREC_IDL_IS_ROW_MODIFIED(ovs_bgp, idl_seqno) ||
                (OVSREC_IDL_IS_ROW_INSERTED(ovs_bgp, idl_seqno))) {
                    modify_bgp_router_config(idl, ovs_bgp, asn);
            }
        }
    }
}

/*
 * Subscribe for changes in the BGP_Router table
 */
static void
bgp_apply_bgp_router_changes (struct ovsdb_idl *idl)
{
    const struct ovsrec_bgp_router *bgp_first;
    struct bgp *bgp_cfg;
    static struct ovsdb_idl_txn *confirm_txn = NULL;

    bgp_first = ovsrec_bgp_router_first(idl);

    /*
     * Check if any table changes present.
     * If no change just return from here
     */
    if (bgp_first && !OVSREC_IDL_ANY_TABLE_ROWS_INSERTED(bgp_first, idl_seqno)
        && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED(bgp_first, idl_seqno)
        && !OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED(bgp_first, idl_seqno)
        && !OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_vrf_col_active_router_id, idl_seqno)) {
        VLOG_DBG("No BGP_Router changes");
        return;
    }

    if (bgp_first == NULL) {
        /* Check if it is a first row deletion */
        VLOG_DBG("BGP config empty!\n");
        bgp_cfg = bgp_lookup_by_name(NULL);
        if (bgp_cfg) {
            bgp_delete(bgp_cfg);
        }
        return;
    }

    /* Check if any row deletion */
    if (OVSREC_IDL_ANY_TABLE_ROWS_DELETED(bgp_first, idl_seqno)) {
        delete_bgp_router_config(idl);
    }

    if (NULL == bgp_first->router_id
        || OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_vrf_col_active_router_id, idl_seqno)){
         bgp_update_router_id_from_active_router_id();
    }

    /* insert and modify cases */
    bgp_router_read_ovsdb_apply_changes(idl);
}

/*
 * Iterate through all the peers of the BGP and check against
 * ovsdb to identify which neighbor has been deleted. If it doesn't exist
 * in ovsdb then it is considered deleted.
 */
static void
check_and_delete_bgp_neighbors (struct bgp *bgp,
    const struct ovsrec_bgp_router *ovs_bgp,
    struct ovsdb_idl *idl)
{
    struct peer *peer;
    struct listnode *node, *nnode;
    struct ovsrec_bgp_neighbor *ovs_nbr;
    int i;
    bool deleted_from_database;

    for (ALL_LIST_ELEMENTS (bgp->peer, node, nnode, peer)) {
        deleted_from_database = true;
        for (i = 0; i < ovs_bgp->n_bgp_neighbors; i++) {
            ovs_nbr = ovs_bgp->value_bgp_neighbors[i];
            if (object_is_peer(ovs_nbr) &&
                !strcmp(ovs_bgp->key_bgp_neighbors[i], peer->host)) {
                    deleted_from_database = false;
                    break;
            }
        }

        if (deleted_from_database) {
            VLOG_DBG("bgp peer %s being deleted", peer->host);
            peer_delete(peer);
        }
    }
}

/*
 * same as above but for peer groups
 */
static void
check_and_delete_bgp_neighbor_peer_groups (struct bgp *bgp,
    const struct ovsrec_bgp_router *ovs_bgp,
    struct ovsdb_idl *idl)
{
    struct peer_group *peer_group;
    struct listnode *node, *nnode;
    struct ovsrec_bgp_neighbor *ovs_nbr;
    bool deleted_from_database;
    int i;

    for (ALL_LIST_ELEMENTS (bgp->group, node, nnode, peer_group)) {
        deleted_from_database = true;
        for (i = 0; i < ovs_bgp->n_bgp_neighbors; i++) {
            ovs_nbr = ovs_bgp->value_bgp_neighbors[i];
            if (object_is_peer_group(ovs_nbr) &&
                !strcmp(ovs_bgp->key_bgp_neighbors[i], peer_group->name)) {
                    deleted_from_database = false;
                    break;
            }
        }

        if (deleted_from_database) {
            VLOG_DBG("peer group %s being deleted", peer_group->name);
            peer_group_delete(peer_group);
        }
    }
}

/*
 * since we cannot possibly know in advance what is deleted
 * from the database, we check for *ALL* bgps, all of their
 * groups & all of their peers.
 */
static void
delete_bgp_neighbors_and_peer_groups (struct ovsdb_idl *idl)
{
    const struct ovsrec_vrf *ovs_vrf = NULL;
    const struct ovsrec_bgp_router *ovs_bgp;
    struct smap_node *node;
    int64_t asn;
    int i;
    struct bgp *pbgp;

    OVSREC_VRF_FOR_EACH(ovs_vrf, idl) {
        for (i = 0; i < ovs_vrf->n_bgp_routers; i++) {
            asn = ovs_vrf->key_bgp_routers[i];
            ovs_bgp = ovs_vrf->value_bgp_routers[i];
            pbgp = bgp_lookup(asn, NULL);
            if (!pbgp) {
               VLOG_ERR("%%cannot find daemon bgp router instance %d %%\n", asn);
               continue;
            }
            VLOG_DBG("bgp router instance %d found\n", asn);
            check_and_delete_bgp_neighbors(pbgp, ovs_bgp, idl);
            check_and_delete_bgp_neighbor_peer_groups(pbgp, ovs_bgp, idl);
        }
    }
}

/*
 * vrf_name CAN be NULL but ipaddr should NOT be passed as NULL
 */
static const struct ovsrec_bgp_neighbor *
get_bgp_neighbor_with_VrfName_BgpRouterAsn_Ipaddr (struct ovsdb_idl *idl,
    char *vrf_name,
    int64_t asn,
    const char *ipaddr)
{
    int i, j;
    const struct ovsrec_vrf *ovs_vrf;
    const struct ovsrec_bgp_router *ovs_bgp;

    if (NULL == vrf_name) {
    vrf_name = DEFAULT_VRF_NAME;
    }

    OVSREC_VRF_FOR_EACH(ovs_vrf, idl) {
        if (strcmp(ovs_vrf->name, vrf_name)) {
            continue;
        }
        for (i = 0; i < ovs_vrf->n_bgp_routers; i++) {
            if (asn != ovs_vrf->key_bgp_routers[i]) {
                continue;
            }
            ovs_bgp = ovs_vrf->value_bgp_routers[i];
            for (j = 0; j < ovs_bgp->n_bgp_neighbors; j++) {
                if (ip_addr_is_equal(ipaddr, ovs_bgp->key_bgp_neighbors[j])) {
                    return ovs_bgp->value_bgp_neighbors[j];
                }
            }
        }
    }
    return NULL;
}

const struct ovsrec_bgp_neighbor *
get_bgp_neighbor_db_row (struct peer *peer)
{
    const char *ipaddr;
    char ip_addr_string [64];

    ipaddr = sockunion2str(&peer->su, ip_addr_string, 63);
    if (ipaddr) {
        return
            get_bgp_neighbor_with_VrfName_BgpRouterAsn_Ipaddr(idl, NULL,
                peer->bgp->as, ipaddr);
    }
    return NULL;
}

void
bgp_daemon_ovsdb_neighbor_statistics_update (bool start_new_db_txn,
    const struct ovsrec_bgp_neighbor *ovs_bgp_neighbor_ptr,
    struct peer *peer)
{

#define MAX_BGP_NEIGHBOR_STATS        64

    struct ovsdb_idl_txn *db_txn;
    char *keywords[MAX_BGP_NEIGHBOR_STATS];
    int64_t values [MAX_BGP_NEIGHBOR_STATS];
    int count;
    enum ovsdb_idl_txn_status status;

#define ADD_BGPN_STAT(key, value) \
    keywords[count] = key; \
    values[count] = value; \
    count++

    /* if row is not given, find it */
    if (NULL == ovs_bgp_neighbor_ptr) {
        ovs_bgp_neighbor_ptr = get_bgp_neighbor_db_row(peer);

        /* it is possible to come here with no db entry, this is ok */
        if (NULL == ovs_bgp_neighbor_ptr) return;
    }

    /* is this an independent txn or piggybacked onto another txn */
    if (start_new_db_txn) {
        db_txn = ovsdb_idl_txn_create(idl);
        if (NULL == db_txn) {
            VLOG_ERR("%%ovsdb_idl_txn_create failed in "
            "bgp_daemon_ovsdb_neighbor_statistics_update\n");
            return;
        }
    }

    count = 0;

    ADD_BGPN_STAT(BGP_PEER_ESTABLISHED_COUNT,  peer->established);
    ADD_BGPN_STAT(BGP_PEER_DROPPED_COUNT,  peer->dropped);
    ADD_BGPN_STAT(BGP_PEER_OPEN_IN_COUNT,  peer->open_in);
    ADD_BGPN_STAT(BGP_PEER_OPEN_OUT_COUNT, peer->open_out);
    ADD_BGPN_STAT(BGP_PEER_UPDATE_IN_COUNT, peer->update_in);
    ADD_BGPN_STAT(BGP_PEER_UPDATE_OUT_COUNT, peer->update_out);
    ADD_BGPN_STAT(BGP_PEER_KEEPALIVE_IN_COUNT, peer->keepalive_in);
    ADD_BGPN_STAT(BGP_PEER_KEEPALIVE_OUT_COUNT, peer->keepalive_out);
    ADD_BGPN_STAT(BGP_PEER_NOTIFY_IN_COUNT, peer->notify_in);
    ADD_BGPN_STAT(BGP_PEER_NOTIFY_OUT_COUNT, peer->notify_out);
    ADD_BGPN_STAT(BGP_PEER_REFRESH_IN_COUNT, peer->refresh_in);
    ADD_BGPN_STAT(BGP_PEER_REFRESH_OUT_COUNT, peer->refresh_out);
    ADD_BGPN_STAT(BGP_PEER_DYNAMIC_CAP_IN_COUNT, peer->dynamic_cap_in);
    ADD_BGPN_STAT(BGP_PEER_DYNAMIC_CAP_OUT_COUNT, peer->dynamic_cap_out);

    ADD_BGPN_STAT(BGP_PEER_UPTIME, peer->uptime);
    ADD_BGPN_STAT(BGP_PEER_READTIME, peer->readtime);
    ADD_BGPN_STAT(BGP_PEER_RESETTIME, peer->resettime);

    ovsrec_bgp_neighbor_set_statistics(ovs_bgp_neighbor_ptr,
    keywords, values, count);

    if (start_new_db_txn) {
        status = ovsdb_idl_txn_commit(db_txn);
        ovsdb_idl_txn_destroy(db_txn);
        VLOG_DBG("%s OVSDB Neighbour statistics update transaction status is %s",
                __FUNCTION__, ovsdb_idl_txn_status_to_string(status));
    }
}

/*
 * update a bunch of BGP_Neighbor related info
 * in the ovs database, from the daemon side
 */
void bgp_daemon_ovsdb_neighbor_update (struct peer *peer,
    bool update_stats_too)
{
    const struct ovsrec_bgp_neighbor *ovs_bgp_neighbor_ptr;
    struct ovsdb_idl_txn *db_txn;
    enum ovsdb_idl_txn_status status;
    struct smap smap;

    ovs_bgp_neighbor_ptr = get_bgp_neighbor_db_row(peer);
    if (NULL == ovs_bgp_neighbor_ptr) {
        VLOG_DBG("bgp_daemon_ovsdb_neighbor_update cannot find db row or "
                 "returned neighbor was a peer-group");
        return;
    }

    VLOG_DBG("updating bgp neighbor %s remote-as %d in db\n",
           ovsdb_nbr_from_row_to_peer_name(idl, ovs_bgp_neighbor_ptr, NULL),
           *ovs_bgp_neighbor_ptr->remote_as);

    db_txn = ovsdb_idl_txn_create(idl);
    if (NULL == db_txn) {
    VLOG_ERR("%%ovsdb_idl_txn_create failed in "
        "bgp_daemon_ovsdb_neighbor_update\n");
    return;
    }

    /* update fields of this peer/neighbor in the ovsdb */

    if (peer->group) {
    /* TO DO LATER */
    }

    VLOG_DBG("updating port to %d\n", peer->port);
    ovsrec_bgp_neighbor_set_tcp_port_number(ovs_bgp_neighbor_ptr,
        (int64_t*) &peer->port, 1);

    /*
     * OPS_TODO
    VLOG_DBG("updating local_as to %d\n", peer->local_as);
    This causes the entire transaction to be rejected, investigate later
    ovsrec_bgp_neighbor_set_local_as(ovs_bgp_neighbor_ptr,
        &peer->local_as, 1);
     */

    VLOG_DBG("updating weight to %d\n", peer->weight);
    ovsrec_bgp_neighbor_set_weight(ovs_bgp_neighbor_ptr,
        (int64_t*) &peer->weight, 1);

    smap_init(&smap);
    smap_add(&smap, BGP_PEER_STATE, bgp_peer_status_to_string(peer->status));
    VLOG_DBG("updating bgp neighbor status to %s\n",
    bgp_peer_status_to_string(peer->status));
    ovsrec_bgp_neighbor_set_status(ovs_bgp_neighbor_ptr, &smap);

    /* update statistics */
    if (update_stats_too) {
    bgp_daemon_ovsdb_neighbor_statistics_update(false,
        ovs_bgp_neighbor_ptr, peer);
    VLOG_DBG("updated stats also\n");
    }

    status = ovsdb_idl_txn_commit(db_txn);
    VLOG_DBG("%s OVSDB Neighbour update status is %s", __FUNCTION__,
                    ovsdb_idl_txn_status_to_string(status));
    ovsdb_idl_txn_destroy(db_txn);
}

static int
fetch_key_value (char **key, const int64_t *value,
    size_t n_elem, char *your_key)
{
    int i;

    for (i = 0; i < n_elem; i++) {
        if (strcmp(key[i], your_key) == 0) {
            return value[i];
        }
    }
    return -1;
}

static void
bgp_nbr_remote_as_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    char * name,
    struct bgp *bgp_instance)

{
    /* remote-as */
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_remote_as, idl_seqno)) {
        VLOG_DBG("Setting remote-as %lld", *ovs_nbr->remote_as);
        daemon_neighbor_remote_as_cmd_execute(bgp_instance,
            name, (as_t *)ovs_nbr->remote_as, AFI_IP, SAFI_UNICAST);
    }
}

static void
bgp_nbr_fallover_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    char * name,
    struct bgp *bgp_instance)
{
    bool is_set = (ovs_nbr->bfd_fallover_enable) ? true : false;

    /* fallover */
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_bfd_fallover_enable, idl_seqno)) {
        VLOG_DBG("Fallover BFD %s for %s", (is_set) ? "Enable" : "Disable", name);
        daemon_neighbor_bfd_fallover_enable_cmd_execute(bgp_instance, name, is_set);
    }
}

static int
bfd_session_state_string_to_enum (const char *state_str)
{
    if (!state_str)
        return BFD_SESSION_STATE_ADMIN_DOWN;

    VLOG_DBG("bfd_session_state_string_to_enum: input string is %s", state_str);

    if (strcmp(state_str, BFD_SESSION_STATE_STR_ADMIN_DOWN) == 0)
        return BFD_SESSION_STATE_ADMIN_DOWN;
    else if (strcmp(state_str, BFD_SESSION_STATE_STR_DOWN) == 0)
        return BFD_SESSION_STATE_DOWN;
    else if (strcmp(state_str, BFD_SESSION_STATE_STR_INIT) == 0)
        return BFD_SESSION_STATE_INIT;
    else if (strcmp(state_str, BFD_SESSION_STATE_STR_UP) == 0)
        return BFD_SESSION_STATE_UP;

    return BFD_SESSION_STATE_ADMIN_DOWN;
}

static void
bgp_nbr_bfd_session_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    char *name, struct bgp *bgp_instance, bool bfd_session_changed)
{
    const struct ovsrec_bfd_session *ovs_bfd_session;
    int bfd_state;

    VLOG_DBG("BGP-BFD: bgp_nbr_bfd_session_ovsdb_apply_changes: %s\n", name);

    if (!ovs_nbr->bfd_session)
        return;

    ovs_bfd_session = (struct ovsrec_bfd_session *)ovs_nbr->bfd_session;

    /* BFD Session Update */
    // FIXME - Fix this to invoke only when there is a change!!
    // for some reason COL_CHANGED or ROW_CHANGED are not getting triggered
    if (COL_CHANGED(ovs_bfd_session, ovsrec_bfd_session_col_state, idl_seqno) ||
        ROW_CHANGED(ovs_bfd_session, idl_seqno) ||
        bfd_session_changed)
    {
        if (ovs_bfd_session->state) {
            bfd_state = bfd_session_state_string_to_enum (ovs_bfd_session->state);
            VLOG_DBG("BGP-BFD: BFD_Session state changed to %s for %s\n",
                     ovs_bfd_session->state, name);
            daemon_neighbor_bfd_state_cmd_execute(bgp_instance, name, bfd_state);
        }
    }
}

static void
bgp_nbr_peer_group_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    const struct ovsrec_bgp_router *ovs_bgp,
    char * name,
    struct bgp *bgp_instance)
{
    int j;

    /* peer group */
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_bgp_peer_group, idl_seqno)) {
        VLOG_DBG("Setting for peer: %s", name);
        const struct ovsrec_bgp_neighbor *peer_group = ovs_nbr->bgp_peer_group;

        for (j = 0; j < ovs_bgp->n_bgp_neighbors; j++) {
            if (ovs_bgp->value_bgp_neighbors[j] == peer_group) {
                break;
            }
        }

        if (peer_group) {
            VLOG_DBG("Binding to peergroup: %s", ovs_bgp->key_bgp_neighbors[j]);
            daemon_neighbor_set_peer_group_cmd_execute(bgp_instance,
                name, ovs_bgp->key_bgp_neighbors[j], AFI_IP, SAFI_UNICAST);
        } else {
            VLOG_DBG("Unbinding peer from peergroup");
            daemon_no_neighbor_set_peer_group_cmd_execute(bgp_instance,
                name, AFI_IP, SAFI_UNICAST);
        }
    }
}

static void
bgp_nbr_description_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    const struct ovsrec_bgp_router *ovs_bgp,
    char * name,
    struct bgp *bgp_instance)
{
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_description, idl_seqno)) {
        daemon_neighbor_description_cmd_execute(bgp_instance,
            name, ovs_nbr->description);
    }
}

static void
bgp_nbr_password_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    const struct ovsrec_bgp_router *ovs_bgp,
    char * name,
    struct bgp *bgp_instance)
{
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_password, idl_seqno)) {
        daemon_neighbor_password_cmd_execute(bgp_instance,
            name, ovs_nbr->password);
    }
}

static void
bgp_nbr_advertisement_interval_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    const struct ovsrec_bgp_router *ovs_bgp,
    char * name,
    struct bgp *bgp_instance)
{
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_advertisement_interval, idl_seqno)) {
        daemon_neighbor_advertisement_interval_cmd_execute(bgp_instance,
            name, ovs_nbr->advertisement_interval);
    }
}

static void
bgp_nbr_shutdown_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    const struct ovsrec_bgp_router *ovs_bgp,
    char * name,
    struct bgp *bgp_instance)
{
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_shutdown, idl_seqno)) {
        bool shut = ovs_nbr->n_shutdown && ovs_nbr->shutdown[0];
        daemon_neighbor_shutdown_cmd_execute(bgp_instance, name, shut);
    }
}

static void
bgp_nbr_inbound_soft_reconfig_ovsdb_apply_changes
    (const struct ovsrec_bgp_neighbor *ovs_nbr,
     const struct ovsrec_bgp_router *ovs_bgp,
     char * name,
     struct bgp *bgp_instance)
{
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_inbound_soft_reconfiguration,
        idl_seqno)) {
            bool enable =
                ovs_nbr->n_inbound_soft_reconfiguration &&
                ovs_nbr->inbound_soft_reconfiguration[0];
            daemon_neighbor_inbound_soft_reconfiguration_cmd_execute
                (bgp_instance, name, AFI_IP, SAFI_UNICAST, enable);
    }
}

static void
bgp_nbr_route_map_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    const struct ovsrec_bgp_router *ovs_bgp,
    char * name,
    struct bgp *bgp_instance)
{
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_route_maps, idl_seqno)) {
        apply_bgp_neighbor_route_map_changes(ovs_nbr, bgp_instance);
    }
}


static void
bgp_nbr_prefix_list_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    const struct ovsrec_bgp_router *ovs_bgp,
    char * name,
    struct bgp *bgp_instance)
{
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_prefix_lists, idl_seqno)) {
        apply_bgp_neighbor_prefix_list_changes(ovs_nbr, bgp_instance);
    }
}

static void
bgp_nbr_aspath_filter_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
                                           const struct ovsrec_bgp_router *ovs_bgp,
                                           char * name,
                                           struct bgp *bgp_instance)
{
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_aspath_filters, idl_seqno)) {
        apply_bgp_neighbor_aspath_filter_changes(ovs_nbr, bgp_instance);
    }
}

static void
bgp_nbr_timers_ovsdb_apply_changes(const struct ovsrec_bgp_neighbor *ovs_nbr,
                                   const struct ovsrec_bgp_router *ovs_bgp,
                                   char * name,
                                   struct bgp *bgp_instance)
{
    int keepalive = 0;
    int holdtimer = 0;
    bool set = true;

    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_timers, idl_seqno)) {
        if (ovs_nbr->n_timers) {
            keepalive = fetch_key_value(ovs_nbr->key_timers,
                                        ovs_nbr->value_timers,
                                        ovs_nbr->n_timers,
                                        OVSDB_BGP_TIMER_KEEPALIVE);
            holdtimer = fetch_key_value(ovs_nbr->key_timers,
                                        ovs_nbr->value_timers,
                                        ovs_nbr->n_timers,
                                        OVSDB_BGP_TIMER_HOLDTIME);
        } else {
            VLOG_DBG("Unsetting neighbor timers");
            set = false;
        }

        /* When !set, change is considered as unsetting. Keepalive and hold
         * timer values are not required/used in unsetting case. Only in
         * set case do we check for valid keepalive and hold timer values.
         */
        if (!set || ((keepalive >= 0) && (holdtimer >= 0))) {
            daemon_neighbor_timers_cmd_execute(bgp_instance, name,
                                               (u_int32_t)keepalive,
                                               (u_int32_t)holdtimer, set);
        } else {
            VLOG_ERR("Invalid neighbor keepalive/holdtimer");
        }
    }
}

static void
bgp_nbr_allow_as_in_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    const struct ovsrec_bgp_router *ovs_bgp,
    char * name,
    struct bgp *bgp_instance)
{
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_allow_as_in, idl_seqno)) {
        daemon_neighbor_allow_as_in_cmd_execute(bgp_instance,
            name, AFI_IP, SAFI_UNICAST, ovs_nbr->allow_as_in);
    }
}

static void
bgp_nbr_remove_private_as_ovsdb_apply_changes(
    const struct ovsrec_bgp_neighbor *ovs_nbr,
    const struct ovsrec_bgp_router *ovs_bgp,
    char *name,
    struct bgp *bgp_instance)
{
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_remove_private_as,
                    idl_seqno)) {
        bool doit = (ovs_nbr->n_remove_private_as &&
                     ovs_nbr->remove_private_as[0]);
        daemon_neighbor_remove_private_as_cmd_execute(bgp_instance,
                                                      name, AFI_IP,
                                                      SAFI_UNICAST, doit);
    }
}

static void
bgp_nbr_ebgp_multihop_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    const struct ovsrec_bgp_router *ovs_bgp,
    char * name,
    struct bgp *bgp_instance)

{
    /* ebgp-multihop */
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_ebgp_multihop, idl_seqno)) {
        bool ebgp = ovs_nbr->n_ebgp_multihop && ovs_nbr->ebgp_multihop[0];
        daemon_neighbor_ebgp_multihop_cmd_execute(bgp_instance,
            name, ebgp);
    }
}

static void
bgp_nbr_ttl_security_hops_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    const struct ovsrec_bgp_router *ovs_bgp,
    char * name,
    struct bgp *bgp_instance)
{
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_ttl_security_hops, idl_seqno)) {
        daemon_neighbor_ttl_security_hops_cmd_execute(bgp_instance,
            name, ovs_nbr->ttl_security_hops);
    }
}

static void
bgp_nbr_update_source_ovsdb_apply_changes (const struct ovsrec_bgp_neighbor *ovs_nbr,
    const struct ovsrec_bgp_router *ovs_bgp,
    char * name,
    struct bgp *bgp_instance)
{
    if (COL_CHANGED(ovs_nbr, ovsrec_bgp_neighbor_col_update_source, idl_seqno)) {
        daemon_neighbor_update_source_cmd_execute(bgp_instance,
            name, ovs_nbr->update_source);
    }
}

/*
 * Find bgp neighbor for clear counter updates
 */
static const struct ovsrec_bgp_neighbor *
get_bgp_neighbor_context (struct ovsdb_idl *idl,
                          char *name)
{
    int i, j;
    const struct ovsrec_vrf *ovs_vrf = NULL;
    const struct ovsrec_bgp_router *ovs_bgp = NULL;

    if (!name) {
        VLOG_INFO("Peer name is null for neighbor context\n");
        return NULL;
    }

    if (!idl) {
        VLOG_INFO("IDL instance for getting neighbor context is NULL\n");
        return NULL;
    }

    ovs_bgp = ovsrec_bgp_router_first(idl);
    for (j = 0; j < ovs_bgp->n_bgp_neighbors; j++) {
        if (ovs_bgp &&
           (0 == strcmp(ovs_bgp->key_bgp_neighbors[j], name))) {
           return ovs_bgp->value_bgp_neighbors[j];
        }
    }
    return NULL;
}

/*
 * Update clear counters for clear bgp neighbor soft in commands
 */

static bool
bgp_check_neighbor_clear_soft_in (struct ovsdb_idl *idl,
                                  const struct
                                  ovsrec_bgp_neighbor *neighbor_row,
                                  char *name)
{
    const struct ovsrec_bgp_neighbor *ovs_neighbor = NULL;
    int clear_bgp_neighbor_table_requested = 0;
    int clear_bgp_neighbor_table_performed = 0;
    struct smap smap_status;
    char clear_bgp_neighbor_table_str_performed[MAX_BUF_LEN] = {0};
    char clear_bgp_neighbor_table_str_requested[MAX_BUF_LEN] = {0};
    int req_cnt, perf_cnt;

    if (!idl) {
        VLOG_INFO("IDL instance for updating clear counters for"
             "clear bgp neighbor soft in commands is NULL\n");
        return false;
    }

    if (!neighbor_row) {
        VLOG_INFO("Neighbor instance for updating clear counters for"
             "clear bgp neighbor soft in commands is NULL\n");
        return false;
    }

    if (!name) {
        VLOG_INFO("Peer name updating clear counters for"
             "clear bgp neighbor soft in commands is NULL\n");
        return false;
    }

    if (object_is_peer_group(neighbor_row)) {
        VLOG_INFO("Updating clear counters for peer soft in"
                  "clear request for PEER-GROUP %s\n", name?name:"NA");
    } else {
        VLOG_INFO("Updating clear counters for peer soft in"
                  "clear request for PEER %s\n", name?name:"NA");
    }

    clear_bgp_neighbor_table_requested = smap_get_int(&neighbor_row->status,
        OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_IN_REQUESTED, 0);
    clear_bgp_neighbor_table_performed = smap_get_int(&neighbor_row->status,
        OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_IN_PERFORMED, 0);

    VLOG_INFO("request count %d, performed count %d\n",
               clear_bgp_neighbor_table_requested,
               clear_bgp_neighbor_table_performed);

    if (clear_bgp_neighbor_table_requested >
        clear_bgp_neighbor_table_performed) {
        if (object_is_peer_group(neighbor_row)) {
            daemon_bgp_clear_request(NULL, AFI_IP6, SAFI_UNICAST, clear_group,
                                     BGP_CLEAR_SOFT_IN, name);
        } else {
            daemon_bgp_clear_request(NULL, AFI_IP6, SAFI_UNICAST, clear_peer,
                                     BGP_CLEAR_SOFT_IN, name);
        }

        clear_bgp_neighbor_table_performed++;
        clear_bgp_neighbor_table_requested = clear_bgp_neighbor_table_performed;
        snprintf(clear_bgp_neighbor_table_str_performed, MAX_BUF_LEN-1, "%d",
                 clear_bgp_neighbor_table_performed);
        snprintf(clear_bgp_neighbor_table_str_requested, MAX_BUF_LEN-1, "%d",
                 clear_bgp_neighbor_table_requested);

        ovs_neighbor = get_bgp_neighbor_context(idl, name);
        if (ovs_neighbor) {
            VLOG_INFO("Adding smap\n");
            smap_init(&smap_status);
            smap_add(&smap_status,
                     OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_IN_PERFORMED,
                     clear_bgp_neighbor_table_str_performed);
            smap_add(&smap_status,
                     OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_IN_REQUESTED,
                     clear_bgp_neighbor_table_str_requested);
            ovsrec_bgp_neighbor_set_status(ovs_neighbor, &smap_status);

            req_cnt =
                smap_get_int(&ovs_neighbor->status,
                OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_IN_REQUESTED,
                0);

            perf_cnt =
                smap_get_int(&ovs_neighbor->status,
                OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_IN_PERFORMED,
                0);

            VLOG_INFO("Requested count %d, performed count %d\n",
                      req_cnt, perf_cnt);

            VLOG_INFO("Done with clear op for bgp peer soft in"
                      "requested count %d, performed count %d\n",
                      clear_bgp_neighbor_table_requested,
                      clear_bgp_neighbor_table_performed);

            smap_destroy(&smap_status);
        } else {
            VLOG_INFO("BGP neighbor row is NULL for smap set operation\n");
        }
    }
    return true;
}


/*
 * Update clear counters for clear bgp neighbor soft out commands
 */

static bool
bgp_check_neighbor_clear_soft_out (struct ovsdb_idl *idl,
                                  const struct
                                  ovsrec_bgp_neighbor *neighbor_row,
                                  char *name)
{
    const struct ovsrec_bgp_neighbor *ovs_neighbor = NULL;
    int clear_bgp_neighbor_table_requested = 0;
    int clear_bgp_neighbor_table_performed = 0;
    struct smap smap_status;
    char clear_bgp_neighbor_table_str_performed[MAX_BUF_LEN] = {0};
    char clear_bgp_neighbor_table_str_requested[MAX_BUF_LEN] = {0};
    int req_cnt, perf_cnt;

    if (!idl) {
        VLOG_INFO("IDL instance for updating clear counters for"
             "clear bgp neighbor soft out commands is NULL\n");
        return false;
    }

    if (!neighbor_row) {
        VLOG_INFO("Neighbor instance for updating clear counters for"
             "clear bgp neighbor soft out commands is NULL\n");
        return false;
    }

    if (!name) {
        VLOG_INFO("Peer name updating clear counters for"
             "clear bgp neighbor soft out commands is NULL\n");
        return false;
    }

    if (object_is_peer_group(neighbor_row)) {
        VLOG_INFO("Updating clear counters for peer soft out"
                  "clear request for PEER-GROUP %s\n", name?name:"NA");
    } else {
        VLOG_INFO("Updating clear counters for peer soft out"
                  "clear request for PEER %s\n", name?name:"NA");
    }

    clear_bgp_neighbor_table_requested = smap_get_int(&neighbor_row->status,
        OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_OUT_REQUESTED, 0);
    clear_bgp_neighbor_table_performed = smap_get_int(&neighbor_row->status,
        OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_OUT_PERFORMED, 0);

    VLOG_INFO("request count %d, performed count %d\n",
               clear_bgp_neighbor_table_requested,
               clear_bgp_neighbor_table_performed);

    if (clear_bgp_neighbor_table_requested >
        clear_bgp_neighbor_table_performed) {
        if (object_is_peer_group(neighbor_row)) {
            daemon_bgp_clear_request(NULL, AFI_IP6, SAFI_UNICAST, clear_group,
                                     BGP_CLEAR_SOFT_OUT, name);
        } else {
            daemon_bgp_clear_request(NULL, AFI_IP6, SAFI_UNICAST, clear_peer,
                                     BGP_CLEAR_SOFT_OUT, name);
        }

        clear_bgp_neighbor_table_performed++;
        clear_bgp_neighbor_table_requested = clear_bgp_neighbor_table_performed;
        snprintf(clear_bgp_neighbor_table_str_performed, MAX_BUF_LEN-1, "%d",
                 clear_bgp_neighbor_table_performed);
        snprintf(clear_bgp_neighbor_table_str_requested, MAX_BUF_LEN-1, "%d",
                 clear_bgp_neighbor_table_requested);
        /*
         * Get neighbor here
         */
        ovs_neighbor = get_bgp_neighbor_context(idl, name);
        if (ovs_neighbor) {
            VLOG_INFO("Adding smap\n");
            smap_init(&smap_status);
            smap_add(&smap_status,
                     OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_OUT_PERFORMED,
                     clear_bgp_neighbor_table_str_performed);
            smap_add(&smap_status,
                     OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_OUT_REQUESTED,
                     clear_bgp_neighbor_table_str_requested);
            ovsrec_bgp_neighbor_set_status(ovs_neighbor, &smap_status);

            req_cnt =
                smap_get_int(&ovs_neighbor->status,
                OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_OUT_REQUESTED,
                0);

            perf_cnt =
                smap_get_int(&ovs_neighbor->status,
                OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_OUT_PERFORMED,
                0);

            VLOG_INFO("Requested count %d, performed count %d\n",
                      req_cnt, perf_cnt);

            VLOG_INFO("Done with clear op for bgp peer soft out"
                      "requested count %d, performed count %d\n",
                      clear_bgp_neighbor_table_requested,
                      clear_bgp_neighbor_table_performed);

            smap_destroy(&smap_status);
        } else {
            VLOG_INFO("BGP neighbor row is NULL for smap set operation\n");
        }
    }
    return true;
}

/*
 * Do bgp nbr changes according to ovsdb changes
 */
static void
bgp_nbr_read_ovsdb_apply_changes (struct ovsdb_idl *idl, bool bfd_session_changed)
{
    const struct ovsrec_vrf *ovs_vrf = NULL;
    const struct ovsrec_bgp_router *ovs_bgp;
    const struct ovsrec_bgp_neighbor *ovs_nbr;
    struct smap_node *node;
    int64_t asn;
    char peer[80];
    int i, j;
    struct bgp *bgp_instance;
    static struct ovsdb_idl_txn *confirm_txn = NULL;
    enum ovsdb_idl_txn_status status;
    int req_cnt_in, perf_cnt_in, req_cnt_out, perf_cnt_out;

    OVSREC_VRF_FOR_EACH(ovs_vrf, idl) {
      for (i = 0; i < ovs_vrf->n_bgp_routers; i++) {
        asn = ovs_vrf->key_bgp_routers[i];
        ovs_bgp = ovs_vrf->value_bgp_routers[i];

        bgp_instance = bgp_lookup(asn, NULL);
        if (!bgp_instance) {
            VLOG_ERR("%%cannot find daemon bgp router instance %d\n", asn);
            continue;
        }
        for (j = 0; j < ovs_bgp->n_bgp_neighbors; j++) {
            ovs_nbr = ovs_bgp->value_bgp_neighbors[j];

            if (!OVSREC_IDL_IS_ROW_INSERTED(ovs_nbr, idl_seqno) &&
                !OVSREC_IDL_IS_ROW_MODIFIED(ovs_nbr, idl_seqno) &&
                !bfd_session_changed) {
                    continue;
            }

            /* If this is a new row, call the appropriate
             * daemon function depending on whether the
             * created object is a bgp peer or a bgp peer
             * group and if remote-as has been specified.
             */
            if (NEW_ROW(ovs_nbr, idl_seqno)) {
                /* Creating a peer requires that the AS be set. Only permit
                 * creating a peer if the AS is valid; otherwise, if it's
                 * a peer-group, then proceed with invoking the peer-group
                 * creation function. Once created, subsequent checks
                 * will occur for setting the AS if, in the same OVSDB
                 * transaction, the remote-as was also set.
                 */
                if (object_is_peer(ovs_nbr)) {
                    if (ovs_nbr->n_remote_as) {
                        VLOG_DBG("Creating a peer with remote-as %d",
                                 *ovs_nbr->remote_as);
                        daemon_neighbor_remote_as_cmd_execute(bgp_instance,
                            ovs_bgp->key_bgp_neighbors[j], (as_t *) ovs_nbr->remote_as,
                            AFI_IP, SAFI_UNICAST);
                    } else {
                        VLOG_ERR("Invalid remote-as for peer creation.");
                    }
                } else {
                    VLOG_DBG("Creating a peer-group");
                    daemon_neighbor_peer_group_cmd_execute(bgp_instance,
                        ovs_bgp->key_bgp_neighbors[j]);
                }
            }

            /* fallover */
            bgp_nbr_fallover_ovsdb_apply_changes(ovs_nbr,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

            /* bfd-session update */
            bgp_nbr_bfd_session_ovsdb_apply_changes(ovs_nbr,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance, bfd_session_changed);

            /* Create a confirmed database transaction for nbr updates */
            if (!confirm_txn) {
                VLOG_DBG("Check here for clear counters for neighbor %s\n"
                         ,ovs_bgp->key_bgp_neighbors[j]);
                confirm_txn = ovsdb_idl_txn_create(idl);
                bgp_check_neighbor_clear_soft_in(idl, ovs_nbr,
                                                 ovs_bgp->key_bgp_neighbors[j]);
                bgp_check_neighbor_clear_soft_out(idl, ovs_nbr,
                                                 ovs_bgp->key_bgp_neighbors[j]);

                status = ovsdb_idl_txn_commit_block(confirm_txn);
                ovsdb_idl_txn_destroy(confirm_txn);
                VLOG_DBG("Neighbor clear operation txn result: %s\n",
                         ovsdb_idl_txn_status_to_string(status));
                confirm_txn = NULL;
                req_cnt_in =
                    smap_get_int(&ovs_nbr->status,
                    OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_IN_REQUESTED,
                    0);

                perf_cnt_in =
                    smap_get_int(&ovs_nbr->status,
                    OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_IN_PERFORMED,
                    0);
                req_cnt_out =
                    smap_get_int(&ovs_nbr->status,
                    OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_OUT_REQUESTED,
                    0);

                perf_cnt_out =
                    smap_get_int(&ovs_nbr->status,
                    OVSDB_BGP_NEIGHBOR_CLEAR_COUNTERS_SOFT_OUT_PERFORMED,
                    0);

                VLOG_INFO("After neighbor clear operation txn commit:"
                          " soft in requested count %d, performed count %d;"
                          " soft out requested count %d, performed count %d\n",
                          req_cnt_in, perf_cnt_in, req_cnt_out, perf_cnt_out);
            }

        /* remote-as */
            bgp_nbr_remote_as_ovsdb_apply_changes(ovs_nbr,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

            /* peer group */
            bgp_nbr_peer_group_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

        /* description */
            bgp_nbr_description_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

        /* passwd */
            bgp_nbr_password_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

            /* shutdown */
            bgp_nbr_shutdown_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

        /* inbound_soft_reconfiguration */
            bgp_nbr_inbound_soft_reconfig_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

        /* route map */
            bgp_nbr_route_map_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

        /* prefix list */
            bgp_nbr_prefix_list_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

        /* filter list */
            bgp_nbr_aspath_filter_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

        /* timers */
            bgp_nbr_timers_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

        /* allow_as_in */
            bgp_nbr_allow_as_in_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

            /* remove_private_as */
            bgp_nbr_remove_private_as_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

            /* advertisement_interval */
            bgp_nbr_advertisement_interval_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

        /* ebgp_multihop */
            bgp_nbr_ebgp_multihop_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

        /* ttl_security_hops */
            bgp_nbr_ttl_security_hops_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

        /* update_source */
            bgp_nbr_update_source_ovsdb_apply_changes(ovs_nbr, ovs_bgp,
                ovs_bgp->key_bgp_neighbors[j], bgp_instance);

         }
      }
   }
}

/*
 * Process potential changes in the BGP_Neighbor table
 */
static void
bgp_apply_bgp_neighbor_changes (struct ovsdb_idl *idl)
{
    const struct ovsrec_bgp_bgp *ovs_bgp;
    const struct ovsrec_bgp_neighbor *ovs_nbr;
    const struct ovsrec_bfd_session *ovs_bfd_session;
    bool bfd_session_changed = false;
    struct bgp *bgp_instance;
    bool inserted = false;
    bool modified = false;
    bool deleted = false;
    u_int32_t keepalive;
    u_int32_t holdtimer;

    ovs_nbr = ovsrec_bgp_neighbor_first(idl);

    /*
     * if there are no bgp neighbor/peer-groups, there
     * are two possibilities: either nothing has been
     * created or everything has been deleted.  We have
     * to assume everything may have been deleted and
     * process accordingly.  If we assume that, obviously
     * it follows that modified or inserted can NOT be true.
     */
    if (!ovs_nbr) {
    deleted = true;
    } else {
    if (ANY_ROW_DELETED(ovs_nbr, idl_seqno)) {
        deleted = true;
    }
    if (ANY_NEW_ROW(ovs_nbr, idl_seqno)) {
        inserted = true;
    }
    if (ANY_ROW_CHANGED(ovs_nbr, idl_seqno)) {
        modified = true;
    }

        OVSREC_BFD_SESSION_FOR_EACH(ovs_bfd_session, idl) {
            if (OVSREC_IDL_IS_ROW_INSERTED(ovs_bfd_session, idl_seqno) ||
                OVSREC_IDL_IS_ROW_MODIFIED(ovs_bfd_session, idl_seqno)) {
                bfd_session_changed = true;
                break;
            }
        }
    }

    /* deletions are handled differently, do them first */
    if (deleted) {
        VLOG_DBG("Checking for any bgp neighbor/peer-group deletions\n");
        delete_bgp_neighbors_and_peer_groups(idl);
    }

    /* nothing else changed ? */
    if (!modified && !inserted && !bfd_session_changed) {
    VLOG_DBG("no other changes occured in BGP Neighbor table\n");
    return;
    }

    VLOG_DBG("now processing bgp neighbor modifications\n");
    bgp_nbr_read_ovsdb_apply_changes(idl, bfd_session_changed);
}

static const struct ovsrec_bfd_session *
find_matching_bfd_session_in_ovsdb(struct ovsdb_idl *idl, const char *remote)
{
        const struct ovsrec_bfd_session *ovs_bfd_session;

        OVSREC_BFD_SESSION_FOR_EACH(ovs_bfd_session, idl) {
                if (strcmp(ovs_bfd_session->bfd_dst_ip, remote) == 0) {
                        return ovs_bfd_session;
                }
        }
        return NULL;
}

void
bgp_create_bfd_session_in_ovsdb(char *remote, char *local, as_t asn)
{
    const struct ovsrec_bgp_neighbor *ovs_nbr;
    const struct ovsrec_bfd_session *ovs_bfd_session;
    struct ovsdb_idl_txn *ovs_txn=NULL;
    enum ovsdb_idl_txn_status status;

    VLOG_DBG("Creating BFD session in DB for remote=%s local=%s\n", remote, local);

    ovs_nbr = get_bgp_neighbor_with_VrfName_BgpRouterAsn_Ipaddr(idl, NULL, asn, remote);
    if (!ovs_nbr) {
        VLOG_ERR("BGP-BFD: BGP Neighbor not found for %s, asn=%d", remote, asn);
        return;
    }

    /*
     * TODO: bgp_txn_finish() needs be added here after rel/dill merge
     */
    ovs_txn = ovsdb_idl_txn_create(idl);

    ovs_bfd_session = find_matching_bfd_session_in_ovsdb(idl, remote);
    if (ovs_bfd_session) {
      VLOG_INFO("BFD session exists for remote=%s local=%s\n", remote, local);
      if (strcmp(ovs_bfd_session->bfd_src_ip, local) == 0) {
          VLOG_INFO("DB has the correct BFD Session info already! \n");
      } else {
          ovsrec_bfd_session_set_bfd_src_ip(ovs_bfd_session, local);
      }
    } else {
      ovs_bfd_session = ovsrec_bfd_session_insert(ovs_txn);
      if (ovs_bfd_session) {
          VLOG_DBG("New BFD Session created for remote %s local %s \n", remote, local);
          ovsrec_bfd_session_set_bfd_dst_ip(ovs_bfd_session, remote);
          ovsrec_bfd_session_set_bfd_src_ip(ovs_bfd_session, local);
          ovsrec_bfd_session_set_from(ovs_bfd_session, OVSREC_BFD_SESSION_FROM_BGP);
          ovsrec_bgp_neighbor_set_bfd_session(ovs_nbr, ovs_bfd_session);
      }
    }

    status = ovsdb_idl_txn_commit(ovs_txn);
    VLOG_DBG("BGP-BFD: create BFD Session for remote=%s local=%s : commit status %s",
             remote, local, ovsdb_idl_txn_status_to_string(status));
    ovsdb_idl_txn_destroy(ovs_txn);
}

void
bgp_delete_bfd_session_in_ovsdb(char *remote, as_t asn)
{
    const struct ovsrec_bgp_neighbor *ovs_nbr;
    const struct ovsrec_bfd_session *ovs_bfd_session;
    struct ovsdb_idl_txn *ovs_txn=NULL;
    enum ovsdb_idl_txn_status status;
    const int64_t asid = asn;

    VLOG_DBG("Delete BDF session in DB for remote=%s\n", remote);

    ovs_nbr = get_bgp_neighbor_with_VrfName_BgpRouterAsn_Ipaddr(idl, NULL, asn, remote);
    if (!ovs_nbr) {
        VLOG_ERR("BGP-BFD: BGP Neighbor not found for %s, asn=%d", remote, asn);
        return;
    }

    /*
     * TODO: bgp_txn_finish() needs be added here after rel/dill merge
     */
    ovs_txn = ovsdb_idl_txn_create(idl);

    ovs_bfd_session = find_matching_bfd_session_in_ovsdb(idl, remote);
    if (ovs_bfd_session) {
        VLOG_INFO("Session found, proceeding to delete BFD session for remote=%s \n", remote);
        ovsrec_bgp_neighbor_set_bfd_session(ovs_nbr, NULL);
        ovsrec_bfd_session_delete(ovs_bfd_session);
    }

    status = ovsdb_idl_txn_commit(ovs_txn);
    VLOG_DBG("BGP-BFD: Delete BFD Session for remote=%s: commit status %s",
            remote, ovsdb_idl_txn_status_to_string(status));
    ovsdb_idl_txn_destroy(ovs_txn);
}

static void
bgp_reconfigure (struct ovsdb_idl *idl)
{
    unsigned int new_idl_seqno = ovsdb_idl_get_seqno(idl);
    COVERAGE_INC(bgp_ovsdb_cnt);

    if (new_idl_seqno == idl_seqno){
        VLOG_DBG("No config change for bgp in ovs\n");
        return;
    }

    /*
     * Apply prefix list, community filter and route map changes
     */
    policy_prefix_list_read_ovsdb_apply_changes(idl);
    policy_community_filter_read_ovsdb_apply_changes(idl);
    policy_rt_map_read_ovsdb_apply_changes(idl);
    policy_aspath_filter_read_ovsdb_apply_changes(idl);

    /* Apply the changes */
    bgp_apply_global_changes();
    bgp_apply_bgp_router_changes(idl);
    bgp_apply_bgp_neighbor_changes(idl);

    /* Scan active route transaction list and handle completions */
    bgp_txn_complete_processing();

    /* update the seq. number */
    idl_seqno = new_idl_seqno;
}

/* Wrapper function that checks for idl updates and reconfigures the daemon
 */
static void
bgp_ovs_run ()
{
    ovsdb_idl_run(idl);
    unixctl_server_run(appctl);

    if (ovsdb_idl_is_lock_contended(idl)) {
        static struct vlog_rate_limit rl = VLOG_RATE_LIMIT_INIT(1, 1);

        VLOG_ERR_RL(&rl, "another bgpd process is running, "
                    "disabling this process until it goes away");
        return;
    } else if (!ovsdb_idl_has_lock(idl)) {
        return;
    }

    bgp_chk_for_system_configured();
    if (system_configured) {
        bgp_reconfigure(idl);
        daemonize_complete();
        vlog_enable_async();
        VLOG_INFO_ONCE("%s (OpenSwitch bgpd) %s", program_name, VERSION);
    }
}

static void
bgp_ovs_wait (void)
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
bovs_cb (struct thread *thread)
{
    bgp_ovsdb_t *bovs_g;
    if (!thread) {
        VLOG_ERR("NULL thread in read cb function\n");
        return -1;
    }
    bovs_g = THREAD_ARG(thread);
    if (!bovs_g) {
        VLOG_ERR("NULL args in read cb function\n");
        return -1;
    }

    bgp_ovs_clear_fds();
    bgp_ovs_run();
    bgp_ovs_wait();

    if (0 != bgp_ovspoll_enqueue(bovs_g)) {
        /* Could not enqueue the events. Retry in 1 sec */
        thread_add_timer(bovs_g->master, bovs_cb, bovs_g, 1);
    }
    return 1;
}

/*
 * Add the list of OVS poll fd to the master thread of the daemon
 */
static int
bgp_ovspoll_enqueue (bgp_ovsdb_t *bovs_g)
{
    struct poll_loop *loop = poll_loop();
    struct poll_node *node;
    long int timeout;
    int retval = -1;

    /* Populate with all the fds events. */
    HMAP_FOR_EACH(node, hmap_node, &loop->poll_nodes) {

        if(node->pollfd.events & POLLIN){
            thread_add_read(bovs_g->master, bovs_cb, bovs_g, node->pollfd.fd);
            bovs_g->read_cb_count++;
        }

        if(node->pollfd.events & POLLOUT){
            thread_add_write(bovs_g->master, bovs_cb, bovs_g, node->pollfd.fd);
            bovs_g->write_cb_count++;
        }
        /*
         * If we successfully connected to OVS return 0.
         * Else return -1 so that we try to reconnect.
         */
        retval = 0;
    }

    /* Populate the timeout event */
    timeout = loop->timeout_when - time_msec();
    if (timeout > 0 && loop->timeout_when > 0 &&
         loop->timeout_when < LLONG_MAX) {
        /* Convert msec to sec */
        timeout = (timeout + 999)/1000;
        thread_add_timer(bovs_g->master, bovs_cb, bovs_g, timeout);
    }
    else if (loop->timeout_when < 0){
        timeout = 0;
        thread_add_timer(bovs_g->master, bovs_cb, bovs_g, timeout);
    }

    return retval;
}

/* Initialize and integrate the ovs poll loop with the daemon */
void bgp_ovsdb_init_poll_loop (struct bgp_master *bm)
{
    if (!glob_bgp_ovs.enabled) {
        VLOG_ERR("OVS not enabled for bgp. Return\n");
        return;
    }
    bgpmaster  = bm;
    glob_bgp_ovs.master = bm->master;

    bgp_ovs_clear_fds();
    bgp_ovs_run();
    bgp_ovs_wait();
    bgp_ovspoll_enqueue(&glob_bgp_ovs);
}

static void
ovsdb_exit (void)
{
    ovsdb_idl_destroy(idl);
}

/* When the daemon is ready to shut, delete the idl cache
 * This happens with the ovs-appctl exit command.
 */
void bgp_ovsdb_exit (void)
{
    ovsdb_exit();
}
