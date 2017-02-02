

/* bgp daemon ovsdb Route table integration.
 *
 * Hewlett-Packard Company Confidential (C)
 * Copyright 2015 Hewlett-Packard Development Company, L.P.
 *
 * (c) Copyright 2015-2016 Hewlett Packard Enterprise Development LP.
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
 * File: bgp_ovsdb_route.c
 *
 * Purpose: This file interfaces with the OVSDB Route table to do the following:
 * a) Inserts all BGP routes in the BGP local Route table needed for the show commands.
 * b) Announces best route by inserting in the global Route table.
 * c) Withdraws best route by deleting the entry from the global route table.
 * d) Deletes route from local BGP Route table.
 */

#include <zebra.h>
#include "prefix.h"
#include "linklist.h"
#include "memory.h"
#include "command.h"
#include "stream.h"
#include "filter.h"
#include "str.h"
#include "log.h"
#include "routemap.h"
#include "buffer.h"
#include "sockunion.h"
#include "plist.h"
#include "thread.h"
#include "workqueue.h"
#include "ovs/hash.h"
#include "bgpd/bgpd.h"
#include "bgpd/bgp_table.h"
#include "bgpd/bgp_route.h"
#include "bgpd/bgp_attr.h"
#include "bgpd/bgp_debug.h"
#include "bgpd/bgp_aspath.h"
#include "bgpd/bgp_regex.h"
#include "bgpd/bgp_mpath.h"
#include "bgpd/bgp_ovsdb_route.h"
#include "openvswitch/vlog.h"
#include "bgpd/bgp_ovsdb_if.h"
#include "bgpd/bgp_clist.h"
#include "bgpd/bgp_filter.h"
#include "bgpd/bgp_community.h"
#include "bgpd/bgp_ecommunity.h"

#define MAX_ARGC         10
#define MAX_ARG_LEN     256

extern unsigned int idl_seqno;
extern const char *bgp_origin_str[];
extern const char *bgp_origin_long_str[];
static struct hmap global_hmap = HMAP_INITIALIZER(&global_hmap);

VLOG_DEFINE_THIS_MODULE(bgp_ovsdb_route);

/* Structure definition for path attributes data (psd) column in the
 * OVSDB BGP_Route table. These fields are owned by bgpd and shared
 * with CLI daemon.
 */
typedef struct route_psd_bgp_s {
    int flags;
    const char *aspath;
    const char *origin;
    int local_pref;
    bool internal;
    bool ibgp;
    const char *uptime;
} route_psd_bgp_t;


enum txn_bgp_request {
    TXN_BGP_ADD,
    TXN_BGP_DEL,
    TXN_BGP_UPD_ANNOUNCE,
    TXN_BGP_UPD_WITHDRAW,
    TXN_BGP_UPD_ATTR
};

char *txn_bgp_request_str[]={
    "TXN_BGP_ADD",
    "TXN_BGP_DEL",
    "TXN_BGP_UPD_ANNOUNCE",
    "TXN_BGP_UPD_WITHDRAW",
    "TXN_BGP_UPD_ATTR"
};

struct bgp_ovsdb_txn {
    struct hmap_node hmap_node;
    int    request;
    struct ovsdb_idl_txn *txn;
    as_t   as_no;
    afi_t  afi;
    safi_t safi;
    struct prefix prefix;
    struct bgp_info *bgp_info;
    unsigned int info_attr_hash;
    time_t update_time;
};

void bgp_txn_init(void);
void bgp_txn_destroy(void);
void bgp_txn_insert(struct hmap_node *txn_node);
void bgp_txn_remove(struct hmap_node *txn_node);
int route_map_action_str_to_enum(const char *action_str, int *action);
int
policy_rt_map_apply_changes (struct route_map *map,
                             const char **argv1, char **argvmatch, char **argvset,
                             int argc1, int argcmatch, int argcset,
                             unsigned long pref, int action);

static bool bgp_review(struct bgp_ovsdb_txn *txn, enum txn_op_type op, bgp_table_type_t table_type);
static uint32_t get_lookup_key(char *prefix, char *table_name);

static int
txn_command_result(enum ovsdb_idl_txn_status status, char *msg, char *pr)
{
    if ((status != TXN_SUCCESS)
        && (status != TXN_INCOMPLETE)
        && (status != TXN_UNCHANGED)) {
        VLOG_ERR("%s: Route table txn failure: %s, status %d\n",
                 __FUNCTION__, msg, status);
        return -1;
    }
    VLOG_DBG("%s %s txn sent, rc = %d\n",
             msg, pr, status);
    return 0;
}


/* Allocate a transaction recovery node, set it up and add to hmap */
#define HASH_DB_TXN(txn, req, p, info, asn, safi)                       \
    do {                                                                \
        char p_str[PREFIX_MAXLEN];                                      \
        struct bgp_ovsdb_txn *txn_rec = NULL;                           \
        txn_rec = xzalloc(sizeof (*txn_rec));                           \
        if (txn_rec == NULL) {                                          \
            VLOG_ERR("%s: %s\n",                                        \
                     __FUNCTION__, "Failed to insert txn to hash");     \
            ovsdb_idl_txn_destroy(txn);                                 \
            return -1;                                                  \
        }                                                               \
        txn_rec->request = req;                                         \
        txn_rec->txn = txn;                                             \
        memcpy (&txn_rec->prefix, p, sizeof (*p));                      \
        txn_rec->bgp_info = info;                                       \
        if (info? info->attr : 0)  {                                    \
            txn_rec->info_attr_hash = attrhash_key_make(info->attr);    \
        }                                                               \
        txn_rec->as_no = asn;                                           \
        txn_rec->afi = family2afi(p->family);                           \
        txn_rec->safi = safi;                                           \
        txn_rec->update_time = time (NULL);                             \
        bgp_txn_insert(&txn_rec->hmap_node);                            \
        prefix2str(p, p_str, sizeof(p_str));                            \
    } while (0)

#define START_DB_TXN(txn, msg, req, p, info, asn, safi)                 \
    do {                                                                \
        enum ovsdb_idl_txn_status status;                               \
        txn = ovsdb_idl_txn_create(idl);                                \
        if (txn == NULL) {                                              \
            VLOG_ERR("%s: %s\n",                                        \
                     __FUNCTION__, msg);                                \
            return -1;                                                  \
        }                                                               \
        HASH_DB_TXN(txn, req, p, info, asn, safi);                      \
    } while (0)

#define END_DB_TXN(txn, msg, pr)                          \
    do {                                                  \
        enum ovsdb_idl_txn_status status;                 \
        status = ovsdb_idl_txn_commit_block(txn);               \
        return txn_command_result(status, msg, pr);       \
    } while (0)


/* used when NO error is detected but still need to terminate */
#define ABORT_DB_TXN(txn, msg)                                      \
    do {                                                            \
        ovsdb_idl_txn_destroy(txn);                                 \
        VLOG_ERR("%s: Aborting txn: %s\n", __FUNCTION__, msg);      \
        return CMD_SUCCESS;                                         \
    } while (0)

static const char *
get_str_from_afi(u_char family)
{
    if (family == AF_INET)
        return "ipv4";
    else if (family == AF_INET6)
        return "ipv6";
    else
        return NULL;
}

static const char *
get_str_from_safi(safi_t safi)
{
    if (safi == SAFI_UNICAST)
        return "unicast";
    else if (safi == SAFI_MULTICAST)
        return "multicast";
    else if (safi == SAFI_MPLS_VPN)
        return "vpn";
    else
        return NULL;
}


const struct ovsrec_vrf*
bgp_ovsdb_get_vrf(struct bgp *bgp)
{
    int j;
    const struct ovsrec_vrf *ovs_vrf;
    /* TODO: Add support for multiple-vrf instance
    OVSREC_VRF_FOR_EACH (ovs_vrf, idl) {
        for (j = 0; j < ovs_vrf->n_bgp_routers; j ++) {
            if (ovs_vrf->key_bgp_routers[j] == (int64_t)bgp->as) {
                return ovs_vrf;
            }
        }
    }
    return NULL;
    */

    ovs_vrf = ovsrec_vrf_first(idl);
    return ovs_vrf;
}


static int
bgp_ovsdb_set_rib_path_attributes(struct smap *smap,
                                  struct bgp_info *info,
                                  struct bgp *bgp)
{
    struct attr *attr;
    struct peer *peer;
    char *comm = NULL;
    char *ecomm = NULL;
    time_t tbuf;

     if (info == NULL) {
        VLOG_DBG("In %s info is NULL", __FUNCTION__);
        return -1;
    }

    attr = info->attr;
    peer = info->peer;
    smap_add_format(smap,
                    OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_FLAGS,
                    "%d",
                    info->flags);
    smap_add(smap,
             OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_AS_PATH,
             aspath_print(info->attr->aspath));
    smap_add(smap,
             OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_ORIGIN,
             bgp_origin_str[info->attr->origin]);

    if (attr->community) {
        comm = (char *)community_str(attr->community);
    }
    if (attr->extra) {
        if (attr->extra->ecommunity) {
            ecomm =  (char *)ecommunity_str(attr->extra->ecommunity);
        }
    }
    if(comm != NULL) {
        smap_add(smap,
                 OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_COMMUNITY,
                 comm);
    } else if(comm == NULL) {
        smap_add(smap,
                 OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_COMMUNITY,
                 "");
    }
    if(ecomm != NULL) {
        smap_add(smap,
                 OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_ECOMMUNITY,
                 ecomm);
    } else if(ecomm == NULL) {
        smap_add(smap,
                 OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_ECOMMUNITY,
                 "");
    }

    smap_add_format(smap,
                    OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_LOC_PREF,
                    "%d",
                    attr->local_pref?attr->local_pref:0);
    if (attr->extra) {
        smap_add_format(smap,
                        OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_WEIGHT,
                        "%d",
                        attr->extra->weight?attr->extra->weight:0);

        if (CHECK_FLAG(attr->flag, ATTR_FLAG_BIT(BGP_ATTR_AGGREGATOR))) {
            smap_add_format(smap,
                            OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_AGGREGATOR_ID,
                            "%d",
                            attr->extra->aggregator_as?
                            attr->extra->aggregator_as:0);
            smap_add(smap,
                     OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_AGGREGATOR_ADDR,
                     inet_ntoa(attr->extra->aggregator_addr));
        } else {
            smap_add_format(smap,
                            OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_AGGREGATOR_ID,
                            "%d", 0);
            smap_add(smap,
                     OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_AGGREGATOR_ADDR,
                     "");
        }

    } else {
        smap_add_format(smap,
                        OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_WEIGHT,
                        "%d", 0);
        smap_add_format(smap,
                        OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_AGGREGATOR_ID,
                        "%d", 0);
        smap_add(smap,
                 OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_AGGREGATOR_ADDR,
                 "");
        smap_add(smap,
                OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_ECOMMUNITY,
                 "");
    }
    if (attr->flag & ATTR_FLAG_BIT(BGP_ATTR_ATOMIC_AGGREGATE)) {
        smap_add(smap,
                 OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_ATOMIC_AGGREGATE,
                 "atomic-aggregate");
    } else {
        smap_add(smap,
                 OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_ATOMIC_AGGREGATE,
                 "");
    }
    /* TODO: Check for confed flag later */
    if (peer->sort == BGP_PEER_IBGP) {
        smap_add(smap,
                 OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_INTERNAL,
                 "true");
        smap_add(smap,
                 OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_IBGP,
                 "true");

    } else if ((peer->sort == BGP_PEER_EBGP && peer->ttl != 1)
               || CHECK_FLAG (peer->flags, PEER_FLAG_DISABLE_CONNECTED_CHECK)) {
        smap_add(smap,
                 OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_INTERNAL,
                 "true");
    } else {
        smap_add(smap,
                 OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_INTERNAL,
                 "false");
        smap_add(smap,
                 OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_IBGP,
                 "false");
    }
#ifdef HAVE_CLOCK_MONOTONIC
    tbuf = time(NULL) - (bgp_clock() - info->uptime);
#else
    tbuf = info->uptime;
#endif
    smap_add(smap,
             OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_UPTIME,
             ctime(&tbuf));
    return 0;
}

static const struct ovsrec_nexthop*
bgp_ovsdb_lookup_nexthop(char *ip)
{
    const struct ovsrec_nexthop *row = NULL;
    if (!ip)
        assert(0);

    OVSREC_NEXTHOP_FOR_EACH(row, idl) {
        if (row->ip_address)
        {
            VLOG_DBG("bgp_ovsdb_lookup_nexthop IP address '%s', next record '%s'\n",
                         ip, row->ip_address);
            if (ip_addr_is_equal(ip, row->ip_address)) {
                /* Match */
                return row;
            }
        }
    }
    return NULL;
}

static const struct ovsrec_bgp_nexthop*
bgp_ovsdb_lookup_local_nexthop(char *ip)
{
    const struct ovsrec_bgp_nexthop *row = NULL;
    if (!ip)
        assert(0);

    OVSREC_BGP_NEXTHOP_FOR_EACH(row, idl) {
        if (row->ip_address)
        {
            VLOG_DBG("bgp_ovsdb_lookup_local_nexthop IP address '%s', next record '%s'\n",
                         ip, row->ip_address);
            if (ip_addr_is_equal(ip, row->ip_address)) {
                /* Match */
                return row;
            }
        }
    }
    return NULL;
}

/*
 * This function sets nexthop entries for a route in global nexthop table.
 */
static int
bgp_ovsdb_set_rib_nexthop(struct ovsdb_idl_txn *txn,
                          const struct ovsrec_route *rib,
                          struct prefix *p,
                          struct bgp_info *info,
                          int nexthop_num,
                          safi_t safi)
{
    struct bgp_info *mpinfo;
    struct in_addr *nexthop;
    struct in6_addr *nexthop6;
    struct ovsrec_nexthop **nexthop_list;
    char nexthop_buf[INET6_ADDRSTRLEN];
    const struct ovsrec_nexthop *pnexthop = NULL;
    bool selected;
    char pr[PREFIX_MAXLEN];
    const char *safi_str;
    prefix2str(p, pr, sizeof(pr));
    safi_str = get_str_from_safi(safi);
    if (strcmp(safi_str, "unicast")) {
        VLOG_ERR ("Invalid sub-address family %s for nexthop\n", safi_str);
        return -1;
    }
    if (p->family == AF_INET) {
        nexthop = &info->attr->nexthop;
        if (nexthop->s_addr == 0) {
            VLOG_INFO("%s: Nexthop address is 0 for route %s\n",
                      __FUNCTION__, pr);
            return -1;
        }
        inet_ntop(p->family, nexthop, nexthop_buf, sizeof(nexthop_buf));
    } else if (p->family == AF_INET6) {
        nexthop6 = &info->attr->extra->mp_nexthop_global;
        if (((uint32_t)(nexthop6->s6_addr[0] == 0)) &&
            ((uint32_t)(nexthop6->s6_addr[4] == 0)) &&
            ((uint32_t)(nexthop6->s6_addr[8] == 0)) &&
            ((uint32_t)(nexthop6->s6_addr[12] == 0))) {
            VLOG_INFO("%s: Nexthop6 address is 0 for route %s\n",
                      __FUNCTION__, pr);
            return -1;
        }
        inet_ntop(p->family, nexthop6, nexthop_buf, sizeof(nexthop_buf));
    }
    nexthop_list = xmalloc(sizeof *rib->nexthops * nexthop_num);
    /* Set first nexthop */
    pnexthop = bgp_ovsdb_lookup_nexthop(nexthop_buf);
    if (!pnexthop) {
        pnexthop = ovsrec_nexthop_insert(txn);
        ovsrec_nexthop_set_ip_address(pnexthop, nexthop_buf);
        VLOG_DBG("Setting nexthop IP address %s\n", nexthop_buf);
        ovsrec_nexthop_set_type(pnexthop, safi_str);
    }
    selected = 1;
    ovsrec_nexthop_set_selected(pnexthop, &selected, 1);
    nexthop_list[0] = (struct ovsrec_nexthop*) pnexthop;
    nexthop_list[0]->ip_address = xstrdup(nexthop_buf);

    int ii = 1;
    if(get_global_ecmp_status())
    {
        /* Set multipath nexthops */
        for(mpinfo = bgp_info_mpath_first (info); mpinfo;
            mpinfo = bgp_info_mpath_next (mpinfo))
        {
            /* Update the nexthop table. */
            if (p->family == AF_INET) {
                nexthop = &mpinfo->attr->nexthop;
                if (nexthop->s_addr == 0) {
                    VLOG_INFO("%s: Nexthop address is 0 for route %s\n",
                              __FUNCTION__, pr);
                    return -1;
                }
                inet_ntop(p->family, nexthop, nexthop_buf, sizeof(nexthop_buf));
            } else if (p->family == AF_INET6) {
                nexthop6 = &mpinfo->attr->extra->mp_nexthop_global;
                if (((uint32_t)(nexthop6->s6_addr[0] == 0)) &&
                   ((uint32_t)(nexthop6->s6_addr[4] == 0)) &&
                   ((uint32_t)(nexthop6->s6_addr[8] == 0)) &&
                   ((uint32_t)(nexthop6->s6_addr[12] == 0))) {
                    VLOG_INFO("%s: Nexthop6 address is 0 for route %s\n",
                              __FUNCTION__, pr);
                    return -1;
                   }
                inet_ntop(p->family, nexthop6, nexthop_buf, sizeof(nexthop_buf));
            }
            pnexthop = bgp_ovsdb_lookup_nexthop(nexthop_buf);
            if (!pnexthop) {
                pnexthop = ovsrec_nexthop_insert(txn);
                ovsrec_nexthop_set_ip_address(pnexthop, nexthop_buf);
                VLOG_DBG("Setting nexthop IP address %s, count %d\n",
                         nexthop_buf, ii);
                ovsrec_nexthop_set_type(pnexthop, safi_str);
            }
            selected = 1;
            ovsrec_nexthop_set_selected(pnexthop, &selected, 1);
            nexthop_list[ii] = (struct ovsrec_nexthop*) pnexthop;
            nexthop_list[ii]->ip_address = xstrdup(nexthop_buf);
            ii++;
        }
    }
    ovsrec_route_set_nexthops(rib, nexthop_list, nexthop_num);
    for (ii = 0; ii < nexthop_num; ii++)
        free(nexthop_list[ii]->ip_address);
    free(nexthop_list);
    return 0;
}


/*
 * This function sets nexthop entries for a route in Route table
 */
static int
bgp_ovsdb_set_local_rib_nexthop(struct ovsdb_idl_txn *txn,
                                const struct ovsrec_bgp_route *rib,
                                struct prefix *p,
                                struct bgp_info *info,
                                int nexthop_num,
                                safi_t safi)
{
    struct bgp_info *mpinfo;
    struct in_addr *nexthop;
    struct in6_addr *nexthop6;
    struct ovsrec_bgp_nexthop **nexthop_list;
    char nexthop_buf[INET6_ADDRSTRLEN];
    const struct ovsrec_bgp_nexthop *pnexthop = NULL;
    char pr[PREFIX_MAXLEN];
    const char *safi_str;

    prefix2str(p, pr, sizeof(pr));
    safi_str = get_str_from_safi(safi);
    if (strcmp(safi_str, "unicast")) {
        VLOG_ERR ("Invalid sub-address family %s for nexthop\n", safi_str);
        return -1;
    }

    if (p->family == AF_INET) {
        nexthop = &info->attr->nexthop;
        if (nexthop->s_addr == 0) {
            VLOG_INFO("%s: Nexthop address is 0 for route %s\n",
                      __FUNCTION__, pr);
            return -1;
        }
        inet_ntop(p->family, nexthop, nexthop_buf, sizeof(nexthop_buf));
    } else if (p->family == AF_INET6) {
        nexthop6 = &info->attr->extra->mp_nexthop_global;
        if (((uint32_t)(nexthop6->s6_addr[0] == 0)) &&
            ((uint32_t)(nexthop6->s6_addr[4] == 0)) &&
            ((uint32_t)(nexthop6->s6_addr[8] == 0)) &&
            ((uint32_t)(nexthop6->s6_addr[12] == 0))) {
            VLOG_INFO("%s: Nexthop6 address is 0 for route %s\n",
                      __FUNCTION__, pr);
            return -1;
        }
        inet_ntop(p->family, nexthop6, nexthop_buf, sizeof(nexthop_buf));
    }

    nexthop_list = xmalloc(sizeof *rib->bgp_nexthops * nexthop_num);

    /* Set first nexthop */
    pnexthop = bgp_ovsdb_lookup_local_nexthop(nexthop_buf);
    if (!pnexthop) {
        pnexthop = ovsrec_bgp_nexthop_insert(txn);
        ovsrec_bgp_nexthop_set_ip_address(pnexthop, nexthop_buf);
        VLOG_DBG("Setting local nexthop IP address %s\n", nexthop_buf);
        ovsrec_bgp_nexthop_set_type(pnexthop, safi_str);
    }
    nexthop_list[0] = (struct ovsrec_bgp_nexthop *) pnexthop;
    nexthop_list[0]->ip_address = xstrdup(nexthop_buf);
    int ii = 1;
    /* Set multipath nexthops */
    for(mpinfo = bgp_info_mpath_first (info); mpinfo;
        mpinfo = bgp_info_mpath_next (mpinfo))
        {
            /* Update the nexthop table. */
            if (p->family == AF_INET) {
                nexthop = &mpinfo->attr->nexthop;
                if (nexthop->s_addr == 0) {
                    VLOG_INFO("%s: Nexthop address is 0 for route %s\n",
                      __FUNCTION__, pr);
                    return -1;
                }
               inet_ntop(p->family, nexthop, nexthop_buf, sizeof(nexthop_buf));
            } else if (p->family == AF_INET6) {
                nexthop6 = &mpinfo->attr->extra->mp_nexthop_global;
                if (((uint32_t)(nexthop6->s6_addr[0] == 0)) &&
                   ((uint32_t)(nexthop6->s6_addr[4] == 0)) &&
                   ((uint32_t)(nexthop6->s6_addr[8] == 0)) &&
                   ((uint32_t)(nexthop6->s6_addr[12] == 0))) {
                   VLOG_INFO("%s: Nexthop6 address is 0 for route %s\n",
                             __FUNCTION__, pr);
                   return -1;
                }
                inet_ntop(p->family, nexthop6, nexthop_buf, sizeof(nexthop_buf));
            }
            pnexthop = bgp_ovsdb_lookup_local_nexthop(nexthop_buf);
            if (!pnexthop) {
                pnexthop = ovsrec_bgp_nexthop_insert(txn);
                ovsrec_bgp_nexthop_set_ip_address(pnexthop, nexthop_buf);
                VLOG_DBG("Setting local nexthop IP address %s, count %d\n",
                         nexthop_buf, ii);
                ovsrec_bgp_nexthop_set_type(pnexthop, safi_str);
            }
            nexthop_list[ii] = (struct ovsrec_bgp_nexthop *) pnexthop;
            nexthop_list[ii]->ip_address = xstrdup(nexthop_buf);
            ii++;
        }
    ovsrec_bgp_route_set_bgp_nexthops(rib, nexthop_list, nexthop_num);
    for (ii = 0; ii < nexthop_num; ii++)
        free(nexthop_list[ii]->ip_address);
    free(nexthop_list);
    return 0;
}

const struct ovsrec_bgp_route*
bgp_ovsdb_lookup_local_rib_entry(struct prefix *p)
{
    char pr[PREFIX_MAXLEN];
    struct lookup_hmap_element *hmap_entry = NULL;
    uint32_t lookup_hash;

    prefix2str(p, pr, sizeof(pr));
    lookup_hash = get_lookup_key(pr, BGP_ROUTE_TABLE);

    HMAP_FOR_EACH_IN_BUCKET(hmap_entry, node, lookup_hash, &global_hmap) {
        if(!strcmp(hmap_entry->prefix, pr) &&
                            (hmap_entry->table_type == BGP_ROUTE)){
            const struct ovsrec_bgp_route *ri_row =
                        ovsrec_bgp_route_get_for_uuid(idl, &hmap_entry->uuid);
            return ri_row;
        }
    }
    return NULL;
}

static void
bgp_ovsdb_get_rib_path_attributes(const struct ovsrec_bgp_route *rib_row,
                                  route_psd_bgp_t *data)
{
    const char *value;

    assert(data);
    memset(data, 0, sizeof(*data));

    data->flags = smap_get_int(&rib_row->path_attributes,
                               OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_FLAGS, 0);
    data->aspath = smap_get(&rib_row->path_attributes,
                            OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_AS_PATH);
    data->origin = smap_get(&rib_row->path_attributes,
                            OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_ORIGIN);
    data->local_pref = smap_get_int(&rib_row->path_attributes,
                                    OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_LOC_PREF, 0);
    value = smap_get(&rib_row->path_attributes,
                     OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_INTERNAL);
    if (value) {
        if (!strcmp(value, "true")) {
            data->internal = 1;
        } else {
            data->internal = 0;
        }
    }

    value = smap_get(&rib_row->path_attributes,
                     OVSDB_BGP_ROUTE_PATH_ATTRIBUTES_IBGP);
    if (value) {
        if (!strcmp(value, "true")) {
            data->ibgp = 1;
        } else {
            data->ibgp = 0;
        }
    }
    return;
}



const struct ovsrec_route*
bgp_ovsdb_lookup_rib_entry(struct prefix *p)
{
    char pr[PREFIX_MAXLEN];
    struct lookup_hmap_element *hmap_entry = NULL;
    uint32_t lookup_hash;

    prefix2str(p, pr, sizeof(pr));
    lookup_hash = get_lookup_key(pr, ROUTE_TABLE);

    HMAP_FOR_EACH_IN_BUCKET (hmap_entry, node, lookup_hash, &global_hmap) {
        if(!strcmp(hmap_entry->prefix, pr) &&
                             (hmap_entry->table_type == ROUTE)){
            const struct ovsrec_route *ri_row =
                        ovsrec_route_get_for_uuid(idl, &hmap_entry->uuid);
            return ri_row;
        }
    }

    return NULL;
}



/*
 * This function withdraws previously announced route to Zebra.
 */
int
bgp_ovsdb_withdraw_rib_entry(struct prefix *p,
                             struct bgp_info *info,
                             struct bgp *bgp,
                             safi_t safi)

{
    const struct ovsrec_route *rib_row = NULL;
    char pr[PREFIX_MAXLEN];
    struct ovsdb_idl_txn *txn = NULL;
    int flags;
    uint32_t lookup_hash;
    struct lookup_hmap_element *hmap_entry = NULL;

    prefix2str(p, pr, sizeof(pr));

    VLOG_DBG("%s: Withdrawing route %s, flags %d\n",
             __FUNCTION__, pr, info? info->flags : 0);

    lookup_hash = get_lookup_key(pr, ROUTE_TABLE);

    HMAP_FOR_EACH_IN_BUCKET(hmap_entry, node, lookup_hash, &global_hmap) {
        if(!strcmp(hmap_entry->prefix, pr)  && (hmap_entry->table_type == ROUTE)){
            if(hmap_entry->state != DB_SYNC){
                hmap_entry->needs_review = 1;
                return 0;
            }
            else {
                rib_row = ovsrec_route_get_for_uuid(idl, &hmap_entry->uuid);
                break;
            }
        }
    }

    if (!rib_row) {
        VLOG_ERR("%s: Failed to find route %s in Route table\n",
                 __FUNCTION__, pr);
        return -1;
    }

    if (CHECK_FLAG(info? info->flags : 0, BGP_INFO_SELECTED)) {
        VLOG_ERR("%s:BGP info flag is set to selected, cannot withdraw route %s",
                 __FUNCTION__, pr);
        return -1;
    }
    START_DB_TXN(txn, "Failed to create route table txn",
                 TXN_BGP_UPD_WITHDRAW, p, info, bgp->as, safi);

    /* Clear route */
    ovsrec_route_delete(rib_row);

    /* Update global hash map entry with delete operation */
    hmap_entry->needs_review = 0;
    hmap_entry->state = IN_FLIGHT;
    hmap_entry->op_type = DELETE;

    END_DB_TXN(txn, "withdraw route", pr);
}

/*
 * This function deletes a BGP route from Route table.
 */
int
bgp_ovsdb_delete_local_rib_entry(struct prefix *p,
                                 struct bgp_info *info,
                                 struct bgp *bgp,
                                 safi_t safi)
{
    const struct ovsrec_bgp_route *rib_row = NULL;
    char pr[PREFIX_MAXLEN];
    struct ovsdb_idl_txn *txn = NULL;
    struct lookup_hmap_element *hmap_entry = NULL;
    uint32_t lookup_hash;

    prefix2str(p, pr, sizeof(pr));

    VLOG_DBG("%s: Deleting route %s, flags %d\n",
             __FUNCTION__, pr, info? info->flags : 0);

    lookup_hash = get_lookup_key(pr, BGP_ROUTE_TABLE);

    HMAP_FOR_EACH_IN_BUCKET(hmap_entry, node, lookup_hash, &global_hmap) {
        if(!strcmp(hmap_entry->prefix, pr)  && (hmap_entry->table_type == BGP_ROUTE)){
            if(hmap_entry->state != DB_SYNC) {
                hmap_entry->needs_review = 1;
            }
            rib_row = ovsrec_bgp_route_get_for_uuid(idl, &hmap_entry->uuid);
            break;
        }
    }

    if (!rib_row) {
        VLOG_ERR("%s: Failed to find route %s in Route table\n",
                 __FUNCTION__, pr);
        return -1;
    }

    /*
     *
     * Disable check to allow route to be deleted regardless of flag.
     * if (CHECK_FLAG(info->flags, BGP_INFO_SELECTED)) {
     *   VLOG_ERR("%s:BGP info flag is set to selected, cannot \
     *       remove route %s", __FUNCTION__, pr);
     *   return -1;
     * }
     */
    START_DB_TXN(txn, "Failed to create route table txn",
                 TXN_BGP_DEL, p, info, bgp->as, safi);

    /* Delete route from RIB */
    ovsrec_bgp_route_delete(rib_row);

    /* Update global hash map entry with delete operation */
    hmap_entry->needs_review = 0;
    hmap_entry->state = IN_FLIGHT;
    hmap_entry->op_type = DELETE;

    END_DB_TXN(txn, "delete route", pr);
}

/*
 * This function announces best selected route to Zebra
 */
int
bgp_ovsdb_announce_rib_entry(struct prefix *p,
                             struct bgp_info *info,
                             struct bgp *bgp,
                             safi_t safi)
{
    const struct ovsrec_route *rib = NULL;
    struct ovsdb_idl_txn *txn = NULL;
    char pr[PREFIX_MAXLEN];
    const char *afi, *safi_str;
    int64_t flags = 0;
    int64_t distance = 0, nexthop_num;
    int64_t metric_val = 0;
    const struct ovsrec_vrf *vrf = NULL;
    struct smap smap;
    struct lookup_hmap_element *global_hmap_node;
    struct lookup_hmap_element *hmap_entry = NULL;
    uint32_t lookup_hash;

    prefix2str(p, pr, sizeof(pr));
    afi= get_str_from_afi(p->family);
    VLOG_DBG(" AS %d, %s: route %s\n",bgp->as,
             __FUNCTION__, pr);

    if (!afi) {
        VLOG_ERR ("Invalid address family for route %s\n", pr);
        return -1;
    }
    safi_str = get_str_from_safi(safi);
    if (!safi_str) {
        VLOG_ERR ("Invalid sub-address family for route %s\n", pr);
        return -1;
    }
    /* Lookup VRF */
    vrf = bgp_ovsdb_get_vrf(bgp);
    if (!vrf) {
        VLOG_ERR("VRF entry not found for this route %s, BGP router ASN %d\n",
                 pr, bgp->as);
        return -1;
    }

    lookup_hash = get_lookup_key(pr, ROUTE_TABLE);

    HMAP_FOR_EACH_IN_BUCKET(hmap_entry, node, lookup_hash, &global_hmap) {
        if(!strcmp(hmap_entry->prefix, pr) && (hmap_entry->table_type == ROUTE)){
            if(hmap_entry->state != DB_SYNC){
                hmap_entry->needs_review = 1;
                return 0;
            }
            else{
                rib = ovsrec_route_get_for_uuid(idl, &hmap_entry->uuid);
                break;
            }
        }
    }

    START_DB_TXN(txn, "Failed to create route table txn",
                 TXN_BGP_UPD_ANNOUNCE, p, info, bgp->as, safi);

    if (!rib) {
        VLOG_DBG("Inserting route %s\n", pr);
        rib = ovsrec_route_insert(txn);
        ovsrec_route_set_prefix(rib, pr);
        VLOG_INFO("%s: setting prefix %s\n", __FUNCTION__, pr);
        ovsrec_route_set_address_family(rib, afi);
        ovsrec_route_set_sub_address_family(rib, safi_str);
        ovsrec_route_set_from(rib, "bgp");
        /* Set VRF */
        ovsrec_route_set_vrf(rib, vrf);
        if (p->family == AF_INET) {
            distance = bgp_distance_apply (p, info, bgp);
        } else if (p->family == AF_INET6) {
            if (info->peer->sort == BGP_PEER_EBGP) {
                distance = ZEBRA_EBGP_DISTANCE_DEFAULT;
            } else {
                distance = ZEBRA_IBGP_DISTANCE_DEFAULT;
            }
        }
        VLOG_DBG("distance %d\n", distance);
        if (distance) {
            ovsrec_route_set_distance(rib, (const int64_t *)&distance, 1);
        }
        metric_val = info->attr->med;
        ovsrec_route_set_metric(rib, (const int64_t *)&metric_val, 1);

        /*Insert into global hash map, with temporary UUID*/
        global_hmap_node = malloc(sizeof(struct lookup_hmap_element));
        global_hmap_node->uuid = rib->header_.uuid;
        global_hmap_node->needs_review = 0;
        global_hmap_node->state = IN_FLIGHT;
        global_hmap_node->op_type = INSERT;
        global_hmap_node->table_type = ROUTE;
        strcpy(global_hmap_node->prefix, pr);
        hmap_insert(&global_hmap, &global_hmap_node->node, lookup_hash);
    } else
    {
        VLOG_DBG("Found route %s, updating ...\n", pr);
        /* Update global hash map entry with update operation */
        hmap_entry->needs_review = 0;
        hmap_entry->state = IN_FLIGHT;
        hmap_entry->op_type = UPDATE;
    }
    /* If global ECMP is disabled, only publish 1 path to rib */
    if(!get_global_ecmp_status()) {
        if(bgp_info_mpath_count (info)) {
            nexthop_num = 1;
            VLOG_DBG("Ecmp disable, Setting nexthop num %d, metric %d, bgp_info_flags 0x%x\n",
                      nexthop_num, info->attr->med, info->flags);
            bgp_ovsdb_set_rib_nexthop(txn, rib, p, info, nexthop_num, safi);
        }
    } else {
        nexthop_num = 1 + bgp_info_mpath_count (info);
        VLOG_DBG("Ecmp enabled, Setting nexthop num %d, metric %d, bgp_info_flags 0x%x\n",
                 nexthop_num, info->attr->med, info->flags);
        /* Nexthop list */
        bgp_ovsdb_set_rib_nexthop(txn, rib, p, info, nexthop_num, safi);
    }

    END_DB_TXN(txn, "announced route", pr);
}


/*
 * This function adds BGP route to BGP Route table
 */
int
bgp_ovsdb_add_local_rib_entry(struct prefix *p,
                              struct bgp_info *info,
                              struct bgp *bgp,
                              safi_t safi)
{
    const struct ovsrec_bgp_route *rib = NULL;
    struct ovsdb_idl_txn *txn = NULL;
    char pr[PREFIX_MAXLEN];
    const char *afi, *safi_str;
    int64_t flags = 0;
    int64_t distance = 0, nexthop_num;
    int64_t metric_val = 0;
    const struct ovsrec_vrf *vrf = NULL;
    struct smap smap;
    struct lookup_hmap_element *global_hmap_node = NULL;
    struct lookup_hmap_element *hmap_entry = NULL;
    uint32_t lookup_hash;

    prefix2str(p, pr, sizeof(pr));
    lookup_hash = get_lookup_key(pr, BGP_ROUTE_TABLE);

    HMAP_FOR_EACH_IN_BUCKET(hmap_entry, node, lookup_hash, &global_hmap) {
        if(!strcmp(hmap_entry->prefix, pr) && (hmap_entry->table_type == BGP_ROUTE)){
            if(hmap_entry->state != DB_SYNC){
                hmap_entry->needs_review = 1;
                return 0;
            }
        }
    }

    afi= get_str_from_afi(p->family);
    VLOG_DBG(" AS %d, %s ENTER: route %s\n",bgp->as,
             __FUNCTION__, pr);

    if (!afi) {
        VLOG_ERR ("Invalid address family for route %s\n", pr);
        return -1;
    }
    safi_str = get_str_from_safi(safi);
    if (!safi_str) {
        VLOG_ERR ("Invalid sub-address family for route %s\n", pr);
        return -1;
    }
    /* Lookup VRF */
    vrf = bgp_ovsdb_get_vrf(bgp);
    if (!vrf) {
        VLOG_ERR("VRF entry not found for this route %s, BGP router ASN %d\n",
                 pr, bgp->as);
        return -1;
    }

    START_DB_TXN(txn, "Failed to create bgp route table txn",
                 TXN_BGP_ADD, p, info, bgp->as, safi);
    rib = ovsrec_bgp_route_insert(txn);

    ovsrec_bgp_route_set_prefix(rib, pr);
    VLOG_INFO("%s: setting prefix %s\n", __FUNCTION__, pr);
    ovsrec_bgp_route_set_address_family(rib, afi);
    ovsrec_bgp_route_set_sub_address_family(rib, safi_str);

    /* Set Peer */
    ovsrec_bgp_route_set_peer(rib, info->peer->host);

    if (p->family == AF_INET) {
        distance = bgp_distance_apply (p, info, bgp);
    } else if (p->family == AF_INET6) {
        if (info->peer->sort == BGP_PEER_EBGP) {
            distance = ZEBRA_EBGP_DISTANCE_DEFAULT;
        } else {
            distance = ZEBRA_IBGP_DISTANCE_DEFAULT;
        }
    }
    VLOG_DBG("distance %d\n", distance);
    if (distance) {
        ovsrec_bgp_route_set_distance(rib, (const int64_t *)&distance, 1);
    }
    metric_val = info->attr->med;
    ovsrec_bgp_route_set_metric(rib, (const int64_t *)&metric_val, 1);

    /* Nexthops */
    nexthop_num = 1 + bgp_info_mpath_count (info);
    VLOG_DBG("Setting nexthop num %d, metric %d, bgp_info_flags 0x%x\n",
             nexthop_num, info->attr->med, info->flags);
    /* Nexthop list */
    bgp_ovsdb_set_local_rib_nexthop(txn, rib, p, info, nexthop_num, safi);

    /* Set VRF */
    ovsrec_bgp_route_set_vrf(rib, vrf);
    /* Set path attributes */
    smap_init(&smap);
    if (bgp_ovsdb_set_rib_path_attributes(&smap, info, bgp) == 0)
        ovsrec_bgp_route_set_path_attributes(rib, &smap);
    smap_destroy(&smap);

    /*Insert into global hash map, with temporary UUID*/
    global_hmap_node = malloc(sizeof(struct lookup_hmap_element));
    global_hmap_node->uuid = rib->header_.uuid;
    global_hmap_node->needs_review = 0;
    global_hmap_node->state = IN_FLIGHT;
    global_hmap_node->op_type = INSERT;
    global_hmap_node->table_type = BGP_ROUTE;
    strcpy(global_hmap_node->prefix, pr);
    hmap_insert(&global_hmap, &global_hmap_node->node, lookup_hash);

    END_DB_TXN(txn, "added route to local RIB, prefix:", pr);
}

/* Function updates flags for a route in local RIB */
int
bgp_ovsdb_update_local_rib_entry_attributes(struct prefix *p,
                                            struct bgp_info *info,
                                            struct bgp *bgp,
                                            safi_t safi)
{
    const struct ovsrec_bgp_route *rib_row = NULL;
    char pr[PREFIX_MAXLEN];
    struct ovsdb_idl_txn *txn = NULL;
    struct smap smap;
    struct lookup_hmap_element *hmap_entry = NULL;
    uint32_t lookup_hash;

    prefix2str(p, pr, sizeof(pr));
    lookup_hash = get_lookup_key(pr, BGP_ROUTE_TABLE);

    VLOG_DBG("%s: Updating flags for route %s, flags %d\n",
             __FUNCTION__, pr, info? info->flags : 0);

    HMAP_FOR_EACH_IN_BUCKET(hmap_entry, node, lookup_hash, &global_hmap) {
        if(!strcmp(hmap_entry->prefix, pr) && (hmap_entry->table_type == BGP_ROUTE)) {
            if(hmap_entry->state != DB_SYNC){
                hmap_entry->needs_review = 1;
                return 0;
            }
            else {
                rib_row = ovsrec_bgp_route_get_for_uuid(idl, &hmap_entry->uuid);
                break;
            }
        }
    }

    if (!rib_row) {
        VLOG_ERR("%s: Failed to find route %s in Route table\n",
                 __FUNCTION__, pr);
        return -1;
    }

    VLOG_DBG("%s: Found route %s from peer %s\n", __FUNCTION__,
                 pr, info? (info->peer? info->peer->host: "NULL") :"NULL");

    START_DB_TXN(txn, "Failed to create route table txn",
                 TXN_BGP_UPD_ATTR, p, info, bgp->as, safi);
    smap_init(&smap);
    if (bgp_ovsdb_set_rib_path_attributes(&smap, info, bgp) == 0)
        ovsrec_bgp_route_set_path_attributes(rib_row, &smap);
    smap_destroy(&smap);

    /* Update global hash map entry with update operation */
    hmap_entry->needs_review = 0;
    hmap_entry->state = IN_FLIGHT;
    hmap_entry->op_type = UPDATE;

    END_DB_TXN(txn, "update route", pr);
}

static struct hmap bgp_ovsdb_txn_hmap =
              HMAP_INITIALIZER(&bgp_ovsdb_txn_hmap);

void
bgp_txn_init(void) {
    hmap_init(&bgp_ovsdb_txn_hmap);
}

void
bgp_txn_destroy(void) {
    hmap_destroy(&bgp_ovsdb_txn_hmap);
}

void
bgp_txn_insert(struct hmap_node *txn_node) {
    hmap_insert(&bgp_ovsdb_txn_hmap, txn_node, hash_pointer(txn_node, 0));
}

void
bgp_txn_remove(struct hmap_node *txn_node) {
    hmap_remove(&bgp_ovsdb_txn_hmap, txn_node);
}

/*
 * Check if an OVSDB route exists for a given BGP route transaction
 * in local RIB table.
 * The reason for this verification is that BGP and OVSDB can get
 * out of sync
 */
static bool
bgp_txn_local_route_found(struct bgp_ovsdb_txn *txn)
{
    struct bgp *bgp = bgp_lookup(txn->as_no, NULL);

    if (bgp && bgp_ovsdb_lookup_local_rib_entry(&txn->prefix)) {
        return true;
    } else {
        return false;
    }
}

/*
 * Check if an OVSDB route exists for a given BGP route transaction
 * in Global Route table.
 * The reason for this verification is that BGP and OVSDB can get
 * out of sync
 */
static bool
bgp_txn_route_found(struct bgp_ovsdb_txn *txn)
{
    struct bgp *bgp = bgp_lookup(txn->as_no, NULL);

    if (bgp && bgp_ovsdb_lookup_rib_entry(&txn->prefix)) {
        return true;
    } else {
        return false;
    }
}

/*
 * Traverse bgp_info link list off of bgp_node and look for
 * a bgp_info match as well as an attribute hash match
 */
static bool
bgp_info_found(struct bgp *bgp, struct bgp_ovsdb_txn *txn)
{
    struct bgp_node *rn;
    struct bgp_info *ri;

    rn = bgp_node_get (bgp->rib[txn->afi][txn->safi], &txn->prefix);
    if (rn == NULL) {
        VLOG_ERR("BGP info found is NULL\n");
        return false;
    }

    for (ri = rn->info; ri; ri = ri->next) {
        /* compare transaction's bgp_info to bgp's */
        if ( (ri == txn->bgp_info) &&
        /* compare attribute hash */
             (ri->attr &&
             (txn->info_attr_hash == attrhash_key_make(ri->attr))))
        {
            route_unlock_node((struct route_node *)rn);
            return true;
        }
    }
    route_unlock_node((struct route_node *)rn);
    return false;
}

/*
 * Free up a transaction entry
 * out of sync
 */
static void
bgp_txn_free(struct bgp_ovsdb_txn *txn)
{
    ovsdb_idl_txn_destroy(txn->txn);
    bgp_txn_remove (&txn->hmap_node);
    free(txn);
}

/*
 * Log unexpected transaction completion
 */
static void
bgp_txn_log(struct bgp_ovsdb_txn *txn, int status)
{
    char prefix_str[PREFIX_MAXLEN];

    prefix2str(&txn->prefix, prefix_str, sizeof(prefix_str));
    VLOG_DBG("Active Transaction for route %s at time %lld status=%d",
              prefix_str, txn->update_time, status);
}

/*
 *
 * Invoke HMAP_FOR_EACH (txn, txn_node, &bgp_ovsdb_txn_hmap)
 * to walk over all outstanding transactions in list {
 *    if ( transaction complete successfully ) {
 *          ovsdb_idl_txn_destroy()
 *          bgp_txn_remove (txn_node)
 *    } else
 *    if ( transaction incompete and !timeout ) {
 *          VLOG_DBG
 *          skip txn
 *    } else
 *    if ( (ADD_REQ ||
 *          ADD_UPD_ANNOUNCE ||
 *          ADD_UPD_WITHDRAW ||
 *          ADD_UPD_FLAGS) &&
 *          bgp_route_lookup(txn_node) ) {
 *          add/update route in OVSDB
 *          ovsdb_idl_txn_destroy()
 *          bgp_txn_remove (txn_node)
 *    } else
 *    if ( DEL_REQ && !bgp_route_lookup(txn_node) ) {
 *          delete route from OVSDB
 *          ovsdb_idl_txn_destroy()
 *          bgp_txn_remove (txn_node)
 *    } else
 *          VLOG_ERR
 *          ovsdb_idl_txn_destroy()
 *          bgp_txn_remove (txn_node)
 *    }
 * }
 *
 */

static int skip_txn=0;
void
bgp_txn_complete_processing(void)
{
    struct bgp_ovsdb_txn *txn;
    struct bgp *bgp;
    enum   ovsdb_idl_txn_status status;
    char prefix_str[PREFIX_MAXLEN];
    struct lookup_hmap_element *hmap_entry = NULL;
    uint32_t lookup_hash;
    bgp_table_type_t table_type;
    int needs_review;
    enum txn_op_type op_type;

    HMAP_FOR_EACH (txn, hmap_node, &bgp_ovsdb_txn_hmap) {
        /* Get commit status for transaction */
        status = ovsdb_idl_txn_commit_block(txn->txn);
        prefix2str(&txn->prefix, prefix_str, sizeof(prefix_str));

        /* log transaction */
        bgp_txn_log(txn, status);

        /* Clean up an free txn on success */
        if ((status == TXN_SUCCESS) || (status == TXN_UNCHANGED) ||
            (status == TXN_ABORTED) || (status == TXN_ERROR)) {
            if (status != TXN_SUCCESS) {
                bgp_txn_log(txn, status);
            }

            if((status == TXN_SUCCESS) || (status == TXN_UNCHANGED))
            {
                /* Identify table type and compute hash key based on request */
                if ((txn->request == TXN_BGP_ADD) || (txn->request ==
                           TXN_BGP_DEL) || (txn->request == TXN_BGP_UPD_ATTR)){
                    table_type = BGP_ROUTE;
                    lookup_hash = get_lookup_key(prefix_str, BGP_ROUTE_TABLE);
                }
                else if (txn->request == TXN_BGP_UPD_ANNOUNCE ||
                             txn->request == TXN_BGP_UPD_WITHDRAW){
                    table_type = ROUTE;
                    lookup_hash = get_lookup_key(prefix_str, ROUTE_TABLE);
                }

                /* Find node in global hash map, and update real UUID */
                HMAP_FOR_EACH_IN_BUCKET (hmap_entry, node, lookup_hash,
                                                        &global_hmap) {
                    if (!strcmp(hmap_entry->prefix, prefix_str) &&
                                        (table_type == hmap_entry->table_type)){

                        table_type = hmap_entry->table_type;
                        needs_review = hmap_entry->needs_review;
                        op_type = hmap_entry->op_type;

                        /* If last operation was Delete, remove node from map*/
                        if (hmap_entry->op_type == DELETE) {
                            hmap_remove(&global_hmap, &(hmap_entry->node));
                            free(hmap_entry);
                        }
                        /* If last operation was Insert/Update, hash
                           node is updated */
                        else {
                            hmap_entry->state = DB_SYNC;
                            hmap_entry->needs_review = 0;
                            const struct uuid *db_uuid =
                                ovsdb_idl_txn_get_insert_uuid(txn->txn,
                                                             &(hmap_entry->uuid));
                            if(db_uuid != NULL) {
                                hmap_entry->uuid = *(db_uuid);
                            }
                        }
                        if(needs_review == 1)
                            bgp_review(txn, op_type, table_type);

                        break;
                    }
                }
            }
            bgp_txn_free(txn);
            continue;
        }

        /* If incomplete allow more time to complete */
        if (status == TXN_INCOMPLETE){
            VLOG_DBG("Route transaction incomplete as=%d prefix=%s time=%lld",
                     txn->as_no, prefix_str, txn->update_time);
            continue;
        }

        /*
         * Handle all error cases
         */

        /* Get bgp pointer correspending to as_no */
        bgp = bgp_lookup(txn->as_no, NULL);
        if (bgp == NULL) {
            bgp_txn_free(txn);
            VLOG_ERR("Route transaction bgp mismatch as=%d prefix=%s",
                     txn->as_no, prefix_str);
            continue;
        }
        /* Search bgp route info linked list for txn->bgp_info */
        if (!bgp_info_found(bgp, txn)) {
            bgp_txn_free(txn);
            VLOG_ERR("Route transaction bgp_info mismatch as=%d prefix=%s",
                     txn->as_no, prefix_str);
            continue;
        }

        /* In case the transaction is inconsistent with OVSDB,
           don't add/update */

        if ((txn->request == TXN_BGP_ADD) &&
            !bgp_txn_local_route_found(txn)) {
            /* add route in OVSDB route table */
            bgp_ovsdb_add_local_rib_entry(&txn->prefix,
                                          txn->bgp_info, bgp, txn->safi);
            bgp_txn_free(txn);
        } else
        if ((txn->request == TXN_BGP_UPD_ANNOUNCE) &&
            bgp_txn_route_found(txn)) {
            /* announce route in OVSDB route table */
            bgp_ovsdb_announce_rib_entry(&txn->prefix,
                                         txn->bgp_info, bgp, txn->safi);
            bgp_txn_free(txn);
        } else
        if ((txn->request == TXN_BGP_UPD_WITHDRAW) &&
            bgp_txn_route_found(txn)) {
            /* withdraw route from OVSDB route table */
            bgp_ovsdb_withdraw_rib_entry(&txn->prefix,
                                         txn->bgp_info, bgp, txn->safi);
            bgp_txn_free(txn);
        } else
        if ((txn->request == TXN_BGP_UPD_ATTR) &&
            bgp_txn_local_route_found(txn)) {
            /* update route flags in OVSDB route table */
            bgp_ovsdb_update_local_rib_entry_attributes(&txn->prefix,
                                                        txn->bgp_info, bgp, txn->safi);
            bgp_txn_free(txn);
        } else
        if ((txn->request == TXN_BGP_DEL) &&
            bgp_txn_local_route_found(txn)) {
            /* delete route from OVSDB route table */
            bgp_ovsdb_delete_local_rib_entry(&txn->prefix,
                                             txn->bgp_info, bgp, txn->safi);
            bgp_txn_free(txn);
        } else {
            /* Fall back - if can't recover free up txn */
            prefix2str(&txn->prefix, prefix_str, sizeof(prefix_str));
            VLOG_ERR("Route request %s recovey failure as=%d prefix=%s",
                     txn_bgp_request_str[txn->request],
                     txn->as_no, prefix_str);
            bgp_txn_free(txn);
        }
    }
}



struct lookup_entry {
   int index;
   char *cli_cmd;
   char *table_key;
};

/*
 * Translation table from ovsdb to guagga
 */
const struct lookup_entry match_table[]={
  {MATCH_PREFIX, "ip address prefix-list", "prefix_list"},
  {MATCH_IPV6_PREFIX, "ipv6 address prefix-list", "ipv6_prefix_list"},
  {MATCH_COMMUNITY, "community", "community"},
  {MATCH_EXTCOMMUNITY, "extcommunity", "extcommunity"},
  {MATCH_ASPATH, "as-path", "as_path"},
  {MATCH_ORIGIN, "origin", "origin"},
  {MATCH_METRIC, "metric", "metric"},
  {MATCH_IPV6_NEXTHOP, "ipv6 next-hop","ipv6_next_hop"},
  {MATCH_PROBABILITY, "probability","probability"},
  {0, NULL, NULL},
};

const struct lookup_entry set_table[]={
  {SET_COMMUNITY, "community", "community"},
  {SET_METRIC, "metric", "metric"},
  {SET_AGGREGATOR_AS, "aggregator as", "aggregator_as"},
  {SET_AS_PATH_EXCLUDE, "as-path exclude", "as_path_exclude"},
  {SET_AS_PATH_PREPEND, "as-path prepend", "as_path_prepend"},
  {SET_ATOMIC_AGGREGATE, "atomic-aggregate", "atomic_aggregate"},
  {SET_COMM_LIST, "comm-list", "comm_list"},
  {SET_ECOMMUNITY_RT, "extcommunity rt", "extcommunity_rt"},
  {SET_ECOMMUNITY_SOO, "extcommunity soo", "extcommunity_soo"},
  {SET_IPV6_NEXT_HOP_GLOBAL, "ipv6 next-hop global", "ipv6_next_hop_global"},
  {SET_LOCAL_PREFERENCE, "local-preference", "local_preference"},
  {SET_ORIGIN, "origin", "origin"},
  {SET_WEIGHT, "weight", "weight"},
  {0, NULL, NULL},
};

/*
 * Free memory allocated for argv list
 */
void
policy_ovsdb_free_arg_list(char ***parmv, int argcsize)
{
    int i;
    char ** argv = *parmv;

    if (argv == NULL) return;

    for (i = 0; i < argcsize; i ++)
    {
        if (argv[i]) {
            free(argv[i]);
            argv[i] = NULL;
        }
    }
    free(argv);
    argv = NULL;
    *parmv = argv;
}

/*
 * Allocate memory for argv list
 */
char **
policy_ovsdb_alloc_arg_list(int argcsize, int argvsize)
{
    int i;
    char ** parmv = NULL;

    parmv = xmalloc(sizeof (char *) * argcsize);
    if (!parmv)
        return NULL;

    for (i = 0; i < argcsize; i ++)
      {
        parmv[i] = xmalloc(sizeof(char) * argvsize);
        if (!(parmv[i])) {
            policy_ovsdb_free_arg_list(&parmv, argcsize);
            return NULL;
        }
      }

    return parmv;
}

void
policy_rt_map_read_ovsdb_apply_deletion (struct ovsdb_idl *idl)
{
    const struct ovsrec_route_map *ovs_map, *ovs_first;
    int matched = 0;
    struct route_map * map;

    /* route map */
    ovs_first = ovsrec_route_map_first(idl);
    if (ovs_first && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ovs_first, idl_seqno)) {
        VLOG_DBG("No route map rows were deleted");
        return;
    }

    for (map = route_map_master.head; map; map = map->next) {
        matched = 0;
        OVSREC_ROUTE_MAP_FOR_EACH(ovs_map, idl) {
            if (strcmp (map->name, ovs_map->name) == 0) {
                matched = 1;
                break;
            }
        }

        if (!matched) {
            route_map_delete (map);
            VLOG_DBG("Route map row deleted");
        }
    }
}

void
policy_rt_map_entry_read_ovsdb_apply_deletion (struct ovsdb_idl *idl)
{
    const struct ovsrec_route_map_entry *ovs_first;
    const struct ovsrec_route_map *ovs_map;
    struct route_map_index *index;
    struct route_map * map;
    int matched = 0;
    int i;

    /* route map entry */
    ovs_first = ovsrec_route_map_entry_first(idl);
    if (ovs_first && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ovs_first, idl_seqno)) {
        VLOG_DBG("No route map entry deletions detected.");
        return;
    }

    VLOG_DBG("Checking for route map entry deletions");
    for (map = route_map_master.head; map; map = map->next) {
        VLOG_DBG("Finding route-map with name: %s", map->name);

        OVSREC_ROUTE_MAP_FOR_EACH(ovs_map, idl) {
            VLOG_DBG("Comparing against route-map with name: %s",
                     ovs_map->name);

            if (strcmp (map->name, ovs_map->name) == 0) {
                for (index = map->head; index; index = index->next) {
                    VLOG_DBG("Checking pref %lld", index->pref);

                    matched = 0;
                    for (i = 0; i < ovs_map->n_route_map_entries; i ++) {
                        VLOG_DBG("Checking against pref %lld", index->pref);

                        if (index->pref == ovs_map->key_route_map_entries[i]) {
                            matched = 1;
                            break;
                        }
                    }

                    if (!matched) {
                        route_map_index_delete (index, 1);
                        VLOG_DBG("Route map entry deleted");
                    }
                }
            }
        }
    }
}

void
policy_rt_map_description_ovsdb_apply_changes(
    struct ovsrec_route_map_entry *ovs_entry,
    char **argv1, int *argc)
{
    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_route_map_entry_col_description,
                                      idl_seqno)) {
        VLOG_DBG("Route-map description was modified");
        *argc = RT_MAP_DESCRIPTION;
        if (ovs_entry->description) {
            VLOG_DBG("Setting description %s", ovs_entry->description);
            strcpy(argv1[RT_MAP_DESCRIPTION], ovs_entry->description);
        } else {
            VLOG_DBG("Unsetting description");
            argv1[RT_MAP_DESCRIPTION] = NULL;
        }
    }
}

void
policy_rt_map_match_ovsdb_apply_changes(
    struct ovsrec_route_map_entry *ovs_entry,
    struct route_map *map, unsigned long pref, int action,
    char **argv, int *argc)
{
    VLOG_DBG("Checking for route map match changes...");
    struct route_map_rule_cmd *cmd;
    struct route_map_index *index;
    char *match_name;
    const char *tmp;

    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_route_map_entry_col_match,
                                      idl_seqno)) {
        VLOG_DBG("Route map match was changed. Detecting additions/deletions.");
        int i;
        for (i = 0, *argc = 0; match_table[i].table_key; i++) {
            VLOG_DBG("Checking value for: %s", match_table[i].table_key);

            tmp  = smap_get(&ovs_entry->match, match_table[i].table_key);
            match_name = match_table[i].cli_cmd;
            if (tmp) {
                VLOG_DBG("Value was set with: %s", tmp);
                strcpy(argv[(*argc)++], match_name);
                strcpy(argv[(*argc)++], tmp);
            } else {
                VLOG_DBG("Value was not set. Detecting deletion.");

                /* Value was not found in the ovsdb record, check if
                 * it exists in BGP. If exists, then indicates it was deleted.
                 */
                index = route_map_index_lookup(map, action, pref);
                if (index) {
                    /* Attempt to delete the match rule. */
                    if (route_map_delete_match(index, match_name, NULL) == 0) {
                        VLOG_DBG("Route map match deleted");
                    }
                }
            }
        }
    }
}

void
policy_rt_map_set_ovsdb_apply_changes(
    struct ovsrec_route_map_entry *ovs_entry,
    struct route_map *map, unsigned long pref, int action,
    char **argv, int *argc)
{
    VLOG_DBG("Checking for route map set changes...");
    struct route_map_rule_cmd *cmd;
    struct route_map_index *index;
    char *set_name;
    const char *tmp;

    if (OVSREC_IDL_IS_COLUMN_MODIFIED(ovsrec_route_map_entry_col_set,
                                      idl_seqno)) {
        VLOG_DBG("Route map set was changed. Detecting additions/deletions.");
        int i;
        for (i = 0, *argc = 0; set_table[i].table_key; i++) {
            VLOG_DBG("Checking value for: %s", set_table[i].table_key);

            tmp  = smap_get(&ovs_entry->set, set_table[i].table_key);
            set_name = set_table[i].cli_cmd;
            if (tmp) {
                VLOG_DBG("Value was set with: %s", tmp);
                strcpy(argv[(*argc)++], set_name);
                strcpy(argv[(*argc)++], tmp);
            } else {
                VLOG_DBG("Value was not set. Detecting deletion.");

                /* Value was not found in the ovsdb record, check if
                 * it exists in BGP. If exists, then indicates it was deleted.
                 */
                index = route_map_index_lookup(map, action, pref);
                if (index) {
                    /* Attempt to delete the set rule. */
                    if (route_map_delete_set(index, set_name, NULL) == 0) {
                        VLOG_DBG("Route map set deleted");
                    }
                }
            }
        }
    }
}

/*
 * route-map RM_TO_UPSTREAM_PEER permit 10
 */
/*
 * Read rt map config from ovsdb to argv
 */
void
policy_rt_map_do_change(struct ovsdb_idl *idl,
                        char **argv1, char **argvmatch, char **argvset)
{
    const struct ovsrec_route_map * ovs_map;
    struct ovsrec_route_map_entry * ovs_entry;
    struct route_map *map;
    unsigned long pref;
    int argc1 = 0, argcmatch = 0, argcset = 0;
    int i;
    int rmap_action;

    /*
     * Read from ovsdb
     */
    OVSREC_ROUTE_MAP_FOR_EACH(ovs_map, idl) {
        strcpy(argv1[RT_MAP_NAME], ovs_map->name);
        argc1 = RT_MAP_NAME;

        /* Get route map associated with the provided name. */
        VLOG_DBG("Configuring for route-map with name: %s", argv1[RT_MAP_NAME]);
        map = route_map_get(argv1[RT_MAP_NAME]);

        for (i = 0; i < ovs_map->n_route_map_entries; i ++) {
            ovs_entry = ovs_map->value_route_map_entries[i];
            if (!(OVSREC_IDL_IS_ROW_INSERTED(ovs_entry, idl_seqno)) &&
                !(OVSREC_IDL_IS_ROW_MODIFIED(ovs_entry, idl_seqno))) {
                continue;
            }

            strcpy(argv1[RT_MAP_ACTION], ovs_entry->action);
            /* Convert route-map action string and check if valid. */
            if (route_map_action_str_to_enum(argv1[RT_MAP_ACTION],
                                             &rmap_action) != CMD_SUCCESS) {
                VLOG_ERR("Invalid action");
                return;
            }

            argc1 = RT_MAP_ACTION;
            pref = ovs_map->key_route_map_entries[i];
            /* Preference check. */
            if ((pref == ULONG_MAX) || (pref == 0) || (pref > 65535)) {
                VLOG_ERR("Invalid pref value");
                return;
            }

            policy_rt_map_description_ovsdb_apply_changes(ovs_entry, argv1,
                                                          &argc1);

            policy_rt_map_match_ovsdb_apply_changes(ovs_entry, map, pref,
                                                    rmap_action, argvmatch,
                                                    &argcmatch);

            policy_rt_map_set_ovsdb_apply_changes(ovs_entry, map, pref,
                                                  rmap_action, argvset,
                                                  &argcset);

            /*
             * programming back end
             */
            policy_rt_map_apply_changes(map, (const char **) argv1, argvmatch, argvset, argc1,
                                        argcmatch, argcset, pref, rmap_action);
        }
    }
}

int
policy_rt_map_read_ovsdb_apply_changes (struct ovsdb_idl *idl)
{
    char **argv1;
    char **argvmatch;
    char **argvset;
    const struct ovsrec_route_map_entry * rt_map_first;
    const struct ovsrec_route_map_entry * rt_map_next;

    /* Handle route map deletion */
    policy_rt_map_read_ovsdb_apply_deletion (idl);

    /* Handle route map entry deletion */
    policy_rt_map_entry_read_ovsdb_apply_deletion (idl);

    /* handle route map insert/change case */
    rt_map_first = ovsrec_route_map_entry_first(idl);
    if (rt_map_first == NULL) {
        VLOG_DBG("Nothing was configured for route map");
        return CMD_SUCCESS;
    }

    if (!(OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED(rt_map_first, idl_seqno)) &&
        !(OVSREC_IDL_ANY_TABLE_ROWS_INSERTED(rt_map_first, idl_seqno))) {
        VLOG_DBG("Nothing was changed for route map");
        return CMD_SUCCESS;
    }

    /* Alloc three argv lists */
    if (!(argv1 = policy_ovsdb_alloc_arg_list(MAX_ARGC, MAX_ARG_LEN)) ||
        !(argvmatch = policy_ovsdb_alloc_arg_list(MAX_ARGC, MAX_ARG_LEN)) ||
        !(argvset = policy_ovsdb_alloc_arg_list(MAX_ARGC, MAX_ARG_LEN))) {
        VLOG_ERR("Memory allocation failed for working buffer\n");
        return CMD_SUCCESS;
    }

    policy_rt_map_do_change(idl, argv1, argvmatch, argvset);

    policy_ovsdb_free_arg_list(&argv1, MAX_ARGC);
    policy_ovsdb_free_arg_list(&argvmatch, MAX_ARGC);
    policy_ovsdb_free_arg_list(&argvset, MAX_ARGC);

    return CMD_SUCCESS;
}

/*
 * Log info
 */
int
policy_ovsdb_rt_map_vlog(int ret)
{
    if (ret)
    {
        switch (ret)
        {
        case RMAP_RULE_MISSING:
        VLOG_INFO("%% Can't find rule.\n");
            return CMD_WARNING;
        case RMAP_COMPILE_ERROR:
            VLOG_INFO("%% Argument is malformed.\n");
            return CMD_WARNING;
        }
    }
    return CMD_SUCCESS;
}

int route_map_action_str_to_enum(const char *action_str, int *action) {
    if (!action_str || !action_str[0]) {
        VLOG_ERR("Invalid action string");
        return CMD_WARNING;
    }

    int action_len = strlen(action_str);
    if (strncmp(action_str, "permit", action_len) == 0)
        *action = RMAP_PERMIT;
    else if (strncmp(action_str, "deny", action_len) == 0)
        *action = RMAP_DENY;
    else
        return CMD_WARNING;

    return CMD_SUCCESS;
}

/*
 * Set up route map at the back end
 * Read from ovsdb, then program back end policy route map
 *
 * Specific cli command:
 * route-map RM_TO_UPSTREAM_PEER permit 10
 */
int
policy_rt_map_apply_changes (struct route_map *map,
                             const char **argv1, char **argvmatch, char **argvset,
                             int argc1, int argcmatch, int argcset,
                             unsigned long pref, int action)
{
    int i;
    int ret;
    struct route_map_index *index;

    if (!argc1) {
        VLOG_DBG("Nothing to configure for route-map");
        return CMD_SUCCESS;
    }

    index = route_map_index_get(map, action, pref);

    if (!index) {
        VLOG_ERR("Route map not found");
        return CMD_SUCCESS;
    }

    if (argc1 == RT_MAP_DESCRIPTION) {
        if (index->description)
            XFREE (MTYPE_TMP, index->description);

        index->description = argv1[RT_MAP_DESCRIPTION] ?
                                argv_concat (&argv1[RT_MAP_DESCRIPTION], 1, 0) :
                                NULL;
    }

    /*
    * Add route map match command
    */
    for (i = 0; i < argcmatch; i += 2) {
        ret = route_map_add_match (index, argvmatch[i], argvmatch[i+1]);
        /* log if error */
        ret = policy_ovsdb_rt_map_vlog(ret);
    }

    /*
    * Add route map set command
    */
    for (i = 0; i < argcset; i += 2) {
        ret = route_map_add_set (index, argvset[i], argvset[i+1]);
        ret = policy_ovsdb_rt_map_vlog(ret);
    }

    return CMD_SUCCESS;
}

int
prefix_list_type_str_to_enum(char *typestr, enum prefix_list_type *type)
{
    /* Check filter type. */
    if (strncmp("permit", typestr, 1) == 0)
        *type = PREFIX_PERMIT;
    else if (strncmp("deny", typestr, 1) == 0)
        *type = PREFIX_DENY;
    else
        return CMD_WARNING;

    return CMD_SUCCESS;
}

static int
invalid_prefix_range (const char *prefix)
{
  VLOG_DBG("Invalid prefix range for i %s, make sure:"
             " len < ge-value <= le-value",prefix);

  return CMD_SUCCESS;
}

int
prefix_list_desc_unset ( char *name)
{
    struct prefix_list *plist;
    plist = prefix_list_lookup (AFI_IP6, name);

    VLOG_DBG("Deleting prefix list %s description %s",plist->name,plist->desc);

    if (plist->desc) {
        XFREE (MTYPE_TMP, plist->desc);
        plist->desc = NULL;
    }

    if (plist->head == NULL && plist->tail == NULL && plist->desc == NULL) {
        prefix_list_delete (plist);
    }

    return CMD_SUCCESS;
}

/*
 * Get prefix configuration from ovsdb database
 */
int
policy_prefix_list_apply_changes (struct ovsdb_idl *idl, afi_t afi,
                        char **argv1, char **argvseq,
                        int argc1, int argcseq,
                        unsigned long seqnum)
{
    int ret;
    enum prefix_list_type type;
    struct prefix_list *plist;
    struct prefix_list_entry *pentry;
    struct prefix_list_entry *dup;
    struct prefix p;
    int any = 0;
    int lenum = 0;
    int genum = 0;


    if (!argc1) {
        return CMD_SUCCESS;
    }
    /* Get prefix_list with name. */
    plist = prefix_list_get (afi, argv1[PREFIX_LIST_NAME]);

    if (prefix_list_type_str_to_enum(argv1[PREFIX_LIST_ACTION],
                                   &type) != CMD_SUCCESS) {
        VLOG_ERR("Invalid prefix-list type");
        return CMD_SUCCESS;
    }

    /* ge and le number */
    if (argv1[PREFIX_LIST_GE]) {
        genum = atoi (argv1[PREFIX_LIST_GE]);
    }
    if (argv1[PREFIX_LIST_LE]){
        lenum = atoi (argv1[PREFIX_LIST_LE]);
    }


    if (afi == AFI_IP) {
        if (strncmp ("any", argv1[PREFIX_LIST_PREFIX],
                 strlen (argv1[PREFIX_LIST_PREFIX])) == 0) {
            ret = str2prefix_ipv4 ("0.0.0.0/0", (struct prefix_ipv4 *) &p);
            genum = 0;
            lenum = IPV4_MAX_BITLEN;
            any = 1;
        } else {
            ret = str2prefix_ipv4 (argv1[PREFIX_LIST_PREFIX],
                              (struct prefix_ipv4 *) &p);
        }
        if (ret <= 0) {
            VLOG_DBG("Malformed IPv4 prefix");
            return CMD_SUCCESS;
        }
    }
#ifdef HAVE_IPV6
    else if (afi == AFI_IP6) {
        if (strncmp ("any", argv1[PREFIX_LIST_PREFIX],
                 strlen(argv1[PREFIX_LIST_PREFIX])) == 0) {
            ret = str2prefix_ipv6 ("::/0", (struct prefix_ipv6 *) &p);
            genum = 0;
            lenum = IPV6_MAX_BITLEN;
            any = 1;
        } else {
            ret = str2prefix_ipv6 (argv1[PREFIX_LIST_PREFIX],
                             (struct prefix_ipv6 *) &p);
        } if (ret <= 0) {
            VLOG_DBG("Malformed IPv6 prefix");
            return CMD_SUCCESS;
        }
    }
#endif

    if (genum && (genum <= p.prefixlen)) {
        return invalid_prefix_range (argv1[PREFIX_LIST_PREFIX]);
    }
    if (lenum && (lenum <= p.prefixlen)) {
        return invalid_prefix_range (argv1[PREFIX_LIST_PREFIX]);
    }
    if (lenum && (genum > lenum)) {
        return invalid_prefix_range (argv1[PREFIX_LIST_PREFIX]);
    }
    if (genum && (lenum == (afi == AFI_IP ? 32 : 128))) {
        lenum = 0;
    }
    /* Make prefix entry. */
    pentry = prefix_list_entry_make (&p, type, seqnum, lenum, genum, any);

    /* Check same policy. */
    dup = prefix_entry_dup_check (plist, pentry);

    if (dup) {
        prefix_list_entry_free (pentry);
        return CMD_SUCCESS;
    }

    /* Install new filter to the access_list. */
    prefix_list_entry_add (plist, pentry);

    return CMD_SUCCESS;
}

const struct ovsrec_prefix_list *
lookup_prefix_list_from_ovsdb(const char *name)
{
    const struct ovsrec_prefix_list *ovs_plist;

    if (!name) {
        VLOG_ERR("Prefix List name is NULL.");
        return NULL;
    }

    OVSREC_PREFIX_LIST_FOR_EACH(ovs_plist, idl) {
        if (strcmp (name, ovs_plist->name) == 0) {
            return ovs_plist;
        }
    }

    return NULL;
}

void
prefix_list_read_ovsdb_delete_from_master(struct prefix_list *plist_head)
{
    struct prefix_list * plist;

    int ret = -1; /*delet this*/
    if (!plist_head) {
        VLOG_DBG("Prefix List head is NULL.");
        return;
    }

    for (plist = plist_head; plist; plist = plist->next) {
        if (!lookup_prefix_list_from_ovsdb(plist->name)) {
            if (plist->desc) {
                ret = prefix_list_desc_unset(plist->name);
                if (!ret) {
                    VLOG_DBG("Deleted prefix_list description");
                }
            } else {
               VLOG_DBG("Deleting prefix list: %s", plist->name);
               prefix_list_delete(plist);
            }
        }
    }
}

bool
prefix_list_compare_ovs_quagga_plist_entry(
        int64_t ovs_seq_num,
        struct ovsrec_prefix_list_entry *ovs_plist_entry,
        struct prefix_list_entry *plist_entry)
{
    int le = 0, ge = 0;
    enum prefix_list_type type;
    char prefix_str[256];
    int prefix_str_len;

    prefix_str_len = sizeof(prefix_str);
    memset(prefix_str, 0, prefix_str_len);

    if (prefix2str(&plist_entry->prefix, prefix_str, prefix_str_len)) {
        VLOG_ERR("Invalid prefix string");
        return false;
    }

    if (!ovs_plist_entry || !plist_entry) {
        VLOG_ERR("Invalid prefix list entry");
        return false;
    }

    if (prefix_list_type_str_to_enum(ovs_plist_entry->action,
                                     &type) != CMD_SUCCESS) {
        VLOG_ERR("Invalid prefix-list type");
        return false;
    }

    if ((ovs_seq_num == plist_entry->seq) && (type == plist_entry->type) &&
        !strcmp(ovs_plist_entry->prefix, prefix_str)) {
        le = plist_entry->le;
        ge = plist_entry->ge;

        if (!(ovs_plist_entry->n_le && (le != ovs_plist_entry->le[0])) &&
            !(ovs_plist_entry->n_ge && (ge != ovs_plist_entry->ge[0]))) {
            VLOG_DBG("prefix-list entry values match");
            return true;
        }
    }

    return false;
}

void
prefix_list_entry_read_ovsdb_delete_from_master(struct prefix_list *plist_head)
{
    struct prefix_list *plist;
    struct prefix_list_entry *plist_entry;
    const struct ovsrec_prefix_list *ovs_plist;
    struct ovsrec_prefix_list_entry *ovs_plist_entry;

    int update_list = 1;
    int i;

    if (!plist_head) {
        VLOG_DBG("Prefix List head is NULL.");
        return;
    }

    VLOG_DBG("Checking for prefix list entry deletions.");
    for (plist = plist_head; plist; plist = plist->next) {
        ovs_plist = lookup_prefix_list_from_ovsdb(plist->name);
        if (ovs_plist) {
            for (plist_entry = plist->head; plist_entry;
                 plist_entry = plist_entry->next) {
                bool matched = false;

                /* Search against entries in prefix list stored in OVSDB */
                for (i = 0; i < ovs_plist->n_prefix_list_entries; i++) {
                    /* The key of the prefix list entry is the seq number */
                    int64_t ovs_seqnum = ovs_plist->key_prefix_list_entries[i];
                    ovs_plist_entry = ovs_plist->value_prefix_list_entries[i];

                    if (prefix_list_compare_ovs_quagga_plist_entry(ovs_seqnum,
                            ovs_plist_entry, plist_entry)) {
                        matched = true;
                        break;
                    }
                }

                if (!matched) {
                    VLOG_DBG("Deleting plist entry");
                    prefix_list_entry_delete(plist, plist_entry, update_list);
                }
            }
        }
    }
}

void
policy_prefix_list_read_ovsdb_apply_deletion(struct ovsdb_idl *idl)
{
    const struct ovsrec_prefix_list *ovs_first;
    struct prefix_master *master_ipv4;;
    struct prefix_master *master_ipv6;
    ovs_first = ovsrec_prefix_list_first(idl);
    VLOG_DBG("Checking for prefix list deletions");
    if (ovs_first && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ovs_first, idl_seqno)) {
        VLOG_DBG("No prefix list deletions detected.");
        return;
    }

    master_ipv4 = prefix_master_get (AFI_IP);
    master_ipv6 = prefix_master_get (AFI_IP6);
    if (master_ipv4 == NULL && master_ipv6 == NULL) {
        VLOG_DBG("No prefix list to delete");
        return;
    }
    /* Check number based name list */
    prefix_list_read_ovsdb_delete_from_master(master_ipv4->num.head);

    /* Check string based name list */
    prefix_list_read_ovsdb_delete_from_master(master_ipv4->str.head);

    /* Check number based name list */
    prefix_list_read_ovsdb_delete_from_master(master_ipv6->num.head);

    /* Check string based name list */
    prefix_list_read_ovsdb_delete_from_master(master_ipv6->str.head);
}

void
policy_prefix_list_entry_read_ovsdb_apply_deletion (struct ovsdb_idl *idl)
{
    const struct ovsrec_prefix_list_entry *ovs_first;
    struct prefix_master *master_ipv4;
    struct prefix_master *master_ipv6;

    /* prefix list */
    ovs_first = ovsrec_prefix_list_entry_first(idl);
    if (ovs_first && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ovs_first, idl_seqno)) {
        VLOG_DBG("No prefix list entry deletions detected.");
        return;
    }

    master_ipv4 = prefix_master_get (AFI_IP);
    master_ipv6 = prefix_master_get (AFI_IP6);
    if (master_ipv4  == NULL && master_ipv6 == NULL) {
        VLOG_DBG("No prefix list to delete");
        return;
    }

    /* Check number based name list */
    prefix_list_entry_read_ovsdb_delete_from_master(master_ipv4->num.head);

    /* Check string based name list */
    prefix_list_entry_read_ovsdb_delete_from_master(master_ipv4->str.head);

    /* Check number based name list */
    prefix_list_entry_read_ovsdb_delete_from_master(master_ipv6->num.head);

    /* Check string based name list */
    prefix_list_entry_read_ovsdb_delete_from_master(master_ipv6->str.head);

}

int
policy_prefix_list_read_ovsdb_apply_changes(struct ovsdb_idl *idl)
{
    int ret;
    int seqnum = -1;
    char **argv1;
    char **argvseq;
    int argc1 = -1 , argcseq = -1;
    const struct ovsrec_prefix_list * prefix_list_first;
    const struct ovsrec_prefix_list_entry * prefix_list_entry_first;
    const struct ovsrec_prefix_list * ovs_plist;
    struct ovsrec_prefix_list_entry * ovs_entry;
    int i;
    struct in6_addr addrv6;
    char *temp_prefix;
    struct prefix_list *plist;

    /* Handle prefix list deletions. */
    policy_prefix_list_read_ovsdb_apply_deletion (idl);

    /* Handle prefix list entry deletions. */
    policy_prefix_list_entry_read_ovsdb_apply_deletion (idl);

    prefix_list_first = ovsrec_prefix_list_first(idl);
    prefix_list_entry_first = ovsrec_prefix_list_entry_first(idl);

    if (prefix_list_first == NULL && prefix_list_entry_first == NULL) {
        VLOG_DBG("No prefix list configured");
        return CMD_SUCCESS;
    }

    if ((!(OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED(prefix_list_first, idl_seqno)) &&
        !(OVSREC_IDL_ANY_TABLE_ROWS_INSERTED(prefix_list_first, idl_seqno))) &&
        (!(OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED(prefix_list_entry_first, idl_seqno)) &&
        !(OVSREC_IDL_ANY_TABLE_ROWS_INSERTED(prefix_list_entry_first, idl_seqno)))) {
        VLOG_DBG("No changes for prefix list");
        return CMD_SUCCESS;
    }

    /* Allocate two argv lists. */
    if (!(argv1 = policy_ovsdb_alloc_arg_list(MAX_ARGC, MAX_ARG_LEN)) ||
        !(argvseq = policy_ovsdb_alloc_arg_list(MAX_ARGC, MAX_ARG_LEN))) {
        return CMD_SUCCESS;
    }

    /* Read ovsdb and apply changes */
    OVSREC_PREFIX_LIST_FOR_EACH(ovs_plist, idl) {

        strcpy(argv1[PREFIX_LIST_NAME], ovs_plist->name);

       if (strlen(ovs_plist->description) !=0) {
            plist = prefix_list_get (AFI_IP6, argv1[PREFIX_LIST_NAME]);
            plist->desc = (char *)malloc(sizeof(ovs_plist->description));
            strcpy(plist->desc,ovs_plist->description);
            VLOG_DBG("Setting prefix list: %s description: %s",
                       plist->name,plist->desc);
        }
        argc1 = PREFIX_LIST_NAME;
        for (i = 0; i < ovs_plist->n_prefix_list_entries; i ++) {
            ovs_entry = ovs_plist->value_prefix_list_entries[i];
            if (!(OVSREC_IDL_IS_ROW_INSERTED(ovs_entry, idl_seqno)) &&
                   !(OVSREC_IDL_IS_ROW_MODIFIED(ovs_entry, idl_seqno))) {
                continue;
            }
            VLOG_DBG("prefix list config modified");
            strcpy(argv1[PREFIX_LIST_ACTION], ovs_entry->action);
            strcpy(argv1[PREFIX_LIST_PREFIX], ovs_entry->prefix);


            sprintf(argv1[PREFIX_LIST_GE], "%d" ,ovs_entry->ge[0]);
            sprintf(argv1[PREFIX_LIST_LE], "%d" ,ovs_entry->le[0]);
            argc1 = PREFIX_LIST_PREFIX + 1;
            seqnum = ovs_plist->key_prefix_list_entries[i];
            argcseq =1 ;

            temp_prefix = (char *)malloc(strlen(ovs_entry->prefix)+1);

            strcpy(temp_prefix,ovs_entry->prefix);
            strtok(temp_prefix,"/");

            if (strcmp(ovs_entry->prefix,"any") == 0
                   || (ovs_entry->ge[0] == 0
                   && ovs_entry->le[0] == 0 )) {

                if (ovs_entry->le[0] == 128) {
                    policy_prefix_list_apply_changes(idl, AFI_IP6, argv1,
                                 argvseq,argc1, argcseq, seqnum);

                } else if (inet_pton(AF_INET6,temp_prefix,
                           &addrv6) == 1) {
                    policy_prefix_list_apply_changes(idl, AFI_IP6, argv1,
                                  argvseq,argc1, argcseq, seqnum);

                } else {
                    policy_prefix_list_apply_changes(idl, AFI_IP, argv1,
                                  argvseq,argc1, argcseq, seqnum);

                }
            } else if (strcmp(ovs_entry->prefix,"any") != 0
                       && ovs_entry->le[0] == 0 ) {

                if (inet_pton(AF_INET6,temp_prefix,&addrv6) == 1) {
                        policy_prefix_list_apply_changes(idl, AFI_IP6, argv1,
                                 argvseq,argc1, argcseq, seqnum);
                } else {
                        policy_prefix_list_apply_changes(idl, AFI_IP, argv1,
                                 argvseq,argc1, argcseq, seqnum);
                }
            } else if (strcmp(ovs_entry->prefix,"any") != 0
                       && ovs_entry->ge[0] == 0 ) {
                if (inet_pton(AF_INET6,temp_prefix,&addrv6) == 1) {
                        policy_prefix_list_apply_changes(idl, AFI_IP6, argv1,
                                 argvseq,argc1, argcseq, seqnum);

                } else {
                        policy_prefix_list_apply_changes(idl, AFI_IP, argv1,
                                 argvseq,argc1, argcseq, seqnum);
                }

            } else {
                if (inet_pton(AF_INET6,temp_prefix,&addrv6) == 1) {
                        policy_prefix_list_apply_changes(idl, AFI_IP6, argv1,
                                 argvseq,argc1, argcseq, seqnum);
                } else {
                        policy_prefix_list_apply_changes(idl, AFI_IP, argv1,
                                 argvseq,argc1, argcseq, seqnum);
                }
            }
            free(temp_prefix);
        }
    }

    policy_ovsdb_free_arg_list(&argv1, MAX_ARGC);
    policy_ovsdb_free_arg_list(&argvseq, MAX_ARGC);
    return CMD_SUCCESS;
}

const struct ovsrec_bgp_community_filter *
lookup_community_filter_from_ovsdb(const char *name)
{
    const struct ovsrec_bgp_community_filter *ovs_cfilter;
    if (!name) {
        VLOG_ERR("Community Filter name is NULL.");
        return NULL;
    }
    OVSREC_BGP_COMMUNITY_FILTER_FOR_EACH(ovs_cfilter, idl) {
        if (strcmp (name, ovs_cfilter->name) == 0) {
            return ovs_cfilter;
        }
    }
    return NULL;
}

/* Community Filter deletions */
void
policy_community_filter_read_ovsdb_apply_deletion (struct ovsdb_idl *idl)
{
    const struct ovsrec_bgp_community_filter *ovs_first;
    struct community_list *list;
    struct community_list_master *cm;

    int ret = -1;
    int direct = 0;
    char *str = NULL;

    ovs_first = ovsrec_bgp_community_filter_first(idl);
    VLOG_DBG("Checking for community filter deletions");
    if (ovs_first && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED
                                 (ovs_first, idl_seqno)) {
        VLOG_DBG("No community filter deletions detected.");
        return;
    }
    cm = community_list_master_lookup (bgp_clist, EXTCOMMUNITY_LIST_MASTER);
    for (list = cm->str.head; list; list = list->next) {
        if (!lookup_community_filter_from_ovsdb(list->name)) {
            VLOG_DBG("Deleting Extended Community List: %s",list->name);
            community_list_delete (list);
        }
    }
    cm = community_list_master_lookup (bgp_clist, COMMUNITY_LIST_MASTER);
    for (list = cm->str.head; list; list = list->next) {
        if (!lookup_community_filter_from_ovsdb(list->name)) {
            VLOG_DBG("Deleting Community List : %s",list->name);
            community_list_delete (list);
        }
    }
}


int
policy_community_filter_read_ovsdb_apply_changes(struct ovsdb_idl *idl)
{
    int ret;
    int direct;
    const struct ovsrec_bgp_community_filter *ovs_cfilter;
    const struct ovsrec_bgp_community_filter *community_filter_first;
    int i;

    /*Handle Community Filter deletions*/
    policy_community_filter_read_ovsdb_apply_deletion (idl);

    community_filter_first =  ovsrec_bgp_community_filter_first(idl);
    if (community_filter_first == NULL) {
        VLOG_DBG("No community filter configuration");
        return CMD_SUCCESS;
    }
    if (!(OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED
                           (community_filter_first, idl_seqno)) &&
        !(OVSREC_IDL_ANY_TABLE_ROWS_INSERTED
                           (community_filter_first, idl_seqno))) {
        VLOG_DBG("No changes for community filter list");
        return CMD_SUCCESS;
    }
    /* Read ovsdb and apply changes */
    VLOG_DBG("community filter config modified");
    OVSREC_BGP_COMMUNITY_FILTER_FOR_EACH(ovs_cfilter, idl) {
        if (ovs_cfilter->n_permit) {
            direct = COMMUNITY_PERMIT;
            if (!strcmp(ovs_cfilter->type,"extcommunity-list")) {
                for (i = 0; i < ovs_cfilter->n_permit; i++) {
                    ret = extcommunity_list_set (bgp_clist,
                                 ovs_cfilter->name,
                                 ovs_cfilter->permit[i],
                                 direct,
                                 EXTCOMMUNITY_LIST_EXPANDED);
                    if (!ret) {
                        VLOG_DBG("Extcommunity filter permit configuration"
                                 " changes set");
                    } else {
                        VLOG_ERR("Error in setting extcommunity filter"
                                 " permit configuration");
                    }
                }
            } else if (!strcmp(ovs_cfilter->type,"community-list")) {
                for (i = 0; i < ovs_cfilter->n_permit; i++) {
                    ret = community_list_set (bgp_clist,
                                 ovs_cfilter->name,
                                 ovs_cfilter->permit[i],
                                 direct,
                                 COMMUNITY_LIST_EXPANDED);
                    if (!ret) {
                        VLOG_DBG("Community filter permit configuration"
                                 " changes set");
                    } else {
                        VLOG_ERR("Error in setting community filter"
                                 " permit configuration");
                    }
                }
            }
        }
        if (ovs_cfilter->n_deny) {
            direct = COMMUNITY_DENY;
            if (!strcmp(ovs_cfilter->type,"extcommunity-list")) {
                for (i = 0; i < ovs_cfilter->n_deny; i++) {
                    ret = extcommunity_list_set (bgp_clist,
                                 ovs_cfilter->name,
                                 ovs_cfilter->deny[i],
                                 direct,
                                 EXTCOMMUNITY_LIST_EXPANDED);
                    if (!ret) {
                        VLOG_DBG("Extcommunity filter deny configuration"
                                 " changes set");
                    } else {
                        VLOG_ERR("Error in setting extcommunity filter"
                                 " deny configuration");
                    }
                }
            } else if (!strcmp(ovs_cfilter->type,"community-list")) {
                for (i = 0; i < ovs_cfilter->n_deny; i++) {
                    ret = community_list_set (bgp_clist,
                                 ovs_cfilter->name,
                                 ovs_cfilter->deny[i],
                                 direct,
                                 COMMUNITY_LIST_EXPANDED);
                    if (!ret) {
                        VLOG_DBG("Community filter deny configuration"
                                 " changes set");
                    } else {
                        VLOG_ERR("Error in setting community filter"
                                 " deny configuration");
                    }
                }
            }
        }
    }
    return CMD_SUCCESS;
}

/* ip as-path access-list */
static bool
lookup_aspath_filter_match_from_ovsdb(const struct ovsrec_bgp_aspath_filter *flist,
                                      const char *match)
{
    int itr;
    if (match) {
        for(itr=0; itr < flist->n_permit; itr++) {
            if(!strcmp(flist->permit[itr], match))
                return true;
        }
        for(itr=0; itr < flist->n_deny; itr++) {
            if(!strcmp(flist->deny[itr], match))
                return true;
        }
    }
    return false;
}

const struct ovsrec_bgp_aspath_filter *
lookup_aspath_filter_from_ovsdb(const char *name, const char *match)
{
    const struct ovsrec_bgp_aspath_filter *ovs_flist;

    if (!name || !match) {
        VLOG_ERR("Filter List name or match is NULL.");
        return NULL;
    }

    OVSREC_BGP_ASPATH_FILTER_FOR_EACH(ovs_flist, idl) {
        if (!strcmp (name, ovs_flist->name)
            && (lookup_aspath_filter_match_from_ovsdb(ovs_flist, match) == true)) {
            return ovs_flist;
        }
    }
    return NULL;
}

void
aspath_filter_read_ovsdb_delete_from_master(struct as_list *flist_head){
    struct as_list *aslist;
    struct as_filter *asfilter;

    if(!flist_head) {
        VLOG_DBG("Filter List head is NULL");
        return;
    }

    for (aslist = flist_head; aslist; aslist = aslist->next) {
        for (asfilter = aslist->head; asfilter; asfilter = asfilter->next) {
            if (lookup_aspath_filter_from_ovsdb(aslist->name, asfilter->reg_str) == 0) {
                VLOG_DBG("Deleting Filter List : %s with match string %s",
                         aslist->name, asfilter->reg_str);
                as_list_filter_delete (aslist, asfilter);
            }
        }
    }
}

void
policy_aspath_filter_read_ovsdb_apply_deletion(struct ovsdb_idl *idl)
{
    const struct ovsrec_bgp_aspath_filter *ovs_first;
    struct as_filter *asfilter;
    struct as_list *aslist;
    struct as_list_master *as_list;
    char *str = NULL;

    ovs_first = ovsrec_bgp_aspath_filter_first(idl);
    VLOG_DBG("Checking for filter list deletions");
    if (ovs_first && !OVSREC_IDL_ANY_TABLE_ROWS_DELETED(ovs_first, idl_seqno)) {
        VLOG_DBG("No filter list deletions detected.");
        return;
    }

    as_list = as_list_master_get();
    if(as_list == NULL) {
        VLOG_DBG("No filter list to delete");
        return;
    }

    aspath_filter_read_ovsdb_delete_from_master(as_list->num.head);

    aspath_filter_read_ovsdb_delete_from_master(as_list->str.head);
}

int
policy_aspath_filter_apply_changes(struct ovsdb_idl *idl,
                                   char **argv1, int argc1)
{
    int ret;
    int direct;
    char *str;
    regex_t *regex;
    struct as_filter *asfilter;
    struct as_list *aslist;

    /* Check the list type. */
    if (strncmp (argv1[BGP_ASPATH_FILTER_ACTION], "p", 1) == 0) {
        direct = AS_FILTER_PERMIT;
    }
    else if (strncmp (argv1[BGP_ASPATH_FILTER_ACTION], "d", 1) == 0) {
        direct = AS_FILTER_DENY;
    }
    else {
        VLOG_ERR("Matching condition must be permit or deny");
        return CMD_WARNING;
    }

    regex = bgp_regcomp (argv1[BGP_ASPATH_FILTER_DESCRIPTION]);

    asfilter = as_filter_make(regex, argv1[BGP_ASPATH_FILTER_DESCRIPTION], direct);

    /* Install new filter to the access_list. */
    aslist = as_list_get (argv1[BGP_ASPATH_FILTER_NAME]);

    /* Duplicate insertion check. */
    if (as_list_dup_check (aslist, asfilter))
        as_filter_free (asfilter);
    else
        as_list_filter_add (aslist, asfilter);

    return CMD_SUCCESS;
}

int
policy_aspath_filter_read_ovsdb_apply_changes(struct ovsdb_idl *idl)
{
    int ret;
    char **argv1;
    int argc1 =-1;
    const struct ovsrec_bgp_aspath_filter *ovs_flist;
    const struct ovsrec_bgp_aspath_filter *aspath_filter_first;
    int i, itr;

    /* Handle filter list deletions */
    policy_aspath_filter_read_ovsdb_apply_deletion (idl);

    aspath_filter_first =  ovsrec_bgp_aspath_filter_first(idl);
    if (aspath_filter_first == NULL) {
        VLOG_DBG("No filter list configuration");
        return CMD_SUCCESS;
    }

    if (!(OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED(aspath_filter_first, idl_seqno)) &&
        !(OVSREC_IDL_ANY_TABLE_ROWS_INSERTED(aspath_filter_first, idl_seqno))) {
        VLOG_DBG("No changes for filter list");
        return CMD_SUCCESS;
    }

    /* Allocate two argv lists */
    if (!(argv1 = policy_ovsdb_alloc_arg_list(MAX_ARGC, MAX_ARG_LEN)))
        return CMD_SUCCESS;

    /* Read ovsdb and apply changes */
    VLOG_DBG("filter list config modified");
    OVSREC_BGP_ASPATH_FILTER_FOR_EACH(ovs_flist, idl) {
        argc1 = BGP_ASPATH_FILTER_NAME;
        strcpy(argv1[BGP_ASPATH_FILTER_NAME], ovs_flist->name);

        /* Parsing permit column */
        for(itr=0; itr < ovs_flist->n_permit; itr++) {
            strcpy(argv1[BGP_ASPATH_FILTER_ACTION], "permit");
            strcpy(argv1[BGP_ASPATH_FILTER_DESCRIPTION], ovs_flist->permit[itr]);
            argc1 = BGP_ASPATH_FILTER_MAX;

            ret = policy_aspath_filter_apply_changes(idl, argv1, argc1);

            if (!ret)
                VLOG_DBG("filter list configuration changes set");
        }

        /* Parsing deny column */
        for(itr=0; itr < ovs_flist->n_deny; itr++) {
            strcpy(argv1[BGP_ASPATH_FILTER_ACTION], "deny");
            strcpy(argv1[BGP_ASPATH_FILTER_DESCRIPTION], ovs_flist->deny[itr]);
            argc1 = BGP_ASPATH_FILTER_MAX;

            ret = policy_aspath_filter_apply_changes(idl, argv1, argc1);

            if (!ret)
                VLOG_DBG("filter list configuration changes set");
        }
    }

    policy_ovsdb_free_arg_list(&argv1, MAX_ARGC);

    return CMD_SUCCESS;
}

int
bgp_ovsdb_republish_route(const struct ovsrec_bgp_router *bgp_first, int asn)
{
    struct bgp_node *rn;
    struct bgp_info *ri;
    struct bgp * bgp;
    char pr[20];
    bgp = bgp_lookup((as_t)asn, NULL);
    if(!bgp)
    {
       VLOG_ERR("%s Invalid bgp ",__FUNCTION__ );
       return -1;
    }
    VLOG_INFO("%s for AS %d",__FUNCTION__, asn );
    for (rn = bgp_table_top (bgp->rib[AFI_IP][SAFI_UNICAST]); rn;
         rn = bgp_route_next (rn))
    {
        for (ri = rn->info;ri;ri = ri->next)
        {
            if( CHECK_FLAG (ri->flags, BGP_INFO_SELECTED) && bgp_info_mpath_count(ri))
            {
                prefix2str(&rn->p, pr, sizeof(pr));
                VLOG_DBG("%s del route %s, has mpaths = %d\n",__FUNCTION__,
                         pr, bgp_info_mpath_count(ri));
                bgp_ovsdb_withdraw_rib_entry(&rn->p, ri,bgp, SAFI_UNICAST);
                VLOG_DBG("%s re-announce route %s\n",__FUNCTION__, pr);
                bgp_ovsdb_announce_rib_entry(&rn->p, ri,bgp, SAFI_UNICAST);
            }
        }
    }
    return 0;
}

static uint32_t get_lookup_key(char *prefix, char *table_name) {
    char key[MAX_KEY_LEN];
    int hashkey;
    memset(key, 0 ,sizeof(key));
    strcpy(key, prefix);
    strcat(key, table_name);
    hashkey = hash_string(key, 0);
    return hashkey;
}

static bool
bgp_review(struct bgp_ovsdb_txn *txn, enum txn_op_type op,
                                   bgp_table_type_t table_type)
{
    char pr_bgp[PREFIX_MAXLEN];
    struct bgp* bgp = NULL;
    struct bgp_node *rn = NULL;
    struct bgp_info *ri = NULL;
    int prefix_found = 0;
    bool bgp_info_found = false;

    prefix2str(&txn->prefix, pr_bgp, sizeof(pr_bgp));
    bgp = bgp_lookup(txn->as_no, NULL);

    if (!bgp) {
        VLOG_ERR("BGP node is NULL for incoming prefix %s\n", pr_bgp);
        return false;
    }

    rn = bgp_node_lookup (bgp->rib[txn->afi][txn->safi], &txn->prefix);

    if(rn == NULL)
    {
        prefix_found = 0;
    }
    else
    {
        ri = rn->info;
        if(ri)
        {
            if (!(ri->flags & BGP_INFO_REMOVED)){
                prefix_found = 1;
                bgp_info_found = true;
            }
        }

        if (!bgp_info_found) {
            prefix_found = 0;
        }
        route_unlock_node((struct route_node *)rn);
    }

    /* If last operation was an insert or update, and prefix
       is not found in BGP, do a delete, otherwise update. */
    if(op == INSERT || op == UPDATE){
        if (prefix_found == 0) {

            if (table_type == BGP_ROUTE) {
                bgp_ovsdb_delete_local_rib_entry(&txn->prefix,
                                      ri, bgp, txn->safi);
            } else {
                bgp_ovsdb_withdraw_rib_entry(&txn->prefix,
                                      ri, bgp, txn->safi);
            }
        }
        else {

            if (table_type == BGP_ROUTE) {
                bgp_ovsdb_update_local_rib_entry_attributes(&txn->prefix,
                                          ri, bgp, txn->safi);
            } else {
                bgp_ovsdb_announce_rib_entry(&txn->prefix,
                                          ri, bgp, txn->safi);
            }
        }
    }

    /* If last operation was a delete, and prefix is not found in
       BGP, do an add */
    else if (op == DELETE){
        if (prefix_found)
        {
            if (table_type == BGP_ROUTE) {
                bgp_ovsdb_add_local_rib_entry(&txn->prefix,
                                          ri, bgp, txn->safi);
            } else {
                bgp_ovsdb_announce_rib_entry(&txn->prefix,
                                      ri, bgp, txn->safi);
            }
        }
    }
    return true;
}
