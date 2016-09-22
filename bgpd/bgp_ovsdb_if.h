/* bgp daemon ovsdb integration.
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

#ifndef BGP_OVSDB_IF_H
#define BGP_OVSDB_IF_H 1

/* data type for memory diag-dump of bgp.
 * TODO These two structure are duplication of hash and hash_backet structure
 * from lib/hash.h. Should future update in lib/hash.h apply, these two structure
 * need to be updated for accurate memory calculation */
struct bgp_mem_hash_backet
{
  /* Linked list.  */
  struct bgp_mem_hash_backet *next;

  /* Hash key. */
  unsigned int key;

  /* Data.  */
  void *data;
};

struct bgp_mem_hash
{
  /* Hash backet. */
  struct bgp_mem_hash_backet **index;

  /* Hash table size. Must be power of 2 */
  unsigned int size;

  /* If expansion failed. */
  int no_expand;

  /* Key make function. */
  unsigned int (*hash_key) (void *);

  /* Data compare function. */
  int (*hash_cmp) (const void *, const void *);

  /* Backet alloc. */
  unsigned long count;
};

/* Setup zebra to connect with ovsdb and daemonize. This daemonize is used
 * over the daemonize in the main function to keep the behavior consistent
 * with the other daemons in the OpenSwitch system
 */
void bgp_ovsdb_init(int argc, char *argv[]);

/* When the daemon is ready to shut, delete the idl cache
 * This happens with the ovs-appctl exit command.
 */
void bgp_ovsdb_exit(void);

/*
** Original names are soo long.. exceeds 80 chars,
** shorten them a bit
*/
#define ANY_NEW_ROW			OVSREC_IDL_ANY_TABLE_ROWS_INSERTED
#define ANY_ROW_CHANGED			OVSREC_IDL_ANY_TABLE_ROWS_MODIFIED
#define ANY_ROW_DELETED			OVSREC_IDL_ANY_TABLE_ROWS_DELETED
#define NEW_ROW				OVSREC_IDL_IS_ROW_INSERTED
#define ROW_CHANGED			OVSREC_IDL_IS_ROW_MODIFIED
/* row is not used now but may be in the future */
#define COL_CHANGED(row, col, s)	OVSREC_IDL_IS_COLUMN_MODIFIED(col, s)

/* Initialize and integrate the ovs poll loop with the daemon */
void bgp_ovsdb_init_poll_loop (struct bgp_master *bm);
boolean  get_global_ecmp_status(void);

#endif /* BGP_OVSDB_IF_H */
