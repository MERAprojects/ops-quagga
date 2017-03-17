/*
 *
 * Hewlett-Packard Company Confidential (C) Copyright 2015 Hewlett-Packard Development Company, L.P.
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
 * File: bgp_ovsdb_if.h
 *
 * Purpose: This file includes all public interface defines needed by
 *          the new bgp_ovsdb.c for bgp - ovsdb integration
 */

#ifndef BGP_BACKEND_FUNCTIONS_H
#define BGP_BACKEND_FUNCTIONS_H 1

/* BGP clear sort. */
enum clear_sort
{
  clear_all,
  clear_peer,
  clear_group,
  clear_external,
  clear_as
};

extern int daemon_neighbor_shutdown_cmd_execute (struct bgp *bgp, char *peer_str, bool shut);
extern int daemon_neighbor_prefix_list_cmd_execute(struct bgp *bgp, char *peer_str,
                            afi_t afi, safi_t safi,const char *name_str, const char *direct_str);
extern int daemon_neighbor_route_map_cmd_execute(struct bgp *bgp, char *peer_str,
                            afi_t afi, safi_t safi,const char *name_str, const char *direct_str);
extern int daemon_neighbor_aspath_filter_cmd_execute(struct bgp *bgp, char *peer_str,
                            afi_t afi, safi_t safi,const char *name_str, const char *direct_str);
extern int daemon_neighbor_remote_as_cmd_execute (struct bgp *bgp, char *peer_str,
                            as_t *asp, afi_t afi, safi_t safi);
extern int daemon_neighbor_set_peer_group_cmd_execute (struct bgp *bgp, const char *peer_str,
                            const char *peer_group_name, afi_t afi, safi_t safi);
extern int daemon_no_neighbor_set_peer_group_cmd_execute (struct bgp *bgp, const char *peer_str,
                            afi_t afi, safi_t safi);
extern int daemon_neighbor_description_cmd_execute (struct bgp *bgp, char *peer_str, char *description);
extern int daemon_neighbor_password_cmd_execute (struct bgp *bgp, char *peer_str, char *password);
extern int daemon_neighbor_advertisement_interval_cmd_execute (struct bgp *bgp, char *peer_str,
                            int64_t *interval);
extern int daemon_neighbor_inbound_soft_reconfiguration_cmd_execute (struct bgp *bgp, const char *peer_str,
                            afi_t afi, safi_t safi, bool is_set);
extern int daemon_neighbor_timers_cmd_execute (struct bgp *bgp, const char *peer_str, const u_int32_t keepalive,
                            const u_int32_t holdtime, bool set);
extern int daemon_neighbor_allow_as_in_cmd_execute (struct bgp *bgp, char *peer_str, afi_t afi,
                            safi_t safi, int64_t *allow_as_in);
extern int daemon_neighbor_remove_private_as_cmd_execute (struct bgp *bgp, char *peer_str,
                            afi_t afi, safi_t safi, bool private_as);
extern int daemon_neighbor_ebgp_multihop_cmd_execute(struct bgp *bgp, const char *peer_str, bool is_set);
extern int daemon_neighbor_ttl_security_hops_cmd_execute(struct bgp *bgp, const char *peer_str, int64_t *ttl);
extern int daemon_neighbor_update_source_cmd_execute(struct bgp *bgp, const char *peer_str, const char *source_st);
extern int daemon_bgp_clear_request (const char *name, afi_t afi, safi_t safi,
                            enum clear_sort sort, enum bgp_clear_type stype,
                            const char *arg);
extern int daemon_neighbor_peer_group_cmd_execute (struct bgp *bgp, const char *groupName);
extern int daemon_neighbor_weight_cmd_execute(struct bgp *bgp, const char *peer_str, const uint16_t weight);
extern int daemon_neighbor_next_hop_self_cmd_execute (struct bgp *bgp, char *peer_str, afi_t afi, safi_t safi, bool next_hop_self);

#define BFD_SESSION_STATE_ADMIN_DOWN   0 // must match ovsrec_bfd_session_state
#define BFD_SESSION_STATE_DOWN         1 // must match ovsrec_bfd_session_state
#define BFD_SESSION_STATE_INIT         2 // must match ovsrec_bfd_session_state
#define BFD_SESSION_STATE_UP           3 // must match ovsrec_bfd_session_state

#define BFD_SESSION_STATE_STR_ADMIN_DOWN "admin_down"
#define BFD_SESSION_STATE_STR_DOWN       "down"
#define BFD_SESSION_STATE_STR_INIT       "init"
#define BFD_SESSION_STATE_STR_UP         "up"

extern int daemon_neighbor_bfd_fallover_enable_cmd_execute (struct bgp *bgp, char *peer_str, bool fall_over);

extern int daemon_neighbor_bfd_state_cmd_execute (struct bgp *bgp, char *peer_str, int bfd_state);

extern int bgp_bfd_neigh_add(struct peer *peer);
extern int bgp_bfd_neigh_del(struct peer *peer);
extern int bgp_bfd_neigh_estab(struct peer *peer);


#endif /* BGP_BACKEND_FUNCTIONS_H */
