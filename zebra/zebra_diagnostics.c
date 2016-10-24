/* Diagnostics and debug functions for zebra daemon.
 *
 * (c) Copyright 2016 Hewlett Packard Enterprise Development LP
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

#include <zebra.h>
#include "zebra/zserv.h"
#include "zebra/debug.h"
#include <diag_dump.h>
#include "dynamic-string.h"
#include "unixctl.h"
#include "memory.h"
#include "openvswitch/vlog.h"
#include "zebra/rib.h"
#include "zebra/rt.h"
#include "vswitch-idl.h"
#include "openswitch-idl.h"
#include "zebra/zebra_ovsdb_if.h"
#include "zebra/zebra_diagnostics.h"

VLOG_DEFINE_THIS_MODULE(zebra_diagnostics);
boolean exiting = false;


/*
 * the string representation of the port actions.
 */
char* zebra_l3_port_cache_actions_str[] =
{
  "L3 port no change",
  "L3 port add",
  "L3 port changed to L2",
  "L3 port delete",
  "L3 port IP address update",
  "L3 port active state change"
};

/*
 * This function returns the string for the various route types
 * supported by zebra.
 */
static char*
zebra_route_type_to_str (int route_type)
{
  switch (route_type)
    {
      case ZEBRA_ROUTE_SYSTEM:
        return("system");
      case ZEBRA_ROUTE_KERNEL:
        return("kernel");
      case ZEBRA_ROUTE_CONNECT:
        return("connected");
      case ZEBRA_ROUTE_STATIC:
        return("static");
      case ZEBRA_ROUTE_RIP:
        return("rip");
      case ZEBRA_ROUTE_RIPNG:
        return("ripng");
      case ZEBRA_ROUTE_OSPF:
        return("ospf");
      case ZEBRA_ROUTE_OSPF6:
        return("ospf6");
      case ZEBRA_ROUTE_ISIS:
        return("isis");
      case ZEBRA_ROUTE_BGP:
        return("bgp");
      case ZEBRA_ROUTE_PIM:
        return("pim");
      case ZEBRA_ROUTE_HSLS:
        return("hsls");
      case ZEBRA_ROUTE_OLSR:
        return("olsr");
      case ZEBRA_ROUTE_BABEL:
        return("babel");
      default:
        return("unsupported");
    }
}


/*
 * This function parses debug level options for the 'zebra/debug' appctl command
 */
static void
parse_debug_level_options(int argc, const char *argv[], char *return_status,
        struct unixctl_conn *conn)
{
  if (!strncmp("event", argv[1], NUM_CHAR_CMP))
    zebra_debug_event = ZEBRA_DEBUG_EVENT;
  else if (!strncmp("packet", argv[1], NUM_CHAR_CMP))
    zebra_debug_packet |= ZEBRA_DEBUG_PACKET;
  else if (!strncmp("send", argv[1], NUM_CHAR_CMP))
    zebra_debug_packet |= ZEBRA_DEBUG_SEND;
  else if (!strncmp("recv", argv[1], NUM_CHAR_CMP))
    zebra_debug_packet |= ZEBRA_DEBUG_RECV;
  else if (!strncmp("detail", argv[1], NUM_CHAR_CMP))
    zebra_debug_packet |= ZEBRA_DEBUG_DETAIL;
  else if (!strncmp("kernel", argv[1], NUM_CHAR_CMP))
    zebra_debug_kernel = ZEBRA_DEBUG_KERNEL;
  else if (!strncmp("rib", argv[1], NUM_CHAR_CMP))
    zebra_debug_rib |= ZEBRA_DEBUG_RIB;
  else if (!strncmp("ribq", argv[1], NUM_CHAR_CMP))
    zebra_debug_rib |= ZEBRA_DEBUG_RIB_Q;
  else if (!strncmp("fpm", argv[1], NUM_CHAR_CMP))
    zebra_debug_fpm = ZEBRA_DEBUG_FPM;
  else if (!strncmp("all", argv[1], NUM_CHAR_CMP))
    {
      zebra_debug_event = ZEBRA_DEBUG_EVENT;
      zebra_debug_packet = ZEBRA_DEBUG_PACKET | ZEBRA_DEBUG_SEND | \
                           ZEBRA_DEBUG_RECV  | ZEBRA_DEBUG_DETAIL;
      zebra_debug_kernel = ZEBRA_DEBUG_KERNEL;
      zebra_debug_rib = ZEBRA_DEBUG_RIB | ZEBRA_DEBUG_RIB_Q;
      zebra_debug_fpm = ZEBRA_DEBUG_FPM;
    }
  else if (!strncmp("off", argv[1], NUM_CHAR_CMP))
    {
      zebra_debug_event = 0;
      zebra_debug_packet = 0;
      zebra_debug_kernel = 0;
      zebra_debug_rib = 0;
      zebra_debug_fpm = 0;
    }
  else if (!strncmp("show", argv[1], NUM_CHAR_CMP))
    {
      if (IS_ZEBRA_DEBUG_EVENT)
        sprintf(return_status + strlen(return_status), "event\n");
      if (IS_ZEBRA_DEBUG_KERNEL)
        sprintf(return_status + strlen(return_status), "kernel\n");
      if (IS_ZEBRA_DEBUG_FPM)
        sprintf(return_status + strlen(return_status), "fpm\n");
      if (IS_ZEBRA_DEBUG_PACKET)
        sprintf(return_status + strlen(return_status), "packet\n");
      if (IS_ZEBRA_DEBUG_SEND)
        sprintf(return_status + strlen(return_status), "send\n");
      if (IS_ZEBRA_DEBUG_RECV)
        sprintf(return_status + strlen(return_status), "recv\n");
      if (IS_ZEBRA_DEBUG_DETAIL)
        sprintf(return_status + strlen(return_status), "detail\n");
      if (IS_ZEBRA_DEBUG_RIB)
        sprintf(return_status + strlen(return_status), "rib\n");
      if (IS_ZEBRA_DEBUG_RIB_Q)
        sprintf(return_status + strlen(return_status), "ribq\n");
    }
  else
    sprintf(return_status, "Unsupported argument - %s", argv[1]);
}

/*
 * This function parses options for the 'zebra/dump' appctl command
 */
static int
parse_diag_dump_options(int argc, const char *argv[], char *return_status,
                   struct unixctl_conn *conn)
{

  if (argc < 2)
    return 0;

  if (strcmp("rib", argv[1]) &&
      strcmp("kernel-routes", argv[1]) &&
      strcmp("l3-port-cache", argv[1]) &&
      strcmp("memory", argv[1]))
    {
      sprintf(return_status, "Argument %s not supported", argv[1]);
      return 1;
    }

  return 0;
}

/*
 * If 'ds' is non NULL, this function appends the formatted string to 'ds'
 * Else, the formatted string is written to the vlog
 */
static void
zebra_dump_formatted_string(struct ds *ds, const char *format, ...)
{
  va_list args;
  va_start(args, format);

  if (ds)
    {
      ds_put_format_valist(ds, format, args);
    }
  else
    {
      vlog_valist(vlog_module_from_name("zebra_diagnostics"),
                  VLL_DBG, format, args);
    }

  va_end(args);
}

/*
 * This function prints the content of a nexthop in zebra's rib entry.
 */
static void
zebra_kernel_routes_dump(struct ds *ds, bool is_v6)
{
  FILE* fp = NULL;
  char line_buf[MAX_PROMPT_MSG_STR_LEN];
  char *command = is_v6 ? "ip -6 route" : "ip route";
  fp = popen(command, "r");

  zebra_dump_formatted_string(ds, "\n-------- Kernel %s routes dump: --------\n",
                              is_v6 ? "IPv6" : "IPv4");
  if (fp)
    {
      while (fgets(line_buf, sizeof(line_buf), fp))
           {
             zebra_dump_formatted_string(ds, "%s", line_buf);
           }
      pclose(fp);
    }
}

/*
 * This function prints the memory allocation statistics for various data
 * structures used within zebra
 */
static void
zebra_memory_dump(struct ds *ds)
{
  char memstrbuf[MTYPE_MEMSTR_LEN];
  unsigned long count;

  if(!ds)
    {
      VLOG_ERR("Invalid Entry\n");
      return;
    }

  /* RIB related usage stats */
  count = mtype_stats_alloc (MTYPE_RIB);
  ds_put_format (ds, "%ld RIB nodes, using %s of memory\n", count,
                 mtype_memstr (memstrbuf, sizeof (memstrbuf),
                               count * sizeof (struct rib)));

  count = mtype_stats_alloc (MTYPE_NEXTHOP);
  ds_put_format (ds, "%ld nexthop nodes, using %s of memory\n", count,
                 mtype_memstr (memstrbuf, sizeof (memstrbuf),
                               count * sizeof (struct nexthop)));

  count = mtype_stats_alloc (MTYPE_STATIC_IPV4);
  ds_put_format (ds, "%ld static IPv4 routes, using %s of memory\n",
                     count,
                     mtype_memstr (memstrbuf, sizeof (memstrbuf),
                                   count * sizeof (struct static_ipv4)));

  count = mtype_stats_alloc (MTYPE_STATIC_IPV6);
  ds_put_format (ds, "%ld static IPv6 routes, using %s of memory\n", count,
                 mtype_memstr (memstrbuf, sizeof (memstrbuf),
                               count * sizeof (struct static_ipv6)));

  count = mtype_stats_alloc (MTYPE_WORK_QUEUE);
  ds_put_format (ds, "%ld work queues, using %s of memory\n", count,
                 mtype_memstr (memstrbuf, sizeof (memstrbuf),
                               count * sizeof (struct work_queue)));

  count = mtype_stats_alloc (MTYPE_RIB_DEST);
  ds_put_format (ds, "%ld RIB destinations , using %s of memory\n", count,
                 mtype_memstr (memstrbuf, sizeof (memstrbuf),
                               count * sizeof (rib_dest_t)));

  count = mtype_stats_alloc (MTYPE_VRF);
  ds_put_format (ds, "%ld VRFs, using %s of memory\n", count,
                 mtype_memstr (memstrbuf, sizeof (memstrbuf),
                               count * sizeof (struct vrf)));

  count = mtype_stats_alloc (MTYPE_RIB_TABLE_INFO);
  ds_put_format (ds, "%ld RIB table info nodes, using %s of memory\n", count,
                 mtype_memstr (memstrbuf, sizeof (memstrbuf),
                               count * sizeof (rib_table_info_t)));
}

/*
 * Helper function to dump various zebra diagnostics, depending on the dump_option
 * passed.
 */
static void
zebrad_internals_dump(struct ds *ds, const char *dump_option)
{
  if (!ds)
    return;

  if (!dump_option || !strcmp(dump_option, "rib"))
    {
      zebra_dump_formatted_string(ds, "\n-------- Zebra internal IPv4 "
                                  "routes dump: --------\n");
      zebra_dump_internal_route_table(ds, vrf_table(AFI_IP,
                                      SAFI_UNICAST, 0));

      zebra_dump_formatted_string(ds, "\n-------- Zebra internal IPv6 "
                                  "routes dump: --------\n");
      zebra_dump_internal_route_table(ds, vrf_table(AFI_IP6,
                                      SAFI_UNICAST, 0));
    }

  if (!dump_option || !strcmp(dump_option, "kernel-routes"))
    {
      zebra_kernel_routes_dump(ds, false);
      zebra_kernel_routes_dump(ds, true);
    }

  if (!dump_option || !strcmp(dump_option, "l3-port-cache"))
    {
      zebra_dump_formatted_string(ds, "\n-------- Zebra L3 port "
                                  "cache dump: --------\n");
      zebra_l3_port_walk_cache_and_print(ds, &zebra_cached_l3_ports, true);
      zebra_l3_port_walk_cache_and_print(ds, &zebra_updated_or_changed_l3_ports,
                                         false);
    }

  if (!dump_option || !strcmp(dump_option, "memory"))
    {
      zebra_dump_formatted_string(ds, "\n-------- Zebra memory dump: --------\n");
      zebra_memory_dump(ds);
    }
}

/* Callback handler function for dumping basic diagnostics for ops-zebra daemon.
 * It allocates memory as per requirment and populates data.
 * INIT_DIAG_DUMP_BASIC framework will free allocated memory.
 */
static void
zebra_diag_dump_basic_cb(const char *feature , char **buf)
{
  struct ds ds = DS_EMPTY_INITIALIZER;
  char* memory_unavailable_message = "Route-manager diagnostics dump "
                                     "not possible due to memory constraint";

  if (!buf)
    return;

  /*
   * Dump all zebra diagnostics data into 'ds'
   */
  zebrad_internals_dump(&ds, NULL);

  /*
   * Allocate memory which can hold all the diagnostics data in 'ds'
   */
  *buf =  malloc(ds.length + 1);

  if (!(*buf))
    {
      VLOG_ERR("Unable to allocate %lu byptes of memory for route-manager"
               "diagnostics", (ds.length + 1));

      ds_destroy(&ds);

      /*
       * If buffer allocation fails, then signal to user that buffer allocation
       * failed because of memory exhaustion.
       */
      *buf =  malloc(strlen(memory_unavailable_message) + 1);

      if ((*buf))
        {
          snprintf(*buf, strlen(memory_unavailable_message) + 1,
                   memory_unavailable_message);
        }

      return;
    }

  VLOG_DBG("Allocated %lu bytes for ops-zebra diags", (ds.length + 1));

  /*
   * Copy the diagnostics data into the allocated memory
   */
  snprintf(*buf, ds.length + 1, ds_cstr(&ds));

  ds_destroy(&ds);
}

/*
 * ovs appctl dump of zebra's internal data structures, used for debugging
 */
static void
zebra_unixctl_diag_dump (struct unixctl_conn *conn, int argc OVS_UNUSED,
                    const char *argv[] OVS_UNUSED, void *aux OVS_UNUSED)
{
  struct ds ds = DS_EMPTY_INITIALIZER;
  char err_str[MAX_PROMPT_MSG_STR_LEN];
  char* memory_unavailable_message = "Route-manager diagnostics dump "
                                     "not possible due to memory constraint";
  char* buf;

  if (parse_diag_dump_options(argc, argv, err_str, conn))
    {
      unixctl_command_reply_error(conn, err_str);
      return;
    }

  /*
   * Dump all zebra diagnostics data into 'ds'
   */
  zebrad_internals_dump(&ds, (argc == 2 ? argv[1] : NULL));

  /*
   * Allocate memory which can hold all the diagnostics data in 'ds'
   */
  buf = malloc(ds.length + 1);

  if (!buf)
    {
      VLOG_ERR("Unable to allocate %lu byptes of memory for route-manager"
               "diagnostics", (ds.length + 1));

      ds_destroy(&ds);

      /*
       * Send the appctl error response
       */
      unixctl_command_reply_error(conn, memory_unavailable_message);

      return;
    }

  VLOG_DBG("Allocated %lu bytes for ops-zebra diags", (ds.length + 1));

  /*
   * Copy the diagnostics data into the allocated memory
   */
  snprintf(buf, ds.length + 1, ds_cstr(&ds));

  /*
   * Send the appctl response
   */
  unixctl_command_reply(conn, buf);

  ds_destroy(&ds);

  /*
   * Free the allocated buffer
   */
  free(buf);
}

/*
 * ovs appctl function to display or modify the level of zebra logging.
 */
static void
zebra_unixctl_set_debug_level (struct unixctl_conn *conn, int argc OVS_UNUSED,
                               const char *argv[] OVS_UNUSED, void *aux OVS_UNUSED)
{
  char return_status[MAX_PROMPT_MSG_STR_LEN] = "";

  parse_debug_level_options(argc, argv, return_status, conn);

  if (!strncmp(return_status, "Unsupported argument", NUM_CHAR_UNSUPPORTED))
    unixctl_command_reply_error(conn, return_status);
  else
    unixctl_command_reply(conn, return_status);
}

/* This function is invoked on appctl exit command to stop the daemon
 */
static void
ops_zebra_exit (struct unixctl_conn *conn, int argc OVS_UNUSED,
                const char *argv[] OVS_UNUSED, void *exiting_)
{
  boolean *exiting = exiting_;
  *exiting = true;
  unixctl_command_reply(conn, NULL);
}

/*
 * Initialize call back functions and unixctl commands used for
 * zebra's diagnostics
 */
void
zebra_diagnostics_init()
{
  int retval;

  /* Create UDS connection for ovs-appctl. */
  retval = unixctl_server_create(appctl_path, &appctl);

  if (retval)
    exit(EXIT_FAILURE);

  /* Register the ovs-appctl "exit" command for this daemon. */
  unixctl_command_register("exit", "", 0, 0, ops_zebra_exit, &exiting);

  /* Initialize diag-dump framework for zebra */
  INIT_DIAG_DUMP_BASIC(zebra_diag_dump_basic_cb);

   /* Register ovs-appctl commands for this daemon. */
  unixctl_command_register("zebra/dump", "rib|kernel-routes|l3-port-cache|memory",
                           0, 1, zebra_unixctl_diag_dump, NULL);
  unixctl_command_register("zebra/debug", "event|packet|send|recv|detail|kernel"
                           "|rib|ribq|fpm|all|show|off", 1, 1,
                           zebra_unixctl_set_debug_level, NULL);
}

/*
 ********************************************************************
 * Start of the set of debugging functions for dumping zebra's route
 * table.
 ********************************************************************
 */

/*
 * This function prints the content of a nexthop in zebra's rib entry.
 * If the dynamic-string 'ds' is NULL, the formatted string is written to VLOG.
 * Otherwise, it is appended to 'ds'
 */
void
zebra_dump_internal_nexthop (struct ds *ds, struct prefix *p,
                             struct nexthop* nexthop)
{
  char nexthop_str[256];

  if (!nexthop)
    {
      zebra_dump_formatted_string(ds, "       Nexthop is NULL\n");
      return;
    }

  memset(nexthop_str, 0, sizeof(nexthop_str));

  if (p->family == AF_INET)
    if (nexthop->type == NEXTHOP_TYPE_IPV4)
      {
        inet_ntop(AF_INET, &nexthop->gate.ipv4,
                  nexthop_str, sizeof(nexthop_str));
         zebra_dump_formatted_string(ds, "      Nexthop->%s Active: %s\n",
                                     nexthop_str,
                                     CHECK_FLAG(nexthop->flags,
                                     NEXTHOP_FLAG_ACTIVE)? "true":"false");
      }

   if (p->family == AF_INET6)
     if (nexthop->type == NEXTHOP_TYPE_IPV6)
       {
         inet_ntop(AF_INET6, &nexthop->gate.ipv6,
                   nexthop_str, sizeof(nexthop_str));
         zebra_dump_formatted_string(ds, "      Nexthop->%s Active: %s\n",
                                     nexthop_str,
                                     CHECK_FLAG(nexthop->flags,
                                     NEXTHOP_FLAG_ACTIVE)? "true":"false");
       }

   if ((nexthop->type == NEXTHOP_TYPE_IFNAME) ||
       (nexthop->type == NEXTHOP_TYPE_IPV4_IFNAME) ||
       (nexthop->type == NEXTHOP_TYPE_IPV6_IFNAME))
       zebra_dump_formatted_string(ds, "      Nexthop->%s Active: %s\n",
                                   nexthop->ifname,
                                   CHECK_FLAG(nexthop->flags,
                                   NEXTHOP_FLAG_ACTIVE)? "true":"false");
}

/*
 * This function prints the contents of a rib entry in the zebra
 * route node. If the dynamic-string 'ds' is NULL, the formatted string is
 * written to VLOG. Otherwise, it is appended to 'ds'
 */
void
zebra_dump_internal_rib_entry (struct ds *ds, struct prefix *p, struct rib* rib)
{
  struct nexthop *nexthop;
  char nexthop_str[256];

  if (!rib)
    {
      zebra_dump_formatted_string(ds, "   Rib entry is NULL\n");
      return;
    }

  if (!(rib->nexthop))
    {
      zebra_dump_formatted_string(ds, "   Empty RIB entry\n");
      return;
    }

  zebra_dump_formatted_string(ds, "    Route type: %s Metric: %u "
                              "Distance: %u Number: %u\n",
                              zebra_route_type_to_str(rib->type), rib->metric,
                              rib->distance, rib->nexthop_num);

  for (nexthop = rib->nexthop; nexthop; nexthop = nexthop->next)
   {
     zebra_dump_internal_nexthop(ds, p, nexthop);
   }
}

/*
 * This function dumps the contents of a route node in zebra's
 * route table. If the dynamic-string 'ds' is NULL, the formatted string
 * is written to VLOG. Otherwise, it is appended to 'ds'
 */
void
zebra_dump_internal_route_node (struct ds *ds, struct route_node *rn)
{
  struct rib *rib;
  struct nexthop *nexthop;
  char prefix_str[256];
  char nexthop_str[256];
  struct prefix *p = NULL;

  if (!rn)
    {
      return;
    }

  p = &rn->p;

  if (!p)
    {
      return;
    }

  memset(prefix_str, 0, sizeof(prefix_str));
  prefix2str(p, prefix_str, sizeof(prefix_str));

  zebra_dump_formatted_string(ds, "Prefix %s Family %d\n",prefix_str,
                              PREFIX_FAMILY(p));

  RNODE_FOREACH_RIB (rn, rib)
    {
      zebra_dump_internal_rib_entry(ds, p, rib);
    }
}

/*
 * This function walks the zebra route table and prints the contents
 * of all route nodes.  If the dynamic-string 'ds' is NULL, the formatted string
 * is written to VLOG. Otherwise, it is appended to 'ds'
 */
void
zebra_dump_internal_route_table (struct ds *ds, struct route_table *table)
{
  struct route_node *rn;

  if (!table)
    {
      zebra_dump_formatted_string(ds, "The internal route table is null");
      return;
    }

  for (rn = route_top (table); rn; rn = route_next (rn))
    {
      zebra_dump_internal_route_node(ds, rn);
    }
}

/*
 ********************************************************************
 * End of the set of debugging functions for dumping zebra's route
 * table.
 ********************************************************************
 */

/*
 ********************************************************************
 * Start of the set of debugging functions for OVSDB zebra interface.
 ********************************************************************
 */

/*
 * This function returns the UUID of a some entry in OVSDB in string
 * format.
 */
char*
zebra_dump_ovsdb_uuid (struct uuid* uuid)
{
  static char uuid_to_string[ZEBRA_MAX_STRING_LEN];

  memset(uuid_to_string, 0, ZEBRA_MAX_STRING_LEN);

  if (!uuid)
    snprintf(uuid_to_string, ZEBRA_MAX_STRING_LEN,
             "The UUID is NULL");
  else
    snprintf(uuid_to_string, ZEBRA_MAX_STRING_LEN, "%u-%u-%u-%u",
             uuid->parts[0], uuid->parts[1], uuid->parts[2],
             uuid->parts[3]);

  return(uuid_to_string);
}

/*
 * This function prints the contents of the cached L3 port node. This is
 * useful for debugging the port/interface triggers.  If the dynamic-string
 * 'ds' is NULL, the formatted string is written to VLOG. Otherwise,
 * it is appended to 'ds'
 */
void
zebra_l3_port_node_print (struct ds *ds, struct zebra_l3_port* l3_port)
{
  struct shash_node *node, *next;
  char* ip_secondary_address;
  struct uuid* connected_route_uuid;
  int secondary_address_count, route_uuid_count;

  if (!l3_port)
    {
      return;
    }

  zebra_dump_formatted_string(ds, "Printing the L3 node for Port name: %s\n",
                              l3_port->port_name ?
                              l3_port->port_name : "NULL");

  zebra_dump_formatted_string(ds,"     Port Primary IP Address: %s\n",
                              l3_port->ip4_address ? l3_port->ip4_address : "NULL");
  zebra_dump_formatted_string(ds,"     Port Primary IPv6 Address: %s\n",
                              l3_port->ip6_address ?
                              l3_port->ip6_address : "NULL");

  zebra_dump_formatted_string(ds,"     OVSDB port UUID is: %s\n",
                              zebra_dump_ovsdb_uuid((struct uuid*)&(l3_port->ovsrec_port_uuid)));

  zebra_dump_formatted_string(ds,"     Port action is: %s\n", zebra_l3_port_cache_actions_str[
                              l3_port->port_action]);
  zebra_dump_formatted_string(ds,"     Port state is: %s\n",
                              l3_port->if_active ? "Active" : "Inactive");

  zebra_dump_formatted_string(ds,"     Printing the IPv4 seconary address in the port\n");

  if (!shash_count(&(l3_port->ip4_address_secondary)))
    zebra_dump_formatted_string(ds,"         No IPv4 seconary address in the port\n");
  else
    {
      secondary_address_count = 0;
      SHASH_FOR_EACH_SAFE (node, next, &(l3_port->ip4_address_secondary))
        {
          if (!node)
            {
              zebra_dump_formatted_string(ds,"No node found in the L3 port hash\n");
              continue;
            }

          if (!(node->data))
            {
              zebra_dump_formatted_string(ds,"No node data found\n");
              continue;
            }

          ip_secondary_address = (char*)node->data;
          ++secondary_address_count;

          zebra_dump_formatted_string(ds,"         %d. Address %s\n", secondary_address_count,
                                      ip_secondary_address);

        }
    }

  zebra_dump_formatted_string(ds,"     Printing the IPv4 connected route UUIDs in the port\n");

  if (!shash_count(&(l3_port->ip4_connected_routes_uuid)))
    zebra_dump_formatted_string(ds,"         No IPv4 connected route UUIDs in the port\n");
  else
    {
      route_uuid_count = 0;
      SHASH_FOR_EACH_SAFE (node, next, &(l3_port->ip4_connected_routes_uuid))
        {
          if (!node)
            {
              zebra_dump_formatted_string(ds,"No node found in the L3 port hash\n");
              continue;
            }

          if (!(node->data))
            {
              zebra_dump_formatted_string(ds,"No node data found\n");
              continue;
            }

          connected_route_uuid = (struct uuid*)node->data;
          ++route_uuid_count;

          zebra_dump_formatted_string(ds,"         %d. IPv4 connected route UUID %s\n",
                                      route_uuid_count,
                                      zebra_dump_ovsdb_uuid(connected_route_uuid));

        }
    }

  zebra_dump_formatted_string(ds,"     Printing the IPv6 seconary address in the port\n");

  if (!shash_count(&(l3_port->ip6_address_secondary)))
    zebra_dump_formatted_string(ds,"         No IPv6 seconary address in the port\n");
  else
    {
      secondary_address_count = 0;
      SHASH_FOR_EACH_SAFE (node, next, &(l3_port->ip6_address_secondary))
        {
          if (!node)
            {
              zebra_dump_formatted_string(ds,"No node found in the L3 port hash\n");
              continue;
            }

          if (!(node->data))
            {
              zebra_dump_formatted_string(ds,"No node data found\n");
               continue;
            }

          ip_secondary_address = (char*)node->data;
          ++secondary_address_count;

          zebra_dump_formatted_string(ds,"         %d. Address %s\n",
                                      secondary_address_count,
                                      ip_secondary_address);

        }
    }

  zebra_dump_formatted_string(ds,"     Printing the IPv6 connected route UUIDs in the port\n");

  if (!shash_count(&(l3_port->ip6_connected_routes_uuid)))
    zebra_dump_formatted_string(ds,"         No IPv6 connected route"
                                "UUIDs in the port\n");
  else
    {
      route_uuid_count = 0;
      SHASH_FOR_EACH_SAFE (node, next, &(l3_port->ip6_connected_routes_uuid))
        {
          if (!node)
            {
              zebra_dump_formatted_string(ds,"No node found in the L3 port hash\n");
              continue;
            }

          if (!(node->data))
            {
              zebra_dump_formatted_string(ds,"No node data found\n");
              continue;
            }

          connected_route_uuid = (struct uuid*)node->data;
          ++route_uuid_count;

          zebra_dump_formatted_string(ds,"         %d. IPv6 connected route UUID %s\n",
                                      route_uuid_count,
                                      zebra_dump_ovsdb_uuid(connected_route_uuid));

        }
    }
}

/*
 * Walk all cached L3 ports in the hash table 'zebra_cached_l3_ports' This is
 * useful for debugging the port/interface triggers.  If the dynamic-string
 * 'ds' is NULL, the formatted string is written to VLOG. Otherwise,
 * it is appended to 'ds'
 */
void
zebra_l3_port_walk_cache_and_print (struct ds *ds,
                                    struct shash* zebra_cached_l3_ports,
                                    bool if_permanent_hash)
{
  struct shash_node *node, *next;
  struct zebra_l3_port* l3_port;

  zebra_dump_formatted_string(ds, "Walking the L3 port cache to print all "
                              "L3 ports in %s cache\n",
                              if_permanent_hash ? "permanent" : "temporary");

  if (!shash_count(zebra_cached_l3_ports))
    {
      zebra_dump_formatted_string(ds, "The hash table is empty. "
                                  "Nothing to walk and print\n");
      return;
    }

  SHASH_FOR_EACH_SAFE (node, next, zebra_cached_l3_ports)
    {
      if (!node)
        {
          zebra_dump_formatted_string(ds, "No node found in the L3 port hash\n");
          continue;
        }

      if (!(node->data))
        {
          zebra_dump_formatted_string(ds, "No node data found\n");
          continue;
        }

      l3_port = (struct zebra_l3_port*)node->data;

      zebra_l3_port_node_print(ds, l3_port);
    }
}

/*
 * This function dumps the details of the next-hops for a given route row in
 * OVSDB route table.
 */
static void
zebra_dump_ovsdb_nexthop_entry (const struct ovsrec_nexthop *nh_row)
{
  int port_index;

  if (!nh_row)
    {
      VLOG_DBG("    The next-hop entry is NULL\n");
      return;
    }

  /*
   * Printing next-hop row parameters.
   */
  VLOG_DBG("    Address = %s %s%s\n", nh_row->ip_address,
           OVSREC_IDL_IS_ROW_INSERTED(nh_row, idl_seqno) ? "(I)":"",
           OVSREC_IDL_IS_ROW_MODIFIED(nh_row, idl_seqno) ? "(M)":"");

  /*
   * Walk the port list for the next-hop and print the details of
   * next-hop.
   */
  for (port_index = 0; port_index < nh_row->n_ports; ++port_index)
    {
      VLOG_DBG("        The next-hop port is %s\n",
              (nh_row->ports[port_index]->name) ?
              nh_row->ports[port_index]->name :
              "NULL");
    }
}

/*
 * This function dumps the details of a route row in OVSDB route table.
 */
static void
zebra_dump_ovsdb_route_entry (const struct ovsrec_route *route_row)
{
  int next_hop_index;
  struct uuid route_uuid;

  if (!route_row)
    {
      VLOG_DBG("The route entry is NULL\n");
      return;
    }

  route_uuid = OVSREC_IDL_GET_TABLE_ROW_UUID(route_row);

  /*
   * Printing the route row details.
   */
  VLOG_DBG("Route = %s AF = %s protocol = %s vrf = %s\n uuid = %s %s%s",
           route_row->prefix ? route_row->prefix : "NULL",
           route_row->address_family ? route_row->address_family : "NULL",
           route_row->from ? route_row->from : "NULL",
           route_row->vrf ? (route_row->vrf->name ? route_row->vrf->name :
                             "NULL") : "NULL",
           zebra_dump_ovsdb_uuid(&route_uuid),
           OVSREC_IDL_IS_ROW_INSERTED(route_row, idl_seqno) ? "(I)":"",
           OVSREC_IDL_IS_ROW_MODIFIED(route_row, idl_seqno) ? "(M)":"");

  /*
   * Walk the array of nxt-hops and print the route's next-hop details.
   */
  for (next_hop_index = 0; next_hop_index < route_row->n_nexthops;
       ++next_hop_index)
    {
      zebra_dump_ovsdb_nexthop_entry(route_row->nexthops[next_hop_index]);
    }
}

/*
 * This function causes the dumps of the entire OVSDB route table.
 */
void
zebra_dump_ovsdb_route_table (void)
{
  const struct ovsrec_route *route_row = NULL;
  int count = 0;

  VLOG_DBG("Printing the OVSDB route table snapshot\n");

  /*
   * Walk all the entries in the OVSDB route table and print all the
   * route entries.
   */
  OVSREC_ROUTE_FOR_EACH (route_row, idl)
    {
      if (route_row)
        {
          ++count;
          zebra_dump_ovsdb_route_entry(route_row);
        }
    }

  VLOG_DBG("Total number of route entries in OVSDB route table are %d\n",
           count);
}

/*
 ******************************************************************
 * End of the set of debugging functions for OVSDB zebra interface.
 ******************************************************************
 */

